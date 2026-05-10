# -*- coding: utf-8 -*-
"""
Test Environment Variables - Phase 3 Validation
Valide que les .env restaures de l'historique git fonctionnent correctement
"""
import pytest
import os
from pathlib import Path


def test_env_file_exists(backend_root_path):
    """Valider que le fichier .env existe a la racine du backend"""
    env_path = backend_root_path / '.env'
    assert env_path.exists(), f".env file not found at {env_path}"


def test_env_file_not_empty(backend_root_path):
    """Valider que .env n'est pas vide"""
    env_path = backend_root_path / '.env'
    content = env_path.read_text()
    assert len(content) > 0, ".env file is empty"
    assert len(content.splitlines()) > 10, ".env file should have multiple lines"


class TestSupabaseEnvironment:
    """Tests pour les variables d'environnement Supabase restaurees"""

    def test_supabase_url(self, settings):
        """Valider SUPABASE_URL restaure Phase 3"""
        assert settings.SUPABASE_URL == "https://bpdzfkymgydjxxwlctam.supabase.co", \
            "SUPABASE_URL ne correspond pas a la valeur restauree"

    def test_supabase_anon_key_format(self, settings):
        """Valider format Supabase Anon Key (JWT)"""
        assert settings.SUPABASE_ANON_KEY is not None, "SUPABASE_ANON_KEY is None"
        assert settings.SUPABASE_ANON_KEY.startswith("eyJ"), \
            "SUPABASE_ANON_KEY should be JWT format (start with eyJ)"
        assert len(settings.SUPABASE_ANON_KEY) > 100, \
            "SUPABASE_ANON_KEY seems too short"

    def test_supabase_service_role_key_format(self, settings):
        """Valider format Supabase Service Role Key (JWT)"""
        assert settings.SUPABASE_SERVICE_ROLE_KEY is not None, \
            "SUPABASE_SERVICE_ROLE_KEY is None"
        assert settings.SUPABASE_SERVICE_ROLE_KEY.startswith("eyJ"), \
            "SUPABASE_SERVICE_ROLE_KEY should be JWT format"
        assert len(settings.SUPABASE_SERVICE_ROLE_KEY) > 100, \
            "SUPABASE_SERVICE_ROLE_KEY seems too short"

    def test_database_url_format(self, settings):
        """Valider format DATABASE_URL PostgreSQL"""
        assert settings.DATABASE_URL is not None, "DATABASE_URL is None"
        assert settings.DATABASE_URL.startswith("postgresql://"), \
            "DATABASE_URL should start with postgresql://"
        assert "bpdzfkymgydjxxwlctam.supabase.co" in settings.DATABASE_URL, \
            "DATABASE_URL should contain Supabase host"
        assert ":5432/" in settings.DATABASE_URL, \
            "DATABASE_URL should contain PostgreSQL port 5432"


class TestFirebaseEnvironment:
    """Tests pour les variables d'environnement Firebase"""

    def test_firebase_project_id(self, settings):
        """Valider FIREBASE_PROJECT_ID"""
        assert settings.FIREBASE_PROJECT_ID == "taxasge-dev", \
            "FIREBASE_PROJECT_ID should be 'taxasge-dev'"

    def test_firebase_android_app_id(self, settings):
        """Valider Firebase Android App ID format"""
        assert settings.FIREBASE_ANDROID_APP_ID is not None
        assert settings.FIREBASE_ANDROID_APP_ID.startswith("1:392159428433:"), \
            "FIREBASE_ANDROID_APP_ID format incorrect"

    def test_firebase_storage_bucket(self, settings):
        """Valider Firebase Storage Bucket"""
        assert settings.FIREBASE_STORAGE_BUCKET is not None
        assert "firebase" in settings.FIREBASE_STORAGE_BUCKET.lower(), \
            "FIREBASE_STORAGE_BUCKET should contain 'firebase'"


class TestSMTPEnvironment:
    """Tests pour la configuration email SMTP"""

    def test_smtp_username(self, settings):
        """Valider SMTP_USERNAME restaure"""
        assert settings.SMTP_USERNAME == "libressai@gmail.com", \
            "SMTP_USERNAME ne correspond pas a la valeur restauree"

    def test_smtp_host(self, settings):
        """Valider SMTP_HOST"""
        assert settings.SMTP_HOST == "smtp.gmail.com", \
            "SMTP_HOST should be smtp.gmail.com"

    def test_smtp_port(self, settings):
        """Valider SMTP_PORT"""
        assert settings.SMTP_PORT == 587, \
            "SMTP_PORT should be 587 for TLS"


class TestApplicationEnvironment:
    """Tests pour les variables d'environnement de l'application"""

    def test_environment_value(self, settings):
        """Valider ENVIRONMENT setting"""
        assert settings.ENVIRONMENT in ["development", "testing", "production"], \
            f"Invalid ENVIRONMENT value: {settings.ENVIRONMENT}"

    def test_debug_mode(self, settings):
        """Valider DEBUG mode"""
        assert isinstance(settings.DEBUG, bool), \
            "DEBUG should be boolean"
        # En development, DEBUG devrait etre True
        if settings.ENVIRONMENT == "development":
            assert settings.DEBUG is True, \
                "DEBUG should be True in development"

    def test_api_host(self, settings):
        """Valider API_HOST configuration"""
        assert settings.API_HOST is not None
        assert settings.API_HOST in ["0.0.0.0", "localhost", "127.0.0.1"], \
            "API_HOST should be valid local address"

    def test_port(self, settings):
        """Valider API_PORT configuration"""
        assert isinstance(settings.API_PORT, int), "API_PORT should be integer"
        assert 1024 <= settings.API_PORT <= 65535, \
            "API_PORT should be between 1024 and 65535"


class TestSecurityEnvironment:
    """Tests pour les variables de securite"""

    def test_secret_key_exists(self, settings):
        """Valider que SECRET_KEY existe"""
        assert settings.SECRET_KEY is not None
        assert len(settings.SECRET_KEY) > 0

    def test_jwt_secret_key_exists(self, settings):
        """Valider que JWT_SECRET_KEY existe"""
        assert settings.JWT_SECRET_KEY is not None
        assert len(settings.JWT_SECRET_KEY) > 0

    def test_access_token_expire_minutes(self, settings):
        """Valider ACCESS_TOKEN_EXPIRE_MINUTES"""
        assert isinstance(settings.ACCESS_TOKEN_EXPIRE_MINUTES, int)
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


class TestMonitoringEnvironment:
    """Tests pour les variables de monitoring"""

    def test_sonar_token_exists(self, settings):
        """Valider que SONAR_TOKEN existe"""
        assert settings.SONAR_TOKEN is not None
        assert len(settings.SONAR_TOKEN) > 0

    def test_slack_webhook_url(self, settings):
        """Valider format SLACK_WEBHOOK_URL"""
        assert settings.SLACK_WEBHOOK_URL is not None
        assert settings.SLACK_WEBHOOK_URL.startswith("https://hooks.slack.com/"), \
            "SLACK_WEBHOOK_URL should be valid Slack webhook"
