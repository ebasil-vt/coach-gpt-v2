"""Pipeline — Chains agents together: Ingest → Analyze → Report.

This is the orchestration layer. For Phase 1, it's simple sequential calls.
In Phase 2+, this becomes the Orchestrator Agent using Claude Agent SDK.
"""

import json
import os
from pathlib import Path
from datetime import datetime

from coachgpt import database as db
from coachgpt.agents.ingestion import (
    ingest_game_data, ingest_from_image, ingest_from_pdf, ingest_from_csv
)
from coachgpt.agents.analyst import analyze_game, analyze_opponent
from coachgpt.agents.report_writer import write_postgame_report, write_scouting_report, write_pregame_brief
from coachgpt.agents.researcher import research_and_compare

_data_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", str(Path(__file__).parent.parent))
REPORTS_DIR = Path(_data_dir) / "reports"


def _store_structured_data(structured: dict, raw_notes: str = "") -> str:
    """Store parsed game data in the database. Returns game_id."""
    game_info = structured["game"]
    game_id = db.create_game(
        opponent=game_info["opponent"],
        date=game_info["date"],
        our_team=game_info.get("our_team"),
        location=game_info.get("location"),
        result=game_info.get("result"),
        our_score=game_info.get("our_score"),
        opp_score=game_info.get("opp_score"),
        notes=raw_notes,
    )

    if structured.get("our_player_stats"):
        db.add_player_stats(game_id, structured["our_player_stats"])

    if structured.get("opp_player_stats"):
        db.add_player_stats(game_id, structured["opp_player_stats"])

    team_stats_to_store = []
    if structured.get("our_team_totals"):
        team_stats_to_store.append(structured["our_team_totals"])
    if structured.get("opp_team_totals"):
        team_stats_to_store.append(structured["opp_team_totals"])

    quarter_scores = structured.get("quarter_scores", {})
    for side, label in [("ours", "ours"), ("opponent", "opponent")]:
        for q, pts in quarter_scores.get(side, {}).items():
            team_stats_to_store.append({
                "team": label, "quarter": q, "points": pts,
                "source": "gamechanger",
            })

    if team_stats_to_store:
        db.add_team_stats(game_id, team_stats_to_store)

    if structured.get("observations"):
        db.add_observations(game_id, structured["observations"])

    # Auto-extract opponent player tendencies from observations
    _extract_opponent_players(game_info["opponent"], structured.get("observations", []),
                              game_info.get("date"))

    return game_id


def _extract_opponent_players(opponent: str, observations: list, game_date: str = None):
    """Extract opponent player tendencies from observations that mention jersey numbers."""
    import re
    for obs in observations:
        detail = obs.get("detail", "")
        # Find patterns like "#10 can't handle pressure" or "#7 best player"
        matches = re.findall(r'#(\d+)\s+(.+?)(?:\.|;|$)', detail)
        if not matches:
            # Also try "number 10" pattern
            matches = re.findall(r'(?:number|no\.?)\s*(\d+)\s+(.+?)(?:\.|;|$)', detail, re.IGNORECASE)

        for number, tendency in matches:
            tendency = tendency.strip().rstrip(',').strip()
            if len(tendency) > 5:  # Skip very short fragments
                db.upsert_opponent_player(
                    opponent_team=opponent,
                    number=number,
                    tendency=tendency,
                    game_date=game_date,
                )


def process_game(raw_input: str, callback=None) -> dict:
    """Full pipeline: raw text → structured DB → analysis → report."""
    def emit(agent, step, detail):
        msg = f"[{agent}] {detail}"
        if callback:
            callback(agent, step, detail)
        print(f"  {msg}")

    emit("orchestrator", "start", "Routing to Ingestion Agent...")
    emit("ingestion", "working", "Reading and parsing game data...")
    structured = ingest_game_data(raw_input)
    game_info = structured["game"]
    opponent = game_info.get("opponent", "Unknown")
    emit("ingestion", "done", f"Parsed: {opponent} — {game_info.get('our_score', '?')}-{game_info.get('opp_score', '?')}")

    emit("orchestrator", "storing", "Saving structured data to database...")
    game_id = _store_structured_data(structured, raw_input)
    player_count = len(structured.get("our_player_stats", [])) + len(structured.get("opp_player_stats", []))
    obs_count = len(structured.get("observations", []))
    emit("orchestrator", "stored", f"Stored: {player_count} player records, {obs_count} observations")

    emit("orchestrator", "routing", "Handing off to Analyst Agent...")
    emit("analyst", "working", "Computing stats and detecting patterns...")
    game_data = db.get_full_game_data(game_id)
    analysis = analyze_game(game_data)
    patterns = len(analysis.get("patterns_detected", []))
    emit("analyst", "done", f"Found {patterns} patterns, analysis complete")

    emit("orchestrator", "routing", "Handing off to Report Writer Agent...")
    emit("report_writer", "working", "Writing postgame report...")
    report_text = write_postgame_report(analysis=analysis, coach_notes=raw_input)
    emit("report_writer", "done", "Postgame report generated")

    db.save_report(game_id=game_id, opponent=opponent,
                   report_type="postgame", analysis_json=json.dumps(analysis),
                   report_text=report_text)

    report_path = _save_report_file(report_text, "postgame", opponent, game_info["date"])
    emit("orchestrator", "complete", f"All agents finished — report ready")

    return {
        "game_id": game_id, "opponent": opponent,
        "date": game_info["date"],
        "result": f"{game_info.get('our_score', '?')}-{game_info.get('opp_score', '?')} {game_info.get('result', '')}",
        "analysis": analysis, "report_text": report_text,
        "report_path": str(report_path),
    }


