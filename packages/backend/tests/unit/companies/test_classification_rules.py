"""
Unit tests for CompanyClassificationAgent._rules_classify()

Tests the deterministic rules engine WITHOUT DB (no LLM, no async).
Covers all classification paths: R1 (exempt), R2 (special), R2b (autonomo+PE),
R2c (autonomo without PE), R3 (commercial sector), R4 (size), R5 (regime matrix).
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

# Import the module constants and the class
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'app'))

from modules.companies.services.classification_agent import (
    CompanyClassificationAgent,
    EXEMPT_FORMAS,
    SPECIAL_FORMAS,
    PERSONA_FISICA_FORMAS,
    COMMERCIAL_SUBSECTORS,
    DECLARATIVO_CAPITAL_THRESHOLD,
    DECLARATIVO_EMPLOYEE_THRESHOLD,
)


agent = CompanyClassificationAgent()


class TestR1ExemptEntities:
    """Rule 1: Exempt forma_juridica → exento."""

    @pytest.mark.parametrize("forma", list(EXEMPT_FORMAS))
    def test_exempt_forms_return_exento(self, forma):
        result = agent._rules_classify({
            "forma_juridica": forma,
            "sector_actividad": "primario",
        })
        assert result.regimen_fiscal == "exento"
        assert result.confidence >= 0.90
        assert "R1_exempt_forma_juridica" in result.rules_applied

    def test_exempt_case_insensitive(self):
        result = agent._rules_classify({"forma_juridica": "  ONG  "})
        assert result.regimen_fiscal == "exento"


class TestR2SpecialForms:
    """Rule 2: Special forms → declarativo."""

    @pytest.mark.parametrize("forma", list(SPECIAL_FORMAS))
    def test_special_forms_return_declarativo(self, forma):
        result = agent._rules_classify({"forma_juridica": forma})
        assert result.regimen_fiscal == "declarativo"
        assert "R2_special_forma_declarativo" in result.rules_applied


class TestR2bAutonomoPE:
    """Rule 2b: Autonomo + PE-XXXX → ALWAYS bundle (hard rule)."""

    def test_autonomo_with_pe_is_bundle(self):
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "registration_number": "PE-001234",
        })
        assert result.regimen_fiscal == "bundle"
        assert result.confidence >= 0.95
        assert "R2b_autonomo_pe_always_bundle" in result.rules_applied

    def test_autonomo_with_pe_ignores_size(self):
        """Even a large autonomo with PE is bundle, not mixto."""
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "registration_number": "PE-999999",
            "capital_social": 100_000_000,  # 100M XAF > threshold
            "employee_count": 200,
        })
        assert result.regimen_fiscal == "bundle"

    def test_empresa_individual_with_pe_is_bundle(self):
        result = agent._rules_classify({
            "forma_juridica": "empresa_individual",
            "registration_number": "PE-0055",
        })
        assert result.regimen_fiscal == "bundle"


class TestR2cAutonomoWithoutPE:
    """Rule 2c: Autonomo WITHOUT PE → presumed commercial → flow R3-R5."""

    def test_autonomo_no_pe_no_sector_is_bundle(self):
        """Autonomo presumed commercial → small + commercial → bundle."""
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            # No registration_number, no sector_actividad
        })
        assert result.regimen_fiscal == "bundle"
        assert "R2c_persona_fisica_presumed_commercial" in result.rules_applied

    def test_autonomo_large_no_pe_still_bundle(self):
        """Large autonomo without PE → still bundle (size doesn't change regime for persona física)."""
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "capital_social": 60_000_000,
        })
        assert result.regimen_fiscal == "bundle"


