"use client";

import { useState } from "react";
import { ArrowUp, ArrowDown, ChevronsUpDown, Rows2, Rows3 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

/**
 * Generic server-side data grid (Lot 1 / L1.2) — the reusable list surface for
 * every admin table. Sorting/filtering/pagination are SERVER-side: the grid is
 * controlled (parent owns sort/filters/page state and refetches). It renders the
 * list contract `{items,total}` with a sticky header, density toggle, optional
 * per-row selection (compat with bulk actions), and empty/loading/error states.
 */
export interface DataGridColumn<T> {
  key: string;
  header: string;
  sortable?: boolean; // header click toggles sort on this key
  filter?: { type: "text" | "select"; options?: { value: string; label: string }[]; placeholder?: string };
  cell?: (row: T) => React.ReactNode; // custom cell; default = String(row[key])
  className?: string;
  headClassName?: string;
  align?: "right";
  stopClick?: boolean; // interactive cell (actions/inline edit) — don't trigger onRowClick
}

export interface DataGridSelection {
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  allOnPage: boolean;
}

export interface DataGridProps<T> {
  columns: DataGridColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  pageSize: number;
  sort: string; // "field" asc / "-field" desc
  onSortChange: (sort: string) => void;
  filters: Record<string, string>;
  onFilterChange: (key: string, value: string) => void;
  isLoading?: boolean;
  error?: boolean;
  selection?: DataGridSelection;
  onRowClick?: (row: T) => void; // open a master-detail panel
  selectedId?: string;           // highlight the active row
  emptyLabel?: string;
  onPageSizeChange?: (size: number) => void; // opt-in: show a rows-per-page selector
  pageSizeOptions?: number[];                // default [20, 50, 100, 200] (≤ backend cap)

  // Pagination mode. "offset" (default): page index + total, "X–Y of N" footer.
  // "cursor" (scale 1M+): forward keyset Prev/Next + capped "N+" count — no total
  // position is known, so the footer shows results count and Prev/Next only.
  mode?: "offset" | "cursor";
  // offset mode:
  total?: number;
  page?: number;
  onPageChange?: (page: number) => void;
  // cursor mode:
  hasPrev?: boolean;
  hasNext?: boolean;
  onPrev?: () => void;
  onNext?: () => void;
  count?: number;
  capped?: boolean;
}

// Backend caps list `limit` at 200 (app.api.list_query.MAX_LIMIT) — keep the
// largest option in step so the grid never asks for more than the server allows.
const DEFAULT_PAGE_SIZES = [20, 50, 100, 200];

export function DataGrid<T>({
  columns, rows, rowKey, pageSize,
  sort, onSortChange, filters, onFilterChange, isLoading, error,
  selection, onRowClick, selectedId, emptyLabel = "No data.",
  onPageSizeChange, pageSizeOptions = DEFAULT_PAGE_SIZES,
  mode = "offset", total = 0, page = 0, onPageChange,
  hasPrev = false, hasNext = false, onPrev, onNext, count = 0, capped = false,
}: DataGridProps<T>) {
  const [dense, setDense] = useState(false);
  const span = columns.length + (selection ? 1 : 0);
  const hasFilters = columns.some((c) => c.filter);

  function nextSort(key: string): string {
    if (sort === key) return `-${key}`;        // asc -> desc
    if (sort === `-${key}`) return key;          // desc -> asc
    return key;                                  // unsorted -> asc
  }
  function sortIcon(key: string) {
    if (sort === key) return <ArrowUp className="size-3" />;
    if (sort === `-${key}`) return <ArrowDown className="size-3" />;
    return <ChevronsUpDown className="size-3 opacity-40" />;
  }

  const from = total === 0 ? 0 : page * pageSize + 1;
  const to = Math.min((page + 1) * pageSize, total);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="min-h-0 flex-1 overflow-auto rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-card">
            <TableRow>
              {selection && (
                <TableHead className="w-10">
                  <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
                    aria-label="Select all on page" checked={selection.allOnPage}
                    onChange={selection.onToggleAll} />
                </TableHead>
              )}
              {columns.map((c) => (
                <TableHead key={c.key} className={cn(c.align === "right" && "text-right", c.headClassName)}>
                  {c.sortable ? (
                    <button type="button"
                      className="inline-flex items-center gap-1 font-medium hover:text-foreground"
                      onClick={() => onSortChange(nextSort(c.key))}>
                      {c.header} {sortIcon(c.key)}
                    </button>
                  ) : c.header}
                </TableHead>
              ))}
            </TableRow>
            {hasFilters && (
              <TableRow className="hover:bg-transparent">
                {selection && <TableHead className="w-10" />}
                {columns.map((c) => (
                  <TableHead key={c.key} className="py-1">
                    {c.filter?.type === "text" && (
                      <Input className="h-7 text-xs" placeholder={c.filter.placeholder || "Filter…"}
                        value={filters[c.key] ?? ""} onChange={(e) => onFilterChange(c.key, e.target.value)} />
                    )}
                    {c.filter?.type === "select" && (
                      <Select className="h-7 text-xs" value={filters[c.key] ?? ""}
                        onChange={(e) => onFilterChange(c.key, e.target.value)}>
                        <option value="">All</option>
                        {c.filter.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </Select>
                    )}
                  </TableHead>
                ))}
              </TableRow>
            )}
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={span} className="py-8 text-center text-muted-foreground">Loading…</TableCell></TableRow>
            )}
            {error && !isLoading && (
              <TableRow><TableCell colSpan={span} className="py-8 text-center text-destructive">Failed to load.</TableCell></TableRow>
            )}
            {!isLoading && !error && rows.length === 0 && (
              <TableRow><TableCell colSpan={span} className="py-8 text-center text-muted-foreground">{emptyLabel}</TableCell></TableRow>
            )}
            {!isLoading && !error && rows.map((row) => {
              const id = rowKey(row);
              const active = selectedId === id;
              return (
                <TableRow key={id}
                  className={cn(dense && "[&_td]:py-1", onRowClick && "cursor-pointer",
                    active && "bg-primary/10 hover:bg-primary/10")}
                  data-state={selection?.selected.has(id) ? "selected" : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}>
                  {selection && (
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" className="size-4 accent-[hsl(var(--primary))]"
                        aria-label={`Select row ${id}`} checked={selection.selected.has(id)}
                        onChange={() => selection.onToggle(id)} />
                    </TableCell>
                  )}
                  {columns.map((c) => (
                    <TableCell key={c.key}
                      className={cn(c.align === "right" && "text-right", c.className)}
                      onClick={c.stopClick ? (e) => e.stopPropagation() : undefined}>
                      {c.cell ? c.cell(row) : String((row as Record<string, unknown>)[c.key] ?? "")}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Footer — density + server pagination with total */}
      <div className="flex items-center gap-2 text-sm">
        <Button variant="outline" size="icon" title="Density" onClick={() => setDense((d) => !d)}>
          {dense ? <Rows3 className="size-4" /> : <Rows2 className="size-4" />}
        </Button>
        {onPageSizeChange && (
          <Select aria-label="Rows per page" className="h-8 w-auto text-xs"
            value={String(pageSize)} onChange={(e) => onPageSizeChange(Number(e.target.value))}>
            {pageSizeOptions.map((n) => <option key={n} value={n}>{n} / page</option>)}
          </Select>
        )}
        {mode === "cursor" ? (
          <>
            <span className="ml-auto text-muted-foreground">{capped ? `${count}+` : count} results</span>
            <Button variant="outline" size="sm" disabled={!hasPrev} onClick={onPrev}>Prev</Button>
            <Button variant="outline" size="sm" disabled={!hasNext} onClick={onNext}>Next</Button>
          </>
        ) : (
          <>
            <span className="ml-auto text-muted-foreground">{from}–{to} of {total}</span>
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => onPageChange?.(page - 1)}>Prev</Button>
            <Button variant="outline" size="sm" disabled={(page + 1) * pageSize >= total} onClick={() => onPageChange?.(page + 1)}>Next</Button>
          </>
        )}
      </div>
    </div>
  );
}
