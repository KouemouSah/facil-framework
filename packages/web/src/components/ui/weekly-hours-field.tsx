"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  DAYS, type Day, type DaySchedule, type OperatingHours, type Target, type Exception,
  normalize, applyQuickFill, copyDay, isValid, isRangeValid, rangesOverlap,
  sortExceptions, MAX_EXCEPTIONS,
} from "@/components/ui/weekly-hours";

const TARGETS: Target[] = ["weekdays", "weekend", "all"];
type Mode = "closed" | "h24" | "custom";
function modeOf(d: DaySchedule | undefined): Mode {
  if (!d || "closed" in d) return "closed";
  if ("h24" in d) return "h24";
  return "custom";
}
function daySchedule(mode: Mode, prev: DaySchedule | undefined, lastRanges?: string[]): DaySchedule {
  if (mode === "closed") return { closed: true };
  if (mode === "h24") return { h24: true };
  if (prev && "ranges" in prev && prev.ranges.length) return prev;
  if (lastRanges && lastRanges.length) return { ranges: lastRanges };
  return { ranges: ["09:00-17:00"] };
}
function splitRange(r: string) { const [from, to] = r.split("-"); return { from: from ?? "", to: to ?? "" }; }

/**
 * Bespoke control for `type: "json", widget: "weekly_hours"` (spec §12 —
 * motivated by `Site.operating_hours`). WEEKLY section: quick-fill bar,
 * per-day mode select (Closed/24h/Custom), and a ranges editor (overnight
 * allowed) with per-day "copy to…". EXCEPTIONS section: a date-sorted list
 * of overrides (Closed/24h/Custom + ranges) plus an "add exception" date
 * picker that dedups client-side and respects `MAX_EXCEPTIONS`.
 *
 * Value/onChange mirror `JsonField` (`(value, valid) => void`) so it drops
 * into `RecordForm`'s existing json-field state (`jsonValues`/`jsonOk`)
 * without any change to that plumbing. `valid` is the REAL result of
 * `isValid(next)` — a reversed/overlapping range, or a duplicate/invalid
 * exception date, flows into `jsonOk` and blocks save via
 * `RecordForm.validate()`, mirroring the backend validator (which remains
 * the authority — this is the UX mirror).
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
  // Per-day shadow of the last non-empty custom ranges, so switching a day to
  // Closed/24h and back to Custom restores what the user entered instead of
  // resetting to the hardcoded default. UI-only — never serialized via onChange.
  const [lastRanges, setLastRanges] = useState<Partial<Record<Day, string[]>>>(() => {
    const init: Partial<Record<Day, string[]>> = {};
    for (const day of DAYS) {
      const d = oh.weekly[day];
      if (d && "ranges" in d && d.ranges.length) init[day] = d.ranges;
    }
    return init;
  });
  // Same shadow mechanism as `lastRanges`, keyed by exception date instead of
  // weekday, so an exception's Custom→Closed→Custom toggle restores what the
  // user entered instead of resetting to the hardcoded default. UI-only.
  const [lastExcRanges, setLastExcRanges] = useState<Partial<Record<string, string[]>>>(() => {
    const init: Partial<Record<string, string[]>> = {};
    for (const ex of oh.exceptions) {
      if ("ranges" in ex && ex.ranges.length) init[ex.date] = ex.ranges;
    }
    return init;
  });
  const [qf, setQf] = useState({ from: "09:00", to: "17:00", target: "weekdays" as Target });
  const [excDupWarning, setExcDupWarning] = useState(false);

  function commit(next: OperatingHours) {
    setOh(next);
    setLastRanges((p) => {
      let changed = false; const upd = { ...p };
      for (const day of DAYS) {
        const d = next.weekly[day];
        if (d && "ranges" in d && d.ranges.length) { upd[day] = d.ranges; changed = true; }
      }
      return changed ? upd : p;
    });
    setLastExcRanges((p) => {
      let changed = false; const upd = { ...p };
      for (const ex of next.exceptions) {
        if ("ranges" in ex && ex.ranges.length) { upd[ex.date] = ex.ranges; changed = true; }
      }
      return changed ? upd : p;
    });
    onChange(next, isValid(next));
  }
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
        <input type="time" value={qf.from} disabled={disabled} aria-label={t("from")}
          onChange={(e) => setQf({ ...qf, from: e.target.value })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
        <span className="text-xs">{t("to")}</span>
        <input type="time" value={qf.to} disabled={disabled} aria-label={t("to")}
          onChange={(e) => setQf({ ...qf, to: e.target.value })}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
        <select value={qf.target} disabled={disabled} aria-label={t("quick_fill")}
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
                  aria-label={`${t(`day.${day}`)} — ${t("mode.label")}`}
                  onChange={(e) => setDay(day, daySchedule(e.target.value as Mode, d, lastRanges[day]))}
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
                        <input type="time" value={from} disabled={disabled} aria-label={t("from")}
                          onChange={(e) => setRange(day, idx, "from", e.target.value)}
                          className={cn("h-8 rounded-md border bg-background px-2 text-xs", bad ? "border-destructive" : "border-input")} />
                        <span className="text-xs text-muted-foreground">{t("to")}</span>
                        <input type="time" value={to} disabled={disabled} aria-label={t("to")}
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
                      <select disabled={disabled} defaultValue="" aria-label={t("copy_to")}
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

      {/* Exceptions */}
      <div className="space-y-2 rounded-md border p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("exceptions.title")}</p>
        {oh.exceptions.length === 0 && <p className="text-xs text-muted-foreground">{t("exceptions.none")}</p>}
        {sortExceptions(oh.exceptions).map((e: Exception) => {
          const mode = modeOf(e);
          const eranges = "ranges" in e ? e.ranges : [];
          const setException = (sched: DaySchedule) => {
            const next = oh.exceptions.map((x) => (x.date === e.date ? { date: e.date, ...sched } : x));
            commit({ ...oh, exceptions: next });
          };
          const addExcRange = () => setException({ ranges: [...eranges, "09:00-17:00"] });
          // Unlike the weekly `removeRange`, do NOT fall back to `{closed:true}`
          // when the last range is removed — keep the exception in Custom mode
          // with an empty ranges list so the row stays editable (add-range still
          // visible); `isValid`/backend flag an empty-ranges custom day as invalid,
          // which is the correct signal here (mirrors backend `_validate_day`).
          const removeExcRange = (idx: number) => setException({ ranges: eranges.filter((_, i) => i !== idx) });
          return (
            <div key={e.date} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono text-xs">{e.date}</span>
              <select value={mode} disabled={disabled}
                aria-label={`${e.date} — ${t("mode.label")}`}
                onChange={(ev) => setException(daySchedule(ev.target.value as Mode, e, lastExcRanges[e.date]))}
                className="h-7 rounded-md border border-input bg-background px-1 text-xs">
                <option value="closed">{t("mode.closed")}</option>
                <option value="h24">{t("mode.h24")}</option>
                <option value="custom">{t("mode.custom")}</option>
              </select>
              {mode === "custom" && eranges.map((r, idx) => {
                const { from, to } = splitRange(r);
                const bad = !isRangeValid(r) || eranges.some((o, i) => i !== idx && rangesOverlap(r, o));
                return (
                  <span key={idx} className="flex items-center gap-1">
                    <input type="time" value={from} disabled={disabled} aria-label={t("from")}
                      onChange={(ev) => {
                        const s = splitRange(r); const nr = [...eranges];
                        nr[idx] = `${ev.target.value || "00:00"}-${s.to || "00:00"}`;
                        setException({ ranges: nr });
                      }}
                      className={cn("h-7 rounded-md border bg-background px-1 text-xs", bad ? "border-destructive" : "border-input")} />
                    <span className="text-xs">{t("to")}</span>
                    <input type="time" value={to} disabled={disabled} aria-label={t("to")}
                      onChange={(ev) => {
                        const s = splitRange(r); const nr = [...eranges];
                        nr[idx] = `${s.from || "00:00"}-${ev.target.value || "00:00"}`;
                        setException({ ranges: nr });
                      }}
                      className={cn("h-7 rounded-md border bg-background px-1 text-xs", bad ? "border-destructive" : "border-input")} />
                    {!disabled && (
                      <Button type="button" variant="ghost" size="icon" className="size-6"
                        title={t("remove_shift")} onClick={() => removeExcRange(idx)}>
                        <Trash2 className="size-3.5" />
                      </Button>
                    )}
                  </span>
                );
              })}
              {mode === "custom" && !disabled && (
                <Button type="button" variant="ghost" size="sm" className="h-6 px-2 text-xs"
                  onClick={addExcRange}><Plus className="size-3.5" /> {t("add_shift")}</Button>
              )}
              {!disabled && (
                <Button type="button" variant="ghost" size="icon" className="size-6" title={t("remove_shift")}
                  onClick={() => { setExcDupWarning(false); commit({ ...oh, exceptions: oh.exceptions.filter((x) => x.date !== e.date) }); }}>
                  <Trash2 className="size-3.5" />
                </Button>
              )}
            </div>
          );
        })}
        {!disabled && oh.exceptions.length < MAX_EXCEPTIONS && (
          <div className="flex items-center gap-2">
            <label htmlFor={`${id}-exception-date`} className="text-xs text-muted-foreground">{t("exceptions.add")}</label>
            <input id={`${id}-exception-date`} type="date" aria-label={t("exceptions.date")}
              onChange={(ev) => {
                const dstr = ev.target.value;
                if (!dstr) return;
                if (oh.exceptions.some((x) => x.date === dstr)) { setExcDupWarning(true); ev.target.value = ""; return; }
                setExcDupWarning(false);
                commit({ ...oh, exceptions: [...oh.exceptions, { date: dstr, closed: true }] });
                ev.target.value = "";
              }}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs" />
            {excDupWarning && <span className="text-xs text-destructive" role="alert">{t("exceptions.duplicate")}</span>}
          </div>
        )}
      </div>

      <p className="text-xs text-muted-foreground">{t("tz_note")}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
