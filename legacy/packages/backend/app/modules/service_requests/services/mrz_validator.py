"""
MRZ (Machine Readable Zone) Validator - ICAO 9303 Standard.

Validates check digits for TD1 (ID cards, 3x30) and TD3 (passports, 2x44).
Returns per-check-digit ValidationResult objects for integration with
SchemaValidationEngine.

Supports:
- PASAPORTE_GQ: TD3 format (2 lines x 44 chars, 5 check digits)
- DIP_GQ: TD1 format (3 lines x 30 chars, 4 check digits)
- PERMISO_RESIDENCIA_GQ: TD1 format (3 lines x 30 chars, 4 check digits)

Author: Claude Code
Date: 2026-02-06
"""

from typing import Dict, Any, List, Optional

from loguru import logger

from .validation_types import ValidationResult


# ═══════════════════════════════════════════════════════════════════════════════
# ICAO 9303 CHECK DIGIT ALGORITHM
# ═══════════════════════════════════════════════════════════════════════════════

WEIGHTS = [7, 3, 1]


def icao_check_digit(data: str) -> int:
    """
    Compute ICAO 9303 modulo-10 check digit.

    Characters: 0-9 -> 0-9, A-Z -> 10-35, '<' -> 0
    Weight cycle: 7, 3, 1 repeating.

    Args:
        data: String of MRZ characters (digits, uppercase letters, '<')

    Returns:
        Check digit (0-9)
    """
    total = 0
    for i, ch in enumerate(data):
        if ch.isdigit():
            val = int(ch)
        elif ch.isalpha() and ch.isupper():
            val = ord(ch) - 55  # A=10, B=11, ..., Z=35
        elif ch == '<':
            val = 0
        else:
            val = 0  # Unexpected character (OCR artifact) - treat as filler
        total += val * WEIGHTS[i % 3]
    return total % 10


# ═══════════════════════════════════════════════════════════════════════════════
# TD3 POSITIONS (Passport - 2 lines x 44 chars)
# ═══════════════════════════════════════════════════════════════════════════════

TD3_CHECKS = [
    {
        "id": "passport_number",
        "line": 2, "data_start": 0, "data_end": 9, "digit_pos": 9,
        "desc_es": "numero de pasaporte",
        "desc_fr": "numero de passeport",
    },
    {
        "id": "birth_date",
        "line": 2, "data_start": 13, "data_end": 19, "digit_pos": 19,
        "desc_es": "fecha de nacimiento",
        "desc_fr": "date de naissance",
    },
    {
        "id": "expiry_date",
        "line": 2, "data_start": 21, "data_end": 27, "digit_pos": 27,
        "desc_es": "fecha de expiracion",
        "desc_fr": "date d'expiration",
    },
    {
        "id": "optional_data",
        "line": 2, "data_start": 28, "data_end": 42, "digit_pos": 42,
        "desc_es": "datos opcionales",
        "desc_fr": "donnees optionnelles",
    },
]

TD3_COMPOSITE = {
    "id": "composite",
    "line": 2,
    # Composite covers: pos 0-9 (num+check) + pos 13-19 (birth+check) + pos 21-42 (exp+check+opt+check)
    "ranges": [(0, 10), (13, 20), (21, 43)],
    "digit_pos": 43,
    "desc_es": "composite global",
    "desc_fr": "composite global",
}


# ═══════════════════════════════════════════════════════════════════════════════
# TD1 POSITIONS (ID Card / Residence Permit - 3 lines x 30 chars)
# ═══════════════════════════════════════════════════════════════════════════════

TD1_CHECKS = [
    {
        "id": "document_number",
        "line": 1, "data_start": 5, "data_end": 14, "digit_pos": 14,
        "desc_es": "numero de documento",
        "desc_fr": "numero de document",
    },
    {
        "id": "birth_date",
        "line": 2, "data_start": 0, "data_end": 6, "digit_pos": 6,
        "desc_es": "fecha de nacimiento",
        "desc_fr": "date de naissance",
    },
    {
        "id": "expiry_date",
        "line": 2, "data_start": 8, "data_end": 14, "digit_pos": 14,
        "desc_es": "fecha de expiracion",
        "desc_fr": "date d'expiration",
    },
]

