"""
Category Metadata - Localized labels and table associations for system translation categories

This module provides metadata for translation categories including:
- Group classification (domain: users, declarations, payments, etc.)
- Localized labels (ES, FR, EN)
- Database table association
- Field/column associations
- Description

Used by the /categories endpoint to return enriched category information.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


# =============================================================================
# GROUP DEFINITIONS
# =============================================================================
# Groups are based on:
# 1. PostgreSQL ENUM types (from DATABASE_SCHEMA_REFERENCE.md) - for DB enums
# 2. Functional groups - for non-enum categories (UI, forms, messages)
#
# The group field in CategoryMetadata uses db_enum when available,
# otherwise uses a functional group name.

# Functional groups for non-enum translations
FUNCTIONAL_GROUPS: Dict[str, Dict[str, str]] = {
    "ui": {
        "label_es": "Interfaz de Usuario",
        "label_fr": "Interface Utilisateur",
        "label_en": "User Interface",
    },
    "forms": {
        "label_es": "Formularios",
        "label_fr": "Formulaires",
        "label_en": "Forms",
    },
    "messages": {
        "label_es": "Mensajes del Sistema",
        "label_fr": "Messages Système",
        "label_en": "System Messages",
    },
    "notifications": {
        "label_es": "Notificaciones",
        "label_fr": "Notifications",
        "label_en": "Notifications",
    },
    "chatbot": {
        "label_es": "Chatbot",
        "label_fr": "Chatbot",
        "label_en": "Chatbot",
    },
    "other": {
        "label_es": "Otros",
        "label_fr": "Autres",
        "label_en": "Other",
    },
}

# PostgreSQL ENUM types with localized labels
# Based on DATABASE_SCHEMA_REFERENCE.md - Section 2: ENUM TYPES
DB_ENUM_GROUPS: Dict[str, Dict[str, str]] = {
    "user_role_enum": {
        "label_es": "Rol de Usuario",
        "label_fr": "Rôle Utilisateur",
        "label_en": "User Role",
        "table": "users",
        "column": "role",
    },
    "user_status_enum": {
        "label_es": "Estado de Usuario",
        "label_fr": "Statut Utilisateur",
        "label_en": "User Status",
        "table": "users",
        "column": "status",
    },
    "declaration_status_enum": {
        "label_es": "Estado de Declaración",
        "label_fr": "Statut de Déclaration",
        "label_en": "Declaration Status",
        "table": "declarations",
        "column": "status",
    },
    "declaration_type_enum": {
        "label_es": "Tipo de Declaración",
        "label_fr": "Type de Déclaration",
        "label_en": "Declaration Type",
        "table": "declarations",
        "column": "declaration_type",
    },
    "payment_status_enum": {
        "label_es": "Estado de Pago",
        "label_fr": "Statut de Paiement",
        "label_en": "Payment Status",
        "table": "payments",
        "column": "status",
    },
    "payment_method_enum": {
        "label_es": "Método de Pago",
        "label_fr": "Méthode de Paiement",
        "label_en": "Payment Method",
        "table": "payments",
        "column": "payment_method",
    },
    "payment_type_enum": {
        "label_es": "Tipo de Pago",
        "label_fr": "Type de Paiement",
        "label_en": "Payment Type",
        "table": "payments",
        "column": "payment_type",
    },
    "service_status_enum": {
        "label_es": "Estado de Servicio",
        "label_fr": "Statut de Service",
        "label_en": "Service Status",
        "table": "fiscal_services",
        "column": "status",
    },
    "service_type_enum": {
        "label_es": "Tipo de Servicio",
        "label_fr": "Type de Service",
        "label_en": "Service Type",
        "table": "fiscal_services",
        "column": "service_type",
    },
    "calculation_method_enum": {
        "label_es": "Método de Cálculo",
        "label_fr": "Méthode de Calcul",
        "label_en": "Calculation Method",
        "table": "fiscal_services",
        "column": "calculation_method",
    },
    "company_role_enum": {
        "label_es": "Rol en Empresa",
        "label_fr": "Rôle Entreprise",
        "label_en": "Company Role",
        "table": "user_company_memberships",
        "column": "role",
    },
    "assignment_status_enum": {
        "label_es": "Estado de Asignación",
        "label_fr": "Statut d'Assignation",
        "label_en": "Assignment Status",
        "table": "agent_assignments",
        "column": "status",
    },
    "agent_action_type_enum": {
        "label_es": "Tipo de Acción de Agente",
        "label_fr": "Type d'Action Agent",
        "label_en": "Agent Action Type",
        "table": "agent_actions",
        "column": "action_type",
    },
    "agent_availability_enum": {
        "label_es": "Disponibilidad de Agente",
        "label_fr": "Disponibilité Agent",
        "label_en": "Agent Availability",
        "table": "agents",
        "column": "availability",
    },
    "assignment_method_enum": {
        "label_es": "Método de Asignación",
        "label_fr": "Méthode d'Assignation",
        "label_en": "Assignment Method",
        "table": "assignment_rules",
        "column": "method",
    },
    "reassignment_reason_enum": {
        "label_es": "Razón de Reasignación",
        "label_fr": "Raison de Réassignation",
        "label_en": "Reassignment Reason",
        "table": "agent_assignments",
        "column": "reassignment_reason",
    },
    "attachment_type_enum": {
        "label_es": "Tipo de Adjunto",
        "label_fr": "Type de Pièce Jointe",
        "label_en": "Attachment Type",
        "table": "declaration_attachments",
        "column": "attachment_type",
    },
    "notification_priority_enum": {
        "label_es": "Prioridad de Notificación",
        "label_fr": "Priorité de Notification",
        "label_en": "Notification Priority",
        "table": "notifications",
        "column": "priority",
    },
    "ocr_engine_enum": {
        "label_es": "Motor OCR",
        "label_fr": "Moteur OCR",
        "label_en": "OCR Engine",
        "table": "document_ocr_results",
        "column": "engine",
    },
    "rule_status_enum": {
        "label_es": "Estado de Regla",
        "label_fr": "Statut de Règle",
        "label_en": "Rule Status",
        "table": "assignment_rules",
        "column": "status",
    },
}

# Combined groups (for API response)
def get_all_groups(language: str = "es") -> List[Dict]:
    """Get all groups (enum + functional) with localized labels"""
    groups = []

    # Add DB enum groups
    for code, info in DB_ENUM_GROUPS.items():
        label_key = f"label_{language}" if f"label_{language}" in info else "label_es"
        groups.append({
            "code": code,
            "label": info.get(label_key, info.get("label_es", code)),
            "type": "enum",
            "table": info.get("table"),
            "column": info.get("column"),
        })

    # Add functional groups
    for code, info in FUNCTIONAL_GROUPS.items():
        label_key = f"label_{language}" if f"label_{language}" in info else "label_es"
        groups.append({
            "code": code,
            "label": info.get(label_key, info.get("label_es", code)),
            "type": "functional",
            "table": None,
            "column": None,
        })

    return groups


def get_categories_for_group(group_code: str) -> List[str]:
    """
    Get all category codes that belong to a specific group.

    Args:
        group_code: The group code (enum type or functional group)

    Returns:
        List of category codes belonging to this group
    """
    categories = []

    for cat_code, metadata in CATEGORY_METADATA.items():
        # Get effective group (db_enum if exists, otherwise functional group)
        effective_group = metadata.db_enum if metadata.db_enum else metadata.group
        if effective_group == group_code:
            categories.append(cat_code)

    return categories


@dataclass
class CategoryMetadata:
    """Metadata for a translation category"""
    code: str  # Category code (e.g., "enum.user_role")
    group: str  # Group/domain (users, declarations, payments, etc.)
    label_es: str  # Spanish label
    label_fr: str  # French label
    label_en: str  # English label
    description_es: str  # Spanish description
    description_fr: str  # French description
    description_en: str  # English description
    db_table: Optional[str] = None  # Associated database table
    db_column: Optional[str] = None  # Associated column/field
    db_enum: Optional[str] = None  # Associated PostgreSQL ENUM type


# Category metadata registry
# Organized by category type: enum.*, ui.*, form.*, message.*, etc.
CATEGORY_METADATA: Dict[str, CategoryMetadata] = {
    # ==========================================================================
    # ENUM TRANSLATIONS - PostgreSQL ENUM types - USERS GROUP
    # ==========================================================================

    "enum.user_role": CategoryMetadata(
        code="enum.user_role",
        group="users",
        label_es="Rol de usuario",
        label_fr="Rôle d'utilisateur",
        label_en="User role",
        description_es="Valores del enum user_role_enum: admin, agent, supervisor, user, guest",
        description_fr="Valeurs de l'énumération user_role_enum: admin, agent, supervisor, user, guest",
        description_en="Values for user_role_enum: admin, agent, supervisor, user, guest",
        db_table="users",
        db_column="role",
        db_enum="user_role_enum",
    ),

    "enum.user_status": CategoryMetadata(
        code="enum.user_status",
        group="users",
        label_es="Estado de usuario",
        label_fr="Statut d'utilisateur",
        label_en="User status",
        description_es="Valores del enum user_status_enum: active, inactive, suspended, pending_verification",
        description_fr="Valeurs de l'énumération user_status_enum: active, inactive, suspended, pending_verification",
        description_en="Values for user_status_enum: active, inactive, suspended, pending_verification",
        db_table="users",
        db_column="status",
        db_enum="user_status_enum",
    ),

    # ==========================================================================
    # ENUM TRANSLATIONS - DECLARATIONS GROUP
    # ==========================================================================

    "enum.declaration_status": CategoryMetadata(
        code="enum.declaration_status",
        group="declarations",
        label_es="Estado de declaración",
        label_fr="Statut de déclaration",
        label_en="Declaration status",
        description_es="Valores del enum declaration_status_enum: draft, submitted, under_review, validated, rejected, paid, archived",
        description_fr="Valeurs de l'énumération declaration_status_enum: draft, submitted, under_review, validated, rejected, paid, archived",
        description_en="Values for declaration_status_enum: draft, submitted, under_review, validated, rejected, paid, archived",
        db_table="declarations",
        db_column="status",
        db_enum="declaration_status_enum",
    ),

    "enum.declaration_type": CategoryMetadata(
        code="enum.declaration_type",
        group="declarations",
        label_es="Tipo de declaración",
        label_fr="Type de déclaration",
        label_en="Declaration type",
        description_es="Valores del enum declaration_type_enum: income_tax, vat, property_tax, etc.",
        description_fr="Valeurs de l'énumération declaration_type_enum: income_tax, vat, property_tax, etc.",
        description_en="Values for declaration_type_enum: income_tax, vat, property_tax, etc.",
        db_table="declarations",
        db_column="declaration_type",
        db_enum="declaration_type_enum",
    ),

    # ==========================================================================
    # ENUM TRANSLATIONS - PAYMENTS GROUP
    # ==========================================================================

    "enum.payment_status": CategoryMetadata(
        code="enum.payment_status",
        group="payments",
        label_es="Estado de pago",
        label_fr="Statut de paiement",
        label_en="Payment status",
        description_es="Valores del enum payment_status_enum: pending, processing, completed, failed, refunded, cancelled",
        description_fr="Valeurs de l'énumération payment_status_enum: pending, processing, completed, failed, refunded, cancelled",
        description_en="Values for payment_status_enum: pending, processing, completed, failed, refunded, cancelled",
        db_table="payments",
        db_column="status",
        db_enum="payment_status_enum",
    ),

    "enum.payment_method": CategoryMetadata(
        code="enum.payment_method",
        group="payments",
        label_es="Método de pago",
        label_fr="Méthode de paiement",
        label_en="Payment method",
        description_es="Valores del enum payment_method_enum: mobile_money, bank_transfer, card, cash",
        description_fr="Valeurs de l'énumération payment_method_enum: mobile_money, bank_transfer, card, cash",
        description_en="Values for payment_method_enum: mobile_money, bank_transfer, card, cash",
        db_table="payments",
        db_column="payment_method",
        db_enum="payment_method_enum",
    ),

    # ==========================================================================
    # ENUM TRANSLATIONS - FISCAL SERVICES GROUP
    # ==========================================================================

    "enum.service_status": CategoryMetadata(
        code="enum.service_status",
        group="fiscal_services",
        label_es="Estado de servicio",
        label_fr="Statut de service",
        label_en="Service status",
        description_es="Valores del enum service_status_enum: active, inactive, deprecated",
        description_fr="Valeurs de l'énumération service_status_enum: active, inactive, deprecated",
        description_en="Values for service_status_enum: active, inactive, deprecated",
        db_table="fiscal_services",
        db_column="status",
        db_enum="service_status_enum",
    ),

    "enum.service_type": CategoryMetadata(
        code="enum.service_type",
        group="fiscal_services",
        label_es="Tipo de servicio",
        label_fr="Type de service",
        label_en="Service type",
        description_es="Valores del enum service_type_enum: tax, fee, permit, registration, certificate, license",
        description_fr="Valeurs de l'énumération service_type_enum: tax, fee, permit, registration, certificate, license",
        description_en="Values for service_type_enum: tax, fee, permit, registration, certificate, license",
        db_table="fiscal_services",
        db_column="service_type",
        db_enum="service_type_enum",
    ),

    "enum.calculation_method": CategoryMetadata(
        code="enum.calculation_method",
        group="fiscal_services",
        label_es="Método de cálculo",
        label_fr="Méthode de calcul",
        label_en="Calculation method",
        description_es="Valores del enum calculation_method_enum: fixed, percentage, tiered, formula, variable",
        description_fr="Valeurs de l'énumération calculation_method_enum: fixed, percentage, tiered, formula, variable",
        description_en="Values for calculation_method_enum: fixed, percentage, tiered, formula, variable",
        db_table="fiscal_services",
        db_column="calculation_method",
        db_enum="calculation_method_enum",
    ),

    "fiscal.period": CategoryMetadata(
        code="fiscal.period",
        group="fiscal_services",
        label_es="Períodos fiscales",
        label_fr="Périodes fiscales",
        label_en="Fiscal periods",
        description_es="Nombres de períodos fiscales: mensual, trimestral, anual",
        description_fr="Noms des périodes fiscales: mensuel, trimestriel, annuel",
        description_en="Fiscal period names: monthly, quarterly, annual",
        db_table="fiscal_periods",
        db_column="period_type",
    ),

    "fiscal.tax_type": CategoryMetadata(
        code="fiscal.tax_type",
        group="fiscal_services",
        label_es="Tipos de impuestos",
        label_fr="Types d'impôts",
        label_en="Tax types",
        description_es="Nombres de tipos de impuestos y tasas",
        description_fr="Noms des types d'impôts et taxes",
        description_en="Tax and fee type names",
        db_table=None,
        db_column=None,
    ),

    # ==========================================================================
    # ENUM TRANSLATIONS - AGENTS GROUP
    # ==========================================================================

    "enum.assignment_status": CategoryMetadata(
        code="enum.assignment_status",
        group="agents",
        label_es="Estado de asignación",
        label_fr="Statut d'assignation",
        label_en="Assignment status",
        description_es="Valores del enum assignment_status_enum: pending, assigned, in_progress, completed, reassigned",
        description_fr="Valeurs de l'énumération assignment_status_enum: pending, assigned, in_progress, completed, reassigned",
        description_en="Values for assignment_status_enum: pending, assigned, in_progress, completed, reassigned",
        db_table="agent_assignments",
        db_column="status",
        db_enum="assignment_status_enum",
    ),

    "enum.agent_action_type": CategoryMetadata(
        code="enum.agent_action_type",
        group="agents",
        label_es="Tipo de acción de agente",
        label_fr="Type d'action d'agent",
        label_en="Agent action type",
        description_es="Valores del enum agent_action_type: review, approve, reject, escalate, comment",
        description_fr="Valeurs de l'énumération agent_action_type: review, approve, reject, escalate, comment",
        description_en="Values for agent_action_type: review, approve, reject, escalate, comment",
        db_table="agent_actions",
        db_column="action_type",
        db_enum="agent_action_type",
    ),

    "agent.dashboard": CategoryMetadata(
        code="agent.dashboard",
        group="agents",
        label_es="Panel del agente",
        label_fr="Tableau de bord agent",
        label_en="Agent dashboard",
        description_es="Textos del panel de control de agentes fiscales",
        description_fr="Textes du tableau de bord des agents fiscaux",
        description_en="Fiscal agent dashboard texts",
        db_table=None,
        db_column=None,
    ),

    "agent.workflow": CategoryMetadata(
        code="agent.workflow",
        group="agents",
        label_es="Flujo de trabajo del agente",
        label_fr="Flux de travail agent",
        label_en="Agent workflow",
        description_es="Textos del flujo de trabajo de procesamiento de declaraciones",
        description_fr="Textes du flux de traitement des déclarations",
        description_en="Declaration processing workflow texts",
        db_table=None,
        db_column=None,
    ),

    # ==========================================================================
    # ENUM TRANSLATIONS - COMPANIES GROUP
    # ==========================================================================

    "enum.company_role": CategoryMetadata(
        code="enum.company_role",
        group="companies",
        label_es="Rol en empresa",
        label_fr="Rôle dans l'entreprise",
        label_en="Company role",
        description_es="Valores del enum company_role_enum: owner, admin, accountant, employee",
        description_fr="Valeurs de l'énumération company_role_enum: owner, admin, accountant, employee",
        description_en="Values for company_role_enum: owner, admin, accountant, employee",
        db_table="user_company_memberships",
        db_column="role",
        db_enum="company_role_enum",
    ),

    "enum.company_status": CategoryMetadata(
        code="enum.company_status",
        group="companies",
        label_es="Estado de empresa",
        label_fr="Statut d'entreprise",
        label_en="Company status",
        description_es="Valores del enum company_status_enum: active, inactive, suspended",
        description_fr="Valeurs de l'énumération company_status_enum: active, inactive, suspended",
        description_en="Values for company_status_enum: active, inactive, suspended",
        db_table="companies",
        db_column="status",
        db_enum="company_status_enum",
    ),

    # ==========================================================================
    # ENUM TRANSLATIONS - DOCUMENTS GROUP
    # ==========================================================================

    "enum.document_status": CategoryMetadata(
        code="enum.document_status",
        group="documents",
        label_es="Estado de documento",
        label_fr="Statut de document",
        label_en="Document status",
        description_es="Valores del enum document_status_enum: pending, uploaded, verified, rejected",
        description_fr="Valeurs de l'énumération document_status_enum: pending, uploaded, verified, rejected",
        description_en="Values for document_status_enum: pending, uploaded, verified, rejected",
        db_table="user_documents",
        db_column="status",
        db_enum="document_status_enum",
    ),

    "enum.document_type": CategoryMetadata(
        code="enum.document_type",
        group="documents",
        label_es="Tipo de documento",
        label_fr="Type de document",
        label_en="Document type",
        description_es="Valores del enum document_type_enum: id_card, passport, tax_certificate, etc.",
        description_fr="Valeurs de l'énumération document_type_enum: id_card, passport, tax_certificate, etc.",
        description_en="Values for document_type_enum: id_card, passport, tax_certificate, etc.",
        db_table="document_templates",
        db_column="document_type",
        db_enum="document_type_enum",
    ),

    # ==========================================================================
    # PERMISSIONS GROUP
    # ==========================================================================

    "enum.permission_scope": CategoryMetadata(
        code="enum.permission_scope",
        group="permissions",
        label_es="Ámbito de permiso",
        label_fr="Portée de permission",
        label_en="Permission scope",
        description_es="Valores del enum permission_scope_enum: global, own, team",
        description_fr="Valeurs de l'énumération permission_scope_enum: global, own, team",
        description_en="Values for permission_scope_enum: global, own, team",
        db_table="permissions",
        db_column="scope",
        db_enum="permission_scope_enum",
    ),

    "enum.role_type": CategoryMetadata(
        code="enum.role_type",
        group="permissions",
        label_es="Tipo de rol",
        label_fr="Type de rôle",
        label_en="Role type",
        description_es="Valores del enum role_type_enum: system, custom",
        description_fr="Valeurs de l'énumération role_type_enum: system, custom",
        description_en="Values for role_type_enum: system, custom",
        db_table="roles",
        db_column="role_type",
        db_enum="role_type_enum",
    ),

    # ==========================================================================
    # UI TRANSLATIONS - User interface elements
    # ==========================================================================

    "ui.button": CategoryMetadata(
        code="ui.button",
        group="ui",
        label_es="Botones",
        label_fr="Boutons",
        label_en="Buttons",
        description_es="Etiquetas de botones de la interfaz: guardar, cancelar, enviar, etc.",
        description_fr="Libellés des boutons de l'interface: enregistrer, annuler, soumettre, etc.",
        description_en="Button labels: save, cancel, submit, etc.",
        db_table=None,
        db_column=None,
    ),

    "ui.menu": CategoryMetadata(
        code="ui.menu",
        group="ui",
        label_es="Menús",
        label_fr="Menus",
        label_en="Menus",
        description_es="Elementos del menú de navegación",
        description_fr="Éléments du menu de navigation",
        description_en="Navigation menu items",
        db_table=None,
        db_column=None,
    ),

    "ui.label": CategoryMetadata(
        code="ui.label",
        group="ui",
        label_es="Etiquetas",
        label_fr="Étiquettes",
        label_en="Labels",
        description_es="Etiquetas de campos de formulario y elementos UI",
        description_fr="Étiquettes des champs de formulaire et éléments UI",
        description_en="Form field and UI element labels",
        db_table=None,
        db_column=None,
    ),

    "ui.tooltip": CategoryMetadata(
        code="ui.tooltip",
        group="ui",
        label_es="Tooltips",
        label_fr="Info-bulles",
        label_en="Tooltips",
        description_es="Textos de ayuda contextual",
        description_fr="Textes d'aide contextuelle",
        description_en="Contextual help text",
        db_table=None,
        db_column=None,
    ),

    "ui.placeholder": CategoryMetadata(
        code="ui.placeholder",
        group="ui",
        label_es="Placeholders",
        label_fr="Textes indicatifs",
        label_en="Placeholders",
        description_es="Textos de placeholder en campos de entrada",
        description_fr="Textes indicatifs dans les champs de saisie",
        description_en="Placeholder text in input fields",
        db_table=None,
        db_column=None,
    ),

    "ui.title": CategoryMetadata(
        code="ui.title",
        group="ui",
        label_es="Títulos",
        label_fr="Titres",
        label_en="Titles",
        description_es="Títulos de páginas y secciones",
        description_fr="Titres des pages et sections",
        description_en="Page and section titles",
        db_table=None,
        db_column=None,
    ),

    "ui.tab": CategoryMetadata(
        code="ui.tab",
        group="ui",
        label_es="Pestañas",
        label_fr="Onglets",
        label_en="Tabs",
        description_es="Etiquetas de pestañas de navegación",
        description_fr="Libellés des onglets de navigation",
        description_en="Tab navigation labels",
        db_table=None,
        db_column=None,
    ),

    # ==========================================================================
    # FORM TRANSLATIONS - Form-specific texts
    # ==========================================================================

    "form.validation": CategoryMetadata(
        code="form.validation",
        group="forms",
        label_es="Validación de formularios",
        label_fr="Validation de formulaires",
        label_en="Form validation",
        description_es="Mensajes de validación de campos: requerido, formato inválido, etc.",
        description_fr="Messages de validation des champs: requis, format invalide, etc.",
        description_en="Field validation messages: required, invalid format, etc.",
        db_table=None,
        db_column=None,
    ),

    "form.error": CategoryMetadata(
        code="form.error",
        group="forms",
        label_es="Errores de formulario",
        label_fr="Erreurs de formulaire",
        label_en="Form errors",
        description_es="Mensajes de error en formularios",
        description_fr="Messages d'erreur dans les formulaires",
        description_en="Form error messages",
        db_table=None,
        db_column=None,
    ),

    "form.success": CategoryMetadata(
        code="form.success",
        group="forms",
        label_es="Mensajes de éxito",
        label_fr="Messages de succès",
        label_en="Success messages",
        description_es="Mensajes de confirmación tras operaciones exitosas",
        description_fr="Messages de confirmation après opérations réussies",
        description_en="Confirmation messages after successful operations",
        db_table=None,
        db_column=None,
    ),

    "form.label": CategoryMetadata(
        code="form.label",
        group="forms",
        label_es="Etiquetas de formulario",
        label_fr="Libellés de formulaire",
        label_en="Form labels",
        description_es="Etiquetas de campos en formularios de declaración y registro",
        description_fr="Libellés des champs dans les formulaires de déclaration et inscription",
        description_en="Field labels in declaration and registration forms",
        db_table=None,
        db_column=None,
    ),

    "form.help": CategoryMetadata(
        code="form.help",
        group="forms",
        label_es="Ayuda de formulario",
        label_fr="Aide de formulaire",
        label_en="Form help",
        description_es="Textos de ayuda para campos de formulario",
        description_fr="Textes d'aide pour les champs de formulaire",
        description_en="Help text for form fields",
        db_table=None,
        db_column=None,
    ),

    # ==========================================================================
    # MESSAGE TRANSLATIONS - System messages and notifications
    # ==========================================================================

    "message.info": CategoryMetadata(
        code="message.info",
        group="messages",
        label_es="Mensajes informativos",
        label_fr="Messages informatifs",
        label_en="Info messages",
        description_es="Mensajes informativos del sistema",
        description_fr="Messages informatifs du système",
        description_en="System informational messages",
        db_table=None,
        db_column=None,
    ),

    "message.warning": CategoryMetadata(
        code="message.warning",
        group="messages",
        label_es="Advertencias",
        label_fr="Avertissements",
        label_en="Warnings",
        description_es="Mensajes de advertencia del sistema",
        description_fr="Messages d'avertissement du système",
        description_en="System warning messages",
        db_table=None,
        db_column=None,
    ),

    "message.error": CategoryMetadata(
        code="message.error",
        group="messages",
        label_es="Errores",
        label_fr="Erreurs",
        label_en="Errors",
        description_es="Mensajes de error del sistema",
        description_fr="Messages d'erreur du système",
        description_en="System error messages",
        db_table=None,
        db_column=None,
    ),

    "system.message": CategoryMetadata(
        code="system.message",
        group="messages",
        label_es="Mensajes del sistema",
        label_fr="Messages système",
        label_en="System messages",
        description_es="Mensajes generales del sistema",
        description_fr="Messages généraux du système",
        description_en="General system messages",
        db_table=None,
        db_column=None,
    ),

    "system.status": CategoryMetadata(
        code="system.status",
        group="messages",
        label_es="Estados del sistema",
        label_fr="Statuts système",
        label_en="System statuses",
        description_es="Textos de estados del sistema: cargando, procesando, etc.",
        description_fr="Textes d'états du système: chargement, traitement, etc.",
        description_en="System state texts: loading, processing, etc.",
        db_table=None,
        db_column=None,
    ),

    # ==========================================================================
    # EMAIL/NOTIFICATION TRANSLATIONS
    # ==========================================================================

    "email.subject": CategoryMetadata(
        code="email.subject",
        group="notifications",
        label_es="Asuntos de correo",
        label_fr="Objets d'email",
        label_en="Email subjects",
        description_es="Asuntos de correos electrónicos del sistema",
        description_fr="Objets des emails du système",
        description_en="System email subject lines",
        db_table=None,
        db_column=None,
    ),

    "email.body": CategoryMetadata(
        code="email.body",
        group="notifications",
        label_es="Cuerpos de correo",
        label_fr="Corps d'email",
        label_en="Email bodies",
        description_es="Plantillas de contenido de correos electrónicos",
        description_fr="Modèles de contenu des emails",
        description_en="Email content templates",
        db_table=None,
        db_column=None,
    ),

    "notification.push": CategoryMetadata(
        code="notification.push",
        group="notifications",
        label_es="Notificaciones push",
        label_fr="Notifications push",
        label_en="Push notifications",
        description_es="Textos de notificaciones push móviles",
        description_fr="Textes des notifications push mobiles",
        description_en="Mobile push notification texts",
        db_table=None,
        db_column=None,
    ),

    "notification.sms": CategoryMetadata(
        code="notification.sms",
        group="notifications",
        label_es="Mensajes SMS",
        label_fr="Messages SMS",
        label_en="SMS messages",
        description_es="Plantillas de mensajes SMS",
        description_fr="Modèles de messages SMS",
        description_en="SMS message templates",
        db_table=None,
        db_column=None,
    ),

    # ==========================================================================
    # CHATBOT TRANSLATIONS
    # ==========================================================================

    "chatbot.response": CategoryMetadata(
        code="chatbot.response",
        group="chatbot",
        label_es="Respuestas del chatbot",
        label_fr="Réponses du chatbot",
        label_en="Chatbot responses",
        description_es="Respuestas predefinidas del asistente virtual",
        description_fr="Réponses prédéfinies de l'assistant virtuel",
        description_en="Predefined virtual assistant responses",
        db_table=None,
        db_column=None,
    ),

    "chatbot.greeting": CategoryMetadata(
        code="chatbot.greeting",
        group="chatbot",
        label_es="Saludos del chatbot",
        label_fr="Salutations du chatbot",
        label_en="Chatbot greetings",
        description_es="Mensajes de bienvenida y saludos del chatbot",
        description_fr="Messages de bienvenue et salutations du chatbot",
        description_en="Chatbot welcome and greeting messages",
        db_table=None,
        db_column=None,
    ),

    "chatbot.error": CategoryMetadata(
        code="chatbot.error",
        group="chatbot",
        label_es="Errores del chatbot",
        label_fr="Erreurs du chatbot",
        label_en="Chatbot errors",
        description_es="Mensajes de error del asistente virtual",
        description_fr="Messages d'erreur de l'assistant virtuel",
        description_en="Virtual assistant error messages",
        db_table=None,
        db_column=None,
    ),
}


def get_category_metadata(code: str) -> Optional[CategoryMetadata]:
    """
    Get metadata for a specific category code

    Args:
        code: Category code (e.g., "enum.user_role")

    Returns:
        CategoryMetadata or None if not found
    """
    return CATEGORY_METADATA.get(code)


def get_all_category_metadata() -> Dict[str, CategoryMetadata]:
    """
    Get all category metadata

    Returns:
        Dict of category code to CategoryMetadata
    """
    return CATEGORY_METADATA


def get_category_label(code: str, language: str = "es") -> str:
    """
    Get localized label for a category

    Args:
        code: Category code
        language: Language code (es, fr, en)

    Returns:
        Localized label or code if not found
    """
    metadata = CATEGORY_METADATA.get(code)
    if not metadata:
        return code  # Return code as fallback

    if language == "fr":
        return metadata.label_fr
    elif language == "en":
        return metadata.label_en
    else:
        return metadata.label_es


def get_group_label(group_code: str, language: str = "es") -> str:
    """
    Get localized label for a group

    Args:
        group_code: Group code (enum type or functional group)
        language: Language code (es, fr, en)

    Returns:
        Localized label or code if not found
    """
    label_key = f"label_{language}"

    # Check DB enum groups first
    if group_code in DB_ENUM_GROUPS:
        info = DB_ENUM_GROUPS[group_code]
        return info.get(label_key, info.get("label_es", group_code))

    # Check functional groups
    if group_code in FUNCTIONAL_GROUPS:
        info = FUNCTIONAL_GROUPS[group_code]
        return info.get(label_key, info.get("label_es", group_code))

    return group_code


def enrich_categories(
    categories: List[str],
    language: str = "es"
) -> List[Dict]:
    """
    Enrich category list with metadata including group information

    Args:
        categories: List of category codes from database
        language: Language code for labels

    Returns:
        List of enriched category dicts with labels and group info
    """
    enriched = []

    for code in categories:
        metadata = CATEGORY_METADATA.get(code)

        if metadata:
            # Get label based on language
            if language == "fr":
                label = metadata.label_fr
                description = metadata.description_fr
            elif language == "en":
                label = metadata.label_en
                description = metadata.description_en
            else:
                label = metadata.label_es
                description = metadata.description_es

            # Determine effective group: use db_enum if available, otherwise use group
            effective_group = metadata.db_enum if metadata.db_enum else metadata.group
            group_label = get_group_label(effective_group, language)

            enriched.append({
                "code": code,
                "label": label,
                "description": description,
                "db_table": metadata.db_table,
                "db_column": metadata.db_column,
                "db_enum": metadata.db_enum,
                "group": effective_group,
                "group_label": group_label,
            })
        else:
            # Unknown category - use code as label, group as "other"
            enriched.append({
                "code": code,
                "label": code,  # Fallback to code
                "description": None,
                "db_table": None,
                "db_column": None,
                "db_enum": None,
                "group": "other",
                "group_label": get_group_label("other", language),
            })

    return enriched
