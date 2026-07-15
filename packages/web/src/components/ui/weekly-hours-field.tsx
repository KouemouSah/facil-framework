"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
type Day = (typeof DAYS)[number];
type WeeklyHours = Partial<Record<Day, string[]>>;

const RANGE_RE = /^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$/;

function isWeeklyHours(v: unknown): v is WeeklyHours {
  if (v === null || typeof v !== "object" || Array.isArray(v)) return false;
  return Object.entries(v as Record<string, unknown>).every(
    ([k, ranges]) => (DAYS as readonly string[]).includes(k) && Array.isArray(ranges)
      && ranges.every((r) => typeof r === "string"));
}

function normalize(v: unknown): WeeklyHours {
  return isWeeklyHours(v) ? v : {};
}

function splitRange(r: string): { from: string; to: string } {
  const [from, to] = r.split("-");
  return { from: from ?? "", to: to ?? "" };
}

/**
 * Bespoke control for `type: "json", widget: "weekly_hours"` (spec §12 —
 * motivated by `Site.operating_hours`, whose free-form JSON shape
 * `{"mon": ["09:00-17:00"], "sat": []}` a raw `JsonField` textarea makes
 * error-prone to hand-type). One row per day: an "open" toggle plus zero or
 * more `HH:MM-HH:MM` shift ranges, editable as two time inputs each.
 *
 * Value/onChange mirror `JsonField` exactly (`(value, valid) => void`) so it
 * drops into `RecordForm`'s existing json-field state (`jsonValues`/
 * `jsonOk`) without any change to that plumbing — only the CONTROL differs.
 * `valid` is always `true`: every edit here already produces a well-formed
 * `{day: ["HH:MM-HH:MM", ...]}` object (times come from native <input
 * type="time"> pickers), so there is no free-text parse step that can fail.
 */
export function WeeklyHoursField({ id, label, value, hint, disabled, onChange }: {
  id: string;
  label: string;
  value: unknown;
  hint?: string;
  disabled?: boolean;
  onChange: (value: unknown, valid: boolean) => void;
}) {
  const t = useTranslations("weekly_hours");
  const [hours, setHours] = useState<WeeklyHours>(() => normalize(value));

  function commit(next: WeeklyHours) {
    setHours(next);
    onChange(next, true);
  }

  function toggleDay(day: Day, open: boolean) {
    const next = { ...hours };
    if (open) next[day] = next[day]?.length ? next[day] : ["09:00-17:00"];
    else delete next[day];
    commit(next);
  }

  function addShift(day: Day) {
    commit({ ...hours, [day]: [...(hours[day] ?? []), "09:00-17:00"] });
  }

  function removeShift(day: Day, idx: number) {
    const ranges = (hours[day] ?? []).filter((_, i) => i !== idx);
    const next = { ...hours };
    if (ranges.length) next[day] = ranges;
    else delete next[day];
    commit(next);
  }

  function setShift(day: Day, idx: number, part: "from" | "to", v: string) {
    const ranges = [...(hours[day] ?? [])];
    const cur = splitRange(ranges[idx] ?? "");
    const merged = { ...cur, [part]: v };
    ranges[idx] = `${merged.from || "00:00"}-${merged.to || "00:00"}`;
    commit({ ...hours, [day]: ranges });
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="space-y-2 rounded-md border p-3">
        {DAYS.map((day) => {
          const ranges = hours[day] ?? [];
          const open = day in hours;
          return (
            <div key={day} className="grid grid-cols-[7rem_1fr] items-start gap-2 text-sm">
              <label className="flex items-center gap-2 pt-1.5">
                <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
                  checked={open} disabled={disabled}
                  onChange={(e) => toggleDay(day, e.target.checked)} />
                {t(`day.${day}`)}
              </label>
              <div className="space-y-1.5">
                {!open && <p className="pt-1.5 text-xs text-muted-foreground">{t("closed")}</p>}
                {ranges.map((r, idx) => {
                  const { from, to } = splitRange(r);
                  const valid = RANGE_RE.test(r);
                  return (
                    <div key={idx} className="flex items-center gap-1.5">
                      <span className="sr-only">{t("from")}</span>
                      <input type="time" value={from} disabled={disabled}
                        onChange={(e) => setShift(day, idx, "from", e.target.value)}
                        className={cn("h-8 rounded-md border bg-background px-2 text-xs shadow-sm",
                          valid ? "border-input" : "border-destructive")} />
                      <span className="text-xs text-muted-foreground">{t("to")}</span>
                      <input type="time" value={to} disabled={disabled}
                        onChange={(e) => setShift(day, idx, "to", e.target.value)}
                        className={cn("h-8 rounded-md border bg-background px-2 text-xs shadow-sm",
                          valid ? "border-input" : "border-destructive")} />
                      {!disabled && (
                        <Button type="button" variant="ghost" size="icon" className="size-7"
                          title={t("remove_shift")} onClick={() => removeShift(day, idx)}>
                          <Trash2 className="size-3.5" />
                        </Button>
                      )}
                    </div>
                  );
                })}
                {open && !disabled && (
                  <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs"
                    onClick={() => addShift(day)}>
                    <Plus className="size-3.5" /> {t("add_shift")}
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
