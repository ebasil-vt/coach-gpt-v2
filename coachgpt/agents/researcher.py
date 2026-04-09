"""Research Agent — Looks up opponent info from public sources and cross-references.

Uses Sonnet with web search context to find opponent game history,
then cross-references with our own database for comparative analysis.
"""

import json
import os

from coachgpt.ai_client import get_client, HAIKU, SONNET
from coachgpt import database as db

# Team config — override via env vars so no personal data is hardcoded in source
_TEAM_NAME = os.environ.get("COACHGPT_TEAM_NAME", "Maryland Sting 2031 - Peay")
_TEAM_LOCATION = os.environ.get("COACHGPT_TEAM_LOCATION", "Columbia, MD")
_TEAM_AGE_GROUP = os.environ.get("COACHGPT_TEAM_AGE_GROUP", "8th grade (2026-27)")
_GC_TEAM_PREV = os.environ.get("COACHGPT_GC_TEAM_PREV", "vf2TC4nINA77")
_GC_TEAM_CURRENT = os.environ.get("COACHGPT_GC_TEAM_CURRENT", "VGbwJULEMkSE")
_LEAGUE_INSTANCE = os.environ.get("COACHGPT_LEAGUE_INSTANCE", "228050")
_LEAGUE_SUBSEASON = os.environ.get("COACHGPT_LEAGUE_SUBSEASON", "957781")
_TEAM_INSTANCE = os.environ.get("COACHGPT_TEAM_INSTANCE", "10442151")


