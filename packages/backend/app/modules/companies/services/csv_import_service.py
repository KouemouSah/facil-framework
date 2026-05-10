"""
CSVImportService — Bulk company import from CSV.

Parse → validate → classify batch → create drafts.
Supports CSV with configurable column mappings.

Identifier rules (GE):
  - autonomo → registration_number (PE-XXXX format), NIF optional
  - All other forma_juridica → NIF required, registration_number optional
  - NIF format: alphanumeric, 5-20 chars
  - PE format: PE- followed by digits (e.g. PE-0001234)
"""

import csv
import io
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

import asyncpg
from loguru import logger

from app.modules.companies.services.classification_agent import classification_agent


# Required columns (must be present in CSV header)
REQUIRED_COLUMNS = {"legal_name", "forma_juridica"}

# Optional columns (recognized but not required)
OPTIONAL_COLUMNS = {
    "nif", "tax_id", "registration_number", "trade_name",
    "sector_actividad", "subsector_actividad", "objeto_social",
    "commerce_type", "capital_social", "employee_count",
    "localidad", "provincia",
    "domicilio_fiscal", "address", "phone", "email",
    "representante_legal", "nacionalidad",
}

# Column aliases (user-friendly names → internal field names)
COLUMN_ALIASES = {
    "nombre_empresa": "legal_name",
    "razon_social": "legal_name",
    "actividad_comercial": "objeto_social",
    "capital": "capital_social",
    "numero_empleados": "employee_count",
    "empleados": "employee_count",
    "numero_registro": "registration_number",
    "num_registro": "registration_number",
    "domicilio": "domicilio_fiscal",
    "direccion": "address",
    "telefono": "phone",
    "correo": "email",
    "representante": "representante_legal",
}

# Validation patterns
NIF_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$", re.IGNORECASE)
PE_PATTERN = re.compile(r"^PE-\d{3,10}$", re.IGNORECASE)

# Persona física forms that use registration_number (PE-XXXX) instead of NIF
# Aligned with classification_agent.PERSONA_FISICA_FORMAS
AUTONOMO_FORMS = {"autonomo", "empresa_individual"}


