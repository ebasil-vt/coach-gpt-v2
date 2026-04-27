"use client";

import { useEffect, useState } from "react";
import { Calendar, Plus, Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  ApiError,
  EmptyState,
  LoadingList,
  NotSignedIn,
} from "@/components/page-states";
import { Markdown } from "@/components/markdown";
import {
  AgentPipeline,
  SCOUT_PIPELINE,
  type ProgressByAgent,
} from "@/components/agent-pipeline";
import { apiGet, apiPost } from "@/lib/api";
import { streamPost } from "@/lib/sse";
import type { OpponentPlayer } from "@/lib/types";

type ListState =
  | { kind: "loading" }
  | { kind: "ok"; opponents: string[] }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

type Action = "scout" | "pregame" | "research";

export default function ScoutPage() {
  const [state, setState] = useState<ListState>({ kind: "loading" });
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    apiGet<string[]>("/api/opponents").then((r) => {
      if (r.kind === "ok") setState({ kind: "ok", opponents: r.data });
      else if (r.kind === "unauthorized") setState({ kind: "unauthorized" });
      else setState({ kind: "error", message: r.message });
    });
  }, []);

  const filtered =
    state.kind === "ok"
      ? state.opponents.filter((o) =>
          o.toLowerCase().includes(query.toLowerCase()),
        )
      : [];

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">Scout</h1>
        <p className="text-muted-foreground text-sm">
          Search past opponents. Open one to run scout, pre-game, or research.
        </p>
      </header>

      <div className="relative mb-4">
        <Search className="text-muted-foreground absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" />
        <Input
          placeholder="Filter opponents…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {state.kind === "loading" && <LoadingList />}
      {state.kind === "unauthorized" && <NotSignedIn />}
      {state.kind === "error" && <ApiError message={state.message} />}
      {state.kind === "ok" && state.opponents.length === 0 && (
        <EmptyState
          title="No opponents yet"
          description="Process a game to populate the opponent list."
        />
      )}
      {state.kind === "ok" && filtered.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((opp) => (
            <button
              key={opp}
              type="button"
              onClick={() => setSelected(opp)}
              className="text-left"
            >
              <Card className="hover:bg-muted/40 transition-colors">
                <CardContent className="px-4 py-3">
                  <div className="font-semibold truncate">{opp}</div>
                  <div className="text-muted-foreground mt-0.5 text-xs">
                    Tap to open
                  </div>
                </CardContent>
              </Card>
            </button>
          ))}
        </div>
      )}

      <Sheet
        open={selected !== null}
        onOpenChange={(o) => !o && setSelected(null)}
      >
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl overflow-y-auto"
        >
          {selected && <OpponentDetail opponent={selected} />}
        </SheetContent>
      </Sheet>
    </main>
  );
}

