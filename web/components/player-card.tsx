"use client";

import { TrendingUp, TrendingDown, Minus, Clock, Calendar } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  XAxis,
  YAxis,
} from "recharts";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Badge } from "@/components/ui/badge";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import type { GameLogEntry, PlayerCardData } from "@/lib/types";

// Per-stat realistic maxes for 7th-grade rec/AAU. Values get scaled to 0-100
// against these so the radar polygon actually fills the chart instead of
// collapsing near the center. Tune as the season progresses.
const STAT_MAX = {
  ppg: 20,
  rpg: 10,
  apg: 6,
  spg: 4,
  fg_pct: 60,
  three_pct: 45,
} as const;

function scale(value: number, max: number): number {
  return Math.min(100, Math.max(0, (value / max) * 100));
}

// ── Role mapping (same thresholds as legacy index.html:3365) ─────────────
const ROLE_COLORS: Record<string, string> = {
  Scorer: "#34d399",
  Playmaker: "#ef4444",
  Disruptor: "#fb923c",
  Rebounder: "#a78bfa",
  Contributor: "#898993",
  "Role Player": "#898993",
};

function rolesFor(p: PlayerCardData): string[] {
  const r: string[] = [];
  if (p.ppg >= 8) r.push("Scorer");
  if (p.apg >= 3) r.push("Playmaker");
  if (p.spg >= 2) r.push("Disruptor");
  if (p.rpg >= 5) r.push("Rebounder");
  if (r.length === 0) r.push(p.ppg >= 3 ? "Contributor" : "Role Player");
  return r.slice(0, 2);
}

function headlinerFor(p: PlayerCardData, primaryRole: string) {
  if (primaryRole === "Rebounder" && p.rpg > p.ppg * 0.8) {
    return { value: p.rpg, label: "RPG", trend: p.rpg_trend };
  }
  return { value: p.ppg, label: "PPG", trend: p.ppg_trend };
}

// ── L5 narrative — describe what's changed in the last 5 games ────────────
type Axis = { name: string; season: number; l5: number; delta: number; unit: string };

function narrativeFor(
  axes: Axis[],
  gamesPlayed: number,
): { up: Axis[]; down: Axis[]; summary: string } {
  const allEqual = axes.every((a) => a.season === a.l5);

  // If every axis is identical and the player has <= 5 games, L5 == season by
  // definition — there's no separate "last 5" sample yet.
  if (allEqual && gamesPlayed <= 5) {
    return {
      up: [],
      down: [],
      summary: `Only ${gamesPlayed} game${gamesPlayed === 1 ? "" : "s"} played — last-5 trend will appear after game 6.`,
    };
  }

  // What counts as "meaningful": >= 0.4 raw delta for counting stats, >= 3 pp for shooting
  const meaningful = axes.filter((a) => {
    const threshold = a.unit === "%" ? 3 : 0.4;
    return Math.abs(a.delta) >= threshold;
  });
  const up = meaningful.filter((a) => a.delta > 0).sort((a, b) => b.delta - a.delta);
  const down = meaningful.filter((a) => a.delta < 0).sort((a, b) => a.delta - b.delta);

  let summary: string;
  if (up.length === 0 && down.length === 0) {
    summary = "Steady across the last 5 — no significant swing in any stat.";
  } else if (up.length > 0 && down.length === 0) {
    summary = `Trending up — ${up[0].name} now ${up[0].l5}${up[0].unit} (+${up[0].delta.toFixed(1)}${up[0].unit}).`;
  } else if (down.length > 0 && up.length === 0) {
    summary = `Trending down — ${down[0].name} now ${down[0].l5}${down[0].unit} (${down[0].delta.toFixed(1)}${down[0].unit}).`;
  } else {
    summary = `Mixed — ${up[0].name} up ${up[0].delta.toFixed(1)}${up[0].unit}, ${down[0].name} down ${Math.abs(down[0].delta).toFixed(1)}${down[0].unit}.`;
  }
  return { up, down, summary };
}

