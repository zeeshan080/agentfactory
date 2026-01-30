"""Async database connection management for AgentFactory API.

Design for cloud databases (Neon, Supabase, PlanetScale):
- Uses NullPool to avoid keeping connections open
- Each request gets a fresh connection from the cloud pooler
- Connections are released immediately after use
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import String, Text, Integer, DateTime, Index, ARRAY
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from .config import get_config


# =============================================================================
# SQLAlchemy Models
# =============================================================================


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class PersonalizedArtifact(Base):
    """Global library of personalized lesson content.

    This table stores pointers to R2 content, NOT user data.
    Content is deduplicated by (lesson_id, grade_level, interest_tag, media_type).

    Key insight: No user_id here - this is a SHARED GLOBAL LIBRARY.
    If User A generates "Newton's Laws (Grade 6, Soccer)", User B with
    same profile gets it instantly at zero cost.
    """

    __tablename__ = "personalized_artifacts"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Search keys - the "Who" and "What"
    lesson_id: Mapped[str] = mapped_column(String(100), nullable=False)
    grade_level: Mapped[str] = mapped_column(String(20), nullable=False)
    interest_tag: Mapped[str] = mapped_column(String(50), nullable=False)

    # The pointer - the "Where"
    r2_storage_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    media_type: Mapped[str] = mapped_column(String(20), default="text")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Unique constraint and index for fast lookups
    __table_args__ = (
        Index(
            "idx_artifact_lookup",
            "lesson_id",
            "grade_level",
            "interest_tag",
            "media_type",
            unique=True,
        ),
    )


class UserPreferences(Base):
    """User personalization preferences collected during onboarding.

    Stores each user's grade level and interests for content personalization.
    This table is PER-USER (unlike PersonalizedArtifact which is global).

    Workflow:
    1. User logs in for first time
    2. System checks if user_id exists in this table
    3. If not → redirect to onboarding page
    4. After onboarding → create row with their preferences
    5. On personalization requests → use these preferences
    """

    __tablename__ = "user_preferences"

    # Primary key is the user_id from SSO token
    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Grade level: elementary, middle-school, high-school, college
    grade_level: Mapped[str] = mapped_column(String(20), nullable=False)

    # Interests as PostgreSQL array (e.g., ["programming", "gaming"])
    interests: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, default=list
    )

    # Timestamps
    onboarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# =============================================================================
# Database Connection
# =============================================================================


def _create_engine() -> AsyncEngine:
    """Create a new async engine configured for cloud databases.

    Uses NullPool so connections are not held open between requests.
    Cloud database providers (Neon, Supabase) handle connection pooling.

    Returns:
        AsyncEngine: SQLAlchemy async engine with NullPool.
    """
    config = get_config()
    return create_async_engine(
        config.effective_database_url,
        echo=config.log_level == "DEBUG",
        poolclass=NullPool,  # No local pooling - cloud handles it
    )


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session with automatic cleanup.

    Creates a fresh connection for each request and disposes it after.
    This pattern is ideal for:
    - Serverless environments (no persistent connections)
    - Cloud databases with external pooling (Neon, Supabase)
    - Stateless HTTP servers

    Yields:
        AsyncSession: Database session that commits on success, rolls back on error.

    Example:
        async with get_session() as session:
            result = await session.execute(select(PersonalizedArtifact))
            # Auto-commits on exit, rolls back on exception
            # Connection is released immediately after
    """
    engine = _create_engine()
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        # Dispose engine to release connection back to cloud pooler
        pool_class = type(engine.pool).__name__
        if pool_class == "AsyncAdaptedNullPool":
            await engine.dispose()


async def init_db() -> None:
    """Initialize database tables (for development/testing).

    Creates all tables defined in models if they don't exist.
    For production, use Alembic migrations instead.
    """
    engine = _create_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()
