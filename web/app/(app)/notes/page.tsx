"use client";

import { useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  EmptyState,
  LoadingList,
  NotSignedIn,
} from "@/components/page-states";
import { apiGet, apiPost } from "@/lib/api";
import {
  EMPTY_SECTIONS,
  SECTION_DEFS,
  markdownToSections,
  sectionsToMarkdown,
  type NoteSections,
} from "@/lib/coach-note-template";
import type { CoachNote } from "@/lib/types";

type State =
  | { kind: "loading" }
  | { kind: "ok"; notes: CoachNote[] }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

export default function NotesPage() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [editing, setEditing] = useState<CoachNote | null>(null);

  async function refresh() {
    const r = await apiGet<CoachNote[]>("/api/notes");
    if (r.kind === "ok") setState({ kind: "ok", notes: r.data });
    else if (r.kind === "unauthorized") setState({ kind: "unauthorized" });
    else setState({ kind: "error", message: r.message });
  }

  useEffect(() => {
    refresh();
  }, []);

  function startNew() {
    setEditing({
      id: "",
      content: "",
      opponent: "",
      date: new Date().toISOString().split("T")[0],
    });
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 md:px-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
            Notes
          </h1>
          <p className="text-muted-foreground text-sm">
            Take notes during or right after a game — same 5 sections as New
            Game so they drop straight back in later.
          </p>
        </div>
        <Button onClick={startNew}>
          <Plus className="mr-1 h-4 w-4" />
          New note
        </Button>
      </header>

      {editing && (
        <NoteEditor
          note={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}

      {state.kind === "loading" && <LoadingList />}
      {state.kind === "unauthorized" && <NotSignedIn />}
      {state.kind === "error" && <ApiError message={state.message} />}
      {state.kind === "ok" && state.notes.length === 0 && !editing && (
        <EmptyState
          title="No notes yet"
          description="Tap 'New note' on the bench or in the parking lot — fill what you remember, save, then load it back into New Game when you process the box score later."
        />
      )}
      {state.kind === "ok" && state.notes.length > 0 && (
        <ul className="space-y-2">
          {state.notes.map((n) => (
            <NoteRow
              key={n.id}
              note={n}
              onEdit={() => setEditing(n)}
              onDeleted={refresh}
            />
          ))}
        </ul>
      )}
    </main>
  );
}

function NoteEditor({
  note,
  onClose,
  onSaved,
}: {
  note: CoachNote;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [opponent, setOpponent] = useState(note.opponent ?? "");
  const [date, setDate] = useState(note.date ?? "");
  const [sections, setSections] = useState<NoteSections>(() =>
    note.content ? markdownToSections(note.content) : EMPTY_SECTIONS,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const md = sectionsToMarkdown(sections);
    if (!md.trim()) {
      setError("Add something to at least one section before saving.");
      return;
    }
    setBusy(true);
    setError(null);
    const r = await apiPost<{ id: string; ok: boolean }>("/api/note", {
      id: note.id || undefined,
      content: md,
      opponent: opponent.trim(),
      date: date.trim(),
    });
    setBusy(false);
    if (r.kind === "ok") onSaved();
    else if (r.kind === "unauthorized") setError("Session expired.");
    else setError(r.message);
  }

  function setField(key: keyof NoteSections, value: string) {
    setSections((s) => ({ ...s, [key]: value }));
  }

  return (
    <Card className="mb-4">
      <CardContent className="space-y-4 px-4 py-4">
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
          <div className="space-y-1.5">
            <Label htmlFor="note_opponent">Opponent (optional)</Label>
            <Input
              id="note_opponent"
              value={opponent}
              onChange={(e) => setOpponent(e.target.value)}
              placeholder="Howard Hawks"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="note_date">Date</Label>
            <Input
              id="note_date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
        </div>

        {SECTION_DEFS.map((def) => (
          <div key={def.key} className="space-y-1.5">
            <Label
              htmlFor={`note_${def.key}`}
              className={`text-[11px] font-bold uppercase tracking-wider ${def.accent ?? ""}`}
            >
              {def.heading}
              {def.hint && (
                <span className="text-muted-foreground ml-2 font-normal normal-case tracking-normal">
                  {def.hint}
                </span>
              )}
            </Label>
            <Textarea
              id={`note_${def.key}`}
              value={sections[def.key]}
              onChange={(e) => setField(def.key, e.target.value)}
              placeholder={def.placeholder}
              rows={3}
              className="text-sm"
            />
          </div>
        ))}

        {error && <p className="text-rose-600 text-xs font-semibold">{error}</p>}
        <div className="flex gap-2">
          <Button onClick={save} disabled={busy}>
            <Save className="mr-1 h-4 w-4" />
            {busy ? "Saving…" : "Save"}
          </Button>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function NoteRow({
  note,
  onEdit,
  onDeleted,
}: {
  note: CoachNote;
  onEdit: () => void;
  onDeleted: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function del() {
    if (!confirm("Delete this note?")) return;
    setBusy(true);
    const res = await fetch(`/api/note/${encodeURIComponent(note.id)}`, {
      method: "DELETE",
      credentials: "include",
    });
    setBusy(false);
    if (res.ok) onDeleted();
  }

  // Derive a one-line preview from the first non-empty section
  const sections = markdownToSections(note.content);
  const firstFilled = SECTION_DEFS.find((d) => sections[d.key].trim());
  const previewHeading = firstFilled?.heading ?? "Untitled";
  const previewBody =
    firstFilled
      ? sections[firstFilled.key].split("\n").slice(0, 2).join(" · ")
      : "(empty)";

  return (
    <li>
      <Card className="hover:bg-muted/30 transition-colors">
        <CardContent className="flex items-start gap-3 px-4 py-3">
          <div className="min-w-0 flex-1 cursor-pointer" onClick={onEdit}>
            <div className="flex flex-wrap items-baseline gap-2">
              {note.opponent && (
                <span className="font-semibold">{note.opponent}</span>
              )}
              {note.date && (
                <span className="text-muted-foreground text-xs">
                  {note.date}
                </span>
              )}
              {!note.opponent && !note.date && (
                <span className="text-muted-foreground italic">Untitled</span>
              )}
            </div>
            <div className="text-muted-foreground mt-1 text-[10px] uppercase tracking-wider">
              {previewHeading}
            </div>
            <p className="text-foreground/80 mt-0.5 line-clamp-2 text-sm">
              {previewBody}
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            <Button variant="ghost" size="sm" onClick={onEdit}>
              Edit
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={del}
              disabled={busy}
              className="text-rose-600 hover:bg-rose-500/10"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </li>
  );
}
