"""
⚙️ TaxasGE Backend Configuration
Gestion des configurations par environnement (dev/prod)
Compatible: Local Development, Firebase Functions, CI/CD

Author: KOUEMOU SAH Jean Emac
"""

import os
import secrets
from typing import List, Optional, Dict, Any
from functools import lru_cache
from loguru import logger

from pydantic_settings import BaseSettings
from pydantic import validator, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# BASE CONFIGURATION CLASS
# ============================================================================

class Settings(BaseSettings):
    """
    Configuration de base pour TaxasGE Backend
    Utilise Pydantic pour validation et gestion des types
    """

    def __init__(self, **kwargs):
        """Initialize settings and load secrets from Google Cloud Secret Manager"""
        super().__init__(**kwargs)

        # Load SMTP_PASSWORD from Secret Manager (secret: smtp-password)
        if not self.SMTP_PASSWORD:
            try:
                from app.core.secrets import get_smtp_password
                secret_pass = get_smtp_password()
                if secret_pass:
                    self.SMTP_PASSWORD = secret_pass
                    logger.info("✅ SMTP password loaded from Secret Manager")
                else:
                    # Fallback to env var
                    self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
                    if self.SMTP_PASSWORD:
                        logger.warning("⚠️ SMTP password loaded from env var (local dev)")
                    else:
                        logger.error("❌ SMTP_PASSWORD not configured (emails will fail)")
            except Exception as e:
                logger.error(f"❌ Failed to load SMTP password from Secret Manager: {e}")
                self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        
        # Load Firebase Admin Keys from Secret Manager
        try:
            from app.core.secrets import get_secret
            
            # Load Dev Firebase Key
            firebase_key_dev = get_secret("firebase-admin-key-dev")
            if firebase_key_dev:
                self.FIREBASE_ADMIN_KEY_DEV = firebase_key_dev
                logger.info("✅ Firebase Admin Key (DEV) loaded from Secret Manager")
            else:
                logger.warning("⚠️ Firebase Admin Key (DEV) not found in Secret Manager")
            
            # Load Pro Firebase Key
            firebase_key_pro = get_secret("firebase-admin-key-pro")
            if firebase_key_pro:
                self.FIREBASE_ADMIN_KEY_PRO = firebase_key_pro
                logger.info("✅ Firebase Admin Key (PRO) loaded from Secret Manager")
            else:
                logger.warning("⚠️ Firebase Admin Key (PRO) not found in Secret Manager")
                
        except Exception as e:
            logger.error(f"❌ Failed to load Firebase Admin Keys from Secret Manager: {e}")

        # Load RECEIPT_VERIFICATION_SECRET from Secret Manager if not set via env
        if not self.RECEIPT_VERIFICATION_SECRET:
            try:
                from app.core.secrets import get_secret
                receipt_secret = get_secret("receipt-verification-secret")
                if receipt_secret:
                    self.RECEIPT_VERIFICATION_SECRET = receipt_secret
                    logger.info("✅ RECEIPT_VERIFICATION_SECRET loaded from Secret Manager")
                else:
                    logger.warning(
                        "⚠️ RECEIPT_VERIFICATION_SECRET not found in Secret Manager — "
                        "falling back to JWT_SECRET_KEY for QR code tokens"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Could not load RECEIPT_VERIFICATION_SECRET from Secret Manager: {e}")
        else:
            logger.info("✅ RECEIPT_VERIFICATION_SECRET configured (env var)")

    # ========================================================================
    # APPLICATION SETTINGS
    # ========================================================================
    
    PROJECT_NAME: str = "TaxasGE API"
    PROJECT_DESCRIPTION: str = "API de gestion fiscale pour la Guinée Équatoriale"
    # Bumped from 1.0.0 to match the runtime value previously held by main.py's
    # local Settings class (api_version="1.1.8") — the duplicate Settings class
    # was removed 2026-05-02. Preserve this string when bumping; multiple
    # health endpoints expose it.
    VERSION: str = "1.1.8"
    
    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="PORT")

    # Frontend URL (for email links, password reset, etc.)
    # Production domain: taxasge.emacsah.com
    FRONTEND_URL: str = Field(default="https://taxasge.emacsah.com", env="FRONTEND_URL")

    # Whitelisted mobile deep-link schemes for payment return_url validation.
    # Comma-separated. The mobile app uses 'facil' (cf. packages/mobile/app.json).
    MOBILE_DEEP_LINK_SCHEMES: str = Field(default="facil", env="MOBILE_DEEP_LINK_SCHEMES")

    # Backend API Base URL (for webhooks callbacks)
    # Cloud Run URL or custom domain
    API_BASE_URL: str = Field(default="https://taxasge-backend-staging-677954753182.europe-west1.run.app", env="API_BASE_URL")
    
    # ========================================================================
    # SECURITY SETTINGS
    # ========================================================================
    
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32), env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # JWT Configuration
    JWT_ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32), env="JWT_SECRET_KEY")
    
    # Password hashing
    BCRYPT_ROUNDS: int = 12

    # TOTP secret encryption key (Fernet, base64-encoded 32 bytes)
    # If not set, derived from JWT_SECRET_KEY via SHA256 + base64
    TOTP_ENCRYPTION_KEY: str = Field(default="", env="TOTP_ENCRYPTION_KEY")

    # Receipt verification (HMAC key for QR code security)
    # IMPORTANT: Set this as a PERMANENT env var in Cloud Run / Secret Manager.
    # This key signs the QR code tokens on all PDF receipts and service requests.
    # If not set, falls back to JWT_SECRET_KEY (permanent) — but dedicated key is preferred.
    # NEVER rotate this key after receipts have been issued: existing QR codes will break.
    RECEIPT_VERIFICATION_SECRET: str = Field(
        default="",
        env="RECEIPT_VERIFICATION_SECRET"
    )

    # ========================================================================
    # DATABASE SETTINGS
    # ========================================================================
    
    # Supabase Configuration (Optional for local development)
    SUPABASE_URL: Optional[str] = Field(default=None, env="SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = Field(default=None, env="SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_ANON_KEY: Optional[str] = Field(default=None, env="SUPABASE_ANON_KEY")
    
    # PostgreSQL Direct Connection (backup)
    DATABASE_URL: Optional[str] = Field(default=None, env="DATABASE_URL")
    
    # Database Pool Settings
    DB_POOL_SIZE: int = Field(default=5, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=10, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")

    # Connection Pool Settings (for asyncpg)
    # Supabase: ~60 total connections limit. With 2 Cloud Run instances: 20×2=40 < 60.
    DATABASE_MIN_CONNECTIONS: int = Field(default=10, env="DATABASE_MIN_CONNECTIONS")
    DATABASE_MAX_CONNECTIONS: int = Field(default=20, env="DATABASE_MAX_CONNECTIONS")
    
    # ========================================================================
    # FIREBASE SETTINGS (Using actual GitHub Secrets names)
    # ========================================================================
    
    # Firebase Project Configuration
    FIREBASE_PROJECT_ID: str = Field(default="taxasge-dev", env="FIREBASE_PROJECT_ID")
    FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV: Optional[str] = Field(default=None, env="FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV")
    
    # Firebase Android App Configuration
    FIREBASE_ANDROID_APP_ID: Optional[str] = Field(default=None, env="FIREBASE_ANDROID_APP_ID")
    
    # Firebase Storage
    FIREBASE_STORAGE_BUCKET: Optional[str] = Field(default=None, env="FIREBASE_STORAGE_BUCKET")
    
    # ========================================================================
    # MONITORING & NOTIFICATIONS (Using actual GitHub Secrets names)
    # ========================================================================
    
    # SonarQube Integration
    SONAR_TOKEN: Optional[str] = Field(default=None, env="SONAR_TOKEN")
    
    # Slack Notifications
    SLACK_WEBHOOK_URL: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    
    # ========================================================================
    # CORS SETTINGS
    # ========================================================================
    
    ALLOWED_HOSTS: List[str] = Field(default=["*"])
    CORS_ORIGINS: List[str] = Field(default=[])
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # ========================================================================
    # LOGGING SETTINGS
    # ========================================================================
    
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = Field(default=None, env="LOG_FILE")
    
    # Structured logging
    ENABLE_STRUCTURED_LOGGING: bool = Field(default=True, env="ENABLE_STRUCTURED_LOGGING")
    
    # ========================================================================
    # AI/ML SETTINGS
    # ========================================================================

    # TensorFlow Lite Model (Legacy - deprecated)
    #AI_MODEL_PATH: str = Field(default="assets/ml/taxasge_model.tflite", env="AI_MODEL_PATH")
    #AI_TOKENIZER_PATH: str = Field(default="assets/ml/tokenizer.json", env="AI_TOKENIZER_PATH")
    #AI_INTENTS_PATH: str = Field(default="assets/ml/intents.json", env="AI_INTENTS_PATH")

    # AI Configuration
    AI_MAX_TOKENS: int = Field(default=512, env="AI_MAX_TOKENS")
    AI_CONFIDENCE_THRESHOLD: float = Field(default=0.7, env="AI_CONFIDENCE_THRESHOLD")

    # ========================================================================
    # GOOGLE CLOUD AI / VERTEX AI SETTINGS
    # ========================================================================

    # Google Cloud Project (inherited from Cloud Run environment)
    GOOGLE_CLOUD_PROJECT: str = Field(
        default="taxasge-dev",
        env="GOOGLE_CLOUD_PROJECT"
    )
    GOOGLE_CLOUD_LOCATION: str = Field(
        default="us-central1",
        env="GOOGLE_CLOUD_LOCATION"
    )

    # Gemini Models Configuration
    # Dual-backend: set GEMINI_API_KEY for Google AI Studio, or use Vertex AI (default)
    # gemini-2.5-flash-preview: latest Flash with built-in thinking/reasoning
    GEMINI_API_KEY: str = Field(default="", env="GEMINI_API_KEY")
    GEMINI_CHAT_MODEL: str = Field(
        default="gemini-2.5-flash",
        env="GEMINI_CHAT_MODEL"
    )
    GEMINI_PRO_MODEL: str = Field(
        default="gemini-2.5-flash",
        env="GEMINI_PRO_MODEL"
    )
    GEMINI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-005",
        env="GEMINI_EMBEDDING_MODEL"
    )

    # Gemini Generation Configuration
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=2048, env="GEMINI_MAX_OUTPUT_TOKENS")
    GEMINI_TEMPERATURE: float = Field(default=0.5, env="GEMINI_TEMPERATURE")
    GEMINI_TOP_P: float = Field(default=0.9, env="GEMINI_TOP_P")
    GEMINI_TOP_K: int = Field(default=40, env="GEMINI_TOP_K")

    # Embedding Configuration
    EMBEDDING_DIMENSIONS: int = Field(default=768, env="EMBEDDING_DIMENSIONS")
    EMBEDDING_BATCH_SIZE: int = Field(default=250, env="EMBEDDING_BATCH_SIZE")

    # Semantic Search Configuration
    SEMANTIC_SEARCH_TOP_K: int = Field(default=5, env="SEMANTIC_SEARCH_TOP_K")
    # Similarity threshold for RAG results. text-embedding-005 gives better scores
    # than 004. 0.35 filters noise while keeping cross-language results (fr/en -> es).
    # Adjust via env var if needed.
    SEMANTIC_SEARCH_SIMILARITY_THRESHOLD: float = Field(
        default=0.35,
        env="SEMANTIC_SEARCH_SIMILARITY_THRESHOLD"
    )

    # RAG Configuration — Gemini 2.0 Flash has 1M context, use it generously
    RAG_MAX_CONTEXT_SERVICES: int = Field(default=10, env="RAG_MAX_CONTEXT_SERVICES")
    RAG_MAX_CONTEXT_DOCUMENTS: int = Field(default=10, env="RAG_MAX_CONTEXT_DOCUMENTS")
    RAG_CONVERSATION_HISTORY_LENGTH: int = Field(default=30, env="RAG_CONVERSATION_HISTORY_LENGTH")
    MAX_CONTEXT_TOKENS: int = Field(default=50000, env="MAX_CONTEXT_TOKENS")
    PDF_CHUNK_SIZE: int = Field(default=1000, env="PDF_CHUNK_SIZE")
    PDF_CHUNK_OVERLAP: int = Field(default=100, env="PDF_CHUNK_OVERLAP")
    SUGGESTION_SIMILARITY_THRESHOLD: float = Field(default=0.4, env="SUGGESTION_SIMILARITY_THRESHOLD")
    RAG_EXTENDED_SEARCH_TOP_K: int = Field(default=20, env="RAG_EXTENDED_SEARCH_TOP_K")
    RAG_MIN_CONTEXT_LENGTH: int = Field(default=100, env="RAG_MIN_CONTEXT_LENGTH")
    
    # ========================================================================
    # EXTERNAL SERVICES
    # ========================================================================
    
    # Bange Payment Integration
    BANGE_API_URL: Optional[str] = Field(default=None, env="BANGE_API_URL")
    BANGE_API_KEY: Optional[str] = Field(default=None, env="BANGE_API_KEY")
    BANGE_MERCHANT_ID: Optional[str] = Field(default=None, env="BANGE_MERCHANT_ID")
    BANGE_WEBHOOK_SECRET: Optional[str] = Field(default=None, env="BANGE_WEBHOOK_SECRET")

    # Ecobank Payment Integration (developer.ecobank.com)
    ECOBANK_API_URL: Optional[str] = Field(default=None, env="ECOBANK_API_URL")
    ECOBANK_CLIENT_ID: Optional[str] = Field(default=None, env="ECOBANK_CLIENT_ID")
    ECOBANK_CLIENT_SECRET: Optional[str] = Field(default=None, env="ECOBANK_CLIENT_SECRET")
    ECOBANK_WEBHOOK_SECRET: Optional[str] = Field(default=None, env="ECOBANK_WEBHOOK_SECRET")
    # Comma-separated methods to force Ecobank as primary (e.g., "mobile_money,card")
    ECOBANK_PRIMARY_METHODS: Optional[str] = Field(default=None, env="ECOBANK_PRIMARY_METHODS")

    # Mastercard Payment Gateway Services (MPGS) via Ecobank
    MPGS_API_URL: Optional[str] = Field(default=None, env="MPGS_API_URL")
    MPGS_MERCHANT_ID: Optional[str] = Field(default=None, env="MPGS_MERCHANT_ID")
    MPGS_API_PASSWORD: Optional[str] = Field(default=None, env="MPGS_API_PASSWORD")
    MPGS_API_VERSION: str = Field(default="85", env="MPGS_API_VERSION")
    MPGS_WEBHOOK_SECRET: Optional[str] = Field(default=None, env="MPGS_WEBHOOK_SECRET")
    MPGS_PRIMARY_METHODS: Optional[str] = Field(default="card", env="MPGS_PRIMARY_METHODS")
    
    # Email Service (MODULE_02)
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    SMTP_FROM_EMAIL: Optional[str] = Field(default=None, env="SMTP_FROM_EMAIL")
    SMTP_FROM_NAME: str = Field(default="Facil", env="SMTP_FROM_NAME")

    # SMTP_PASSWORD: Load from Secret Manager at startup
    # Will be set by __init__ method below
    SMTP_PASSWORD: Optional[str] = None
    
    # ========================================================================
    # FIREBASE ADMIN SDK
    # ========================================================================
    
    # Firebase Admin SDK Keys: Load from Secret Manager at startup
    # Will be set by __init__ method below
    FIREBASE_ADMIN_KEY_DEV: Optional[str] = None
    FIREBASE_ADMIN_KEY_PRO: Optional[str] = None
    
    # ========================================================================
    # CACHE SETTINGS
    # ========================================================================
    
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # 1 hour
    
    # ========================================================================
    # ASSIGNMENT OUTBOX
    # ========================================================================

    OUTBOX_BATCH_SIZE: int = Field(default=50, env="OUTBOX_BATCH_SIZE")
    OUTBOX_ORPHAN_THRESHOLD_MINUTES: int = Field(default=10, env="OUTBOX_ORPHAN_THRESHOLD_MINUTES")
    OUTBOX_STALE_PROCESSING_MINUTES: int = Field(default=5, env="OUTBOX_STALE_PROCESSING_MINUTES")
    OUTBOX_RETRY_DELAYS: str = Field(default="30,60,120,300,600", env="OUTBOX_RETRY_DELAYS")

    # ========================================================================
    # AGENT QUEUE
    # ========================================================================

    QUEUE_DEFAULT_SLA_HOURS: int = Field(default=48, env="QUEUE_DEFAULT_SLA_HOURS")
    QUEUE_ESCALATION_BOOST: int = Field(default=50, env="QUEUE_ESCALATION_BOOST")
    QUEUE_SLA_WARNING_HOURS: int = Field(default=6, env="QUEUE_SLA_WARNING_HOURS")
    QUEUE_MAX_WORKLOAD_PCT: float = Field(default=80.0, env="QUEUE_MAX_WORKLOAD_PCT")
    QUEUE_AGE_BOOST_24H: int = Field(default=10, env="QUEUE_AGE_BOOST_24H")
    QUEUE_AGE_BOOST_48H: int = Field(default=15, env="QUEUE_AGE_BOOST_48H")
    QUEUE_AGE_BOOST_72H: int = Field(default=25, env="QUEUE_AGE_BOOST_72H")

    # ========================================================================
    # ASSIGNMENT ESCALATION
    # ========================================================================

    ESCALATION_SLA_CRITICAL_HOURS: int = Field(default=0, env="ESCALATION_SLA_CRITICAL_HOURS")
    ESCALATION_SLA_HIGH_HOURS: int = Field(default=6, env="ESCALATION_SLA_HIGH_HOURS")
    ESCALATION_PROCESSING_MAX_HOURS: int = Field(default=24, env="ESCALATION_PROCESSING_MAX_HOURS")
    ESCALATION_PENDING_REVIEW_MAX_HOURS: int = Field(default=12, env="ESCALATION_PENDING_REVIEW_MAX_HOURS")
    REASSIGNMENT_COOLDOWN_HOURS: float = Field(default=1.0, env="REASSIGNMENT_COOLDOWN_HOURS")

    # ========================================================================
    # CRON SECURITY
    # ========================================================================

    CRON_SECRET: Optional[str] = Field(default=None, env="CRON_SECRET")

    # ========================================================================
    # LEGAL — Privacy Policy + Terms of Service versions (Phase 10/B)
    # ========================================================================
    # Mobile reads these at sign-up via GET /api/v1/legal/versions and submits
    # them back in POST /auth/register (or POST /legal/accept for existing
    # users). Bumping these triggers the post-login mobile modal to re-prompt
    # acceptance (only for citizen/business/accountant — admin/agent/funcionario
    # are exempt by role check). See migration 331 + .claude/plans/MOBILE_PHASE_10_B_LEGAL_DETAILED.md.

    LEGAL_PRIVACY_VERSION: str = Field(default="1.0.0", env="LEGAL_PRIVACY_VERSION")
    LEGAL_PRIVACY_LAST_UPDATED: str = Field(default="2026-05-02", env="LEGAL_PRIVACY_LAST_UPDATED")
    LEGAL_TERMS_VERSION: str = Field(default="1.0.0", env="LEGAL_TERMS_VERSION")
    LEGAL_TERMS_LAST_UPDATED: str = Field(default="2026-05-02", env="LEGAL_TERMS_LAST_UPDATED")
    LEGAL_COOKIES_VERSION: str = Field(default="1.0.0", env="LEGAL_COOKIES_VERSION")
    LEGAL_COOKIES_LAST_UPDATED: str = Field(default="2026-05-02", env="LEGAL_COOKIES_LAST_UPDATED")

    # ========================================================================
    # INTERNAL SCHEDULER (replaces Cloud Scheduler)
    # ========================================================================

    SCHEDULER_ENABLED: bool = Field(default=True, env="SCHEDULER_ENABLED")
    SCHEDULER_OUTBOX_INTERVAL: int = Field(default=60, env="SCHEDULER_OUTBOX_INTERVAL")
    SCHEDULER_HEALTH_CHECK_INTERVAL: int = Field(default=300, env="SCHEDULER_HEALTH_CHECK_INTERVAL")
    SCHEDULER_EXPIRED_HOLDS_INTERVAL: int = Field(default=900, env="SCHEDULER_EXPIRED_HOLDS_INTERVAL")
    SCHEDULER_ESCALATION_SLA_INTERVAL: int = Field(default=7200, env="SCHEDULER_ESCALATION_SLA_INTERVAL")
    SCHEDULER_QUEUE_PRIORITY_INTERVAL: int = Field(default=21600, env="SCHEDULER_QUEUE_PRIORITY_INTERVAL")
    SCHEDULER_DAILY_INTERVAL: int = Field(default=86400, env="SCHEDULER_DAILY_INTERVAL")
    SCHEDULER_WEEKLY_INTERVAL: int = Field(default=604800, env="SCHEDULER_WEEKLY_INTERVAL")

    # ========================================================================
    # MULTI-CRITERIA SCORING (Assignment Intelligence)
    # ========================================================================

    SCORING_WEIGHT_WORKLOAD: float = Field(default=0.30, env="SCORING_WEIGHT_WORKLOAD")
    SCORING_WEIGHT_SUCCESS: float = Field(default=0.25, env="SCORING_WEIGHT_SUCCESS")
    SCORING_WEIGHT_SPECIALIZATION: float = Field(default=0.20, env="SCORING_WEIGHT_SPECIALIZATION")
    SCORING_WEIGHT_SITE: float = Field(default=0.15, env="SCORING_WEIGHT_SITE")
    SCORING_WEIGHT_SPEED: float = Field(default=0.10, env="SCORING_WEIGHT_SPEED")
    SCORING_NEW_AGENT_DEFAULT: float = Field(default=50.0, env="SCORING_NEW_AGENT_DEFAULT")
    SPECIALIZATION_THRESHOLD: int = Field(default=3, env="SPECIALIZATION_THRESHOLD")
    SPECIALIZATION_REMOVE_THRESHOLD: float = Field(default=40.0, env="SPECIALIZATION_REMOVE_THRESHOLD")

    # Predictive escalation
    ESCALATION_PREDICTIVE_MIN_COMPLETIONS: int = Field(default=5, env="ESCALATION_PREDICTIVE_MIN_COMPLETIONS")
    ESCALATION_PREDICTIVE_SUCCESS_THRESHOLD: float = Field(default=60.0, env="ESCALATION_PREDICTIVE_SUCCESS_THRESHOLD")
    ESCALATION_PREDICTIVE_COMPLEXITY_THRESHOLD: int = Field(default=60, env="ESCALATION_PREDICTIVE_COMPLEXITY_THRESHOLD")  # complexity_score 0-100 scale (migration 136)

    # Anomaly detection
    ANOMALY_QUEUE_SPIKE_MULTIPLIER: float = Field(default=2.0, env="ANOMALY_QUEUE_SPIKE_MULTIPLIER")
    ANOMALY_UNDERPERFORMER_THRESHOLD: float = Field(default=40.0, env="ANOMALY_UNDERPERFORMER_THRESHOLD")
    ANOMALY_PROCESSING_TIME_SPIKE_HOURS: float = Field(default=72.0, env="ANOMALY_PROCESSING_TIME_SPIKE_HOURS")
    ANOMALY_REJECTION_RATE_THRESHOLD: float = Field(default=0.5, env="ANOMALY_REJECTION_RATE_THRESHOLD")
    ANOMALY_REJECTION_MIN_ACTIONS: int = Field(default=3, env="ANOMALY_REJECTION_MIN_ACTIONS")
    ANOMALY_REJECTION_LOOKBACK_DAYS: int = Field(default=7, env="ANOMALY_REJECTION_LOOKBACK_DAYS")
    ANOMALY_SITE_IMBALANCE_MULTIPLIER: int = Field(default=3, env="ANOMALY_SITE_IMBALANCE_MULTIPLIER")
    ANOMALY_CAPACITY_MIN_FLOOR: int = Field(default=5, env="ANOMALY_CAPACITY_MIN_FLOOR")
    ANOMALY_CAPACITY_REDUCTION_STEP: int = Field(default=5, env="ANOMALY_CAPACITY_REDUCTION_STEP")
    ANOMALY_UNDERPERFORMER_PENALTY: float = Field(default=0.5, env="ANOMALY_UNDERPERFORMER_PENALTY")

    # Penalty system — disabled by default, enable with PENALTIES_ENABLED=true
    PENALTIES_ENABLED: bool = Field(default=False, env="PENALTIES_ENABLED")

    # Auto-rebalancing
    REBALANCE_OVERLOAD_OFFSET: float = Field(default=1.0, env="REBALANCE_OVERLOAD_OFFSET")
    REBALANCE_UNDERLOAD_OFFSET: float = Field(default=0.5, env="REBALANCE_UNDERLOAD_OFFSET")
    REBALANCE_MAX_REASSIGNMENTS_PER_RUN: int = Field(default=10, env="REBALANCE_MAX_REASSIGNMENTS_PER_RUN")
    REBALANCE_MOBILITY_URGENT: int = Field(default=100, env="REBALANCE_MOBILITY_URGENT")
    REBALANCE_MOBILITY_HIGH: int = Field(default=70, env="REBALANCE_MOBILITY_HIGH")
    REBALANCE_MOBILITY_SLA_PRESSURE: int = Field(default=80, env="REBALANCE_MOBILITY_SLA_PRESSURE")
    REBALANCE_MOBILITY_NORMAL: int = Field(default=30, env="REBALANCE_MOBILITY_NORMAL")
    REBALANCE_MOBILITY_DEFAULT: int = Field(default=10, env="REBALANCE_MOBILITY_DEFAULT")

    # Scoring sub-parameters
    SCORING_SPEED_MAX_HOURS: float = Field(default=48.0, env="SCORING_SPEED_MAX_HOURS")
    SCORING_SPEED_DEFAULT_HOURS: float = Field(default=24.0, env="SCORING_SPEED_DEFAULT_HOURS")
    SCORING_SITE_MATCH: float = Field(default=100.0, env="SCORING_SITE_MATCH")
    SCORING_SITE_NEUTRAL: float = Field(default=50.0, env="SCORING_SITE_NEUTRAL")

    # Agent Executive Tools (Phase 5) — submit_prepared_request, book_appointment.
    # Uses a confirmation_code single-use mechanism (Redis TTL 5min) orthogonal
    # to user_agent_permissions because migration 287 CHECK rejects level=3.
    # Default OFF — flip to True only after Phase 5.5 restores the execution
    # logic that was removed in Phase 4.
    FEATURE_EXECUTIVE_TOOLS: bool = Field(default=False, env="FEATURE_EXECUTIVE_TOOLS")

    # LLM Routing (Gemini-augmented assignment)
    FEATURE_LLM_ROUTING_ENABLED: bool = Field(default=False, env="FEATURE_LLM_ROUTING_ENABLED")
    LLM_ROUTING_SCORE_GAP_THRESHOLD: float = Field(default=5.0, env="LLM_ROUTING_SCORE_GAP_THRESHOLD")
    LLM_ROUTING_CONFIDENCE_THRESHOLD: float = Field(default=0.7, env="LLM_ROUTING_CONFIDENCE_THRESHOLD")
    LLM_ROUTING_MAX_CANDIDATES: int = Field(default=5, env="LLM_ROUTING_MAX_CANDIDATES")
    LLM_ROUTING_TIMEOUT_SECONDS: float = Field(default=5.0, env="LLM_ROUTING_TIMEOUT_SECONDS")
    LLM_ROUTING_MODEL: str = Field(default="gemini-2.0-flash", env="LLM_ROUTING_MODEL")
    LLM_ROUTING_TEMPERATURE: float = Field(default=0.1, env="LLM_ROUTING_TEMPERATURE")
    LLM_ROUTING_MAX_TOKENS: int = Field(default=512, env="LLM_ROUTING_MAX_TOKENS")

    # Dashboard quality score
    QUALITY_SCORE_SLA_WEIGHT: float = Field(default=0.5, env="QUALITY_SCORE_SLA_WEIGHT")
    QUALITY_SCORE_ACCEPTANCE_WEIGHT: float = Field(default=0.25, env="QUALITY_SCORE_ACCEPTANCE_WEIGHT")
    QUALITY_SCORE_RESPONSE_WEIGHT: float = Field(default=0.25, env="QUALITY_SCORE_RESPONSE_WEIGHT")
    QUALITY_SCORE_MAX_RESPONSE_HOURS: float = Field(default=48.0, env="QUALITY_SCORE_MAX_RESPONSE_HOURS")

    # Reporting time windows
    REPORT_PERIOD_DAYS: int = Field(default=30, env="REPORT_PERIOD_DAYS")
    REPORT_TODAY_LOOKBACK_HOURS: int = Field(default=24, env="REPORT_TODAY_LOOKBACK_HOURS")
    REPORT_ESCALATION_RECENT_DAYS: int = Field(default=7, env="REPORT_ESCALATION_RECENT_DAYS")

    # Specialist definition
    SPECIALIST_MIN_COMPLETIONS: int = Field(default=3, env="SPECIALIST_MIN_COMPLETIONS")
    SPECIALIST_MIN_SUCCESS_RATE: float = Field(default=60.0, env="SPECIALIST_MIN_SUCCESS_RATE")

    # ========================================================================
    # CLEANUP & EXPIRATION (Plan P2 — INSPECTION_BUNDLE_P2_DETAIL.md)
    # ========================================================================

    # DRAFT service_requests cleanup threshold (hours).
    # Bundle workflows (BUNDLE_PAYMENT, FIELD_INSPECTION) are ALWAYS excluded
    # from cleanup regardless of this value. Normal DRAFTs older than this
    # are deleted by the hourly cron /cron/cleanup-abandoned-requests.
    DRAFT_CLEANUP_MAX_HOURS: int = Field(default=2, env="DRAFT_CLEANUP_MAX_HOURS")

    # Gemini extraction preview cache TTL (minutes).
    # User must confirm the preview within this window.
    PREVIEW_EXPIRY_MINUTES: int = Field(default=30, env="PREVIEW_EXPIRY_MINUTES")

    # Wizard session TTL (seconds) — Redis cache for in-progress wizards.
    WIZARD_SESSION_TTL_SECONDS: int = Field(default=1800, env="WIZARD_SESSION_TTL_SECONDS")

    # ========================================================================
    # RATE LIMITING
    # ========================================================================
    
    RATE_LIMIT_ENABLED: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_REQUESTS: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    
    # ========================================================================
    # MONITORING & METRICS
    # ========================================================================
    
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    # ========================================================================
    # VALIDATORS
    # ========================================================================
    
    @validator("API_PORT", pre=True)
    def validate_api_port(cls, v):
        """Convert API_PORT to integer if string"""
        if isinstance(v, str):
            return int(v)
        return v

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment value"""
        allowed_envs = ["development", "testing", "staging", "production"]
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of: {allowed_envs}")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level"""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v.upper()
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from string or list"""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v
    
    # ========================================================================
    # COMPUTED PROPERTIES
    # ========================================================================
    
    # ------------------------------------------------------------------------
    # Backward-compat alias — main.py's removed local Settings class exposed
    # `api_version`. Other modules use module-local "version" strings so this
    # alias is only needed for main.py. Keep until main.py is migrated to read
    # `settings.VERSION` directly (low-risk refactor, low priority).
    # ------------------------------------------------------------------------
    @property
    def api_version(self) -> str:
        return self.VERSION

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode"""
        return self.ENVIRONMENT == "testing"
    
    @property
    def database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return {
            "supabase_url": self.SUPABASE_URL,
            "supabase_key": self.SUPABASE_SERVICE_ROLE_KEY,
            "database_url": self.DATABASE_URL,
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT
        }
    
    @property
    def firebase_config(self) -> Dict[str, Any]:
        """Get Firebase configuration using actual secret names"""
        return {
            "project_id": self.FIREBASE_PROJECT_ID,
            "service_account": self.FIREBASE_SERVICE_ACCOUNT_TAXASGE_DEV,
            "android_app_id": self.FIREBASE_ANDROID_APP_ID,
            "storage_bucket": self.FIREBASE_STORAGE_BUCKET
        }
    
    @property
    def monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring and notification configuration"""
        return {
            "sonar_token": self.SONAR_TOKEN,
            "slack_webhook": self.SLACK_WEBHOOK_URL
        }
    
    @property
    def ai_config(self) -> Dict[str, Any]:
        """Get AI/ML configuration (legacy - deprecated, using Gemini now)"""
        return {
            "max_tokens": self.AI_MAX_TOKENS,
            "confidence_threshold": self.AI_CONFIDENCE_THRESHOLD
        }

    @property
    def gemini_config(self) -> Dict[str, Any]:
        """Get Gemini AI configuration"""
        return {
            "project": self.GOOGLE_CLOUD_PROJECT,
            "location": self.GOOGLE_CLOUD_LOCATION,
            "chat_model": self.GEMINI_CHAT_MODEL,
            "pro_model": self.GEMINI_PRO_MODEL,
            "embedding_model": self.GEMINI_EMBEDDING_MODEL,
            "max_output_tokens": self.GEMINI_MAX_OUTPUT_TOKENS,
            "temperature": self.GEMINI_TEMPERATURE,
            "top_p": self.GEMINI_TOP_P,
            "top_k": self.GEMINI_TOP_K,
        }

    @property
    def rag_config(self) -> Dict[str, Any]:
        """Get RAG configuration"""
        return {
            "embedding_dimensions": self.EMBEDDING_DIMENSIONS,
            "embedding_batch_size": self.EMBEDDING_BATCH_SIZE,
            "search_top_k": self.SEMANTIC_SEARCH_TOP_K,
            "similarity_threshold": self.SEMANTIC_SEARCH_SIMILARITY_THRESHOLD,
            "max_context_services": self.RAG_MAX_CONTEXT_SERVICES,
            "max_context_documents": self.RAG_MAX_CONTEXT_DOCUMENTS, # New
            "conversation_history_length": self.RAG_CONVERSATION_HISTORY_LENGTH,
            "max_context_tokens": self.MAX_CONTEXT_TOKENS, # New
            "pdf_chunk_size": self.PDF_CHUNK_SIZE,
            "pdf_chunk_overlap": self.PDF_CHUNK_OVERLAP,
            "suggestion_similarity_threshold": self.SUGGESTION_SIMILARITY_THRESHOLD,
            "extended_search_top_k": self.RAG_EXTENDED_SEARCH_TOP_K,
            "min_context_length": self.RAG_MIN_CONTEXT_LENGTH,
        }
    
    # ========================================================================
    # ENVIRONMENT-SPECIFIC CONFIGURATIONS
    # ========================================================================
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins based on environment"""
        if self.CORS_ORIGINS:
            return self.CORS_ORIGINS
        
        default_origins = {
            "development": [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://localhost:8081",
                "https://taxasge-dev.web.app"
            ],
            "production": [
                "https://taxasge.app",
                "https://taxasge-prod.web.app"
            ],
            "testing": ["http://localhost:8000"]
        }
        
        return default_origins.get(self.ENVIRONMENT, default_origins["development"])
    
    def get_firebase_project_id(self) -> str:
        """Get Firebase project ID based on environment"""
        if self.FIREBASE_PROJECT_ID:
            return self.FIREBASE_PROJECT_ID
        
        project_ids = {
            "development": "taxasge-dev",
            "production": "taxasge-prod",
            "testing": "taxasge-test"
        }
        
        return project_ids.get(self.ENVIRONMENT, "taxasge-dev")
    
    # ========================================================================
    # PYDANTIC CONFIG
    # ========================================================================
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # ✅ CORRECTION: Permettre les champs supplémentaires
        
        # Custom environment variable parsing
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            """Custom environment variable parsing"""
            if field_name in ["DEBUG", "CORS_ALLOW_CREDENTIALS", "SMTP_USE_TLS", "RATE_LIMIT_ENABLED", "ENABLE_METRICS"]:
                return raw_val.lower() in ("true", "1", "yes", "on")
            return raw_val

# ============================================================================
# CONFIGURATION FACTORY
# ============================================================================

@lru_cache()
def get_settings() -> Settings:
    """
    Get settings instance (cached)
    This function is cached to ensure singleton behavior
    """
    return Settings()

# ============================================================================
# ENVIRONMENT-SPECIFIC SETTINGS
# ============================================================================

class DevelopmentSettings(Settings):
    """Development environment settings"""
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

class ProductionSettings(Settings):
    """Production environment settings"""
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

class TestingSettings(Settings):
    """Testing environment settings"""
    ENVIRONMENT: str = "testing"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

# ============================================================================
# SETTINGS FACTORY
# ============================================================================

def get_settings_by_environment(environment: str) -> Settings:
    """Get settings based on environment"""
    settings_map = {
        "development": DevelopmentSettings,
        "production": ProductionSettings,
        "testing": TestingSettings
    }
    
    settings_class = settings_map.get(environment, DevelopmentSettings)
    return settings_class()

# ============================================================================
# EXPORT DEFAULT SETTINGS
# ============================================================================

# Default settings instance
settings = get_settings()

# ============================================================================