// ── Trend pill — hidden when delta is below threshold ───────────────────
function TrendPill({
  value,
  suffix = "",
  threshold = 0.5,
}: {
  value: number;
  suffix?: string;
  threshold?: number;
}) {
  if (Math.abs(value) < threshold) return null;
  const className =
    "inline-flex items-center gap-1 text-xs font-semibold tabular-nums";
  if (value > 0) {
    return (
      <span className={`${className} text-emerald-500`}>
        <TrendingUp className="h-3 w-3" />+{value}
        {suffix} vs L5
      </span>
    );
  }
  return (
    <span className={`${className} text-rose-500`}>
      <TrendingDown className="h-3 w-3" />
      {value}
      {suffix} vs L5
    </span>
  );
}

// ── Dual-bar sparkline (for Detailed view) ────────────────────────────────
function RingTrend({ value }: { value: number }) {
  if (value > 0) {
    return (
      <div className="mt-1 inline-flex items-center gap-0.5 text-[9px] font-bold text-emerald-500 tabular-nums">
        <TrendingUp className="h-2 w-2" />+{Math.abs(value)}
      </div>
    );
  }
  if (value < 0) {
    return (
      <div className="mt-1 inline-flex items-center gap-0.5 text-[9px] font-bold text-rose-500 tabular-nums">
        <TrendingDown className="h-2 w-2" />−{Math.abs(value)}
      </div>
    );
  }
  return (
    <div className="mt-1 inline-flex items-center gap-0.5 text-[9px] font-bold text-muted-foreground tabular-nums">
      <Minus className="h-2 w-2" />0
    </div>
  );
}

// ── Game-log tile (last 5 games) ──────────────────────────────────────────
function GameTile({ g, ppg }: { g: GameLogEntry; ppg: number }) {
  const abbr = (g.opponent || "???").slice(0, 3).toUpperCase();
  const aboveAvg = g.above_avg;
  const wellBelow = g.points < ppg * 0.7;
  const dotColor = aboveAvg
    ? "bg-emerald-500"
    : wellBelow
      ? "bg-rose-500"
      : "bg-muted-foreground";

  // Plain-language interpretation for the hover
  const meaning = aboveAvg
    ? `Above season avg (${ppg} PPG) — strong outing.`
    : wellBelow
      ? `Below 70% of season avg — quiet game.`
      : "Around season average.";

  return (
    <HoverCard>
      <HoverCardTrigger
        render={
          <button
            type="button"
            className="flex flex-col items-center rounded-lg border bg-muted/40 py-2 hover:bg-muted hover:border-foreground/20 transition-colors cursor-default"
          />
        }
      >
        <div className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
          {abbr}
        </div>
        <div className="tabular-nums text-[18px] font-black leading-none mt-1">
          {g.points}
        </div>
        <div className={`mt-1.5 h-1.5 w-1.5 rounded-full ${dotColor}`} />
      </HoverCardTrigger>
      <HoverCardContent side="top" className="w-64 p-3 text-xs">
        <div className="flex items-baseline justify-between">
          <span className="font-semibold text-sm">vs {g.opponent}</span>
          <span className="tabular-nums font-bold">{g.score}</span>
        </div>
        {g.date && (
          <div className="text-muted-foreground mt-0.5 inline-flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {g.date}
          </div>
        )}
        <div className="my-2 h-px bg-border" />
        <div className="grid grid-cols-4 gap-2 tabular-nums">
          <Stat label="PTS" value={g.points} />
          <Stat label="REB" value={g.rebounds} />
          <Stat label="AST" value={g.assists} />
          <Stat label="STL" value={g.steals} />
        </div>
        <p className="text-muted-foreground mt-2 leading-relaxed">{meaning}</p>
      </HoverCardContent>
    </HoverCard>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center">
      <div className="text-base font-black tabular-nums">{value}</div>
      <div className="text-muted-foreground text-[9px] font-bold uppercase tracking-wider">
        {label}
      </div>
    </div>
  );
}

// ── Radar (default view) — dual series w/ custom dual-value axis labels ───
// Hardcoded hex so they render even if base-nova chart tokens stay grayscale.
const SEASON_COLOR = "#64748b"; // slate-500
const L5_COLOR = "#f97316"; // orange-500