def process_game_image(image_bytes: bytes, media_type: str,
                       coach_notes: str = "", metadata: str = "",
                       callback=None) -> dict:
    """Full pipeline from screenshot/photo."""
    def emit(agent, step, detail):
        if callback:
            callback(agent, step, detail)
        print(f"  [{agent}] {detail}")

    emit("orchestrator", "start", "Image detected — routing to Ingestion Agent with Vision...")
    emit("ingestion", "working", "Reading box score from image using Claude Vision...")
    structured = ingest_from_image(image_bytes, media_type, coach_notes, metadata)
    game_info = structured["game"]
    opponent = game_info.get("opponent", "Unknown")
    emit("ingestion", "done", f"Extracted stats: {opponent} — {game_info.get('our_score', '?')}-{game_info.get('opp_score', '?')}")

    emit("orchestrator", "storing", "Saving to database...")
    game_id = _store_structured_data(structured, coach_notes)
    player_count = len(structured.get("our_player_stats", [])) + len(structured.get("opp_player_stats", []))
    obs_count = len(structured.get("observations", []))
    emit("orchestrator", "stored", f"Stored: {player_count} players, {obs_count} observations")

    emit("orchestrator", "routing", "Handing off to Analyst Agent...")
    emit("analyst", "working", "Analyzing patterns and tendencies...")
    game_data = db.get_full_game_data(game_id)
    analysis = analyze_game(game_data)
    patterns = len(analysis.get("patterns_detected", []))
    emit("analyst", "done", f"Found {patterns} patterns")

    emit("orchestrator", "routing", "Handing off to Report Writer Agent...")
    emit("report_writer", "working", "Writing postgame report...")
    report_text = write_postgame_report(analysis=analysis, coach_notes=coach_notes)
    emit("report_writer", "done", "Report complete")

    db.save_report(game_id=game_id, opponent=opponent,
                   report_type="postgame", analysis_json=json.dumps(analysis),
                   report_text=report_text)

    report_path = _save_report_file(report_text, "postgame", opponent, game_info["date"])
    emit("orchestrator", "complete", "All agents finished — report ready")

    return {
        "game_id": game_id, "opponent": opponent, "date": game_info["date"],
        "result": f"{game_info.get('our_score', '?')}-{game_info.get('opp_score', '?')} {game_info.get('result', '')}",
        "analysis": analysis, "report_text": report_text,
        "report_path": str(report_path),
    }


