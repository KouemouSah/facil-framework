/** Mirror of app/core/schema/conditions.py. The SERVER is authoritative — this
 *  half only avoids showing the user a field that would be rejected anyway. */

import type { Condition, FieldSpec } from "./types";

function matches(rule: Condition | undefined, values: Record<string, unknown>): boolean {
  if (!rule) return true;
  const actual = values[rule.field];
  switch (rule.op) {
    case "eq": return actual === rule.value;
    case "ne": return actual !== rule.value;
    case "in": return Array.isArray(rule.value) && rule.value.includes(actual);
    default: return true;
  }
}

export function isVisible(spec: FieldSpec, values: Record<string, unknown>): boolean {
  return matches(spec.rules?.visible_if, values);
}

export function isRequired(spec: FieldSpec, values: Record<string, unknown>): boolean {
  if (!isVisible(spec, values)) return false;   // invisible ⇒ never required
  if (spec.required) return true;
  return spec.rules?.required_if ? matches(spec.rules.required_if, values) : false;
}
