"""Game Analyst Agent — Computes patterns and tendencies from structured game data.

Uses Sonnet for reasoning about basketball patterns. Takes structured game data
and produces analysis JSON. Never writes narratives — that's the Report Writer's job.
"""

import json

from coachgpt.ai_client import get_client, SONNET

SINGLE_GAME_PROMPT = """You are the CoachGPT basketball analyst. You take structured game data and
produce statistical analysis with pattern detection.

You NEVER write narratives or reports. You output STRUCTURED JSON only.

Your output MUST be valid JSON with this structure:

{
  "analysis_type": "postgame",
  "game_id": "from input",
  "our_team_metrics": {
    "points": int,
    "fg_pct": float (0-1),
    "three_pct": float (0-1),
    "ft_pct": float (0-1),
    "rebounds": int,
    "assists": int,
    "turnovers": int,
    "steals": int,
    "blocks": int,
    "assist_to_turnover": float,
    "estimated_possessions": int or null,
    "estimated_pace": float or null
  },
  "opponent_metrics": {
    same structure
  },
  "quarter_flow": {
    "description": "How the game momentum shifted",
    "our_scoring_by_quarter": {"Q1": int, ...},
    "opp_scoring_by_quarter": {"Q1": int, ...},
    "best_quarter": "Q3",
    "worst_quarter": "Q1",
    "momentum_shifts": ["description of shifts"]
  },
  "key_performers": [
    {
      "player": "name",
      "team": "ours" or "opponent",
      "standout_stats": {"stat": value, ...},
      "impact_note": "brief note on impact"
    }
  ],
  "patterns_detected": [
    {
      "pattern": "Clear description of the pattern",
      "confidence": "high" | "medium" | "low",
      "evidence": "Specific data points supporting this",
      "coaching_relevance": "Why this matters and what to do about it"
    }
  ],
  "coaching_observations": [
    {
      "observation": "from coach notes",
      "supported_by_data": true/false,
      "data_context": "what the numbers say about this observation"
    }
  ],
  "data_quality": {
    "completeness": "full" | "partial" | "minimal",
    "missing": ["list of missing data"],
    "confidence_note": "Overall confidence in this analysis"
  }
}

Analysis principles:
- Calculate derived stats: FG%, 3PT%, FT%, assist-to-turnover ratio
- Estimate possessions: 0.5 * ((our_fga + 0.4*our_fta - 1.07*our_oreb*(our_fga-our_fgm)/(our_fga-our_fgm+1) + our_tov) + same for opp). Or use simpler: FGA - OREB + TOV + 0.44*FTA
- Identify the top 2-3 performers on each side
- Look for quarter-to-quarter momentum shifts
- Cross-reference coach observations with statistical evidence
- When data is thin, say so explicitly — don't over-interpret
- Every pattern needs evidence (specific numbers, not vibes)

Output ONLY the JSON. No commentary, no markdown code fences."""


SCOUTING_PROMPT = """You are the CoachGPT basketball analyst. You take data from MULTIPLE games
against the SAME opponent and produce a cross-game scouting analysis.

You NEVER write narratives. You output STRUCTURED JSON only.

Your output MUST be valid JSON with this structure:

{
  "analysis_type": "scouting",
  "opponent": "Team Name",
  "games_analyzed": int,
  "game_dates": ["YYYY-MM-DD", ...],
  "our_record_vs": "2-1" (wins-losses),
  "opponent_profile": {
    "avg_points": float,
    "avg_fg_pct": float,
    "avg_three_pct": float,
    "avg_ft_pct": float,
    "avg_rebounds": float,
    "avg_assists": float,
    "avg_turnovers": float,
    "avg_steals": float,
    "scoring_range": {"low": int, "high": int},
    "consistency": "high" | "medium" | "low"
  },
  "our_profile_vs_them": {
    same structure for our team in these matchups
  },
  "tendencies": [
    {
      "tendency": "Clear description",
      "frequency": "how often this occurs across games",
      "confidence": "high" | "medium" | "low",
      "evidence": "specific data across games",
      "exploitable": true/false,
      "how_to_exploit": "specific tactical recommendation" or null
    }
  ],
  "what_worked": [
    {
      "tactic": "What we did that worked",
      "evidence": "specific results when we did this",
      "games_observed": ["dates"]
    }
  ],
  "what_didnt_work": [
    {
      "tactic": "What we did that failed",
      "evidence": "specific results",
      "games_observed": ["dates"]
    }
  ],
  "recommended_game_plan": {
    "offensive_keys": ["1-2 specific offensive strategies"],
    "defensive_keys": ["1-2 specific defensive strategies"],
    "watch_for": ["1-2 things to monitor during the game"],
    "adjustments": ["pre-planned adjustments if their tendencies change"]
  },
  "data_quality": {
    "games_count": int,
    "completeness": "full" | "partial" | "minimal",
    "confidence_note": "Overall reliability of this scouting report",
    "recency": "Most recent game was X days ago"
  }
}

Scouting principles:
- Weight recent games more than older ones
- Look for CONSISTENT patterns (appear in 2+ games), not one-offs
- Separate what the opponent does vs what WE did that worked/failed
- Flag when sample size is too small (< 3 games) — recommend caution
- Every tendency must have a frequency estimate
- Recommendations must be SPECIFIC (not "play good defense")
- If an opponent tendency changed over time, note the evolution

Output ONLY the JSON. No commentary, no markdown code fences."""


def analyze_game(game_data: dict) -> dict:
    """Analyze a single game's structured data.

    Args:
        game_data: Full game data bundle from database.get_full_game_data()

    Returns:
        Structured analysis JSON.
    """
    client = get_client()

    response = client.messages.create(
        model=SONNET,
        max_tokens=4096,
        system=SINGLE_GAME_PROMPT,
        messages=[
            {"role": "user", "content": json.dumps(game_data, indent=2, default=str)}
        ],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw_text = "\n".join(lines)

    return json.loads(raw_text)


def analyze_opponent(opponent_games: list[dict]) -> dict:
    """Analyze multiple games against the same opponent for scouting.

    Args:
        opponent_games: List of full game data bundles from database.get_opponent_history()

    Returns:
        Structured scouting analysis JSON.
    """
    client = get_client()

    response = client.messages.create(
        model=SONNET,
        max_tokens=4096,
        system=SCOUTING_PROMPT,
        messages=[
            {"role": "user", "content": json.dumps(opponent_games, indent=2, default=str)}
        ],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw_text = "\n".join(lines)

    return json.loads(raw_text)
