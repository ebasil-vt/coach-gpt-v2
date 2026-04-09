# CoachGPT — Coach's Guide

## What Is CoachGPT?

CoachGPT is your AI assistant coach. It takes your game data, stats, and notes and turns them into scouting reports, pre-game briefs, and opponent analysis. It learns from every game you feed it.

**Access**: Open `http://localhost:8080` in your browser (same WiFi as the Mac running CoachGPT).

---

## Starting the Server

Open Terminal and run:

```
cd ~/projects/coach-gpt && source .venv/bin/activate && export ANTHROPIC_API_KEY="your-key" && python -m coachgpt.web.server
```

Then open `http://localhost:8080` on your Mac, iPad, or phone.

---

## The 6 Tabs

| Tab | What It Does |
|---|---|
| **New Game** | Process a game — upload box score + your notes → get a postgame report |
| **Team** | Import season stats from GameChanger CSV → see your roster and player cards |
| **League** | Import league standings/schedule → see all teams ranked with matchup projections |
| **Games** | View all processed games |
| **Reports** | Browse all generated reports (postgame, scouting, research, pre-game, league) |
| **Scout** | Research opponents, generate scouting reports and pre-game briefs |

---

## How to Process a Game (After Every Game)

### What You Need
- Box score from GameChanger (PDF export or screenshot)
- OR just the score + your notes (the system works with minimal data)

### Steps
1. Go to **New Game** tab
2. Make sure YOUR TEAM name is filled in at the top (saves automatically after first time)
3. **Upload** the GameChanger box score PDF or screenshot
   - On your phone: GameChanger app → Game → Box Score → Share → Export PDF
   - AirDrop to Mac, or email to yourself, then upload
4. **Game Info**: Type opponent name, date, score if not in the file
   - Example: `vs Emmorton Eagles, Won 49-40, Jan 30 2026`
5. **Coach Notes**: Type your observations. Be specific:
   - What did the opponent run? (zone, press, motion)
   - What player tendencies did you notice? (use jersey numbers)
   - What adjustments did you make?
   - What worked? What didn't?
6. Hit **Process Game**
7. Watch the agents work (30-60 seconds)
8. Read the postgame report

### Example Coach Notes (the more detail, the better reports)
```
They ran 2-3 zone. We broke it with baseline drives.
#1 is their best shooter — scored most of their points.
#10 can't handle ball pressure — turned it over 5 times.
#7 is their big man, controls the boards.
We pressed in Q3 and it changed the game — 8 turnovers.
Their press break is pass to corner then over the top.
We need to box out better — they got too many offensive boards.
```

### What the System Does
1. **Ingestion Agent** reads your box score (PDF, screenshot, or text)
2. **Analyst Agent** finds patterns (shooting splits, momentum shifts, key performers)
3. **Report Writer Agent** generates a postgame report with specific recommendations

---

## How to Import Your Season Stats

### What You Need
- Season stats CSV from GameChanger

### How to Get the CSV
1. Go to `web.gc.com` on your computer
2. Sign in → Select your team
3. Go to Stats tab
4. Scroll to bottom → **Export Stats** button
5. Download the CSV file

### Steps
1. Go to **Team** tab
2. Type the season name (e.g. `Fall 2025`)
3. Team name auto-fills from YOUR TEAM field
4. Upload the CSV file
5. Hit **Import Season**
6. See your full roster with player cards, stats, and role badges

### What You Get
- Player cards with PPG, shooting splits, stat bars
- Role badges: Scorer, Playmaker, Disruptor, Rebounder
- Color-coded shooting percentages (green = good, red = needs work)
- This data gives future reports context about your players

### Multiple Seasons
- Import a new CSV each season
- Use the dropdown to switch between seasons
- Returning players keep their history — new players get added automatically

---

## How to Import League Standings

### What You Need
- HCRPS standings (pasted text) OR
- HCRPS schedule page (saved as webarchive)

### Option 1: Paste Standings (Fastest)
1. Open HCRPS league page in your browser
2. Find the standings table
3. Select All → Copy
4. Go to **League** tab in CoachGPT
5. Type the season name (e.g. `Winter 2025-2026 — 7th Grade Alliance`)
6. Paste into the text box
7. Hit **Import League Data**

### Option 2: Save Webarchive (Best — Gets Every Game Score)
1. Open the HCRPS league schedule page
2. **Important**: Change the URL to use `schedule_type=index`
   - This shows ALL games on one page, not just one day
   - Example: `https://www.hcrpsports.org/schedule/print/league_instance/228050?schedule_type=index&subseason=957781`
   - Replace the numbers with your league's IDs (from the URL when you browse HCRPS)
3. In Safari: **File → Save As → Web Archive**
4. Go to **League** tab in CoachGPT
5. Type the season name
6. Upload the `.webarchive` file
7. Hit **Import League Data**

