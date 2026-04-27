"use client";

import { useEffect, useState } from "react";
import { Trophy, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  EmptyState,
  LoadingList,
  NotSignedIn,
} from "@/components/page-states";
import { Markdown } from "@/components/markdown";
import { FileInputButton } from "@/components/file-input-button";
import { apiGet, apiPostForm } from "@/lib/api";

type LeagueSummary = {
  id: string;
  name: string;
  created_at: string;
  teams_count: number;
};

type LeagueDetail = {
  standings?: Array<{
    rank?: number;
    team: string;
    record?: string;
    wins?: number;
    losses?: number;
    pct?: number | string;
  }>;
  teams_count?: number;
  season?: string;
  team_name?: string;
  report_text?: string;
};

type ListState =
  | { kind: "loading" }
  | { kind: "ok"; leagues: LeagueSummary[] }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

export default function LeaguePage() {
  const [state, setState] = useState<ListState>({ kind: "loading" });
  const [open, setOpen] = useState<LeagueSummary | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  async function refresh() {
    setState({ kind: "loading" });
    const r = await apiGet<LeagueSummary[]>("/api/leagues");
    if (r.kind === "ok") setState({ kind: "ok", leagues: r.data });
    else if (r.kind === "unauthorized") setState({ kind: "unauthorized" });
    else setState({ kind: "error", message: r.message });
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
            League
          </h1>
          <p className="text-muted-foreground text-sm">
            Imported standings and schedules.
          </p>
        </div>
        <Sheet open={importOpen} onOpenChange={setImportOpen}>
          <SheetTrigger
            render={
              <Button>
                <Upload className="mr-1 h-4 w-4" />
                Import
              </Button>
            }
          />
          <SheetContent
            side="right"
            className="w-full sm:max-w-xl overflow-y-auto"
          >
            <SheetHeader>
              <SheetTitle>Import league data</SheetTitle>
            </SheetHeader>
            <div className="px-4">
              <ImportForm
                onDone={() => {
                  setImportOpen(false);
                  refresh();
                }}
              />
            </div>
          </SheetContent>
        </Sheet>
      </header>

      {state.kind === "loading" && <LoadingList />}
      {state.kind === "unauthorized" && <NotSignedIn />}
      {state.kind === "error" && <ApiError message={state.message} />}
      {state.kind === "ok" && state.leagues.length === 0 && (
        <EmptyState
          title="No leagues imported"
          description="Paste standings text or upload a webarchive/PDF to populate this page."
        />
      )}
      {state.kind === "ok" && state.leagues.length > 0 && (
        <ul className="space-y-2">
          {state.leagues.map((l) => (
            <li key={l.id}>
              <button
                type="button"
                onClick={() => setOpen(l)}
                className="block w-full text-left"
              >
                <Card className="hover:bg-muted/40 transition-colors">
                  <CardContent className="flex items-center gap-3 px-4 py-3">
                    <Trophy className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold truncate">{l.name}</div>
                      <div className="text-muted-foreground text-xs">
                        {new Date(l.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <Badge variant="secondary" className="text-[10px]">
                      {l.teams_count} teams
                    </Badge>
                  </CardContent>
                </Card>
              </button>
            </li>
          ))}
        </ul>
      )}

      <Sheet open={open !== null} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent
          side="right"
          className="w-full sm:max-w-2xl overflow-y-auto"
        >
          {open && <LeagueDetailView id={open.id} name={open.name} />}
        </SheetContent>
      </Sheet>
    </main>
  );
}

function ImportForm({ onDone }: { onDone: () => void }) {
  const [standingsText, setStandingsText] = useState("");
  const [teamName, setTeamName] = useState("");
  const [seasonName, setSeasonName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!standingsText.trim() && !file) {
      setError("Paste standings or pick a file.");
      return;
    }
    setBusy(true);
    const fd = new FormData();
    fd.append("standings_text", standingsText);
    fd.append("team_name", teamName);
    fd.append("season_name", seasonName);
    if (file) fd.append("file", file);
    const r = await apiPostForm<{ teams_count?: number; error?: string }>(
      "/api/league/import",
      fd,
    );
    setBusy(false);
    if (r.kind === "ok") {
      onDone();
    } else if (r.kind === "unauthorized") {
      setError("Session expired. Please sign in again.");
    } else {
      setError(r.message);
    }
  }

  return (
    <form className="space-y-4 py-4" onSubmit={submit}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="team_name">Your team name (optional)</Label>
          <Input
            id="team_name"
            value={teamName}
            onChange={(e) => setTeamName(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="season_name">Season name (optional)</Label>
          <Input
            id="season_name"
            value={seasonName}
            onChange={(e) => setSeasonName(e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>File (.webarchive, .pdf, or .txt)</Label>
        <FileInputButton
          value={file}
          onChange={setFile}
          accept=".webarchive,.pdf,.txt"
          label="Upload file"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="standings_text">…or paste standings text</Label>
        <Textarea
          id="standings_text"
          value={standingsText}
          onChange={(e) => setStandingsText(e.target.value)}
          rows={8}
          placeholder="Paste the standings table here…"
          className="font-mono text-xs"
        />
      </div>
      {error && (
        <p className="text-rose-600 text-xs font-semibold">{error}</p>
      )}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Importing…" : "Import"}
      </Button>
    </form>
  );
}

function LeagueDetailView({ id, name }: { id: string; name: string }) {
  const [data, setData] = useState<LeagueDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<LeagueDetail>(`/api/league/${encodeURIComponent(id)}`).then((r) => {
      if (r.kind === "ok") setData(r.data);
      else if (r.kind === "error") setError(r.message);
    });
  }, [id]);

  return (
    <>
      <SheetHeader>
        <SheetTitle>{name}</SheetTitle>
      </SheetHeader>
      <div className="px-4 py-4">
        {error && <ApiError message={error} />}
        {!data && !error && <LoadingList count={4} />}
        {data?.standings && data.standings.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground text-left text-[10px] uppercase tracking-wider">
                <th className="pb-2">#</th>
                <th className="pb-2">Team</th>
                <th className="pb-2 text-right">Record</th>
              </tr>
            </thead>
            <tbody>
              {data.standings.map((s, i) => (
                <tr key={i} className="border-t">
                  <td className="text-muted-foreground py-2 tabular-nums">
                    {s.rank ?? i + 1}
                  </td>
                  <td className="py-2 font-medium">{s.team}</td>
                  <td className="py-2 text-right tabular-nums">
                    {s.record ?? `${s.wins ?? 0}-${s.losses ?? 0}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data?.report_text && (
          <div className="mt-4">
            <Markdown>{data.report_text}</Markdown>
          </div>
        )}
      </div>
    </>
  );
}
