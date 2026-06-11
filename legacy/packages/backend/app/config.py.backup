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

    # ========================================================================
    # APPLICATION SETTINGS
    # ========================================================================
    
    PROJECT_NAME: str = "TaxasGE API"
    PROJECT_DESCRIPTION: str = "API de gestion fiscale pour la Guinée Équatoriale"
    VERSION: str = "1.0.0"
    
    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="PORT")
    
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
    DATABASE_MIN_CONNECTIONS: int = Field(default=10, env="DATABASE_MIN_CONNECTIONS")
    DATABASE_MAX_CONNECTIONS: int = Field(default=50, env="DATABASE_MAX_CONNECTIONS")
    
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
    
    # TensorFlow Lite Model
    AI_MODEL_PATH: str = Field(default="assets/ml/taxasge_model.tflite", env="AI_MODEL_PATH")
    AI_TOKENIZER_PATH: str = Field(default="assets/ml/tokenizer.json", env="AI_TOKENIZER_PATH")
    AI_INTENTS_PATH: str = Field(default="assets/ml/intents.json", env="AI_INTENTS_PATH")
    
    # AI Configuration
    AI_MAX_TOKENS: int = Field(default=512, env="AI_MAX_TOKENS")
    AI_CONFIDENCE_THRESHOLD: float = Field(default=0.7, env="AI_CONFIDENCE_THRESHOLD")
    
    # ========================================================================
    # EXTERNAL SERVICES
    # ========================================================================
    
    # Bange Payment Integration
    BANGE_API_URL: Optional[str] = Field(default=None, env="BANGE_API_URL")
    BANGE_API_KEY: Optional[str] = Field(default=None, env="BANGE_API_KEY")
    BANGE_MERCHANT_ID: Optional[str] = Field(default=None, env="BANGE_MERCHANT_ID")
    
    # Email Service (MODULE_02)
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    SMTP_FROM_EMAIL: Optional[str] = Field(default=None, env="SMTP_FROM_EMAIL")
    SMTP_FROM_NAME: str = Field(default="TaxasGE Platform", env="SMTP_FROM_NAME")

    # SMTP_PASSWORD: Load from Secret Manager at startup
    # Will be set by __init__ method below
    SMTP_PASSWORD: Optional[str] = None
    
    # ========================================================================
    # CACHE SETTINGS
    # ========================================================================
    
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # 1 hour
    
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
        """Get AI/ML configuration"""
        return {
            "model_path": self.AI_MODEL_PATH,
            "tokenizer_path": self.AI_TOKENIZER_PATH,
            "intents_path": self.AI_INTENTS_PATH,
            "max_tokens": self.AI_MAX_TOKENS,
            "confidence_threshold": self.AI_CONFIDENCE_THRESHOLD
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