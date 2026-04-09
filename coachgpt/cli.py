"""CoachGPT CLI — Command-line interface for basketball coaching intelligence."""

import json
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel

from coachgpt import database as db
from coachgpt.pipeline import process_game, scout_opponent

console = Console()


@click.group()
def cli():
    """CoachGPT — Basketball coaching intelligence platform."""
    pass


@cli.command()
@click.option("--file", "-f", type=click.Path(exists=True), help="Read game data from a file")
def game(file):
    """Process a new game. Paste stats + notes, get a postgame report.

    You can either paste data interactively or provide a file with --file.

    Examples:
        coachgpt game
        coachgpt game --file game_data.txt
    """
    if file:
        with open(file) as f:
            raw_input = f.read()
    else:
        console.print(
            Panel(
                "[bold]Paste your game data below.[/bold]\n"
                "Include any combination of:\n"
                "  - Box score stats (GameChanger export, CSV, or plain text)\n"
                "  - Coach notes (your observations)\n"
                "  - Score and opponent info\n\n"
                "When done, press [bold]Enter[/bold] twice on an empty line.",
                title="CoachGPT — Game Input",
            )
        )
        lines = []
        empty_count = 0
        while True:
            try:
                line = input()
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                    lines.append(line)
                else:
                    empty_count = 0
                    lines.append(line)
            except EOFError:
                break

        raw_input = "\n".join(lines).strip()

    if not raw_input:
        console.print("[red]No input provided. Aborting.[/red]")
        return

    console.print("\n[bold cyan]Processing game...[/bold cyan]")

    try:
        result = process_game(raw_input)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise

    console.print(f"\n[green]Game stored:[/green] {result['opponent']} ({result['date']}) — {result['result']}")
    console.print(f"[green]Game ID:[/green] {result['game_id']}")
    console.print(f"[green]Report saved:[/green] {result['report_path']}")
    console.print()
    console.print(Panel(Markdown(result["report_text"]), title="Postgame Report"))


@cli.command()
@click.argument("opponent")
def scout(opponent):
    """Generate a scouting report for an opponent.

    Pulls all past games against OPPONENT and generates a cross-game
    scouting report with tendencies and game plan recommendations.

    Example:
        coachgpt scout "Lincoln High"
    """
    console.print(f"\n[bold cyan]Scouting {opponent}...[/bold cyan]")

    try:
        result = scout_opponent(opponent)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise

    if "error" in result:
        console.print(f"\n[red]{result['error']}[/red]")
        console.print("Use [bold]coachgpt game[/bold] to add games first.")
        return

    console.print(f"\n[green]Games analyzed:[/green] {result['games_analyzed']}")
    console.print(f"[green]Report saved:[/green] {result['report_path']}")
    console.print()
    console.print(Panel(Markdown(result["report_text"]), title=f"Scouting Report: {opponent}"))


@cli.command()
@click.option("--opponent", "-o", help="Filter by opponent name")
@click.option("--limit", "-n", default=20, help="Number of games to show")
def games(opponent, limit):
    """List all recorded games.

    Example:
        coachgpt games
        coachgpt games --opponent "Lincoln"
    """
    game_list = db.list_games(opponent=opponent, limit=limit)

    if not game_list:
        console.print("[yellow]No games found.[/yellow]")
        return

    table = Table(title="Recorded Games")
    table.add_column("ID", style="dim")
    table.add_column("Date")
    table.add_column("Opponent")
    table.add_column("Score", justify="right")
    table.add_column("Result", justify="center")

    for g in game_list:
        score = f"{g.get('our_score', '?')}-{g.get('opp_score', '?')}"
        result = g.get("result", "?")
        style = "green" if result == "W" else "red" if result == "L" else ""
        table.add_row(g["id"], g["date"], g["opponent"], score, f"[{style}]{result}[/{style}]")

    console.print(table)


@cli.command()
@click.argument("game_id")
def show(game_id):
    """Show details for a specific game.

    Example:
        coachgpt show abc12345
    """
    game_data = db.get_full_game_data(game_id)
    if not game_data:
        console.print(f"[red]Game '{game_id}' not found.[/red]")
        return

    g = game_data["game"]
    console.print(Panel(
        f"[bold]{g['opponent']}[/bold] — {g['date']}\n"
        f"Score: {g.get('our_score', '?')}-{g.get('opp_score', '?')} ({g.get('result', '?')})\n"
        f"Location: {g.get('location', 'N/A')}",
        title=f"Game {game_id}"
    ))

    # Player stats
    if game_data["our_player_stats"]:
        table = Table(title="Our Player Stats")
        table.add_column("Player")
        table.add_column("PTS", justify="right")
        table.add_column("FG", justify="right")
        table.add_column("3PT", justify="right")
        table.add_column("FT", justify="right")
        table.add_column("REB", justify="right")
        table.add_column("AST", justify="right")
        table.add_column("STL", justify="right")
        table.add_column("TO", justify="right")

        for p in game_data["our_player_stats"]:
            table.add_row(
                p.get("player_name", "?"),
                str(p.get("points", 0)),
                f"{p.get('fg_made', 0)}-{p.get('fg_attempted', 0)}",
                f"{p.get('three_made', 0)}-{p.get('three_attempted', 0)}",
                f"{p.get('ft_made', 0)}-{p.get('ft_attempted', 0)}",
                str(p.get("rebounds", 0)),
                str(p.get("assists", 0)),
                str(p.get("steals", 0)),
                str(p.get("turnovers", 0)),
            )
        console.print(table)

    # Observations
    if game_data["observations"]:
        console.print("\n[bold]Observations:[/bold]")
        for obs in game_data["observations"]:
            q = f"[{obs['quarter']}] " if obs.get("quarter") else ""
            console.print(f"  [{obs['category']}] {q}{obs['detail']}")

    # Reports
    reports = db.get_reports(game_id=game_id)
    if reports:
        console.print(f"\n[bold]Reports:[/bold] {len(reports)} available")
        for r in reports:
            console.print(f"  - {r['report_type']} ({r['created_at']})")


@cli.command()
@click.option("--opponent", "-o", help="Filter by opponent")
@click.option("--type", "-t", "report_type", help="Filter by type: postgame, scouting, trend")
def reports(opponent, report_type):
    """List all generated reports.

    Example:
        coachgpt reports
        coachgpt reports --opponent "Lincoln" --type scouting
    """
    report_list = db.get_reports(opponent=opponent, report_type=report_type)

    if not report_list:
        console.print("[yellow]No reports found.[/yellow]")
        return

    table = Table(title="Reports")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Opponent")
    table.add_column("Game ID", style="dim")
    table.add_column("Created")

    for r in report_list:
        table.add_row(
            r["id"], r["report_type"], r.get("opponent", "—"),
            r.get("game_id", "—"), r["created_at"]
        )

    console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
