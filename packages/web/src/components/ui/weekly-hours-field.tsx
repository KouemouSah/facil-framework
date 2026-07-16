"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  DAYS, type Day, type DaySchedule, type OperatingHours, type Target,
  normalize, applyQuickFill, copyDay, isValid, isRangeValid, rangesOverlap,
} from "@/components/ui/weekly-hours";

const TARGETS: Target[] = ["weekdays", "weekend", "all"];
type Mode = "closed" | "h24" | "custom";
function modeOf(d: DaySchedule | undefined): Mode {
  if (!d || "closed" in d) return "closed";
  if ("h24" in d) return "h24";
  return "custom";
}
function daySchedule(mode: Mode, prev: DaySchedule | undefined): DaySchedule {
  if (mode === "closed") return { closed: true };
  if (mode === "h24") return { h24: true };
  return prev && "ranges" in prev && prev.ranges.length ? prev : { ranges: ["09:00-17:00"] };
}
function splitRange(r: string) { const [from, to] = r.split("-"); return { from: from ?? "", to: to ?? "" }; }

/**
 * Bespoke control for `type: "json", widget: "weekly_hours"` (spec §12 —
 * motivated by `Site.operating_hours`). WEEKLY section: quick-fill bar,
 * per-day mode select (Closed/24h/Custom), and a ranges editor (overnight
 * allowed) with per-day "copy to…". The EXCEPTIONS section is added on top
 * of this in a follow-up task; this component owns the weekly grid only.
 *
 * Value/onChange mirror `JsonField` (`(value, valid) => void`) so it drops
 * into `RecordForm`'s existing json-field state (`jsonValues`/`jsonOk`)
 * without any change to that plumbing. Unlike the previous version, `valid`
 * is the REAL result of `isValid(next)` — a reversed/overlapping range (or,
 * once exceptions land, a duplicate/invalid exception date) now flows into
 * `jsonOk` and blocks save via `RecordForm.validate()`, mirroring the
 * backend validator (which remains the authority — this is the UX mirror).
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
  const [oh, setOh] = useState<OperatingHours>(() => normalize(value));
  const [qf, setQf] = useState({ from: "09:00", to: "17:00", target: "weekdays" as Target });

  function commit(next: OperatingHours) { setOh(next); onChange(next, isValid(next)); }
  function setDay(day: Day, d: DaySchedule) { commit({ ...oh, weekly: { ...oh.weekly, [day]: d } }); }
  function setRange(day: Day, idx: number, part: "from" | "to", v: string) {
    const cur = oh.weekly[day]; if (!cur || !("ranges" in cur)) return;
    const ranges = [...cur.ranges];
    const s = splitRange(ranges[idx] ?? ""); const m = { ...s, [part]: v };
    ranges[idx] = `${m.from || "00:00"}-${m.to || "00:00"}`;
    setDay(day, { ranges });
  }
  function addRange(day: Day) {
    const cur = oh.weekly[day]; const ranges = cur && "ranges" in cur ? cur.ranges : [];
    setDay(day, { ranges: [...ranges, "09:00-17:00"] });
  }
  function removeRange(day: Day, idx: number) {
    const cur = oh.weekly[day]; if (!cur || !("ranges" in cur)) return;
    const ranges = cur.ranges.filter((_, i) => i !== idx);
    setDay(day, ranges.length ? { ranges } : { closed: true });
  }

  return (
    <div className="space-y-3">
      <Label htmlFor={id}>{label}</Label>

      {/* Quick fill */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-2 text-sm">
        <span className="text-xs font-medium text-muted-foreground">{t("quick_fill")}</span>
        <input type="time" value={qf.from} disabled={disabled}
          onChange={(e) => setQf({ ...qf, from: e.target.value })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
        <span className="text-xs">{t("to")}</span>
        <input type="time" value={qf.to} disabled={disabled}
          onChange={(e) => setQf({ ...qf, to: e.target.value })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
        <select value={qf.target} disabled={disabled}
          onChange={(e) => setQf({ ...qf, target: e.target.value as Target })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs">
          {TARGETS.map((tg) => <option key={tg} value={tg}>{t(`target.${tg}`)}</option>)}
        </select>
        <Button type="button" size="sm" className="h-8" disabled={disabled}
          onClick={() => commit(applyQuickFill(oh, qf.from, qf.to, qf.target))}>{t("apply")}</Button>
      </div>

      {/* Weekly grid: 2 columns on lg, stacked on narrow */}
      <div className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-md border p-3 lg:grid-cols-2">
        {DAYS.map((day) => {
          const d = oh.weekly[day]; const mode = modeOf(d);
          const ranges = d && "ranges" in d ? d.ranges : [];
          return (
            <div key={day} className="grid grid-cols-[6rem_1fr] items-start gap-2 text-sm">
              <div className="flex flex-col gap-1 pt-1">
                <span className="font-medium">{t(`day.${day}`)}</span>
                <select value={mode} disabled={disabled}
                  onChange={(e) => setDay(day, daySchedule(e.target.value as Mode, d))}
                  className="h-7 rounded-md border border-input bg-background px-1 text-xs">
                  <option value="closed">{t("mode.closed")}</option>
                  <option value="h24">{t("mode.h24")}</option>
                  <option value="custom">{t("mode.custom")}</option>
                </select>
              </div>
              <div className="space-y-1.5">
                {mode === "closed" && <p className="pt-1.5 text-xs text-muted-foreground">{t("mode.closed")}</p>}
                {mode === "h24" && <p className="pt-1.5 text-xs text-muted-foreground">{t("mode.h24")}</p>}
                {mode === "custom" && (<>
                  {ranges.map((r, idx) => {
                    const { from, to } = splitRange(r);
                    const bad = !isRangeValid(r) || ranges.some((o, i) => i !== idx && rangesOverlap(r, o));
                    return (
                      <div key={idx} className="flex items-center gap-1.5">
                        <input type="time" value={from} disabled={disabled}
                          onChange={(e) => setRange(day, idx, "from", e.target.value)}
                          className={cn("h-8 rounded-md border bg-background px-2 text-xs", bad ? "border-destructive" : "border-input")} />
                        <span className="text-xs text-muted-foreground">{t("to")}</span>
                        <input type="time" value={to} disabled={disabled}
                          onChange={(e) => setRange(day, idx, "to", e.target.value)}
                          className={cn("h-8 rounded-md border bg-background px-2 text-xs", bad ? "border-destructive" : "border-input")} />
                        {!disabled && (
                          <Button type="button" variant="ghost" size="icon" className="size-7"
                            title={t("remove_shift")} onClick={() => removeRange(day, idx)}>
                            <Trash2 className="size-3.5" />
                          </Button>
                        )}
                      </div>
                    );
                  })}
                  {!disabled && (
                    <div className="flex items-center gap-2">
                      <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs"
                        onClick={() => addRange(day)}><Plus className="size-3.5" /> {t("add_shift")}</Button>
                      <select disabled={disabled} defaultValue=""
                        onChange={(e) => { if (e.target.value) { commit(copyDay(oh, day, e.target.value as Target)); e.target.value = ""; } }}
                        className="h-7 rounded-md border border-input bg-background px-1 text-xs text-muted-foreground">
                        <option value="">{t("copy_to")}</option>
                        {TARGETS.map((tg) => <option key={tg} value={tg}>{t(`target.${tg}`)}</option>)}
                      </select>
                    </div>
                  )}
                </>)}
              </div>
            </div>
          );
        })}
      </div>

      {/* EXCEPTIONS section is added in Task 4, here. */}

      <p className="text-xs text-muted-foreground">{t("tz_note")}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
