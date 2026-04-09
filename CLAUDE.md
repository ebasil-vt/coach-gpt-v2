# CoachGPT — Basketball Coaching Intelligence Platform

## Project Overview
CoachGPT is an AI-powered basketball coaching assistant for youth basketball (Maryland Sting 2031 - Peay). It processes game data, generates scouting reports, pre-game briefs, and opponent analysis using Claude AI agents.

## Tech Stack
- **Backend**: Python 3.13, FastAPI, SQLite
- **AI**: Anthropic Claude API (Haiku for parsing, Sonnet for analysis/writing)
- **Frontend**: Single-page HTML/CSS/JS (vanilla, no framework)
- **Hosting Target**: AWS (EC2 + Bedrock)

## Project Structure
```
coach-gpt/
├── coachgpt/
│   ├── __init__.py
│   ├── cli.py                 # CLI interface
│   ├── database.py            # SQLite schema + CRUD operations
│   ├── pipeline.py            # Agent orchestration: Ingest → Analyze → Report
│   ├── season_import.py       # GameChanger season CSV parser
│   ├── league_import.py       # HCRPS league standings/schedule parser
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── ingestion.py       # Parses raw data → structured JSON (Haiku)
│   │   ├── analyst.py         # Pattern detection → analysis JSON (Sonnet)
│   │   ├── report_writer.py   # Generates narrative reports (Sonnet)
│   │   └── researcher.py      # Opponent web lookup + cross-reference (Sonnet)
│   └── web/
│       ├── __init__.py
│       ├── server.py          # FastAPI server + SSE streaming + auth
│       └── static/
│           └── index.html     # Full web UI (7 tabs)
├── tests/                     # Sample game data files
├── reports/                   # Generated report files
├── data/                      # SQLite database (gitignored)
├── COACH-GUIDE.md             # End-user guide for coaches
├── system-architecture.md     # Full system design document
├── agent-architecture.md      # Agent design + workflow documentation
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Project config
├── Procfile                   # Process file for deployment
└── runtime.txt                # Python version
```

## Running Locally
```bash
cd ~/projects/coach-gpt
source .venv/bin/activate
export ANTHROPIC_API_KEY="sk-ant-..."
python -m coachgpt.web.server
# Opens on http://localhost:8080
```

## Environment Variables
| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (direct API) | Anthropic API key |
| `AWS_REGION` | Yes (Bedrock) | AWS region for Bedrock (e.g. us-east-1) |
| `AWS_ACCESS_KEY_ID` | Yes (Bedrock) | IAM credentials for Bedrock |
| `AWS_SECRET_ACCESS_KEY` | Yes (Bedrock) | IAM credentials for Bedrock |
| `COACHGPT_PASSWORD` | Optional | Password protection for web UI |
| `RAILWAY_VOLUME_MOUNT_PATH` | Optional | Persistent storage path (Railway) |
| `PORT` | Optional | Server port (default 8080) |

## Database
- SQLite at `data/games.db` (auto-created on first run)
- Path configurable via `RAILWAY_VOLUME_MOUNT_PATH` env var
- Tables: games, player_stats, team_stats, observations, clips, reports, seasons, roster, season_roster, team_season_totals, opponent_players

## AI Agents (4 agents)
1. **Ingestion Agent** (Haiku) — Parses text/PDF/image/CSV into structured JSON
2. **Game Analyst** (Sonnet) — Computes patterns, detects tendencies, cross-game analysis
3. **Report Writer** (Sonnet) — Generates postgame, scouting, pre-game, team identity reports
4. **Research Agent** (Sonnet + Haiku) — Web lookup for opponents, cross-references common opponents

## Web UI (7 tabs)
1. **New Game** — Structured form: opponent, date, score, box score upload, coach notes (4 sections)
2. **Team** — Season CSV import, player cards with stat bars, team identity report
3. **League** — Standings import (paste text or upload webarchive), league dropdown, game-by-game breakdowns
4. **Games** — List all processed games
5. **Reports** — All reports with type filter (postgame, scouting, pregame, research, league, team_identity)
6. **Scout** — Opponent search with 3 actions (Scout, Pre-Game, Research), opponent player cards with add/edit/delete
7. **Guide** — Coach's usage guide

## Features Built
- Multi-format ingestion (text, PDF, image via Claude Vision, CSV)
- SSE streaming for real-time agent progress in UI
- Password-protected web access
- League standings parsing from HCRPS webarchive files
- Game-by-game breakdown per team from league schedule data
- Opponent player tendency tracking across games
- Post-game follow-up prompts (GC link, tendencies, adjustments)
- Copy/print buttons on all reports
- Print-friendly CSS
- Season roster management (players persist across seasons)

