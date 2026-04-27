# CoachGPT UI Audit — shadcn/ui Migration

Anchored to the new `web/` Next.js app. Legacy UI lives in
`coachgpt/web/static/index.html` (3,894 lines, vanilla HTML/JS).

## 1. Top 7 Component Swaps (priority order)

| # | Current (legacy file:line) | shadcn replacement | UX rationale | Effort |
|---|---|---|---|---|
| 1 | PlayerCard stat-bar / sparkline grid (`index.html:3361` `renderPlayerCard`) | `Card` + `ChartContainer` + `RadarChart` (Recharts) | One glance shows player shape vs league. Six axes beat 8 stacked sparklines for "is this a scorer or a defender?" | M — **shipped** in `web/components/player-card.tsx` |
| 2 | 7-tab top nav (`index.html` tab buttons around game/team/league/games/reports/scout/guide) | shadcn `Sidebar` (collapsible) + `Tabs` for sub-views | Sticky vertical nav scales past 7 items; current pill row is already cramped on 13" laptops. Sidebar enables nested groupings (Games, Reports, Scouting). | L |
| 3 | Inline `<form>` blocks for New Game + Season Import + League Import | `Form` (RHF + Zod) + `Input` / `Textarea` / `FileTrigger` + `Button` with loading state | Real validation, inline errors, disabled-while-submitting. Replaces ad-hoc `status` divs. | M |
| 4 | Reports list with type filter | `DataTable` (TanStack) + `Select` + `Badge` for report type + `Sheet` for detail | Sortable by date, filterable by type and opponent in one place. Detail in a side sheet keeps list context. | M |
| 5 | SSE progress modals (`#progress-status-dot` pattern) | `Toast` (Sonner) + `Progress` bar + step labels | Non-modal — coaches can keep working while a pre-game brief streams. Free retry/dismiss UX. | S |
| 6 | Opponent player cards in Scout tab (add/edit/delete inline) | `HoverCard` for quick stats + `Dialog` (drawer on mobile) for edit | Reduces tap targets on phones; `HoverCard` shows scouting tendencies on desktop without a click. | M |
| 7 | League standings table (paste-and-parse output) | `Table` + `Badge` (W-L color) + `HoverCard` for game-by-game | Current parsed standings render as plain divs; proper `Table` gives sticky headers, sortable columns, mobile horizontal scroll. | S |

## 2. PlayerCard Radar — shipped

- File: `web/components/player-card.tsx`
- Helper: `web/lib/percentiles.ts` (piecewise normalizer over 7th-grade AAU benchmarks — placeholders, tune with real data)
- Page: `web/app/page.tsx` server-fetches `/api/player-cards` and renders the grid
- Axes: PPG, RPG, APG, SPG, FG%, 3PT% — all normalized to a 0–1 percentile scale so the radar shape is honest across stat types
- Tooltip: `28.4 — 94th pctl` style (raw value + percentile)
- Trend pills: `ppg_trend` and `fg_trend` from existing API fields

Run: `cd coach-gpt-v2/web && pnpm install && pnpm dev` (or `npm`/`yarn`).
Expect FastAPI on `:8080` with `COACHGPT_CORS_ORIGINS=http://localhost:3000`.

## 3. Industry Benchmark Rating (1–10)

| Benchmark | Visual Polish | Information Density | Interaction Quality | Mobile UX | Overall |
|---|---|---|---|---|---|
| NBA.com | 9 | 8 | 8 | 7 | **8** |
| FotMob | 9 | 9 | 9 | 9 | **9** |
| Sorare | 10 | 7 | 9 | 9 | **9** |
| ESPN | 7 | 8 | 6 | 7 | **7** |
| **CoachGPT today** (legacy `index.html`) | **5** | **7** | **5** | **5** | **5** |
| **CoachGPT after this PR** (Team tab only) | **7** | **8** | **7** | **7** | **7** |

### 3-sentence gap analysis

The legacy UI already crams a lot of useful information in (sparklines, rings, role badges) — its problem isn't density, it's that 3,894 lines of vanilla HTML can't keep visual rhythm consistent across 7 tabs, so each section feels hand-built rather than part of one product. The single biggest perceived-quality lift is **swap #2 (Sidebar + Tabs)**: a coherent nav frame instantly makes every page underneath it look 30% more "real," because users stop noticing layout drift between tabs. After that, swap #3 (Form primitives) does the most for daily usability — every session in CoachGPT starts with a form, and the current ad-hoc inputs are where the app most obviously feels under-built.

## 4. Follow-up swaps — file paths

2. Sidebar nav → new `web/components/app-sidebar.tsx` + `web/app/layout.tsx` (replaces tab row at `coachgpt/web/static/index.html` ~L820)
3. Forms → `web/app/games/new/page.tsx` + `web/components/forms/new-game-form.tsx` (replaces New Game tab markup at `index.html` ~L820–950)
4. Reports table → `web/app/reports/page.tsx` + `web/components/reports-table.tsx` (replaces `index.html` reports section)
5. SSE toasts → `web/lib/sse-client.ts` + use `sonner` Toast, called from `new-game-form.tsx` and scout flow (replaces `progress-status-dot` pattern, e.g. `index.html:829`)
6. Opponent player cards → `web/app/scout/[opponent]/page.tsx` + `web/components/opponent-player-card.tsx` (replaces Scout tab markup at `index.html` ~L1224+)
7. League standings table → `web/app/league/page.tsx` + `web/components/standings-table.tsx` (replaces league rendering near `index.html:1015`)
