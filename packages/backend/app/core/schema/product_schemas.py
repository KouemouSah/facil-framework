"""Product-owned schemas — declared in code, versioned with it, non-editable.

`organization.document_identity` is the letterhead/footer/seal identity that the
Document Designer (SP2) renders. It is deliberately FLAT: the per-format layout
lives in the TEMPLATE (CSS @page + margin boxes), not here. Conflating the two
is what forces one hand-positioned layout per (format × document × org).
"""

from __future__ import annotations

from typing import Any

from app.core.schema.spec import field

DOCUMENT_IDENTITY: list[dict[str, Any]] = [
    field("legal_name",
          {"en": "Legal name", "fr": "Raison sociale", "es": "Razón social"},
          required=True, rules={"max_length": 200}, group="identity", order=1, col_span=2),
    field("short_code",
          {"en": "Short code", "fr": "Code court", "es": "Código corto"},
          hint={"en": "Printed on reports to identify the issuing entity",
                "fr": "Imprimé sur les rapports pour identifier l'entité émettrice",
                "es": "Impreso en los informes para identificar la entidad emisora"},
          rules={"max_length": 20}, group="identity", order=2),
    field("tax_id", {"en": "Tax ID", "fr": "Identifiant fiscal", "es": "NIF"},
          rules={"max_length": 50}, group="identity", order=3),
    field("registration_number",
          {"en": "Registration number", "fr": "Numéro d'enregistrement",
           "es": "Número de registro"},
          rules={"max_length": 50}, group="identity", order=4),
    field("logo_url", {"en": "Logo", "fr": "Logo", "es": "Logotipo"},
          type="file", widget="image", group="branding", order=1),
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
