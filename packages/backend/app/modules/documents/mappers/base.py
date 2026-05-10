"""
Base Form Mapper for TaxasGE Documents
Maps extracted data to frontend form fields

Author: Claude Code
Date: 2025-11-13
Version: 2.0 - Form mapping for frontend pre-fill
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class FormMappingResult(BaseModel):
    """Result of form mapping"""
    success: bool = Field(..., description="Mapping success status")
    form_type: str = Field(..., description="Target form type (declaration_iva, declaration_irpf, etc.)")
    pre_filled_fields: Dict[str, Any] = Field(default_factory=dict, description="Fields to pre-fill in frontend")
    fields_confidence: Dict[str, float] = Field(default_factory=dict, description="Confidence per field")
    mapping_quality: Dict[str, Any] = Field(default_factory=dict, description="Quality metrics")
    unmapped_fields: List[str] = Field(default_factory=list, description="Extracted fields not mapped")
    warnings: List[str] = Field(default_factory=list, description="Mapping warnings")


class BaseFormMapper(ABC):
    """
    Abstract base class for form mappers

    Mappers convert extracted OCR data to frontend form structure
    """

    @abstractmethod
    def get_form_type(self) -> str:
        """
        Get the target form type this mapper handles

        Returns:
            Form type identifier (e.g., "declaration_iva")
        """
        pass

    @abstractmethod
    def get_field_mapping(self) -> Dict[str, str]:
        """
        Get the mapping from extracted field names to form field names

        Returns:
            Dict mapping extracted_field_name -> form_field_name
        """
        pass

    async def map(
        self,
        extracted_data: Dict[str, Any],
        field_confidences: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> FormMappingResult:
        """
        Map extracted data to form fields

        Args:
            extracted_data: Extracted data from document
            field_confidences: Confidence scores per field
            metadata: Optional metadata

        Returns:
            FormMappingResult with pre-filled fields
        """
        try:
            form_type = self.get_form_type()
            field_mapping = self.get_field_mapping()

            pre_filled_fields = {}
            mapped_confidences = {}
            unmapped_fields = []
            warnings = []

            # Map each extracted field to form field
            for extracted_field, value in extracted_data.items():
                if extracted_field in field_mapping:
                    form_field = field_mapping[extracted_field]

                    # Transform value if needed
                    transformed_value = self._transform_value(
                        form_field,
                        value,
                        metadata
                    )

                    pre_filled_fields[form_field] = transformed_value
                    mapped_confidences[form_field] = field_confidences.get(extracted_field, 0.5)
                else:
                    unmapped_fields.append(extracted_field)

            # Add derived fields if applicable
            derived_fields = self._calculate_derived_fields(pre_filled_fields)
            pre_filled_fields.update(derived_fields)

            # Calculate mapping quality
            mapping_quality = self._calculate_mapping_quality(
                extracted_data,
                pre_filled_fields,
                mapped_confidences
            )

            return FormMappingResult(
                success=len(pre_filled_fields) > 0,
                form_type=form_type,
                pre_filled_fields=pre_filled_fields,
                fields_confidence=mapped_confidences,
                mapping_quality=mapping_quality,
                unmapped_fields=unmapped_fields,
                warnings=warnings
            )

        except Exception as e:
            return FormMappingResult(
                success=False,
                form_type=self.get_form_type(),
                warnings=[f"Mapping error: {str(e)}"]
            )

    def _transform_value(
        self,
        form_field: str,
        value: Any,
        metadata: Optional[Dict[str, Any]]
    ) -> Any:
        """
        Transform extracted value to form field format

        Args:
            form_field: Form field name
            value: Extracted value
            metadata: Optional metadata

        Returns:
            Transformed value suitable for frontend
        """
        # Override in subclasses for field-specific transformations
        return value

    def _calculate_derived_fields(self, pre_filled_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate derived fields from pre-filled fields

        Args:
            pre_filled_fields: Already mapped fields

        Returns:
            Dict of derived fields
        """
        # Override in subclasses for form-specific calculations
        return {}

    def _calculate_mapping_quality(
        self,
        extracted_data: Dict[str, Any],
        pre_filled_fields: Dict[str, Any],
        confidences: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Calculate mapping quality metrics

        Args:
            extracted_data: Original extracted data
            pre_filled_fields: Mapped form fields
            confidences: Field confidences

        Returns:
            Quality metrics
        """
        total_extracted = len(extracted_data)
        total_mapped = len(pre_filled_fields)
        avg_confidence = sum(confidences.values()) / len(confidences) if confidences else 0.0

        # Overall score: 50% coverage + 50% confidence
        coverage = total_mapped / total_extracted if total_extracted > 0 else 0
        overall_score = (coverage * 0.5) + (avg_confidence * 0.5)

        return {
            "overall_score": round(overall_score, 3),
            "coverage": round(coverage, 3),
            "avg_confidence": round(avg_confidence, 3),
            "fields_extracted": total_extracted,
            "fields_mapped": total_mapped,
            "mapping_completeness": f"{total_mapped}/{total_extracted}"
        }
