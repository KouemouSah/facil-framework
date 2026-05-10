/**
 * Centralized Export Utilities — CSV & Excel
 *
 * Uses the `xlsx` package (already in deps) for both formats.
 * BOM prefix for CSV ensures Excel opens UTF-8 correctly.
 *
 * @module core/utils/export
 */

import * as XLSX from 'xlsx';

interface ExportOptions {
  /** File name without extension */
  fileName: string;
  /** Sheet name for Excel (max 31 chars, auto-trimmed) */
  sheetName?: string;
}

/**
 * Export an array of objects as CSV with BOM for Excel UTF-8 compatibility.
 */
export function exportToCsv<T extends Record<string, unknown>>(
  data: T[],
  options: ExportOptions
): void {
  if (data.length === 0) return;

  const ws = XLSX.utils.json_to_sheet(data);
  const csv = XLSX.utils.sheet_to_csv(ws);
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  downloadBlob(blob, `${options.fileName}.csv`);
}

/**
 * Export an array of objects as XLSX with auto-width columns.
 */
export function exportToExcel<T extends Record<string, unknown>>(
  data: T[],
  options: ExportOptions
): void {
  if (data.length === 0) return;

  const ws = XLSX.utils.json_to_sheet(data);

  // Auto-width columns
  const keys = Object.keys(data[0]);
  ws['!cols'] = keys.map(key => ({
    wch: Math.max(
      key.length,
      ...data.map(row => String(row[key] ?? '').length)
    ) + 2,
  }));

  const wb = XLSX.utils.book_new();
  const sheetName = (options.sheetName || options.fileName).slice(0, 31);
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  XLSX.writeFile(wb, `${options.fileName}.xlsx`);
}

/** Internal: trigger download from Blob */
function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
