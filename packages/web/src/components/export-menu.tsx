"use client";

import { useEffect, useRef, useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { downloadFile } from "@/lib/download";

/**
 * Export control offering CSV or Excel (.xlsx). Both hit the same backend
 * endpoint with `?format=`; the backend dispatches (app.api.csv_export). Uses
 * the lightweight zero-dep popover pattern (like OrgCombobox) — no menu lib.
 *
 * `path` is the export URL WITHOUT the format param (may already carry filters);
 * `filename` is the base name (extension is appended per format).
 */
export function ExportMenu({ path, filename, disabled }: {
  path: string;
  filename: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const sep = path.includes("?") ? "&" : "?";
  function go(fmt: "csv" | "xlsx") {
    setOpen(false);
    downloadFile(`${path}${sep}format=${fmt}`, `${filename}.${fmt}`);
  }

  return (
    <div className="relative" ref={ref}>
      <Button variant="outline" size="sm" title="Export" disabled={disabled}
        onClick={() => setOpen((o) => !o)}>
        <Download className="size-4" /> Export
      </Button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-36 rounded-md border bg-card p-1 shadow-md">
          <button type="button" onClick={() => go("csv")}
            className="block w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent">CSV</button>
          <button type="button" onClick={() => go("xlsx")}
            className="block w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent">Excel (.xlsx)</button>
        </div>
      )}
    </div>
  );
}