def process_game_pdf(pdf_bytes: bytes, coach_notes: str = "",
                     metadata: str = "", callback=None) -> dict:
    """Full pipeline from PDF."""
    def emit(agent, step, detail):
        if callback:
            callback(agent, step, detail)
        print(f"  [{agent}] {detail}")

    emit("orchestrator", "start", "PDF detected — routing to Ingestion Agent...")
    emit("ingestion", "working", "Extracting stats from PDF document...")
    structured = ingest_from_pdf(pdf_bytes, coach_notes, metadata)
    game_info = structured["game"]
    opponent = game_info.get("opponent", "Unknown")
    emit("ingestion", "done", f"Extracted: {opponent} — {game_info.get('our_score', '?')}-{game_info.get('opp_score', '?')}")

    emit("orchestrator", "storing", "Saving to database...")
    game_id = _store_structured_data(structured, coach_notes)
    emit("orchestrator", "stored", "Data stored")

    emit("orchestrator", "routing", "Handing off to Analyst Agent...")
    emit("analyst", "working", "Computing patterns and tendencies...")
    game_data = db.get_full_game_data(game_id)
    analysis = analyze_game(game_data)
    patterns = len(analysis.get("patterns_detected", []))
    emit("analyst", "done", f"Found {patterns} patterns")

    emit("orchestrator", "routing", "Handing off to Report Writer Agent...")
    emit("report_writer", "working", "Writing postgame report...")
    report_text = write_postgame_report(analysis=analysis, coach_notes=coach_notes)
    emit("report_writer", "done", "Report complete")

    db.save_report(game_id=game_id, opponent=opponent,
                   report_type="postgame", analysis_json=json.dumps(analysis),
                   report_text=report_text)

    report_path = _save_report_file(report_text, "postgame", opponent, game_info["date"])
    emit("orchestrator", "complete", "All agents finished — report ready")

    return {
        "game_id": game_id, "opponent": opponent, "date": game_info["date"],
        "result": f"{game_info.get('our_score', '?')}-{game_info.get('opp_score', '?')} {game_info.get('result', '')}",
        "analysis": analysis, "report_text": report_text,
        "report_path": str(report_path),
    }


def scout_opponent(opponent: str, callback=None) -> dict:
    """Pull all games vs opponent → cross-game analysis → scouting report."""
    def emit(agent, step, detail):
        if callback:
            callback(agent, step, detail)
        print(f"  [{agent}] {detail}")

    emit("orchestrator", "start", f"Scouting request: {opponent}")
    emit("orchestrator", "working", "Pulling game history from database...")
    games = db.get_opponent_history(opponent)

    if not games:
        return {"error": f"No games found against '{opponent}'."}

    games = [g for g in games if g is not None]
    if not games:
        return {"error": f"No valid game data found for '{opponent}'."}

    emit("orchestrator", "stored", f"Found {len(games)} game(s) vs {opponent}")

    emit("orchestrator", "routing", "Handing off to Analyst Agent...")
    emit("analyst", "working", f"Cross-game analysis on {len(games)} matchup(s)...")
    scouting_analysis = analyze_opponent(games)
    tendencies = len(scouting_analysis.get("tendencies", []))
    emit("analyst", "done", f"Identified {tendencies} tendencies")

    emit("orchestrator", "routing", "Handing off to Report Writer Agent...")
    emit("report_writer", "working", "Writing scouting report...")
    report_text = write_scouting_report(scouting_analysis)
    emit("report_writer", "done", "Scouting report complete")

    db.save_report(game_id=None, opponent=opponent, report_type="scouting",
                   analysis_json=json.dumps(scouting_analysis),
                   report_text=report_text)

    report_path = _save_report_file(report_text, "scouting", opponent,
                                     datetime.now().strftime("%Y-%m-%d"))
    emit("orchestrator", "complete", "All agents finished — scouting report ready")

    return {
        "opponent": opponent, "games_analyzed": len(games),
        "analysis": scouting_analysis, "report_text": report_text,
        "report_path": str(report_path),
    }


def generate_pregame_brief(opponent: str, callback=None) -> dict:
    """Generate a pre-game brief for an upcoming game vs opponent."""
    def emit(agent, step, detail):
        if callback:
            callback(agent, step, detail)
        print(f"  [{agent}] {detail}")

    emit("orchestrator", "start", f"Pre-game brief request: {opponent}")
    emit("orchestrator", "working", "Pulling game history and team data...")
    games = db.get_opponent_history(opponent)

    if not games:
        return {"error": f"No games found against '{opponent}'. Scout them first."}

    games = [g for g in games if g is not None]
    if not games:
        return {"error": f"No valid game data for '{opponent}'."}

    # Get our season data for context
    seasons = db.get_seasons()
    season_data = None
    if seasons:
        season_data = db.get_full_season_data(seasons[0]["id"])

    emit("orchestrator", "stored", f"Found {len(games)} game(s) vs {opponent}")

    emit("orchestrator", "routing", "Handing off to Analyst Agent...")
    emit("analyst", "working", f"Cross-game analysis on {len(games)} matchup(s)...")
    scouting_analysis = analyze_opponent(games)
    tendencies = len(scouting_analysis.get("tendencies", []))
    emit("analyst", "done", f"Identified {tendencies} tendencies")

    emit("orchestrator", "routing", "Handing off to Report Writer Agent...")
    emit("report_writer", "working", "Writing pre-game brief...")
    report_text = write_pregame_brief(scouting_analysis, season_data)
    emit("report_writer", "done", "Pre-game brief ready")

    db.save_report(game_id=None, opponent=opponent, report_type="pregame",
                   analysis_json=json.dumps(scouting_analysis),
                   report_text=report_text)

    report_path = _save_report_file(report_text, "pregame", opponent,
                                     datetime.now().strftime("%Y-%m-%d"))
    emit("orchestrator", "complete", "Pre-game brief ready — good luck coach")

    return {
        "opponent": opponent, "games_analyzed": len(games),
        "report_text": report_text, "report_path": str(report_path),
    }


