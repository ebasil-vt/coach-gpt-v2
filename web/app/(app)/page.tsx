"use client";

import { useEffect, useState } from "react";
import { Settings } from "lucide-react";

import { PlayerCard, type PlayerCardView } from "@/components/player-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  ApiError,
  EmptyState,
  NotSignedIn,
} from "@/components/page-states";
import { TeamManageSheet } from "@/components/team-manage-sheet";
import type { PlayerCardData } from "@/lib/types";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; cards: PlayerCardData[] }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

export default function Page() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [view, setView] = useState<PlayerCardView>("detailed");
  const [manageOpen, setManageOpen] = useState(false);

  async function loadCards() {
    setState({ kind: "loading" });
    try {
      const res = await fetch("/api/player-cards", { credentials: "include" });
      if (res.status === 401) {
        setState({ kind: "unauthorized" });
        return;
      }
      if (!res.ok) {
        setState({ kind: "error", message: `HTTP ${res.status}` });
        return;
      }
      const cards = (await res.json()) as PlayerCardData[];
      setState({ kind: "ok", cards });
    } catch (e) {
      setState({
        kind: "error",
        message: e instanceof Error ? e.message : "Network error",
      });
    }
  }

  useEffect(() => {
    loadCards();
  }, []);

  return (
    <main className="min-h-svh px-4 py-8 md:px-8">
      <header className="mx-auto mb-6 flex max-w-7xl flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
            Team
          </h1>
          <p className="text-muted-foreground text-sm">
            Player cards · season averages with last-5 trends
          </p>
        </div>
        <div className="flex items-center gap-2">
          {state.kind === "ok" && state.cards.length > 0 && (
            <Tabs
              value={view}
              onValueChange={(v) => setView(v as PlayerCardView)}
            >
              <TabsList>
                <TabsTrigger value="detailed">Detailed</TabsTrigger>
                <TabsTrigger value="radar">Radar</TabsTrigger>
              </TabsList>
            </Tabs>
          )}
          <Sheet open={manageOpen} onOpenChange={setManageOpen}>
            <SheetTrigger
              render={
                <Button variant="outline" size="sm">
                  <Settings className="mr-1 h-4 w-4" />
                  Manage
                </Button>
              }
            />
            <SheetContent
              side="right"
              className="w-full sm:max-w-xl overflow-y-auto"
            >
              <SheetHeader>
                <SheetTitle>Manage team</SheetTitle>
              </SheetHeader>
              <TeamManageSheet
                onSeasonImported={() => {
                  setManageOpen(false);
                  loadCards();
                }}
              />
            </SheetContent>
          </Sheet>
        </div>
      </header>

      {state.kind === "loading" && <LoadingGrid />}
      {state.kind === "unauthorized" && <NotSignedIn />}
      {state.kind === "error" && <ApiError message={state.message} />}
      {state.kind === "ok" && state.cards.length === 0 && (
        <EmptyState
          title="No player cards yet"
          description="Click Manage above to import a season CSV from GameChanger."
        />
      )}
      {state.kind === "ok" && state.cards.length > 0 && (
        <div className="mx-auto grid max-w-7xl gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {state.cards.map((p) => (
            <PlayerCard key={String(p.number)} p={p} view={view} />
          ))}
        </div>
      )}
    </main>
  );
}

function LoadingGrid() {
  return (
    <div className="mx-auto grid max-w-7xl gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-[520px] w-full rounded-2xl" />
      ))}
    </div>
  );
}
