"""Tests for CachedPostgresStore Redis caching layer.

Tests write-through caching, cache invalidation, and background writes.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from study_mode_api.chatkit_store.cached_postgres_store import CachedPostgresStore
from study_mode_api.chatkit_store.context import RequestContext


class TestCachedStoreInitialization:
    """Test cached store initialization."""

    def test_cache_enabled_with_redis(self):
        """Test caching is enabled when Redis client provided."""
        mock_redis = MagicMock()
        mock_engine = MagicMock()

        store = CachedPostgresStore(engine=mock_engine, redis_client=mock_redis)

        assert store.cache_enabled is True
        assert store.redis == mock_redis

    def test_cache_disabled_without_redis(self):
        """Test caching is disabled when no Redis client."""
        mock_engine = MagicMock()

        store = CachedPostgresStore(engine=mock_engine, redis_client=None)

        assert store.cache_enabled is False
        assert store.redis is None

    def test_ttl_defaults(self):
        """Test cache TTL default values."""
        mock_engine = MagicMock()

        store = CachedPostgresStore(engine=mock_engine)

        assert store.thread_ttl == 3600  # 1 hour
        assert store.items_ttl == 1800  # 30 minutes
        assert store.list_ttl == 600  # 10 minutes


class TestCacheKeys:
    """Test cache key generation."""

    @pytest.fixture
    def store(self):
        """Create cached store with mock engine."""
        mock_engine = MagicMock()
        return CachedPostgresStore(engine=mock_engine)

    def test_thread_cache_key(self, store):
        """Test thread cache key format."""
        key = store._get_thread_cache_key("user-123", "thread-456")
        assert key == "chatkit:thread:user-123:thread-456"

    def test_items_cache_key(self, store):
        """Test items cache key format."""
        key = store._get_items_cache_key("user-123", "thread-456", 30, "desc")
        assert key == "chatkit:items:user-123:thread-456:30:desc"

    def test_list_cache_key(self, store):
        """Test thread list cache key format."""
        key = store._get_list_cache_key("user-123", 20, "desc")
        assert key == "chatkit:threads:user-123:20:desc"


class TestCacheOperations:
    """Test cache read/write operations."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        redis.ttl = AsyncMock(return_value=1800)
        return redis

    @pytest.fixture
    def store(self, mock_redis):
        """Create cached store with mock Redis."""
        mock_engine = MagicMock()
        return CachedPostgresStore(engine=mock_engine, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_get_cached_returns_value(self, store, mock_redis):
        """Test _get_cached returns cached value."""
        mock_redis.get = AsyncMock(return_value='{"key": "value"}')

        result = await store._get_cached("test_key")

        assert result == {"key": "value"}
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_cached_returns_none_on_miss(self, store, mock_redis):
        """Test _get_cached returns None on cache miss."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await store._get_cached("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_returns_none_on_error(self, store, mock_redis):
        """Test _get_cached returns None on Redis error."""
        mock_redis.get = AsyncMock(side_effect=Exception("Connection error"))

        result = await store._get_cached("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_cached_stores_value(self, store, mock_redis):
        """Test _set_cached stores value with TTL."""
        await store._set_cached("test_key", {"data": "value"}, 3600)

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == "test_key"
        assert args[0][1] == 3600
        assert "data" in args[0][2]

    @pytest.mark.asyncio
    async def test_delete_cached(self, store, mock_redis):
        """Test _delete_cached removes key."""
        await store._delete_cached("test_key")

        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_pattern(self, store, mock_redis):
        """Test _delete_pattern removes matching keys."""
        mock_redis.scan = AsyncMock(return_value=(0, ["key1", "key2"]))

        await store._delete_pattern("chatkit:items:*")

        mock_redis.scan.assert_called()
        mock_redis.delete.assert_called_with("key1", "key2")


class TestCacheDisabled:
    """Test behavior when caching is disabled."""

    @pytest.fixture
    def store_no_cache(self):
        """Create store without Redis."""
        mock_engine = MagicMock()
        return CachedPostgresStore(engine=mock_engine, redis_client=None)

    @pytest.mark.asyncio
    async def test_get_cached_returns_none(self, store_no_cache):
        """Test _get_cached returns None when cache disabled."""
        result = await store_no_cache._get_cached("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_cached_is_noop(self, store_no_cache):
        """Test _set_cached does nothing when cache disabled."""
        # Should not raise
        await store_no_cache._set_cached("test_key", {"data": "value"}, 3600)

    @pytest.mark.asyncio
    async def test_delete_cached_is_noop(self, store_no_cache):
        """Test _delete_cached does nothing when cache disabled."""
        # Should not raise
        await store_no_cache._delete_cached("test_key")


class TestBackgroundWriter:
    """Test background write queue."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def store(self, mock_redis):
        """Create cached store."""
        mock_engine = MagicMock()
        return CachedPostgresStore(engine=mock_engine, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_start_background_writer(self, store):
        """Test background writer starts."""
        await store.start_background_writer()

        assert store._background_task is not None

        # Cleanup
        await store.stop_background_writer()

    @pytest.mark.asyncio
    async def test_stop_background_writer(self, store):
        """Test background writer stops gracefully."""
        await store.start_background_writer()
        await store.stop_background_writer()

        assert store._background_task is None

    @pytest.mark.asyncio
    async def test_queue_background_write_starts_worker(self, store):
        """Test queuing starts background worker if not running."""
        async def dummy_operation():
            pass

        assert store._background_task is None

        await store._queue_background_write(dummy_operation)

        assert store._background_task is not None

        # Cleanup
        await store.stop_background_writer()


class TestLoadThreadCaching:
    """Test load_thread with caching."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def context(self):
        """Create test context."""
        return RequestContext(user_id="user-123")

    @pytest.mark.asyncio
    async def test_load_thread_cache_hit(self, mock_redis, context):
        """Test load_thread cache key generation."""
        mock_engine = MagicMock()
        store = CachedPostgresStore(engine=mock_engine, redis_client=mock_redis)

        # Verify cache key format
        cache_key = store._get_thread_cache_key("user-123", "thread-123")
        assert cache_key == "chatkit:thread:user-123:thread-123"

    @pytest.mark.asyncio
    async def test_get_cached_parses_json(self, mock_redis):
        """Test _get_cached parses JSON correctly."""
        cached_data = '{"thread": {"id": "thread-123"}}'
        mock_redis.get = AsyncMock(return_value=cached_data)

        mock_engine = MagicMock()
        store = CachedPostgresStore(engine=mock_engine, redis_client=mock_redis)

        result = await store._get_cached("test_key")

        assert result == {"thread": {"id": "thread-123"}}


class TestInvalidation:
    """Test cache invalidation."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis."""
        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest.fixture
    def store(self, mock_redis):
        """Create cached store."""
        mock_engine = MagicMock()
        return CachedPostgresStore(engine=mock_engine, redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_invalidate_thread_cache(self, store, mock_redis):
        """Test thread cache invalidation."""
        mock_redis.scan = AsyncMock(
            side_effect=[
                (0, ["chatkit:items:user-123:thread-456:30:desc"]),
                (0, ["chatkit:threads:user-123:20:desc"]),
            ]
        )

        await store._invalidate_thread_cache("user-123", "thread-456")

        # Should delete thread metadata
        mock_redis.delete.assert_any_call("chatkit:thread:user-123:thread-456")

    @pytest.mark.asyncio
    async def test_invalidation_handles_errors(self, store, mock_redis):
        """Test invalidation handles Redis errors gracefully."""
        mock_redis.delete = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise
        await store._invalidate_thread_cache("user-123", "thread-456")
