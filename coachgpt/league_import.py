"""League standings import — Parses pasted HCRPS/league standings data.

Supports:
- Pasted standings text (copy from HCRPS website)
- HCRPS webarchive files (Safari Save As)
- HCRPS schedule PDF (printable version)
"""

import plistlib
import re
import uuid

from coachgpt import database as db


def parse_league_standings(raw_text: str, our_team_name: str = "",
                           season_name: str = "") -> dict:
    """Parse pasted league standings into structured data.

    Args:
        raw_text: Raw text copied from HCRPS or similar league site
        our_team_name: Our team name for identification
        season_name: Optional season label (e.g. "Winter 2025-2026 — 7th Grade Alliance")

    Returns:
        Dict with league info, teams, and analysis.
    """
    lines = raw_text.strip().split("\n")

    # Try to find league name / division from header lines
    league_name = ""
    division = ""
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        # Look for division/grade info
        if any(kw in line_clean.upper() for kw in ["GRADE", "DIVISION", "LEAGUE"]):
            if not league_name:
                league_name = line_clean
            else:
                division = line_clean
        # Look for season info
        if re.search(r"(winter|spring|summer|fall)\s+\d{4}", line_clean, re.IGNORECASE):
            division = line_clean

    # Parse team rows — look for lines with W/L/T columns
    teams = []
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # Skip header rows
        if line_clean.startswith("TEAM") or line_clean.startswith("STANDINGS"):
            continue

        # Try to parse: TeamName W L T FOR AGAINST +/-
        # The format may have varying whitespace
        # Match from the RIGHT — last 7 numbers are W L T FOR AGAINST +/-
        # This prevents team names with numbers (e.g. "Drave Sports 2031") from being misread
        match = re.match(
            r'(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s*$',
            line_clean
        )
        if not match:
            continue

        # Validate: the captured numbers should make sense as basketball stats
        # W and L should be small (0-50), FOR and AGAINST should be large (50-999)
        groups = [match.group(i) for i in range(2, 8)]
        nums = [int(g) for g in groups]
        # If "wins" looks like a year (>100), the team name ate a number — re-parse
        if nums[0] > 50:
            # Try greedy match: grab everything up to the last 7 number groups
            match2 = re.match(
                r'(.+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s*$',
                line_clean
            )
            if match2:
                match = match2

        if match:
            team_name = match.group(1).strip()
            wins = int(match.group(2))
            losses = int(match.group(3))
            ties = int(match.group(4))
            points_for = int(match.group(5))
            points_against = int(match.group(6))
            point_diff = int(match.group(7))
            games_played = wins + losses + ties

            ppg = round(points_for / games_played, 1) if games_played > 0 else 0
            papg = round(points_against / games_played, 1) if games_played > 0 else 0
            avg_margin = round(point_diff / games_played, 1) if games_played > 0 else 0

            is_us = False
            if our_team_name:
                # Fuzzy match our team name
                our_parts = our_team_name.lower().split()
                team_lower = team_name.lower()
                if all(p in team_lower for p in our_parts[:2]):
                    is_us = True
                elif "peay" in team_lower and "peay" in our_team_name.lower():
                    is_us = True

            teams.append({
                "team": team_name,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "games_played": games_played,
                "points_for": points_for,
                "points_against": points_against,
                "point_diff": point_diff,
                "ppg": ppg,
                "papg": papg,
                "avg_margin": avg_margin,
                "record": f"{wins}-{losses}" + (f"-{ties}" if ties > 0 else ""),
                "is_us": is_us,
            })

    if not teams:
        return {"error": "Could not parse any teams from the standings data."}

    # Sort by wins (desc), then point diff (desc)
    teams.sort(key=lambda t: (t["wins"], t["point_diff"]), reverse=True)

    # Add rank
    for i, t in enumerate(teams):
        t["rank"] = i + 1

    # Find our team
    our_team = next((t for t in teams if t["is_us"]), None)

    # Generate comparisons for every opponent
    comparisons = []
    if our_team:
        for t in teams:
            if t["is_us"]:
                continue
            margin_diff = our_team["avg_margin"] - t["avg_margin"]
            if margin_diff > 8:
                edge = "Strong favorite"
            elif margin_diff > 3:
                edge = "Favored"
            elif margin_diff > -3:
                edge = "Toss-up"
            elif margin_diff > -8:
                edge = "Underdog"
            else:
                edge = "Big underdog"

            comparisons.append({
                "opponent": t["team"],
                "their_record": t["record"],
                "their_rank": t["rank"],
                "their_ppg": t["ppg"],
                "their_papg": t["papg"],
                "their_avg_margin": t["avg_margin"],
                "our_margin_vs_theirs": round(margin_diff, 1),
                "assessment": edge,
            })

    final_league_name = season_name or league_name or "Unknown League"

    return {
        "league_name": final_league_name,
        "division": division,
        "season_name": season_name,
        "teams_count": len(teams),
        "teams": teams,
        "our_team": our_team,
        "comparisons": comparisons,
    }


