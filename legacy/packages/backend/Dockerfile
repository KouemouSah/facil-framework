# =============================================================================
# TaxasGE Backend - Production Dockerfile for Cloud Run
# =============================================================================
# Multi-stage build for optimized production image
# Base: Python 3.11 slim (3.10+ required for importlib.metadata.packages_distributions)
# =============================================================================

FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies for building Python packages
# Includes cairo dev libs for xhtml2pdf/pycairo PDF generation
# Note: libgdk-pixbuf-2.0-dev (with dashes) for Debian Trixie
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Production stage
# =============================================================================
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies including Tesseract OCR and Cairo for PDF generation
# - libpq5: PostgreSQL client library
# - tesseract-ocr: OCR engine for text extraction from images/PDFs
# - tesseract-ocr-spa: Spanish language data (primary for Guinea Ecuatorial)
# - tesseract-ocr-fra: French language data (secondary)
# - tesseract-ocr-eng: English language data (fallback)
# - poppler-utils: PDF rendering utilities (required by pdf2image)
# - libcairo2, libpango*, libgdk-pixbuf-2.0-0: Cairo runtime for PDF generation
RUN apt-get update && apt-get install -y \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    poppler-utils \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libgl1 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Start command using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
