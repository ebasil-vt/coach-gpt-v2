# CoachGPT — Agent Architecture & Workflows

## Design Philosophy

Based on Anthropic's latest guidance (2025):

1. **Start with the simplest pattern that works** — prompt chaining before multi-agent
2. **Use the Orchestrator-Workers pattern** — one brain routes to specialized workers
3. **Agents are for reasoning, not computation** — CV pipelines and stat calculations are code, not agents
4. **Context is finite** — each agent gets only what it needs, not everything
5. **Multi-agent excels when tasks parallelize** — scouting 5 opponents at once, processing multiple games simultaneously

---

## The 5 Agents

```
                    ┌─────────────────────────────────┐
                    │      1. ORCHESTRATOR AGENT       │
                    │  Routes tasks, manages state,    │
                    │  coordinates all other agents    │
                    └──────────────┬──────────────────┘
                                   │
              ┌────────────┬───────┼───────┬────────────┐
              ▼            ▼       ▼       ▼            ▼
   ┌──────────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐
   │ 2. INGESTION │ │ 3. GAME   │ │ 4. REPORT│ │ 5. VISION    │
   │    AGENT     │ │  ANALYST  │ │  WRITER  │ │    AGENT     │
   │              │ │   AGENT   │ │  AGENT   │ │  (Phase 3+)  │
   │ Parses data  │ │ Computes  │ │ Generates│ │ Processes    │
   │ structures it│ │ patterns  │ │ narrative│ │ video → data │
   └──────────────┘ └───────────┘ └──────────┘ └──────────────┘
```

---

## Agent 1: Orchestrator

### Role
The brain of the system. Every user request enters here. It classifies the task, gathers context, routes to the right worker agent(s), and assembles the final output.

### When Active
Always — every interaction flows through this agent.

