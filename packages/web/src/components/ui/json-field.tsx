"use client";

import { useState } from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { parseJsonObject, prettyJson } from "@/lib/json-edit";

/**
 * Reusable editor for a free-form JSONB object field (document_identity,
 * settings, operating_hours, metadata…). Validates on every keystroke and
 * reports `(value, valid)` so the parent can block Save on malformed input.
 *
 * Empty text === `{}` (matches the backend `default_factory=dict`). Arrays and
 * primitives are rejected because the backend field is a `dict`.
 */
export function JsonField({ id, label, value, hint, rows = 6, onChange }: {
  id: string;
  label: string;
  value: unknown; // initial value from the API
  hint?: string;
  rows?: number;
  onChange: (value: unknown, valid: boolean) => void;
}) {
  const [text, setText] = useState(() => prettyJson(value));
  const [error, setError] = useState<string | null>(null);

  function handle(next: string) {
    setText(next);
    const result = parseJsonObject(next);
    setError(result.error);
    onChange(result.value, result.valid);
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        id={id}
        value={text}
        rows={rows}
        spellCheck={false}
        placeholder="{}"
        onChange={(e) => handle(e.target.value)}
        className={cn(
          "flex w-full rounded-md border bg-background px-3 py-2 font-mono text-xs shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2",
          error
            ? "border-destructive focus-visible:ring-destructive"
            : "border-input focus-visible:ring-ring",
        )}
      />
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
