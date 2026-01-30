"""OpenAI Agents SDK integration for lesson personalization.

Uses the OpenAI Agents SDK to generate personalized lesson content
based on grade level and interests. Supports streaming for better UX.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator

from openai import OpenAI

from .config import get_config


@dataclass
class PersonalizationResult:
    """Result from the personalization agent."""

    selected_interest: str
    analogy_logic: str
    personalized_content: str
    generated_at: str
    model: str
    source_content_hash: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "selected_interest": self.selected_interest,
            "analogy_logic": self.analogy_logic,
            "personalized_content": self.personalized_content,
            "generated_at": self.generated_at,
            "model": self.model,
            "source_content_hash": self.source_content_hash,
        }


@dataclass
class StreamingPersonalizationResult:
    """Partial result during streaming."""

    selected_interest: str
    content_chunk: str
    is_complete: bool = False
    analogy_logic: str = ""
    generated_at: str = ""
    model: str = ""


# Grade level descriptions for the prompt
GRADE_DESCRIPTIONS = {
    "elementary": "elementary school students (ages 6-10), using simple language, everyday examples, and concrete concepts",
    "middle-school": "middle school students (ages 11-13), using relatable examples, some technical vocabulary with explanations, and hands-on activities",
    "high-school": "high school students (ages 14-18), using more technical language, real-world applications, and project-based thinking",
    "college": "college students and adult learners, using professional terminology, industry examples, and career-relevant applications",
}


async def generate_personalized_content(
    grade_level: str,
    interest_tag: str,
    source_content: str,
    source_hash: str | None = None,
) -> PersonalizationResult | None:
    """Generate personalized lesson content using OpenAI.

    Args:
        grade_level: Target grade level (elementary, middle-school, high-school, college)
        interest_tag: Interest to incorporate (e.g., "soccer", "minecraft", "programming")
        source_content: Original lesson markdown content
        source_hash: Optional hash of source content for tracking

    Returns:
        PersonalizationResult if successful, None if generation fails.
    """
    config = get_config()

    if not config.openai_enabled:
        # Return mock result for development without OpenAI
        return PersonalizationResult(
            selected_interest=interest_tag.title(),
            analogy_logic=f"[Mock] Connecting lesson concepts to {interest_tag}...",
            personalized_content=f"# Personalized for {interest_tag}\n\n{source_content[:500]}...\n\n*[This is mock content - configure OPENAI_API_KEY for real generation]*",
            generated_at=datetime.now(timezone.utc).isoformat(),
            model="mock",
            source_content_hash=source_hash,
        )

    try:
        client = OpenAI(api_key=config.openai_api_key)

        grade_desc = GRADE_DESCRIPTIONS.get(
            grade_level,
            GRADE_DESCRIPTIONS["college"],
        )

        system_prompt = f"""You are an expert educational content adapter. Your task is to personalize lesson content for a specific audience while maintaining educational value.

Target Audience: {grade_desc}
Interest to incorporate: {interest_tag}

Guidelines:
1. Adapt the reading level and vocabulary for the target grade level
2. Replace generic examples with {interest_tag}-related analogies where appropriate
3. Maintain ALL the original educational content and learning objectives
4. Keep code examples (if any) intact but adjust explanations
5. Add relatable scenarios using {interest_tag} as context
6. Preserve the original structure (headings, sections, code blocks)

Output Format:
First, provide a brief explanation of your adaptation strategy (2-3 sentences).
Then, provide the full personalized lesson content in markdown format.

Use this separator between strategy and content:
---CONTENT_START---"""

        user_prompt = f"""Please personalize this lesson content:

