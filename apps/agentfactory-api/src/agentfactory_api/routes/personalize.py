"""Personalization API endpoints.

POST /api/personalize - Generate or retrieve personalized lesson content.
POST /api/personalize/stream - Stream personalized content in real-time.

Implements the "Generate Once, Read Many" pattern:
1. Check if ANYONE has generated this exact combo before (DB lookup)
2. If yes → Return R2 content (Cost: $0)
3. If no → Generate, Upload to R2, Save pointer to DB (Cost: $$)
"""

import asyncio
import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from ..auth import verify_bearer_token, AuthContext
from ..config import get_config
from ..database import get_session, PersonalizedArtifact
from ..storage import get_storage_key, upload_content, download_content
from ..agent import generate_personalized_content, generate_personalized_content_stream


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class PersonalizeRequest(BaseModel):
    """Request body for personalization endpoint."""

    lessonId: str  # e.g., "01-foundations/01-intro"
    lessonContent: str  # Original markdown content
    gradeLevel: Literal["elementary", "middle-school", "high-school", "college"]
    interestTag: str  # e.g., "programming", "soccer", "minecraft"


class PersonalizeResponse(BaseModel):
    """Response body for personalization endpoint."""

    selectedInterest: str
    analogyLogic: str
    personalizedContent: str
    cached: bool
    generatedAt: str


# =============================================================================
# Endpoint
# =============================================================================


@router.post("/personalize", response_model=PersonalizeResponse)
async def personalize_lesson(
    request: PersonalizeRequest,
    authorization: str | None = Header(default=None),
):
    """Generate or retrieve personalized lesson content.

    The deduplication magic:
    - Check if ANYONE has generated this exact combo before
    - If yes → Return R2 link (Cost: $0)
    - If no → Generate, Upload, Save pointer (Cost: $$)

    No user_id in the artifact table - it's a SHARED GLOBAL LIBRARY.
    """
    # Verify authentication
    auth_context = await verify_bearer_token(authorization)

    if auth_context is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log the request (for analytics, not storage key)
    user_id = auth_context.user_id
    print(
        f"Personalization request: user={user_id}, "
        f"lesson={request.lessonId}, grade={request.gradeLevel}, "
        f"interest={request.interestTag}"
    )

    # Normalize inputs
    lesson_id = request.lessonId.strip()
    grade_level = request.gradeLevel.lower()
    interest_tag = request.interestTag.lower().strip()
    media_type = "text"

    # STEP 1: Fast Lookup (Global Cache Check)
    # Check if ANYONE has generated this exact combination before
    async with get_session() as session:
        result = await session.execute(
            select(PersonalizedArtifact).where(
                PersonalizedArtifact.lesson_id == lesson_id,
                PersonalizedArtifact.grade_level == grade_level,
                PersonalizedArtifact.interest_tag == interest_tag,
                PersonalizedArtifact.media_type == media_type,
            )
        )
        artifact = result.scalar_one_or_none()

    # CASE A: HIT (Exists in library!)
    if artifact:
        print(f"Cache HIT: {artifact.r2_storage_key}")

        # Try to fetch from R2
        content = await download_content(artifact.r2_storage_key)

        if content:
            return PersonalizeResponse(
                selectedInterest=content.get("selected_interest", interest_tag.title()),
                analogyLogic=content.get("analogy_logic", ""),
                personalizedContent=content.get("personalized_content", ""),
                cached=True,
                generatedAt=content.get("generated_at", artifact.created_at.isoformat()),
            )

        # R2 content missing (shouldn't happen) - fall through to regenerate
        print(f"Warning: R2 content missing for {artifact.r2_storage_key}")

    # CASE B: MISS (First time ever - generate)
    print(f"Cache MISS: Generating for {lesson_id}/{grade_level}/{interest_tag}")

    # Compute source content hash for tracking
    source_hash = hashlib.sha256(request.lessonContent.encode()).hexdigest()[:16]

    # 1. Generate via OpenAI
    result = await generate_personalized_content(
        grade_level=grade_level,
        interest_tag=interest_tag,
        source_content=request.lessonContent,
        source_hash=source_hash,
    )

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Content generation failed. Please try again later.",
        )

    # 2. Upload to R2
    storage_key = get_storage_key(lesson_id, grade_level, interest_tag, media_type)

    upload_success = await upload_content(storage_key, result.to_dict())

    if not upload_success:
        # Log but don't fail - content was generated, just not cached
        print(f"Warning: Failed to upload to R2: {storage_key}")

    # 3. Save pointer to DB
    try:
        async with get_session() as session:
            # Check again in case of race condition
            existing = await session.execute(
                select(PersonalizedArtifact).where(
                    PersonalizedArtifact.lesson_id == lesson_id,
                    PersonalizedArtifact.grade_level == grade_level,
                    PersonalizedArtifact.interest_tag == interest_tag,
                    PersonalizedArtifact.media_type == media_type,
                )
            )

            if existing.scalar_one_or_none() is None:
                artifact = PersonalizedArtifact(
                    lesson_id=lesson_id,
                    grade_level=grade_level,
                    interest_tag=interest_tag,
                    r2_storage_key=storage_key,
                    media_type=media_type,
                )
                session.add(artifact)
                # Commit happens automatically on context exit

    except Exception as e:
        # Log but don't fail - content was generated
        print(f"Warning: Failed to save artifact pointer: {e}")

    return PersonalizeResponse(
        selectedInterest=result.selected_interest,
        analogyLogic=result.analogy_logic,
        personalizedContent=result.personalized_content,
        cached=False,
        generatedAt=result.generated_at,
    )


