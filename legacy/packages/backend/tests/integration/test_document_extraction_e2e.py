"""
E2E Tests for Document Extraction System
Tests the full extraction pipeline: Templates → Extractors → Mappers

Author: Claude Code
Date: 2025-11-13
Version: 1.0 - Complete template-based extraction testing
"""

import pytest
from typing import Dict, Any


# Sample OCR text for each form type (simulating real OCR output)
SAMPLE_OCR_IVA_DESTAJO = """
MINISTERIO DE HACIENDA
IMPUESTO SOBRE EL VALOR AÑADIDO (IVA) - DESTAJO

N.I.F.: 12345678A
En nombre y representación de la empresa: CONSTRUCCIONES MALABO SA
Ejercicio: 2024
Periodo: 1T
Fecha: 15/01/2024
Auto-liquidación Nº: 2024/001/IVA

RÉGIMEN GENERAL (01-03)
01 Base Imponible: 50,000.00 €
02 Tipo: 15%
03 Cuota: 7,500.00 €

RÉGIMEN REDUCIDO 1 (04-06)
04 Base Imponible: 20,000.00 €
05 Tipo: 7%
06 Cuota: 1,400.00 €

RÉGIMEN REDUCIDO 2 (07-09)
07 Base Imponible: 10,000.00 €
08 Tipo: 3%
09 Cuota: 300.00 €

10 Total a ingresar: 9,200.00 €
"""

SAMPLE_OCR_RETENCION_SERVICIOS = """
MINISTERIO DE HACIENDA
RETENCIÓN SOBRE SERVICIOS A NO RESIDENTES
ARTÍCULO 10 - SECTOR PETROLERO

N.I.F.: 87654321B
En nombre y representación de la empresa: PETROLEUM SERVICES GQ SL
Ejercicio: 2024
Periodo: 2T
Fecha: 20/04/2024
Auto-liquidación Nº: 2024/045/RET
Municipio: Malabo
Dirección Fiscal: Calle Independencia 123
Provincia: Bioko Norte

Ha ingresado al Tesoro Público, la cantidad de: 15,000.00 €

01 Base Imponible (Servicios Sujetos): 100,000.00 €
Tipo (%): 15%
Cuota: 15,000.00 €

06 Total a ingresar: 15,000.00 €
"""

SAMPLE_OCR_PRODUCTOS_PETROLEROS = """
MINISTERIO DE HACIENDA
IMPUESTO SOBRE PRODUCTOS PETROLÍFEROS - IVS

N.I.F.: 11223344C
En nombre y representación de la empresa: DISTRIBUIDORA COMBUSTIBLES GQ
Ejercicio: 2024
Periodo: 3T
Fecha: 10/07/2024

01 Precio: 250,000.00 €
02 Cuota: 37,500.00 €
03 Total Devengado: 287,500.00 €

020 Total a Ingresar: 287,500.00 €
"""

SAMPLE_OCR_SUELDOS_SALARIOS = """
MINISTERIO DE HACIENDA
IMPUESTO SOBRE SUELDOS Y SALARIOS
SECTOR COMÚN

N.I.F.: 55667788D
En nombre y representación de la empresa: SERVICIOS ADMINISTRATIVOS SA
Ejercicio: 2024
Periodo: 1T
Fecha: 25/01/2024

Importe total de las cuotas retenidas: 8,500.00 €
Recargos: 0.00 €
Intereses de demora: 0.00 €

Total a Ingresar: 8,500.00 €
"""

SAMPLE_OCR_CUOTA_MINIMA = """
MINISTERIO DE HACIENDA
CUOTA MÍNIMA FISCAL
SECTOR COMÚN

N.I.F.: 99887766E
En nombre y representación de la empresa: COMERCIAL BATA LTDA
Ejercicio: 2024
Periodo: 2T
Fecha: 30/04/2024

Base Imponible: 120,000.00 €
Reducciones: 20,000.00 €
Base Liquidable: 100,000.00 €
Tipo de Gravamen: 25%
Cuota: 25,000.00 €

A INGRESAR: 25,000.00 €
"""

