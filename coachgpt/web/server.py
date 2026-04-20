"""FastAPI web server for CoachGPT."""

import hashlib
import json
import os
import queue
import secrets
import threading
import time
import traceback
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from coachgpt import database as db
from coachgpt.pipeline import (
    process_game, process_game_image, process_game_pdf,
    scout_opponent, generate_pregame_brief, lookup_opponent,
)
from coachgpt.league_import import parse_league_standings, parse_webarchive_schedule, save_league_data

app = FastAPI(title="CoachGPT", docs_url=None, redoc_url=None, openapi_url=None)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Auth: user-based (SQLite) or fallback to single password (env var)
APP_PASSWORD = os.environ.get("COACHGPT_PASSWORD", "")
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
SECURE_COOKIES = os.environ.get("COACHGPT_HTTPS", "").lower() in ("true", "1", "yes")
# token → {"username": str, "display_name": str, "role": str, "expires_at": float}
_active_sessions: dict[str, dict] = {}


def _get_session(token: str) -> dict | None:
    """Return session if valid and not expired, else evict and return None."""
    session = _active_sessions.get(token)
    if not session:
        return None
    if time.monotonic() > session.get("expires_at", 0):
        _active_sessions.pop(token, None)
        return None
    return session


def _hash_password(password: str) -> str:
    """Hash a password with SHA-256 + salt prefix."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its stored hash."""
    salt, stored_hash = password_hash.split(":", 1)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return secrets.compare_digest(h, stored_hash)


def _seed_default_user():
    """Create Coach Jason Peay if no users exist. Requires COACHGPT_DEFAULT_PASSWORD env var."""
    users = db.list_users()
    if not users:
        default_pw = os.environ.get("COACHGPT_DEFAULT_PASSWORD", "")
        if not default_pw:
            import logging
            logging.warning(
                "COACHGPT_DEFAULT_PASSWORD not set — skipping default user seed. "
                "Set this env var to create the initial coach account."
            )
            return
        db.create_user(
            username="jpeay",
            password_hash=_hash_password(default_pw),
            display_name="Coach Jason Peay",
            role="coach",
        )


def _has_users() -> bool:
    """Check if user-based auth is available (users table has entries)."""
    return len(db.list_users()) > 0


# ── Rate Limiting ────────────────────────────────────────────────
_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = int(os.environ.get("COACHGPT_RATE_LIMIT", "30"))  # requests per window
RATE_WINDOW = int(os.environ.get("COACHGPT_RATE_WINDOW", "60"))  # seconds


LOGIN_RATE_LIMIT = 5  # max login attempts per window
LOGIN_RATE_WINDOW = 300  # 5 minutes
_login_buckets: dict[str, list[float]] = defaultdict(list)
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB
MAX_NOTES_LENGTH = 10_000
MAX_METADATA_LENGTH = 1_000
MAX_OPPONENT_LENGTH = 200


def _get_client_ip(request: Request) -> str:
    """Get real client IP, handling reverse proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.monotonic()
    bucket = _rate_buckets[client_ip]
    _rate_buckets[client_ip] = [t for t in bucket if now - t < RATE_WINDOW]
    if len(_rate_buckets[client_ip]) >= RATE_LIMIT:
        return False
    _rate_buckets[client_ip].append(now)
    return True


def _check_login_rate(client_ip: str) -> bool:
    """Stricter rate limit for login attempts."""
    now = time.monotonic()
    bucket = _login_buckets[client_ip]
    _login_buckets[client_ip] = [t for t in bucket if now - t < LOGIN_RATE_WINDOW]
    if len(_login_buckets[client_ip]) >= LOGIN_RATE_LIMIT:
        return False
    _login_buckets[client_ip].append(now)
    return True


# ── Security Headers + Auth + Rate Limit Middleware ──────────────
@app.middleware("http")
async def auth_and_rate_limit(request: Request, call_next):
    path = request.url.path

    # Skip auth for known static assets, login, and health check.
    # NOTE: /static serves only frontend assets (index.html, CSS, JS, images).
    # Never place data, config, or sensitive files in the static/ directory.
    _public_paths = ("/static/index.html", "/login", "/health")
    if any(path.startswith(p) or path == p for p in _public_paths):
        response = await call_next(request)
        _add_security_headers(response)
        return response

    # Rate limit all requests
    client_ip = _get_client_ip(request)
    if not _check_rate_limit(client_ip):
        return JSONResponse(
            {"error": "Too many requests. Please wait before trying again."},
            status_code=429,
        )

    # Auth check — user-based or single-password
    auth_required = _has_users() or APP_PASSWORD
    if auth_required and path != "/" and path != "/logout":
        token = request.cookies.get("coachgpt_token")
        if not _get_session(token):
            if path.startswith("/api/"):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return RedirectResponse("/")

    response = await call_next(request)
    _add_security_headers(response)
    return response


def _add_security_headers(response):
    """Add standard security headers to all responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )


