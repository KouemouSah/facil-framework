#!/usr/bin/env python3
"""
i18n drift detector for Facil mobile.

Compares the flat key sets across `es.json`, `fr.json`, `en.json` and exits
non-zero when any locale is missing a key that another one has.

Usage:
  python check-locales-drift.py [--locales-dir PATH]

Exit codes:
  0 — all locales contain the same keys.
  1 — drift detected; the differences are printed.
  2 — file not found / invalid JSON.

Designed to be run by CI as a hard fail-or-pass step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable


def flatten(obj: object, prefix: str = "") -> Dict[str, object]:
    out: Dict[str, object] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            full = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                out.update(flatten(value, full))
            else:
                out[full] = value
    return out


def load_locale(path: Path) -> Dict[str, object]:
    if not path.exists():
        print(f"ERROR: locale file not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with path.open("r", encoding="utf-8") as f:
            return flatten(json.load(f))
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(2)


def report_missing(label: str, missing: Iterable[str]) -> None:
    items = sorted(missing)
    if not items:
        return
    print(f"  {label} ({len(items)} key{'s' if len(items) != 1 else ''}):")
    for k in items:
        print(f"    - {k}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--locales-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "locales",
        help="Directory containing es.json / fr.json / en.json",
    )
    args = parser.parse_args()

    es = load_locale(args.locales_dir / "es.json")
    fr = load_locale(args.locales_dir / "fr.json")
    en = load_locale(args.locales_dir / "en.json")

    es_keys, fr_keys, en_keys = set(es.keys()), set(fr.keys()), set(en.keys())
    union = es_keys | fr_keys | en_keys

    missing_in_es = union - es_keys
    missing_in_fr = union - fr_keys
    missing_in_en = union - en_keys

    if not (missing_in_es or missing_in_fr or missing_in_en):
        print(
            f"OK — {len(es_keys)} keys synced across es / fr / en "
            f"({args.locales_dir})"
        )
        return 0

    print("DRIFT DETECTED:")
    report_missing("missing in es.json", missing_in_es)
    report_missing("missing in fr.json", missing_in_fr)
    report_missing("missing in en.json", missing_in_en)

    print(
        f"\nTotals: es={len(es_keys)}, fr={len(fr_keys)}, en={len(en_keys)} "
        f"(union={len(union)})"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