SAMPLE_OCR_IMPRESO_COMUN = """
MINISTERIO DE HACIENDA
IMPRESO COMÚN - DECLARACIÓN FISCAL GENERAL

N.I.F.: 44556677F
En nombre y representación de la empresa: INVERSIONES MALABO SL
Ejercicio: 2024
Periodo: 1T
Fecha: 15/02/2024

Base Imponible: 75,000.00 €
Tipo de Gravamen: 20%
Cuota: 15,000.00 €

A INGRESAR: 15,000.00 €
"""

SAMPLE_OCR_LIQUIDACION = """
MINISTERIO DE HACIENDA
IMPRESO DE LIQUIDACIÓN
FORMULARIO DE LIQUIDACIÓN FISCAL

N.I.F.: 33445566G
En nombre y representación de la empresa: CONSTRUCCIONES BATA SA
Ejercicio: 2024
Periodo: 2T
Fecha: 20/05/2024

Base Imponible: 150,000.00 €
Tipo de gravamen: 25%
Cuota: 37,500.00 €

Deducciones del periodo: 5,000.00 €
Deducciones de periodos anteriores: 2,000.00 €
Recargo: 500.00 €
Interés de demora: 250.00 €
Sanciones: 0.00 €

Total a ingresar: 31,250.00 €
"""