def _safe_error(e: Exception) -> str:
    """Sanitize error messages — never expose internal paths, AWS details, or tracebacks."""
    import sqlite3
    # Database errors may reveal schema details — never expose
    if isinstance(e, sqlite3.Error):
        return "Database error. Please try again."
    msg = str(e)
    # Strip filesystem paths
    if "/" in msg or "\\" in msg:
        return "An internal error occurred. Please try again."
    # Strip AWS/Bedrock details
    for keyword in ["arn:", "aws", "bedrock", "AccessDenied", "throttl", "credential"]:
        if keyword.lower() in msg.lower():
            return "AI service temporarily unavailable. Please try again."
    return msg


def _strip_internal_fields(result: dict) -> dict:
    """Remove internal fields before sending to frontend."""
    result.pop("report_path", None)
    result.pop("analysis", None)
    return result


@app.get("/health")
async def health():
    # Public endpoint for load balancer checks. Keep minimal — never return
    # version info, uptime, database stats, or any internal state.
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    auth_required = _has_users() or APP_PASSWORD
    if auth_required:
        token = request.cookies.get("coachgpt_token")
        if not _get_session(token):
            return HTMLResponse(_login_page())
    return (STATIC_DIR / "index.html").read_text()


@app.post("/login")
async def login(request: Request):
    client_ip = _get_client_ip(request)
    if not _check_login_rate(client_ip):
        return HTMLResponse(_login_page(error="Too many attempts. Try again in 5 minutes."))

    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")

    # Try user-based auth first
    if _has_users() and username:
        user = db.get_user_by_username(username)
        if user and _verify_password(password, user["password_hash"]):
            token = secrets.token_hex(32)
            _active_sessions[token] = {
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
                "expires_at": time.monotonic() + SESSION_MAX_AGE,
            }
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(
                "coachgpt_token", token, max_age=SESSION_MAX_AGE,
                httponly=True, samesite="strict", secure=SECURE_COOKIES,
            )
            return response
        return HTMLResponse(_login_page(error="Invalid username or password."))

    # Fallback: single password mode (no username required)
    if APP_PASSWORD and secrets.compare_digest(password, APP_PASSWORD):
        token = secrets.token_hex(32)
        _active_sessions[token] = {
            "username": "coach",
            "display_name": "Coach",
            "role": "coach",
            "expires_at": time.monotonic() + SESSION_MAX_AGE,
        }
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            "coachgpt_token", token, max_age=SESSION_MAX_AGE,
            httponly=True, samesite="strict",
        )
        return response

    return HTMLResponse(_login_page(error="Invalid username or password."))


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("coachgpt_token")
    if token:
        _active_sessions.pop(token, None)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("coachgpt_token")
    return response


@app.get("/api/me")
async def api_me(request: Request):
    """Return current user info for the frontend."""
    token = request.cookies.get("coachgpt_token")
    session = _get_session(token)
    if session:
        return JSONResponse({
            "signed_in": True,
            "display_name": session["display_name"],
            "username": session["username"],
            "role": session["role"],
        })
    return JSONResponse({"signed_in": False})


