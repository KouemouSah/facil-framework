"""CSV/XLSX export sanitization (CWE-1236 formula injection) — Phase 4 audit 6.

A cell whose text begins with = + - @ (or tab/CR) is executed as a formula when
the export opens in a spreadsheet. `_cell` must neutralize it with a leading
apostrophe while leaving ordinary values and typed primitives untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.csv_export import _cell  # noqa: E402


def test_cell_neutralizes_formula_prefixes():
    assert _cell("=1+1") == "'=1+1"
    assert _cell("+1") == "'+1"
    assert _cell("-1") == "'-1"
    assert _cell("@cmd") == "'@cmd"
    assert _cell("\ttab") == "'\ttab"
    assert _cell("\rcr") == "'\rcr"


def test_cell_leaves_safe_values_untouched():
    assert _cell("Malabo") == "Malabo"
    assert _cell("a=b") == "a=b"  # trigger only when LEADING
    assert _cell("") == ""


def test_cell_preserves_typed_primitives():
    # Numbers/bools carry no formula risk and must stay typed (xlsx cells).
    assert _cell(5) == 5
    assert _cell(3.14) == 3.14
    assert _cell(True) is True
    assert _cell(None) == ""
