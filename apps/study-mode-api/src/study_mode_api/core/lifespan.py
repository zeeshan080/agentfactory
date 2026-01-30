"""Application lifespan management for startup and shutdown."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .redis_cache import get_redis, start_redis, stop_redis

logger = logging.getLogger(__name__)

# Global store instance (for backwards compatibility)
_postgres_store = None


def get_postgres_store():
    """Get the PostgresStore instance (may be CachedPostgresStore)."""
    return _postgres_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles:
    - Redis connection initialization
    - CachedPostgresStore initialization with Redis layer
    - ChatKitServer creation (stored in app.state)
    - Graceful shutdown
    """
    global _postgres_store

    try:
        logger.info("=" * 60)
        logger.info("STUDY MODE API - STARTUP")
        logger.info("=" * 60)

        # Log environment status
        openai_key = os.getenv("OPENAI_API_KEY", "")
        redis_url = os.getenv("REDIS_URL", "")
        db_url = os.getenv("STUDY_MODE_CHATKIT_DATABASE_URL", "")

        logger.info(f"[ENV] OPENAI_API_KEY: {'SET' if openai_key else 'NOT SET'}")
        logger.info(f"[ENV] REDIS_URL: {'SET' if redis_url else 'NOT SET'}")
        logger.info(f"[ENV] DATABASE_URL: {'SET' if db_url else 'NOT SET'}")

        # Initialize Redis (non-blocking - app works without it)
        logger.info("[INIT] Initializing Redis...")
        await start_redis()

        redis_client = get_redis()
        if redis_client:
            logger.info("[INIT] Redis connected")
        else:
            logger.warning("[INIT] Redis NOT available - caching disabled")

        # Initialize PostgresStore
        logger.info("[INIT] Initializing PostgresStore...")
        try:
            from ..chatkit_store import CachedPostgresStore, StoreConfig

            config = StoreConfig()
            logger.info(f"[DB] URL: {config.database_url[:40]}...")

            _postgres_store = CachedPostgresStore(
                config=config,
                redis_client=redis_client,
            )
            await _postgres_store.initialize_schema()

            cache_status = "enabled" if redis_client else "disabled"
            logger.info(
                f"[DB] Pool: size={config.pool_size}, "
                f"overflow={config.max_overflow}, cache={cache_status}"
            )

            # Store in app state for route access
            app.state.postgres_store = _postgres_store

            # Create ChatKit server (following carfixer pattern)
            from ..chatkit_server import create_chatkit_server

            chatkit_server = create_chatkit_server(_postgres_store)
            app.state.chatkit_server = chatkit_server
            logger.info("[INIT] ChatKit server created")

        except Exception as e:
            logger.error(f"[INIT] PostgresStore FAILED: {e}")
            logger.warning("[INIT] Chat features DISABLED")
            _postgres_store = None
            app.state.postgres_store = None
            app.state.chatkit_server = None

        logger.info("=" * 60)
        logger.info("STARTUP COMPLETE")
        logger.info("=" * 60)

        yield

    finally:
        logger.info("=" * 60)
        logger.info("SHUTDOWN")
        logger.info("=" * 60)

        await stop_redis()

        if _postgres_store:
            await _postgres_store.close()

        logger.info("Shutdown complete")