# =============================================================================
# Streaming Endpoint
# =============================================================================


@router.post("/personalize/stream")
async def personalize_lesson_stream(
    request: PersonalizeRequest,
    authorization: str | None = Header(default=None),
):
    """Stream personalized lesson content in real-time.

    Uses Server-Sent Events (SSE) to stream content as it's generated.
    After streaming completes, saves to R2 and DB in the background.

    Event types:
    - chunk: Content chunk (data: {"content": "..."})
    - cached: Full cached content (data: {"cached": true, ...})
    - complete: Generation complete with metadata
    - error: Error occurred
    """
    # Verify authentication
    auth_context = await verify_bearer_token(authorization)

    if auth_context is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = auth_context.user_id
    print(
        f"Streaming personalization: user={user_id}, "
        f"lesson={request.lessonId}, grade={request.gradeLevel}, "
        f"interest={request.interestTag}"
    )

    # Normalize inputs
    lesson_id = request.lessonId.strip()
    grade_level = request.gradeLevel.lower()
    interest_tag = request.interestTag.lower().strip()
    media_type = "text"

    async def event_generator():
        """Generate SSE events."""
        # STEP 1: Check cache first
        async with get_session() as session:
            result = await session.execute(
                select(PersonalizedArtifact).where(
                    PersonalizedArtifact.lesson_id == lesson_id,
                    PersonalizedArtifact.grade_level == grade_level,
                    PersonalizedArtifact.interest_tag == interest_tag,
                    PersonalizedArtifact.media_type == media_type,
                )
            )
            artifact = result.scalar_one_or_none()

        # CASE A: Cache HIT - stream cached content
        if artifact:
            print(f"Stream cache HIT: {artifact.r2_storage_key}")
            content = await download_content(artifact.r2_storage_key)

            if content:
                # Send cached content as a single event
                cached_data = {
                    "type": "cached",
                    "selectedInterest": content.get("selected_interest", interest_tag.title()),
                    "analogyLogic": content.get("analogy_logic", ""),
                    "personalizedContent": content.get("personalized_content", ""),
                    "cached": True,
                    "generatedAt": content.get("generated_at", ""),
                }
                yield f"data: {json.dumps(cached_data)}\n\n"
                return

        # CASE B: Cache MISS - stream from OpenAI
        print(f"Stream cache MISS: Generating for {lesson_id}/{grade_level}/{interest_tag}")

        full_content = ""
        final_metadata = None

        try:
            async for chunk in generate_personalized_content_stream(
                grade_level=grade_level,
                interest_tag=interest_tag,
                source_content=request.lessonContent,
            ):
                if not chunk.is_complete:
                    # Stream content chunk
                    full_content += chunk.content_chunk
                    chunk_data = {
                        "type": "chunk",
                        "content": chunk.content_chunk,
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                else:
                    # Final chunk with metadata
                    final_metadata = {
                        "selectedInterest": chunk.selected_interest,
                        "analogyLogic": chunk.analogy_logic,
                        "generatedAt": chunk.generated_at,
                        "model": chunk.model,
                    }

            # Send completion event
            complete_data = {
                "type": "complete",
                "cached": False,
                **final_metadata,
            }
            yield f"data: {json.dumps(complete_data)}\n\n"

            # Background save to R2 and DB (don't block the response)
            asyncio.create_task(
                _save_generated_content(
                    lesson_id=lesson_id,
                    grade_level=grade_level,
                    interest_tag=interest_tag,
                    media_type=media_type,
                    full_content=full_content,
                    metadata=final_metadata,
                )
            )

        except Exception as e:
            print(f"Streaming error: {e}")
            error_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def _save_generated_content(
    lesson_id: str,
    grade_level: str,
    interest_tag: str,
    media_type: str,
    full_content: str,
    metadata: dict,
):
    """Save generated content to R2 and DB (background task)."""
    try:
        storage_key = get_storage_key(lesson_id, grade_level, interest_tag, media_type)

        # Prepare content for storage
        content_data = {
            "selected_interest": metadata.get("selectedInterest", interest_tag.title()),
            "analogy_logic": metadata.get("analogyLogic", ""),
            "personalized_content": full_content,
            "generated_at": metadata.get("generatedAt", ""),
            "model": metadata.get("model", ""),
        }

        # Upload to R2
        upload_success = await upload_content(storage_key, content_data)

        if not upload_success:
            print(f"Warning: Failed to upload to R2: {storage_key}")
            return

        # Save pointer to DB
        async with get_session() as session:
            # Check for existing (race condition)
            existing = await session.execute(
                select(PersonalizedArtifact).where(
                    PersonalizedArtifact.lesson_id == lesson_id,
                    PersonalizedArtifact.grade_level == grade_level,
                    PersonalizedArtifact.interest_tag == interest_tag,
                    PersonalizedArtifact.media_type == media_type,
                )
            )

            if existing.scalar_one_or_none() is None:
                artifact = PersonalizedArtifact(
                    lesson_id=lesson_id,
                    grade_level=grade_level,
                    interest_tag=interest_tag,
                    r2_storage_key=storage_key,
                    media_type=media_type,
                )
                session.add(artifact)

        print(f"Saved to R2 and DB: {storage_key}")

    except Exception as e:
        print(f"Background save error: {e}")