def lookup_opponent(opponent: str, league_info: str = "",
                    callback=None) -> dict:
    """Research an opponent we may not have played — find their record,
    cross-reference common opponents, assess relative strength."""
    def emit(agent, step, detail):
        if callback:
            callback(agent, step, detail)
        print(f"  [{agent}] {detail}")

    emit("orchestrator", "start", f"Researching {opponent}...")
    emit("researcher", "working", f"Searching for {opponent} game history online...")

    research = research_and_compare(opponent, league_info)

    if research.get("error"):
        emit("researcher", "done", f"Error: {research['error']}")
        return research

    # Build a summary
    record = research.get("opponent_record", {})
    common = research.get("common_opponents", [])
    strength = research.get("strength_assessment", {})
    results_found = len(research.get("opponent_results", []))

    emit("researcher", "done",
         f"Found {results_found} game results, {len(common)} common opponents")

    # Generate a readable report from the research
    emit("report_writer", "working", "Writing opponent research report...")
    report_text = _format_research_report(opponent, research)
    emit("report_writer", "done", "Research report complete")

    # Save as a report
    db.save_report(game_id=None, opponent=opponent, report_type="research",
                   analysis_json=json.dumps(research),
                   report_text=report_text)

    report_path = _save_report_file(report_text, "research", opponent,
                                     datetime.now().strftime("%Y-%m-%d"))
    emit("orchestrator", "complete", "Opponent research complete")

    return {
        "opponent": opponent,
        "research": research,
        "report_text": report_text,
        "report_path": str(report_path),
    }


def _format_research_report(opponent: str, research: dict) -> str:
    """Format research JSON into a readable markdown report."""
    lines = [f"# Opponent Research: {opponent}", ""]

    # Record
    record = research.get("opponent_record", {})
    if record.get("wins") is not None:
        lines.append(f"**Record**: {record.get('wins', '?')}-{record.get('losses', '?')}")
        if record.get("record_source"):
            lines.append(f"*Source: {record['record_source']}*")
        lines.append("")

    # Their results
    results = research.get("opponent_results", [])
    if results:
        lines.append("## Their Game Results")
        for r in results:
            score = f" ({r['score']})" if r.get("score") else ""
            date = f" — {r['date']}" if r.get("date") else ""
            lines.append(f"- **{r.get('result', '?')}** vs {r['vs']}{score}{date}")
        lines.append("")

    # Common opponents — the most valuable part
    common = research.get("common_opponents", [])
    if common:
        lines.append("## Common Opponents (Key Comparison)")
        lines.append("")
        lines.append("| Team | Our Result | Their Result | Edge |")
        lines.append("|---|---|---|---|")
        for c in common:
            lines.append(f"| {c['team']} | {c.get('our_result', '?')} | {c.get('their_result', '?')} | {c.get('comparison', '')} |")
        lines.append("")

    # Strength assessment
    strength = research.get("strength_assessment", {})
    if strength.get("level"):
        level_labels = {
            "weaker": "We should be favored",
            "comparable": "This will be a close game",
            "stronger": "They're likely the tougher team",
            "unknown": "Not enough data to compare",
        }
        lines.append(f"## Strength Assessment: **{level_labels.get(strength['level'], strength['level'])}**")
        lines.append(f"Confidence: {strength.get('confidence', 'unknown')}")
        if strength.get("reasoning"):
            lines.append(f"\n{strength['reasoning']}")
        lines.append("")

    # Key findings
    findings = research.get("key_findings", [])
    if findings:
        lines.append("## Key Findings")
        for f in findings:
            lines.append(f"- {f}")
        lines.append("")

    # Data quality
    dq = research.get("data_quality", {})
    if dq:
        lines.append(f"---\n*Data: {dq.get('completeness', 'unknown')}. {dq.get('note', '')}*")

    return "\n".join(lines)


def _save_report_file(report_text: str, report_type: str,
                       opponent: str, date: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_opponent = opponent.lower().replace(" ", "_")
    filename = f"{date}_{report_type}_{safe_opponent}.md"
    path = REPORTS_DIR / filename
    path.write_text(report_text, encoding="utf-8")
    return path