## Known Data Sources
### GameChanger
- Previous season team: https://web.gc.com/teams/vf2TC4nINA77
- Current season team: https://web.gc.com/teams/VGbwJULEMkSE
- Per-game recap: https://web.gc.com/teams/{TEAM_ID}/schedule/{GAME_ID}/recap
- Season stats CSV export from web.gc.com (staff account)
- Box score PDF export from GC app

### HCRPS (Howard County Recreation & Parks Sports)
- League schedule (all games): https://www.hcrpsports.org/schedule/print/league_instance/{LEAGUE_ID}?schedule_type=index&subseason={SEASON_ID}
- Winter 2025-2026: league_instance=228050, subseason=957781, team_instance=10442151
- Winter 2026-2027: new season registered, IDs TBD
- Save pages as Safari webarchive → upload to CoachGPT for automatic parsing

## AWS Deployment TODO
### Switch from Direct Anthropic API to Bedrock
All agent files use `anthropic.Anthropic()` client. To switch to Bedrock:

1. Install bedrock support: `pip install anthropic[bedrock]`
2. Change client initialization in all agent files:
   ```python
   # FROM:
   client = anthropic.Anthropic()
   
   # TO:
   client = anthropic.AnthropicBedrock(aws_region=os.environ.get("AWS_REGION", "us-east-1"))
   ```
3. Update model names:
   ```python
   # FROM:
   model="claude-haiku-4-5-20251001"
   model="claude-sonnet-4-6"
   
   # TO:
   model="us.anthropic.claude-haiku-4-5-20251001-v1:0"
   model="us.anthropic.claude-sonnet-4-6-v1:0"
   ```

Files to update:
- `coachgpt/agents/ingestion.py` — 4 places (ingest_game_data, ingest_from_image, ingest_from_pdf, ingest_from_csv)
- `coachgpt/agents/analyst.py` — 2 places (analyze_game, analyze_opponent)
- `coachgpt/agents/report_writer.py` — 4 places (write_postgame_report, write_scouting_report, write_pregame_brief, write_team_identity)
- `coachgpt/agents/researcher.py` — 2 places (research_opponent, _web_search)

**Recommended approach**: Create a shared client factory:
```python
# coachgpt/ai_client.py
import os
import anthropic

def get_client():
    if os.environ.get("AWS_REGION"):
        return anthropic.AnthropicBedrock(
            aws_region=os.environ["AWS_REGION"]
        )
    return anthropic.Anthropic()

HAIKU = os.environ.get("COACHGPT_MODEL_HAIKU", "claude-haiku-4-5-20251001")
SONNET = os.environ.get("COACHGPT_MODEL_SONNET", "claude-sonnet-4-6")
```
Then all agents import `from coachgpt.ai_client import get_client, HAIKU, SONNET`.

### AWS Infrastructure Setup
1. **EC2 t3.micro** or **Lightsail $3.50/month** instance
2. **Security group**: allow port 80/443 inbound
3. **IAM role** for Bedrock: `coachgpt-bedrock-role`
   - Policy: `bedrock:InvokeModel` on Claude Haiku and Sonnet only
   - NO access to Opus or other expensive models
4. **EBS volume**: 10GB for SQLite persistence
5. **AWS Budget**: alert at $20/month
6. **Optional**: Route 53 domain + ACM certificate for HTTPS

### Bedrock IAM Policy (minimal)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/us.anthropic.claude-sonnet-4-6-v1:0"
      ]
    }
  ]
}
```

### Deploy Steps
1. Launch EC2 t3.micro (Ubuntu 24.04)
2. Install Python 3.13, git, pip
3. Clone repo: `git clone <repo-url>`
4. Install deps: `pip install -r requirements.txt`
5. Set env vars (or use AWS Systems Manager Parameter Store)
6. Run: `uvicorn coachgpt.web.server:app --host 0.0.0.0 --port 80`
7. Use systemd to run as service (survives reboots)

## Cost Model
| Component | Estimated Monthly Cost |
|---|---|
| EC2 t3.micro | $8 (or Lightsail $3.50) |
| Bedrock Haiku calls | $1-3 |
| Bedrock Sonnet calls | $3-10 |
| EBS 10GB | $1 |
| **Total** | **$13-22/month** |

Per-game cost: ~$0.15-0.20
Full 30-game season: ~$5-10 in API calls

## Team Info
- **Team**: Maryland Sting 2031 - Peay
- **Location**: Columbia, MD
- **League**: HCRPS (Howard County Recreation & Parks Sports)
- **Previous Season**: Winter 2025-2026, 7th Grade Alliance — 9-0 undefeated
- **Current Season**: Winter 2026-2027 (just started)
- **Fall 2025 Stats**: 44 games, 13 players imported from GameChanger CSV