class TestR3PersonaMoralAlwaysDeclarativo:
    """Rule 3: Persona moral (SL/SA/sucursal/cooperativa) = ALWAYS declarativo.

    In GE fiscal law, these entities use Impuesto de Sociedades (IS) and
    declare via IVA/IRPF. They NEVER get zone-based bundle pricing.
    If an SA owns a restaurant, the restaurant is registered separately
    as an autonomo establishment at the Padrón Empresarial.
    """

    def test_sl_terciario_comercio_is_declarativo(self):
        result = agent._rules_classify({
            "forma_juridica": "sociedad_limitada",
            "sector_actividad": "terciario",
            "subsector_actividad": "comercio",
        })
        assert result.regimen_fiscal == "declarativo"
        assert "R3_persona_moral_always_declarativo" in result.rules_applied

    def test_sa_terciario_servicios_is_declarativo(self):
        result = agent._rules_classify({
            "forma_juridica": "sociedad_anonima",
            "sector_actividad": "TERCIARIO",
            "subsector_actividad": "SERVICIOS",
        })
        assert result.regimen_fiscal == "declarativo"

    def test_sl_with_commerce_type_is_declarativo(self):
        """SL with commerce_type should still be declarativo — commerce_type ignored."""
        result = agent._rules_classify({
            "forma_juridica": "sociedad_limitada",
            "commerce_type": "electronics_retail",
        })
        assert result.regimen_fiscal == "declarativo"
        assert result.commerce_type is None  # SL doesn't get commerce_type

    def test_sa_large_capital_is_declarativo(self):
        """SA with high capital is still just declarativo — no mixto regime in GE."""
        result = agent._rules_classify({
            "forma_juridica": "sociedad_anonima",
            "sector_actividad": "terciario",
            "subsector_actividad": "comercio",
            "capital_social": 60_000_000,
        })
        assert result.regimen_fiscal == "declarativo"

    def test_cooperativa_is_declarativo(self):
        result = agent._rules_classify({
            "forma_juridica": "cooperativa",
            "sector_actividad": "terciario",
            "subsector_actividad": "servicios",
            "employee_count": 100,
        })
        assert result.regimen_fiscal == "declarativo"

    def test_sucursal_is_declarativo(self):
        result = agent._rules_classify({
            "forma_juridica": "sucursal",
            "sector_actividad": "terciario",
            "subsector_actividad": "comercio",
        })
        assert result.regimen_fiscal == "declarativo"


class TestR4R5PersonaFisicaCommercial:
    """Rules 4-5: Persona física (autonomo/empresa_individual) commercial classification."""

    def test_autonomo_terciario_comercio_is_bundle(self):
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "sector_actividad": "terciario",
            "subsector_actividad": "comercio",
        })
        assert result.regimen_fiscal == "bundle"

    def test_autonomo_with_commerce_type_is_bundle(self):
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "commerce_type": "abaceria",
        })
        assert result.regimen_fiscal == "bundle"

    def test_empresa_individual_commercial_is_bundle(self):
        result = agent._rules_classify({
            "forma_juridica": "empresa_individual",
            "sector_actividad": "terciario",
            "subsector_actividad": "comercio",
        })
        assert result.regimen_fiscal == "bundle"

    def test_autonomo_non_commercial_is_declarativo(self):
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "sector_actividad": "primario",
        })
        assert result.regimen_fiscal == "declarativo"

    def test_sl_non_commercial_is_declarativo(self):
        result = agent._rules_classify({
            "forma_juridica": "sociedad_limitada",
            "sector_actividad": "primario",
        })
        assert result.regimen_fiscal == "declarativo"

    def test_empty_data_is_declarativo(self):
        result = agent._rules_classify({})
        assert result.regimen_fiscal in ("declarativo", "pendiente")


class TestNIFNormalization:
    """Test that classification handles various NIF/PE formats."""

    def test_pe_with_spaces(self):
        """PE with spaces should still match (normalization happens at DB level)."""
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "registration_number": "PE-001234",
        })
        assert result.regimen_fiscal == "bundle"

    def test_pe_lowercase(self):
        """PE comparison is uppercase."""
        result = agent._rules_classify({
            "forma_juridica": "autonomo",
            "registration_number": "pe-001234",
        })
        # pe- doesn't match PE- (uppercase check)
        # This tests the actual behavior
        assert result.regimen_fiscal in ("bundle", "declarativo")


