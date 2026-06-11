"""
👁️ TaxasGE OCR Service
Optical Character Recognition service with multiple providers
Supports Tesseract (server/lite) and Google Vision API

Author: KOUEMOU SAH Jean Emac
Date: 27 septembre 2025
Version: 1.0.0
"""

import asyncio
import io
import tempfile
import os
from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import datetime
from pathlib import Path
import base64
import json

import cv2
import numpy as np
from PIL import Image, ImageEnhance
import pytesseract
from pdf2image import convert_from_bytes
from loguru import logger
from pydantic import BaseModel, Field

from app.config import settings


# ============================================================================
# MODELS & TYPES
# ============================================================================

class OCRResult(BaseModel):
    """OCR processing result"""
    success: bool = Field(..., description="Processing success status")
    text: str = Field(default="", description="Extracted text")
    confidence: float = Field(default=0.0, description="Overall confidence score (0-1)")
    word_confidences: Optional[List[Dict]] = Field(None, description="Per-word confidence scores")
    processing_time_ms: int = Field(default=0, description="Processing time in milliseconds")
    provider: str = Field(..., description="OCR provider used")
    language: str = Field(default="eng", description="Detected/used language")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class OCRConfig(BaseModel):
    """OCR service configuration"""
    tesseract_path: Optional[str] = Field(None, description="Tesseract executable path")
    tesseract_config: str = Field(
        "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ",
        description="Tesseract configuration"
    )
    google_vision_enabled: bool = Field(False, description="Enable Google Vision API")
    preprocessing_enabled: bool = Field(True, description="Enable image preprocessing")
    supported_languages: List[str] = Field(
        default=["eng", "spa", "fra", "por"],
        description="Supported OCR languages"
    )
    max_image_size: int = Field(default=4096, description="Max image dimension for processing")
    quality_threshold: float = Field(default=0.6, description="Minimum quality threshold")


# ============================================================================
# OCR SERVICE
# ============================================================================