class TestDocumentExtractionE2E:
    """End-to-end tests for document extraction pipeline"""

    @pytest.fixture
    def template_loader(self):
        """Load template loader"""
        from app.core.documents.extractors.template_loader import template_loader
        return template_loader

    @pytest.fixture
    def zone_extractor(self):
        """Load zone-label extractor"""
        from app.core.documents.extractors.zone_label_extractor import zone_label_extractor
        return zone_extractor

    @pytest.mark.asyncio
    async def test_iva_destajo_extraction_e2e(self, template_loader, zone_extractor):
        """Test IVA Destajo form: template → extraction → mapping"""
        # Load template
        template = template_loader.load("iva_destajo", "declaration")
        assert template is not None
        assert template.name == "iva_destajo"
        assert template.category == "iva"

        # Extract data
        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_IVA_DESTAJO,
            template,
            ocr_confidence=0.95
        )

        # Verify extraction
        assert result.success
        assert result.extracted_data["nif"] == "12345678A"
        assert result.extracted_data["empresa"] == "CONSTRUCCIONES MALABO SA"
        assert result.extracted_data["ejercicio"] == "2024"
        assert result.extracted_data["periodo"] == "1T"

        # Check numeric fields
        assert float(result.extracted_data["base_imponible_general"]) == 50000.00
        assert float(result.extracted_data["tipo_general"]) == 15.0
        assert float(result.extracted_data["cuota_general"]) == 7500.00

        # Map to frontend form
        from app.core.documents.mappers import iva_form_mapper
        mapping_result = await iva_form_mapper.map(
            result.extracted_data,
            result.field_confidences
        )

        assert mapping_result.success
        assert mapping_result.form_type == "declaration_iva"
        assert mapping_result.pre_filled_fields["nif"] == "12345678A"
        assert mapping_result.pre_filled_fields["regimen_general_base"] == 50000.00

    @pytest.mark.asyncio
    async def test_retencion_servicios_extraction_e2e(self, template_loader, zone_extractor):
        """Test Retención Servicios form extraction"""
        template = template_loader.load("form_retencion_servicios", "declaration")
        assert template is not None

        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_RETENCION_SERVICIOS,
            template,
            ocr_confidence=0.92
        )

        assert result.success
        assert result.extracted_data["nif"] == "87654321B"
        assert result.extracted_data["municipio"] == "Malabo"
        assert float(result.extracted_data["servicios_sujetos_base"]) == 100000.00
        assert float(result.extracted_data["servicios_sujetos_tipo"]) == 15.0

        # Map to form
        from app.core.documents.mappers import retencion_servicios_mapper
        mapping_result = await retencion_servicios_mapper.map(
            result.extracted_data,
            result.field_confidences
        )

        assert mapping_result.success
        assert mapping_result.form_type == "declaration_retencion_servicios"
        assert mapping_result.pre_filled_fields["base_imponible"] == 100000.00

    @pytest.mark.asyncio
    async def test_petroleum_products_extraction_e2e(self, template_loader, zone_extractor):
        """Test Petroleum Products form extraction"""
        template = template_loader.load("form_imp_productos_petroleros", "declaration")
        assert template is not None

        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_PRODUCTOS_PETROLEROS,
            template
        )

        assert result.success
        assert result.extracted_data["nif"] == "11223344C"
        assert float(result.extracted_data["prod_sujetos_precio"]) == 250000.00
        assert float(result.extracted_data["total_a_ingresar"]) == 287500.00

        # Map to form
        from app.core.documents.mappers import petroleum_products_mapper
        mapping_result = await petroleum_products_mapper.map(
            result.extracted_data,
            result.field_confidences
        )

        assert mapping_result.success
        assert mapping_result.pre_filled_fields["productos_precio"] == 250000.00

    @pytest.mark.asyncio
    async def test_payroll_tax_extraction_e2e(self, template_loader, zone_extractor):
        """Test Payroll Tax (Sueldos y Salarios) extraction"""
        template = template_loader.load("form_imp_sueldos_salarios", "declaration")
        assert template is not None

        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_SUELDOS_SALARIOS,
            template
        )

        assert result.success
        assert result.extracted_data["nif"] == "55667788D"
        assert float(result.extracted_data["importe_total_retenidas"]) == 8500.00
        assert float(result.extracted_data["total_a_ingresar"]) == 8500.00

        # Map to form
        from app.core.documents.mappers import payroll_tax_mapper
        mapping_result = await payroll_tax_mapper.map(
            result.extracted_data,
            result.field_confidences
        )

        assert mapping_result.success
        assert mapping_result.pre_filled_fields["importe_retenido"] == 8500.00

    @pytest.mark.asyncio
    async def test_minimum_fiscal_fee_extraction_e2e(self, template_loader, zone_extractor):
        """Test Cuota Mínima Fiscal extraction with deductions"""
        template = template_loader.load("form_cuota_minima_fiscal", "declaration")
        assert template is not None

        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_CUOTA_MINIMA,
            template
        )

        assert result.success
        assert result.extracted_data["nif"] == "99887766E"
        assert float(result.extracted_data["base_imponible"]) == 120000.00
        assert float(result.extracted_data["reducciones"]) == 20000.00
        assert float(result.extracted_data["base_liquidable"]) == 100000.00

        # Map and verify derived calculations
        from app.core.documents.mappers import minimum_fiscal_fee_mapper
        mapping_result = await minimum_fiscal_fee_mapper.map(
            result.extracted_data,
            result.field_confidences
        )

        assert mapping_result.success
        # Verify derived field: base_liquidable = base_imponible - reducciones
        assert mapping_result.pre_filled_fields["base_liquidable_calculated"] == 100000.00

    @pytest.mark.asyncio
    async def test_general_tax_extraction_e2e(self, template_loader, zone_extractor):
        """Test Impreso Común (General Tax) extraction"""
        template = template_loader.load("form_impreso_comun", "declaration")
        assert template is not None

        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_IMPRESO_COMUN,
            template
        )

        assert result.success
        assert result.extracted_data["nif"] == "44556677F"
        assert float(result.extracted_data["base_imponible"]) == 75000.00
        assert float(result.extracted_data["cuota"]) == 15000.00

        # Map to form
        from app.core.documents.mappers import general_tax_mapper
        mapping_result = await general_tax_mapper.map(
            result.extracted_data,
            result.field_confidences
        )

        assert mapping_result.success
        # Verify derived calculation
        assert mapping_result.pre_filled_fields["cuota_calculated"] == 15000.00

    @pytest.mark.asyncio
    async def test_tax_settlement_extraction_e2e(self, template_loader, zone_extractor):
        """Test Impreso de Liquidación (Tax Settlement) extraction"""
        template = template_loader.load("form_impreso_liquidacion", "declaration")
        assert template is not None

        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_LIQUIDACION,
            template
        )

        assert result.success
        assert result.extracted_data["nif"] == "33445566G"
        assert float(result.extracted_data["deducciones_periodo"]) == 5000.00
        assert float(result.extracted_data["recargo"]) == 500.00
        assert float(result.extracted_data["interes_demora"]) == 250.00

        # Map to form
        from app.core.documents.mappers import tax_settlement_mapper
        mapping_result = await tax_settlement_mapper.map(
            result.extracted_data,
            result.field_confidences
        )

        assert mapping_result.success
        # Verify derived fields: total deductions and charges
        assert mapping_result.pre_filled_fields["total_deducciones"] == 7000.00  # 5000 + 2000
        assert mapping_result.pre_filled_fields["total_recargos"] == 750.00  # 500 + 250 + 0

    @pytest.mark.asyncio
    async def test_template_validation_rules(self, template_loader, zone_extractor):
        """Test that validation rules in templates are applied"""
        template = template_loader.load("form_cuota_minima_fiscal", "declaration")

        # Verify template has validations
        assert len(template.validations) > 0

        # Check calculation validation exists
        calc_validations = [v for v in template.validations if v.type == "calculation"]
        assert len(calc_validations) > 0

        # Test with valid data
        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_CUOTA_MINIMA,
            template
        )

        # The extracted cuota should match calculated value within tolerance
        base_liq = float(result.extracted_data["base_liquidable"])
        tipo = float(result.extracted_data["tipo_de_gravamen"])
        cuota = float(result.extracted_data["cuota"])

        calculated_cuota = base_liq * (tipo / 100)
        assert abs(cuota - calculated_cuota) < 0.01  # Within tolerance

    @pytest.mark.asyncio
    async def test_confidence_scoring(self, template_loader, zone_extractor):
        """Test that confidence scores are properly calculated"""
        template = template_loader.load("iva_destajo", "declaration")

        result = await zone_extractor.extract_from_template(
            SAMPLE_OCR_IVA_DESTAJO,
            template,
            ocr_confidence=0.90
        )

        # Check that confidence scores exist for extracted fields
        assert len(result.field_confidences) > 0

        # Confidence should be between 0 and 1
        for field, confidence in result.field_confidences.items():
            assert 0.0 <= confidence <= 1.0

        # Overall confidence should be calculated
        assert 0.0 <= result.overall_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_missing_fields_handling(self, template_loader, zone_extractor):
        """Test extraction when some fields are missing"""
        template = template_loader.load("form_impreso_comun", "declaration")

        # OCR text with missing optional fields
        partial_ocr = """
        N.I.F.: 12345678A
        En nombre y representación de la empresa: TEST SA
        Ejercicio: 2024
        Base Imponible: 50,000.00 €
        """

        result = await zone_extractor.extract_from_template(
            partial_ocr,
            template
        )

        # Should still succeed with required fields
        assert result.success
        assert "nif" in result.extracted_data
        assert "base_imponible" in result.extracted_data

        # Missing fields should have lower overall confidence
        assert result.overall_confidence < 0.8

    def test_all_templates_loadable(self, template_loader):
        """Verify all 7 templates can be loaded without errors"""
        templates = [
            "iva_destajo",
            "form_retencion_servicios",
            "form_imp_productos_petroleros",
            "form_imp_sueldos_salarios",
            "form_cuota_minima_fiscal",
            "form_impreso_comun",
            "form_impreso_liquidacion"
        ]

        for template_name in templates:
            template = template_loader.load(template_name, "declaration")
            assert template is not None, f"Failed to load template: {template_name}"
            assert len(template.fields) > 0, f"Template {template_name} has no fields"

    def test_all_mappers_instantiatable(self):
        """Verify all mappers can be imported and instantiated"""
        from app.core.documents.mappers import (
            iva_form_mapper,
            retencion_servicios_mapper,
            petroleum_products_mapper,
            payroll_tax_mapper,
            minimum_fiscal_fee_mapper,
            general_tax_mapper,
            tax_settlement_mapper
        )

        mappers = [
            iva_form_mapper,
            retencion_servicios_mapper,
            petroleum_products_mapper,
            payroll_tax_mapper,
            minimum_fiscal_fee_mapper,
            general_tax_mapper,
            tax_settlement_mapper
        ]

        for mapper in mappers:
            assert mapper is not None
            assert hasattr(mapper, 'get_form_type')
            assert hasattr(mapper, 'get_field_mapping')
            assert hasattr(mapper, 'map')