const radarConfig = {
  season: { label: "Season", color: SEASON_COLOR },
  l5: { label: "Last 5", color: L5_COLOR },
} satisfies ChartConfig;

function RadarView({ p }: { p: PlayerCardData }) {
  const axes: Axis[] = [
    { name: "PPG", season: p.ppg, l5: p.l5_ppg, delta: +(p.l5_ppg - p.ppg).toFixed(1), unit: "" },
    { name: "RPG", season: p.rpg, l5: p.l5_rpg, delta: +(p.l5_rpg - p.rpg).toFixed(1), unit: "" },
    { name: "APG", season: p.apg, l5: p.l5_apg, delta: +(p.l5_apg - p.apg).toFixed(1), unit: "" },
    { name: "SPG", season: p.spg, l5: p.l5_spg, delta: +(p.l5_spg - p.spg).toFixed(1), unit: "" },
    {
      name: "FG%",
      season: Math.round(p.fg_pct * 100),
      l5: Math.round(p.l5_fg_pct * 100),
      delta: Math.round((p.l5_fg_pct - p.fg_pct) * 100),
      unit: "%",
    },
    {
      name: "3PT%",
      season: Math.round(p.three_pct * 100),
      l5: Math.round(p.l5_three_pct * 100),
      delta: Math.round((p.l5_three_pct - p.three_pct) * 100),
      unit: "%",
    },
  ];

  const maxFor = (n: string): number => {
    if (n === "FG%") return STAT_MAX.fg_pct;
    if (n === "3PT%") return STAT_MAX.three_pct;
    return STAT_MAX[n.toLowerCase() as "ppg" | "rpg" | "apg" | "spg"];
  };

  const chartData = axes.map((a) => ({
    axis: a.name,
    season: scale(a.season, maxFor(a.name)),
    l5: scale(a.l5, maxFor(a.name)),
    seasonRaw: a.season,
    l5Raw: a.l5,
    delta: a.delta,
    unit: a.unit,
  }));

  const { summary } = narrativeFor(axes, p.games_played);

  return (
    <div className="space-y-3">
      <ChartContainer
        config={radarConfig}
        className="mx-auto aspect-square max-h-[340px] w-full"
      >
        <RadarChart
          data={chartData}
          margin={{ top: 24, right: 24, bottom: 24, left: 24 }}
          outerRadius="78%"
        >
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                indicator="line"
                formatter={(_v, name, item) => {
                  const d = item.payload as (typeof chartData)[number];
                  if (name === "season") {
                    return `Season ${d.seasonRaw}${d.unit}`;
                  }
                  return `Last 5: ${d.l5Raw}${d.unit} (${d.delta >= 0 ? "+" : ""}${d.delta}${d.unit})`;
                }}
              />
            }
          />
          <PolarAngleAxis
            dataKey="axis"
            tick={(props) => {
              const { x, y, textAnchor, index } = props as {
                x: number;
                y: number;
                textAnchor: "inherit" | "start" | "end" | "middle";
                index: number;
              };
              const d = chartData[index];
              const deltaColor =
                d.delta > 0
                  ? "fill-emerald-500"
                  : d.delta < 0
                    ? "fill-rose-500"
                    : "fill-muted-foreground";
              return (
                <text
                  x={x}
                  y={y + (index === 0 ? -8 : 0)}
                  textAnchor={textAnchor}
                  fontSize={11}
                  fontWeight={600}
                  className="fill-foreground"
                >
                  {d.seasonRaw === d.l5Raw ? (
                    <tspan>{d.seasonRaw}{d.unit}</tspan>
                  ) : (
                    <>
                      <tspan>{d.seasonRaw}{d.unit}</tspan>
                      <tspan className="fill-muted-foreground">{" → "}</tspan>
                      <tspan className={deltaColor}>{d.l5Raw}{d.unit}</tspan>
                    </>
                  )}
                  <tspan
                    x={x}
                    dy="0.95rem"
                    fontSize={10}
                    fontWeight={700}
                    className="fill-muted-foreground uppercase tracking-wider"
                  >
                    {d.axis}
                  </tspan>
                </text>
              );
            }}
          />
          <PolarGrid stroke="currentColor" strokeOpacity={0.15} />
          <Radar
            dataKey="season"
            fill={SEASON_COLOR}
            fillOpacity={0.18}
            stroke={SEASON_COLOR}
            strokeWidth={1.5}
            strokeDasharray="4 4"
          />
          <Radar
            dataKey="l5"
            fill={L5_COLOR}
            fillOpacity={0.5}
            stroke={L5_COLOR}
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: L5_COLOR, fillOpacity: 1, strokeWidth: 0 }}
          />
        </RadarChart>
      </ChartContainer>

      <div className="flex items-center justify-center gap-4 text-[10px] uppercase tracking-wider">
        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
          <span
            className="inline-block h-0.5 w-4"
            style={{
              background: `repeating-linear-gradient(to right, ${SEASON_COLOR} 0 3px, transparent 3px 6px)`,
            }}
          />
          Season
        </span>
        <span className="inline-flex items-center gap-1.5 text-foreground font-semibold">
          <span
            className="inline-block h-0.5 w-4"
            style={{ background: L5_COLOR }}
          />
          Last 5
        </span>
      </div>

      <div className="rounded-lg border bg-muted/40 px-4 py-3 text-center">
        <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
          Last 5 trend
        </div>
        <p className="text-sm font-semibold leading-snug text-foreground">
          {summary}
        </p>
      </div>
    </div>
  );
}

