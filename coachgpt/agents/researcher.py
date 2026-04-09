"""Research Agent — Looks up opponent info from public sources and cross-references.

Uses Sonnet with web search context to find opponent game history,
then cross-references with our own database for comparative analysis.
"""

import json
import os

import httpx

from coachgpt.ai_client import get_client, HAIKU, SONNET
from coachgpt import database as db

BRAVE_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")

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


def _brave_search(query: str, count: int = 5) -> list[dict]:
    """Search using Brave Search API. Returns list of {title, url, description}."""
    if not BRAVE_API_KEY:
        return []
    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count},
            headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        results = []
        for item in resp.json().get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            })
        return results
    except Exception as e:
        print(f"  [researcher] Brave search error: {e}")
        return []


def _fetch_page(url: str, timeout: int = 15) -> str:
    """Fetch a web page and return its text content (stripped of HTML tags)."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": "CoachGPT/1.0 (basketball research)"})
        resp.raise_for_status()
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        # Limit to first 8000 chars to avoid token bloat
        return text[:8000]
    except Exception as e:
        print(f"  [researcher] Fetch error for {url}: {e}")
        return ""


def _web_search(client, opponent: str,
                league_info: str = "") -> str:
    """Multi-tier web search with fallback chain and quality tracking.

    Tier 1: Direct known URLs (GC team pages, HCRPS schedule)
    Tier 2: Brave Search (site-specific: GC, HCRPS, Exposure Events)
    Tier 3: Brave Search (general web)
    Each tier logs what it found so we can report data quality.
    """

    source_log = []  # Track what each source returned

    # ── TIER 1: Direct fetch of known URLs ──────────────────────────
    fetched_pages = []

    # Our team's GC schedule (always fetch — shows all opponents we've played)
    our_gc_url = f"https://web.gc.com/teams/{_GC_TEAM_CURRENT}"
    print(f"  [researcher] Tier 1: Fetching our GC schedule: {our_gc_url}")
    our_gc_text = _fetch_page(our_gc_url)
    if our_gc_text and len(our_gc_text) > 200:
        fetched_pages.append(f"SOURCE: Our Team GameChanger Schedule ({our_gc_url})\n{our_gc_text}")
        source_log.append(f"✓ Our GC schedule: {len(our_gc_text)} chars")
    else:
        source_log.append("✗ Our GC schedule: empty or JS-rendered (coach should paste GC data)")

    # Previous season GC (for historical matchups)
    prev_gc_url = f"https://web.gc.com/teams/{_GC_TEAM_PREV}"
    print(f"  [researcher] Tier 1: Fetching previous season GC: {prev_gc_url}")
    prev_gc_text = _fetch_page(prev_gc_url)
    if prev_gc_text and len(prev_gc_text) > 200:
        fetched_pages.append(f"SOURCE: Previous Season GameChanger ({prev_gc_url})\n{prev_gc_text}")
        source_log.append(f"✓ Previous season GC: {len(prev_gc_text)} chars")
    else:
        source_log.append("✗ Previous season GC: empty or JS-rendered")

    # HCRPS standings (direct URL with known IDs)
    hcrps_url = (f"https://www.hcrpsports.org/schedule/print/league_instance/"
                 f"{_LEAGUE_INSTANCE}?schedule_type=index&subseason={_LEAGUE_SUBSEASON}")
    print(f"  [researcher] Tier 1: Fetching HCRPS schedule: {hcrps_url}")
    hcrps_text = _fetch_page(hcrps_url)
    if hcrps_text and len(hcrps_text) > 200:
        fetched_pages.append(f"SOURCE: HCRPS League Schedule ({hcrps_url})\n{hcrps_text}")
        source_log.append(f"✓ HCRPS schedule: {len(hcrps_text)} chars")
    else:
        source_log.append("✗ HCRPS schedule: empty (coach should upload webarchive)")

    # ── TIER 2: Brave Search (site-specific) ────────────────────────
    all_results = []
    if BRAVE_API_KEY:
        site_queries = [
            (f"site:web.gc.com {opponent} basketball", "GameChanger"),
            (f"site:hcrpsports.org {opponent}", "HCRPS"),
            (f"site:exposureevents.com {opponent} basketball", "Exposure Events"),
            (f"\"{_TEAM_NAME}\" vs \"{opponent}\"", "matchup history"),
        ]
        for query, label in site_queries:
            results = _brave_search(query, count=5)
            if results:
                source_log.append(f"✓ Brave [{label}]: {len(results)} results")
                for r in results:
                    if r not in all_results:
                        all_results.append(r)
            else:
                source_log.append(f"✗ Brave [{label}]: no results")

        # ── TIER 3: Brave Search (general) ──────────────────────────
        general_queries = [
            f"{opponent} youth basketball {_TEAM_LOCATION} results 2025 2026",
        ]
        if league_info:
            general_queries.append(f"{opponent} {league_info}")
        for query in general_queries:
            results = _brave_search(query, count=5)
            if results:
                source_log.append(f"✓ Brave [general]: {len(results)} results")
                for r in results:
                    if r not in all_results:
                        all_results.append(r)
    else:
        source_log.append("✗ Brave Search: API key not configured")

    # Fetch top search result pages from priority domains
    priority_domains = ["web.gc.com", "hcrpsports.org", "exposureevents.com", "maxpreps.com"]
    fetch_count = 0
    for r in all_results:
        if fetch_count >= 3:
            break
        url = r.get("url", "")
        if any(domain in url for domain in priority_domains):
            print(f"  [researcher] Fetching search result: {url}")
            page_text = _fetch_page(url)
            if page_text and len(page_text) > 100:
                fetched_pages.append(f"SOURCE: {r['title']} ({url})\n{page_text}")
                fetch_count += 1

    # ── Build source quality report ─────────────────────────────────
    source_report = "SEARCH QUALITY LOG:\n" + "\n".join(source_log)
    successful_sources = sum(1 for s in source_log if s.startswith("✓"))
    total_sources = len(source_log)
    source_report += f"\n\nData coverage: {successful_sources}/{total_sources} sources returned data"

    if successful_sources == 0:
        source_report += ("\n⚠ ALL SOURCES FAILED. Possible reasons:"
                         "\n  - GameChanger pages are JavaScript-rendered (need coach to copy-paste)"
                         "\n  - HCRPS page structure changed (need fresh webarchive upload)"
                         "\n  - Brave API key missing or opponent name doesn't match any results"
                         "\n  - Opponent may not have a public web presence")

    # ── Format for Claude synthesis ─────────────────────────────────
    search_text = ""
    if all_results:
        formatted = []
        for i, r in enumerate(all_results[:15], 1):
            formatted.append(f"{i}. **{r['title']}**\n   URL: {r['url']}\n   {r['description']}")
        search_text = "SEARCH RESULTS:\n" + "\n\n".join(formatted)

    page_content = ""
    if fetched_pages:
        page_content = "\n\nFETCHED PAGE CONTENT:\n" + "\n\n---\n\n".join(fetched_pages)

    if not search_text and not page_content:
        return source_report + "\n\nNo data retrieved from any source."

    # Have Claude synthesize everything
    response = client.messages.create(
        model=HAIKU,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": (
                f"I'm researching basketball team '{opponent}' for an upcoming game.\n\n"
                f"{source_report}\n\n"
                f"{search_text}"
                f"{page_content}\n\n"
                f"Extract ALL factual information about '{opponent}': game results (scores, opponents, "
                f"dates), standings, win-loss record, player names/numbers, tournament placements. "
                f"Also look for any games between '{_TEAM_NAME}' and '{opponent}' in the data.\n\n"
                f"CRITICAL RULES:\n"
                f"1. Only include facts actually present in the data above — NEVER invent results\n"
                f"2. If a page returned empty/JS content, note it as unreliable\n"
                f"3. Clearly label which source each fact came from\n"
                f"4. If data is insufficient, list exactly what the coach should do to get it"
            ),
        }],
    )

    return source_report + "\n\nANALYSIS:\n" + response.content[0].text.strip()


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
