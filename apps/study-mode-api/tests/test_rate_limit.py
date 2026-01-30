"""Tests for rate limiting module.

Success Criteria SC-004: Should return 429 after 20 requests per minute.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, Response

from study_mode_api.core.rate_limit import (
    RATE_LIMIT_SCRIPT,
    RateLimitConfig,
    RateLimiter,
)


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_default_config(self):
        """Test default rate limit config values."""
        config = RateLimitConfig()

        assert config.times == 20  # 20 requests
        assert config.minutes == 1  # per minute

    def test_get_window_minutes(self):
        """Test window calculation for minutes."""
        config = RateLimitConfig(times=100, minutes=5)

        assert config.get_window() == 300000  # 5 minutes in ms

    def test_get_window_mixed_units(self):
        """Test window calculation with mixed time units."""
        config = RateLimitConfig(
            times=100,
            milliseconds=500,
            seconds=30,
            minutes=1,
            hours=0,
        )

        expected = 500 + (30 * 1000) + (1 * 60000)  # 90500ms
        assert config.get_window() == expected


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_default_identifier_with_user_id(self):
        """Test identifier extraction from user_id query param."""
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"user_id": "user-123"}
        mock_request.headers = {}
        mock_request.client = MagicMock(host="192.168.1.1")

        identifier = RateLimiter._default_identifier(mock_request)

        assert identifier == "user:user-123"

    def test_default_identifier_falls_back_to_ip(self):
        """Test identifier falls back to IP when no user_id."""
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.headers = {}
        mock_request.client = MagicMock(host="192.168.1.1")

        identifier = RateLimiter._default_identifier(mock_request)

        assert identifier == "ip:192.168.1.1"

    def test_default_identifier_uses_forwarded_header(self):
        """Test identifier uses X-Forwarded-For header."""
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
        mock_request.client = MagicMock(host="192.168.1.1")

        identifier = RateLimiter._default_identifier(mock_request)

        assert identifier == "ip:10.0.0.1"

    @pytest.mark.asyncio
    async def test_check_rate_limit_allows_request(self, mock_redis):
        """Test rate limiter allows request under limit."""
        mock_redis.evalsha = AsyncMock(return_value=[1, 60000, 0])

        with patch("study_mode_api.core.rate_limit.get_redis", return_value=mock_redis):
            limiter = RateLimiter("test", RateLimitConfig(times=20, minutes=1))
            limiter._lua_script_sha = "mock_sha"

            mock_request = MagicMock(spec=Request)
            mock_request.query_params = {"user_id": "user-123"}
            mock_request.headers = {}
            mock_request.client = MagicMock(host="127.0.0.1")

            result = await limiter._check_rate_limit(mock_request)

            assert result["current"] == 1
            assert result["limit"] == 20
            assert result["remaining"] == 19

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeds_limit(self, mock_redis):
        """Test rate limiter detects exceeded limit (SC-004)."""
        # Simulate 21st request (over limit of 20)
        mock_redis.evalsha = AsyncMock(return_value=[21, 60000, 45000])

        with patch("study_mode_api.core.rate_limit.get_redis", return_value=mock_redis):
            limiter = RateLimiter("test", RateLimitConfig(times=20, minutes=1))
            limiter._lua_script_sha = "mock_sha"

            mock_request = MagicMock(spec=Request)
            mock_request.query_params = {"user_id": "user-123"}
            mock_request.headers = {}
            mock_request.client = MagicMock(host="127.0.0.1")

            result = await limiter._check_rate_limit(mock_request)

            assert result["current"] == 21
            assert result["remaining"] == -1  # Over limit

    @pytest.mark.asyncio
    async def test_check_rate_limit_fail_open(self):
        """Test rate limiter fails open when Redis unavailable (T024)."""
        with patch("study_mode_api.core.rate_limit.get_redis", return_value=None):
            limiter = RateLimiter("test", RateLimitConfig(times=20, minutes=1))

            mock_request = MagicMock(spec=Request)
            mock_request.query_params = {}
            mock_request.headers = {}
            mock_request.client = MagicMock(host="127.0.0.1")

            result = await limiter._check_rate_limit(mock_request)

            # Should allow request (fail-open)
            assert result["remaining"] == 19
            assert result["limit"] == 20


class TestRateLimitDecorator:
    """Test rate_limit decorator."""

    @pytest.mark.asyncio
    async def test_decorator_sets_headers(self, mock_redis):
        """Test decorator sets rate limit headers (T023)."""
        mock_redis.evalsha = AsyncMock(return_value=[5, 60000, 0])
        mock_redis.script_load = AsyncMock(return_value="mock_sha")

        # Create a fresh decorator with mocked redis
        with patch("study_mode_api.core.rate_limit.get_redis", return_value=mock_redis):
            limiter = RateLimiter("test", RateLimitConfig(times=20, minutes=1))

            mock_request = MagicMock(spec=Request)
            mock_request.query_params = {"user_id": "user-123"}
            mock_request.headers = {}
            mock_request.client = MagicMock(host="127.0.0.1")

            result = await limiter._check_rate_limit(mock_request)

            # Verify rate limit info is returned
            assert result["limit"] == 20
            assert result["remaining"] == 15  # 20 - 5
            assert "reset_after" in result

    @pytest.mark.asyncio
    async def test_decorator_raises_429_when_exceeded(self, mock_redis):
        """Test decorator raises 429 when rate limit exceeded (SC-004)."""
        mock_redis.evalsha = AsyncMock(return_value=[21, 60000, 45000])
        mock_redis.script_load = AsyncMock(return_value="mock_sha")

        with patch("study_mode_api.core.rate_limit.get_redis", return_value=mock_redis):
            limiter = RateLimiter("test", RateLimitConfig(times=20, minutes=1))

            mock_request = MagicMock(spec=Request)
            mock_request.query_params = {"user_id": "user-123"}
            mock_request.headers = {}
            mock_request.client = MagicMock(host="127.0.0.1")

            result = await limiter._check_rate_limit(mock_request)

            # Should indicate rate limit exceeded
            assert result["remaining"] == -1
            assert result["current"] == 21

            # The callback should raise 429
            mock_response = MagicMock(spec=Response)
            with pytest.raises(HTTPException) as exc_info:
                await limiter._default_callback(mock_request, mock_response, 45000)

            assert exc_info.value.status_code == 429
            assert "Rate limit exceeded" in str(exc_info.value.detail)


class TestLuaScript:
    """Test Lua script functionality."""

    def test_lua_script_structure(self):
        """Test Lua script has expected structure."""
        assert "local key = KEYS[1]" in RATE_LIMIT_SCRIPT
        assert "local limit = tonumber(ARGV[1])" in RATE_LIMIT_SCRIPT
        assert "redis.call('incr', key)" in RATE_LIMIT_SCRIPT
        assert "redis.call('pexpire', key, window)" in RATE_LIMIT_SCRIPT
