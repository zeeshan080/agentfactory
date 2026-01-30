"""Production-grade rate limiting with Redis Lua script."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Annotated

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

from .redis_cache import get_redis

logger = logging.getLogger(__name__)

# Production-grade atomic rate limiting with Lua
RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('incr', key)
if current == 1 then
    redis.call('pexpire', key, window)
end
local ttl = redis.call('pttl', key)
if current > limit then
    return {current, window, ttl}
end
return {current, window, 0}
"""


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""

    times: Annotated[int, Field(ge=0)] = 20  # 20 requests per window (spec requirement)
    milliseconds: Annotated[int, Field(ge=-1)] = 0
    seconds: Annotated[int, Field(ge=-1)] = 0
    minutes: Annotated[int, Field(ge=-1)] = 1  # Default: 1 minute window
    hours: Annotated[int, Field(ge=-1)] = 0

    def get_window(self) -> int:
        """Calculate total window in milliseconds."""
        return (
            self.milliseconds
            + 1000 * self.seconds
            + 60000 * self.minutes
            + 3600000 * self.hours
        )


class RateLimiter:
    """Production-grade rate limiter with Redis and Lua script."""

    def __init__(
        self,
        redis_key: str,
        config: RateLimitConfig | None = None,
        identifier: Callable[[Request], str] | None = None,
        callback: Callable[[Request, Response, int], None] | None = None,
    ):
        self.redis_key = redis_key
        self.config = config or RateLimitConfig()
        self.identifier = identifier or self._default_identifier
        self.callback = callback or self._default_callback
        self._lua_script_sha: str | None = None

    async def _load_lua_script(self, redis) -> str:
        """Load Lua script into Redis."""
        if not self._lua_script_sha:
            self._lua_script_sha = await redis.script_load(RATE_LIMIT_SCRIPT)
        return self._lua_script_sha

    @staticmethod
    def _default_identifier(request: Request) -> str:
        """Default function to identify clients (by IP or user ID)."""
        # Try to get user_id from header first (ChatKit internal requests)
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            # Then try query params (direct API calls)
            user_id = request.query_params.get("user_id")
        if user_id:
            return f"user:{user_id}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    @staticmethod
    async def _default_callback(
        request: Request, response: Response, retry_after: int
    ) -> None:
        """Default callback when rate limit is exceeded."""
        logger.warning(
            f"Rate limit exceeded for {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after_ms": retry_after,
                "message": f"Too many requests. Retry in {retry_after / 1000:.1f}s.",
            },
        )

    async def _check_rate_limit(self, request: Request) -> dict[str, int | str]:
        """Check rate limit using Redis Lua script."""
        redis_client = get_redis()

        # Fail open if Redis unavailable
        if not redis_client:
            logger.warning("[RateLimit] Redis not available, allowing request (fail-open)")
            return {
                "current": 1,
                "limit": self.config.times,
                "remaining": self.config.times - 1,
                "reset_after": self.config.get_window(),
            }

        try:
            script_sha = await self._load_lua_script(redis_client)

            # Get identifier (e.g., user ID or IP address)
            identifier = self._default_identifier(request)
            key = f"rate_limit:{self.redis_key}:{identifier}"
            window_ms = self.config.get_window()
            logger.info(f"[RateLimit] Identifier resolved: {identifier}")

            # Execute Lua script for atomic operations
            current, window, ttl = await redis_client.evalsha(
                script_sha,
                1,  # number of keys
                key,  # key
                str(self.config.times),  # limit
                str(window_ms),  # window in ms
            )

            logger.info(
                f"[RateLimit] Redis key={key}, current={current}, "
                f"limit={self.config.times}, window={window_ms}ms, ttl={ttl}ms"
            )

            remaining = max(0, self.config.times - current)
            if current > self.config.times:
                remaining = -1

            return {
                "current": current,
                "limit": self.config.times,
                "remaining": remaining,
                "reset_after": ttl if ttl > 0 else window_ms,
            }

        except Exception as e:
            # Fail open but log the error
            logger.error(f"Rate limit check failed: {e}")
            return {
                "current": 1,
                "limit": self.config.times,
                "remaining": self.config.times - 1,
                "reset_after": self.config.get_window(),
            }


def rate_limit(
    redis_key: str,
    max_requests: int = 20,
    period_minutes: int = 1,
    identifier: Callable[[Request], str] | None = None,
    callback: Callable[[Request, Response, int], None] | None = None,
):
    """
    Production-grade rate limiting decorator for FastAPI endpoints.

    Features:
    - Atomic rate limiting using Redis Lua script
    - Per-user identification (user_id param or IP fallback)
    - Rate limit headers in response
    - Graceful degradation (fail-open) if Redis unavailable
    - 429 response with retry information

    Usage:
        @app.get("/api/resource")
        @rate_limit("api", max_requests=20, period_minutes=1)
        async def get_resource(request: Request, response: Response):
            return {"data": "resource"}
    """
    config = RateLimitConfig(times=max_requests, minutes=period_minutes)
    limiter = RateLimiter(redis_key, config, identifier, callback)

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and response
            request = kwargs.get("request")
            response = kwargs.get("response")

            if not request or not response:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                    elif isinstance(arg, Response):
                        response = arg

            if not request or not response:
                logger.error("Rate limit decorator requires Request and Response objects")
                return await func(*args, **kwargs)

            # Check rate limit
            rate_limit_info = await limiter._check_rate_limit(request)

            # Set rate limit headers (T023 requirement)
            response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset_after"])

            # Handle rate limit exceeded
            if rate_limit_info["remaining"] < 0:
                await limiter._default_callback(
                    request, response, rate_limit_info["reset_after"]
                )

            # Execute the endpoint
            return await func(*args, **kwargs)

        return wrapper

    return decorator