function OpponentDetail({ opponent }: { opponent: string }) {
  const [players, setPlayers] = useState<OpponentPlayer[] | null>(null);
  const [streaming, setStreaming] = useState<Action | null>(null);
  const [progress, setProgress] = useState<ProgressByAgent>({});
  const [resultText, setResultText] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    apiGet<OpponentPlayer[]>(`/api/opponent-players/${encodeURIComponent(opponent)}`).then(
      (r) => {
        if (r.kind === "ok") setPlayers(r.data);
      },
    );
  }, [opponent]);

  useEffect(() => {
    if (!streaming) return;
    const start = Date.now();
    setElapsed(0);
    const id = setInterval(
      () => setElapsed(Math.floor((Date.now() - start) / 1000)),
      500,
    );
    return () => clearInterval(id);
  }, [streaming]);

  function setAgent(
    key: string,
    state: "waiting" | "active" | "done" | "error",
    step?: string,
    detail?: string,
  ) {
    setProgress((p) => ({ ...p, [key]: { step, detail, state } }));
  }

  async function runAction(action: Action) {
    setStreaming(action);
    setProgress({});
    setResultText(null);
    const path =
      action === "scout"
        ? `/api/scout/${encodeURIComponent(opponent)}/stream`
        : action === "pregame"
          ? `/api/pregame/${encodeURIComponent(opponent)}/stream`
          : `/api/research/${encodeURIComponent(opponent)}/stream`;
    let lastAgent: string | null = null;
    try {
      await streamPost(path, {}, (e) => {
        if (e.error) {
          if (lastAgent) setAgent(lastAgent, "error", undefined, String(e.error));
          toast.error(String(e.error));
          return;
        }
        if (typeof e.result === "string") {
          setResultText(e.result);
          if (lastAgent) setAgent(lastAgent, "done");
          toast.success(`${action[0].toUpperCase() + action.slice(1)} ready`);
          return;
        }
        if (e.result && typeof e.result === "object" && "report_text" in e.result) {
          setResultText(
            String((e.result as { report_text: string }).report_text),
          );
          if (lastAgent) setAgent(lastAgent, "done");
          toast.success(`${action[0].toUpperCase() + action.slice(1)} ready`);
          return;
        }
        const agent = (e.agent as string | undefined) ?? null;
        const step = e.step as string | undefined;
        const detail = e.detail as string | undefined;
        if (agent) {
          if (lastAgent && lastAgent !== agent) setAgent(lastAgent, "done");
          setAgent(agent, "active", step, detail);
          lastAgent = agent;
        }
      });
      if (lastAgent) setAgent(lastAgent, "done");
    } finally {
      setStreaming(null);
    }
  }

  return (
    <>
      <SheetHeader>
        <SheetTitle>vs {opponent}</SheetTitle>
      </SheetHeader>

      <section className="mt-4 space-y-2 px-4">
        <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
          Run an analysis
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <Button
            disabled={streaming !== null}
            onClick={() => runAction("scout")}
            variant={streaming === "scout" ? "secondary" : "default"}
          >
            {streaming === "scout" ? "Scouting…" : "Scout"}
          </Button>
          <Button
            disabled={streaming !== null}
            onClick={() => runAction("pregame")}
            variant={streaming === "pregame" ? "secondary" : "outline"}
          >
            {streaming === "pregame" ? "Generating…" : "Pre-Game"}
          </Button>
          <Button
            disabled={streaming !== null}
            onClick={() => runAction("research")}
            variant={streaming === "research" ? "secondary" : "outline"}
          >
            {streaming === "research" ? "Researching…" : "Research"}
          </Button>
        </div>
      </section>

      {(streaming || Object.keys(progress).length > 0) && (
        <div className="px-4">
          <AgentPipeline
            pipeline={SCOUT_PIPELINE}
            progress={progress}
            elapsed={elapsed}
          />
        </div>
      )}

      {resultText && (
        <div className="mt-4 px-4 pb-4">
          <Markdown>{resultText}</Markdown>
        </div>
      )}

      <section className="mt-6 px-4">
        <div className="mb-2 flex items-baseline justify-between">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
            Known players
          </h3>
        </div>

        <AddOpponentPlayer
          opponent={opponent}
          onAdded={() =>
            apiGet<OpponentPlayer[]>(
              `/api/opponent-players/${encodeURIComponent(opponent)}`,
            ).then((r) => {
              if (r.kind === "ok") setPlayers(r.data);
            })
          }
        />

        {players === null ? (
          <LoadingList count={3} />
        ) : players.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No players logged for this opponent yet.
          </p>
        ) : (
          <ul className="space-y-2">
            {players.map((p) => (
              <OpponentPlayerRow
                key={p.id}
                player={p}
                onChanged={(updated) =>
                  setPlayers((prev) =>
                    prev ? prev.map((x) => (x.id === updated.id ? updated : x)) : prev,
                  )
                }
                onDeleted={(id) =>
                  setPlayers((prev) => (prev ? prev.filter((x) => x.id !== id) : prev))
                }
              />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

function AddOpponentPlayer({
  opponent,
  onAdded,
}: {
  opponent: string;
  onAdded: () => void;
}) {
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [tendencies, setTendencies] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const cleanNumber = number.replace("#", "").trim();
    if (!cleanNumber) {
      setError("Jersey number required.");
      return;
    }
    setBusy(true);
    const today = new Date().toISOString().split("T")[0];
    const lines = tendencies.split("\n").map((l) => l.trim()).filter(Boolean);
    try {
      // Each tendency goes through the followup endpoint, which creates the
      // opponent player on first hit and appends tendencies on subsequent.
      const items = lines.length > 0 ? lines : [name || "player"];
      for (const line of items) {
        await fetch("/api/game/followup", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            game_id: null,
            opponent,
            date: today,
            gc_link: "",
            tendencies: `#${cleanNumber} ${line}`,
            adjustments: "",
          }),
        });
      }
      setNumber("");
      setName("");
      setTendencies("");
      setOpen(false);
      onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className="mb-3"
      >
        <Plus className="mr-1 h-3 w-3" />
        Add player
      </Button>
    );
  }

  return (
    <Card className="mb-3">
      <CardContent className="px-4 py-3">
        <form className="space-y-3" onSubmit={save}>
          <div className="grid gap-2 sm:grid-cols-2">
            <Input
              placeholder="Jersey #"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              className="h-8"
              autoFocus
            />
            <Input
              placeholder="Name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-8"
            />
          </div>
          <textarea
            placeholder="Tendencies — one per line (optional)"
            value={tendencies}
            onChange={(e) => setTendencies(e.target.value)}
            rows={3}
            className="w-full rounded-md border bg-background px-3 py-1.5 text-xs"
          />
          {error && <p className="text-rose-600 text-xs">{error}</p>}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setOpen(false)}
              disabled={busy}
            >
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function OpponentPlayerRow({
  player,
  onChanged,
  onDeleted,
}: {
  player: OpponentPlayer;
  onChanged: (p: OpponentPlayer) => void;
  onDeleted: (id: string) => void;
}) {
  const [adding, setAdding] = useState("");

  async function addTendency() {
    if (!adding.trim()) return;
    const r = await apiPost<{ ok: boolean; tendencies: string[] }>(
      `/api/opponent-player/${player.id}/update`,
      { action: "add_tendency", tendency: adding.trim() },
    );
    if (r.kind === "ok") {
      onChanged({ ...player, tendencies: r.data.tendencies });
      setAdding("");
    }
  }

  async function deleteTendency(idx: number) {
    const r = await apiPost<{ ok: boolean; tendencies: string[] }>(
      `/api/opponent-player/${player.id}/update`,
      { action: "delete_tendency", index: idx },
    );
    if (r.kind === "ok") {
      onChanged({ ...player, tendencies: r.data.tendencies });
    }
  }

  async function deletePlayer() {
    const r = await apiPost<{ ok: boolean }>(
      `/api/opponent-player/${player.id}/update`,
      { action: "delete_player" },
    );
    if (r.kind === "ok") onDeleted(player.id);
  }

  return (
    <li>
      <Card>
        <CardContent className="space-y-2 px-4 py-3">
          <div className="flex items-baseline justify-between gap-2">
            <div className="flex items-baseline gap-2">
              <span className="text-muted-foreground tabular-nums">
                #{player.player_number}
              </span>
              <span className="font-semibold">
                {player.player_name || "Unknown"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {player.last_seen_date && (
                <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
                  <Calendar className="h-3 w-3" />
                  {player.last_seen_date}
                </span>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="text-rose-600 hover:bg-rose-500/10"
                onClick={deletePlayer}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </div>
          {player.tendencies.length > 0 && (
            <ul className="space-y-1">
              {player.tendencies.map((t, i) => (
                <li
                  key={i}
                  className="bg-muted/40 flex items-center gap-2 rounded-md px-2 py-1 text-xs"
                >
                  <Badge variant="secondary" className="shrink-0 text-[10px]">
                    {i + 1}
                  </Badge>
                  <span className="flex-1">{t}</span>
                  <button
                    type="button"
                    onClick={() => deleteTendency(i)}
                    className="text-muted-foreground hover:text-rose-500"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <Input
              placeholder="Add tendency…"
              value={adding}
              onChange={(e) => setAdding(e.target.value)}
              className="h-8 text-xs"
              onKeyDown={(e) => {
                if (e.key === "Enter") addTendency();
              }}
            />
            <Button
              size="sm"
              variant="outline"
              onClick={addTendency}
              disabled={!adding.trim()}
            >
              <Plus className="h-3 w-3" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </li>
  );
}
