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

export function parseCsv(text: string): Record<string, string>[] {
  const rows = parseRows(text).filter((r) => r.some((c) => c.trim() !== ""));
  if (rows.length === 0) return [];
  const header = rows[0].map((h) => h.trim());
  return rows.slice(1).map((r) =>
    Object.fromEntries(header.map((h, i) => [h, (r[i] ?? "").trim()])));
}
