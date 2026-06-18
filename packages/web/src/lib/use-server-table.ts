"use client";

import { useCallback, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  hasPrev as stackHasPrev, initialPageStack, popPage, pushPage,
} from "@/lib/cursor-stack";

/**
 * Generic server-side table state (scale 1M+ P3) — owns sort / column filters /
 * search / page-size and the keyset cursor stack, and runs the fetch. It removes
 * the per-page duplication of `useState` + `useQuery` + URL building across the
 * admin lists: a page supplies only `fetchPage` (resource-specific URL) and gets
 * back the props the DataGrid (cursor mode) and SavedViews need.
 *
 * Resource-specific concerns (bulk selection, an org gate, the export path) stay
 * in the page — the hook deliberately knows nothing about them.
 *
 * Invariant: any change to sort / filters / search / page-size resets the cursor
 * stack — a keyset cursor is only valid for the exact query it was computed for.
 */
export interface ServerPage<T> {
  items: T[];
  next_cursor: string | null;
  count: number;
  capped: boolean;
}

export interface ServerTableFetchParams {
  cursor: string | null;
  limit: number;
  sort: string;
  filters: Record<string, string>;
  q: string;
}

export interface ServerTableSavedConfig {
  q: string;
  sort: string;
  filters: Record<string, string>;
  // Index signature so this is assignable to SavedViews' `Record<string, unknown>`
  // config prop while keeping the named fields documented.
  [key: string]: unknown;
}

export interface UseServerTableArgs<T> {
  /** Cache namespace + SavedViews resource key. */
  resource: string;
  /** Resource-specific page fetcher (builds the URL, calls apiFetch). */
  fetchPage: (p: ServerTableFetchParams) => Promise<ServerPage<T>>;
  defaultSort: string;
  defaultPageSize?: number;
  initialFilters?: Record<string, string>;
  /** Gate the fetch (e.g. wait for an org to be selected). Default true. */
  enabled?: boolean;
}

export interface UseServerTable<T> {
  rows: T[];
  sort: string;
  onSortChange: (sort: string) => void;
  filters: Record<string, string>;
  onFilterChange: (key: string, value: string) => void;
  pageSize: number;
  onPageSizeChange: (size: number) => void;
  q: string;
  setQ: (q: string) => void;
  hasPrev: boolean;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  count: number;
  capped: boolean;
  isLoading: boolean;
  error: boolean;
  /** Re-run the current page query (after a create/delete mutation). */
  refetch: () => void;
  /** Feed to SavedViews `config` (what to persist) — only query shape, never paging. */
  savedViewConfig: ServerTableSavedConfig;
  /** SavedViews `onApply` — restore a preset and reset paging. */
  applySavedView: (config: Record<string, unknown>) => void;
}

export function useServerTable<T>({
  resource, fetchPage, defaultSort, defaultPageSize = 20, initialFilters = {},
  enabled = true,
}: UseServerTableArgs<T>): UseServerTable<T> {
  const [q, setQState] = useState("");
  const [sort, setSortState] = useState(defaultSort);
  const [filters, setFilters] = useState<Record<string, string>>(initialFilters);
  const [pageSize, setPageSizeState] = useState(defaultPageSize);
  const [paging, setPaging] = useState(initialPageStack);

  const resetPaging = useCallback(() => setPaging(initialPageStack), []);

  // Every query-shape change resets the cursor stack (the invariant).
  const setQ = useCallback((v: string) => { setQState(v); resetPaging(); }, [resetPaging]);
  const onSortChange = useCallback((s: string) => { setSortState(s); resetPaging(); }, [resetPaging]);
  const onFilterChange = useCallback((k: string, v: string) => {
    setFilters((prev) => ({ ...prev, [k]: v }));
    resetPaging();
  }, [resetPaging]);
  const onPageSizeChange = useCallback((n: number) => { setPageSizeState(n); resetPaging(); }, [resetPaging]);

  const query = useQuery({
    queryKey: [resource, q, sort, filters, pageSize, paging.cursor],
    queryFn: () => fetchPage({ cursor: paging.cursor, limit: pageSize, sort, filters, q }),
    enabled,
    // Keep the current page visible while the next/prev one loads (no empty flash).
    placeholderData: keepPreviousData,
  });
  const data = query.data;
  const nextCursor = data?.next_cursor ?? null;

  const onNext = useCallback(() => {
    if (nextCursor) setPaging((p) => pushPage(p, nextCursor));
  }, [nextCursor]);
  const onPrev = useCallback(() => setPaging(popPage), []);

  const savedViewConfig = useMemo<ServerTableSavedConfig>(
    () => ({ q, sort, filters }), [q, sort, filters]);
  const applySavedView = useCallback((c: Record<string, unknown>) => {
    setQState(typeof c.q === "string" ? c.q : "");
    setSortState(typeof c.sort === "string" ? c.sort : defaultSort);
    setFilters(c.filters && typeof c.filters === "object"
      ? (c.filters as Record<string, string>) : {});
    resetPaging();
  }, [defaultSort, resetPaging]);

  return {
    rows: data?.items ?? [],
    sort, onSortChange, filters, onFilterChange, pageSize, onPageSizeChange,
    q, setQ,
    hasPrev: stackHasPrev(paging), hasNext: !!nextCursor, onPrev, onNext,
    count: data?.count ?? 0, capped: data?.capped ?? false,
    isLoading: query.isLoading, error: !!query.error,
    refetch: () => { void query.refetch(); },
    savedViewConfig, applySavedView,
  };
}
