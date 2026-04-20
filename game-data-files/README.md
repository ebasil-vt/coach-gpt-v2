# Game Data Files

Raw game data organized by season. Upload these through the CoachGPT web UI.

## Structure

```
game-data-files/
├── {Season Name}/
│   ├── season-stats/          GameChanger season CSV export
│   │   └── *.csv              Team > Stats > Export from GC
│   ├── league-standings/      HCRPS league data
│   │   └── *.webarchive       Safari Save As > Web Archive from hcrpsports.org
│   ├── league-games/          League game box scores
│   │   └── *.pdf              GameChanger box score PDF exports
│   └── tournament-{name}/     Tournament game box scores
│       └── *.pdf              GameChanger box score PDF exports
```

## How to Use

| File Type | Where to Upload | Tab |
|-----------|----------------|-----|
| Season CSV (`.csv`) | Import Season Stats | Team |
| Webarchive (`.webarchive`) | Import League Data | League |
| Box score PDF (`.pdf`) | Upload box score | New Game |

## Seasons

- **Fall 2025** — 13U, HCRPS league (39 games in CSV)
- **Winter 2026-2027** — 14U, league games + tournaments

## HCRPS IDs

These are embedded in the webarchive filenames:

- `228050` = league_instance (HCRPS league)
- `10442151` = team_instance (Maryland Sting - Peay)
