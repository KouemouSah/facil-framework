#!/usr/bin/env python3
"""Classify backend migrations as DDL / DML / Mixed — Phase C of the
MIGRATIONS_BASELINE_REFACTOR_PLAN.

Rationale
---------
On a fresh database, applying the 319 incremental migrations from
packages/backend/database/migrations/ is slow and fragile. The refactor
splits them into:

  - baseline/000_baseline_<DATE>.sql   (DDL only, generated via pg_dump)
  - seeds/00X_<domain>.sql             (idempotent DML — permissions,
                                        roles, fiscal_services, etc.)
  - migrations/0XX_*.sql               (still applied for legacy staging)

To know what to extract as a seed (vs absorb into the baseline vs leave
behind as a one-shot transformation), we classify each migration:

  - DDL   : only structural statements (CREATE / ALTER / DROP TABLE,
            INDEX, VIEW, FUNCTION, TYPE, EXTENSION, etc.)
  - DML   : only data manipulation (INSERT / UPDATE / DELETE / TRUNCATE)
  - MIXED : both DDL and DML in the same file (the most dangerous to
            replay on a populated DB)
  - EMPTY : nothing actionable (comments only)

Usage
-----
    python deploy/scripts/classify_migrations.py
    python deploy/scripts/classify_migrations.py --output deploy/MIGRATIONS_CLASSIFICATION.md
    python deploy/scripts/classify_migrations.py --csv deploy/migrations_classification.csv

Exit codes
----------
0  Classification produced successfully.
1  Migrations directory not found.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "packages" / "backend" / "database" / "migrations"
DEFAULT_OUTPUT = REPO_ROOT / "deploy" / "MIGRATIONS_CLASSIFICATION.md"


# ---------------------------------------------------------------------------
# Statement-type detection
# ---------------------------------------------------------------------------

# Heuristic regexes — match the FIRST statement keyword on each non-comment line.
# Order matters in the dispatch loop below.
DDL_KEYWORDS = {
    "CREATE", "ALTER", "DROP", "TRUNCATE TABLE",  # TRUNCATE is technically DDL in PG
    "GRANT", "REVOKE",
    "COMMENT", "RENAME",
    "REINDEX", "CLUSTER",
}
DML_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE",
    "MERGE",  # PG 15+
    "COPY",   # bulk load
}
# Statements that don't really count as either (transactional / settings).
NEUTRAL_KEYWORDS = {
    "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE",
    "SET", "RESET",
    "DO",  # anonymous code blocks — could be either; treat as MIXED if non-empty
    "VACUUM", "ANALYZE",
    "WITH",  # CTE — depends on what's wrapped, treat as DML to be safe
    "SELECT",  # data fetch — neutral for our purpose
}


@dataclass
class FileClassification:
    filename: str
    ddl_count: int = 0
    dml_count: int = 0
    neutral_count: int = 0
    do_blocks: int = 0           # DO $$ ... $$ blocks (could mask either)
    line_count: int = 0
    tables_inserted_into: set[str] = field(default_factory=set)

    @property
    def category(self) -> str:
        if self.ddl_count == 0 and self.dml_count == 0 and self.do_blocks == 0:
            return "EMPTY"
        if self.dml_count > 0 and self.ddl_count > 0:
            return "MIXED"
        if self.do_blocks > 0 and (self.ddl_count > 0 or self.dml_count > 0):
            return "MIXED"
        if self.do_blocks > 0:
            return "MIXED"  # DO block alone — can't tell, mark mixed
        if self.dml_count > 0:
            return "DML"
        return "DDL"


# Pre-compile regexes used in the classifier.
RE_LINE_COMMENT = re.compile(r"--.*$", re.MULTILINE)
RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
RE_DO_BLOCK = re.compile(r"\bDO\s+\$\$", re.IGNORECASE)
RE_INSERT_TABLE = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?([\w]+)",
    re.IGNORECASE,
)


def strip_comments(sql: str) -> str:
    sql = RE_BLOCK_COMMENT.sub("", sql)
    sql = RE_LINE_COMMENT.sub("", sql)
    return sql


def first_keyword(stmt: str) -> str:
    """Return the first significant keyword(s) of a statement, uppercased."""
    stripped = stmt.strip()
    if not stripped:
        return ""
    # 1- or 2-word keywords (TRUNCATE TABLE).
    parts = re.split(r"\s+", stripped, maxsplit=2)
    one = parts[0].upper() if parts else ""
    two = f"{one} {parts[1].upper()}" if len(parts) >= 2 else one
    if two in DDL_KEYWORDS:
        return two
    if one in DDL_KEYWORDS or one in DML_KEYWORDS or one in NEUTRAL_KEYWORDS:
        return one
    return one  # unknown keyword — treat as neutral by default


def classify_file(path: Path) -> FileClassification:
    raw = path.read_text(encoding="utf-8", errors="replace")
    fc = FileClassification(filename=path.name, line_count=raw.count("\n"))

    # Count DO blocks separately (they obfuscate the inside).
    fc.do_blocks = len(RE_DO_BLOCK.findall(raw))

    # Tables targeted by INSERT — useful for seed extraction.
    fc.tables_inserted_into = set(
        m.group(1).lower() for m in RE_INSERT_TABLE.finditer(raw)
    )

    # Strip comments + naive split on `;` (good enough for classification —
    # we accept some noise from semicolons-inside-string-literals).
    cleaned = strip_comments(raw)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]

    for stmt in statements:
        kw = first_keyword(stmt)
        if not kw:
            continue
        if kw in DDL_KEYWORDS:
            fc.ddl_count += 1
        elif kw in DML_KEYWORDS:
            fc.dml_count += 1
        else:
            fc.neutral_count += 1

    return fc


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_markdown(results: list[FileClassification]) -> str:
    cat_counts: Counter[str] = Counter(r.category for r in results)
    total = len(results)

    # Tables that receive INSERTs → candidates for seed extraction.
    table_freq: Counter[str] = Counter()
    for r in results:
        for t in r.tables_inserted_into:
            table_freq[t] += 1

    lines = []
    lines.append("# Migrations classification — Phase C")
    lines.append("")
    lines.append(f"Source: `packages/backend/database/migrations/` "
                 f"({total} files)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Category | Count | Share |")
    lines.append("|---|---|---|")
    for cat in ("DDL", "DML", "MIXED", "EMPTY"):
        n = cat_counts.get(cat, 0)
        pct = (n / total * 100) if total else 0
        lines.append(f"| {cat} | {n} | {pct:.1f}% |")
    lines.append("")

    lines.append("## Tables receiving INSERT/UPDATE statements "
                 "(seed extraction candidates)")
    lines.append("")
    lines.append("Sorted by number of migrations that touch each table.")
    lines.append("")
    lines.append("| Table | # migrations | Action |")
    lines.append("|---|---|---|")
    for table, n in table_freq.most_common(40):
        action = "**SEED candidate**" if n >= 1 else ""
        lines.append(f"| `{table}` | {n} | {action} |")
    if len(table_freq) > 40:
        lines.append(f"| ... ({len(table_freq) - 40} more) | | |")
    lines.append("")

    # Recommended seed extraction shortlist (high-confidence reference data).
    SEED_PRIORITY_TABLES = [
        "permissions", "roles", "role_permissions",
        "categories", "ministries", "sectors",
        "fiscal_services", "service_keywords",
        "service_document_assignments", "service_procedure_assignments",
        "procedure_templates", "procedure_template_steps",
        "document_templates",
        "translations", "entity_translations",
        "workflow_menu_mapping",
    ]
    lines.append("## Recommended seed extraction shortlist")
    lines.append("")
    lines.append("Tables that are reference/configuration data (not user-generated). "
                 "Extract these into `database/seeds/` so a fresh DB is "
                 "operational without replaying 319 migrations.")
    lines.append("")
    lines.append("| Priority | Table | Touched by N migrations |")
    lines.append("|---|---|---|")
    for table in SEED_PRIORITY_TABLES:
        n = table_freq.get(table, 0)
        marker = "(no INSERT found)" if n == 0 else ""
        lines.append(f"| HIGH | `{table}` | {n} {marker} |")
    lines.append("")

    lines.append("## Per-file detail")
    lines.append("")
    lines.append("| Filename | Category | DDL | DML | DO | Notes |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda r: r.filename):
        notes = []
        if r.tables_inserted_into:
            top = sorted(r.tables_inserted_into)[:3]
            notes.append(f"INSERTs on: {', '.join(top)}"
                         + ("..." if len(r.tables_inserted_into) > 3 else ""))
        lines.append(
            f"| `{r.filename}` | {r.category} | {r.ddl_count} | "
            f"{r.dml_count} | {r.do_blocks} | {' / '.join(notes)} |"
        )
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append("Each migration is parsed by stripping `--` and `/* */` "
                 "comments, then split on `;`. The first keyword of each "
                 "statement is matched against:")
    lines.append("")
    lines.append("- **DDL**: CREATE, ALTER, DROP, TRUNCATE TABLE, GRANT, "
                 "REVOKE, COMMENT, RENAME, REINDEX, CLUSTER")
    lines.append("- **DML**: INSERT, UPDATE, DELETE, MERGE, COPY")
    lines.append("- **DO blocks** (`DO $$ ... $$`) are counted separately. "
                 "When present, the file is conservatively marked MIXED — "
                 "the parser cannot inspect the body without a full SQL grammar.")
    lines.append("")
    lines.append("Classification is heuristic, not strict — false positives "
                 "(MIXED) on simple files with a DO block are acceptable. "
                 "False negatives (DML missed in a DO block) are caught at "
                 "Phase D when the baseline is generated and at Phase G "
                 "during validation.")
    return "\n".join(lines)


def write_csv(results: list[FileClassification], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "category", "ddl_count", "dml_count",
                         "do_blocks", "line_count", "tables_inserted_into"])
        for r in sorted(results, key=lambda r: r.filename):
            writer.writerow([
                r.filename, r.category, r.ddl_count, r.dml_count,
                r.do_blocks, r.line_count,
                ";".join(sorted(r.tables_inserted_into)),
            ])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--migrations-dir", type=Path, default=MIGRATIONS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--csv", type=Path, default=None,
                        help="Optional CSV output for spreadsheet analysis.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not args.migrations_dir.exists():
        print(f"ERROR: migrations dir not found: {args.migrations_dir}",
              file=sys.stderr)
        return 1

    files = sorted(args.migrations_dir.glob("*.sql"))
    if not args.quiet:
        print(f"Classifying {len(files)} migrations...")

    results = [classify_file(f) for f in files]

    md = render_markdown(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    if not args.quiet:
        print(f"[OK] Markdown report: {args.output}")

    if args.csv:
        write_csv(results, args.csv)
        if not args.quiet:
            print(f"[OK] CSV report: {args.csv}")

    if not args.quiet:
        cat_counts = Counter(r.category for r in results)
        print(f"  DDL={cat_counts.get('DDL', 0)} "
              f"DML={cat_counts.get('DML', 0)} "
              f"MIXED={cat_counts.get('MIXED', 0)} "
              f"EMPTY={cat_counts.get('EMPTY', 0)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