{source_content}"""

        response = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
        )

        full_response = response.choices[0].message.content or ""

        # Parse the response
        if "---CONTENT_START---" in full_response:
            parts = full_response.split("---CONTENT_START---", 1)
            analogy_logic = parts[0].strip()
            personalized_content = parts[1].strip() if len(parts) > 1 else full_response
        else:
            # Fallback if separator not found
            analogy_logic = f"Adapted for {interest_tag} at {grade_level} level."
            personalized_content = full_response

        return PersonalizationResult(
            selected_interest=interest_tag.title(),
            analogy_logic=analogy_logic,
            personalized_content=personalized_content,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=config.openai_model,
            source_content_hash=source_hash,
        )

    except Exception as e:
        print(f"OpenAI generation error: {e}")
        return None


async def generate_personalized_content_stream(
    grade_level: str,
    interest_tag: str,
    source_content: str,
    source_hash: str | None = None,
) -> AsyncGenerator[StreamingPersonalizationResult, None]:
    """Generate personalized lesson content with streaming.

    Yields chunks as they arrive from OpenAI for real-time display.

    Args:
        grade_level: Target grade level
        interest_tag: Interest to incorporate
        source_content: Original lesson markdown content
        source_hash: Optional hash of source content

    Yields:
        StreamingPersonalizationResult with content chunks.
    """
    config = get_config()

    if not config.openai_enabled:
        # Mock streaming for development
        mock_content = f"# Personalized for {interest_tag}\n\n{source_content[:500]}...\n\n*[Mock content - configure OPENAI_API_KEY]*"
        for i in range(0, len(mock_content), 50):
            chunk = mock_content[i : i + 50]
            yield StreamingPersonalizationResult(
                selected_interest=interest_tag.title(),
                content_chunk=chunk,
                is_complete=False,
            )
            import asyncio

            await asyncio.sleep(0.05)  # Simulate streaming delay

        yield StreamingPersonalizationResult(
            selected_interest=interest_tag.title(),
            content_chunk="",
            is_complete=True,
            analogy_logic=f"[Mock] Adapted for {interest_tag}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            model="mock",
        )
        return

    try:
        client = OpenAI(api_key=config.openai_api_key)

        grade_desc = GRADE_DESCRIPTIONS.get(
            grade_level,
            GRADE_DESCRIPTIONS["college"],
        )

        system_prompt = f"""You are an expert educational content adapter. Your task is to personalize lesson content for a specific audience while maintaining educational value.

Target Audience: {grade_desc}
Interest to incorporate: {interest_tag}

Guidelines:
1. Adapt the reading level and vocabulary for the target grade level
2. Replace generic examples with {interest_tag}-related analogies where appropriate
3. Maintain ALL the original educational content and learning objectives
4. Keep code examples (if any) intact but adjust explanations
5. Add relatable scenarios using {interest_tag} as context
6. Preserve the original structure (headings, sections, code blocks)

IMPORTANT: Start your response DIRECTLY with the personalized content in markdown format. Do not include any preamble or explanation - just output the adapted lesson content."""

        user_prompt = f"""Personalize this lesson:\n\n{source_content}"""

        # Use streaming
        stream = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4000,
            stream=True,
        )

        full_content = ""

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                full_content += content_chunk

                yield StreamingPersonalizationResult(
                    selected_interest=interest_tag.title(),
                    content_chunk=content_chunk,
                    is_complete=False,
                )

        # Final chunk with metadata
        yield StreamingPersonalizationResult(
            selected_interest=interest_tag.title(),
            content_chunk="",
            is_complete=True,
            analogy_logic=f"Adapted for {interest_tag} at {grade_level} level using relevant examples and analogies.",
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=config.openai_model,
        )

    except Exception as e:
        print(f"OpenAI streaming error: {e}")
        yield StreamingPersonalizationResult(
            selected_interest=interest_tag.title(),
            content_chunk=f"Error: {str(e)}",
            is_complete=True,
            analogy_logic="",
            generated_at=datetime.now(timezone.utc).isoformat(),
            model="error",
        )


async def health_check() -> dict:
    """Check OpenAI API health.

    Returns:
        Health status dict with status and optional error.
    """
    config = get_config()

    if not config.openai_enabled:
        return {
            "status": "disabled",
            "backend": "openai",
            "message": "OpenAI not configured (development mode)",
        }

    try:
        client = OpenAI(api_key=config.openai_api_key)

        # Simple models list call to verify API key works
        client.models.list()

        return {
            "status": "healthy",
            "backend": "openai",
            "model": config.openai_model,
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "backend": "openai",
            "error": str(e),
        }
