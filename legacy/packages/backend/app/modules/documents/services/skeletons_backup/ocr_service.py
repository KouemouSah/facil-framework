"""
OCR Service - Tesseract and Google Document AI Integration

Service for OCR processing of uploaded documents
Table: ocr_extraction_results

OCR Engines:
- Tesseract: Free, open-source OCR (good for simple documents)
- Google Document AI: Premium AI-powered document processing (structured extraction)
  - Processor: form_parser ONLY (universal form field extraction)
  - Extracts key-value pairs from all document types
  - Better accuracy for tax forms, invoices, receipts
  - Structured data extraction with field detection
"""

from typing import Dict, Any, Optional
from loguru import logger
import uuid


class OCRService:
    """Service for OCR processing with Tesseract and Google Document AI"""

    def __init__(self, project_id: str = "taxasge-dev", location: str = "eu"):
        """
        Initialize OCR service

        Args:
            project_id: GCP project ID (taxasge-dev or taxasge-pro)
            location: Document AI location (eu, us)
        """
        self.project_id = project_id
        self.location = location
        self.tesseract_enabled = True  # TODO: Check Tesseract installation
        self.document_ai_enabled = False  # TODO: Check GCP credentials and processors

    async def process_document(
        self,
        file_id: str,
        file_path: str,
        document_type: str,
        use_document_ai: bool = False,
    ) -> Dict[str, Any]:
        """
        Process document with OCR

        Args:
            file_id: uploaded_files.id
            file_path: Path to file (local or Firebase Storage URL)
            document_type: Type of document (iva, irpf, nota_ingreso, invoice, receipt, etc.)
            use_document_ai: Use Google Document AI form_parser (fallback to Tesseract if false)

        Returns:
            {
                "extraction_id": str,
                "file_id": str,
                "raw_text": str,
                "structured_data": dict,  # Key-value pairs extracted by form_parser
                "confidence": float,
                "ocr_engine": str,
                "processor_type": "form_parser" (if Document AI)
            }
        """
        extraction_id = str(uuid.uuid4())

        try:
            if use_document_ai and self.document_ai_enabled:
                result = await self._process_with_document_ai(file_path)
                ocr_engine = "document_ai"
            else:
                result = await self._process_with_tesseract(file_path)
                ocr_engine = "tesseract"

            logger.info(f"OCR processed file {file_id} with {ocr_engine}")

            response = {
                "extraction_id": extraction_id,
                "file_id": file_id,
                "raw_text": result.get("raw_text", ""),
                "structured_data": result.get("structured_data", {}),
                "confidence": result.get("confidence", 0.0),
                "ocr_engine": ocr_engine,
                "processing_time_ms": result.get("processing_time_ms", 0),
            }

            if use_document_ai:
                response["processor_type"] = "form_parser"

            return response

        except Exception as e:
            logger.error(f"OCR processing failed for file {file_id}: {e}")
            return {
                "extraction_id": extraction_id,
                "file_id": file_id,
                "raw_text": "",
                "structured_data": {},
                "confidence": 0.0,
                "ocr_engine": "none",
                "error": str(e),
            }

    async def _process_with_tesseract(self, file_path: str) -> Dict[str, Any]:
        """
        Process document with Tesseract OCR

        TODO: Implement actual Tesseract integration
        - Install pytesseract
        - Configure Tesseract path
        - Set language (spa for Spanish)
        """
        import time
        start_time = time.time()

        # TODO: Implement Tesseract OCR
        # import pytesseract
        # from PIL import Image
        # image = Image.open(file_path)
        # raw_text = pytesseract.image_to_string(image, lang='spa')

        # Mock result for now
        raw_text = "Mock OCR text from Tesseract"
        structured_data = {}

        processing_time_ms = int((time.time() - start_time) * 1000)

        return {
            "raw_text": raw_text,
            "structured_data": structured_data,
            "confidence": 0.85,
            "processing_time_ms": processing_time_ms,
        }

    async def _process_with_document_ai(
        self,
        file_path: str,
    ) -> Dict[str, Any]:
        """
        Process document with Google Document AI form_parser

        form_parser processor:
        - Universal form field extraction (key-value pairs)
        - Works for all document types: IVA, IRPF, invoices, receipts, tax forms
        - Extracts field names and values automatically
        - No need for document-specific logic

        Args:
            file_path: Path to file (local or Firebase Storage URL)

        Returns:
            {
                "raw_text": str,
                "structured_data": dict,  # Key-value pairs from form fields
                "confidence": float,
                "processing_time_ms": int
            }
        """
        import time
        start_time = time.time()

        # TODO: Implement Google Document AI form_parser integration
        # from google.cloud import documentai_v1 as documentai
        #
        # # Create processor client
        # client = documentai.DocumentProcessorServiceClient()
        #
        # # Get form_parser processor path
        # # Format: projects/{project}/locations/{location}/processors/{processor_id}
        # # IMPORTANT: Use ONLY form_parser processor
        # processor_name = f"projects/{self.project_id}/locations/{self.location}/processors/{form_parser_processor_id}"
        #
        # # Read document
        # with open(file_path, 'rb') as document_file:
        #     document_content = document_file.read()
        #
        # # Create request
        # raw_document = documentai.RawDocument(
        #     content=document_content,
        #     mime_type="application/pdf"  # or "image/jpeg", "image/png"
        # )
        #
        # request = documentai.ProcessRequest(
        #     name=processor_name,
        #     raw_document=raw_document
        # )
        #
        # # Process document with form_parser
        # result = client.process_document(request=request)
        # document = result.document
        #
        # # Extract raw text
        # raw_text = document.text
        #
        # # Extract form fields (key-value pairs)
        # structured_data = {}
        # for page in document.pages:
        #     for field in page.form_fields:
        #         # Get field name
        #         field_name = ""
        #         if field.field_name.text_anchor:
        #             field_name = self._get_text_from_anchor(field.field_name.text_anchor, raw_text)
        #
        #         # Get field value
        #         field_value = ""
        #         if field.field_value.text_anchor:
        #             field_value = self._get_text_from_anchor(field.field_value.text_anchor, raw_text)
        #
        #         if field_name:
        #             structured_data[field_name.strip()] = field_value.strip()
        #
        # # Calculate average confidence
        # confidences = [field.field_name.confidence for page in document.pages for field in page.form_fields]
        # confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Mock result for now - form_parser returns key-value pairs
        raw_text = "Mock OCR text from Google Document AI (form_parser)"
        structured_data = {
            "NIF": "MOCK-NIF-123456",
            "Nom": "Test Company",
            "Montant": "150000",
            "Date": "2025-01-20",
            "Type de déclaration": "IVA",
            "Période": "Janvier 2025",
        }

        processing_time_ms = int((time.time() - start_time) * 1000)

        return {
            "raw_text": raw_text,
            "structured_data": structured_data,
            "confidence": 0.95,  # Document AI form_parser has high confidence
            "processing_time_ms": processing_time_ms,
        }

    def _get_text_from_anchor(self, text_anchor, full_text: str) -> str:
        """
        Helper to extract text from Document AI text anchor

        Args:
            text_anchor: Document AI text anchor
            full_text: Full document text

        Returns:
            Extracted text segment
        """
        # TODO: Implement text extraction from anchor
        # if not text_anchor.text_segments:
        #     return ""
        # segments = []
        # for segment in text_anchor.text_segments:
        #     start_index = segment.start_index if segment.start_index else 0
        #     end_index = segment.end_index if segment.end_index else len(full_text)
        #     segments.append(full_text[start_index:end_index])
        # return "".join(segments)
        return ""

    async def extract_with_template(
        self,
        raw_text: str,
        template_code: str,
    ) -> Dict[str, Any]:
        """
        Extract structured data using form template

        Args:
            raw_text: Raw OCR text
            template_code: form_templates.template_code

        Returns:
            Structured extracted data
        """
        # TODO: Use template_loader and zone_label_extractor
        # from app.modules.documents.extractors.template_loader import TemplateLoader
        # from app.modules.documents.extractors.zone_label_extractor import ZoneLabelExtractor

        # loader = TemplateLoader()
        # template = loader.load_template(template_code)
        # extractor = ZoneLabelExtractor(template)
        # result = extractor.extract(raw_text)

        logger.info(f"Extracting with template {template_code}")

        return {
            "extracted_data": {},
            "confidence": 0.8,
            "template_code": template_code,
        }
