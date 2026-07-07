/**
 * Minimal RFC-4180-ish CSV parser (pure, no deps) for the bulk-import UI.
 * Handles quoted fields (commas/newlines inside quotes), escaped quotes (""),
 * and CRLF/CR/LF. The first non-empty row is the header; each data row becomes
 * an object keyed by the (trimmed) header — the shape the backend import expects.
 */
function parseRows(text: string): string[][] {
  const s = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inQuotes) {
      if (c === '"') {
        if (s[i + 1] === '"') { field += '"'; i++; } // escaped quote
        else inQuotes = false;
      } else field += c;
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field); field = "";
    } else if (c === "\n") {
      row.push(field); rows.push(row); row = []; field = "";
    } else {
      field += c;
    }
  }
  if (field !== "" || row.length > 0) { row.push(field); rows.push(row); }
  return rows;
}

/** Bulk-import row ceiling (audit 6, anti-DoS). Reference imports are small
 *  (hundreds of rows); a file beyond this bounds the emitted rows / POST size. */
export const MAX_IMPORT_ROWS = 10_000;

export function parseCsv(text: string, opts?: { maxRows?: number }): Record<string, string>[] {
  const rows = parseRows(text).filter((r) => r.some((c) => c.trim() !== ""));
  if (rows.length === 0) return [];
  const cap = opts?.maxRows ?? MAX_IMPORT_ROWS;
  if (rows.length - 1 > cap) {
    throw new Error(`CSV has too many rows (max ${cap})`);
  }
  const header = rows[0].map((h) => h.trim());
  // Values are stored verbatim (fidelity): CSV formula-injection (CWE-1236) is an
  // export-time threat, neutralized on the way OUT by the backend csv_export._cell
  // — mutating on import would corrupt legit values like "+240…" phone numbers.
  return rows.slice(1).map((r) =>
    Object.fromEntries(header.map((h, i) => [h, (r[i] ?? "").trim()])));
}
