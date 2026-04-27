"""SQLite database schema and operations for CoachGPT."""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

# Use RAILWAY_VOLUME_MOUNT_PATH if on Railway, otherwise local
_data_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", str(Path(__file__).parent.parent / "data"))
DB_PATH = Path(_data_dir) / "games.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS games (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            opponent TEXT NOT NULL,
            our_team TEXT,
            location TEXT,
            game_type TEXT DEFAULT 'league',  -- league, tournament, scrimmage, playoff
            event_name TEXT,                  -- 'HCRPS 8th Grade', 'MD Sting Classic', etc.
            result TEXT,          -- 'W' or 'L'
            our_score INTEGER,
            opp_score INTEGER,
            notes TEXT,           -- raw coach notes
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS player_stats (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            team TEXT NOT NULL,   -- 'ours' or 'opponent'
            player_name TEXT,
            player_number TEXT,
            minutes INTEGER,
            points INTEGER DEFAULT 0,
            fg_made INTEGER DEFAULT 0,
            fg_attempted INTEGER DEFAULT 0,
            three_made INTEGER DEFAULT 0,
            three_attempted INTEGER DEFAULT 0,
            ft_made INTEGER DEFAULT 0,
            ft_attempted INTEGER DEFAULT 0,
            rebounds INTEGER DEFAULT 0,
            off_rebounds INTEGER DEFAULT 0,
            def_rebounds INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            steals INTEGER DEFAULT 0,
            blocks INTEGER DEFAULT 0,
            turnovers INTEGER DEFAULT 0,
            fouls INTEGER DEFAULT 0,
            source TEXT DEFAULT 'manual'  -- 'gamechanger', 'manual', 'cv'
        );

        CREATE TABLE IF NOT EXISTS team_stats (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            team TEXT NOT NULL,   -- 'ours' or 'opponent'
            quarter TEXT,         -- 'Q1', 'Q2', 'Q3', 'Q4', 'OT', 'total'
            points INTEGER DEFAULT 0,
            fg_made INTEGER DEFAULT 0,
            fg_attempted INTEGER DEFAULT 0,
            three_made INTEGER DEFAULT 0,
            three_attempted INTEGER DEFAULT 0,
            ft_made INTEGER DEFAULT 0,
            ft_attempted INTEGER DEFAULT 0,
            rebounds INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            steals INTEGER DEFAULT 0,
            blocks INTEGER DEFAULT 0,
            turnovers INTEGER DEFAULT 0,
            fouls INTEGER DEFAULT 0,
            source TEXT DEFAULT 'manual'
        );

        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            category TEXT NOT NULL,  -- 'opponent_tendency', 'adjustment', 'key_play', 'general'
            detail TEXT NOT NULL,
            quarter TEXT,
            source TEXT DEFAULT 'coach_notes'
        );

        CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL REFERENCES games(id),
            file_path TEXT,
            tag TEXT,              -- 'transition', 'half_court', 'defense', 'highlight', etc.
            quarter TEXT,
            timestamp_start TEXT,
            timestamp_end TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            game_id TEXT,
            opponent TEXT,
            report_type TEXT NOT NULL,  -- 'postgame', 'scouting', 'trend'
            analysis_json TEXT,         -- raw analysis from analyst agent
            report_text TEXT,           -- final report from report writer
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS opponent_players (
            id TEXT PRIMARY KEY,
            opponent_team TEXT NOT NULL,
            number TEXT,
            name TEXT,
            tendencies TEXT,      -- JSON array of tendency strings
            games_seen INTEGER DEFAULT 1,
            last_seen_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_opp_players_team ON opponent_players(opponent_team);

        CREATE TABLE IF NOT EXISTS seasons (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,         -- 'Fall 2025', 'Spring 2026'
            team_name TEXT NOT NULL,    -- 'Maryland Sting - Peay 2031 13U'
            start_date TEXT,
            end_date TEXT,
            games_played INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS roster (
            id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            number TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS season_roster (
            id TEXT PRIMARY KEY,
            season_id TEXT NOT NULL REFERENCES seasons(id),
            player_id TEXT NOT NULL REFERENCES roster(id),
            number TEXT,                -- number can change between seasons
            status TEXT DEFAULT 'active',  -- 'active', 'graduated', 'injured', 'inactive'
            games_played INTEGER DEFAULT 0,
            games_started INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            fg_made INTEGER DEFAULT 0,
            fg_attempted INTEGER DEFAULT 0,
            three_made INTEGER DEFAULT 0,
            three_attempted INTEGER DEFAULT 0,
            ft_made INTEGER DEFAULT 0,
            ft_attempted INTEGER DEFAULT 0,
            turnovers INTEGER DEFAULT 0,
            rebounds INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            steals INTEGER DEFAULT 0,
            blocks INTEGER DEFAULT 0,
            fouls INTEGER DEFAULT 0,
            fg_pct REAL DEFAULT 0,
            three_pct REAL DEFAULT 0,
            ft_pct REAL DEFAULT 0,
            ppg REAL DEFAULT 0,
            rpg REAL DEFAULT 0,
            apg REAL DEFAULT 0,
            spg REAL DEFAULT 0,
            bpg REAL DEFAULT 0,
            topg REAL DEFAULT 0,
            source TEXT DEFAULT 'gamechanger'
        );

        CREATE TABLE IF NOT EXISTS team_season_totals (
            id TEXT PRIMARY KEY,
            season_id TEXT NOT NULL REFERENCES seasons(id),
            games_played INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            fg_made INTEGER DEFAULT 0,
            fg_attempted INTEGER DEFAULT 0,
            three_made INTEGER DEFAULT 0,
            three_attempted INTEGER DEFAULT 0,
            ft_made INTEGER DEFAULT 0,
            ft_attempted INTEGER DEFAULT 0,
            turnovers INTEGER DEFAULT 0,
            rebounds INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            steals INTEGER DEFAULT 0,
            blocks INTEGER DEFAULT 0,
            fouls INTEGER DEFAULT 0,
            ppg REAL DEFAULT 0,
            fg_pct REAL DEFAULT 0,
            three_pct REAL DEFAULT 0,
            ft_pct REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT DEFAULT 'coach',  -- 'coach', 'admin', 'viewer'
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scouted_teams (
            id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT,
            event_name TEXT,
            event_id TEXT,
            division TEXT,
            location TEXT,
            gc_team_id TEXT,
            last_seen TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS coach_notes (
            id TEXT PRIMARY KEY,
            opponent TEXT,
            date TEXT,
            content TEXT NOT NULL DEFAULT '',
            status TEXT DEFAULT 'active',   -- 'active', 'used' (attached to a game)
            game_id TEXT,                   -- linked game after processing
            updated_at TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_coach_notes_status ON coach_notes(status);
        CREATE INDEX IF NOT EXISTS idx_scouted_teams_name ON scouted_teams(normalized_name);
        CREATE INDEX IF NOT EXISTS idx_scouted_teams_event ON scouted_teams(event_id);

        CREATE INDEX IF NOT EXISTS idx_player_stats_game ON player_stats(game_id);
        CREATE INDEX IF NOT EXISTS idx_team_stats_game ON team_stats(game_id);
        CREATE INDEX IF NOT EXISTS idx_observations_game ON observations(game_id);
        CREATE INDEX IF NOT EXISTS idx_games_opponent ON games(opponent);
        CREATE INDEX IF NOT EXISTS idx_reports_opponent ON reports(opponent);
        CREATE INDEX IF NOT EXISTS idx_season_roster_season ON season_roster(season_id);
        CREATE INDEX IF NOT EXISTS idx_season_roster_player ON season_roster(player_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_roster_name ON roster(first_name, last_name);
    """)
    conn.commit()

    # Migrate existing databases — add columns if missing (safe to re-run)
    cursor = conn.execute("PRAGMA table_info(games)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    if "game_type" not in existing_cols:
        conn.execute("ALTER TABLE games ADD COLUMN game_type TEXT DEFAULT 'league'")
    if "event_name" not in existing_cols:
        conn.execute("ALTER TABLE games ADD COLUMN event_name TEXT")
    conn.commit()
    conn.close()


# ── User Operations ─────────────────────────────────────────────

def create_user(username: str, password_hash: str, display_name: str,
                role: str = "coach") -> str:
    user_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (id, username, password_hash, display_name, role) VALUES (?, ?, ?, ?, ?)",
        (user_id, username.lower(), password_hash, display_name, role)
    )
    conn.commit()
    conn.close()
    return user_id


def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT id, username, display_name, role, created_at FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_password(user_id: str, password_hash: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_user_display_name(user_id: str, display_name: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ── Game Operations ──────────────────────────────────────────────

def create_game(opponent: str, date: str, our_team: str = None,
                location: str = None, result: str = None,
                our_score: int = None, opp_score: int = None,
                notes: str = None, game_type: str = None,
                event_name: str = None) -> str:
    game_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute(
        """INSERT INTO games (id, date, opponent, our_team, location, result,
           our_score, opp_score, notes, game_type, event_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, date, opponent, our_team, location, result,
         our_score, opp_score, notes, game_type or 'league', event_name)
    )
    conn.commit()
    conn.close()
    return game_id


def get_game(game_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_games(opponent: str = None, limit: int = 50) -> list[dict]:
    conn = get_connection()
    if opponent:
        rows = conn.execute(
            "SELECT * FROM games WHERE opponent LIKE ? ORDER BY date DESC LIMIT ?",
            (f"%{opponent}%", limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM games ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Player Stats Operations ─────────────────────────────────────

def add_player_stats(game_id: str, stats: list[dict]):
    conn = get_connection()
    for s in stats:
        conn.execute(
            """INSERT INTO player_stats (id, game_id, team, player_name,
               player_number, minutes, points, fg_made, fg_attempted,
               three_made, three_attempted, ft_made, ft_attempted,
               rebounds, off_rebounds, def_rebounds, assists, steals,
               blocks, turnovers, fouls, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4())[:8], game_id, s.get("team", "ours"),
             s.get("player_name"), s.get("player_number"),
             s.get("minutes"), s.get("points", 0),
             s.get("fg_made", 0), s.get("fg_attempted", 0),
             s.get("three_made", 0), s.get("three_attempted", 0),
             s.get("ft_made", 0), s.get("ft_attempted", 0),
             s.get("rebounds", 0), s.get("off_rebounds", 0),
             s.get("def_rebounds", 0), s.get("assists", 0),
             s.get("steals", 0), s.get("blocks", 0),
             s.get("turnovers", 0), s.get("fouls", 0),
             s.get("source", "manual"))
        )
    conn.commit()
    conn.close()


def get_player_stats(game_id: str, team: str = None) -> list[dict]:
    conn = get_connection()
    if team:
        rows = conn.execute(
            "SELECT * FROM player_stats WHERE game_id = ? AND team = ?",
            (game_id, team)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM player_stats WHERE game_id = ?", (game_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Team Stats Operations ───────────────────────────────────────

def add_team_stats(game_id: str, stats: list[dict]):
    conn = get_connection()
    for s in stats:
        conn.execute(
            """INSERT INTO team_stats (id, game_id, team, quarter, points,
               fg_made, fg_attempted, three_made, three_attempted,
               ft_made, ft_attempted, rebounds, assists, steals,
               blocks, turnovers, fouls, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4())[:8], game_id, s.get("team", "ours"),
             s.get("quarter", "total"), s.get("points", 0),
             s.get("fg_made", 0), s.get("fg_attempted", 0),
             s.get("three_made", 0), s.get("three_attempted", 0),
             s.get("ft_made", 0), s.get("ft_attempted", 0),
             s.get("rebounds", 0), s.get("assists", 0),
             s.get("steals", 0), s.get("blocks", 0),
             s.get("turnovers", 0), s.get("fouls", 0),
             s.get("source", "manual"))
        )
    conn.commit()
    conn.close()


def get_team_stats(game_id: str, team: str = None) -> list[dict]:
    conn = get_connection()
    if team:
        rows = conn.execute(
            "SELECT * FROM team_stats WHERE game_id = ? AND team = ?",
            (game_id, team)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM team_stats WHERE game_id = ?", (game_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Observations ─────────────────────────────────────────────────

def add_observations(game_id: str, observations: list[dict]):
    conn = get_connection()
    for obs in observations:
        conn.execute(
            """INSERT INTO observations (id, game_id, category, detail, quarter, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4())[:8], game_id, obs["category"],
             obs["detail"], obs.get("quarter"), obs.get("source", "coach_notes"))
        )
    conn.commit()
    conn.close()


def get_observations(game_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM observations WHERE game_id = ?", (game_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Reports ──────────────────────────────────────────────────────

def save_report(game_id: str | None, opponent: str | None,
                report_type: str, analysis_json: str,
                report_text: str) -> str:
    report_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute(
        """INSERT INTO reports (id, game_id, opponent, report_type,
           analysis_json, report_text)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (report_id, game_id, opponent, report_type, analysis_json, report_text)
    )
    conn.commit()
    conn.close()
    return report_id


def get_reports(game_id: str = None, opponent: str = None,
                report_type: str = None) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM reports WHERE 1=1"
    params = []
    if game_id:
        query += " AND game_id = ?"
        params.append(game_id)
    if opponent:
        query += " AND opponent LIKE ?"
        params.append(f"%{opponent}%")
    if report_type:
        query += " AND report_type = ?"
        params.append(report_type)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Opponent Players ─────────────────────────────────────────────

def upsert_opponent_player(opponent_team: str, number: str,
                           name: str = None, tendency: str = None,
                           game_date: str = None):
    """Add or update an opponent player's tendencies."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM opponent_players WHERE opponent_team LIKE ? AND number = ?",
        (f"%{opponent_team}%", number)
    ).fetchone()

    if row:
        existing = json.loads(row["tendencies"] or "[]")
        if tendency and tendency not in existing:
            existing.append(tendency)
        games = (row["games_seen"] or 0) + 1
        conn.execute(
            """UPDATE opponent_players SET tendencies = ?, games_seen = ?,
               last_seen_date = ?, name = COALESCE(?, name) WHERE id = ?""",
            (json.dumps(existing), games, game_date, name, row["id"])
        )
    else:
        player_id = str(uuid.uuid4())[:8]
        tendencies = json.dumps([tendency] if tendency else [])
        conn.execute(
            """INSERT INTO opponent_players (id, opponent_team, number, name,
               tendencies, games_seen, last_seen_date)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (player_id, opponent_team, number, name, tendencies, game_date)
        )

    conn.commit()
    conn.close()


def get_opponent_players(opponent_team: str) -> list[dict]:
    """Get all known players for an opponent."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM opponent_players WHERE opponent_team LIKE ? ORDER BY number",
        (f"%{opponent_team}%",)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["tendencies"] = json.loads(d.get("tendencies") or "[]")
        result.append(d)
    return result


def get_all_opponent_players() -> list[dict]:
    """Get all opponent players grouped by team."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM opponent_players ORDER BY opponent_team, number"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["tendencies"] = json.loads(d.get("tendencies") or "[]")
        result.append(d)
    return result


# ── Full Game Bundle (for passing to agents) ─────────────────────

def get_full_game_data(game_id: str) -> dict | None:
    """Get everything about a game in one call — for agent context."""
    game = get_game(game_id)
    if not game:
        return None
    return {
        "game": game,
        "our_player_stats": get_player_stats(game_id, "ours"),
        "opp_player_stats": get_player_stats(game_id, "opponent"),
        "our_team_stats": get_team_stats(game_id, "ours"),
        "opp_team_stats": get_team_stats(game_id, "opponent"),
        "observations": get_observations(game_id),
    }


def get_opponent_history(opponent: str) -> list[dict]:
    """Get all game data for every game against an opponent."""
    games = list_games(opponent=opponent)
    return [get_full_game_data(g["id"]) for g in games]


# ── Season Operations ────────────────────────────────────────────

def create_season(name: str, team_name: str, games_played: int = 0,
                  start_date: str = None, end_date: str = None) -> str:
    season_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute(
        """INSERT INTO seasons (id, name, team_name, games_played, start_date, end_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (season_id, name, team_name, games_played, start_date, end_date)
    )
    conn.commit()
    conn.close()
    return season_id


def get_seasons() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM seasons ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_season(season_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM seasons WHERE id = ?", (season_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Roster Operations ────────────────────────────────────────────

def get_or_create_player(first_name: str, last_name: str, number: str = None) -> str:
    """Find existing player or create new one. Returns player_id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM roster WHERE first_name = ? AND last_name = ?",
        (first_name, last_name)
    ).fetchone()
    if row:
        conn.close()
        return row["id"]
    player_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO roster (id, first_name, last_name, number) VALUES (?, ?, ?, ?)",
        (player_id, first_name, last_name, number)
    )
    conn.commit()
    conn.close()
    return player_id


def add_season_player(season_id: str, player_id: str, number: str,
                      stats: dict) -> str:
    """Add a player's season stats to a season roster."""
    entry_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute(
        """INSERT INTO season_roster (id, season_id, player_id, number, status,
           games_played, games_started, points, fg_made, fg_attempted,
           three_made, three_attempted, ft_made, ft_attempted,
           turnovers, rebounds, assists, steals, blocks, fouls,
           fg_pct, three_pct, ft_pct, ppg, rpg, apg, spg, bpg, topg, source)
           VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_id, season_id, player_id, number,
         stats.get("games_played", 0), stats.get("games_started", 0),
         stats.get("points", 0),
         stats.get("fg_made", 0), stats.get("fg_attempted", 0),
         stats.get("three_made", 0), stats.get("three_attempted", 0),
         stats.get("ft_made", 0), stats.get("ft_attempted", 0),
         stats.get("turnovers", 0), stats.get("rebounds", 0),
         stats.get("assists", 0), stats.get("steals", 0),
         stats.get("blocks", 0), stats.get("fouls", 0),
         stats.get("fg_pct", 0), stats.get("three_pct", 0),
         stats.get("ft_pct", 0), stats.get("ppg", 0),
         stats.get("rpg", 0), stats.get("apg", 0),
         stats.get("spg", 0), stats.get("bpg", 0),
         stats.get("topg", 0), stats.get("source", "gamechanger"))
    )
    conn.commit()
    conn.close()
    return entry_id


def save_team_season_totals(season_id: str, totals: dict) -> str:
    totals_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute(
        """INSERT INTO team_season_totals (id, season_id, games_played, points,
           fg_made, fg_attempted, three_made, three_attempted,
           ft_made, ft_attempted, turnovers, rebounds, assists, steals,
           blocks, fouls, ppg, fg_pct, three_pct, ft_pct)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (totals_id, season_id, totals.get("games_played", 0),
         totals.get("points", 0),
         totals.get("fg_made", 0), totals.get("fg_attempted", 0),
         totals.get("three_made", 0), totals.get("three_attempted", 0),
         totals.get("ft_made", 0), totals.get("ft_attempted", 0),
         totals.get("turnovers", 0), totals.get("rebounds", 0),
         totals.get("assists", 0), totals.get("steals", 0),
         totals.get("blocks", 0), totals.get("fouls", 0),
         totals.get("ppg", 0), totals.get("fg_pct", 0),
         totals.get("three_pct", 0), totals.get("ft_pct", 0))
    )
    conn.commit()
    conn.close()
    return totals_id


def get_season_roster(season_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT sr.*, r.first_name, r.last_name
           FROM season_roster sr
           JOIN roster r ON sr.player_id = r.id
           WHERE sr.season_id = ?
           ORDER BY sr.ppg DESC""",
        (season_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_team_season_totals(season_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM team_season_totals WHERE season_id = ?", (season_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_full_season_data(season_id: str) -> dict | None:
    """Get everything about a season — for agent context."""
    season = get_season(season_id)
    if not season:
        return None
    return {
        "season": season,
        "roster": get_season_roster(season_id),
        "team_totals": get_team_season_totals(season_id),
    }


# ── Scouted Teams ────────────────────────────────────────────────

import re as _re


def _normalize_team_name(name: str) -> str:
    """Normalize a team name for fuzzy matching.

    Strips:
    - Trailing 4-digit year (2030, 2031, etc.)
    - Coach/suffix after " - " or " – " if the part after looks like a name
      (capitalized word, not a number or known suffix like "13U", "14U")
    - Extra whitespace

    Examples:
        "Team PA Jones 2031"       -> "team pa"
        "Team PA - Jones"          -> "team pa"
        "Maryland Sting - Peay"    -> "maryland sting"
        "Elkridge Elite - Johnson" -> "elkridge elite"
        "PA Flight Harrison"       -> "pa flight"
        "Team PA 2030 Williams"    -> "team pa"
    """
    if not name:
        return ""

    s = name.strip()

    # Strip dash-separated suffix (coach name / location) when the suffix looks
    # like a proper name: at least one word that starts with an uppercase letter
    # and is not a division code like "13U".
    dash_match = _re.split(r'\s*[-–]\s*', s, maxsplit=1)
    if len(dash_match) == 2:
        suffix = dash_match[1].strip()
        # Keep the split only if the suffix looks like a name word (not a division)
        if _re.match(r'^[A-Z][a-z]+', suffix) and not _re.match(r'^\d+U$', suffix):
            s = dash_match[0].strip()

    # Strip trailing 4-digit graduation year (2025–2035)
    s = _re.sub(r'\b20[23]\d\b', '', s).strip()

    # Strip trailing word(s) that look like a coach last name:
    # a single capitalized word at the end not matching known suffixes
    def _looks_like_coach(word: str) -> bool:
        if _re.match(r'^\d+U$', word, _re.IGNORECASE):
            return False
        if word.upper() in {"ELITE", "FLIGHT", "STING", "HAWKS", "HEAT",
                             "KINGS", "STORM", "FORCE", "EXPRESS", "UNITED",
                             "SELECT", "PREMIER", "ACADEMY", "NATION"}:
            return False
        return bool(_re.match(r'^[A-Z][a-z]+$', word))

    words = s.split()
    while len(words) > 1 and _looks_like_coach(words[-1]):
        words = words[:-1]
    s = " ".join(words)

    return s.lower().strip()


def upsert_scouted_team(team_name: str, source: str, source_url: str = None,
                        event_name: str = None, event_id: str = None,
                        division: str = None, location: str = None,
                        gc_team_id: str = None) -> str:
    """Insert or update a scouted team. Keyed on normalized_name + event_id."""
    normalized = _normalize_team_name(team_name)
    now = datetime.utcnow().isoformat()
    conn = get_connection()

    # Try to find existing row with same normalized name and event
    row = conn.execute(
        """SELECT id FROM scouted_teams
           WHERE normalized_name = ? AND (event_id = ? OR (event_id IS NULL AND ? IS NULL))""",
        (normalized, event_id, event_id)
    ).fetchone()

    if row:
        team_id = row["id"]
        conn.execute(
            """UPDATE scouted_teams
               SET team_name = ?, source = ?, source_url = COALESCE(?, source_url),
                   event_name = COALESCE(?, event_name), division = COALESCE(?, division),
                   location = COALESCE(?, location), gc_team_id = COALESCE(?, gc_team_id),
                   last_seen = ?
               WHERE id = ?""",
            (team_name, source, source_url, event_name, division,
             location, gc_team_id, now, team_id)
        )
    else:
        team_id = str(uuid.uuid4())[:8]
        conn.execute(
            """INSERT INTO scouted_teams
               (id, team_name, normalized_name, source, source_url,
                event_name, event_id, division, location, gc_team_id, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (team_id, team_name, normalized, source, source_url,
             event_name, event_id, division, location, gc_team_id, now)
        )

    conn.commit()
    conn.close()
    return team_id


def search_scouted_teams(query: str) -> list[dict]:
    """Fuzzy-search scouted teams by name.

    Normalizes the query the same way team names are stored, then searches
    with LIKE. Also tries splitting on " - " to search each part separately.
    Results are ordered: exact normalized match first, then partial matches.
    """
    normalized_query = _normalize_team_name(query)
    if not normalized_query:
        return []

    conn = get_connection()
    seen_ids: set[str] = set()
    results: list[dict] = []

    def _fetch(pattern: str):
        rows = conn.execute(
            "SELECT * FROM scouted_teams WHERE normalized_name LIKE ? ORDER BY last_seen DESC",
            (pattern,)
        ).fetchall()
        for r in rows:
            d = dict(r)
            if d["id"] not in seen_ids:
                seen_ids.add(d["id"])
                results.append(d)

    # Exact normalized match
    _fetch(normalized_query)
    # Partial match on full normalized query
    _fetch(f"%{normalized_query}%")

    # Also try each fragment around " - " in the original query
    parts = _re.split(r'\s*[-–]\s*', query)
    for part in parts:
        part_norm = _normalize_team_name(part.strip())
        if part_norm and part_norm != normalized_query:
            _fetch(f"%{part_norm}%")

    conn.close()
    return results


def get_scouted_teams_by_event(event_id: str) -> list[dict]:
    """Return all scouted teams for a given tournament event ID."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM scouted_teams WHERE event_id = ? ORDER BY team_name",
        (event_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Coach Notes ─────────────────────────────────────────────────

def save_coach_note(note_id: str, content: str, opponent: str = "",
                    date: str = "") -> str:
    """Create or update a coach note. Returns note_id."""
    conn = get_connection()
    existing = conn.execute("SELECT id FROM coach_notes WHERE id = ?", (note_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE coach_notes SET content = ?, opponent = ?, date = ?, updated_at = datetime('now') WHERE id = ?",
            (content, opponent, date, note_id)
        )
    else:
        conn.execute(
            "INSERT INTO coach_notes (id, content, opponent, date) VALUES (?, ?, ?, ?)",
            (note_id, content, opponent, date)
        )
    conn.commit()
    conn.close()
    return note_id


def list_coach_notes(status: str = "active") -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM coach_notes WHERE status = ? ORDER BY updated_at DESC",
        (status,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_coach_note(note_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM coach_notes WHERE id = ?", (note_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_coach_note(note_id: str):
    conn = get_connection()
    conn.execute("DELETE FROM coach_notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


def use_coach_note(note_id: str, game_id: str):
    """Mark a note as used and link it to a game."""
    conn = get_connection()
    conn.execute(
        "UPDATE coach_notes SET status = 'used', game_id = ? WHERE id = ?",
        (game_id, note_id)
    )
    conn.commit()
    conn.close()


def get_player_cards(season_id: str = None) -> list[dict]:
    """Aggregate player stats from per-game box scores into card data.

    Returns list of player dicts with season totals, per-game averages,
    last-5 averages, shooting splits, and recent game log.
    Each player is identified by jersey number (player_number).
    """
    conn = get_connection()

    # Get all our players' per-game stats, joined with game info
    query = """
        SELECT ps.*, g.date, g.opponent, g.result, g.our_score, g.opp_score,
               g.game_type, g.event_name
        FROM player_stats ps
        JOIN games g ON ps.game_id = g.id
        WHERE ps.team = 'ours'
        ORDER BY g.date DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()

    if not rows:
        return []

    # Group by player_number
    from collections import defaultdict
    players = defaultdict(list)
    for r in rows:
        d = dict(r)
        players[d["player_number"]].append(d)

    cards = []
    for number, games in players.items():
        # Sort by date descending (already sorted but ensure)
        games.sort(key=lambda g: g.get("date", ""), reverse=True)

        total_games = len(games)
        if total_games == 0:
            continue

        # Use most recent name
        name = games[0].get("player_name", f"#{number}")

        # Season totals
        total_pts = sum(g.get("points", 0) for g in games)
        total_reb = sum(g.get("rebounds", 0) for g in games)
        total_ast = sum(g.get("assists", 0) for g in games)
        total_stl = sum(g.get("steals", 0) for g in games)
        total_blk = sum(g.get("blocks", 0) for g in games)
        total_to  = sum(g.get("turnovers", 0) for g in games)
        total_fg_m = sum(g.get("fg_made", 0) for g in games)
        total_fg_a = sum(g.get("fg_attempted", 0) for g in games)
        total_3_m  = sum(g.get("three_made", 0) for g in games)
        total_3_a  = sum(g.get("three_attempted", 0) for g in games)
        total_ft_m = sum(g.get("ft_made", 0) for g in games)
        total_ft_a = sum(g.get("ft_attempted", 0) for g in games)

        ppg = round(total_pts / total_games, 1)
        rpg = round(total_reb / total_games, 1)
        apg = round(total_ast / total_games, 1)
        spg = round(total_stl / total_games, 1)
        bpg = round(total_blk / total_games, 1)
        topg = round(total_to / total_games, 1)

        fg_pct = round(total_fg_m / total_fg_a, 3) if total_fg_a > 0 else 0
        three_pct = round(total_3_m / total_3_a, 3) if total_3_a > 0 else 0
        ft_pct = round(total_ft_m / total_ft_a, 3) if total_ft_a > 0 else 0

        # Last 5 games averages
        last5 = games[:5]
        l5_count = len(last5)
        l5_ppg = round(sum(g.get("points", 0) for g in last5) / l5_count, 1) if l5_count else 0
        l5_rpg = round(sum(g.get("rebounds", 0) for g in last5) / l5_count, 1) if l5_count else 0
        l5_apg = round(sum(g.get("assists", 0) for g in last5) / l5_count, 1) if l5_count else 0
        l5_spg = round(sum(g.get("steals", 0) for g in last5) / l5_count, 1) if l5_count else 0

        l5_fg_m = sum(g.get("fg_made", 0) for g in last5)
        l5_fg_a = sum(g.get("fg_attempted", 0) for g in last5)
        l5_3_m  = sum(g.get("three_made", 0) for g in last5)
        l5_3_a  = sum(g.get("three_attempted", 0) for g in last5)
        l5_ft_m = sum(g.get("ft_made", 0) for g in last5)
        l5_ft_a = sum(g.get("ft_attempted", 0) for g in last5)
        l5_fg_pct = round(l5_fg_m / l5_fg_a, 3) if l5_fg_a > 0 else 0
        l5_three_pct = round(l5_3_m / l5_3_a, 3) if l5_3_a > 0 else 0
        l5_ft_pct = round(l5_ft_m / l5_ft_a, 3) if l5_ft_a > 0 else 0

        # Game type breakdown
        type_counts = defaultdict(int)
        for g in games:
            type_counts[g.get("game_type", "league")] += 1

        # Recent game log (last 5)
        game_log = []
        for g in last5:
            game_log.append({
                "opponent": g.get("opponent", "?"),
                "date": g.get("date", ""),
                "score": f"{g.get('our_score', '?')}-{g.get('opp_score', '?')} {g.get('result', '')}",
                "points": g.get("points", 0),
                "rebounds": g.get("rebounds", 0),
                "assists": g.get("assists", 0),
                "steals": g.get("steals", 0),
                "above_avg": g.get("points", 0) > ppg,
                "game_type": g.get("game_type", "league"),
            })

        cards.append({
            "number": number,
            "name": name,
            "games_played": total_games,
            # Season averages
            "ppg": ppg, "rpg": rpg, "apg": apg, "spg": spg, "bpg": bpg, "topg": topg,
            # Last 5 averages
            "l5_ppg": l5_ppg, "l5_rpg": l5_rpg, "l5_apg": l5_apg, "l5_spg": l5_spg,
            # Shooting totals
            "fg_made": total_fg_m, "fg_attempted": total_fg_a, "fg_pct": fg_pct,
            "three_made": total_3_m, "three_attempted": total_3_a, "three_pct": three_pct,
            "ft_made": total_ft_m, "ft_attempted": total_ft_a, "ft_pct": ft_pct,
            # Last 5 shooting
            "l5_fg_pct": l5_fg_pct, "l5_three_pct": l5_three_pct, "l5_ft_pct": l5_ft_pct,
            # Trends (positive = improving)
            "ppg_trend": round(l5_ppg - ppg, 1),
            "rpg_trend": round(l5_rpg - rpg, 1),
            "apg_trend": round(l5_apg - apg, 1),
            "spg_trend": round(l5_spg - spg, 1),
            "fg_trend": round((l5_fg_pct - fg_pct) * 100, 0),
            "three_trend": round((l5_three_pct - three_pct) * 100, 0),
            "ft_trend": round((l5_ft_pct - ft_pct) * 100, 0),
            # Game type counts
            "type_counts": dict(type_counts),
            # Recent games
            "game_log": game_log,
            # Source
            "source": "game_reports",
        })

    # Sort by PPG descending
    cards.sort(key=lambda c: c["ppg"], reverse=True)
    return cards


# Initialize on import
init_db()
