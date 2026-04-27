"use client";

import { useEffect, useState } from "react";
import { Calendar, MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  ApiError,
  EmptyState,
  LoadingList,
  NotSignedIn,
} from "@/components/page-states";
import { apiGet } from "@/lib/api";
import type { Game } from "@/lib/types";

type PlayerStats = {
  player_number?: string;
  player_name?: string;
  points?: number;
  rebounds?: number;
  assists?: number;
  steals?: number;
  blocks?: number;
  turnovers?: number;
  fg_made?: number;
  fg_attempted?: number;
};

type Observation = { category?: string; detail?: string };

type GameDetail = {
  game: Game;
  our_player_stats: PlayerStats[];
  opp_player_stats: PlayerStats[];
  observations: Observation[];
};

type State =
  | { kind: "loading" }
  | { kind: "ok"; games: Game[] }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

export default function GamesPage() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [open, setOpen] = useState<Game | null>(null);

  useEffect(() => {
    apiGet<Game[]>("/api/games").then((r) => {
      if (r.kind === "ok") setState({ kind: "ok", games: r.data });
      else if (r.kind === "unauthorized") setState({ kind: "unauthorized" });
      else setState({ kind: "error", message: r.message });
    });
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">Games</h1>
        <p className="text-muted-foreground text-sm">
          All processed games, most recent first.
        </p>
      </header>

      {state.kind === "loading" && <LoadingList />}
      {state.kind === "unauthorized" && <NotSignedIn />}
      {state.kind === "error" && <ApiError message={state.message} />}
      {state.kind === "ok" && state.games.length === 0 && (
        <EmptyState
          title="No games yet"
          description="Process your first game from the New Game tab."
        />
      )}
      {state.kind === "ok" && state.games.length > 0 && (
        <ul className="space-y-2">
          {state.games.map((g) => (
            <GameRow key={g.id} game={g} onOpen={() => setOpen(g)} />
          ))}
        </ul>
      )}

      <Sheet open={open !== null} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent
          side="right"
          className="w-full sm:max-w-3xl overflow-y-auto"
        >
          {open && <GameDetailView game={open} />}
        </SheetContent>
      </Sheet>
    </main>
  );
}

function GameRow({ game, onOpen }: { game: Game; onOpen: () => void }) {
  const win = game.result?.toUpperCase() === "W";
  const loss = game.result?.toUpperCase() === "L";

  return (
    <li>
      <button type="button" onClick={onOpen} className="block w-full text-left">
        <Card className="hover:bg-muted/40 transition-colors">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="font-semibold truncate">vs {game.opponent}</span>
                {game.game_type && (
                  <Badge variant="secondary" className="text-[10px] uppercase">
                    {game.game_type}
                  </Badge>
                )}
              </div>
              <div className="text-muted-foreground mt-1 flex items-center gap-3 text-xs flex-wrap">
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {game.date}
                </span>
                {game.location && (
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {game.location}
                  </span>
                )}
                {game.event_name && <span>{game.event_name}</span>}
              </div>
            </div>
            <div className="text-right">
              <div className="tabular-nums text-xl font-bold leading-none">
                {game.our_score ?? "—"}
                <span className="text-muted-foreground mx-1">-</span>
                {game.opp_score ?? "—"}
              </div>
              {(win || loss) && (
                <span
                  className={`mt-1 inline-block text-[10px] font-bold uppercase tracking-wider ${
                    win ? "text-emerald-500" : "text-rose-500"
                  }`}
                >
                  {win ? "Win" : "Loss"}
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      </button>
    </li>
  );
}

function GameDetailView({ game }: { game: Game }) {
  const [data, setData] = useState<GameDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<GameDetail>(`/api/game/${encodeURIComponent(game.id)}`).then((r) => {
      if (r.kind === "ok") setData(r.data);
      else if (r.kind === "error") setError(r.message);
    });
  }, [game.id]);

  return (
    <>
      <SheetHeader>
        <SheetTitle>vs {game.opponent}</SheetTitle>
        <SheetDescription>
          {game.date}
          {game.our_score != null &&
            game.opp_score != null &&
            ` · ${game.our_score}-${game.opp_score} ${game.result ?? ""}`}
        </SheetDescription>
      </SheetHeader>
      <div className="px-4 pb-6">
        {error && <ApiError message={error} />}
        {!data && !error && (
          <div className="mt-4">
            <LoadingList count={3} />
          </div>
        )}
        {data && (
          <div className="space-y-4 mt-2">
            <BoxScore title="Our team" players={data.our_player_stats} />
            <BoxScore title={game.opponent} players={data.opp_player_stats} />
            {data.observations.length > 0 && (
              <section>
                <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground mb-2">
                  Observations
                </h3>
                <ul className="space-y-1.5 text-sm">
                  {data.observations.map((o, i) => (
                    <li key={i} className="flex gap-2">
                      {o.category && (
                        <Badge variant="secondary" className="shrink-0 text-[10px]">
                          {o.category}
                        </Badge>
                      )}
                      <span>{o.detail}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>
    </>
  );
}

function BoxScore({ title, players }: { title: string; players: PlayerStats[] }) {
  if (players.length === 0) {
    return (
      <Card>
        <CardContent className="px-4 py-3">
          <h3 className="font-semibold">{title}</h3>
          <p className="text-muted-foreground mt-2 text-sm">No player stats.</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="px-4 py-3">
        <h3 className="mb-2 font-semibold">{title}</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-muted-foreground text-[10px] uppercase tracking-wider">
              <tr>
                <th className="pb-1 text-left">#</th>
                <th className="pb-1 text-left">Name</th>
                <th className="pb-1 text-right">PTS</th>
                <th className="pb-1 text-right">REB</th>
                <th className="pb-1 text-right">AST</th>
                <th className="pb-1 text-right">STL</th>
                <th className="pb-1 text-right">FG</th>
              </tr>
            </thead>
            <tbody>
              {players.map((p, i) => (
                <tr key={i} className="border-t">
                  <td className="text-muted-foreground py-1.5 tabular-nums">
                    {p.player_number}
                  </td>
                  <td className="py-1.5 truncate">{p.player_name ?? "—"}</td>
                  <td className="py-1.5 text-right tabular-nums font-semibold">
                    {p.points ?? 0}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {p.rebounds ?? 0}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {p.assists ?? 0}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {p.steals ?? 0}
                  </td>
                  <td className="text-muted-foreground py-1.5 text-right tabular-nums">
                    {p.fg_made ?? 0}/{p.fg_attempted ?? 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
