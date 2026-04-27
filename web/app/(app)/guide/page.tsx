"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, NotSignedIn } from "@/components/page-states";
import { Markdown } from "@/components/markdown";
import { apiGet } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "ok"; markdown: string }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

export default function GuidePage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    apiGet<{ content: string }>("/api/guide").then((r) => {
      if (r.kind === "ok") {
        setState({ kind: "ok", markdown: r.data.content ?? "" });
      } else if (r.kind === "unauthorized") {
        setState({ kind: "unauthorized" });
      } else {
        setState({ kind: "error", message: r.message });
      }
    });
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 md:px-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">
          Coach&apos;s Guide
        </h1>
        <p className="text-muted-foreground text-sm">
          How to use CoachGPT day-to-day.
        </p>
      </header>

      {state.kind === "loading" && (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      )}
      {state.kind === "unauthorized" && <NotSignedIn />}
      {state.kind === "error" && <ApiError message={state.message} />}
      {state.kind === "ok" && <Markdown>{state.markdown}</Markdown>}
    </main>
  );
}
