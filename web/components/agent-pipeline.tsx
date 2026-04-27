"use client";

import {
  Boxes,
  CheckCircle2,
  Loader2,
  ScrollText,
  Search,
  Sparkles,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export type AgentState = "waiting" | "active" | "done" | "error";

export type AgentStep = {
  state: AgentState;
  step?: string;
  detail?: string;
};

export type AgentDef = {
  key: string;
  label: string;
  icon: LucideIcon;
};

export type ProgressByAgent = Record<string, AgentStep>;

export const NEW_GAME_PIPELINE: AgentDef[] = [
  { key: "orchestrator", label: "Orchestrator", icon: Sparkles },
  { key: "ingestion", label: "Ingestion", icon: Boxes },
  { key: "analyst", label: "Analysis", icon: Zap },
  { key: "report_writer", label: "Report Writer", icon: ScrollText },
];

export const SCOUT_PIPELINE: AgentDef[] = [
  { key: "orchestrator", label: "Orchestrator", icon: Sparkles },
  { key: "researcher", label: "Researcher", icon: Search },
  { key: "analyst", label: "Analysis", icon: Zap },
  { key: "report_writer", label: "Report Writer", icon: ScrollText },
];

export function AgentPipeline({
  pipeline,
  progress,
  elapsed,
  title = "Agent pipeline",
}: {
  pipeline: AgentDef[];
  progress: ProgressByAgent;
  elapsed: number;
  title?: string;
}) {
  return (
    <section className="mt-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
          {title}
        </h2>
        <span className="text-muted-foreground tabular-nums text-[11px] font-mono">
          {elapsed}s
        </span>
      </div>
      <Card>
        <CardContent className="divide-y px-0 py-0">
          {pipeline.map(({ key, label, icon: Icon }) => {
            const p = progress[key];
            const state = p?.state ?? "waiting";
            return (
              <div key={key} className="flex items-start gap-3 px-4 py-3">
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    state === "active"
                      ? "bg-primary/15 text-primary"
                      : state === "done"
                        ? "bg-emerald-500/15 text-emerald-600"
                        : state === "error"
                          ? "bg-rose-500/15 text-rose-600"
                          : "bg-muted text-muted-foreground"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">{label}</div>
                  <div className="text-muted-foreground text-xs">
                    {p?.step
                      ? p.step + (p.detail ? ` — ${p.detail}` : "")
                      : state === "waiting"
                        ? "Waiting"
                        : state === "done"
                          ? "Done"
                          : ""}
                  </div>
                </div>
                <StateIcon state={state} />
              </div>
            );
          })}
        </CardContent>
      </Card>
    </section>
  );
}

function StateIcon({ state }: { state: AgentState }) {
  if (state === "active")
    return <Loader2 className="text-primary h-4 w-4 animate-spin" />;
  if (state === "done")
    return <CheckCircle2 className="text-emerald-500 h-4 w-4" />;
  if (state === "error") return <XCircle className="text-rose-500 h-4 w-4" />;
  return <span className="bg-muted-foreground/30 h-2 w-2 rounded-full" />;
}
