# CoachGPT — Coach's Guide

CoachGPT is your AI assistant coach. Feed it game data, stats, and notes — get back scouting reports, pre-game briefs, and opponent analysis. It learns from every game you process.

**Open it at:** [coachgpt.versatech-inc.com](https://coachgpt.versatech-inc.com/) (or your locally hosted address). Sign in with your coach account.

---

## What's in the sidebar

| Tab | What it's for |
|---|---|
| **New Game** | Process a game — upload box score + your notes, get the postgame report |
| **Team** | Player cards (radar + detailed view) and season CSV import |
| **Games** | List of every processed game with click-through to full box score |
| **Reports** | All generated reports (postgame, scouting, pre-game, research, league, identity) — copy and print |
| **Scout** | Search a past opponent and run Scout / Pre-Game / Research flows |
| **League** | Import standings (paste, webarchive, or PDF) and view league-wide tables |
| **Notes** | Quick coach notes on iPhone — same 5 sections as New Game so they drop straight back in |
| **Guide** | This page |

---

## The two-step coaching workflow

### 1. Take notes during or right after the game (Notes tab)

Open CoachGPT on your phone in the parking lot. Tap **Notes → New note**. Fill what you remember in five sections:

- **What did they run?** — defense, offense, presses (e.g., "2-3 zone", "press break: pass to corner")
- **Opponent player tendencies** — one line per player, with jersey numbers (e.g., "#7 best player, boards")
- **What worked?** — runs, plays, individual matchups
- **What didn't work?** — mistakes, breakdowns
- **Additional notes** — anything else

Set the opponent name, save. Done — takes 2 minutes.

### 2. Process the game later (New Game tab)

When you have the box score (PDF, screenshot, CSV, or text):

1. Open **New Game**
2. Confirm "Your Team" (saved from last time)
3. Pick the **Opponent** (your past opponents autocomplete)
4. Type the **score** — the W/L badge updates live
5. Pick game type, location, event name
6. Drop in the **box score** file
7. Optionally drop in **GameChanger app screenshots** (Sting H1, Sting H2, Opp H1, Opp H2)
8. Click the **"Load saved note…"** dropdown → pick the note you saved on your phone. The 5 sections drop into the matching 5 fields automatically.
9. Hit **Process game**. Watch the agent pipeline (Orchestrator → Ingestion → Analysis → Report Writer) work through your inputs.
10. Postgame report renders below — formatted, printable, ready to share.

After the report renders, fill out the **Postgame follow-up** form (GC link, tendencies, adjustments) and hit Save. Those tendencies become opponent player records you can scout next time.

---

## Scouting an upcoming opponent

Open **Scout**, search the team name (works even if you've never played them — the Researcher agent does a web lookup). Tap the team to open their detail panel. Three actions:

| Action | What it does |
|---|---|
| **Scout** | Pulls everything you've ever recorded about this opponent (your notes, their tendencies, past games against them) and writes a scouting report |
| **Pre-Game** | Tactical brief tailored to the upcoming matchup — start lineup, defense to run, key matchups |
| **Research** | Web-lookup-only — finds the team's recent games, common opponents you've also played, statistical signals |

Each runs through its own agent pipeline (Orchestrator → Researcher → Analysis → Report Writer). You'll see live progress and the final report renders inside the panel — copy or print.

You can also **Add player** in the Scout panel to log opponent jersey numbers + tendencies you observed at a tournament — even if you didn't play them yet.

---

## Tips that make reports better

- **Use jersey numbers in notes** — e.g., "#10 can't handle pressure" beats "the tall kid struggles with pressure"
- **Include the GameChanger recap** in the Game Recap field — it gives the AI quotes and storyline beats to weave in
- **Drop the four halftime screenshots** when you have them — Vision parses team-level stats per half
- **Save reusable templates** — common opponents you face every season can become saved Notes you load in seconds

---

## Reports — copy, print, share

In **Reports**, click any row. The side panel shows the formatted report with **Copy** and **Print** buttons:

- **Copy** drops the markdown to your clipboard — paste into a parents email or a coaches Slack
- **Print** renders a clean letter-sized page (no sidebar, no buttons, headers in red/black, tables with borders)

Reports are auto-categorized: postgame, scouting, pre-game, research, team_identity, league_standings. Use the filter dropdown to narrow down.

---

## League standings

In **League → Import** you can:

- **Paste** the standings text from any league site
- **Upload** a Safari `.webarchive` of the schedule page (HCRPS works directly)
- **Upload** a PDF schedule (Vision API parses it)

Once imported, click any league entry to see standings + game-by-game per team.

---

## Account

Avatar in the bottom-left of the sidebar opens a menu:

- **Account settings** — change your display name and password
- **Sign out**

The theme toggle right above the avatar switches dark / light mode.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Too many requests" | Wait 60 seconds — rate limit applies to API calls only |
| Report rendering looks raw | Hard-refresh the page (Ctrl/Cmd + Shift + R) — CSS may be cached |
| Bad password kicks me to a different page | Click back, retype carefully — caps lock matters |
| New Game upload too big | Box score files capped at 20 MB — try a CSV export instead of a PDF |

---

## What's coming

- Saving game-day notes directly from the Notes tab into specific games (not just templates)
- Per-team identity reports that compare current season to past seasons
- Lineup recommendations based on opponent tendencies
- Mobile-optimized box score photo capture (skip the export entirely)

If something feels broken or missing, tell us — this app is being built around how you actually coach.
