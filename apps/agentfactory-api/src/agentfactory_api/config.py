"""Configuration management for AgentFactory API.

Uses pydantic-settings for environment variable loading with validation.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Config(BaseSettings):
    """AgentFactory API configuration loaded from environment variables.

    Environment variables are prefixed with AGENTFACTORY_ by default.
    Example: AGENTFACTORY_DATABASE_URL=postgresql://...
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENTFACTORY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # =========================================================================
    # Database Configuration
    # =========================================================================
    # PostgreSQL: postgresql+asyncpg://user:pass@host/db
    database_url: str | None = None

    @property
    def effective_database_url(self) -> str:
        """Get database URL, defaulting to SQLite for development.

        Handles common URL formats:
        - postgresql://... → postgresql+asyncpg://...
        - postgres://... → postgresql+asyncpg://...
        - Removes sslmode=require (asyncpg uses ssl=require instead)
        """
        if not self.database_url:
            return "sqlite+aiosqlite:///./agentfactory.db"

        url = self.database_url

        # Auto-convert to asyncpg driver
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)

        # Convert sslmode to asyncpg's ssl parameter
        if "sslmode=require" in url:
            url = url.replace("sslmode=require", "ssl=require")
        elif "sslmode=verify-full" in url:
            url = url.replace("sslmode=verify-full", "ssl=verify-full")

        return url

    # =========================================================================
    # R2 Storage Configuration
    # =========================================================================
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str = "agentfactory-content"

    @property
    def r2_endpoint(self) -> str | None:
        """Get R2 endpoint URL from account ID."""
        if not self.r2_account_id:
            return None
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def storage_enabled(self) -> bool:
        """Check if R2 storage is configured."""
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
        )

    # =========================================================================
    # OpenAI Configuration
    # =========================================================================
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    @property
    def openai_enabled(self) -> bool:
        """Check if OpenAI is configured."""
        return bool(self.openai_api_key)

    # =========================================================================
    # Authentication (SSO)
    # =========================================================================
    # SSO server URL (issuer for JWTs)
    auth_server_url: str | None = None

    # JWKS endpoint path for JWT verification
    auth_jwks_path: str = "/api/auth/jwks"

    # OAuth client ID (audience for id_token validation)
    auth_client_id: str = "agent-factory-public-client"

    # JWKS cache TTL in seconds
    jwks_cache_ttl: int = 3600  # 1 hour

    # Token validation cache TTL in seconds
    token_cache_ttl: int = 300  # 5 minutes

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return bool(self.auth_server_url)

    @property
    def jwks_url(self) -> str | None:
        """Get full JWKS endpoint URL."""
        if not self.auth_server_url:
            return None
        return f"{self.auth_server_url.rstrip('/')}{self.auth_jwks_path}"

    # =========================================================================
    # Server Configuration
    # =========================================================================
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    # CORS origins (comma-separated)
    cors_origins: str = "http://localhost:3000,http://localhost:3002"

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # =========================================================================
    # Observability
    # =========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


# Global config instance (singleton pattern)
_config: Config | None = None


def get_config() -> Config:
    """Get or create the global configuration instance.

    Returns:
        Config: Validated configuration instance.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
