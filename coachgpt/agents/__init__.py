"""CoachGPT agents — Ingestion, Analyst, Report Writer."""

from coachgpt.agents.ingestion import ingest_game_data
from coachgpt.agents.analyst import analyze_game, analyze_opponent
from coachgpt.agents.report_writer import write_postgame_report, write_scouting_report

__all__ = [
    "ingest_game_data",
    "analyze_game",
    "analyze_opponent",
    "write_postgame_report",
    "write_scouting_report",
]
