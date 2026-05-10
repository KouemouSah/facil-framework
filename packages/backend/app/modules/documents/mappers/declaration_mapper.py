"""
Declaration Form Mappers
Maps extracted fiscal declaration data to frontend forms

Author: Claude Code
Date: 2025-11-13
Version: 3.0 - All declaration form mapping (IVA, Retención, Petroleum, Payroll, etc.)
"""

from typing import Dict, Any, Optional
from app.modules.documents.mappers.base import BaseFormMapper


class IVAFormMapper(BaseFormMapper):
    """
    Maps IVA extraction data to FormIVA fields

    Frontend form: FormIVA (React component)
    """

    def get_form_type(self) -> str:
        return "declaration_iva"

    def get_field_mapping(self) -> Dict[str, str]:
        """
        Map extractor fields to FormIVA fields

        Returns:
            Mapping dict: extractor_field -> form_field
        """
        return {
            # Identification
            "nif": "nif",
            "empresa": "empresa_nombre",
            "ejercicio": "ejercicio",
            "periodo": "periodo",
            "fecha": "fecha_presentacion",
            "auto_liquidacion_num": "auto_liquidacion_numero",

            # Régimen General (01-03)
            "base_imponible_general": "regimen_general_base",
            "tipo_general": "regimen_general_tipo",
            "cuota_general": "regimen_general_cuota",

            # Régimen Reducido 1 (04-06)
            "base_imponible_reducido1": "regimen_reducido1_base",
            "tipo_reducido1": "regimen_reducido1_tipo",
            "cuota_reducido1": "regimen_reducido1_cuota",

            # Régimen Reducido 2 (07-09)
            "base_imponible_reducido2": "regimen_reducido2_base",
            "tipo_reducido2": "regimen_reducido2_tipo",
            "cuota_reducido2": "regimen_reducido2_cuota",

            # Total
            "total_ingresar": "total_a_ingresar"
        }

    def _transform_value(
        self,
        form_field: str,
        value: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> Any:
        """Transform value for IVA form"""

        # Currency fields: ensure float format
        if any(keyword in form_field for keyword in ["base", "cuota", "total"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
            return value

        # Percentage fields: ensure float format
        if "tipo" in form_field:
            if isinstance(value, (int, float)):
                return round(value, 2)
            return value

        # Periodo: normalize to "1T", "2T", etc.
        if form_field == "periodo":
            periodo = str(value).upper()
            if periodo.isdigit():
                month = int(periodo)
                if month <= 12:
                    # Monthly to quarterly
                    trimestre = ((month - 1) // 3) + 1
                    return f"{trimestre}T"
                return periodo
            return periodo

        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate IVA derived fields"""
        derived = {}

        # Calculate total IVA if all cuotas are present
        cuotas = []
        for field in ["regimen_general_cuota", "regimen_reducido1_cuota", "regimen_reducido2_cuota"]:
            if field in pre_filled_fields:
                try:
                    cuotas.append(float(pre_filled_fields[field]))
                except:
                    pass

        if cuotas:
            derived["total_cuotas_iva"] = round(sum(cuotas), 2)

        # Verify cuota calculations
        for regime in ["general", "reducido1", "reducido2"]:
            base_field = f"regimen_{regime}_base"
            tipo_field = f"regimen_{regime}_tipo"
            cuota_field = f"regimen_{regime}_cuota"

            if all(f in pre_filled_fields for f in [base_field, tipo_field]):
                try:
                    base = float(pre_filled_fields[base_field])
                    tipo = float(pre_filled_fields[tipo_field])
                    calculated_cuota = base * (tipo / 100)

                    derived[f"regimen_{regime}_cuota_calculated"] = round(calculated_cuota, 2)
                except:
                    pass

        return derived


class IRPFFormMapper(BaseFormMapper):
    """
    Maps IRPF extraction data to FormIRPF fields

    Frontend form: FormIRPF (React component)
    """

    def get_form_type(self) -> str:
        return "declaration_irpf"

    def get_field_mapping(self) -> Dict[str, str]:
        """
        Map extractor fields to FormIRPF fields

        Returns:
            Mapping dict: extractor_field -> form_field
        """
        return {
            # Identification
            "nif": "nif",
            "nombre_completo": "nombre_completo",
            "ejercicio": "ejercicio",

            # Income
            "rendimientos_trabajo": "rendimientos_trabajo",
            "rendimientos_actividades": "rendimientos_actividades_economicas",
            "rendimientos_capital": "rendimientos_capital",

            # Base
            "base_imponible": "base_imponible_general",

            # Deductions
            "deducciones_familiares": "deduccion_minimo_personal",
            "deducciones_vivienda": "deduccion_vivienda_habitual",

            # Result
            "cuota_integra": "cuota_integra",
            "tipo_gravamen": "tipo_medio_gravamen",
            "resultado_declaracion": "resultado_declaracion"
        }

    def _transform_value(
        self,
        form_field: str,
        value: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> Any:
        """Transform value for IRPF form"""

        # Currency fields: ensure float format
        if any(keyword in form_field for keyword in ["rendimientos", "base", "cuota", "deducc", "resultado"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
            return value

        # Percentage fields: ensure float format
        if "tipo" in form_field or "gravamen" in form_field:
            if isinstance(value, (int, float)):
                return round(value, 2)
            return value

        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate IRPF derived fields"""
        derived = {}

        # Calculate total income
        income_fields = [
            "rendimientos_trabajo",
            "rendimientos_actividades_economicas",
            "rendimientos_capital"
        ]

        total_income = 0.0
        for field in income_fields:
            if field in pre_filled_fields:
                try:
                    total_income += float(pre_filled_fields[field])
                except:
                    pass

        if total_income > 0:
            derived["total_ingresos"] = round(total_income, 2)

        # Calculate total deductions
        deduction_fields = [
            "deduccion_minimo_personal",
            "deduccion_vivienda_habitual"
        ]

        total_deductions = 0.0
        for field in deduction_fields:
            if field in pre_filled_fields:
                try:
                    total_deductions += float(pre_filled_fields[field])
                except:
                    pass

        if total_deductions > 0:
            derived["total_deducciones"] = round(total_deductions, 2)

        return derived


class RetencionServiciosFormMapper(BaseFormMapper):
    """
    Maps Retención sobre Servicios data (Articles 3, 5, 10) to frontend form
    Covers: Non-resident services retention (Petrolero & Sec. Común)
    """

    def get_form_type(self) -> str:
        return "declaration_retencion_servicios"

    def get_field_mapping(self) -> Dict[str, str]:
        return {
            # Identification
            "nif": "nif",
            "representacion_empresa": "empresa_nombre",
            "ejercicio": "ejercicio",
            "periodo": "periodo",
            "fecha": "fecha_presentacion",
            "auto_liquidacion_num": "auto_liquidacion_numero",
            "municipio": "municipio",
            "direccion_fiscal": "direccion_fiscal",
            "provincia": "provincia",

            # Amount ingressed
            "cantidad_ingresada": "cantidad_ingresada",

            # Services retention calculation
            "servicios_sujetos_base": "base_imponible",
            "servicios_sujetos_tipo": "tipo_retencion",
            "servicios_sujetos_cuota": "cuota_retencion",
            "total_a_ingresar": "total_a_ingresar"
        }

    def _transform_value(self, form_field: str, value: Any, metadata: Optional[Dict[str, Any]]) -> Any:
        """Transform value for Retención form"""
        # Currency fields
        if any(kw in form_field for kw in ["base", "cuota", "total", "cantidad"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
        # Percentage fields
        if "tipo" in form_field or "retencion" in form_field:
            if isinstance(value, (int, float)):
                return round(value, 2)
        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate retention derived fields"""
        derived = {}

        # Verify cuota calculation
        if all(f in pre_filled_fields for f in ["base_imponible", "tipo_retencion"]):
            try:
                base = float(pre_filled_fields["base_imponible"])
                tipo = float(pre_filled_fields["tipo_retencion"])
                calculated_cuota = base * (tipo / 100)
                derived["cuota_retencion_calculated"] = round(calculated_cuota, 2)
            except:
                pass

        return derived


class PetroleumProductsFormMapper(BaseFormMapper):
    """
    Maps Impuesto sobre Productos Petroleros (IVS, FMI) to frontend form
    """

    def get_form_type(self) -> str:
        return "declaration_productos_petroleros"

    def get_field_mapping(self) -> Dict[str, str]:
        return {
            "nif": "nif",
            "representacion_empresa": "empresa_nombre",
            "ejercicio": "ejercicio",
            "periodo": "periodo",
            "fecha": "fecha_presentacion",
            "prod_sujetos_precio": "productos_precio",
            "prod_sujetos_cuota": "productos_cuota",
            "prod_sujetos_total": "productos_total_devengado",
            "total_a_ingresar": "total_a_ingresar"
        }

    def _transform_value(self, form_field: str, value: Any, metadata: Optional[Dict[str, Any]]) -> Any:
        """Transform value for Petroleum Products form"""
        if any(kw in form_field for kw in ["precio", "cuota", "total"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
        return value


class PayrollTaxFormMapper(BaseFormMapper):
    """
    Maps Impuesto sobre Sueldos y Salarios (Payroll tax) to frontend form
    """

    def get_form_type(self) -> str:
        return "declaration_sueldos_salarios"

    def get_field_mapping(self) -> Dict[str, str]:
        return {
            "nif": "nif",
            "representacion_empresa": "empresa_nombre",
            "ejercicio": "ejercicio",
            "periodo": "periodo",
            "fecha": "fecha_presentacion",
            "importe_total_retenidas": "importe_retenido",
            "recargos": "recargos",
            "intereses_demora": "intereses_demora",
            "total_a_ingresar": "total_a_ingresar"
        }

    def _transform_value(self, form_field: str, value: Any, metadata: Optional[Dict[str, Any]]) -> Any:
        """Transform value for Payroll Tax form"""
        if any(kw in form_field for kw in ["importe", "recargo", "interes", "total"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate payroll tax derived fields"""
        derived = {}

        # Calculate total from components
        components = ["importe_retenido", "recargos", "intereses_demora"]
        total = 0.0
        found_any = False

        for field in components:
            if field in pre_filled_fields:
                try:
                    total += float(pre_filled_fields[field])
                    found_any = True
                except:
                    pass

        if found_any:
            derived["total_calculado"] = round(total, 2)

        return derived


class MinimumFiscalFeeFormMapper(BaseFormMapper):
    """
    Maps Cuota Mínima Fiscal to frontend form
    """

    def get_form_type(self) -> str:
        return "declaration_cuota_minima"

    def get_field_mapping(self) -> Dict[str, str]:
        return {
            "nif": "nif",
            "representacion_empresa": "empresa_nombre",
            "ejercicio": "ejercicio",
            "periodo": "periodo",
            "fecha": "fecha_presentacion",
            "base_imponible": "base_imponible",
            "reducciones": "reducciones",
            "base_liquidable": "base_liquidable",
            "tipo_de_gravamen": "tipo_gravamen",
            "cuota": "cuota",
            "a_ingresar": "total_a_ingresar"
        }

    def _transform_value(self, form_field: str, value: Any, metadata: Optional[Dict[str, Any]]) -> Any:
        """Transform value for Minimum Fiscal Fee form"""
        if any(kw in form_field for kw in ["base", "reduccion", "cuota", "ingresar"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
        if "tipo" in form_field or "gravamen" in form_field:
            if isinstance(value, (int, float)):
                return round(value, 2)
        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate minimum fiscal fee derived fields"""
        derived = {}

        # Calculate base_liquidable
        if "base_imponible" in pre_filled_fields and "reducciones" in pre_filled_fields:
            try:
                base = float(pre_filled_fields["base_imponible"])
                reduc = float(pre_filled_fields.get("reducciones", 0))
                derived["base_liquidable_calculated"] = round(base - reduc, 2)
            except:
                pass

        # Calculate cuota
        if "base_liquidable" in pre_filled_fields and "tipo_gravamen" in pre_filled_fields:
            try:
                base_liq = float(pre_filled_fields["base_liquidable"])
                tipo = float(pre_filled_fields["tipo_gravamen"])
                derived["cuota_calculated"] = round(base_liq * (tipo / 100), 2)
            except:
                pass

        return derived


class GeneralTaxFormMapper(BaseFormMapper):
    """
    Maps Impreso Común (General tax declaration) to frontend form
    """

    def get_form_type(self) -> str:
        return "declaration_impreso_comun"

    def get_field_mapping(self) -> Dict[str, str]:
        return {
            "nif": "nif",
            "representacion_empresa": "empresa_nombre",
            "ejercicio": "ejercicio",
            "periodo": "periodo",
            "fecha": "fecha_presentacion",
            "base_imponible": "base_imponible",
            "tipo_de_gravamen": "tipo_gravamen",
            "cuota": "cuota",
            "a_ingresar": "total_a_ingresar"
        }

    def _transform_value(self, form_field: str, value: Any, metadata: Optional[Dict[str, Any]]) -> Any:
        """Transform value for General Tax form"""
        if any(kw in form_field for kw in ["base", "cuota", "ingresar"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
        if "tipo" in form_field or "gravamen" in form_field:
            if isinstance(value, (int, float)):
                return round(value, 2)
        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate general tax derived fields"""
        derived = {}

        # Verify cuota calculation
        if "base_imponible" in pre_filled_fields and "tipo_gravamen" in pre_filled_fields:
            try:
                base = float(pre_filled_fields["base_imponible"])
                tipo = float(pre_filled_fields["tipo_gravamen"])
                derived["cuota_calculated"] = round(base * (tipo / 100), 2)
            except:
                pass

        return derived


class TaxSettlementFormMapper(BaseFormMapper):
    """
    Maps Impreso de Liquidación (Tax settlement) to frontend form
    """

    def get_form_type(self) -> str:
        return "declaration_impreso_liquidacion"

    def get_field_mapping(self) -> Dict[str, str]:
        return {
            "nif": "nif",
            "representacion_empresa": "empresa_nombre",
            "ejercicio": "ejercicio",
            "periodo": "periodo",
            "fecha": "fecha_presentacion",
            "base_imponible": "base_imponible",
            "tipo_gravamen": "tipo_gravamen",
            "cuota": "cuota",
            "deducciones_periodo": "deducciones_periodo",
            "deducciones_anteriores": "deducciones_anteriores",
            "recargo": "recargo",
            "interes_demora": "interes_demora",
            "sanciones": "sanciones",
            "total_a_ingresar": "total_a_ingresar"
        }

    def _transform_value(self, form_field: str, value: Any, metadata: Optional[Dict[str, Any]]) -> Any:
        """Transform value for Tax Settlement form"""
        if any(kw in form_field for kw in ["base", "cuota", "deduccion", "recargo", "interes", "sancion", "total"]):
            if isinstance(value, (int, float)):
                return round(value, 2)
        if "tipo" in form_field or "gravamen" in form_field:
            if isinstance(value, (int, float)):
                return round(value, 2)
        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate tax settlement derived fields"""
        derived = {}

        # Verify cuota calculation
        if "base_imponible" in pre_filled_fields and "tipo_gravamen" in pre_filled_fields:
            try:
                base = float(pre_filled_fields["base_imponible"])
                tipo = float(pre_filled_fields["tipo_gravamen"])
                derived["cuota_calculated"] = round(base * (tipo / 100), 2)
            except:
                pass

        # Calculate total deductions
        deduction_fields = ["deducciones_periodo", "deducciones_anteriores"]
        total_deduc = 0.0
        found_any = False

        for field in deduction_fields:
            if field in pre_filled_fields:
                try:
                    total_deduc += float(pre_filled_fields[field])
                    found_any = True
                except:
                    pass

        if found_any:
            derived["total_deducciones"] = round(total_deduc, 2)

        # Calculate total charges (recargo + interes + sanciones)
        charge_fields = ["recargo", "interes_demora", "sanciones"]
        total_charges = 0.0
        found_any_charge = False

        for field in charge_fields:
            if field in pre_filled_fields:
                try:
                    total_charges += float(pre_filled_fields[field])
                    found_any_charge = True
                except:
                    pass

        if found_any_charge:
            derived["total_recargos"] = round(total_charges, 2)

        return derived


# Singleton instances
iva_form_mapper = IVAFormMapper()
irpf_form_mapper = IRPFFormMapper()
retencion_servicios_mapper = RetencionServiciosFormMapper()
petroleum_products_mapper = PetroleumProductsFormMapper()
payroll_tax_mapper = PayrollTaxFormMapper()
minimum_fiscal_fee_mapper = MinimumFiscalFeeFormMapper()
general_tax_mapper = GeneralTaxFormMapper()
tax_settlement_mapper = TaxSettlementFormMapper()
