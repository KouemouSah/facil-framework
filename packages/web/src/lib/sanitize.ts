/**
 * Small pure string sanitizers used at trust boundaries (audit 7, 11).
 * No DOM — safe for the node test env and for server route handlers.
 */

// eslint-disable-next-line no-control-regex -- control chars are the target
const ILLEGAL_FILENAME = /[\x00-\x1f<>:"|?*]+/g;

/** Reduce a server-influenced filename to a safe base name: drop any path
 *  component (anti-traversal), replace control/illegal characters, bound length,
 *  and fall back when nothing usable remains. */
export function sanitizeFilename(name: string, fallback = "download"): string {
  const base = name.split(/[\\/]/).pop() ?? "";
  const cleaned = base.replace(ILLEGAL_FILENAME, "_").trim();
  return (cleaned || fallback).slice(0, 200);
}

/** Strip HTML tags and bound the length of a backend-supplied error message
 *  before it is shown, so a hostile/echoed `detail` can't inject markup. */
export function sanitizeErrorMessage(message: string, max = 300): string {
  return message.replace(/<[^>]*>/g, "").trim().slice(0, max);
}