### What You Get
- Full standings with every team ranked
- Matchup projections: "Strong favorite", "Favored", "Toss-up"
- **Games button** next to each team — click to see all their game results
- Point differentials and head-to-head comparisons

### During the Season
- Re-import after each game day to update standings
- Each import shows in the dropdown — compare early season vs late season

### Finding the League URL for a New Season
1. Go to `hcrpsports.org`
2. Navigate to your league
3. Look at the URL — find `league_instance=XXXX` and `subseason=XXXX`
4. Use those numbers in the print URL: `https://www.hcrpsports.org/schedule/print/league_instance/XXXX?schedule_type=index&subseason=XXXX`

---

## How to Scout an Opponent

### Three Options on the Scout Tab

#### 1. Scout (from our games) — Orange button
**Use when**: You've played this team before and processed the game(s)

What it does:
- Pulls all your games against them from the database
- Analyzes patterns across multiple matchups
- Generates a detailed scouting report

#### 2. Pre-Game Brief — Green button
**Use when**: 30 minutes before tip-off

What it does:
- Creates a one-page quick reference card
- Top 3 threats with jersey numbers
- Their tendencies (offense, defense, press break)
- Your game plan (offense + defense, 3 bullets each)
- If/Then adjustments
- 3 keys to winning

#### 3. Research (web lookup) — Teal button
**Use when**: You haven't played this team OR you want to see how they did against other teams

What it does:
- Checks our league standings for their record
- Searches for any online info about them
- Cross-references common opponents
- Shows strength comparison based on shared opponents
- If it can't find data, tells you exactly where to look

### Tips
- Add league context in the second field (e.g. `HCRPS 7th Grade Alliance`)
- The more games you process against an opponent, the better the scouting report
- Always add coach notes when processing games — numbers don't capture everything

---

## After Every Game — What to Do

1. **Process the game** on the New Game tab (box score + notes)
2. **Save the GC recap link** for reference
   - Your team's recaps: `web.gc.com/teams/VGbwJULEMkSE/schedule/{GAME_ID}/recap`
3. **Note opponent player tendencies** in your coach notes — use jersey numbers
4. **Ask the opposing coach** for their GameChanger team link
5. **Re-import league standings** if HCRPS has updated scores

The more data you feed CoachGPT, the better every future report gets.

---

## GameChanger Links

| What | URL |
|---|---|
| Your team (current season) | `web.gc.com/teams/VGbwJULEMkSE` |
| Your team (previous season) | `web.gc.com/teams/vf2TC4nINA77` |
| Search for opponents | `gc.com/search` (requires login) |
| Export season stats | `web.gc.com` → Team → Stats → Export Stats |
| Export game box score | GC App → Game → Box Score → Share → Export PDF |

---

## HCRPS Links

| What | URL |
|---|---|
| Your league page (Winter 25-26) | `hcrpsports.org/page/show/9340532-7th-grade-winter-2025-2026-` |
| Full season schedule (all games) | `hcrpsports.org/schedule/print/league_instance/228050?schedule_type=index&subseason=957781` |
| Your team schedule | `hcrpsports.org/schedule/print/team_instance/10442151?schedule_type=index&subseason=957781` |

For new seasons, replace the numbers with the new league IDs from the HCRPS URL.

---

## Report Types

| Report | Badge Color | When Generated |
|---|---|---|
| **POSTGAME** | Blue | After processing a game |
| **SCOUTING** | Orange | When you hit Scout on an opponent |
| **PRE-GAME** | Green | When you hit Pre-Game on an opponent |
| **RESEARCH** | Teal | When you hit Research on an opponent |
| **LEAGUE** | Purple | When you import league standings |

All reports are saved and viewable in the **Reports** tab.

---

## Tips for Better Reports

1. **Always include jersey numbers** in notes — "#10 can't handle pressure" is 10x more useful than "their guard struggles"
2. **Note what you adjusted and when** — "Switched to press in Q3" helps the system understand what worked
3. **Note what the opponent ran** — "2-3 zone", "triangle offense", "1-2-2 press" gives the scouting report specifics
4. **Process games the same day** — your memory is freshest right after the game
5. **Import league standings regularly** — the Research agent uses this to compare opponents
6. **Ask opposing coaches for their GC link** — their team profile gives you stats without having to scout manually

---

## Cost

Each game costs about $0.15-0.20 in API fees. A full 30-game season costs roughly $5-10 total. Scouting reports cost about $0.10-0.15 each. Research lookups cost about $0.05.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Server won't start | Check API key is set: `export ANTHROPIC_API_KEY="your-key"` |
| "Processing" hangs forever | Check the terminal for errors — usually an API issue |
| Wrong team labeled as "ours" | Make sure YOUR TEAM field is filled in on the New Game tab |
| League import shows no Games button | Use the webarchive import (not pasted text) — only webarchive has individual game scores |
| Can't access from iPad | Make sure iPad is on the same WiFi as the Mac running CoachGPT |
| Reports page shows blank | Hard refresh: Cmd+Shift+R |
