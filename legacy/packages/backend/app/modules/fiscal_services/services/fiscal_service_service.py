"""
Fiscal Service Service - Business logic for fiscal services management

Handles complex operations:
- Creating fiscal services with documents, procedures, keywords, and translations
- Updating services with cascading updates
- Managing service assignments

IMPORTANT CLARIFICATIONS:

1. **KEYWORDS** (service_keywords):
   - Purpose: SEARCH ONLY
   - Improve search functionality in multiple languages
   - Example: "Permiso de Residencia" has keywords:
     * Spanish: "residencia", "permiso", "temporal"
     * English: "residence", "permit", "temporary"
     * French: "résidence", "permis", "temporaire"
   - Users searching "residence" will find "Permiso de Residencia"

2. **TRANSLATIONS** (entity_translations):
   - Purpose: WEBSITE UI LANGUAGE ONLY
   - Display entity info in user's preferred interface language
   - Example: User selects French UI → shows "Permis de Résidence"
   - NOT used for search or user-generated content
   - Source data is always in Spanish (name_es, description_es)
   - Translations provide French/English/Portuguese UI versions

3. **DOCUMENT/PROCEDURE ASSIGNMENTS**:
   - Link services to required documents and procedures
   - Specify if required for expedition vs renewal
   - Control display order in UI
"""

import json
from typing import Optional, List, Dict, Any
from loguru import logger
import asyncpg

from app.modules.fiscal_services.models import (
    FiscalServiceCreate,
    FiscalServiceUpdate,
    FiscalServiceResponse,
    ServiceDocumentAssignmentCreate,
    ServiceProcedureAssignmentCreate,
    ServiceKeywordCreate,
    EntityTranslationCreate,
)