def _build_research_prompt() -> str:
    """Build the research system prompt with team config interpolated at runtime."""
    return f"""You are the CoachGPT research agent. Your job is to analyze an opponent team
based on publicly available information AND our own game history.

## OUR TEAM
- **Team Name**: {_TEAM_NAME}
- **Location**: {_TEAM_LOCATION}
- **Age Group**: {_TEAM_AGE_GROUP}
- **GameChanger Teams**:
  - Previous season: https://web.gc.com/teams/{_GC_TEAM_PREV}
  - Current season: https://web.gc.com/teams/{_GC_TEAM_CURRENT}

## DATA SOURCES

### 1. HCRPS (Howard County Recreation & Parks Sports) — hcrpsports.org
- Our league platform. Standings, schedules, and game scores are public.
- URL patterns:
  - Full season schedule: https://www.hcrpsports.org/schedule/print/league_instance/{{LEAGUE_ID}}?schedule_type=index&subseason={{SEASON_ID}}
  - Team schedule: https://www.hcrpsports.org/schedule/print/team_instance/{{TEAM_ID}}?schedule_type=index&subseason={{SEASON_ID}}
  - Standings: https://www.hcrpsports.org/standings/show/{{STANDINGS_ID}}?subseason={{SEASON_ID}}
- **Known season IDs:** league_instance={_LEAGUE_INSTANCE}, subseason={_LEAGUE_SUBSEASON}, team_instance={_TEAM_INSTANCE}
- Coach saves HCRPS pages as Safari webarchive → uploads to CoachGPT → all scores parsed automatically.

### 2. GameChanger — web.gc.com
- We use GameChanger for scoring and stats.
- **Per-game recap URL pattern**: https://web.gc.com/teams/{{TEAM_ID}}/schedule/{{GAME_ID}}/recap
  - Current season TEAM_ID: {_GC_TEAM_CURRENT}
- **How coach provides GC data**:
  - Export box score PDF from GC app → upload to CoachGPT
  - Export season stats CSV from web.gc.com → upload on Team tab
  - Share the per-game recap link → we note it for reference
  - Ask opposing coaches for their GC team link

### 3. Our Database
- Game results, player stats, coach notes, league standings all stored locally.
- League standings may already include the opponent's record and game-by-game scores.
- ALWAYS check our database first before searching externally.

### 4. Coach Knowledge (ASK AFTER EVERY GAME)
- "What was the score?"
- "Any opponent player tendencies? (jersey # + what they do)"
- "What worked? What adjustments for next time?"
- "Did you get the opponent's GameChanger link?"

### 5. Other Sources
- MaxPreps (maxpreps.com) — some teams listed
- Tournament sites, AAU/travel ball exposure sites

## WHEN DATA IS MISSING
Give SPECIFIC instructions, not generic advice:
- "Save the HCRPS schedule page as webarchive (Safari → File → Save As → Web Archive) and upload here"
- "Open GameChanger → this game → Share → Export PDF → upload here"
- "Share the GC recap link: web.gc.com/teams/{_GC_TEAM_CURRENT}/schedule/{{game}}/recap"
- "Ask the opposing coach for their GameChanger team URL"
- "Paste the HCRPS standings (Select All → Copy → Paste into Scout tab)"

## YOUR ANALYSIS

You will receive:
1. An opponent team name and any known details
2. Information from web search or our database
3. Our game history for cross-referencing common opponents
4. League standings data if available

Your job is to produce a STRUCTURED JSON analysis:

{{
  "opponent": "Team Name",
  "research_sources": ["list of sources used"],
  "data_instructions": ["If data is incomplete, list specific steps the coach should take to get more data"],
  "opponent_record": {{
    "wins": "int or null",
    "losses": "int or null",
    "record_source": "where you found this"
  }},
  "opponent_results": [
    {{
      "vs": "Team Name",
      "result": "W or L",
      "score": "52-48 or null",
      "date": "YYYY-MM-DD or null"
    }}
  ],
  "common_opponents": [
    {{
      "team": "Team Name",
      "our_result": "W 58-40",
      "their_result": "L 45-52 or W 50-48 or unknown",
      "comparison": "We beat them by 18, opponent lost by 7 → we're ~25 points better vs this team"
    }}
  ],
  "strength_assessment": {{
    "level": "weaker | comparable | stronger | unknown",
    "confidence": "high | medium | low",
    "reasoning": "Based on common opponents and results..."
  }},
  "key_findings": [
    "Any notable facts: coaching style, key players, defensive scheme, etc."
  ],
  "data_quality": {{
    "completeness": "full | partial | minimal",
    "note": "What we know vs what's missing"
  }}
}}

Rules:
1. Only include facts you actually found — NEVER invent results or records.
2. ALWAYS check if the opponent exists in our league standings data first.
3. Common opponent comparison is the MOST valuable part. Prioritize it.
4. For strength assessment, only say "stronger" or "weaker" if you have
   2+ common opponent comparisons pointing the same direction.
5. If results are from different seasons/age groups, note that — it affects reliability.
6. When data is missing, provide SPECIFIC instructions for getting it (URLs, steps).
7. Output ONLY the JSON. No commentary, no markdown code fences."""


