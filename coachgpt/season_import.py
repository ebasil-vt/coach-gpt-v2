"""Season CSV import — Parses GameChanger season stats export."""

import csv
import io
import re

from coachgpt import database as db


def _parse_split(val: str) -> tuple[int, int]:
    """Parse '102-250' into (102, 250)."""
    if not val or val == "-":
        return 0, 0
    parts = val.split("-")
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 0, 0


def _parse_pct(val: str) -> float:
    """Parse '41%' into 0.41."""
    if not val or val == "-":
        return 0.0
    try:
        return float(val.replace("%", "")) / 100.0
    except ValueError:
        return 0.0


def _parse_float(val: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _parse_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def import_season_csv(csv_text: str, season_name: str,
                      team_name: str) -> dict:
    """Import a GameChanger season stats CSV.

    Args:
        csv_text: Raw CSV content
        season_name: e.g. 'Fall 2025'
        team_name: e.g. 'Maryland Sting - Peay 2031 13U'

    Returns:
        Dict with season_id, player_count, and team_totals.
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # Find the header row (contains 'Number', 'Last', 'First')
    header_idx = None
    for i, row in enumerate(rows):
        if len(row) > 2 and row[0].strip() == "Number" and row[1].strip() == "Last":
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("Could not find header row in CSV. Expected 'Number,Last,First,...'")

    headers = [h.strip() for h in rows[header_idx]]

    # Create season
    season_id = db.create_season(
        name=season_name,
        team_name=team_name,
    )

    players_imported = []
    team_totals_row = None

    for row in rows[header_idx + 1:]:
        if len(row) < 10:
            continue

        number = row[0].strip()
        last_name = row[1].strip()
        first_name = row[2].strip()

        # Skip special rows
        if number in ("", "Glossary"):
            continue
        if number == "Totals":
            team_totals_row = row
            continue
        if number == "Unassigned":
            continue
        if not last_name and not first_name:
            continue

        # Get or create the player (persists across seasons)
        player_id = db.get_or_create_player(first_name, last_name, number)

        # Parse stats — GameChanger has both averages and totals columns
        # Headers: Number,Last,First, GP,PPG,PFPG,FG%,3PT%,FT%,TOPG,RPG,APG,SPG,BPG,eFG%,TS%,AST/TO, GP,GS,PTS,PF,FG,3PT,FT,TO,REB,AST,STL,BLK
        # Index:   0      1    2      3  4   5    6   7    8   9    10  11  12  13  14   15  16      17 18 19  20 21 22  23 24 25  26  27  28

        fg_made, fg_attempted = _parse_split(row[21].strip() if len(row) > 21 else "")
        three_made, three_attempted = _parse_split(row[22].strip() if len(row) > 22 else "")
        ft_made, ft_attempted = _parse_split(row[23].strip() if len(row) > 23 else "")

        stats = {
            "games_played": _parse_int(row[17].strip() if len(row) > 17 else row[3].strip()),
            "games_started": _parse_int(row[18].strip() if len(row) > 18 else "0"),
            "points": _parse_int(row[19].strip() if len(row) > 19 else "0"),
            "fg_made": fg_made,
            "fg_attempted": fg_attempted,
            "three_made": three_made,
            "three_attempted": three_attempted,
            "ft_made": ft_made,
            "ft_attempted": ft_attempted,
            "turnovers": _parse_int(row[24].strip() if len(row) > 24 else "0"),
            "rebounds": _parse_int(row[25].strip() if len(row) > 25 else "0"),
            "assists": _parse_int(row[26].strip() if len(row) > 26 else "0"),
            "steals": _parse_int(row[27].strip() if len(row) > 27 else "0"),
            "blocks": _parse_int(row[28].strip() if len(row) > 28 else "0"),
            "fouls": _parse_int(row[20].strip() if len(row) > 20 else "0"),
            "fg_pct": _parse_pct(row[6].strip() if len(row) > 6 else ""),
            "three_pct": _parse_pct(row[7].strip() if len(row) > 7 else ""),
            "ft_pct": _parse_pct(row[8].strip() if len(row) > 8 else ""),
            "ppg": _parse_float(row[4].strip() if len(row) > 4 else ""),
            "rpg": _parse_float(row[10].strip() if len(row) > 10 else ""),
            "apg": _parse_float(row[11].strip() if len(row) > 11 else ""),
            "spg": _parse_float(row[12].strip() if len(row) > 12 else ""),
            "bpg": _parse_float(row[13].strip() if len(row) > 13 else ""),
            "topg": _parse_float(row[9].strip() if len(row) > 9 else ""),
            "source": "gamechanger",
        }

        db.add_season_player(season_id, player_id, number, stats)

        players_imported.append({
            "name": f"{first_name} {last_name}",
            "number": number,
            "games": stats["games_played"],
            "ppg": stats["ppg"],
            "role": _infer_role(stats),
        })

    # Store team totals
    team_totals = {}
    if team_totals_row and len(team_totals_row) > 28:
        fg_m, fg_a = _parse_split(team_totals_row[21].strip())
        three_m, three_a = _parse_split(team_totals_row[22].strip())
        ft_m, ft_a = _parse_split(team_totals_row[23].strip())
        gp = _parse_int(team_totals_row[17].strip())
        pts = _parse_int(team_totals_row[19].strip())

        team_totals = {
            "games_played": gp,
            "points": pts,
            "fg_made": fg_m, "fg_attempted": fg_a,
            "three_made": three_m, "three_attempted": three_a,
            "ft_made": ft_m, "ft_attempted": ft_a,
            "turnovers": _parse_int(team_totals_row[24].strip()),
            "rebounds": _parse_int(team_totals_row[25].strip()),
            "assists": _parse_int(team_totals_row[26].strip()),
            "steals": _parse_int(team_totals_row[27].strip()),
            "blocks": _parse_int(team_totals_row[28].strip()),
            "fouls": _parse_int(team_totals_row[20].strip()),
            "ppg": round(pts / gp, 1) if gp > 0 else 0,
            "fg_pct": round(fg_m / fg_a, 3) if fg_a > 0 else 0,
            "three_pct": round(three_m / three_a, 3) if three_a > 0 else 0,
            "ft_pct": round(ft_m / ft_a, 3) if ft_a > 0 else 0,
        }
        db.save_team_season_totals(season_id, team_totals)

    # Update season with game count
    conn = db.get_connection()
    gp = team_totals.get("games_played", 0)
    conn.execute("UPDATE seasons SET games_played = ? WHERE id = ?", (gp, season_id))
    conn.commit()
    conn.close()

    return {
        "season_id": season_id,
        "season_name": season_name,
        "team_name": team_name,
        "players_imported": len(players_imported),
        "games_played": team_totals.get("games_played", 0),
        "players": players_imported,
        "team_totals": team_totals,
    }


def _infer_role(stats: dict) -> str:
    """Infer a player's role from their stats."""
    ppg = stats.get("ppg", 0)
    apg = stats.get("apg", 0)
    spg = stats.get("spg", 0)
    rpg = stats.get("rpg", 0)
    gp = stats.get("games_played", 0)

    if gp < 5:
        return "Reserve"

    roles = []
    if ppg >= 8:
        roles.append("Scorer")
    if apg >= 3:
        roles.append("Playmaker")
    if spg >= 2:
        roles.append("Disruptor")
    if rpg >= 5:
        roles.append("Rebounder")
    if ppg < 3 and gp >= 15:
        roles.append("Role Player")

    return " / ".join(roles) if roles else "Contributor"