TD1_COMPOSITE = {
    "id": "composite",
    # Composite covers: line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29]
    "ranges_multiline": [
        (1, 5, 30),   # line 1: positions 5-29
        (2, 0, 7),    # line 2: positions 0-6 (birth + check)
        (2, 8, 15),   # line 2: positions 8-14 (expiry + check)
        (2, 18, 29),  # line 2: positions 18-28 (optional)
    ],
    "digit_line": 2,
    "digit_pos": 29,
    "desc_es": "composite global",
    "desc_fr": "composite global",
}


# ═══════════════════════════════════════════════════════════════════════════════
# MRZ VALIDATOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════


class MRZValidator:
    """
    Validates MRZ check digits per ICAO 9303.

    Returns one ValidationResult per check digit for granular diagnostics.
    Never raises exceptions - returns empty list on any error.
    """

    def validate(
        self,
        extraction: Dict[str, Any],
        document_code: str,
        schema: Optional[Dict] = None,
    ) -> List[ValidationResult]:
        """
        Validate MRZ check digits from extraction data.

        Looks for MRZ lines in extraction under:
        - extraction["mrz"]["linea_N"] (nested)
        - extraction["linea_N"] (flat fallback)

        Returns empty list if MRZ data is missing or truncated.
        """
        try:
            lines = self._extract_mrz_lines(extraction)
            if not lines:
                return []

            mrz_format = self._detect_format(lines, schema)
            if mrz_format is None:
                return []

            if mrz_format == "TD3":
                return self._validate_td3(lines, document_code)
            elif mrz_format == "TD1":
                return self._validate_td1(lines, document_code)
            else:
                return []
        except Exception as e:
            logger.warning(f"MRZ validation error for '{document_code}': {e}")
            return []

    # ─── MRZ Line Extraction ────────────────────────────────────────────

    @staticmethod
    def _extract_mrz_lines(extraction: Dict[str, Any]) -> Dict[int, str]:
        """Extract MRZ lines from extraction dict. Returns {1: "...", 2: "...", ...}."""
        lines: Dict[int, str] = {}

        # Try nested first: extraction["mrz"]["linea_N"]
        mrz_block = extraction.get("mrz")
        if isinstance(mrz_block, dict):
            for key in ("linea_1", "linea_2", "linea_3"):
                val = mrz_block.get(key)
                if val and isinstance(val, str):
                    line_num = int(key.split("_")[1])
                    lines[line_num] = val.strip().upper().replace(" ", "")

        # Flat fallback: extraction["linea_N"]
        if not lines:
            for key in ("linea_1", "linea_2", "linea_3"):
                val = extraction.get(key)
                if val and isinstance(val, str):
                    line_num = int(key.split("_")[1])
                    lines[line_num] = val.strip().upper().replace(" ", "")

        return lines

    # ─── Format Detection ───────────────────────────────────────────────

    @staticmethod
    def _detect_format(
        lines: Dict[int, str], schema: Optional[Dict]
    ) -> Optional[str]:
        """Detect TD1 vs TD3 from schema or line analysis."""
        # From schema extraction.mrz.format
        if schema:
            mrz_section = schema.get("extraction", {}).get("mrz", {})
            fmt = mrz_section.get("format", "").upper()
            if fmt in ("TD1", "TD3"):
                return fmt

        # Heuristic: 3 lines with ~30 chars = TD1, 2 lines with ~44 chars = TD3
        if 3 in lines and len(lines.get(1, "")) <= 32:
            return "TD1"
        if 1 in lines and 2 in lines and len(lines.get(1, "")) >= 40:
            return "TD3"

        return None

    # ─── TD3 Validation (Passport) ──────────────────────────────────────

    def _validate_td3(
        self, lines: Dict[int, str], document_code: str
    ) -> List[ValidationResult]:
        """Validate TD3 passport MRZ (2 lines x 44 chars)."""
        results: List[ValidationResult] = []
        line2 = lines.get(2, "")

        if len(line2) < 44:
            results.append(self._format_error(
                document_code, "mrz_line2_length",
                f"Linea 2 MRZ truncada ({len(line2)}/44 chars)",
                f"Ligne 2 MRZ tronquee ({len(line2)}/44 chars)",
            ))
            return results

        # Individual check digits
        for check_def in TD3_CHECKS:
            data = line2[check_def["data_start"]:check_def["data_end"]]
            expected_char = line2[check_def["digit_pos"]]
            results.append(self._verify_digit(
                data, expected_char, check_def, document_code
            ))

        # Composite check digit
        composite_data = ""
        for start, end in TD3_COMPOSITE["ranges"]:
            composite_data += line2[start:end]
        composite_expected = line2[TD3_COMPOSITE["digit_pos"]]
        results.append(self._verify_digit(
            composite_data, composite_expected, TD3_COMPOSITE, document_code
        ))

        return results

    # ─── TD1 Validation (ID Card / Residence Permit) ────────────────────

    def _validate_td1(
        self, lines: Dict[int, str], document_code: str
    ) -> List[ValidationResult]:
        """Validate TD1 ID card MRZ (3 lines x 30 chars)."""
        results: List[ValidationResult] = []
        line1 = lines.get(1, "")
        line2 = lines.get(2, "")

        if len(line1) < 30:
            results.append(self._format_error(
                document_code, "mrz_line1_length",
                f"Linea 1 MRZ truncada ({len(line1)}/30 chars)",
                f"Ligne 1 MRZ tronquee ({len(line1)}/30 chars)",
            ))
            return results

        if len(line2) < 30:
            results.append(self._format_error(
                document_code, "mrz_line2_length",
                f"Linea 2 MRZ truncada ({len(line2)}/30 chars)",
                f"Ligne 2 MRZ tronquee ({len(line2)}/30 chars)",
            ))
            return results

        # Individual check digits
        for check_def in TD1_CHECKS:
            line = line1 if check_def["line"] == 1 else line2
            data = line[check_def["data_start"]:check_def["data_end"]]
            expected_char = line[check_def["digit_pos"]]
            results.append(self._verify_digit(
                data, expected_char, check_def, document_code
            ))

        # Composite check digit (spans multiple lines)
        composite_data = ""
        for line_num, start, end in TD1_COMPOSITE["ranges_multiline"]:
            line = lines.get(line_num, "")
            composite_data += line[start:end]
        composite_line = lines.get(TD1_COMPOSITE["digit_line"], "")
        composite_expected = composite_line[TD1_COMPOSITE["digit_pos"]]
        results.append(self._verify_digit(
            composite_data, composite_expected, TD1_COMPOSITE, document_code
        ))

        return results

    # ─── Check Digit Verification ───────────────────────────────────────

    @staticmethod
    def _verify_digit(
        data: str,
        expected_char: str,
        check_def: Dict,
        document_code: str,
    ) -> ValidationResult:
        """Verify a single ICAO 9303 check digit."""
        check_id = check_def["id"]
        desc_es = check_def.get("desc_es", check_id)
        desc_fr = check_def.get("desc_fr", check_id)
        computed = icao_check_digit(data)

        if not expected_char.isdigit():
            return ValidationResult(
                rule_id=f"mrz_check_{check_id}",
                passed=False,
                severity="warning",
                message_es=f"Digito de control MRZ ({desc_es}): caracter no numerico '{expected_char}'",
                message_fr=f"Chiffre de controle MRZ ({desc_fr}): caractere non numerique '{expected_char}'",
                rule=f"ICAO9303_check_digit({check_id})",
                document_code=document_code,
            )

        expected = int(expected_char)
        passed = (computed == expected)

        if passed:
            return ValidationResult(
                rule_id=f"mrz_check_{check_id}",
                passed=True,
                severity="info",
                message_es=f"Digito de control MRZ ({desc_es}): OK",
                message_fr=f"Chiffre de controle MRZ ({desc_fr}): OK",
                rule=f"ICAO9303_check_digit({check_id})",
                document_code=document_code,
            )
        else:
            return ValidationResult(
                rule_id=f"mrz_check_{check_id}",
                passed=False,
                severity="error",
                message_es=f"Digito de control MRZ ({desc_es}): esperado {expected}, calculado {computed}",
                message_fr=f"Chiffre de controle MRZ ({desc_fr}): attendu {expected}, calcule {computed}",
                rule=f"ICAO9303_check_digit({check_id})",
                document_code=document_code,
            )

    @staticmethod
    def _format_error(
        document_code: str, rule_id: str, msg_es: str, msg_fr: str
    ) -> ValidationResult:
        """Create a format-level error ValidationResult."""
        return ValidationResult(
            rule_id=rule_id,
            passed=False,
            severity="warning",
            message_es=msg_es,
            message_fr=msg_fr,
            rule="MRZ_FORMAT_CHECK",
            document_code=document_code,
        )


# Singleton
mrz_validator = MRZValidator()
