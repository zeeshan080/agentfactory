"""Tests for configuration module."""

import os


class TestSettings:
    """Test Settings configuration class."""

    def test_dev_mode_from_env(self):
        """Test dev_mode is loaded from environment."""
        os.environ["DEV_MODE"] = "true"

        # Re-import to pick up env change
        from study_mode_api.config import Settings
        settings = Settings()

        assert settings.dev_mode is True

    def test_allowed_origins_list_parsing(self):
        """Test comma-separated origins are parsed into list."""
        os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,http://example.com,https://app.com"

        from study_mode_api.config import Settings
        settings = Settings()

        assert settings.allowed_origins_list == [
            "http://localhost:3000",
            "http://example.com",
            "https://app.com",
        ]

    def test_allowed_origins_strips_whitespace(self):
        """Test whitespace is stripped from origins."""
        os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000 , http://example.com"

        from study_mode_api.config import Settings
        settings = Settings()

        assert settings.allowed_origins_list == [
            "http://localhost:3000",
            "http://example.com",
        ]

    def test_default_values(self):
        """Test default configuration values."""
        from study_mode_api.config import Settings
        # Use _env_file=None to ignore .env and test true defaults
        settings = Settings(_env_file=None)

        assert settings.content_cache_ttl == 2592000  # 30 days
        assert settings.redis_max_connections > 0  # Valid connection pool size
        assert settings.port == 8000

    def test_chat_enabled_when_chatkit_db_set(self):
        """Test chat_enabled property checks for CHATKIT database URL."""
        os.environ["STUDY_MODE_CHATKIT_DATABASE_URL"] = "postgresql://test"

        from study_mode_api.config import Settings
        settings = Settings()

        assert settings.chat_enabled is True

        # Clean up
        del os.environ["STUDY_MODE_CHATKIT_DATABASE_URL"]

    def test_chat_disabled_when_no_chatkit_db(self):
        """Test chat_enabled is False without CHATKIT database URL."""
        if "STUDY_MODE_CHATKIT_DATABASE_URL" in os.environ:
            del os.environ["STUDY_MODE_CHATKIT_DATABASE_URL"]

        from study_mode_api.config import Settings
        settings = Settings()

        assert settings.chat_enabled is False