class CSVImportService:
    """Bulk company import from CSV files."""

    async def import_csv(
        self,
        conn: asyncpg.Connection,
        file_content: bytes,
        user_id: str,
        zone_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Parse CSV → validate → classify batch → create drafts.

        Returns import result with counts and errors.
        """
        # 1. Parse CSV
        rows, parse_errors = self._parse_csv(file_content)
        if not rows:
            return {
                "total": 0,
                "imported": 0,
                "errors": parse_errors,
                "batch_id": None,
            }

        batch_id = str(uuid.uuid4())

        # 2. Validate rows
        valid_rows = []
        validation_errors = []
        for row in rows:
            row_num = row.get("_csv_row_num", 0)
            issues = self._validate_row(row, row_num)
            if issues:
                validation_errors.extend(issues)
            else:
                valid_rows.append(row)

        if not valid_rows:
            return {
                "total": len(rows),
                "imported": 0,
                "errors": parse_errors + validation_errors,
                "batch_id": batch_id,
            }

        # 3. Pre-import duplicate detection against existing companies
        valid_rows, dup_errors = await self._filter_duplicates(
            conn, valid_rows
        )
        validation_errors.extend(dup_errors)

        if not valid_rows:
            return {
                "total": len(rows),
                "imported": 0,
                "auto_approved": 0,
                "pending_review": 0,
                "classification_errors": 0,
                "validation_errors": validation_errors,
                "parse_errors": parse_errors,
                "batch_id": batch_id,
            }

        # 4. Classify batch (strip internal _csv_row_num before sending)
        clean_rows = [{k: v for k, v in r.items() if k != "_csv_row_num"} for r in valid_rows]
        batch_result = await classification_agent.classify_batch(
            conn, clean_rows, zone_id
        )

        # 5. Create drafts for each classified item
        drafts_created = 0
        for item in batch_result.results:
            try:
                company_data = item.get("company_data", {})
                classification_data = item.get("classification", {})

                from app.modules.companies.models.classification import ClassificationResult
                classification = ClassificationResult(**classification_data)

                await classification_agent.create_draft(
                    conn,
                    company_data=company_data,
                    classification=classification,
                    source_type="csv",
                    batch_id=batch_id,
                    created_by=user_id,
                )
                drafts_created += 1
            except Exception as e:
                validation_errors.append(f"Draft creation error: {e}")
                logger.error(f"CSV import draft creation failed: {e}")

        logger.info(
            f"CSV import complete: {drafts_created}/{len(valid_rows)} drafts created "
            f"(batch={batch_id}, auto_approved={batch_result.auto_approved})"
        )

        return {
            "total": len(rows),
            "imported": drafts_created,
            "auto_approved": batch_result.auto_approved,
            "pending_review": batch_result.pending_review,
            "classification_errors": batch_result.errors,
            "validation_errors": validation_errors,
            "parse_errors": parse_errors,
            "batch_id": batch_id,
        }

    def _parse_csv(
        self, file_content: bytes
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Parse CSV content into list of dicts.

        Handles encoding detection (UTF-8 with BOM, Latin-1 fallback).
        Returns (rows, errors).
        """
        errors = []
        text = None

        # Try UTF-8 (with BOM), then Latin-1
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = file_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            return [], ["Cannot decode CSV file (tried UTF-8, Latin-1)"]

        # Detect delimiter (comma, semicolon, tab)
        first_line = text.split("\n")[0] if text else ""
        delimiter = ","
        if first_line.count(";") > first_line.count(","):
            delimiter = ";"
        elif first_line.count("\t") > first_line.count(","):
            delimiter = "\t"

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            return [], ["CSV has no header row"]

        # Map column aliases
        field_map = {}
        for col in reader.fieldnames:
            clean = col.strip().lower().replace(" ", "_")
            mapped = COLUMN_ALIASES.get(clean, clean)
            field_map[col] = mapped

        # Check required columns
        mapped_cols = set(field_map.values())
        missing = REQUIRED_COLUMNS - mapped_cols
        if missing:
            return [], [f"Missing required columns: {', '.join(missing)}"]

        rows = []
        for i, raw_row in enumerate(reader):
            try:
                row = {}
                row_has_error = False
                for orig_col, mapped_col in field_map.items():
                    val = (raw_row.get(orig_col) or "").strip()
                    if val:
                        # Type coercion for known numeric fields
                        if mapped_col == "capital_social":
                            val = val.replace(".", "").replace(",", ".").replace(" ", "")
                            try:
                                row[mapped_col] = float(val)
                            except ValueError:
                                errors.append(f"Row {i + 2}: invalid capital_social '{val}'")
                                row_has_error = True
                                break
                        elif mapped_col == "employee_count":
                            try:
                                row[mapped_col] = int(val)
                            except ValueError:
                                errors.append(f"Row {i + 2}: invalid employee_count '{val}'")
                                row_has_error = True
                                break
                        else:
                            row[mapped_col] = val

                if row_has_error:
                    continue

                if row.get("legal_name"):
                    row["_csv_row_num"] = i + 2
                    rows.append(row)
                else:
                    errors.append(f"Row {i + 2}: missing legal_name")

            except Exception as e:
                errors.append(f"Row {i + 2}: parse error: {e}")

        return rows, errors

    def _validate_row(self, row: Dict[str, Any], row_num: int) -> List[str]:
        """Validate a single row with identifier cross-checks.

        Rules:
          - legal_name: min 2 chars
          - forma_juridica: required
          - autonomo → must have registration_number (PE-XXXX), NIF optional
          - non-autonomo → should have NIF, registration_number optional
          - NIF format: alphanumeric, 5-20 chars
          - registration_number PE-XXXX: PE- followed by digits

        Returns list of error messages (empty if valid).
        """
        issues = []

        legal_name = row.get("legal_name", "")
        if len(legal_name) < 2:
            issues.append(f"Row {row_num}: legal_name too short ('{legal_name}')")

        forma = (row.get("forma_juridica") or "").lower().strip()
        if not forma:
            issues.append(f"Row {row_num}: missing forma_juridica")

        nif = (row.get("nif") or "").strip()
        reg_num = (row.get("registration_number") or "").strip()

        # NIF format validation
        if nif and not NIF_PATTERN.match(nif):
            issues.append(
                f"Row {row_num}: NIF format invalid ('{nif}') — "
                f"expected 5-20 alphanumeric chars"
            )

        # registration_number PE-XXXX format validation
        if reg_num and reg_num.upper().startswith("PE-") and not PE_PATTERN.match(reg_num):
            issues.append(
                f"Row {row_num}: registration_number format invalid ('{reg_num}') — "
                f"expected PE-XXXX (digits after PE-)"
            )

        # Cross-check: forma_juridica ↔ identifier type
        if forma in AUTONOMO_FORMS:
            # Autonomo MUST have registration_number (PE-XXXX)
            if not reg_num:
                issues.append(
                    f"Row {row_num}: forma_juridica='{forma}' requires "
                    f"registration_number (PE-XXXX format)"
                )
            elif not reg_num.upper().startswith("PE-"):
                issues.append(
                    f"Row {row_num}: forma_juridica='{forma}' — "
                    f"registration_number should be PE-XXXX format, "
                    f"got '{reg_num}'"
                )
        elif forma:
            # Non-autonomo forms: NIF expected
            if not nif and not reg_num:
                issues.append(
                    f"Row {row_num}: forma_juridica='{forma}' requires "
                    f"NIF or registration_number"
                )
            if reg_num and reg_num.upper().startswith("PE-"):
                issues.append(
                    f"Row {row_num}: forma_juridica='{forma}' but "
                    f"registration_number is PE-format ('{reg_num}') — "
                    f"PE-XXXX is for autonomo only"
                )

        return issues

    async def _filter_duplicates(
        self,
        conn: asyncpg.Connection,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Pre-import batch duplicate detection against existing companies.

        Checks both NIF and registration_number uniqueness in a single
        batch query (O(1) DB round-trips, not O(N)).

        Also detects intra-batch duplicates (same NIF/reg_num in CSV).

        Returns:
            (filtered_rows, error_messages)
        """
        errors: List[str] = []

        # Collect identifiers from CSV
        csv_nifs: List[str] = []
        csv_reg_nums: List[str] = []
        for row in rows:
            nif = (row.get("nif") or "").strip()
            reg = (row.get("registration_number") or "").strip()
            if nif:
                csv_nifs.append(nif)
            if reg:
                csv_reg_nums.append(reg)

        # Batch query: existing NIFs
        existing_nifs: Set[str] = set()
        if csv_nifs:
            db_rows = await conn.fetch(
                "SELECT nif FROM companies WHERE nif = ANY($1::text[])",
                csv_nifs,
            )
            existing_nifs = {r["nif"] for r in db_rows}

        # Batch query: existing registration_numbers
        existing_regs: Set[str] = set()
        if csv_reg_nums:
            db_rows = await conn.fetch(
                "SELECT registration_number FROM companies "
                "WHERE registration_number = ANY($1::text[])",
                csv_reg_nums,
            )
            existing_regs = {r["registration_number"] for r in db_rows}

        # Also check pending drafts (not yet approved but in queue)
        if csv_nifs:
            draft_rows = await conn.fetch(
                """SELECT company_data->>'nif' AS nif
                   FROM company_creation_drafts
                   WHERE status IN ('pending_review', 'auto_approved', 'needs_info')
                     AND company_data->>'nif' = ANY($1::text[])""",
                csv_nifs,
            )
            existing_nifs.update(r["nif"] for r in draft_rows if r["nif"])

        if csv_reg_nums:
            draft_rows = await conn.fetch(
                """SELECT company_data->>'registration_number' AS reg
                   FROM company_creation_drafts
                   WHERE status IN ('pending_review', 'auto_approved', 'needs_info')
                     AND company_data->>'registration_number' = ANY($1::text[])""",
                csv_reg_nums,
            )
            existing_regs.update(r["reg"] for r in draft_rows if r["reg"])

        # Filter rows — track intra-batch duplicates too
        seen_nifs: Set[str] = set()
        seen_regs: Set[str] = set()
        filtered: List[Dict[str, Any]] = []

        for row in rows:
            row_num = row.get("_csv_row_num", 0)
            nif = (row.get("nif") or "").strip()
            reg = (row.get("registration_number") or "").strip()
            skip = False

            if nif:
                if nif in existing_nifs:
                    errors.append(
                        f"Row {row_num}: NIF '{nif}' already exists "
                        f"(company or pending draft)"
                    )
                    skip = True
                elif nif in seen_nifs:
                    errors.append(
                        f"Row {row_num}: duplicate NIF '{nif}' in CSV"
                    )
                    skip = True
                else:
                    seen_nifs.add(nif)

            if reg:
                if reg in existing_regs:
                    errors.append(
                        f"Row {row_num}: registration_number '{reg}' "
                        f"already exists (company or pending draft)"
                    )
                    skip = True
                elif reg in seen_regs:
                    errors.append(
                        f"Row {row_num}: duplicate registration_number "
                        f"'{reg}' in CSV"
                    )
                    skip = True
                else:
                    seen_regs.add(reg)

            if not skip:
                filtered.append(row)

        if len(rows) != len(filtered):
            logger.info(
                f"Duplicate filter: {len(rows) - len(filtered)} rows removed "
                f"({len(existing_nifs)} existing NIFs, "
                f"{len(existing_regs)} existing reg_nums)"
            )

        return filtered, errors


# ── Module-level singleton ────────────────────────────────────────────────────

csv_import_service = CSVImportService()
