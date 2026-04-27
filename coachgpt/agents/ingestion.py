"""Ingestion Agent — Parses raw game data into structured database records.

Uses Haiku for fast, cheap parsing of GameChanger exports, coach notes,
and manual stats. Supports text, CSV, PDF, and image (screenshot) inputs
via Claude's vision capability.
"""

import base64
import json

from coachgpt.ai_client import get_client, HAIKU

INGESTION_PROMPT = """You are the CoachGPT data ingestion specialist. Your ONLY job is to take
raw basketball game data and output clean, structured JSON.

You will receive one or more of:
- Box score stats (from GameChanger export, CSV, pasted text, PDF, or screenshot image)
- Coach notes (free text observations about the game)
- Game metadata (opponent, date, score, location)

If you receive an IMAGE of a box score (screenshot from GameChanger or similar app):
- Read all visible stats from the image carefully
- Extract player names, numbers, and all stat columns
- Read quarter scores if visible
- Read the final score and team names

Your output MUST be valid JSON with this exact structure:

{
  "game": {
    "date": "YYYY-MM-DD",
    "opponent": "Team Name",
    "our_team": "Our Team Name or null",
    "location": "Venue or null",
    "result": "W" or "L",
    "our_score": integer,
    "opp_score": integer
  },
  "our_player_stats": [
    {
      "team": "ours",
      "player_name": "Name",
      "player_number": "number or null",
      "minutes": integer or null,
      "points": integer,
      "fg_made": integer,
      "fg_attempted": integer,
      "three_made": integer,
      "three_attempted": integer,
      "ft_made": integer,
      "ft_attempted": integer,
      "rebounds": integer,
      "off_rebounds": integer or 0,
      "def_rebounds": integer or 0,
      "assists": integer,
      "steals": integer,
      "blocks": integer,
      "turnovers": integer,
      "fouls": integer,
      "plus_minus": integer or null,
      "source": "gamechanger" or "manual"
    }
  ],
  "opp_player_stats": [same structure with "team": "opponent"],
  "our_team_totals": {
    "team": "ours",
    "quarter": "total",
    "points": integer,
    "fg_made": integer,
    "fg_attempted": integer,
    "three_made": integer,
    "three_attempted": integer,
    "ft_made": integer,
    "ft_attempted": integer,
    "rebounds": integer,
    "assists": integer,
    "steals": integer,
    "blocks": integer,
    "turnovers": integer,
    "fouls": integer,
    "source": "gamechanger" or "manual"
  },
  "opp_team_totals": {same structure with "team": "opponent"},
  "quarter_scores": {
    "ours": {"Q1": int, "Q2": int, "Q3": int, "Q4": int},
    "opponent": {"Q1": int, "Q2": int, "Q3": int, "Q4": int}
  },
  "observations": [
    {
      "category": "opponent_tendency" | "adjustment" | "key_play" | "general",
      "detail": "Structured observation text",
      "quarter": "Q1" | "Q2" | "Q3" | "Q4" | null
    }
  ]
}

Rules:
1. Parse whatever format the stats come in — CSV, table, plain text, image, PDF, etc.
2. CRITICAL: The "Game info" metadata will tell you which team is OURS (the coach's team).
   Use this to correctly assign "ours" vs "opponent" for all stats.
   If it says "Our team is: Maryland Sting" then Maryland Sting = "ours" and the other team = "opponent".
   The coach's notes are always written from OUR perspective — "we pressed", "we lost" etc.
3. If a stat is missing, use 0 (not null) for counting stats.
   EXCEPTION: `plus_minus` should be `null` (not 0) when the box score
   doesn't include it. GameChanger labels the column "+/-" or "PM" — look
   for negative numbers (e.g. "-7"). 0 is a valid plus-minus value (the
   player was on a wash); null means "not reported in this box score".
4. Extract observations from coach notes. Categorize each one:
   - "opponent_tendency": How the opponent played (their patterns)
   - "adjustment": Changes the coach made during the game
   - "key_play": Specific important plays
   - "general": Everything else
5. If you can determine quarter-level info from notes, include the quarter field.
6. If shooting splits (FG, 3PT, FT) are given as percentages, calculate makes/attempts.
7. Validate: points should roughly equal 2*FG2_made + 3*three_made + FT_made.
   If it doesn't add up, keep the raw data and note the discrepancy.
8. If opponent stats are not provided, set opp_player_stats to empty array
   and fill opp_team_totals with whatever you can derive (score, quarter scores).
9. ALWAYS determine result (W/L) from the scores.
10. If the image is unclear or stats are partially visible, extract what you CAN see
    and set missing values to 0. Note any uncertainty in an observation.
11. Output ONLY the JSON. No commentary, no markdown code fences."""


def _parse_json_response(raw_text: str) -> dict:
    """Clean and parse JSON from model response."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


def ingest_game_data(raw_input: str) -> dict:
    """Parse raw text game data into structured format."""
    client = get_client()
    response = client.messages.create(
        model=HAIKU,
        max_tokens=4096,
        system=INGESTION_PROMPT,
        messages=[{"role": "user", "content": raw_input}],
    )
    return _parse_json_response(response.content[0].text)


def ingest_from_image(image_bytes: bytes, media_type: str,
                      coach_notes: str = "", metadata: str = "") -> dict:
    """Parse game data from a screenshot/photo of a box score.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, etc.)
        media_type: MIME type (e.g., "image/png", "image/jpeg")
        coach_notes: Optional coach notes text
        metadata: Optional metadata (opponent, date, etc.)
    """
    client = get_client()
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_image,
            },
        },
        {
            "type": "text",
            "text": "Extract all basketball stats from this box score image.",
        },
    ]

    if metadata:
        content.append({"type": "text", "text": f"Game info: {metadata}"})
    if coach_notes:
        content.append({"type": "text", "text": f"Coach notes: {coach_notes}"})

    response = client.messages.create(
        model=HAIKU,
        max_tokens=4096,
        system=INGESTION_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return _parse_json_response(response.content[0].text)


def ingest_from_pdf(pdf_bytes: bytes,
                    coach_notes: str = "", metadata: str = "") -> dict:
    """Parse game data from a PDF box score export.

    Args:
        pdf_bytes: Raw PDF bytes
        coach_notes: Optional coach notes text
        metadata: Optional metadata (opponent, date, etc.)
    """
    client = get_client()
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64_pdf,
            },
        },
        {
            "type": "text",
            "text": "Extract all basketball stats from this box score PDF.",
        },
    ]

    if metadata:
        content.append({"type": "text", "text": f"Game info: {metadata}"})
    if coach_notes:
        content.append({"type": "text", "text": f"Coach notes: {coach_notes}"})

    response = client.messages.create(
        model=HAIKU,
        max_tokens=4096,
        system=INGESTION_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return _parse_json_response(response.content[0].text)


def ingest_from_csv(csv_text: str,
                    coach_notes: str = "", metadata: str = "") -> dict:
    """Parse game data from a CSV export."""
    combined = f"CSV DATA:\n{csv_text}"
    if metadata:
        combined = f"Game info: {metadata}\n\n{combined}"
    if coach_notes:
        combined += f"\n\nCoach notes: {coach_notes}"
    return ingest_game_data(combined)
