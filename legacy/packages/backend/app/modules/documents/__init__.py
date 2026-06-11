"""
Document Management Module - TaxasGE Backend

Module complet de gestion documentaire avec OCR:
- Upload et stockage documents (Supabase Storage)
- Traitement OCR (Tesseract/Google Cloud Vision)
- Extraction structurée de données
- Validation et vérification
- Queue asynchrone avec retry

5 Tables DB:
1. uploaded_files (métadonnées fichiers uploadés)
2. document_processing_queue (queue OCR async avec retry, exponential backoff)
3. ocr_extraction_results (résultats OCR bruts JSONB)
4. form_templates (templates OCR - coordonnées champs pour extraction)
5. document_templates (templates documents requis - partagé avec FISCAL_SERVICES)

Extractors:
- declarations (IVA, IRPF, Pétrolifères, etc.)
- fiscal_services (Nota de Ingreso, etc.)
- template_loader (charge les templates OCR)
- zone_label_extractor (extraction par zones)

Priorité: 🔴 CRITIQUE P1
"""

from app.modules.documents.api import document_routes

__all__ = ["document_routes"]