def parse_webarchive_schedule(file_bytes: bytes, our_team_name: str = "") -> dict:
    """Parse an HCRPS webarchive file containing game schedule/results.

    Returns dict with league info and individual game results.
    """
    data = plistlib.loads(file_bytes)
    html = data["WebMainResource"]["WebResourceData"].decode("utf-8", errors="ignore")

    # Extract title
    title_match = re.search(r"<header>(.*?)</header>", html, re.DOTALL)
    league_name = ""
    if title_match:
        league_name = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()

    # Extract game rows — handle both formats:
    # 5-col: Visitor, V_Score, Home, H_Score, Location
    # 7-col: Date, Visitor, V_Score, Home, H_Score, Location, Status
    games = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 5:
            continue

        cleaned = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", "").strip() for c in cells]

        # Detect format by finding which cells have numeric scores
        # Try 7-col format first (Date, Visitor, Score, Home, Score, Location, Status)
        date_str = ""
        visitor = v_score = home = h_score = location = ""

        if len(cleaned) >= 7:
            # Check if index 2 and 4 are scores
            try:
                int(cleaned[2])
                int(cleaned[4])
                date_str = cleaned[0]
                visitor = cleaned[1]
                v_score = cleaned[2]
                home = cleaned[3]
                h_score = cleaned[4]
                location = cleaned[5]
            except ValueError:
                pass

        # Fallback to 5-col format
        if not v_score and len(cleaned) >= 5:
            try:
                int(cleaned[1])
                int(cleaned[3])
                visitor = cleaned[0]
                v_score = cleaned[1]
                home = cleaned[2]
                h_score = cleaned[3]
                location = cleaned[4]
            except ValueError:
                continue

        if v_score and h_score:
            try:
                vs = int(v_score)
                hs = int(h_score)
                winner = visitor if vs > hs else home
                games.append({
                    "date": date_str,
                    "visitor": visitor,
                    "visitor_score": vs,
                    "home": home,
                    "home_score": hs,
                    "location": location,
                    "winner": winner,
                })
            except ValueError:
                pass

    if not games:
        return {"error": "No games found in webarchive."}

    # Build team records from game results
    team_stats = {}
    for g in games:
        for side in ["visitor", "home"]:
            team = g[side]
            score = g[f"{side}_score"]
            opp_side = "home" if side == "visitor" else "visitor"
            opp_score = g[f"{opp_side}_score"]

            if team not in team_stats:
                team_stats[team] = {"wins": 0, "losses": 0, "pf": 0, "pa": 0, "games": []}

            team_stats[team]["pf"] += score
            team_stats[team]["pa"] += opp_score
            team_stats[team]["games"].append(g)
            if score > opp_score:
                team_stats[team]["wins"] += 1
            else:
                team_stats[team]["losses"] += 1

    # Convert to standings format
    teams = []
    for name, stats in team_stats.items():
        gp = stats["wins"] + stats["losses"]
        is_us = False
        if our_team_name:
            our_parts = our_team_name.lower().split()[:2]
            if all(p in name.lower() for p in our_parts):
                is_us = True

        teams.append({
            "team": name,
            "wins": stats["wins"],
            "losses": stats["losses"],
            "ties": 0,
            "games_played": gp,
            "points_for": stats["pf"],
            "points_against": stats["pa"],
            "point_diff": stats["pf"] - stats["pa"],
            "ppg": round(stats["pf"] / gp, 1) if gp > 0 else 0,
            "papg": round(stats["pa"] / gp, 1) if gp > 0 else 0,
            "avg_margin": round((stats["pf"] - stats["pa"]) / gp, 1) if gp > 0 else 0,
            "record": f"{stats['wins']}-{stats['losses']}",
            "is_us": is_us,
            "game_results": stats["games"],
        })

    teams.sort(key=lambda t: (t["wins"], t["point_diff"]), reverse=True)
    for i, t in enumerate(teams):
        t["rank"] = i + 1

    our_team = next((t for t in teams if t["is_us"]), None)

    comparisons = []
    if our_team:
        for t in teams:
            if t["is_us"]:
                continue
            margin_diff = our_team["avg_margin"] - t["avg_margin"]
            if margin_diff > 8:
                edge = "Strong favorite"
            elif margin_diff > 3:
                edge = "Favored"
            elif margin_diff > -3:
                edge = "Toss-up"
            elif margin_diff > -8:
                edge = "Underdog"
            else:
                edge = "Big underdog"

            comparisons.append({
                "opponent": t["team"],
                "their_record": t["record"],
                "their_rank": t["rank"],
                "their_ppg": t["ppg"],
                "their_papg": t["papg"],
                "their_avg_margin": t["avg_margin"],
                "our_margin_vs_theirs": round(margin_diff, 1),
                "assessment": edge,
            })

    return {
        "league_name": league_name or "Schedule Import",
        "division": "",
        "teams_count": len(teams),
        "teams": teams,
        "our_team": our_team,
        "comparisons": comparisons,
        "games": games,
        "games_count": len(games),
    }


