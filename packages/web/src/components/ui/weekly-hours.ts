export const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Day = (typeof DAYS)[number];
export type DaySchedule = { closed: true } | { h24: true } | { ranges: string[] };
export type Exception = { date: string } & DaySchedule;
export type OperatingHours = { weekly: Partial<Record<Day, DaySchedule>>; exceptions: Exception[] };
export type Target = "weekdays" | "weekend" | "all";

export const RANGE_RE = /^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$/;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
export const MAX_EXCEPTIONS = 366;

export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}
export function parseRange(r: string): { from: number; to: number } | null {
  if (!RANGE_RE.test(r)) return null;
  const [f, t] = r.split("-");
  return { from: toMinutes(f), to: toMinutes(t) };
}
export function isRangeValid(r: string): boolean {
  const p = parseRange(r);
  return p !== null && p.from !== p.to;
}
function coveredIntervals(r: string): [number, number][] {
  const p = parseRange(r);
  if (!p) return [];
  if (p.from === p.to) return []; // zero-length range covers no minutes → never overlaps
  return p.from < p.to ? [[p.from, p.to]] : [[p.from, 1440], [0, p.to]]; // overnight → two
}
export function rangesOverlap(a: string, b: string): boolean {
  const A = coveredIntervals(a), B = coveredIntervals(b);
  return A.some(([a0, a1]) => B.some(([b0, b1]) => a0 < b1 && b0 < a1));
}
export function isValidDay(d: DaySchedule): boolean {
  if ("closed" in d || "h24" in d) return true;
  if (!d.ranges.every(isRangeValid)) return false;
  for (let i = 0; i < d.ranges.length; i++)
    for (let j = i + 1; j < d.ranges.length; j++)
      if (rangesOverlap(d.ranges[i], d.ranges[j])) return false;
  return true;
}
export function isValidException(e: Exception, seen: Set<string>): boolean {
  if (!ISO_DATE_RE.test(e.date) || seen.has(e.date)) return false;
  const d = new Date(`${e.date}T00:00:00Z`);
  if (Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== e.date) return false;
  return isValidDay(e);
}
export function isValid(oh: OperatingHours): boolean {
  for (const day of DAYS) { const d = oh.weekly[day]; if (d && !isValidDay(d)) return false; }
  if (oh.exceptions.length > MAX_EXCEPTIONS) return false;
  const seen = new Set<string>();
  for (const e of oh.exceptions) { if (!isValidException(e, seen)) return false; seen.add(e.date); }
  return true;
}
export function targetDays(t: Target): Day[] {
  if (t === "weekdays") return ["mon", "tue", "wed", "thu", "fri"];
  if (t === "weekend") return ["sat", "sun"];
  return [...DAYS];
}
function normalizeDay(v: unknown): DaySchedule | null {
  if (Array.isArray(v)) {
    const rs = v.filter((x) => typeof x === "string") as string[];
    return rs.length ? { ranges: rs } : { closed: true };
  }
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    if (o.h24 === true) return { h24: true };
    if (o.closed === true) return { closed: true };
    if (Array.isArray(o.ranges)) return { ranges: o.ranges.filter((x) => typeof x === "string") as string[] };
  }
  return null;
}
export function normalize(v: unknown): OperatingHours {
  const empty: OperatingHours = { weekly: {}, exceptions: [] };
  if (v === null || typeof v !== "object" || Array.isArray(v)) return empty;
  const o = v as Record<string, unknown>;
  const weekly: Partial<Record<Day, DaySchedule>> = {};
  if ("weekly" in o || "exceptions" in o) {
    const w = (o.weekly ?? {}) as Record<string, unknown>;
    for (const day of DAYS) { const d = normalizeDay(w[day]); if (d) weekly[day] = d; }
    const exceptions: Exception[] = [];
    const ex = Array.isArray(o.exceptions) ? o.exceptions : [];
    for (const raw of ex) {
      if (raw && typeof raw === "object" && typeof (raw as Record<string, unknown>).date === "string") {
        const d = normalizeDay(raw) ?? { closed: true };
        exceptions.push({ date: (raw as { date: string }).date, ...d });
      }
    }
    return { weekly, exceptions };
  }
  for (const day of DAYS) { const d = normalizeDay(o[day]); if (d && !("closed" in d)) weekly[day] = d; }
  return { weekly, exceptions: [] };
}
function cloneDay(d: DaySchedule): DaySchedule {
  return "ranges" in d ? { ranges: [...d.ranges] } : { ...d };
}
export function applyQuickFill(oh: OperatingHours, from: string, to: string, target: Target): OperatingHours {
  const weekly = { ...oh.weekly };
  for (const day of targetDays(target)) weekly[day] = { ranges: [`${from}-${to}`] };
  return { ...oh, weekly };
}
export function copyDay(oh: OperatingHours, src: Day, target: Target): OperatingHours {
  const source = oh.weekly[src] ?? { closed: true as const };
  const weekly = { ...oh.weekly };
  for (const day of targetDays(target)) if (day !== src) weekly[day] = cloneDay(source);
  return { ...oh, weekly };
}
export function sortExceptions(list: Exception[]): Exception[] {
  return [...list].sort((a, b) => a.date.localeCompare(b.date));
}