def _login_page(error=""):
    from html import escape as _esc
    err_html = f'<p style="color:#ff453a;margin-bottom:16px;">{_esc(error)}</p>' if error else ''
    # Show username field if users exist, otherwise password-only
    has_users = _has_users()
    username_field = (
        '<input type="text" name="username" placeholder="Username" autofocus '
        'style="margin-bottom:12px;" autocapitalize="none" autocorrect="off">'
        if has_users else ''
    )
    autofocus = '' if has_users else ' autofocus'
    subtitle = 'Sign in to continue' if has_users else 'Enter password to continue'
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>CoachGPT — Login</title>
    <style>body{{font-family:-apple-system,sans-serif;background:#0f1117;color:#e4e6ed;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;}}
    .box{{background:#1a1d27;border:1px solid #2e3345;border-radius:16px;padding:40px;width:320px;text-align:center;}}
    h1{{font-size:24px;margin-bottom:8px;}}h1 span{{color:#4f8ff7;}}
    p.sub{{color:#9298a8;font-size:14px;margin-bottom:24px;}}
    input{{width:100%;padding:12px;background:#242836;border:1px solid #2e3345;border-radius:8px;color:#e4e6ed;font-size:15px;box-sizing:border-box;}}
    input:focus{{outline:none;border-color:#4f8ff7;}}
    button{{width:100%;padding:12px;background:#4f8ff7;color:#fff;border:none;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;margin-top:16px;}}
    button:hover{{background:#3b7ae0;}}</style></head>
    <body><div class="box"><h1>Coach<span>GPT</span></h1><p class="sub">{subtitle}</p>
    {err_html}
    <form method="POST" action="/login">{username_field}
    <input type="password" name="password" placeholder="Password"{autofocus}>
    <button type="submit">Sign In</button></form></div></body></html>"""


# ── SSE Streaming Game Processing ────────────────────────────────

@app.post("/api/game/stream")
async def api_process_game_stream(
    notes: str = Form(""),
    metadata: str = Form(""),
    file: UploadFile | None = File(None),
):
    """Process a game and stream agent progress via SSE."""
    # Input validation
    if len(notes) > MAX_NOTES_LENGTH:
        return JSONResponse({"error": f"Notes too long (max {MAX_NOTES_LENGTH} chars)."}, status_code=400)
    if len(metadata) > MAX_METADATA_LENGTH:
        return JSONResponse({"error": f"Metadata too long (max {MAX_METADATA_LENGTH} chars)."}, status_code=400)

    # Read file upfront (before generator)
    file_bytes = None
    content_type = ""
    filename = ""
    if file and file.filename:
        file_bytes = await file.read()
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            return JSONResponse({"error": "File too large (max 20MB)."}, status_code=400)
        content_type = file.content_type or ""
        filename = file.filename.lower()

    def generate():
        q = queue.Queue()

        def callback(agent, step, detail):
            q.put({"agent": agent, "step": step, "detail": detail})

        def run_pipeline():
            try:
                if file_bytes:
                    if "pdf" in content_type or filename.endswith(".pdf"):
                        result = process_game_pdf(
                            pdf_bytes=file_bytes, coach_notes=notes,
                            metadata=metadata, callback=callback,
                        )
                    elif filename.endswith(".csv"):
                        csv_text = file_bytes.decode("utf-8")
                        combined = f"Game info: {metadata}\n\nCSV DATA:\n{csv_text}"
                        if notes:
                            combined += f"\n\nCoach notes:\n{notes}"
                        result = process_game(combined, callback=callback)
                    elif any(content_type.startswith(t) for t in
                             ["image/png", "image/jpeg", "image/webp", "image/gif"]):
                        result = process_game_image(
                            image_bytes=file_bytes, media_type=content_type,
                            coach_notes=notes, metadata=metadata,
                            callback=callback,
                        )
                    else:
                        text = file_bytes.decode("utf-8", errors="ignore")
                        combined = text
                        if metadata:
                            combined = f"Game info: {metadata}\n\n{combined}"
                        if notes:
                            combined += f"\n\nCoach notes:\n{notes}"
                        result = process_game(combined, callback=callback)
                elif notes or metadata:
                    combined = ""
                    if metadata:
                        combined += f"Game info: {metadata}\n\n"
                    combined += notes
                    result = process_game(combined, callback=callback)
                else:
                    q.put({"error": "No data provided."})
                    q.put(None)
                    return

                q.put({"result": _strip_internal_fields(result)})
            except Exception as e:
                traceback.print_exc()
                q.put({"error": _safe_error(e)})
            q.put(None)  # Signal done

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        while True:
            try:
                item = q.get(timeout=120)
            except queue.Empty:
                yield f"data: {json.dumps({'error': 'Request timed out. Please try again.'})}\n\n"
                break
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/scout/{opponent}/stream")
async def api_scout_stream(opponent: str):
    """Scout an opponent and stream agent progress via SSE."""
    if len(opponent) > MAX_OPPONENT_LENGTH:
        return JSONResponse({"error": "Opponent name too long."}, status_code=400)
    def generate():
        q = queue.Queue()

        def callback(agent, step, detail):
            q.put({"agent": agent, "step": step, "detail": detail})

        def run_pipeline():
            try:
                result = scout_opponent(opponent, callback=callback)
                if "error" in result:
                    q.put({"error": result["error"]})
                else:
                    q.put({"result": _strip_internal_fields(result)})
            except Exception as e:
                traceback.print_exc()
                q.put({"error": _safe_error(e)})
            q.put(None)

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        while True:
            try:
                item = q.get(timeout=120)
            except queue.Empty:
                yield f"data: {json.dumps({'error': 'Request timed out. Please try again.'})}\n\n"
                break
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/pregame/{opponent}/stream")
async def api_pregame_stream(opponent: str):
    """Generate a pre-game brief and stream agent progress via SSE."""
    if len(opponent) > MAX_OPPONENT_LENGTH:
        return JSONResponse({"error": "Opponent name too long."}, status_code=400)
    def generate():
        q = queue.Queue()

        def callback(agent, step, detail):
            q.put({"agent": agent, "step": step, "detail": detail})

        def run_pipeline():
            try:
                result = generate_pregame_brief(opponent, callback=callback)
                if "error" in result:
                    q.put({"error": result["error"]})
                else:
                    q.put({"result": _strip_internal_fields(result)})
            except Exception as e:
                traceback.print_exc()
                q.put({"error": _safe_error(e)})
            q.put(None)

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        while True:
            try:
                item = q.get(timeout=120)
            except queue.Empty:
                yield f"data: {json.dumps({'error': 'Request timed out. Please try again.'})}\n\n"
                break
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/research/{opponent}/stream")
async def api_research_stream(opponent: str, league_info: str = ""):
    """Research an opponent we haven't played — find their record online."""
    if len(opponent) > MAX_OPPONENT_LENGTH:
        return JSONResponse({"error": "Opponent name too long."}, status_code=400)
    def generate():
        q = queue.Queue()

        def callback(agent, step, detail):
            q.put({"agent": agent, "step": step, "detail": detail})

        def run_pipeline():
            try:
                result = lookup_opponent(opponent, league_info, callback=callback)
                if "error" in result:
                    q.put({"error": result["error"]})
                else:
                    result.pop("research", None)
                    q.put({"result": _strip_internal_fields(result)})
            except Exception as e:
                traceback.print_exc()
                q.put({"error": _safe_error(e)})
            q.put(None)

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        while True:
            try:
                item = q.get(timeout=120)
            except queue.Empty:
                yield f"data: {json.dumps({'error': 'Request timed out. Please try again.'})}\n\n"
                break
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Standard JSON Endpoints (unchanged) ──────────────────────────

@app.post("/api/game")
async def api_process_game(
    notes: str = Form(""),
    metadata: str = Form(""),
    file: UploadFile | None = File(None),
):
    """Process a game (non-streaming fallback)."""
    if len(notes) > MAX_NOTES_LENGTH:
        return JSONResponse({"error": f"Notes too long (max {MAX_NOTES_LENGTH} chars)."}, status_code=400)
    if len(metadata) > MAX_METADATA_LENGTH:
        return JSONResponse({"error": f"Metadata too long (max {MAX_METADATA_LENGTH} chars)."}, status_code=400)
    try:
        if file and file.filename:
            file_bytes = await file.read()
            if len(file_bytes) > MAX_UPLOAD_SIZE:
                return JSONResponse({"error": "File too large (max 20MB)."}, status_code=400)
            content_type = file.content_type or ""
            filename = file.filename.lower()

            if "pdf" in content_type or filename.endswith(".pdf"):
                result = process_game_pdf(pdf_bytes=file_bytes, coach_notes=notes, metadata=metadata)
            elif filename.endswith(".csv"):
                csv_text = file_bytes.decode("utf-8")
                combined = f"Game info: {metadata}\n\nCSV DATA:\n{csv_text}"
                if notes:
                    combined += f"\n\nCoach notes:\n{notes}"
                result = process_game(combined)
            elif any(content_type.startswith(t) for t in ["image/png", "image/jpeg", "image/webp", "image/gif"]):
                result = process_game_image(image_bytes=file_bytes, media_type=content_type, coach_notes=notes, metadata=metadata)
            else:
                text = file_bytes.decode("utf-8", errors="ignore")
                combined = text
                if metadata:
                    combined = f"Game info: {metadata}\n\n{combined}"
                if notes:
                    combined += f"\n\nCoach notes:\n{notes}"
                result = process_game(combined)
        elif notes or metadata:
            combined = ""
            if metadata:
                combined += f"Game info: {metadata}\n\n"
            combined += notes
            result = process_game(combined)
        else:
            return JSONResponse({"error": "No data provided."}, status_code=400)

        return JSONResponse(_strip_internal_fields(result))
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": _safe_error(e)}, status_code=500)


@app.post("/api/scout/{opponent}")
async def api_scout(opponent: str):
    try:
        result = scout_opponent(opponent)
        if "error" in result:
            return JSONResponse(result, status_code=404)
        return JSONResponse(_strip_internal_fields(result))
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": _safe_error(e)}, status_code=500)


@app.post("/api/league/import")
async def api_import_league(
    standings_text: str = Form(""),
    team_name: str = Form(""),
    season_name: str = Form(""),
    file: UploadFile | None = File(None),
):
    """Import league data from pasted text, webarchive, or PDF."""
    try:
        result = None

        if file and file.filename:
            file_bytes = await file.read()
            filename = file.filename.lower()

            if filename.endswith(".webarchive"):
                result = parse_webarchive_schedule(file_bytes, team_name)
            elif filename.endswith(".pdf"):
                # Use Claude Vision to read the schedule PDF
                import base64
                from coachgpt.ai_client import get_client, HAIKU
                client = get_client()
                b64 = base64.b64encode(file_bytes).decode()
                resp = client.messages.create(
                    model=HAIKU,
                    max_tokens=4096,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                            {"type": "text", "text": "Extract all game results from this schedule. For each game list: visitor team, visitor score, home team, home score. Also extract any standings tables. Output as plain text."},
                        ]
                    }],
                )
                extracted_text = resp.content[0].text
                result = parse_league_standings(extracted_text, team_name, season_name)
            else:
                # Try as text file
                text = file_bytes.decode("utf-8", errors="ignore")
                result = parse_league_standings(text, team_name, season_name)

        elif standings_text:
            result = parse_league_standings(standings_text, team_name, season_name)
        else:
            return JSONResponse({"error": "No data provided. Paste standings or upload a file."}, status_code=400)

        if not result:
            return JSONResponse({"error": "Could not parse league data."}, status_code=400)

        if "error" in result:
            return JSONResponse(result, status_code=400)

        save_league_data(result)
        return JSONResponse(result)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": _safe_error(e)}, status_code=500)


@app.get("/api/leagues")
async def api_list_leagues():
    """List all imported league standings."""
    import json as jsonlib
    reports = db.get_reports(report_type="league_standings")
    leagues = []
    for r in reports:
        name = r.get("opponent", "League")
        try:
            data = jsonlib.loads(r.get("analysis_json", "{}"))
            teams_count = data.get("teams_count", 0)
        except Exception:
            teams_count = 0
        leagues.append({
            "id": r["id"],
            "name": name,
            "created_at": r["created_at"],
            "teams_count": teams_count,
        })
    return JSONResponse(leagues)


@app.get("/api/league/{league_id}")
async def api_get_league(league_id: str):
    """Get a specific league import's full data."""
    import json as jsonlib
    reports = db.get_reports(report_type="league_standings")
    for r in reports:
        if r["id"] == league_id:
            try:
                data = jsonlib.loads(r.get("analysis_json", "{}"))
                return JSONResponse(data)
            except Exception:
                return JSONResponse({"report_text": r.get("report_text", "")})
    return JSONResponse({"error": "League not found"}, status_code=404)


@app.get("/api/games")
async def api_list_games(opponent: str = None):
    return JSONResponse(db.list_games(opponent=opponent))


@app.get("/api/game/{game_id}")
async def api_get_game(game_id: str):
    data = db.get_full_game_data(game_id)
    if not data:
        return JSONResponse({"error": "Game not found"}, status_code=404)
    return JSONResponse(data)


@app.get("/api/reports")
async def api_list_reports(opponent: str = None, report_type: str = None):
    return JSONResponse(db.get_reports(opponent=opponent, report_type=report_type))


@app.get("/api/opponents")
async def api_list_opponents():
    games = db.list_games(limit=200)
    opponents = sorted(set(g["opponent"] for g in games if g.get("opponent")))
    return JSONResponse(opponents)


# ── Season Endpoints ─────────────────────────────────────────────

@app.post("/api/season/import")
async def api_import_season(
    season_name: str = Form(""),
    team_name: str = Form(""),
    file: UploadFile = File(...),
):
    """Import a GameChanger season stats CSV."""
    from coachgpt.season_import import import_season_csv
    try:
        csv_bytes = await file.read()
        csv_text = csv_bytes.decode("utf-8", errors="ignore")

        if not season_name:
            season_name = "Imported Season"
        if not team_name:
            team_name = "My Team"

        result = import_season_csv(csv_text, season_name, team_name)
        return JSONResponse(result)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": _safe_error(e)}, status_code=500)


@app.get("/api/seasons")
async def api_list_seasons():
    return JSONResponse(db.get_seasons())


@app.get("/api/season/{season_id}")
async def api_get_season(season_id: str):
    data = db.get_full_season_data(season_id)
    if not data:
        return JSONResponse({"error": "Season not found"}, status_code=404)
    return JSONResponse(data)


@app.post("/api/game/followup")
async def api_game_followup(request: Request):
    """Save post-game follow-up notes: GC link, tendencies, adjustments."""
    import re
    data = await request.json()
    game_id = data.get("game_id")
    opponent = data.get("opponent", "")
    date = data.get("date", "")
    gc_link = data.get("gc_link", "")
    tendencies = data.get("tendencies", "")
    adjustments = data.get("adjustments", "")

    players_added = 0
    observations_added = 0

    # Save GC link as observation (only if we have a game)
    if gc_link and game_id:
        db.add_observations(game_id, [{
            "category": "general",
            "detail": f"GameChanger recap: {gc_link}",
            "source": "postgame_followup",
        }])
        observations_added += 1

    # Parse tendencies — look for #number patterns
    if tendencies:
        for line in tendencies.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            match = re.match(r'#(\d+)\s+(.+)', line)
            if match:
                number, tendency = match.group(1), match.group(2).strip()
                db.upsert_opponent_player(
                    opponent_team=opponent, number=number,
                    tendency=tendency, game_date=date,
                )
                players_added += 1
            elif game_id:
                db.add_observations(game_id, [{
                    "category": "opponent_tendency",
                    "detail": line,
                    "source": "postgame_followup",
                }])
                observations_added += 1

    # Save adjustments (only if we have a game)
    if adjustments and game_id:
        for line in adjustments.strip().split("\n"):
            line = line.strip()
            if line:
                db.add_observations(game_id, [{
                    "category": "adjustment",
                    "detail": f"For next time: {line}",
                    "source": "postgame_followup",
                }])
                observations_added += 1

    return JSONResponse({
        "players_added": players_added,
        "observations_added": observations_added,
    })


@app.get("/api/opponent-players/{opponent}")
async def api_opponent_players(opponent: str):
    players = db.get_opponent_players(opponent)
    return JSONResponse(players)


@app.post("/api/opponent-player/{player_id}/update")
async def api_update_opponent_player(player_id: str, request: Request):
    """Update or delete tendencies for an opponent player."""
    import json as jsonlib
    data = await request.json()
    action = data.get("action")  # "delete_tendency", "add_tendency", "delete_player"

    conn = db.get_connection()
    try:
        row = conn.execute("SELECT * FROM opponent_players WHERE id = ?", (player_id,)).fetchone()
        if not row:
            return JSONResponse({"error": "Player not found"}, status_code=404)

        if action == "delete_player":
            conn.execute("DELETE FROM opponent_players WHERE id = ?", (player_id,))
            conn.commit()
            return JSONResponse({"ok": True})

        tendencies = jsonlib.loads(row["tendencies"] or "[]")

        if action == "delete_tendency":
            idx = data.get("index", -1)
            if 0 <= idx < len(tendencies):
                tendencies.pop(idx)
                conn.execute("UPDATE opponent_players SET tendencies = ? WHERE id = ?",
                             (jsonlib.dumps(tendencies), player_id))
                conn.commit()

        elif action == "add_tendency":
            new_tendency = data.get("tendency", "").strip()
            if new_tendency and new_tendency not in tendencies:
                tendencies.append(new_tendency)
                conn.execute("UPDATE opponent_players SET tendencies = ? WHERE id = ?",
                             (jsonlib.dumps(tendencies), player_id))
                conn.commit()

        return JSONResponse({"ok": True, "tendencies": tendencies})
    finally:
        conn.close()


@app.get("/api/opponent-players")
async def api_all_opponent_players():
    players = db.get_all_opponent_players()
    return JSONResponse(players)


@app.get("/api/player-cards")
async def api_player_cards():
    """Return aggregated player card data from per-game box scores."""
    return JSONResponse(db.get_player_cards())


# ── Coach Notes API ─────────────────────────────────────────────

@app.get("/api/notes")
async def api_list_notes():
    return JSONResponse(db.list_coach_notes())


@app.get("/api/note/{note_id}")
async def api_get_note(note_id: str):
    note = db.get_coach_note(note_id)
    if not note:
        return JSONResponse({"error": "Note not found"}, status_code=404)
    return JSONResponse(note)


@app.post("/api/note")
async def api_save_note(request: Request):
    data = await request.json()
    note_id = data.get("id", str(__import__('uuid').uuid4())[:8])
    content = data.get("content", "")
    opponent = data.get("opponent", "")
    date = data.get("date", "")
    db.save_coach_note(note_id, content, opponent, date)
    return JSONResponse({"id": note_id, "ok": True})


@app.delete("/api/note/{note_id}")
async def api_delete_note(note_id: str):
    db.delete_coach_note(note_id)
    return JSONResponse({"ok": True})


@app.post("/api/season/{season_id}/identity")
async def api_team_identity(season_id: str):
    """Generate a team identity report for a season."""
    from coachgpt.agents.report_writer import write_team_identity
    try:
        data = db.get_full_season_data(season_id)
        if not data:
            return JSONResponse({"error": "Season not found"}, status_code=404)

        report_text = write_team_identity(data)

        db.save_report(game_id=None, opponent=data["season"]["team_name"],
                       report_type="team_identity",
                       analysis_json="", report_text=report_text)

        return JSONResponse({"report_text": report_text})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": _safe_error(e)}, status_code=500)


@app.get("/api/guide")
async def api_guide():
    # NOTE: Paths are hardcoded constants — never make dynamic or user-controlled.
    for p in [
        Path(__file__).parent.parent.parent / "COACH-GUIDE.md",
        Path("/app/COACH-GUIDE.md"),  # Container path
    ]:
        if p.exists():
            return JSONResponse({"content": p.read_text()})
    return JSONResponse({"content": "Guide not found."})


def start():
    import logging
    db.init_db()
    _seed_default_user()
    if not APP_PASSWORD and not _has_users():
        logging.warning(
            "WARNING: No users and no COACHGPT_PASSWORD — all endpoints are publicly accessible. "
            "Set COACHGPT_PASSWORD or create users for production deployments."
        )
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    start()
