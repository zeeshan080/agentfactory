"""User Preferences API endpoints.

GET /api/preferences - Get current user's preferences.
POST /api/preferences - Create or update user preferences.
GET /api/preferences/status - Check if user has completed onboarding.

These preferences are used for content personalization.
"""

from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..auth import verify_bearer_token
from ..database import get_session, UserPreferences


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class PreferencesRequest(BaseModel):
    """Request body for creating/updating preferences."""

    gradeLevel: Literal["elementary", "middle-school", "high-school", "college"]
    interests: list[str]  # e.g., ["programming", "gaming"]


class PreferencesResponse(BaseModel):
    """Response body with user preferences."""

    userId: str
    gradeLevel: str
    interests: list[str]
    onboardedAt: str


class OnboardingStatusResponse(BaseModel):
    """Response body for onboarding status check."""

    hasOnboarded: bool
    preferences: PreferencesResponse | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    authorization: str | None = Header(default=None),
):
    """Get current user's preferences.

    Returns 404 if user hasn't completed onboarding yet.
    """
    auth_context = await verify_bearer_token(authorization)

    if auth_context is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = auth_context.user_id

    async with get_session() as session:
        result = await session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        prefs = result.scalar_one_or_none()

    if prefs is None:
        raise HTTPException(
            status_code=404,
            detail="User preferences not found. Please complete onboarding.",
        )

    return PreferencesResponse(
        userId=prefs.user_id,
        gradeLevel=prefs.grade_level,
        interests=prefs.interests,
        onboardedAt=prefs.onboarded_at.isoformat(),
    )


@router.post("/preferences", response_model=PreferencesResponse)
async def save_preferences(
    request: PreferencesRequest,
    authorization: str | None = Header(default=None),
):
    """Create or update user preferences.

    Called after onboarding form submission.
    If preferences exist, updates them. If not, creates new.
    """
    auth_context = await verify_bearer_token(authorization)

    if auth_context is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = auth_context.user_id

    # Normalize inputs
    grade_level = request.gradeLevel.lower()
    interests = [i.lower().strip() for i in request.interests if i.strip()]

    if not interests:
        raise HTTPException(
            status_code=400,
            detail="At least one interest is required.",
        )

    async with get_session() as session:
        # Check if preferences exist
        result = await session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing preferences
            existing.grade_level = grade_level
            existing.interests = interests
            prefs = existing
            print(f"Updated preferences for user {user_id}")
        else:
            # Create new preferences
            prefs = UserPreferences(
                user_id=user_id,
                grade_level=grade_level,
                interests=interests,
            )
            session.add(prefs)
            print(f"Created preferences for user {user_id}")

        # Commit happens on context exit, but we need to read back
        await session.flush()
        await session.refresh(prefs)

    return PreferencesResponse(
        userId=prefs.user_id,
        gradeLevel=prefs.grade_level,
        interests=prefs.interests,
        onboardedAt=prefs.onboarded_at.isoformat(),
    )


@router.get("/preferences/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    authorization: str | None = Header(default=None),
):
    """Check if user has completed onboarding.

    Returns:
    - hasOnboarded: true if user has preferences, false otherwise
    - preferences: User preferences if they exist, null otherwise

    Used by frontend to determine if user needs to go through onboarding.
    """
    auth_context = await verify_bearer_token(authorization)

    if auth_context is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = auth_context.user_id

    async with get_session() as session:
        result = await session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        prefs = result.scalar_one_or_none()

    if prefs is None:
        return OnboardingStatusResponse(hasOnboarded=False, preferences=None)

    return OnboardingStatusResponse(
        hasOnboarded=True,
        preferences=PreferencesResponse(
            userId=prefs.user_id,
            gradeLevel=prefs.grade_level,
            interests=prefs.interests,
            onboardedAt=prefs.onboarded_at.isoformat(),
        ),
    )
