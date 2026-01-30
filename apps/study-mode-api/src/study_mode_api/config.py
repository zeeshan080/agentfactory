"""Application configuration from environment variables."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore STUDY_MODE_CHATKIT_* vars (handled by StoreConfig)
    )

    # Redis (optional - caching degrades gracefully without it)
    redis_url: str = ""
    redis_password: str = ""
    redis_max_connections: int = 10

    # GitHub content loading
    github_token: str = ""
    github_repo: str = "panaversity/agentfactory"

    # Content cache TTL (seconds) - 30 days (invalidate via GitHub Action on push)
    content_cache_ttl: int = 2592000  # 30 days

    # SSO (required for production)
    sso_url: str = ""

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Debug
    debug: bool = False
    log_level: str = "INFO"

    # Dev mode - bypasses auth for local development
    dev_mode: bool = False
    dev_user_id: str = "dev-user-123"
    dev_user_email: str = "dev@localhost"
    dev_user_name: str = "Dev User"

    # OpenAI API Key (required for chat)
    openai_api_key: str | None = None

    # Server
    port: int = 8000

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated origins into list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def chat_enabled(self) -> bool:
        """Check if chat features are enabled (STUDY_MODE_CHATKIT_DATABASE_URL set)."""
        return os.getenv("STUDY_MODE_CHATKIT_DATABASE_URL") is not None


settings = Settings()
