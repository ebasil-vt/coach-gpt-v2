"use client";

import { useEffect, useState } from "react";
import { Sparkles, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { LoadingList } from "@/components/page-states";
import { Markdown } from "@/components/markdown";
import { FileInputButton } from "@/components/file-input-button";
import { apiGet, apiPost, apiPostForm } from "@/lib/api";
import type { Season } from "@/lib/types";

export function TeamManageSheet({
  onSeasonImported,
}: {
  onSeasonImported: () => void;
}) {
  return (
    <div className="space-y-6 px-4 py-4">
      <ImportSection onImported={onSeasonImported} />
      <Separator />
      <SeasonsSection />
    </div>
  );
}

function ImportSection({ onImported }: { onImported: () => void }) {
  const [seasonName, setSeasonName] = useState("");
  const [teamName, setTeamName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (!file) {
      setError("Pick a CSV file.");
      return;
    }
    setBusy(true);
    const fd = new FormData();
    fd.append("season_name", seasonName);
    fd.append("team_name", teamName);
    fd.append("file", file);
    const r = await apiPostForm<{
      games_imported?: number;
      players_imported?: number;
      error?: string;
    }>("/api/season/import", fd);
    setBusy(false);
    if (r.kind === "ok") {
      setSuccess(
        `Imported · ${r.data.games_imported ?? 0} games, ${r.data.players_imported ?? 0} players.`,
      );
      setSeasonName("");
      setTeamName("");
      setFile(null);
      onImported();
    } else if (r.kind === "unauthorized") {
      setError("Session expired. Please sign in again.");
    } else {
      setError(r.message);
    }
  }

  return (
    <section>
      <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground mb-3">
        Import season CSV
      </h3>
      <form className="space-y-3" onSubmit={submit}>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="season_name">Season name</Label>
            <Input
              id="season_name"
              value={seasonName}
              onChange={(e) => setSeasonName(e.target.value)}
              placeholder="Winter 2026-2027"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="team_name">Team name</Label>
            <Input
              id="team_name"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="Sting 2031 - Peay"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label>GameChanger CSV</Label>
          <FileInputButton
            value={file}
            onChange={setFile}
            accept=".csv"
            label="Upload CSV"
          />
        </div>
        {error && <p className="text-rose-600 text-xs font-semibold">{error}</p>}
        {success && (
          <p className="text-emerald-600 text-xs font-semibold">{success}</p>
        )}
        <Button type="submit" disabled={busy}>
          <Upload className="mr-1 h-4 w-4" />
          {busy ? "Importing…" : "Import"}
        </Button>
      </form>
    </section>
  );
}

function SeasonsSection() {
  const [seasons, setSeasons] = useState<Season[] | null>(null);

  useEffect(() => {
    apiGet<Season[]>("/api/seasons").then((r) => {
      if (r.kind === "ok") setSeasons(r.data);
      else setSeasons([]);
    });
  }, []);

  return (
    <section>
      <h3 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground mb-3">
        Seasons & team identity
      </h3>
      {seasons === null && <LoadingList count={2} />}
      {seasons && seasons.length === 0 && (
        <p className="text-muted-foreground text-sm">
          No imported seasons yet. Import one above to enable identity reports.
        </p>
      )}
      {seasons && seasons.length > 0 && (
        <ul className="space-y-2">
          {seasons.map((s) => (
            <SeasonRow key={s.id} season={s} />
          ))}
        </ul>
      )}
    </section>
  );
}

function SeasonRow({ season }: { season: Season }) {
  const [busy, setBusy] = useState(false);
  const [identity, setIdentity] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setBusy(true);
    setError(null);
    const r = await apiPost<{ identity_text?: string; error?: string }>(
      `/api/season/${encodeURIComponent(season.id)}/identity`,
      {},
    );
    setBusy(false);
    if (r.kind === "ok") {
      setIdentity(r.data.identity_text ?? "(empty)");
    } else if (r.kind === "unauthorized") {
      setError("Session expired.");
    } else {
      setError(r.message);
    }
  }

  return (
    <li>
      <Card>
        <CardContent className="px-3 py-3">
          <div className="flex items-baseline justify-between gap-2">
            <div>
              <div className="font-semibold">{season.name}</div>
              {season.team_name && (
                <div className="text-muted-foreground text-xs">
                  {season.team_name}
                </div>
              )}
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={generate}
              disabled={busy}
            >
              <Sparkles className="mr-1 h-3 w-3" />
              {busy ? "Generating…" : "Identity"}
            </Button>
          </div>
          {error && (
            <p className="text-rose-600 mt-2 text-xs font-semibold">{error}</p>
          )}
          {identity && (
            <div className="mt-3 rounded-md border bg-muted/30 px-3 py-3">
              <Markdown>{identity}</Markdown>
            </div>
          )}
        </CardContent>
      </Card>
    </li>
  );
}
