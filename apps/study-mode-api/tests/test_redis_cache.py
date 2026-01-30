"""Tests for Redis caching module.

Success Criteria SC-002: Cached content should be retrieved in <50ms.
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from study_mode_api.core.redis_cache import (
    CustomJSONEncoder,
    cache_response,
    safe_redis_get,
    safe_redis_set,
    serialize_result,
    start_redis,
    stop_redis,
)


class TestRedisConnection:
    """Test Redis connection management."""

    @pytest.mark.asyncio
    async def test_start_redis_success(self, mock_redis):
        """Test successful Redis connection."""
        with patch("study_mode_api.core.redis_cache.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"
            mock_settings.redis_password = "test"
            mock_settings.redis_max_connections = 10

            with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
                await start_redis()

                mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_redis_no_url(self):
        """Test Redis initialization skipped when no URL provided."""
        # Reset global state
        import study_mode_api.core.redis_cache as redis_module
        redis_module._aredis = None

        with patch("study_mode_api.core.redis_cache.settings") as mock_settings:
            mock_settings.redis_url = ""

            await start_redis()

            # Should not raise, just log warning
            assert redis_module._aredis is None

    @pytest.mark.asyncio
    async def test_stop_redis_closes_connection(self, mock_redis):
        """Test Redis connection is properly closed."""
        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            await stop_redis()

            mock_redis.aclose.assert_called_once()


class TestSafeRedisOperations:
    """Test safe Redis get/set operations."""

    @pytest.mark.asyncio
    async def test_safe_redis_get_returns_value(self, mock_redis):
        """Test safe_redis_get returns cached value."""
        mock_redis.get = AsyncMock(return_value='{"test": "data"}')

        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            result = await safe_redis_get("test_key")

            assert result == '{"test": "data"}'
            mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_safe_redis_get_returns_none_on_error(self, mock_redis):
        """Test safe_redis_get returns None on error (graceful degradation)."""
        mock_redis.get = AsyncMock(side_effect=Exception("Connection error"))

        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            result = await safe_redis_get("test_key")

            assert result is None

    @pytest.mark.asyncio
    async def test_safe_redis_get_returns_none_when_not_initialized(self):
        """Test safe_redis_get returns None when Redis not initialized."""
        with patch("study_mode_api.core.redis_cache._aredis", None):
            result = await safe_redis_get("test_key")

            assert result is None

    @pytest.mark.asyncio
    async def test_safe_redis_set_stores_value(self, mock_redis):
        """Test safe_redis_set stores value with TTL."""
        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            await safe_redis_set("test_key", '{"data": "value"}', 3600)

            mock_redis.setex.assert_called_once_with("test_key", 3600, '{"data": "value"}')

    @pytest.mark.asyncio
    async def test_safe_redis_set_handles_error_gracefully(self, mock_redis):
        """Test safe_redis_set doesn't raise on error."""
        mock_redis.setex = AsyncMock(side_effect=Exception("Write error"))

        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            # Should not raise
            await safe_redis_set("test_key", '{"data": "value"}', 3600)


class TestCacheResponseDecorator:
    """Test cache_response decorator."""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_function(self, mock_redis):
        """Test function is called on cache miss."""
        mock_redis.get = AsyncMock(return_value=None)

        call_count = 0

        @cache_response(ttl=3600)
        async def test_func(arg1: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"result": arg1}

        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            result = await test_func("test")

            assert result == {"result": "test"}
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_value(self, mock_redis):
        """Test cached value is returned on cache hit (SC-002: <50ms)."""
        cached_data = '{"result": "cached"}'
        mock_redis.get = AsyncMock(return_value=cached_data)

        call_count = 0

        @cache_response(ttl=3600)
        async def test_func(arg1: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"result": "fresh"}

        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            start = time.time()
            result = await test_func("test")
            elapsed_ms = (time.time() - start) * 1000

            assert result == {"result": "cached"}
            assert call_count == 0  # Function not called
            assert elapsed_ms < 50  # SC-002: <50ms for cached requests

    @pytest.mark.asyncio
    async def test_cache_decorator_graceful_degradation(self):
        """Test decorator works when Redis unavailable."""
        @cache_response(ttl=3600)
        async def test_func() -> dict:
            return {"result": "direct"}

        with patch("study_mode_api.core.redis_cache._aredis", None):
            result = await test_func()

            assert result == {"result": "direct"}


class TestSerialization:
    """Test JSON serialization utilities."""

    def test_serialize_dict(self):
        """Test serializing a plain dictionary."""
        result = serialize_result({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_serialize_list(self):
        """Test serializing a list."""
        result = serialize_result([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_custom_json_encoder_datetime(self):
        """Test CustomJSONEncoder handles datetime."""
        from datetime import datetime

        dt = datetime(2025, 1, 30, 12, 0, 0)
        result = json.dumps({"date": dt}, cls=CustomJSONEncoder)

        assert "2025-01-30T12:00:00" in result

    def test_custom_json_encoder_time(self):
        """Test CustomJSONEncoder handles time."""
        from datetime import time as dt_time

        t = dt_time(12, 30, 45)
        result = json.dumps({"time": t}, cls=CustomJSONEncoder)

        assert "12:30:45" in result
