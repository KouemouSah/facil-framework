'use client';

/**
 * ArtifactRenderer — Typed artifact display components for any agent.
 *
 * Renders structured data (KPI grids, tables, summaries) from SQL tool results.
 * Moved from treasury-specific to shared agent-chat so all agents reuse it.
 */

import { useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { ArrowDown, ArrowUp, Copy, Download } from 'lucide-react';
import type { TableArtifact, KpiGridArtifact, SummaryArtifact, ArtifactData } from './types';

// ── KPI Grid ─────────────────────────────────────────────────

export function KpiGrid({ artifact }: { artifact: KpiGridArtifact }) {
  return (
    <div className="mb-3">
      {artifact.title && (
        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
          {artifact.title}
        </h4>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {artifact.metrics.map((m, i) => (
          <Card key={i} className="p-3">
            <p className="text-xs text-muted-foreground">{m.label}</p>
            <p className="text-2xl font-bold tracking-tight mt-0.5">{m.value}</p>
            {m.changePct != null && (
              <div
                className={`flex items-center gap-1 text-xs mt-1 ${
                  m.changePct >= 0 ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {m.changePct >= 0 ? (
                  <ArrowUp className="h-3 w-3" />
                ) : (
                  <ArrowDown className="h-3 w-3" />
                )}
                <span>{Math.abs(m.changePct).toFixed(1)}%</span>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

// ── Artifact Table ──────────────────────────────────────────

function generateCsv(artifact: TableArtifact): string {
  const escape = (v: string) =>
    v.includes(',') || v.includes('"') || v.includes('\n')
      ? `"${v.replace(/"/g, '""')}"`
      : v;
  const header = artifact.headers.map(escape).join(',');
  const rows = artifact.rows.map((r) => r.map(escape).join(','));
  return [header, ...rows].join('\n');
}

function generateTsv(artifact: TableArtifact): string {
  const header = artifact.headers.join('\t');
  const rows = artifact.rows.map((r) => r.join('\t'));
  return [header, ...rows].join('\n');
}

export function ArtifactTable({ artifact }: { artifact: TableArtifact }) {
  const handleCopy = useCallback(() => {
    const tsv = generateTsv(artifact);
    navigator.clipboard.writeText(tsv);
  }, [artifact]);

  const handleDownloadCsv = useCallback(() => {
    const csv = generateCsv(artifact);
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${artifact.title.replace(/[^a-zA-Z0-9]/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [artifact]);

  return (
    <Card className="mb-3">
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-medium">{artifact.title}</CardTitle>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleCopy}>
            <Copy className="h-3 w-3 mr-1" />
            Copiar
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={handleDownloadCsv}
          >
            <Download className="h-3 w-3 mr-1" />
            CSV
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {artifact.headers.map((h, i) => (
                  <TableHead
                    key={i}
                    className={`text-xs ${
                      artifact.alignments?.[i] === 'right'
                        ? 'text-right'
                        : artifact.alignments?.[i] === 'center'
                        ? 'text-center'
                        : ''
                    }`}
                  >
                    {h}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {artifact.rows.map((row, ri) => (
                <TableRow key={ri} className={ri % 2 === 1 ? 'bg-muted/30' : ''}>
                  {row.map((cell, ci) => (
                    <TableCell
                      key={ci}
                      className={`text-sm ${
                        artifact.alignments?.[ci] === 'right'
                          ? 'text-right tabular-nums'
                          : artifact.alignments?.[ci] === 'center'
                          ? 'text-center'
                          : ''
                      }`}
                    >
                      {cell}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
              {artifact.rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={artifact.headers.length} className="text-center text-muted-foreground py-4">
                    Sin datos
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Summary ─────────────────────────────────────────────────

const SEVERITY_CLASSES: Record<string, string> = {
  info: 'border-blue-200 bg-blue-50/50',
  warning: 'border-yellow-200 bg-yellow-50/50',
  critical: 'border-red-200 bg-red-50/50',
};

export function ArtifactSummary({ artifact }: { artifact: SummaryArtifact }) {
  return (
    <Card className={`mb-3 ${SEVERITY_CLASSES[artifact.severity || 'info'] || ''}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{artifact.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm">{artifact.content}</p>
      </CardContent>
    </Card>
  );
}

// ── Generic Artifact Renderer ───────────────────────────────

export function ArtifactRenderer({ artifact }: { artifact: ArtifactData }) {
  switch (artifact.type) {
    case 'kpi_grid':
      return <KpiGrid artifact={artifact} />;
    case 'table':
      return <ArtifactTable artifact={artifact} />;
    case 'summary':
      return <ArtifactSummary artifact={artifact} />;
    default:
      return null;
  }
}
