"""AgentFactory API - FastAPI Application.

Main entry point for the lesson personalization service.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .database import init_db
from .routes.personalize import router as personalize_router
from .routes.preferences import router as preferences_router
from . import storage as storage_module
from . import agent as agent_module


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Runs on startup:
    - Initialize database tables (development mode)
    - Log configuration summary

    Runs on shutdown:
    - Cleanup (future: close connections, etc.)
    """
    config = get_config()

    logger.info("Starting AgentFactory API...")
    logger.info(f"Auth enabled: {config.auth_enabled}")
    logger.info(f"R2 storage enabled: {config.storage_enabled}")
    logger.info(f"OpenAI enabled: {config.openai_enabled}")

    # Initialize database tables (for development)
    # Production should use Alembic migrations
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down AgentFactory API...")


# Create FastAPI app
app = FastAPI(
    title="AgentFactory API",
    description="AI-powered lesson personalization service",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(personalize_router, prefix="/api", tags=["personalization"])
app.include_router(preferences_router, prefix="/api", tags=["preferences"])


# =============================================================================
# Health Check Endpoints
# =============================================================================


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "agentfactory-api"}


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status."""
    config = get_config()

    # Check each component
    storage_health = await storage_module.health_check()
    agent_health = await agent_module.health_check()

    # Overall status is healthy only if all enabled components are healthy
    components_healthy = True

    if config.storage_enabled and storage_health.get("status") != "healthy":
        components_healthy = False

    if config.openai_enabled and agent_health.get("status") != "healthy":
        components_healthy = False

    return {
        "status": "healthy" if components_healthy else "degraded",
        "service": "agentfactory-api",
        "components": {
            "storage": storage_health,
            "agent": agent_health,
            "auth": {
                "status": "enabled" if config.auth_enabled else "disabled",
                "issuer": config.auth_server_url if config.auth_enabled else None,
            },
        },
    }


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """Run the server using uvicorn."""
    import uvicorn

    config = get_config()

    uvicorn.run(
        "agentfactory_api.main:app",
        host=config.server_host,
        port=config.server_port,
        reload=True,  # Enable reload for development
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