// ── Detailed view ─────────────────────────────────────────────────────────
// ── Universal shooting-percentage color tiers ────────────────────────────
// <50% = red (rough), 50-79% = orange (developing), 80%+ = green (elite).
function pctColor(pct: number): string {
  if (pct >= 80) return "#22c55e"; // emerald-500
  if (pct >= 50) return "#f97316"; // orange-500
  return "#ef4444"; // red-500
}

function pctTier(pct: number): "elite" | "developing" | "rough" {
  if (pct >= 80) return "elite";
  if (pct >= 50) return "developing";
  return "rough";
}

// ── Detailed view chart configs ──────────────────────────────────────────
const COUNTING_BAR_CONFIG = {
  season: { label: "Season", color: "#94a3b8" },
  l5: { label: "Last 5", color: "#f97316" },
} satisfies ChartConfig;

const SHOOTING_CONFIG = {
  pct: { label: "%" },
  fg: { label: "FG" },
  three: { label: "3PT" },
  ft: { label: "FT" },
} satisfies ChartConfig;

function DetailedView({ p }: { p: PlayerCardData }) {
  const fgPctDisplay = Math.round(p.fg_pct * 100);
  const threePctDisplay = Math.round(p.three_pct * 100);
  const ftPctDisplay = Math.round(p.ft_pct * 100);
  const games = p.game_log ?? [];

  // Bar chart data — horizontal grouped bars per stat, season vs L5
  const countingData = [
    { stat: "PPG", season: p.ppg, l5: p.l5_ppg, max: 25 },
    { stat: "RPG", season: p.rpg, l5: p.l5_rpg, max: 12 },
    { stat: "APG", season: p.apg, l5: p.l5_apg, max: 8 },
    { stat: "SPG", season: p.spg, l5: p.l5_spg, max: 5 },
  ];

  // Radial shooting data — three concentric arcs.
  // Universal color scheme: <50 red, 50-79 orange, 80+ green.
  const shootingData = [
    {
      label: "FT",
      pct: ftPctDisplay,
      made: p.ft_made,
      attempted: p.ft_attempted,
      trend: p.ft_trend,
      fill: pctColor(ftPctDisplay),
      tier: pctTier(ftPctDisplay),
    },
    {
      label: "3PT",
      pct: threePctDisplay,
      made: p.three_made,
      attempted: p.three_attempted,
      trend: p.three_trend,
      fill: pctColor(threePctDisplay),
      tier: pctTier(threePctDisplay),
    },
    {
      label: "FG",
      pct: fgPctDisplay,
      made: p.fg_made,
      attempted: p.fg_attempted,
      trend: p.fg_trend,
      fill: pctColor(fgPctDisplay),
      tier: pctTier(fgPctDisplay),
    },
  ];

  return (
    <div className="space-y-5">
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
            Counting stats
          </h3>
          <span className="flex items-center gap-3 text-[10px] uppercase tracking-wider text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-3 w-0.5 bg-[#94a3b8]" />
              Season
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="inline-block h-1.5 w-3 rounded-sm bg-[#f97316]" />
              Last 5
            </span>
          </span>
        </div>
        <div className="space-y-2">
          {countingData.map((d) => (
            <StatRow key={d.stat} {...d} />
          ))}
        </div>
      </section>

      <section>
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
            Shooting
          </h3>
          <span className="text-[10px] tabular-nums text-muted-foreground">
            last 5 vs season
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {shootingData
            .slice()
            .reverse()
            .map((s) => (
              <ShootingDial
                key={s.label}
                label={s.label}
                pct={s.pct}
                made={s.made}
                attempted={s.attempted}
                trend={s.trend}
                fill={s.fill}
                tier={s.tier}
              />
            ))}
        </div>
      </section>

      {games.length > 0 && (
        <section>
          <div className="mb-2.5 flex items-baseline justify-between">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
              Last {Math.min(5, p.games_played)} games
            </h3>
            <span className="text-muted-foreground text-[10px]">
              Hover for detail
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5">
            {games.slice(0, 5).map((g, i) => (
              <GameTile key={`${g.opponent}-${g.date}-${i}`} g={g} ppg={p.ppg} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ── Single shooting dial — shadcn ChartContainer + RadialBarChart ────────
function ShootingDial({
  label,
  pct,
  made,
  attempted,
  trend,
  fill,
  tier,
}: {
  label: string;
  pct: number;
  made: number;
  attempted: number;
  trend: number;
  fill: string;
  tier: "elite" | "developing" | "rough";
}) {
  const data = [{ name: label, value: pct, fill }];
  const tierLabel = {
    elite: "Elite (≥80%)",
    developing: "Developing (50–79%)",
    rough: "Rough (<50%)",
  }[tier];

  return (
    <HoverCard>
      <HoverCardTrigger
        render={
          <div className="flex cursor-default flex-col items-center rounded-xl border bg-muted/40 px-2 py-3" />
        }
      >
        <div className="relative h-16 w-16">
          <ChartContainer
            config={SHOOTING_CONFIG}
            className="absolute inset-0 aspect-square"
          >
            <RadialBarChart
              data={data}
              startAngle={90}
              endAngle={90 - (pct / 100) * 360}
              innerRadius={22}
              outerRadius={30}
              barSize={6}
            >
              <PolarGrid
                gridType="circle"
                radialLines={false}
                stroke="none"
                polarRadius={[26]}
              />
              <RadialBar
                dataKey="value"
                background={{ fill: "currentColor", fillOpacity: 0.08 }}
                cornerRadius={3}
              />
            </RadialBarChart>
          </ChartContainer>
          <div
            className="absolute inset-0 flex items-center justify-center text-[13px] font-black tabular-nums leading-none"
            style={{ color: fill }}
          >
            {Math.round(pct)}%
          </div>
        </div>
        <div className="text-muted-foreground mt-1.5 tabular-nums text-[10px]">
          {made}/{attempted}
        </div>
        <div className="mt-0.5 text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <RingTrend value={trend} />
      </HoverCardTrigger>
      <HoverCardContent side="top" className="w-72 p-3.5 text-xs">
        <div className="flex items-baseline justify-between">
          <div className="font-bold text-sm">{fullLabel(label)}</div>
          <div className="tabular-nums font-black text-lg" style={{ color: fill }}>
            {Math.round(pct)}%
          </div>
        </div>
        <div className="text-muted-foreground tabular-nums mt-0.5">
          {made} made of {attempted} attempts
        </div>

        <div className="my-2.5 h-px bg-border" />

        <div className="space-y-1">
          <ColorLegend
            current={tier}
            tier="elite"
            color="#22c55e"
            label="Elite"
            range="≥ 80%"
          />
          <ColorLegend
            current={tier}
            tier="developing"
            color="#f97316"
            label="Developing"
            range="50 – 79%"
          />
          <ColorLegend
            current={tier}
            tier="rough"
            color="#ef4444"
            label="Rough"
            range="< 50%"
          />
        </div>

        <div className="my-2.5 h-px bg-border" />

        <div className="flex items-baseline justify-between">
          <span className="text-muted-foreground">Last 5 trend</span>
          <span
            className={`tabular-nums font-semibold ${
              trend > 0
                ? "text-emerald-500"
                : trend < 0
                  ? "text-rose-500"
                  : "text-muted-foreground"
            }`}
          >
            {trend > 0 ? "+" : ""}
            {trend}pp vs season
          </span>
        </div>

        <p className="mt-2 leading-relaxed text-foreground/80">
          {tierLabel}.{" "}
          {trend > 0
            ? "Trending up — last 5 better than season average."
            : trend < 0
              ? "Cooling off — last 5 below season average."
              : "Steady at season average."}
        </p>
      </HoverCardContent>
    </HoverCard>
  );
}

// ── Single stat row — L5 colored bar + season tick marker on a track ─────
function StatRow({
  stat,
  season,
  l5,
  max,
}: {
  stat: string;
  season: number;
  l5: number;
  max: number;
}) {
  const seasonPct = Math.min(100, Math.max(0, (season / max) * 100));
  const l5Pct = Math.min(100, Math.max(0, (l5 / max) * 100));
  const delta = +(l5 - season).toFixed(1);
  const color = delta > 0.4 ? "#22c55e" : delta < -0.4 ? "#ef4444" : "#f97316";

  return (
    <HoverCard>
      <HoverCardTrigger
        render={
          <div className="grid cursor-default grid-cols-[40px_1fr_56px] items-center gap-3" />
        }
      >
        <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          {stat}
        </div>
        <div className="relative h-2 rounded-full bg-muted overflow-visible">
          <div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{ width: `${l5Pct}%`, background: color }}
          />
          <span
            className="absolute top-1/2 -translate-y-1/2 inline-block h-3 w-0.5 bg-foreground/70 rounded-full"
            style={{ left: `calc(${seasonPct}% - 1px)` }}
          />
        </div>
        <div className="flex items-baseline justify-end gap-1.5 text-right tabular-nums text-[12px] leading-tight">
          <span className="text-muted-foreground">{season.toFixed(1)}</span>
          <span style={{ color }} className="font-bold">
            {l5.toFixed(1)}
          </span>
        </div>
      </HoverCardTrigger>
      <HoverCardContent side="top" className="w-64 p-3 text-xs">
        <div className="font-bold text-sm">{stat}</div>
        <div className="my-2 grid grid-cols-2 gap-2">
          <div>
            <div className="text-muted-foreground text-[10px] uppercase tracking-wider">
              Season
            </div>
            <div className="text-base font-bold tabular-nums">
              {season.toFixed(1)}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-[10px] uppercase tracking-wider">
              Last 5
            </div>
            <div
              className="text-base font-bold tabular-nums"
              style={{ color }}
            >
              {l5.toFixed(1)}
            </div>
          </div>
        </div>
        <div className="my-2 h-px bg-border" />
        <div className="flex items-baseline justify-between">
          <span className="text-muted-foreground">Delta vs season</span>
          <span style={{ color }} className="tabular-nums font-semibold">
            {delta > 0 ? "+" : ""}
            {delta.toFixed(1)}
          </span>
        </div>
        <p className="mt-2 text-foreground/80 leading-relaxed">
          {Math.abs(delta) < 0.4
            ? `Holding steady at ${season.toFixed(1)} ${stat} per game.`
            : delta > 0
              ? `Up ${delta.toFixed(1)} per game over the last 5 — trending up.`
              : `Down ${Math.abs(delta).toFixed(1)} per game over the last 5 — cooling off.`}
        </p>
      </HoverCardContent>
    </HoverCard>
  );
}

function fullLabel(short: string): string {
  if (short === "FG") return "Field Goal %";
  if (short === "3PT") return "3-Point %";
  if (short === "FT") return "Free Throw %";
  return short;
}

function ColorLegend({
  current,
  tier,
  color,
  label,
  range,
}: {
  current: "elite" | "developing" | "rough";
  tier: "elite" | "developing" | "rough";
  color: string;
  label: string;
  range: string;
}) {
  const active = current === tier;
  return (
    <div
      className={`flex items-center justify-between rounded px-2 py-1 ${
        active ? "bg-muted ring-1 ring-foreground/10" : "opacity-50"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: color }}
        />
        <span className={active ? "font-semibold" : ""}>{label}</span>
      </div>
      <span className="text-muted-foreground tabular-nums">{range}</span>
    </div>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────
export type PlayerCardView = "detailed" | "radar";

export function PlayerCard({
  p,
  view = "detailed",
}: {
  p: PlayerCardData;
  view?: PlayerCardView;
}) {
  const roles = rolesFor(p);
  const primaryColor = ROLE_COLORS[roles[0]] ?? "#898993";
  const headliner = headlinerFor(p, roles[0]);

  const tc = p.type_counts ?? {};
  const ctxTabs: { label: string; count: number }[] = [
    { label: "All", count: p.games_played },
  ];
  if (tc.league) ctxTabs.push({ label: "League", count: tc.league });
  if (tc.tournament) ctxTabs.push({ label: "Tourn.", count: tc.tournament });
  if (tc.scrimmage) ctxTabs.push({ label: "Scrim.", count: tc.scrimmage });
  if (tc.playoff) ctxTabs.push({ label: "Playoff", count: tc.playoff });

  return (
    <Card className="overflow-hidden p-0 gap-0">
      <div
        className="h-[3px]"
        style={{
          background: `linear-gradient(to right, ${primaryColor}, ${primaryColor}30, transparent)`,
        }}
      />

      <CardHeader className="flex flex-row items-start gap-3 px-5 pt-5 pb-3 sm:gap-4 sm:px-6">
        <div className="flex-shrink-0 pt-0.5">
          <div className="flex items-start gap-0.5">
            <span className="mt-1 text-[18px] font-bold leading-none text-muted-foreground">
              #
            </span>
            <span
              className="text-[42px] font-black leading-none tabular-nums sm:text-[56px]"
              style={{ color: primaryColor }}
            >
              {p.number}
            </span>
          </div>
        </div>
        <div className="min-w-0 flex-1 pt-1">
          <CardTitle className="truncate text-[17px] font-bold leading-snug tracking-tight">
            {p.name}
          </CardTitle>
          <CardDescription className="mt-0.5 text-[11px] uppercase tracking-wider">
            {p.games_played} games
          </CardDescription>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {roles.map((r) => (
              <Badge
                key={r}
                variant="secondary"
                className="text-[10px] font-bold uppercase tracking-wider"
                style={{
                  background: `${ROLE_COLORS[r]}26`,
                  color: ROLE_COLORS[r],
                  borderColor: `${ROLE_COLORS[r]}40`,
                }}
              >
                {r}
              </Badge>
            ))}
          </div>
        </div>
        <div className="flex-shrink-0 text-right">
          <div className="text-[28px] font-black leading-none tracking-tight tabular-nums sm:text-[38px]">
            {headliner.value}
          </div>
          <div className="mt-1 text-[9px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
            {headliner.label} · season
          </div>
          <div className="mt-1.5 flex justify-end">
            <TrendPill value={headliner.trend} />
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-5 pb-4 pt-2">
        {view === "radar" ? <RadarView p={p} /> : <DetailedView p={p} />}
      </CardContent>

      {ctxTabs.length > 1 && (
        <div className="border-t bg-muted/40 px-5 py-2.5">
          <div className="flex gap-1 overflow-x-auto">
            {ctxTabs.map((t) => (
              <button
                key={t.label}
                type="button"
                className="rounded-md px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {t.label} · {t.count}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 border-t bg-muted/60 px-5 py-2">
        <Clock className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
        <p className="text-[10px] leading-tight text-muted-foreground">
          Source:{" "}
          <span className="font-medium text-foreground/80">
            {p.games_played} game reports
          </span>
        </p>
      </div>
    </Card>
  );
}