class FiscalServiceService:
    """Service for fiscal service business logic"""

    async def create_fiscal_service(
        self,
        conn: asyncpg.Connection,
        service: FiscalServiceCreate,
        document_assignments: Optional[List[ServiceDocumentAssignmentCreate]] = None,
        procedure_assignments: Optional[List[ServiceProcedureAssignmentCreate]] = None,
        keywords: Optional[List[ServiceKeywordCreate]] = None,
        translations: Optional[List[EntityTranslationCreate]] = None,
    ) -> Dict[str, Any]:
        """
        Create a fiscal service with all related entities in a transaction

        Args:
            conn: Database connection
            service: Fiscal service data
            document_assignments: Optional list of document assignments
            procedure_assignments: Optional list of procedure assignments
            keywords: Optional list of keywords
            translations: Optional list of translations

        Returns:
            Created fiscal service with all related data

        Raises:
            ValueError: If validation fails
            asyncpg.PostgresError: If database operation fails
        """
        # Start transaction (caller should handle this)
        logger.info(f"Creating fiscal service: {service.service_code}")

        # 1. Create the fiscal service
        # Column names match database schema exactly (verified against information_schema)
        service_query = """
            INSERT INTO fiscal_services (
                service_code, category_id,
                name_es, description_es,
                service_type, calculation_method,
                tasa_expedicion, tasa_renovacion,
                base_percentage, percentage_of,
                unit_rate, unit_type,
                expedition_formula, expedition_unit_measure,
                renewal_formula, renewal_unit_measure,
                calculation_config, rate_tiers,
                tier_group_name, is_tier_component,
                validity_period_months, renewal_frequency_months,
                grace_period_days,
                late_penalty_percentage, late_penalty_fixed,
                penalty_calculation_rules,
                eligibility_criteria, exemption_conditions,
                parent_service_id,
                legal_reference, regulatory_articles,
                tariff_effective_from, tariff_effective_to,
                processing_time_days, priority, complexity_level,
                status,
                created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
                $31, $32, $33, $34, $35, $36, $37,
                NOW(), NOW()
            )
            RETURNING *
        """

        fiscal_service = await conn.fetchrow(
            service_query,
            service.service_code,                                                       # $1
            service.category_id,                                                        # $2
            service.name_es,                                                            # $3
            service.description_es,                                                     # $4
            service.service_type.value,                                                 # $5
            service.calculation_method.value,                                            # $6
            service.tasa_expedicion,                                                     # $7
            service.tasa_renovacion,                                                     # $8
            service.base_percentage,                                                     # $9
            service.percentage_of,                                                       # $10
            service.unit_rate,                                                           # $11
            service.unit_type,                                                           # $12
            service.expedition_formula,                                                  # $13
            service.expedition_unit_measure,                                              # $14
            service.renewal_formula,                                                     # $15
            service.renewal_unit_measure,                                                 # $16
            json.dumps(service.calculation_config) if service.calculation_config else None,  # $17
            json.dumps(service.rate_tiers) if service.rate_tiers else None,               # $18
            service.tier_group_name,                                                     # $19
            service.is_tier_component,                                                   # $20
            service.validity_period_months,                                               # $21
            service.renewal_frequency_months,                                             # $22
            service.grace_period_days,                                                   # $23
            service.late_penalty_percentage,                                              # $24
            service.late_penalty_fixed,                                                  # $25
            json.dumps(service.penalty_calculation_rules) if service.penalty_calculation_rules else None,  # $26
            json.dumps(service.eligibility_criteria) if service.eligibility_criteria else None,  # $27
            json.dumps(service.exemption_conditions) if service.exemption_conditions else None,  # $28
            service.parent_service_id,                                                   # $29
            service.legal_reference,                                                     # $30
            service.regulatory_articles,                                                 # $31
            service.tariff_effective_from,                                                # $32
            service.tariff_effective_to,                                                  # $33
            service.processing_time_days,                                                # $34
            service.priority,                                                            # $35
            service.complexity_level,                                                    # $36
            service.status.value,                                                        # $37
        )

        service_id = fiscal_service["id"]
        logger.info(f"Created fiscal service ID: {service_id}")

        # 2. Create document assignments
        if document_assignments:
            for assignment in document_assignments:
                await self._create_document_assignment(
                    conn, service_id, assignment
                )
            logger.info(f"Created {len(document_assignments)} document assignments")

        # 3. Create procedure assignments
        if procedure_assignments:
            for assignment in procedure_assignments:
                await self._create_procedure_assignment(
                    conn, service_id, assignment
                )
            logger.info(f"Created {len(procedure_assignments)} procedure assignments")

        # 4. Create keywords
        if keywords:
            for keyword in keywords:
                await self._create_keyword(conn, service_id, keyword)
            logger.info(f"Created {len(keywords)} keywords")

        # 5. Create translations
        if translations:
            for translation in translations:
                await self._create_translation(
                    conn, service.service_code, translation
                )
            logger.info(f"Created {len(translations)} translations")

        # 6. Return complete service with all related data
        return await self.get_fiscal_service_complete(conn, service_id)

    async def update_fiscal_service(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        service: FiscalServiceUpdate,
        add_document_assignments: Optional[List[ServiceDocumentAssignmentCreate]] = None,
        remove_document_ids: Optional[List[int]] = None,
        add_procedure_assignments: Optional[List[ServiceProcedureAssignmentCreate]] = None,
        remove_procedure_ids: Optional[List[int]] = None,
        add_keywords: Optional[List[ServiceKeywordCreate]] = None,
        remove_keyword_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Update fiscal service with cascading updates

        Args:
            conn: Database connection
            service_id: Service ID to update
            service: Update data
            add_document_assignments: Documents to add
            remove_document_ids: Document assignment IDs to remove
            add_procedure_assignments: Procedures to add
            remove_procedure_ids: Procedure assignment IDs to remove
            add_keywords: Keywords to add
            remove_keyword_ids: Keyword IDs to remove

        Returns:
            Updated fiscal service with all related data
        """
        logger.info(f"Updating fiscal service ID: {service_id}")

        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 1

        for field, value in service.dict(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ${param_count}")
                # Handle enums
                if hasattr(value, "value"):
                    params.append(value.value)
                else:
                    params.append(value)
                param_count += 1

        if update_fields:
            update_fields.append(f"updated_at = NOW()")
            params.append(service_id)

            query = f"""
                UPDATE fiscal_services
                SET {", ".join(update_fields)}
                WHERE id = ${param_count}
                RETURNING *
            """
            await conn.fetchrow(query, *params)
            logger.info(f"Updated fiscal service fields: {update_fields}")

        # Handle document assignments
        if remove_document_ids:
            await conn.execute(
                "DELETE FROM service_document_assignments WHERE id = ANY($1)",
                remove_document_ids
            )
            logger.info(f"Removed {len(remove_document_ids)} document assignments")

        if add_document_assignments:
            for assignment in add_document_assignments:
                await self._create_document_assignment(
                    conn, service_id, assignment
                )
            logger.info(f"Added {len(add_document_assignments)} document assignments")

        # Handle procedure assignments
        if remove_procedure_ids:
            await conn.execute(
                "DELETE FROM service_procedure_assignments WHERE id = ANY($1)",
                remove_procedure_ids
            )
            logger.info(f"Removed {len(remove_procedure_ids)} procedure assignments")

        if add_procedure_assignments:
            for assignment in add_procedure_assignments:
                await self._create_procedure_assignment(
                    conn, service_id, assignment
                )
            logger.info(f"Added {len(add_procedure_assignments)} procedure assignments")

        # Handle keywords
        if remove_keyword_ids:
            await conn.execute(
                "DELETE FROM service_keywords WHERE id = ANY($1)",
                remove_keyword_ids
            )
            logger.info(f"Removed {len(remove_keyword_ids)} keywords")

        if add_keywords:
            for keyword in add_keywords:
                await self._create_keyword(conn, service_id, keyword)
            logger.info(f"Added {len(add_keywords)} keywords")

        return await self.get_fiscal_service_complete(conn, service_id)

    async def get_fiscal_service_complete(
        self,
        conn: asyncpg.Connection,
        service_id: int
    ) -> Dict[str, Any]:
        """
        Get fiscal service with all related data

        Returns a complete view including:
        - Basic service info
        - Document assignments
        - Procedure assignments
        - Keywords
        - Translations
        """
        # Get base service
        service = await conn.fetchrow(
            """
            SELECT fs.*, c.name_es as category_name
            FROM fiscal_services fs
            LEFT JOIN categories c ON c.id = fs.category_id
            WHERE fs.id = $1
            """,
            service_id
        )

        if not service:
            raise ValueError(f"Fiscal service {service_id} not found")

        result = dict(service)

        # Get document assignments
        doc_assignments = await conn.fetch(
            """
            SELECT sda.*, dt.document_name_es
            FROM service_document_assignments sda
            LEFT JOIN document_templates dt ON dt.id = sda.document_template_id
            WHERE sda.fiscal_service_id = $1
            ORDER BY sda.display_order
            """,
            service_id
        )
        result["document_assignments"] = [dict(d) for d in doc_assignments]

        # Get procedure assignments
        proc_assignments = await conn.fetch(
            """
            SELECT spa.*, pt.name_es as procedure_name
            FROM service_procedure_assignments spa
            LEFT JOIN procedure_templates pt ON pt.id = spa.template_id
            WHERE spa.fiscal_service_id = $1
            ORDER BY spa.display_order
            """,
            service_id
        )
        result["procedure_assignments"] = [dict(p) for p in proc_assignments]

        # Get keywords
        keywords = await conn.fetch(
            """
            SELECT *
            FROM service_keywords
            WHERE fiscal_service_id = $1
            ORDER BY weight DESC, keyword
            """,
            service_id
        )
        result["keywords"] = [dict(k) for k in keywords]

        # Get translations
        translations = await conn.fetch(
            """
            SELECT *
            FROM entity_translations
            WHERE entity_type = 'fiscal_service'
            AND entity_code = $1
            """,
            service["service_code"]
        )
        result["translations"] = [dict(t) for t in translations]

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # Private Helper Methods
    # ═══════════════════════════════════════════════════════════════════════

    async def _create_document_assignment(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        assignment: ServiceDocumentAssignmentCreate
    ) -> None:
        """Create a document assignment"""
        await conn.execute(
            """
            INSERT INTO service_document_assignments (
                fiscal_service_id, document_template_id,
                is_required_expedition, is_required_renewal,
                display_order, custom_notes, assigned_by, assigned_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """,
            service_id,
            assignment.document_template_id,
            assignment.is_required_expedition,
            assignment.is_required_renewal,
            assignment.display_order,
            assignment.custom_notes,
            assignment.assigned_by,
        )

    async def _create_procedure_assignment(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        assignment: ServiceProcedureAssignmentCreate
    ) -> None:
        """Create a procedure assignment"""
        await conn.execute(
            """
            INSERT INTO service_procedure_assignments (
                fiscal_service_id, template_id,
                applies_to, display_order, custom_notes,
                override_steps, assigned_by, assigned_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """,
            service_id,
            assignment.template_id,
            assignment.applies_to,
            assignment.display_order,
            assignment.custom_notes,
            assignment.override_steps,
            assignment.assigned_by,
        )

    async def _create_keyword(
        self,
        conn: asyncpg.Connection,
        service_id: int,
        keyword: ServiceKeywordCreate
    ) -> None:
        """Create a keyword"""
        await conn.execute(
            """
            INSERT INTO service_keywords (
                fiscal_service_id, keyword, language_code,
                weight, is_auto_generated, created_at
            )
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (fiscal_service_id, keyword, language_code) DO NOTHING
            """,
            service_id,
            keyword.keyword.lower(),
            keyword.language_code,
            keyword.weight,
            keyword.is_auto_generated,
        )

    async def _create_translation(
        self,
        conn: asyncpg.Connection,
        entity_code: str,
        translation: EntityTranslationCreate
    ) -> None:
        """Create a translation"""
        await conn.execute(
            """
            INSERT INTO entity_translations (
                entity_type, entity_code, language_code, field_name,
                translation_text, translation_source, translation_quality,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            ON CONFLICT (entity_type, entity_code, language_code, field_name)
            DO UPDATE SET
                translation_text = EXCLUDED.translation_text,
                translation_source = EXCLUDED.translation_source,
                translation_quality = EXCLUDED.translation_quality,
                updated_at = NOW()
            """,
            translation.entity_type.value,
            entity_code,
            translation.language_code,
            translation.field_name,
            translation.translation_text,
            translation.translation_source,
            translation.translation_quality,
        )
