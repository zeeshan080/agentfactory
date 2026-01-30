"""Tests for PostgreSQL store implementation.

Tests connection pooling, user isolation, and CRUD operations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from study_mode_api.chatkit_store.config import StoreConfig
from study_mode_api.chatkit_store.context import RequestContext
from study_mode_api.chatkit_store.postgres_store import (
    ItemData,
    PostgresStore,
    ThreadData,
)


class TestStoreConfig:
    """Test store configuration."""

    def test_default_pool_settings(self, monkeypatch):
        """Test default connection pool settings."""
        # Clear env vars that might override defaults
        monkeypatch.delenv("STUDY_MODE_CHATKIT_POOL_SIZE", raising=False)
        monkeypatch.delenv("STUDY_MODE_CHATKIT_MAX_OVERFLOW", raising=False)
        monkeypatch.delenv("STUDY_MODE_CHATKIT_POOL_TIMEOUT", raising=False)
        monkeypatch.delenv("STUDY_MODE_CHATKIT_POOL_RECYCLE", raising=False)

        # Use _env_file=None to ignore .env and test true defaults
        config = StoreConfig(database_url="postgresql://test", _env_file=None)

        assert config.pool_size == 20
        assert config.max_overflow == 10
        assert config.pool_timeout == 30.0
        assert config.pool_recycle == 3600

    def test_validates_database_url_prefix(self):
        """Test database URL must start with postgresql://."""
        with pytest.raises(ValueError) as exc_info:
            StoreConfig(database_url="mysql://test")

        assert "postgresql://" in str(exc_info.value)

    def test_converts_postgresql_to_asyncpg(self):
        """Test postgresql:// is converted to postgresql+asyncpg://."""
        config = StoreConfig(database_url="postgresql://user:pass@host/db")

        assert config.database_url.startswith("postgresql+asyncpg://")

    def test_fixes_ssl_parameters(self):
        """Test sslmode is converted to ssl for asyncpg."""
        config = StoreConfig(
            database_url="postgresql://user:pass@host/db?sslmode=require"
        )

        assert "ssl=require" in config.database_url
        assert "sslmode=require" not in config.database_url

    def test_schema_name_default(self):
        """Test default schema name."""
        config = StoreConfig(database_url="postgresql://test")

        assert config.schema_name == "study_mode_chat"


class TestRequestContext:
    """Test request context."""

    def test_user_id_required(self):
        """Test user_id is required."""
        with pytest.raises(ValueError):
            RequestContext(user_id="")

    def test_context_creation(self):
        """Test context with all fields."""
        context = RequestContext(
            user_id="user-123",
            organization_id="org-456",
            request_id="req-789",
            metadata={"lesson_path": "/docs/test"},
        )

        assert context.user_id == "user-123"
        assert context.organization_id == "org-456"
        assert context.request_id == "req-789"
        assert context.metadata["lesson_path"] == "/docs/test"

    def test_optional_fields(self):
        """Test optional fields default to None/empty."""
        context = RequestContext(user_id="user-123")

        assert context.organization_id is None
        assert context.request_id is None
        assert context.metadata == {}


class TestPostgresStore:
    """Test PostgresStore implementation."""

    @pytest.fixture
    def mock_engine(self):
        """Create mock SQLAlchemy engine."""
        engine = MagicMock()
        engine.dispose = AsyncMock()
        return engine

    @pytest.fixture
    def store(self, mock_engine):
        """Create store with mock engine."""
        return PostgresStore(engine=mock_engine)

    @pytest.fixture
    def context(self):
        """Create test request context."""
        return RequestContext(
            user_id="test-user-123",
            organization_id="test-org",
        )

    def test_store_initialization(self, mock_engine):
        """Test store initializes with engine."""
        store = PostgresStore(engine=mock_engine)

        assert store.engine == mock_engine
        assert store.session_factory is not None

    def test_store_creates_engine_from_config(self):
        """Test store creates engine from config."""
        with patch(
            "study_mode_api.chatkit_store.postgres_store.create_async_engine"
        ) as mock_create:
            mock_create.return_value = MagicMock()

            config = StoreConfig(database_url="postgresql://test")
            _store = PostgresStore(config=config)  # noqa: F841

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["pool_pre_ping"] is True  # T019

    def test_get_table_name(self, store):
        """Test table name includes schema."""
        store.config = StoreConfig(database_url="postgresql://test")

        table_name = store._get_table_name("threads")

        assert table_name == "study_mode_chat.threads"

    @pytest.mark.asyncio
    async def test_close_disposes_engine(self, store, mock_engine):
        """Test close disposes connection pool."""
        await store.close()

        mock_engine.dispose.assert_called_once()


class TestThreadData:
    """Test thread data wrapper."""

    def test_thread_data_serialization(self):
        """Test ThreadData wraps ThreadMetadata for serialization."""
        from chatkit.types import ThreadMetadata

        thread = ThreadMetadata(
            id="thread-123",
            created_at=datetime.now(),
        )

        data = ThreadData(thread=thread)

        assert data.thread.id == "thread-123"
        json_str = data.model_dump_json()
        assert "thread-123" in json_str


class TestItemData:
    """Test item data wrapper."""

    def test_item_data_model_exists(self):
        """Test ItemData model is properly defined for wrapping ThreadItem."""
        # ItemData wraps the complex ThreadItem union type
        # The actual serialization is tested through integration tests
        # Here we verify the model structure is correct
        assert hasattr(ItemData, "model_fields")
        assert "item" in ItemData.model_fields

        # Verify the model accepts the expected field
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            # Empty item should fail validation
            ItemData(item=None)


class TestConnectionPoolResilience:
    """Test connection pool resilience (US2)."""

    def test_pool_pre_ping_enabled(self):
        """Test pool_pre_ping is enabled (T019)."""
        with patch(
            "study_mode_api.chatkit_store.postgres_store.create_async_engine"
        ) as mock_create:
            mock_create.return_value = MagicMock()

            config = StoreConfig(database_url="postgresql://test")
            PostgresStore(config=config)

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["pool_pre_ping"] is True

    def test_connection_timeout_configured(self):
        """Test connection timeout is set (T020)."""
        with patch(
            "study_mode_api.chatkit_store.postgres_store.create_async_engine"
        ) as mock_create:
            mock_create.return_value = MagicMock()

            config = StoreConfig(database_url="postgresql://test")
            PostgresStore(config=config)

            call_kwargs = mock_create.call_args.kwargs
            connect_args = call_kwargs["connect_args"]
            assert connect_args["command_timeout"] == 30

    def test_statement_timeout_configured(self):
        """Test statement timeout is set in server settings."""
        with patch(
            "study_mode_api.chatkit_store.postgres_store.create_async_engine"
        ) as mock_create:
            mock_create.return_value = MagicMock()

            config = StoreConfig(database_url="postgresql://test", statement_timeout=60000)
            PostgresStore(config=config)

            call_kwargs = mock_create.call_args.kwargs
            server_settings = call_kwargs["connect_args"]["server_settings"]
            assert server_settings["statement_timeout"] == "60000"

    @pytest.mark.asyncio
    async def test_warm_connection_pool(self):
        """Test connection pool warming."""
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.connect = MagicMock(return_value=mock_conn)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        store = PostgresStore(engine=mock_engine)
        store.config = StoreConfig(database_url="postgresql://test", pool_size=5)

        await store._warm_connection_pool()

        # Should warm up to min(3, pool_size) connections
        assert mock_conn.execute.call_count >= 1