def save_league_data(league_data: dict) -> str:
    """Save parsed league data to the database as a report for reference."""
    import json
    report_text = format_league_report(league_data)

    # Store the full structured data in analysis_json so we can reload it
    league_json = json.dumps({
        "league_name": league_data.get("league_name"),
        "season_name": league_data.get("season_name"),
        "teams_count": league_data.get("teams_count"),
        "teams": league_data.get("teams"),
        "our_team": league_data.get("our_team"),
        "comparisons": league_data.get("comparisons"),
    })

    report_id = db.save_report(
        game_id=None,
        opponent=league_data.get("league_name", "League"),
        report_type="league_standings",
        analysis_json=league_json,
        report_text=report_text,
    )

    return report_id


def format_league_report(data: dict) -> str:
    """Format league standings into a readable report."""
    lines = [f"# League Standings: {data.get('league_name', 'Unknown')}"]
    if data.get("division"):
        lines.append(f"*{data['division']}*")
    lines.append("")

    # Standings table
    lines.append("| Rank | Team | Record | PPG | Opp PPG | +/- |")
    lines.append("|---:|---|---|---:|---:|---:|")
    for t in data.get("teams", []):
        marker = " **<<**" if t.get("is_us") else ""
        lines.append(
            f"| {t['rank']} | {t['team']}{marker} | {t['record']} | "
            f"{t['ppg']} | {t['papg']} | {t['avg_margin']:+.1f} |"
        )
    lines.append("")

    # Our position
    our = data.get("our_team")
    if our:
        lines.append(f"## Our Position: #{our['rank']} of {data['teams_count']}")
        lines.append(f"**{our['team']}** — {our['record']}, {our['ppg']} PPG, "
                      f"{our['papg']} against, {our['avg_margin']:+.1f} avg margin")
        lines.append("")

    # Comparisons
    comps = data.get("comparisons", [])
    if comps:
        lines.append("## Head-to-Head Projections")
        lines.append("")
        lines.append("| Opponent | Record | Their Margin | Gap | Assessment |")
        lines.append("|---|---|---:|---:|---|")
        for c in comps:
            lines.append(
                f"| {c['opponent']} | {c['their_record']} | "
                f"{c['their_avg_margin']:+.1f} | "
                f"{c['our_margin_vs_theirs']:+.1f} | **{c['assessment']}** |"
            )
        lines.append("")

        # Key insights
        lines.append("## Key Matchups")
        toughest = sorted(comps, key=lambda c: c["our_margin_vs_theirs"])
        for c in toughest[:3]:
            lines.append(f"- **{c['opponent']}** ({c['their_record']}) — {c['assessment']}. "
                          f"They avg {c['their_ppg']} PPG, give up {c['their_papg']}. "
                          f"Margin gap: {c['our_margin_vs_theirs']:+.1f} pts/game.")

    return "\n".join(lines)
