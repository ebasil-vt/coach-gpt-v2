"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Wand2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FileInputButton } from "@/components/file-input-button";
import { Markdown } from "@/components/markdown";
import {
  AgentPipeline,
  NEW_GAME_PIPELINE,
  type ProgressByAgent,
} from "@/components/agent-pipeline";
import { apiGet } from "@/lib/api";
import { streamPost } from "@/lib/sse";
import { markdownToSections } from "@/lib/coach-note-template";
import type { CoachNote } from "@/lib/types";

type GameResult = {
  game_id?: string;
  opponent?: string;
  date?: string;
  result?: string;
  our_score?: number;
  opp_score?: number;
  report_text?: string;
} & Record<string, unknown>;

const TEAM_STORAGE_KEY = "coachgpt:my_team";
const DEFAULT_TEAM = "Maryland Sting 2031 - Peay";

export default function NewGamePage() {
  // Game details — Your Team persists across sessions (per-browser)
  const [myTeam, setMyTeam] = useState(DEFAULT_TEAM);
  const [opponent, setOpponent] = useState("");
  const [date, setDate] = useState("");
  const [ourScore, setOurScore] = useState("");
  const [oppScore, setOppScore] = useState("");
  const [location, setLocation] = useState("");
  const [gameType, setGameType] = useState<
    "league" | "tournament" | "scrimmage" | "playoff"
  >("league");
  const [eventName, setEventName] = useState("");

  // Game recap
  const [recap, setRecap] = useState("");

  // Box score
  const [boxScore, setBoxScore] = useState<File | null>(null);

  // Insights — 4 screenshots
  const [insightStingH1, setInsightStingH1] = useState<File | null>(null);
  const [insightStingH2, setInsightStingH2] = useState<File | null>(null);
  const [insightOppH1, setInsightOppH1] = useState<File | null>(null);
  const [insightOppH2, setInsightOppH2] = useState<File | null>(null);

  // Coach notes — 5 sections
  const [whatTheyRan, setWhatTheyRan] = useState("");
  const [oppTendencies, setOppTendencies] = useState("");
  const [whatWorked, setWhatWorked] = useState("");
  const [whatDidnt, setWhatDidnt] = useState("");
  const [extraNotes, setExtraNotes] = useState("");

  // Saved-notes loader
  const [savedNotes, setSavedNotes] = useState<CoachNote[]>([]);
  const [opponents, setOpponents] = useState<string[]>([]);

  // Submit / progress
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<ProgressByAgent>({});
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GameResult | null>(null);
  const [elapsed, setElapsed] = useState(0);

  // Load saved notes + opponents for autocomplete + persisted team name
  useEffect(() => {
    apiGet<CoachNote[]>("/api/notes").then((r) => {
      if (r.kind === "ok") setSavedNotes(r.data);
    });
    apiGet<string[]>("/api/opponents").then((r) => {
      if (r.kind === "ok") setOpponents(r.data);
    });
    if (typeof window !== "undefined") {
      const stored = window.localStorage.getItem(TEAM_STORAGE_KEY);
      if (stored) setMyTeam(stored);
    }
  }, []);

  // Persist team name on change
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (myTeam) window.localStorage.setItem(TEAM_STORAGE_KEY, myTeam);
  }, [myTeam]);

  // Live elapsed timer while streaming
  useEffect(() => {
    if (!busy) return;
    const start = Date.now();
    setElapsed(0);
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - start) / 1000)),
      500,
    );
    return () => clearInterval(id);
  }, [busy]);

  const wlBadge = useMemo(() => {
    const o = parseInt(ourScore, 10);
    const t = parseInt(oppScore, 10);
    if (Number.isNaN(o) || Number.isNaN(t)) return null;
    if (o > t)
      return {
        label: "WIN",
        className: "bg-emerald-500/15 text-emerald-600 border-emerald-500/30",
      };
    if (o < t)
      return {
        label: "LOSS",
        className: "bg-rose-500/15 text-rose-600 border-rose-500/30",
      };
    return {
      label: "TIE",
      className: "bg-muted text-foreground border-border",
    };
  }, [ourScore, oppScore]);

  function loadSavedNote(id: string | null) {
    if (!id) return;
    const n = savedNotes.find((x) => x.id === id);
    if (!n) return;
    // Notes are stored with the same 5-section template as this form, so we
    // can drop each section directly into its matching field. Existing
    // values are preserved by appending with a blank line.
    const sec = markdownToSections(n.content);
    const merge = (current: string, incoming: string) => {
      if (!incoming.trim()) return current;
      if (!current.trim()) return incoming.trim();
      return `${current.trim()}\n\n${incoming.trim()}`;
    };
    setWhatTheyRan((v) => merge(v, sec.whatTheyRan));
    setOppTendencies((v) => merge(v, sec.oppTendencies));
    setWhatWorked((v) => merge(v, sec.whatWorked));
    setWhatDidnt((v) => merge(v, sec.whatDidnt));
    setExtraNotes((v) => merge(v, sec.extra));
    if (!opponent && n.opponent) setOpponent(n.opponent);
    if (!date && n.date) setDate(n.date);
  }

  function combinedNotes(): string {
    const parts: string[] = [];
    if (whatTheyRan.trim())
      parts.push(`What did they run:\n${whatTheyRan.trim()}`);
    if (oppTendencies.trim())
      parts.push(`Opponent player tendencies:\n${oppTendencies.trim()}`);
    if (whatWorked.trim()) parts.push(`What worked:\n${whatWorked.trim()}`);
    if (whatDidnt.trim()) parts.push(`What didn't work:\n${whatDidnt.trim()}`);
    if (extraNotes.trim()) parts.push(`Additional notes:\n${extraNotes.trim()}`);
    if (recap.trim()) parts.push(`Game recap:\n${recap.trim()}`);
    return parts.join("\n\n");
  }

  function metadata(): string {
    const parts: string[] = [];
    if (myTeam.trim()) parts.push(`our team: ${myTeam.trim()}`);
    if (opponent.trim()) parts.push(`opponent: ${opponent.trim()}`);
    if (date.trim()) parts.push(`date: ${date.trim()}`);
    if (ourScore && oppScore)
      parts.push(`score: ${ourScore}-${oppScore}${wlBadge ? ` ${wlBadge.label[0]}` : ""}`);
    if (location.trim()) parts.push(`location: ${location.trim()}`);
    if (gameType) parts.push(`game type: ${gameType}`);
    if (eventName.trim()) parts.push(`event: ${eventName.trim()}`);
    return parts.join("; ");
  }

  function setAgent(
    key: string,
    state: "waiting" | "active" | "done" | "error",
    step?: string,
    detail?: string,
  ) {
    setProgress((p) => ({
      ...p,
      [key]: { step, detail, state },
    }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!boxScore && !whatTheyRan.trim() && !oppTendencies.trim() && !recap.trim()) {
      setError("Provide at least a box score, recap, or coach notes.");
      return;
    }
    setBusy(true);
    setError(null);
    setProgress({});
    setResult(null);

    const fd = new FormData();
    fd.append("notes", combinedNotes());
    fd.append("metadata", metadata());
    if (boxScore) fd.append("file", boxScore);
    if (insightStingH1) fd.append("insight_sting_h1", insightStingH1);
    if (insightStingH2) fd.append("insight_sting_h2", insightStingH2);
    if (insightOppH1) fd.append("insight_opp_h1", insightOppH1);
    if (insightOppH2) fd.append("insight_opp_h2", insightOppH2);

    let lastAgent: string | null = null;
    await streamPost("/api/game/stream", fd, (e) => {
      if (e.error) {
        setError(String(e.error));
        toast.error(String(e.error));
        if (lastAgent) setAgent(lastAgent, "error", undefined, String(e.error));
        return;
      }
      if (e.result && typeof e.result === "object") {
        setResult(e.result as GameResult);
        if (lastAgent) setAgent(lastAgent, "done");
        toast.success("Postgame report ready");
        return;
      }
      const agent = (e.agent as string | undefined) ?? null;
      const step = e.step as string | undefined;
      const detail = e.detail as string | undefined;
      if (agent) {
        if (lastAgent && lastAgent !== agent) {
          setAgent(lastAgent, "done");
        }
        setAgent(agent, "active", step, detail);
        lastAgent = agent;
      }
    });
    if (lastAgent) setAgent(lastAgent, "done");
    setBusy(false);
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 md:px-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
          New Game
        </h1>
        <p className="text-muted-foreground text-sm">
          Process a game — stats, notes, screenshots — and get a postgame
          report.
        </p>
      </header>

      <form className="space-y-4" onSubmit={submit}>
        {/* Your team — persistent context */}
        <Card>
          <CardContent className="px-4 py-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
              <Label htmlFor="my_team" className="shrink-0 sm:w-24 text-[11px] font-bold uppercase tracking-wider">
                Your Team
              </Label>
              <Input
                id="my_team"
                value={myTeam}
                onChange={(e) => setMyTeam(e.target.value)}
                placeholder="Maryland Sting 2031 - Peay"
                className="h-9 flex-1"
              />
            </div>
          </CardContent>
        </Card>

        {/* Game details */}
        <Card>
          <CardContent className="space-y-4 px-4 py-4">
            <h2 className="font-bold">Game Details</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="opponent">Opponent</Label>
                <Input
                  id="opponent"
                  value={opponent}
                  onChange={(e) => setOpponent(e.target.value)}
                  placeholder="Emmorton Eagles"
                  list="opponent-list"
                  autoComplete="off"
                />
                <datalist id="opponent-list">
                  {opponents.map((o) => (
                    <option key={o} value={o} />
                  ))}
                </datalist>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="date">Date</Label>
                <Input
                  id="date"
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>
            </div>

            {/* Visual score */}
            <div className="space-y-1.5">
              <Label className="text-[11px] font-bold uppercase tracking-wider">
                Final Score
              </Label>
              <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2">
                <ScoreBox
                  label="US"
                  value={ourScore}
                  onChange={setOurScore}
                  accent="bg-muted/40 border-border text-foreground"
                />
                <div className="flex items-center justify-center text-2xl font-black text-muted-foreground">
                  –
                </div>
                <ScoreBox
                  label="THEM"
                  value={oppScore}
                  onChange={setOppScore}
                  accent="bg-muted/40 border-border text-foreground"
                />
              </div>
              {wlBadge && (
                <div className="flex justify-center pt-1">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-black uppercase tracking-wider ${wlBadge.className}`}
                  >
                    {wlBadge.label}
                  </span>
                </div>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Meadowbrook Athletic Complex"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="game_type">Game Type</Label>
                <Select
                  value={gameType}
                  onValueChange={(v) => setGameType(v as typeof gameType)}
                >
                  <SelectTrigger id="game_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="league">League</SelectItem>
                    <SelectItem value="tournament">Tournament</SelectItem>
                    <SelectItem value="scrimmage">Scrimmage</SelectItem>
                    <SelectItem value="playoff">Playoff</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="event_name">
                {gameType === "tournament"
                  ? "Tournament Name"
                  : gameType === "playoff"
                    ? "Playoff Name"
                    : "League Name"}{" "}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Input
                id="event_name"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                placeholder="HCRPS 8th Grade Alliance"
              />
            </div>
          </CardContent>
        </Card>

        {/* Game recap */}
        <Card>
          <CardContent className="space-y-2 px-4 py-4">
            <div className="flex items-baseline justify-between">
              <h2 className="font-bold">Game Recap</h2>
              <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
                Optional
              </span>
            </div>
            <p className="text-muted-foreground text-xs">
              Paste the GameChanger story recap here.
            </p>
            <Textarea
              value={recap}
              onChange={(e) => setRecap(e.target.value)}
              rows={4}
              placeholder="Paste the GameChanger match recap…"
            />
          </CardContent>
        </Card>

        {/* Box score */}
        <Card>
          <CardContent className="space-y-3 px-4 py-4">
            <div className="flex items-baseline justify-between">
              <h2 className="font-bold">Box Score</h2>
              <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
                Optional
              </span>
            </div>
            <p className="text-muted-foreground text-xs">
              GameChanger PDF, screenshot, CSV, or text. Skip if notes-only.
            </p>
            <FileInputButton
              value={boxScore}
              onChange={setBoxScore}
              accept=".pdf,.csv,.txt,image/png,image/jpeg,image/webp"
              label="Upload box score"
            />
          </CardContent>
        </Card>

        {/* Game insights — 2x2 screenshot grid */}
        <Card>
          <CardContent className="space-y-3 px-4 py-4">
            <div className="flex items-baseline justify-between">
              <h2 className="font-bold">Game Insights</h2>
              <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
                Optional
              </span>
            </div>
            <p className="text-muted-foreground text-xs">
              GameChanger app insights — screenshot each half for both teams.
            </p>
            <div className="grid grid-cols-2 gap-2 sm:gap-3">
              <InsightCell
                label="🏀 Sting H1"
                file={insightStingH1}
                onChange={setInsightStingH1}
              />
              <InsightCell
                label="🏀 Sting H2"
                file={insightStingH2}
                onChange={setInsightStingH2}
              />
              <InsightCell
                label="⚔ Opp H1"
                file={insightOppH1}
                onChange={setInsightOppH1}
              />
              <InsightCell
                label="⚔ Opp H2"
                file={insightOppH2}
                onChange={setInsightOppH2}
              />
            </div>
          </CardContent>
        </Card>

        {/* Coach notes — 5 specific sections */}
        <Card>
          <CardContent className="space-y-4 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-bold">Coach Notes</h2>
              {savedNotes.length > 0 && (
                <Select onValueChange={loadSavedNote}>
                  <SelectTrigger className="h-8 w-[220px] text-xs">
                    <SelectValue placeholder="Load saved note…" />
                  </SelectTrigger>
                  <SelectContent>
                    {savedNotes.map((n) => (
                      <SelectItem key={n.id} value={n.id}>
                        {(n.opponent || "Untitled") +
                          (n.date ? ` · ${n.date}` : "")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <p className="text-muted-foreground text-xs">
              The more detail, the better the report. Use jersey numbers.
            </p>

            <div className="grid gap-3 sm:grid-cols-2">
              <NotesField
                id="what_they_ran"
                label="What did they run?"
                hint="Defense, offense, presses"
                value={whatTheyRan}
                onChange={setWhatTheyRan}
                placeholder={
                  "2-3 zone\nTriangle offense\n3-2 press\nPress break: pass to corner"
                }
              />
              <NotesField
                id="opp_tendencies"
                label="Opponent player tendencies"
                hint="One per player, with jersey #"
                value={oppTendencies}
                onChange={setOppTendencies}
                placeholder={
                  "#1 can shoot, scored most\n#10 can't handle pressure\n#7 best player, boards\n#13 drives, make him shoot"
                }
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <NotesField
                id="what_worked"
                label="What worked?"
                hint="Plays, runs, individual matchups"
                value={whatWorked}
                onChange={setWhatWorked}
                accent="text-emerald-600"
                placeholder={
                  "Full court press Q3\nBaseline drives broke zone\nTransition off steals"
                }
              />
              <NotesField
                id="what_didnt"
                label="What didn't work?"
                hint="Mistakes, breakdowns"
                value={whatDidnt}
                onChange={setWhatDidnt}
                accent="text-rose-600"
                placeholder={
                  "Too many turnovers\nDidn't match intensity\n3pt shooting off"
                }
              />
            </div>
            <NotesField
              id="extra_notes"
              label="Additional notes"
              hint=""
              value={extraNotes}
              onChange={setExtraNotes}
              rows={3}
              placeholder="Other observations, key plays, adjustments…"
            />
          </CardContent>
        </Card>

        {error && (
          <p className="text-rose-600 text-sm font-semibold">{error}</p>
        )}

        <Button type="submit" disabled={busy} className="w-full">
          <Wand2 className="mr-2 h-4 w-4" />
          {busy ? "Processing…" : "Process game"}
        </Button>
      </form>

      {/* Agent pipeline visualization */}
      {(busy || Object.keys(progress).length > 0) && (
        <AgentPipeline
          pipeline={NEW_GAME_PIPELINE}
          progress={progress}
          elapsed={elapsed}
        />
      )}

      {/* Postgame report */}
      {result && (
        <section className="mt-6 space-y-4">
          <h2 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
            Postgame report
          </h2>
          <Card>
            <CardContent className="px-4 py-4">
              {result.opponent && (
                <div className="mb-3 flex flex-wrap items-baseline gap-2 border-b pb-3">
                  <span className="font-semibold">vs {result.opponent}</span>
                  {result.date && (
                    <span className="text-muted-foreground text-sm">
                      · {result.date}
                    </span>
                  )}
                  {result.our_score != null && result.opp_score != null && (
                    <span className="text-muted-foreground ml-auto tabular-nums text-sm">
                      {result.our_score}-{result.opp_score} {result.result}
                    </span>
                  )}
                </div>
              )}
              {result.report_text && <Markdown>{result.report_text}</Markdown>}
            </CardContent>
          </Card>

          <PostgameFollowup
            gameId={result.game_id}
            opponent={result.opponent ?? opponent}
            date={result.date ?? date}
          />
        </section>
      )}
    </main>
  );
}

function ScoreBox({
  label,
  value,
  onChange,
  accent,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  accent: string;
}) {
  return (
    <div
      className={`flex flex-col items-center rounded-xl border px-2 py-2 ${accent}`}
    >
      <div className="text-[10px] font-bold uppercase tracking-widest">
        {label}
      </div>
      <input
        type="number"
        inputMode="numeric"
        placeholder="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-transparent border-0 p-1 text-center text-4xl font-black tabular-nums focus:outline-none sm:text-5xl"
      />
    </div>
  );
}

function InsightCell({
  label,
  file,
  onChange,
}: {
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
}) {
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <label
      className={`group relative flex aspect-[4/3] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-lg border-2 border-dashed transition-colors ${
        file
          ? "border-emerald-500/40 bg-emerald-500/5"
          : "border-border hover:border-primary hover:bg-muted/40"
      }`}
    >
      {preview && (
        <img
          src={preview}
          alt={label}
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}
      <div
        className={`relative z-10 flex flex-col items-center gap-0.5 ${preview ? "bg-black/50 text-white px-2 py-1 rounded" : ""}`}
      >
        <span className="text-xs font-semibold">{label}</span>
        {!preview && (
          <span className="text-muted-foreground text-[10px]">
            Tap to upload
          </span>
        )}
      </div>
      {file && (
        <span className="absolute right-1.5 top-1.5 z-10 inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white">
          <CheckCircle2 className="h-3.5 w-3.5" />
        </span>
      )}
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="sr-only"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

function NotesField({
  id,
  label,
  hint,
  value,
  onChange,
  rows = 3,
  accent,
  placeholder,
}: {
  id: string;
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  accent?: string;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label
        htmlFor={id}
        className={`text-[11px] font-bold uppercase tracking-wider ${accent ?? ""}`}
      >
        {label}
        {hint && (
          <span className="text-muted-foreground ml-2 font-normal normal-case tracking-normal">
            {hint}
          </span>
        )}
      </Label>
      <Textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        placeholder={placeholder}
        className="text-sm"
      />
    </div>
  );
}

function PostgameFollowup({
  gameId,
  opponent,
  date,
}: {
  gameId?: string;
  opponent: string;
  date: string;
}) {
  const [gcLink, setGcLink] = useState("");
  const [tendencies, setTendencies] = useState("");
  const [adjustments, setAdjustments] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!gcLink.trim() && !tendencies.trim() && !adjustments.trim()) {
      setError("Add at least one field before saving.");
      return;
    }
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const res = await fetch("/api/game/followup", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game_id: gameId,
          opponent,
          date,
          gc_link: gcLink.trim(),
          tendencies: tendencies.trim(),
          adjustments: adjustments.trim(),
        }),
      });
      const data = (await res.json()) as {
        error?: string;
        players_added?: number;
        observations_added?: number;
      };
      if (!res.ok || data.error) {
        setError(data.error ?? `HTTP ${res.status}`);
      } else {
        setStatus(
          `Saved · ${data.players_added ?? 0} player tendencies, ${data.observations_added ?? 0} observations.`,
        );
        setGcLink("");
        setTendencies("");
        setAdjustments("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="px-4 py-4">
        <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground mb-3">
          Postgame follow-up
        </h3>
        <form className="space-y-3" onSubmit={save}>
          <div className="space-y-1.5">
            <Label htmlFor="gc_link">GameChanger recap link</Label>
            <Input
              id="gc_link"
              value={gcLink}
              onChange={(e) => setGcLink(e.target.value)}
              placeholder="https://web.gc.com/teams/…/recap"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="postgame_tendencies">
              Opponent tendencies (one per line)
            </Label>
            <Textarea
              id="postgame_tendencies"
              value={tendencies}
              onChange={(e) => setTendencies(e.target.value)}
              rows={3}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="postgame_adjustments">Adjustments / takeaways</Label>
            <Textarea
              id="postgame_adjustments"
              value={adjustments}
              onChange={(e) => setAdjustments(e.target.value)}
              rows={3}
            />
          </div>
          {error && (
            <p className="text-rose-600 text-xs font-semibold">{error}</p>
          )}
          {status && (
            <p className="text-emerald-600 text-xs font-semibold">{status}</p>
          )}
          <Button type="submit" disabled={busy} variant="outline">
            {busy ? "Saving…" : "Save follow-up"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