def research_opponent(opponent: str, league_info: str = "",
                      our_games: list = None, our_season: dict = None) -> dict:
    """Research an opponent using web search and cross-reference with our data.

    Args:
        opponent: Team name to research
        league_info: Optional league/location context (e.g. "HCRPS basketball 13U")
        our_games: Our game history for cross-referencing
        our_season: Our season stats for context

    Returns:
        Structured research JSON with opponent analysis.
    """
    client = get_client()

    # Build the context for the research agent
    context_parts = [f"Research this opponent: {opponent}"]

    if league_info:
        context_parts.append(f"League/context: {league_info}")

    # Check league standings data from our database FIRST
    league_data = _check_league_standings(opponent)
    if league_data:
        context_parts.append(f"LEAGUE STANDINGS DATA (from our database — this is reliable):\n{league_data}")

    # Add our game history for cross-referencing
    if our_games:
        opponents_played = []
        for g in our_games:
            if g and g.get("game"):
                game = g["game"]
                opponents_played.append({
                    "opponent": game["opponent"],
                    "date": game["date"],
                    "result": game.get("result"),
                    "our_score": game.get("our_score"),
                    "opp_score": game.get("opp_score"),
                })
        context_parts.append(f"OUR GAME HISTORY (for finding common opponents):\n{json.dumps(opponents_played, indent=2)}")

    if our_season:
        context_parts.append(f"OUR TEAM SEASON STATS:\n{json.dumps(our_season, indent=2, default=str)}")

    if not league_data:
        context_parts.append(
            f"\nNo league standings found in our database for this opponent."
            f"\nSearch the web for: \"{opponent} basketball schedule results 2025 2026\""
            f"\nAlso try: \"{opponent} HCRPS standings\" or \"{opponent} GameChanger\""
            f"\nAlso try: \"{opponent} youth basketball Maryland results\""
            f"\nIf you can't find data, provide SPECIFIC instructions for the coach."
        )

    user_content = "\n\n".join(context_parts)

    # Step 1: Web search (skip if we already have league data)
    search_results = ""
    if not league_data:
        search_results = _web_search(client, opponent, league_info)

    # Step 2: Analyze with context
    full_context = user_content + f"\n\nWEB SEARCH RESULTS:\n{search_results}"

    response = client.messages.create(
        model=SONNET,
        max_tokens=4096,
        system=_build_research_prompt(),
        messages=[{"role": "user", "content": full_context}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw_text = "\n".join(lines).strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "opponent": opponent,
            "error": "Could not parse research results",
            "raw_response": raw_text[:1000],
        }


def _check_league_standings(opponent: str) -> str | None:
    """Check if we have league standings data that includes this opponent."""
    reports = db.get_reports(report_type="league_standings")
    if not reports:
        return None

    # Search through league standing reports for this opponent
    for report in reports:
        report_text = report.get("report_text", "")
        if opponent.lower() in report_text.lower():
            # Found them — return the relevant parts
            lines = report_text.split("\n")
            relevant = []
            for line in lines:
                # Include header, table rows, and any line mentioning the opponent
                if (line.startswith("#") or line.startswith("|") or
                        opponent.lower() in line.lower() or
                        "Maryland Sting" in line):
                    relevant.append(line)
            if relevant:
                return "\n".join(relevant)

    return None


def _web_search(client, opponent: str,
                league_info: str = "") -> str:
    """Use Claude to search the web for opponent information."""

    search_queries = [
        f"{opponent} basketball schedule results 2025 2026",
        f"{opponent} youth basketball Maryland standings",
    ]
    if league_info:
        search_queries.append(f"{opponent} {league_info}")

    # Use Claude with a simple prompt to synthesize what it knows
    # In production, this would use WebSearch/WebFetch tools via Agent SDK
    response = client.messages.create(
        model=HAIKU,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": (
                f"I'm looking for public basketball game results and schedule for a team called '{opponent}'."
                f"\n{'League context: ' + league_info if league_info else ''}"
                f"\n\nSearch queries to try:\n"
                + "\n".join(f"- {q}" for q in search_queries)
                + "\n\nIf you have any knowledge about this team, their league, or similar teams in the area, share it."
                "\nIf you don't have specific information, say 'No public data found for this team.'"
                "\nDo NOT invent results or records."
            ),
        }],
    )

    return response.content[0].text.strip()


def research_and_compare(opponent: str, league_info: str = "") -> dict:
    """Full research pipeline: lookup opponent, cross-reference, assess strength.

    This is the main entry point called by the pipeline.
    """
    # Get our game history
    all_games = db.list_games(limit=100)
    our_game_data = []
    for g in all_games:
        our_game_data.append({
            "game": g,
        })

    # Get our season stats
    seasons = db.get_seasons()
    our_season = None
    if seasons:
        our_season = db.get_full_season_data(seasons[0]["id"])

    # Run the research
    result = research_opponent(
        opponent=opponent,
        league_info=league_info,
        our_games=our_game_data,
        our_season=our_season,
    )

    return result
