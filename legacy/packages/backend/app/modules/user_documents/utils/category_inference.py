"""
Shared category inference for vault documents.

Single source of truth for mapping a `document_type` string (manual
hint from the user OR Gemini classification output) to the coarse
`document_category` enum stored in `user_documents.document_category`.

Used by:
- `user_documents_routes.py` upload endpoint (when the user provides a
  `document_type_hint`)
- `auto_classify_service.py` background task (when Gemini provides a
  classification)

Keeping the mapping in ONE place avoids drift between the two callers.
Extracted during Phase 6 hardening.
"""
from __future__ import annotations

# Token sets per category — matched as substrings (case-insensitive) so
# variants like "pasaporte_nuevo" or "carnet_conducir_a" still resolve.
_CATEGORY_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "identity",
        (
            "passport", "pasaporte", "national_id", "dip", "nif", "nie",
            "cedula", "birth_certificate", "acta_nacimiento", "dni",
            "identidad",
        ),
    ),
    (
        "vehicle",
        (
            "matricula", "matric", "permiso_conducir", "carnet_conducir",
            "vehicle_registration", "driving_license", "itv", "vehicul",
            "permis",
        ),
    ),
    (
        "financial",
        (
            "bank_statement", "receipt", "invoice", "tax_return", "factura",
            "nota_ingreso", "solvencia", "recibo",
        ),
    ),
    (
        "legal",
        (
            "contract", "contrato", "notarial", "poder", "escritura",
            "acta", "certificado", "legaliza",
        ),
    ),
    (
        "medical",
        ("medical", "certificado_medico", "health", "vacunacion"),
    ),
    (
        "education",
        ("diploma", "titulo", "certificado_academico", "education"),
    ),
    (
        "photo",
        ("photo", "foto", "photograph"),
    ),
    (
        "business",
        ("business_license", "licencia_comercial", "registro_mercantil"),
    ),
    (
        "employment",
        ("employment", "contrato_trabajo", "nomina", "payslip"),
    ),
)


def infer_category(document_type: str | None) -> str:
    """Infer a document_category enum value from a free-form type string.

    Returns "other" as a safe fallback when no token matches. The
    returned value is always a valid `user_documents.document_category`
    enum member (identity, vehicle, legal, financial, administrative,
    medical, education, photo, business, employment, other).
    """
    if not document_type:
        return "other"
    lower = document_type.lower()
    for category, tokens in _CATEGORY_TOKENS:
        if any(tok in lower for tok in tokens):
            return category
    return "other"