### Pattern
**Routing + Orchestrator-Workers** (Anthropic patterns #3 and #5)

The orchestrator never does the actual work. It:
1. Classifies the intent ("process a game," "scout an opponent," "show me trends")
2. Determines which agents to invoke (sometimes in parallel)
3. Passes structured context to each worker (not raw user input)
4. Receives structured output from workers
5. Assembles and delivers the final result

### Tools
- `Read`, `Glob`, `Grep` — access game database and stored files
- `Agent` — spawn and coordinate worker agents
- `AskUserQuestion` — clarify ambiguous requests
- Custom MCP tools:
  - `game_db.list_games` — query game database
  - `game_db.get_game` — retrieve specific game data
  - `game_db.get_opponent_history` — pull all games vs an opponent

### System Prompt (Core)
```
You are the CoachGPT orchestrator. You manage a basketball coaching
intelligence system. When a coach makes a request, you:

1. Classify the request type:
   - INGEST: New game data, stats, notes, or clips to process
   - ANALYZE: Question about patterns, tendencies, or stats
   - REPORT: Generate a postgame, scouting, or trend report
   - VIDEO: Process video footage (Phase 3+)
   - LIVE: Real-time game mode (Phase 4+)

2. Gather the minimum context needed from the database
3. Route to the appropriate worker agent(s)
4. If multiple agents are needed, run them in parallel when possible
5. Assemble the final output and deliver to the coach

Rules:
- Never generate reports yourself — always delegate to Report Writer
- Never parse raw data yourself — always delegate to Ingestion Agent
- For scouting reports, FIRST use Game Analyst to compute cross-game
  stats, THEN pass structured analysis to Report Writer
- Always confirm with coach before overwriting existing game data
```

### SDK Configuration
```python
orchestrator_options = ClaudeAgentOptions(
    system_prompt=ORCHESTRATOR_PROMPT,
    model="sonnet",  # Fast routing, doesn't need Opus
    allowed_tools=[
        "Read", "Glob", "Grep", "Agent", "AskUserQuestion",
        "mcp__game_db__list_games",
        "mcp__game_db__get_game",
        "mcp__game_db__get_opponent_history",
    ],
    agents={
        "ingestion": ingestion_agent_def,
        "analyst": analyst_agent_def,
        "report_writer": report_writer_def,
        "vision": vision_agent_def,  # Phase 3+
    },
    max_turns=15,
    max_budget_usd=0.50,  # Cap per request
)
```

---

## Agent 2: Ingestion Agent

### Role
Parses, validates, and structures all incoming data. Takes messy inputs (GameChanger exports, free-text notes, clip files, CSV stats) and transforms them into clean, structured database records.

### When Active
Every time new game data enters the system.

### Pattern
**Prompt Chain** (Anthropic pattern #2) — Parse → Validate → Store → Confirm

### What It Handles

| Input Type | How It Arrives | What Agent Does |
|---|---|---|
| GameChanger box score | CSV paste or screenshot | Extracts player stats, team totals, validates numbers |
| Coach notes | Free text | Extracts structured observations (opponent tendencies, key plays, adjustments made) |
| Clip metadata | File upload with tags | Validates tags, extracts timestamps, links to game record |
| Manual stats | Form entry | Validates against known ranges, flags anomalies |
| Opponent info | Name, record, roster | Creates/updates opponent profile |

### Tools
- `Read`, `Write`, `Edit` — file operations for data storage
- `Bash` — run data validation scripts
- Custom MCP tools:
  - `game_db.create_game` — create new game record
  - `game_db.upsert_stats` — add/update stats
  - `game_db.add_clips` — register clip files
  - `game_db.add_notes` — store structured notes

### System Prompt (Core)
```
You are the CoachGPT data ingestion specialist. Your job is to take
raw, messy data from various sources and structure it cleanly.

When you receive data:
1. Identify the data type (box score, notes, clips, roster, etc.)
2. Parse into structured format
3. Validate:
   - Stats must be numerically reasonable (no 200-point games)
   - Player names should match known roster if available
   - Timestamps should be valid
   - Tags should match allowed categories
4. Store in the database using provided tools
5. Return a structured confirmation of what was stored

IMPORTANT:
- If data is ambiguous, return specific questions (don't guess)
- If GameChanger data conflicts with manual entry, flag the conflict
- Always track data source (gamechanger, manual, coach_notes, video_cv)
- When processing box scores, calculate derived stats:
  - Team FG%, 3PT%, FT%
  - Team rebounds, assists, turnovers
  - Pace estimate (possessions per game)
```

### SDK Configuration
```python
ingestion_options = ClaudeAgentOptions(
    system_prompt=INGESTION_PROMPT,
    model="haiku",  # Parsing/structuring is simple — use cheapest model
    allowed_tools=[
        "Read", "Write", "Edit",
        "mcp__game_db__create_game",
        "mcp__game_db__upsert_stats",
        "mcp__game_db__add_clips",
        "mcp__game_db__add_notes",
    ],
    max_turns=10,
    max_budget_usd=0.05,  # Ingestion should be cheap
)
```

### Example Workflow

```
Coach: "Here's tonight's game stats from GameChanger:
        [pastes CSV or screenshot text]
        We played Lincoln High. We won 58-52.
        Notes: They ran a lot of transition in Q1-Q2 but
        we shut it down with press in the second half."

Ingestion Agent:
  1. Parses CSV → extracts player stats
  2. Creates game record: {date, opponent: "Lincoln High", score: "58-52 W"}
  3. Stores player stats with source: "gamechanger"
  4. Parses notes → structures as:
     {
       "observations": [
         {"type": "opponent_tendency", "detail": "heavy transition Q1-Q2"},
         {"type": "adjustment", "detail": "full court press Q3-Q4"},
         {"type": "adjustment_result", "detail": "shut down transition"}
       ]
     }
  5. Returns confirmation with game_id
```

---

## Agent 3: Game Analyst

### Role
The statistical engine. Takes structured game data and computes patterns, tendencies, comparisons, and anomalies. This agent COMPUTES — it doesn't narrate. It produces structured JSON that the Report Writer turns into prose.

### When Active
Before every report generation. Also on-demand for coach questions about stats/patterns.

### Pattern
**Augmented LLM + Tool Use** (Anthropic pattern #1) — Claude reasons about what to compute, calls statistical tools, interprets results

### What It Computes

| Analysis Type | Input | Output |
|---|---|---|
| **Single-game stats** | One game record | Derived metrics (pace, efficiency, shooting splits) |
| **Opponent profile** | All games vs one opponent | Aggregated tendencies, consistency scores |
| **Trend detection** | Season games for your team | Performance trends over time, regression/improvement areas |
| **Matchup comparison** | Two teams' profiles | Strength vs weakness mapping |
| **Anomaly detection** | Game stats vs season averages | "This was unusual" flags |

### Tools
- `Read`, `Bash` — access data and run computation scripts
- Custom MCP tools:
  - `stats.compute_team_metrics` — aggregated team stats
  - `stats.compute_opponent_profile` — cross-game opponent analysis
  - `stats.detect_trends` — season trend detection
  - `stats.compare_matchup` — head-to-head analysis
  - `stats.detect_anomalies` — unusual performance flags

### System Prompt (Core)
```
You are the CoachGPT analyst. You compute basketball statistics
and detect patterns. You NEVER write narratives or reports —
you produce structured analysis that the Report Writer uses.

Your output format is ALWAYS structured JSON:
{
  "analysis_type": "postgame" | "scouting" | "trend" | "matchup",
  "game_ids": [...],
  "team_metrics": { ... },
  "opponent_metrics": { ... },
  "patterns_detected": [
    {
      "pattern": "description",
      "confidence": "high" | "medium" | "low",
      "evidence": "specific data points",
      "coaching_relevance": "why this matters"
    }
  ],
  "anomalies": [ ... ],
  "key_stats": { ... }
}

Analysis principles:
- Always compute per-quarter breakdowns (not just game totals)
- Flag when sample size is too small for reliable patterns (< 3 games)
- Compare against baselines when available (season avg, league avg)
- Separate "facts" (hard stats) from "inferences" (pattern interpretations)
- When data is incomplete, explicitly note what's missing and how it
  affects confidence
- For opponent scouting, weight recent games more than older ones
```

### SDK Configuration
```python
analyst_options = ClaudeAgentOptions(
    system_prompt=ANALYST_PROMPT,
    model="sonnet",  # Needs reasoning for pattern detection
    allowed_tools=[
        "Read", "Bash",
        "mcp__stats__compute_team_metrics",
        "mcp__stats__compute_opponent_profile",
        "mcp__stats__detect_trends",
        "mcp__stats__compare_matchup",
        "mcp__stats__detect_anomalies",
    ],
    max_turns=20,
    max_budget_usd=0.30,
)
```

### Example Output

```json
{
  "analysis_type": "scouting",
  "opponent": "Lincoln High",
  "games_analyzed": 3,
  "opponent_metrics": {
    "avg_points": 54.3,
    "avg_pace": 68.2,
    "transition_rate": 0.42,
    "half_court_rate": 0.58,
    "fg_pct": 0.44,
    "three_pct": 0.31,
    "ft_pct": 0.68,
    "turnovers_per_game": 15.3
  },
  "patterns_detected": [
    {
      "pattern": "Heavy transition offense in Q1, decreases each quarter",
      "confidence": "high",
      "evidence": "Q1 transition rate 0.55 vs Q4 rate 0.28 across all 3 games",
      "coaching_relevance": "Start in press to disrupt early transition; they don't adjust well"
    },
    {
      "pattern": "Weak left-side half-court offense",
      "confidence": "medium",
      "evidence": "Only 22% of half-court possessions attack left side; shoot 31% from left wing",
      "coaching_relevance": "Force them left in half-court sets"
    }
  ],
  "anomalies": [],
  "data_gaps": ["No Q4 breakdown available for game 2 (GameChanger partial)"]
}
```

---

## Agent 4: Report Writer

### Role
The storyteller. Takes structured analysis (JSON from Game Analyst) and generates coach-readable narrative reports. This is where Claude's language ability shines — turning numbers into coaching decisions.

### When Active
After every analysis. Produces the final deliverable the coach reads.

### Pattern
**Prompt Chain with Evaluation** (Anthropic patterns #2 + #6) — Draft → Self-evaluate → Refine

### What It Produces

| Report Type | Input | Output Format | Length |
|---|---|---|---|
| **Postgame report** | Single-game analysis JSON + coach notes | PDF/Markdown | 400-600 words |
| **Opponent scouting report** | Cross-game opponent profile JSON | PDF/Markdown | 600-1000 words |
| **Season trend report** | Season analysis JSON | PDF/Markdown | 500-800 words |
| **Halftime quick take** | Q1-Q2 partial analysis (Phase 4+) | Plain text / push notification | 100-150 words |
| **Pre-game brief** | Opponent profile + last matchup | PDF/Markdown | 300-500 words |

### Tools
- `Read`, `Write` — read templates and write output reports
- Custom MCP tools:
  - `reports.render_pdf` — convert markdown to formatted PDF
  - `reports.get_template` — load report template
  - `reports.store_report` — save to report database

### System Prompt (Core)
```
You are the CoachGPT report writer. You take structured basketball
analysis data and produce clear, actionable coaching reports.

Report principles:
1. LEAD WITH ACTIONABLE INSIGHT — First sentence should be something
   the coach can ACT on. Not "Lincoln scored 54 points." Instead:
   "Lincoln's transition offense is their weapon — press early to
   neutralize it."

2. STRUCTURE:
   - Headline insight (1 sentence)
   - Summary (2-3 sentences)
   - Key patterns with evidence (bullet points)
   - Quarter-by-quarter breakdown (when applicable)
   - Tactical recommendations (numbered, specific)
   - Data confidence note (what we know vs what we're inferring)

3. TONE: Direct, coaching language. Not academic. Not corporate.
   Write like a trusted assistant coach who watched the film.
   "They collapse the paint" not "The opponent demonstrates a
   tendency toward interior defensive consolidation."

4. HONESTY: If data is thin (< 3 games), say so. "Based on only
   2 games — take this with a grain of salt." Coaches respect
   honesty more than false confidence.

5. NEVER FABRICATE STATS. If the analysis JSON doesn't include a
   number, don't invent one. Say "we don't have data on X" instead.

6. REFERENCE SPECIFIC GAMES when possible: "In the Feb 12 game,
   their transition rate dropped to 25% after you pressed."

7. RECOMMENDATIONS must be SPECIFIC:
   Bad: "Consider adjusting your defense"
   Good: "Start Q1 in 1-2-2 press. Their transition drops 30% when
   pressured. Switch to half-court zone when they adjust (~Q2)."
```

### SDK Configuration
```python
report_writer_options = ClaudeAgentOptions(
    system_prompt=REPORT_WRITER_PROMPT,
    model="sonnet",  # Needs strong writing ability
    allowed_tools=[
        "Read", "Write",
        "mcp__reports__render_pdf",
        "mcp__reports__get_template",
        "mcp__reports__store_report",
    ],
    max_turns=10,
    max_budget_usd=0.20,
)
```

### Example Output (Postgame)

```markdown
# Postgame Report: vs Lincoln High — W 58-52

## Start in press next time. Lincoln lives off transition and
dies in the half-court.

Lincoln ran transition on 42% of possessions — well above their
season average. Your second-half press cut that to 22% and they
had no answer. Their half-court offense is exploitable, especially
when forced left.

### Key Patterns

- **Transition-heavy Q1-Q2**: 55% of possessions in transition,
  scored on 68% of them. This is their identity.
- **Press vulnerability**: Your Q3 press forced 8 backcourt turnovers.
  They didn't adjust for 6 minutes.
- **Weak left side**: Only 22% of half-court attacks went left.
  When forced left, they shot 31% — 13 points below their average.
- **Free throw liability**: 68% FT shooting. Fouling in the bonus
  is less costly than giving up transition layups.

### Quarter Breakdown

| | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| Your score | 12 | 14 | 18 | 14 |
| Lincoln score | 16 | 15 | 10 | 11 |
| Lincoln transition % | 55% | 48% | 25% | 19% |
| Lincoln FG% | 52% | 48% | 33% | 35% |

### Recommendations for Next Matchup

1. **Start in full-court press from Q1.** Don't wait until Q3.
   Their Q1 transition rate is 55% — eliminate it immediately.
2. **Force left in half-court.** Overplay the right wing passing lane.
   They shoot 31% when forced left vs 47% going right.
3. **Foul aggressively inside.** Their 68% FT rate makes fouling
   a better tradeoff than allowing paint finishes.

### Data Confidence
Based on tonight's game + 2 prior matchups this season. Transition
pattern is consistent across all 3 games (high confidence). Left-side
weakness observed in 2 of 3 games (medium confidence).
```

---

## Agent 5: Vision Agent (Phase 3+)

### Role
Processes video footage into structured tracking data. This agent is a **hybrid** — it uses Claude for reasoning about what to extract and how to interpret results, but delegates the actual CV computation to Python scripts and ML models running as tools.

### When Active
Phase 3: Post-game video processing (batch)
Phase 4+: Live game processing (real-time)

### Pattern
**Augmented LLM** (Anthropic pattern #1) — Claude orchestrates the CV pipeline tools, interprets results, and handles edge cases. The heavy computation (YOLO, ByteTrack, homography) runs in Python scripts invoked as tools.

### What It Does

| Mode | Input | Processing | Output |
|---|---|---|---|
| **Post-game batch** | Full game MP4 | Run full CV pipeline, extract all events | Tracking data + events + clips |
| **Clip analysis** | 20-30s clip | Detect players, classify transition/half-court | Tagged clip with structured metadata |
| **Live processing** (Phase 4+) | Real-time camera feed | Continuous CV pipeline | Live dashboard data + recorded events |

### Tools
- `Bash` — execute CV pipeline scripts
- `Read`, `Write` — handle data files
- Custom MCP tools:
  - `cv.run_detection` — run YOLO on video segment
  - `cv.run_tracking` — run ByteTrack on detections
  - `cv.calibrate_court` — compute homography from court points
  - `cv.classify_teams` — run jersey color clustering
  - `cv.extract_events` — run rule-based event extraction
  - `cv.generate_heatmap` — produce team heatmap from tracking data
  - `cv.segment_possessions` — split game into possession clips

### System Prompt (Core)
```
You are the CoachGPT vision processing agent. You orchestrate
computer vision tools to extract basketball intelligence from
video footage.

Your workflow for processing a game:
1. Check video quality and length
2. If court calibration doesn't exist, request manual calibration
   (4 court points) or attempt auto-detection
3. Run detection pipeline (YOLO) on video segments
4. Run tracking pipeline (ByteTrack) on detections
5. Run team classification on tracked players
6. Run event extraction on tracking data
7. Generate heatmaps and zone stats
8. Segment into possession clips
9. Output structured data matching the game database schema

Quality checks at each step:
- Detection rate: flag if < 8 persons detected on average (expect 10+)
- Tracking continuity: flag if average track length < 30 frames
- Team classification: flag if > 10% "unknown" team labels
- Court mapping: flag if positions fall outside court bounds > 5%

When quality is low:
- Do NOT silently proceed with bad data
- Report the quality issue and what caused it (camera angle,
  lighting, occlusion, etc.)
- Suggest whether the data is usable with caveats or should
  be discarded
```

### SDK Configuration
```python
vision_options = ClaudeAgentOptions(
    system_prompt=VISION_PROMPT,
    model="haiku",  # Orchestrating tools, not deep reasoning
    allowed_tools=[
        "Bash", "Read", "Write",
        "mcp__cv__run_detection",
        "mcp__cv__run_tracking",
        "mcp__cv__calibrate_court",
        "mcp__cv__classify_teams",
        "mcp__cv__extract_events",
        "mcp__cv__generate_heatmap",
        "mcp__cv__segment_possessions",
    ],
    max_turns=30,  # CV pipeline has many steps
    max_budget_usd=0.15,  # Most compute is in Python tools, not LLM
)
```

---

## 5 Core Workflows

### Workflow 1: Process a New Game (Phase 1 — Day 1)

```
COACH: "Here's tonight's game against Lincoln. [stats + notes]"
         │
         ▼
┌─────────────────┐
│  ORCHESTRATOR    │  Classifies as INGEST + ANALYZE + REPORT
│  Routes to:      │
│  1. Ingestion    │  (first)
│  2. Analyst      │  (after ingestion)
│  3. Report Writer│  (after analysis)
└────────┬────────┘
         │
         ▼ Step 1: Ingest
┌─────────────────┐
│  INGESTION      │  Parses stats, structures notes
│  AGENT          │  Creates game record in DB
│  (Haiku)        │  Returns: game_id, structured data
└────────┬────────┘
         │
         ▼ Step 2: Analyze
┌─────────────────┐
│  GAME ANALYST   │  Computes derived stats
│  AGENT          │  Detects patterns (transition rate, zone tendencies)
│  (Sonnet)       │  Compares to prior games vs same opponent
│                 │  Returns: structured analysis JSON
└────────┬────────┘
         │
         ▼ Step 3: Report
┌─────────────────┐
│  REPORT WRITER  │  Takes analysis JSON + coach notes
│  AGENT          │  Generates postgame report
│  (Sonnet)       │  Saves as PDF/Markdown
│                 │  Returns: report_path
└────────┬────────┘
         │
         ▼
COACH receives postgame report (< 5 minutes total)
```

**Token cost estimate**: ~$0.15-0.30 per game

### Workflow 2: Scout an Opponent (Phase 2)

```
COACH: "Pull up scouting report for Lincoln — we play them Friday"
         │
         ▼
┌─────────────────┐
│  ORCHESTRATOR    │  Classifies as ANALYZE + REPORT
│                 │  Queries DB: finds 3 games vs Lincoln
│  Routes to:      │
│  1. Analyst      │  (with all 3 games' data)
│  2. Report Writer│  (with cross-game analysis)
└────────┬────────┘
         │
         ▼ Step 1: Cross-game analysis
┌─────────────────┐
│  GAME ANALYST   │  Aggregates across all 3 games
│  AGENT          │  Computes opponent tendencies
│                 │  Identifies consistency vs variability
│                 │  Weights recent games more heavily
│                 │  Returns: opponent_profile JSON
└────────┬────────┘
         │
         ▼ Step 2: Scouting report
┌─────────────────┐
│  REPORT WRITER  │  Takes opponent profile JSON
│  AGENT          │  Generates scouting report with:
│                 │    - Opponent identity/tendencies
│                 │    - What worked against them before
│                 │    - Recommended game plan
│                 │    - Key matchup considerations
│                 │  Returns: scouting_report_path
└────────┬────────┘
         │
         ▼
COACH receives scouting report before the game
```

**Token cost estimate**: ~$0.20-0.40 per scouting report

### Workflow 3: Process Game Video (Phase 3+)

```
COACH: "Here's the full game video from tonight"
         │
         ▼
┌─────────────────┐
│  ORCHESTRATOR    │  Classifies as VIDEO + ANALYZE + REPORT
│  Routes to:      │
│  1. Vision Agent │  (process video first)
│  2. Ingestion    │  (merge CV data with manual stats)
│  3. Analyst      │  (enhanced analysis with spatial data)
│  4. Report Writer│  (report with heatmaps)
└────────┬────────┘
         │
         ▼ Step 1: CV Processing (30-45 min for full game)
┌─────────────────┐
│  VISION AGENT   │  Runs full pipeline:
│  (Haiku)        │    Detection → Tracking → Team classification
│                 │    Court mapping → Event extraction
│                 │    Heatmap generation → Possession segmentation
│                 │  Returns: tracking_data, events, clips, heatmaps
└────────┬────────┘
         │
         ▼ Step 2: Merge data
┌─────────────────┐
│  INGESTION      │  Merges CV-extracted data with
│  AGENT          │  GameChanger stats and coach notes
│                 │  Flags conflicts between sources
└────────┬────────┘
         │
         ▼ Step 3: Enhanced analysis
┌─────────────────┐
│  GAME ANALYST   │  Now has spatial data:
│                 │    Zone occupancy, transition rates from CV
│                 │    Team spacing metrics
│                 │    Possession-level breakdowns
│                 │  Returns: enhanced analysis JSON (includes heatmaps)
└────────┬────────┘
         │
         ▼ Step 4: Enhanced report
┌─────────────────┐
│  REPORT WRITER  │  Report now includes:
│                 │    Heat map visualizations
│                 │    Zone-by-zone breakdown
│                 │    Transition vs half-court with spatial evidence
│                 │    Linked clips for key possessions
└────────┬────────┘
         │
         ▼
COACH receives enhanced report with visual data
```

### Workflow 4: Live Game Mode (Phase 4+)

```
GAME STARTS — Camera connected, Mac mini running
         │
         ▼
┌─────────────────────────────────────────────────┐
│  VISION AGENT (running continuously)             │
│                                                  │
│  Every frame (10-15 fps):                        │
│    Detection → Tracking → Team classification    │
│    → Court mapping → Zone accumulation           │
│                                                  │
│  Every 10-15 seconds:                            │
│    Update heatmaps                               │
│    Update zone occupancy                         │
│    Update transition rate                        │
│    Check alert triggers                          │
│                                                  │
│  Push to local dashboard (WebSocket)             │
└────────┬────────────────────────────────────────┘
         │
         │ At halftime / end of quarter:
         ▼
┌─────────────────┐
│  GAME ANALYST   │  Quick partial analysis
│  (Sonnet)       │  Q1-Q2 patterns
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  REPORT WRITER  │  Generates halftime quick take
│  (Haiku)        │  "Lincoln running 55% transition.
│                 │   They're attacking right wing.
│                 │   Recommend switching to press."
└────────┬────────┘
         │
         ▼
COACH sees quick take on iPad dashboard

         │ After game ends:
         ▼
Normal Workflow 1 runs with enhanced CV data
```

### Workflow 5: Season Trend Check

```
COACH: "How are we trending this season?"
         │
         ▼
┌─────────────────┐
│  ORCHESTRATOR    │  Queries all games this season
│  Routes to:      │
│  1. Analyst (parallel calls):
│     a. Team offense trends
│     b. Team defense trends
│     c. Opponent difficulty curve
│  2. Report Writer
└────────┬────────┘
         │
         ▼ Step 1: Parallel analysis (3 subagents)
┌──────────────────────────────────────────────┐
│          ┌──────────┐                        │
│          │ Offense  │  FG%, pace, transition │
│     ┌───▶│ Trends   │  rate over time        │
│     │    └──────────┘                        │
│     │    ┌──────────┐                        │
│  ───┼───▶│ Defense  │  Opp FG%, turnovers    │
│     │    │ Trends   │  forced, zone coverage  │
│     │    └──────────┘                        │
│     │    ┌──────────┐                        │
│     └───▶│ Schedule │  Opponent strength,     │
│          │ Context  │  result vs difficulty    │
│          └──────────┘                        │
└──────────────────┬───────────────────────────┘
                   │
                   ▼ Step 2: Synthesized report
┌─────────────────┐
│  REPORT WRITER  │  Season trend report:
│                 │    - What's improving
│                 │    - What's declining
│                 │    - Upcoming opponent concerns
│                 │    - Practice focus recommendations
└────────┬────────┘
         │
         ▼
COACH receives season trend report
```

---

## Implementation: Phase-by-Phase Agent Buildout

### Phase 1 (Weeks 1-4): Minimal Viable Agents

**Build these first:**

```
Week 1: Ingestion Agent + database schema
Week 2: Game Analyst Agent (single-game analysis only)
Week 3: Report Writer Agent (postgame reports only)
Week 4: Orchestrator (simple routing: ingest → analyze → report)
```

**What you skip:** Vision Agent, live mode, scouting, trends

**Architecture:** Simple Python script with sequential calls. No need for full Agent SDK yet.

```python
# Phase 1: Simple sequential pipeline (no SDK needed)
import anthropic

client = anthropic.Anthropic()

def process_game(raw_stats: str, coach_notes: str):
    # Step 1: Ingest (structure the data)
    structured = client.messages.create(
        model="claude-haiku-4-5-20251001",
        system=INGESTION_PROMPT,
        messages=[{"role": "user", "content": f"Stats:\n{raw_stats}\n\nNotes:\n{coach_notes}"}]
    )
    
    # Step 2: Analyze
    analysis = client.messages.create(
        model="claude-sonnet-4-6",
        system=ANALYST_PROMPT,
        messages=[{"role": "user", "content": f"Analyze this game:\n{structured.content}"}]
    )
    
    # Step 3: Report
    report = client.messages.create(
        model="claude-sonnet-4-6",
        system=REPORT_WRITER_PROMPT,
        messages=[{"role": "user", "content": f"Generate postgame report:\n{analysis.content}"}]
    )
    
    return report.content
```

**Cost per game:** ~$0.10-0.25
**Total Phase 1 infra:** Python + SQLite + Claude API. That's it.

### Phase 2 (Weeks 5-8): Add Scouting + Trends

- Extend Analyst to handle multi-game cross-analysis
- Add scouting report template to Report Writer
- Build season trend analysis
- Introduce Claude Agent SDK for orchestration

### Phase 3 (Weeks 9-14): Add Vision Agent

- Build CV pipeline as Python scripts (YOLO + ByteTrack)
- Wrap as MCP tools
- Build Vision Agent that orchestrates CV tools
- Integrate CV data into existing analysis pipeline

### Phase 4 (Weeks 15-22): Live Mode

- Optimize CV pipeline for real-time
- Build local dashboard
- Add halftime quick-take workflow
- Deploy on Mac mini

---

## Cost Model

| Workflow | Models Used | Estimated Cost |
|---|---|---|
| Process 1 game (Phase 1) | Haiku + Sonnet + Sonnet | $0.10-0.25 |
| Scouting report (3 games) | Sonnet + Sonnet | $0.20-0.40 |
| Season trend (10 games) | Sonnet (parallel) + Sonnet | $0.30-0.60 |
| Live halftime take | Haiku + Sonnet | $0.05-0.10 |
| Full game with CV | Haiku (vision) + Haiku + Sonnet + Sonnet | $0.15-0.35 |
| **Season total (~30 games)** | All workflows | **$15-30** |

Use **Haiku** for parsing, structuring, and CV orchestration (cheap, fast).
Use **Sonnet** for analysis and report writing (strong reasoning + writing).
Use **Opus** only if report quality from Sonnet is insufficient (unlikely).

---

## Tech Stack Summary

| Component | Technology | Why |
|---|---|---|
| **Language** | Python 3.12+ | Best CV/ML ecosystem, Claude SDK support |
| **LLM** | Claude API (Haiku + Sonnet) | Best writing quality for reports, strong tool use |
| **Agent Framework** | Claude Agent SDK (Phase 2+) | Native tool use, sessions, subagents |
| **Database** | SQLite (local) → Postgres (cloud, Phase 2+) | Simple to start, scales when needed |
| **CV Models** | YOLOv8/v9 via Ultralytics (Phase 3+) | Best speed/accuracy for Apple Silicon |
| **Tracking** | ByteTrack (Phase 3+) | Fast, no re-ID model needed |
| **Web Dashboard** | FastAPI + HTMX or simple React (Phase 4+) | Lightweight, serves from Mac mini |
| **Report Rendering** | Markdown → PDF via WeasyPrint or Pandoc | Clean output for coaches |
| **Cloud Hosting** | Supabase (DB + auth) or Railway | Simple deployment for backend |
| **Edge Device** | Mac mini M2 Pro+ (Phase 4+) | Best price/performance for Apple Silicon ML |
