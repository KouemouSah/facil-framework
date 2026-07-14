"""Product-owned schemas — declared in code, versioned with it, non-editable.

`organization.document_identity` is the letterhead/footer/seal identity that the
Document Designer (SP2) renders. It is deliberately FLAT: the per-format layout
lives in the TEMPLATE (CSS @page + margin boxes), not here. Conflating the two
is what forces one hand-positioned layout per (format × document × org).

`legal_name`, `tax_id`, `registration_number` and `logo_url` are DELIBERATELY
ABSENT from this schema (SP1 debt D1): `Organization` already carries them as
REAL COLUMNS (`app/modules/organization/models.py`) — re-declaring them here
would create two sources of truth for the same legal identity that WILL
diverge (fix the legal name in the org's own record, the document keeps
printing the old one). `Organization` is the single source of truth for legal
identity; `document_identity` carries only what is document-specific. Read
the resolved identity (columns + blob + child-entity overrides, with origin
per key) via `core.schema.issuer.resolve_issuer_identity`, never by
re-declaring these keys in a blob. See `DOCUMENT_IDENTITY_OVERRIDE` below for
the (deliberately narrower) set that a child `OrgUnit`/`Site` MAY override.

`organization.settings` replaces the raw-JSON `Organization.settings` column
with a generated form. The column has NO consumer in the code today, so only
the per-organisation settings the product genuinely needs are declared here —
`document_number_prefix` is reserved for the SP2 legal numbering sequence,
`default_document_locale`/`fiscal_year_start_month` are read by nothing yet.
Inventing extra fields "just in case" would be the exact placeholder this
schema layer exists to forbid.
"""

from __future__ import annotations

from typing import Any

from app.core.schema.spec import field

DOCUMENT_IDENTITY: list[dict[str, Any]] = [
    field("short_code",
          {"en": "Short code", "fr": "Code court", "es": "Código corto"},
          hint={"en": "Printed on reports to identify the issuing entity",
                "fr": "Imprimé sur les rapports pour identifier l'entité émettrice",
                "es": "Impreso en los informes para identificar la entidad emisora"},
          rules={"max_length": 20}, group="identity", order=2),
    field("seal_url", {"en": "Seal / stamp", "fr": "Sceau / cachet", "es": "Sello"},
          type="file", widget="image",
          hint={"en": "Reserved zone for the signature seal (SP2)",
                "fr": "Zone réservée au sceau de signature (SP2)",
                "es": "Zona reservada para el sello de firma (SP2)"},
          group="branding", order=2),
    field("header_note", {"en": "Header note", "fr": "Mention d'en-tête",
                          "es": "Nota de encabezado"},
          type="text", rules={"max_length": 300}, group="layout", order=1, col_span=2),
    field("footer_note", {"en": "Footer note", "fr": "Mention de pied de page",
                          "es": "Nota de pie de página"},
          type="text", rules={"max_length": 300}, group="layout", order=2, col_span=2),
    field("legal_mentions", {"en": "Legal mentions", "fr": "Mentions légales",
                             "es": "Menciones legales"},
          type="richtext", group="layout", order=3, col_span=2),
    field("contact_line", {"en": "Contact line", "fr": "Ligne de contact",
                           "es": "Línea de contacto"},
          rules={"max_length": 200}, group="layout", order=4, col_span=2),
]

# Optional overrides an `OrgUnit` or `Site` may declare on ITS OWN
# `document_identity` blob (SP1 debt D1 — value inheritance). An organisation
# never overrides its own name (meaningless); overrides only exist GOING
# DOWN the hierarchy — a department or branch wants its own name/code printed
# on its documents. Deliberately narrower than `DOCUMENT_IDENTITY`:
# `tax_id`/`registration_number` (legal/fiscal identifiers) and
# `seal_url`/`header_note`/`legal_mentions` (organisation-wide legal text) are
# NOT overridable — only identity/branding fields a sub-entity would
# legitimately want to localise. `resolve_issuer_identity` (core/schema/
# issuer.py) is what a document actually reads: it walks
# Site -> OrgUnit -> Organization, first non-empty value wins, and reports
# WHERE each value came from.
DOCUMENT_IDENTITY_OVERRIDE: list[dict[str, Any]] = [
    field("legal_name",
          {"en": "Legal name (override)", "fr": "Raison sociale (surcharge)",
           "es": "Razón social (anulación)"},
          hint={"en": "Leave empty to inherit the organization's legal name",
                "fr": "Laisser vide pour hériter de la raison sociale de l'organisation",
                "es": "Dejar vacío para heredar la razón social de la organización"},
          rules={"max_length": 200}, group="identity", order=1, col_span=2),
    field("short_code",
          {"en": "Short code", "fr": "Code court", "es": "Código corto"},
          hint={"en": "Leave empty to inherit the organization's short code",
                "fr": "Laisser vide pour hériter du code court de l'organisation",
                "es": "Dejar vacío para heredar el código corto de la organización"},
          rules={"max_length": 20}, group="identity", order=2),
    field("logo_url", {"en": "Logo", "fr": "Logo", "es": "Logotipo"},
          type="file", widget="image",
          hint={"en": "Leave empty to inherit the organization's logo",
                "fr": "Laisser vide pour hériter du logo de l'organisation",
                "es": "Dejar vacío para heredar el logotipo de la organización"},
          group="branding", order=1),
    field("contact_line", {"en": "Contact line", "fr": "Ligne de contact",
                           "es": "Línea de contacto"},
          rules={"max_length": 200}, group="layout", order=1, col_span=2),
    field("footer_note", {"en": "Footer note", "fr": "Mention de pied de page",
                          "es": "Nota de pie de página"},
          type="text", rules={"max_length": 300}, group="layout", order=2, col_span=2),
]

ORGANIZATION_SETTINGS: list[dict[str, Any]] = [
    field("default_document_locale",
          {"en": "Default document locale", "fr": "Langue par défaut des documents",
           "es": "Idioma predeterminado de los documentos"},
          type="select",
          options=[{"value": "en", "label": {"en": "English", "fr": "Anglais", "es": "Inglés"}},
                   {"value": "fr", "label": {"en": "French", "fr": "Français", "es": "Francés"}},
                   {"value": "es", "label": {"en": "Spanish", "fr": "Espagnol", "es": "Español"}}],
          group="documents", order=1),
    field("document_number_prefix",
          {"en": "Document number prefix", "fr": "Préfixe de numérotation",
           "es": "Prefijo de numeración"},
          hint={"en": "Reserved for the SP2 legal sequence (e.g. \"GQ-\")",
                "fr": "Réservé à la séquence légale SP2 (ex. « GQ- »)",
                "es": "Reservado para la secuencia legal SP2 (p. ej. «GQ-»)"},
          rules={"max_length": 10, "pattern": "^[A-Z0-9-]*$"}, group="documents", order=2),
    field("fiscal_year_start_month",
          {"en": "Fiscal year start month", "fr": "Mois de début d'exercice",
           "es": "Mes de inicio del ejercicio"},
          type="number", rules={"min": 1, "max": 12}, default=1,
          group="accounting", order=1),
]