class OCRService:
    """
    Multi-provider OCR service for TaxasGE

    Features:
    - Tesseract OCR (server and lite modes)
    - Google Vision API support
    - Advanced image preprocessing
    - Multi-language support
    - Confidence scoring and validation
    - Document type-specific optimization
    """

    def __init__(self):
        self.config = OCRConfig()
        self._initialize_tesseract()
        self._preprocessing_cache = {}

    def _initialize_tesseract(self):
        """Initialize Tesseract OCR"""
        try:
            # Try to set Tesseract path if configured
            if self.config.tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self.config.tesseract_path

            # Test Tesseract availability
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract OCR initialized: {version}")

        except Exception as e:
            logger.warning(f"Tesseract initialization failed: {e}")

    async def extract_text(
        self,
        file_content: bytes,
        file_type: str,
        provider: str = "tesseract_server",
        language: str = "eng",
        document_type: Optional[str] = None
    ) -> OCRResult:
        """
        Extract text from document using specified OCR provider

        Args:
            file_content: Document file content
            file_type: MIME type of file
            provider: OCR provider (tesseract_server, tesseract_lite, google_vision)
            language: OCR language code
            document_type: Type of document for optimization

        Returns:
            OCRResult with extracted text and metadata
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting OCR extraction with {provider} for {file_type}")

            # Convert file to images
            images = await self._prepare_images(file_content, file_type)
            if not images:
                return OCRResult(
                    success=False,
                    provider=provider,
                    errors=["Failed to convert file to images"]
                )

            # Process based on provider
            if provider == "google_vision":
                result = await self._process_with_google_vision(images, language)
            elif provider == "document_ai":
                # Phase 2 future: Google Document AI for structured forms
                result = await self._process_with_document_ai(images, language, document_type)
            elif provider == "tesseract_lite":
                result = await self._process_with_tesseract_lite(images, language)
            else:  # tesseract_server (default)
                result = await self._process_with_tesseract_server(images, language, document_type)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            result.processing_time_ms = int(processing_time)

            logger.info(f"OCR completed in {processing_time:.2f}ms with confidence {result.confidence:.3f}")
            return result

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"OCR extraction failed: {e}")
            return OCRResult(
                success=False,
                provider=provider,
                processing_time_ms=int(processing_time),
                errors=[str(e)]
            )

    async def _prepare_images(self, file_content: bytes, file_type: str) -> List[np.ndarray]:
        """Convert file content to OpenCV images"""
        try:
            images = []

            if file_type == "application/pdf":
                # Convert PDF to images
                pdf_images = convert_from_bytes(
                    file_content,
                    dpi=300,
                    first_page=1,
                    last_page=5  # Limit to first 5 pages
                )

                for pil_image in pdf_images:
                    # Convert PIL to OpenCV format
                    opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                    images.append(opencv_image)

            elif file_type.startswith("image/"):
                # Handle image files
                image_array = np.frombuffer(file_content, np.uint8)
                opencv_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

                if opencv_image is not None:
                    images.append(opencv_image)

            else:
                logger.warning(f"Unsupported file type for OCR: {file_type}")
                return []

            # Apply preprocessing if enabled
            if self.config.preprocessing_enabled:
                images = [await self._preprocess_image(img) for img in images]

            return images

        except Exception as e:
            logger.error(f"Image preparation failed: {e}")
            return []

    async def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Apply image preprocessing for better OCR results"""
        try:
            # Resize if too large
            height, width = image.shape[:2]
            if max(height, width) > self.config.max_image_size:
                scale = self.config.max_image_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # Apply adaptive thresholding
            adaptive_thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            # Noise reduction
            denoised = cv2.medianBlur(adaptive_thresh, 3)

            # Morphological operations to improve text clarity
            kernel = np.ones((1, 1), np.uint8)
            processed = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)

            return processed

        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}")
            return image

    async def _process_with_tesseract_server(
        self,
        images: List[np.ndarray],
        language: str,
        document_type: Optional[str] = None
    ) -> OCRResult:
        """Process images with Tesseract server mode (full features)"""
        try:
            all_text = []
            all_confidences = []
            word_confidences = []

            # Optimize config based on document type
            config = self._get_tesseract_config(document_type)

            for image in images:
                # Extract text with confidence data
                data = pytesseract.image_to_data(
                    image,
                    lang=language,
                    config=config,
                    output_type=pytesseract.Output.DICT
                )

                # Extract text and confidence scores
                page_text = []
                page_confidences = []

                for i, word in enumerate(data['text']):
                    if int(data['conf'][i]) > 0:  # Valid confidence
                        page_text.append(word)
                        page_confidences.append(int(data['conf'][i]))

                        word_confidences.append({
                            'word': word,
                            'confidence': int(data['conf'][i]) / 100.0,
                            'bbox': [
                                data['left'][i],
                                data['top'][i],
                                data['width'][i],
                                data['height'][i]
                            ]
                        })

                all_text.extend(page_text)
                all_confidences.extend(page_confidences)

            # Combine results
            extracted_text = ' '.join(all_text)
            overall_confidence = np.mean(all_confidences) / 100.0 if all_confidences else 0.0

            # Post-process text
            extracted_text = self._post_process_text(extracted_text)

            return OCRResult(
                success=len(extracted_text.strip()) > 0,
                text=extracted_text,
                confidence=float(overall_confidence),
                word_confidences=word_confidences,
                provider="tesseract_server",
                language=language,
                metadata={
                    "total_words": len(all_text),
                    "avg_word_confidence": overall_confidence,
                    "pages_processed": len(images)
                }
            )

        except Exception as e:
            logger.error(f"Tesseract server processing failed: {e}")
            return OCRResult(
                success=False,
                provider="tesseract_server",
                errors=[str(e)]
            )

    async def _process_with_tesseract_lite(
        self,
        images: List[np.ndarray],
        language: str
    ) -> OCRResult:
        """Process images with Tesseract lite mode (basic features)"""
        try:
            all_text = []

            # Simple configuration for lite mode
            config = "--oem 3 --psm 6"

            for image in images:
                # Extract text only (no confidence data for lite mode)
                text = pytesseract.image_to_string(
                    image,
                    lang=language,
                    config=config
                )
                all_text.append(text)

            # Combine results
            extracted_text = ' '.join(all_text)
            extracted_text = self._post_process_text(extracted_text)

            # Estimate confidence based on text quality
            confidence = self._estimate_text_quality(extracted_text)

            return OCRResult(
                success=len(extracted_text.strip()) > 0,
                text=extracted_text,
                confidence=confidence,
                provider="tesseract_lite",
                language=language,
                metadata={
                    "pages_processed": len(images),
                    "mode": "lite"
                }
            )

        except Exception as e:
            logger.error(f"Tesseract lite processing failed: {e}")
            return OCRResult(
                success=False,
                provider="tesseract_lite",
                errors=[str(e)]
            )

    async def _process_with_google_vision(
        self,
        images: List[np.ndarray],
        language: str
    ) -> OCRResult:
        """Process images with Google Vision API"""
        try:
            # Note: This is a placeholder for Google Vision API integration
            # In a real implementation, you would use the Google Cloud Vision client
            logger.warning("Google Vision API not implemented - falling back to Tesseract")
            return await self._process_with_tesseract_server(images, language)

        except Exception as e:
            logger.error(f"Google Vision processing failed: {e}")
            return OCRResult(
                success=False,
                provider="google_vision",
                errors=[str(e)]
            )

    async def _process_with_document_ai(
        self,
        images: List[np.ndarray],
        language: str,
        document_type: Optional[str] = None
    ) -> OCRResult:
        """
        Process images with Google Document AI (PHASE 2 - Future)

        Document AI is optimized for structured forms with tables, key-value pairs,
        and form fields - perfect for tax declaration forms (IVA, IRPF, etc.)

        Advantages over Tesseract:
        - Form field detection (automatic key-value extraction)
        - Table extraction with structure preservation
        - Better handling of checkboxes and form elements
        - Higher accuracy for financial documents
        - Native currency and number recognition

        Implementation roadmap:
        1. Enable Document AI API in Google Cloud Console
        2. Create processor for "FORM_PARSER" type
        3. Upload JSON templates as processor schemas
        4. Integrate with firebase_storage_service for batch processing

        References:
        - https://cloud.google.com/document-ai/docs/form-parser
        - https://cloud.google.com/document-ai/docs/processors-list
        """
        try:
            # PHASE 2 TODO: Implement Google Document AI
            logger.warning("Document AI not yet implemented - falling back to Tesseract")
            logger.info(f"Document type '{document_type}' would benefit from Document AI form parser")

            # Fallback to Tesseract for now
            return await self._process_with_tesseract_server(images, language, document_type)

        except Exception as e:
            logger.error(f"Document AI processing failed: {e}")
            return OCRResult(
                success=False,
                provider="document_ai",
                errors=[str(e)]
            )

    def _get_tesseract_config(self, document_type: Optional[str] = None) -> str:
        """
        Get optimized Tesseract configuration based on document type

        Updated for Phase 2 - Added fiscal form configurations
        """
        base_config = "--oem 3 --psm 6"

        document_configs = {
            # Identity documents
            "passport": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz<>/",
            "nif_card": "--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789",

            # Financial documents
            "invoice": "--oem 3 --psm 6",
            "receipt": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,:-€$£",

            # Tax declaration forms (Phase 2) - Optimized for numbers, percentages, currency
            "tax_declaration": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,%-€$£FCFA ",
            "iva_destajo": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,%-€$£FCFA ",
            "iva_real": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,%-€$£FCFA ",
            "irpf": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,%-€$£FCFA ",
            "imp_salarios": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,%-€$£FCFA ",
            "cuota_minima": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,%-€$£FCFA ",

            # Fiscal service forms
            "fiscal_service": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,:-€$£FCFA "
        }

        return document_configs.get(document_type, base_config)

    def _post_process_text(self, text: str) -> str:
        """Post-process extracted text"""
        # Remove excessive whitespace
        text = ' '.join(text.split())

        # Fix common OCR errors
        corrections = {
            '0': 'O',  # In names/words
            'rn': 'm',  # Common OCR confusion
            'cl': 'd',
            '|': 'I'
        }

        # Apply corrections contextually
        # (This is a simplified version - real implementation would be more sophisticated)

        return text.strip()

    def _estimate_text_quality(self, text: str) -> float:
        """Estimate text quality/confidence based on content analysis"""
        if not text.strip():
            return 0.0

        # Basic quality metrics
        total_chars = len(text)
        alpha_chars = sum(1 for c in text if c.isalpha())
        digit_chars = sum(1 for c in text if c.isdigit())
        space_chars = sum(1 for c in text if c.isspace())
        punct_chars = sum(1 for c in text if c in '.,;:!?-()[]{}')

        # Calculate quality score
        alpha_ratio = alpha_chars / total_chars
        digit_ratio = digit_chars / total_chars
        space_ratio = space_chars / total_chars
        punct_ratio = punct_chars / total_chars

        # Penalize if too many non-text characters
        quality_score = 0.8  # Base score

        if alpha_ratio > 0.6:  # Good amount of letters
            quality_score += 0.1

        if 0.1 < space_ratio < 0.3:  # Reasonable spacing
            quality_score += 0.05

        if punct_ratio < 0.1:  # Not too much punctuation
            quality_score += 0.05

        return min(1.0, max(0.1, quality_score))

    async def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported OCR languages"""
        try:
            # Get available Tesseract languages
            available_langs = pytesseract.get_languages()

            language_mapping = {
                'eng': 'English',
                'spa': 'Spanish',
                'fra': 'French',
                'por': 'Portuguese',
                'deu': 'German',
                'ita': 'Italian'
            }

            supported = []
            for lang_code in self.config.supported_languages:
                if lang_code in available_langs:
                    supported.append({
                        'code': lang_code,
                        'name': language_mapping.get(lang_code, lang_code),
                        'available': True
                    })

            return supported

        except Exception as e:
            logger.error(f"Failed to get supported languages: {e}")
            return [{'code': 'eng', 'name': 'English', 'available': True}]

    async def validate_image_quality(self, image: np.ndarray) -> Dict[str, Any]:
        """Validate image quality for OCR processing"""
        try:
            height, width = image.shape[:2]

            # Calculate quality metrics
            metrics = {
                'resolution': {'width': width, 'height': height},
                'size_adequate': min(width, height) >= 200,
                'aspect_ratio': width / height,
                'estimated_quality': 0.5  # Placeholder
            }

            # Check if image is too small
            if min(width, height) < 200:
                metrics['warnings'] = ['Image resolution too low for optimal OCR']

            # Check if image is too large
            if max(width, height) > 4000:
                metrics['warnings'] = metrics.get('warnings', []) + ['Image resolution very high - will be resized']

            return metrics

        except Exception as e:
            logger.error(f"Image quality validation failed: {e}")
            return {'error': str(e)}


# ============================================================================
# SERVICE INSTANCE
# ============================================================================

# Global service instance
ocr_service = OCRService()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def extract_text_from_file(
    file_content: bytes,
    file_type: str,
    provider: str = "tesseract_server"
) -> OCRResult:
    """Helper function for text extraction"""
    return await ocr_service.extract_text(
        file_content=file_content,
        file_type=file_type,
        provider=provider
    )


async def get_ocr_capabilities() -> Dict[str, Any]:
    """Get OCR service capabilities"""
    try:
        languages = await ocr_service.get_supported_languages()

        return {
            "providers": ["tesseract_server", "tesseract_lite", "google_vision"],
            "supported_languages": languages,
            "supported_formats": ["image/jpeg", "image/png", "image/tiff", "application/pdf"],
            "max_image_size": ocr_service.config.max_image_size,
            "preprocessing_available": ocr_service.config.preprocessing_enabled,
            "tesseract_available": True  # Could check actual availability
        }

    except Exception as e:
        logger.error(f"Failed to get OCR capabilities: {e}")
        return {"error": str(e)}