/** Compile declarative `rules` into a zod validator.
 *
 *  A DB-defined field can never carry a zod OBJECT (not serialisable), so the
 *  descriptor carries declarative rules and the client compiles them here.
 *  RecordForm keeps values as strings, so the rules apply to the string form. */

import { z } from "zod";
import type { FieldSpec } from "./types";

export function rulesToZod(spec: FieldSpec): z.ZodTypeAny {
  const r = spec.rules ?? {};
  const label = spec.key;

  if (spec.type === "number" || spec.type === "decimal") {
    let s: z.ZodTypeAny = z
      .string()
      .refine((v) => v === "" || !Number.isNaN(Number(v)), `${label} must be a number`);
    if (r.min !== undefined)
      s = s.refine((v) => v === "" || Number(v) >= Number(r.min), `${label} must be ≥ ${r.min}`);
    if (r.max !== undefined)
      s = s.refine((v) => v === "" || Number(v) <= Number(r.max), `${label} must be ≤ ${r.max}`);
    if (r.step !== undefined)
      s = s.refine((v) => v === "" || Number(v) % r.step! === 0, `${label} must be a multiple of ${r.step}`);
    if (r.precision !== undefined)
      s = s.refine((v) => v === "" || (v.split(".")[1]?.length ?? 0) <= r.precision!,
        `${label}: at most ${r.precision} decimal places`);
    if (spec.required)
      s = s.refine((v) => v !== "", `${label} is required`);
    return s;
  }

  if (spec.type === "date" || spec.type === "datetime" || spec.type === "time") {
    const resolve = (b: number | string): string =>
      b === "today" ? new Date().toISOString().slice(0, 10)
        : b === "now" ? new Date().toISOString().slice(0, 19)
        : String(b);
    let d: z.ZodTypeAny = z.string();
    if (r.min !== undefined)
      d = d.refine((v) => v === "" || v >= resolve(r.min!), `${label} must be ≥ ${r.min}`);
    if (r.max !== undefined)
      d = d.refine((v) => v === "" || v <= resolve(r.max!), `${label} must be ≤ ${r.max}`);
    if (spec.required) d = d.refine((v) => v !== "", `${label} is required`);
    return d;
  }

  let s = z.string();
  if (r.min_length !== undefined) s = s.min(r.min_length, `${label}: too short`);
  if (r.max_length !== undefined) s = s.max(r.max_length, `${label}: too long`);
  if (r.pattern) s = s.regex(new RegExp(r.pattern), `${label}: invalid format`);
  if (spec.required) return s.trim().min(1, `${label} is required`);
  return s.optional().or(z.literal(""));
}
