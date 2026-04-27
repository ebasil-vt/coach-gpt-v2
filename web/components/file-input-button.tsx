"use client";

import { useId, useRef } from "react";
import { Upload, X } from "lucide-react";

import { Button } from "@/components/ui/button";

export function FileInputButton({
  value,
  onChange,
  accept,
  label = "Choose file",
  disabled = false,
}: {
  value: File | null;
  onChange: (f: File | null) => void;
  accept?: string;
  label?: string;
  disabled?: boolean;
}) {
  const id = useId();
  const ref = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        id={id}
        ref={ref}
        type="file"
        accept={accept}
        disabled={disabled}
        className="sr-only"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => ref.current?.click()}
      >
        <Upload className="mr-1 h-3.5 w-3.5" />
        {value ? "Replace" : label}
      </Button>
      {value && (
        <div className="bg-muted/40 flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-xs">
          <span className="truncate font-mono">{value.name}</span>
          <span className="text-muted-foreground tabular-nums">
            {formatBytes(value.size)}
          </span>
          <button
            type="button"
            onClick={() => {
              onChange(null);
              if (ref.current) ref.current.value = "";
            }}
            className="text-muted-foreground hover:text-rose-500"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
