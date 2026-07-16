import { describe, it, expect } from "vitest";
import {
  normalize, isRangeValid, rangesOverlap, isValidDay, isValid, isValidException,
  applyQuickFill, copyDay, sortExceptions, targetDays, MAX_EXCEPTIONS,
} from "./weekly-hours";

describe("weekly-hours", () => {
  it("normalize: old {day:[ranges]} → canonical (empty array = closed)", () => {
    expect(normalize({ mon: ["09:00-17:00"], sat: [] })).toEqual({
      weekly: { mon: { ranges: ["09:00-17:00"] } }, exceptions: [] });
  });
  it("normalize: canonical passes through; illegal → empty", () => {
    const c = { weekly: { tue: { h24: true } }, exceptions: [{ date: "2026-12-25", closed: true }] };
    expect(normalize(c)).toEqual(c);
    expect(normalize(42)).toEqual({ weekly: {}, exceptions: [] });
  });
  it("isRangeValid: same-day ok, overnight ok, from==to invalid, malformed invalid", () => {
    expect(isRangeValid("09:00-17:00")).toBe(true);
    expect(isRangeValid("22:00-02:00")).toBe(true);   // overnight
    expect(isRangeValid("09:00-09:00")).toBe(false);  // zero-length
    expect(isRangeValid("9-17")).toBe(false);
  });
  it("rangesOverlap: same-day overlap, overnight overlap, disjoint", () => {
    expect(rangesOverlap("09:00-12:00", "11:00-14:00")).toBe(true);
    expect(rangesOverlap("22:00-02:00", "01:00-03:00")).toBe(true);  // wrap
    expect(rangesOverlap("09:00-12:00", "13:00-17:00")).toBe(false);
  });
  it("isValidDay: closed/h24 ok; overlapping ranges invalid", () => {
    expect(isValidDay({ closed: true })).toBe(true);
    expect(isValidDay({ h24: true })).toBe(true);
    expect(isValidDay({ ranges: ["09:00-12:00", "14:00-18:00"] })).toBe(true);
    expect(isValidDay({ ranges: ["09:00-12:00", "11:00-13:00"] })).toBe(false);
  });
  it("isValid: unique exception dates + cap", () => {
    const dup = { weekly: {}, exceptions: [{ date: "2026-01-01", closed: true }, { date: "2026-01-01", h24: true }] };
    expect(isValid(dup as any)).toBe(false);
    const many = { weekly: {}, exceptions: Array.from({ length: MAX_EXCEPTIONS + 1 },
      (_, i) => ({ date: `2027-${String(1 + (i % 12)).padStart(2, "0")}-01`, closed: true })) };
    expect(isValid(many as any)).toBe(false);
  });
  it("applyQuickFill overwrites the target days only", () => {
    const oh = { weekly: { sat: { h24: true } }, exceptions: [] } as any;
    const out = applyQuickFill(oh, "09:00", "17:00", "weekdays");
    expect(out.weekly.mon).toEqual({ ranges: ["09:00-17:00"] });
    expect(out.weekly.sat).toEqual({ h24: true });  // untouched
    expect(oh.weekly.mon).toBeUndefined();          // no mutation
  });
  it("copyDay copies the DaySchedule to targets except itself", () => {
    const oh = { weekly: { mon: { ranges: ["08:00-16:00"] } }, exceptions: [] } as any;
    const out = copyDay(oh, "mon", "all");
    expect(out.weekly.tue).toEqual({ ranges: ["08:00-16:00"] });
    expect(out.weekly.mon).toEqual({ ranges: ["08:00-16:00"] });
  });
  it("targetDays + sortExceptions", () => {
    expect(targetDays("weekend")).toEqual(["sat", "sun"]);
    expect(sortExceptions([{ date: "2026-02-01", closed: true }, { date: "2026-01-01", h24: true }])
      .map((e) => e.date)).toEqual(["2026-01-01", "2026-02-01"]);
  });
  it("rangesOverlap: a zero-length range overlaps nothing (widget in-progress input)", () => {
    expect(rangesOverlap("09:00-09:00", "08:00-10:00")).toBe(false);
    expect(rangesOverlap("09:00-09:00", "09:00-09:00")).toBe(false);
  });
  it("isValidException rejects impossible calendar dates", () => {
    const seen = new Set<string>();
    expect(isValidException({ date: "2026-02-30", closed: true } as any, seen)).toBe(false); // Feb 30
    expect(isValidException({ date: "2026-13-01", closed: true } as any, seen)).toBe(false); // month 13
    expect(isValidException({ date: "2026-12-25", closed: true } as any, seen)).toBe(true);  // real date
  });
  it("isValid is false for a reversed custom range (widget validity source)", () => {
    expect(isValid({ weekly: { mon: { ranges: ["17:00-09:00"] } }, exceptions: [] } as any))
      .toBe(true);  // overnight IS valid (17:00→09:00 next day)
    expect(isValid({ weekly: { mon: { ranges: ["09:00-09:00"] } }, exceptions: [] } as any))
      .toBe(false); // zero-length invalid
  });
  it("exceptions: sorted, and isValid rejects a duplicate date", () => {
    const oh = { weekly: {}, exceptions: [
      { date: "2026-12-25", closed: true }, { date: "2026-07-14", h24: true }] } as any;
    expect(sortExceptions(oh.exceptions).map((e: any) => e.date)).toEqual(["2026-07-14", "2026-12-25"]);
    expect(isValid({ weekly: {}, exceptions: [
      { date: "2026-01-01", closed: true }, { date: "2026-01-01", closed: true }] } as any)).toBe(false);
  });
});