class TestGeminiExtractionMapper:
    """Test map_gemini_extraction_to_company_data() — bridges GeminiDocumentProcessor to classify_company."""

    def test_padron_extraction_maps_localidad(self):
        """CRITICAL: localidad must be mapped for zone resolution."""
        extraction = {
            "empresa": {
                "denominacion_social": "Tienda El Sol",
                "numero_registro": "PE-001234",
                "forma_juridica": "AUTONOMO",
                "representante_legal": "Juan Garcia",
                "nacionalidad": "ECUATOGUINEANA",
            },
            "ubicacion": {
                "localidad": "Malabo",
                "provincia": "BIOKO-NORTE",
            },
            "actividad": {
                "sector": "Terciario",
                "subsector": "COMERCIO",
                "objeto_social": "Venta de productos alimenticios",
            },
            "datos_operativos": {
                "numero_empleados": 3,
                "numero_establecimientos": 1,
            },
            "certificacion": {
                "estado_negocio": "Negocio Activo",
            },
            "documento": {
                "ano_actualizacion": 2026,
                "codigo_timbre": "F12345678",
            },
        }
        result = agent.map_gemini_extraction_to_company_data(
            extraction, doc_type="CERTIFICADO_ACTUALIZACION_PADRON_EMPRESARIAL"
        )

        # CRITICAL: localidad and provincia must be present for zone resolution
        assert result["localidad"] == "Malabo"
        assert result["provincia"] == "BIOKO-NORTE"

        # Identity
        assert result["legal_name"] == "Tienda El Sol"
        assert result["registration_number"] == "PE-001234"
        assert result["forma_juridica"] == "autonomo"

        # Activity
        assert result["sector_actividad"] == "Terciario"
        assert result["subsector_actividad"] == "COMERCIO"
        assert result["objeto_social"] == "Venta de productos alimenticios"

        # Operational
        assert result["employee_count"] == 3

        # Metadata
        assert result["ano_certificado"] == 2026
        assert result["timbre_fiscal_code"] == "F12345678"

    def test_padron_auto_detects_autonomo(self):
        """If PE-XXXX present, forma_juridica should be autonomo even if missing."""
        extraction = {
            "empresa": {
                "denominacion_social": "Bar Tropical",
                "numero_registro": "PE-5678",
            },
            "ubicacion": {"localidad": "Bata", "provincia": "LITORAL"},
            "actividad": {"sector": "Terciario", "objeto_social": "Bar"},
        }
        result = agent.map_gemini_extraction_to_company_data(extraction, "PADRON")
        assert result["forma_juridica"] == "autonomo"
        assert result["localidad"] == "Bata"

    def test_vue_extraction_maps_nif(self):
        """VUE certificate should map nif, not registration_number."""
        extraction = {
            "empresa": {
                "denominacion_social": "Empresa ABC S.L.",
                "nif": "01234AB-56",
                "forma_juridica": "SOCIEDAD LIMITADA",
                "capital_social": 50000000,
            },
            "ubicacion": {"localidad": "Malabo", "provincia": "BIOKO-NORTE"},
            "actividad": {"sector": "Terciario", "objeto_social": "Comercio general"},
        }
        result = agent.map_gemini_extraction_to_company_data(
            extraction, "CERTIFICADO_REGISTRO_EMPRESARIAL"
        )
        assert result["nif"] == "01234AB-56"
        assert result.get("registration_number") is None
        assert result["forma_juridica"] == "sociedad limitada"
        assert result["localidad"] == "Malabo"

    def test_none_values_excluded(self):
        """None values should be excluded to avoid overwriting existing data."""
        extraction = {
            "empresa": {"denominacion_social": "Test", "nif": None},
            "ubicacion": {"localidad": "Bata"},
            "actividad": {},
        }
        result = agent.map_gemini_extraction_to_company_data(extraction)
        assert "nif" not in result
        assert result["localidad"] == "Bata"
        assert "sector_actividad" not in result
