"""Agent tools for content access.

Simple abstractions for agents to access book content:
- get_chapter_lessons: List lessons in a chapter
- load_lesson: Load specific lesson content

These tools enable agents to dynamically reference content when users
ask questions like "I read about X in another lesson..."
"""

import logging
from typing import Any

from agents import function_tool

from ..services.content_loader import load_lesson_content

logger = logging.getLogger(__name__)

# Book structure constants (can be loaded from config later)
GITHUB_REPO = "panaversity/agentfactory"
DOCS_BASE = "apps/learn-app/docs"


@function_tool
async def load_lesson(lesson_path: str) -> dict[str, Any]:
    """
    Load content from a specific lesson.

    Use this when you need to reference content from another lesson
    that the user mentions or that's relevant to the current topic.

    Args:
        lesson_path: Path to the lesson, e.g.:
            - "01-intro/02-concepts" (chapter/lesson)
            - "02-agents/05-skills.md" (with extension)
            - Full path also works

    Returns:
        Dict with 'title', 'content', and 'cached' fields.
        If not found, content will be empty string.

    Example:
        If user says "I read about skills in chapter 2",
        call load_lesson("02-agents/05-skills") to verify.
    """
    logger.info(f"[Tool] load_lesson called with: {lesson_path}")

    result = await load_lesson_content(lesson_path)

    # Return a simplified response for the agent
    return {
        "title": result.get("title", "Unknown"),
        "content": result.get("content", "")[:6000],  # Limit for context window
        "path": lesson_path,
        "found": bool(result.get("content")),
    }


@function_tool
async def get_chapter_lessons(chapter_number: int) -> dict[str, Any]:
    """
    Get list of lessons in a chapter.

    Use this when you need to help the user navigate to related content
    or understand what topics are covered in a chapter.

    Args:
        chapter_number: The chapter number (1, 2, 3, etc.)

    Returns:
        Dict with chapter info and lesson list.
        Note: This is a placeholder - actual implementation requires
        either GitHub API or pre-built index.

    Example:
        User asks "What else is in this chapter?"
        call get_chapter_lessons(2) to list lessons.
    """
    logger.info(f"[Tool] get_chapter_lessons called for chapter: {chapter_number}")

    # TODO: Implement actual chapter listing
    # Options:
    # 1. GitHub API to list directory contents
    # 2. Pre-built index in Redis
    # 3. Manifest file in the repo

    return {
        "chapter": chapter_number,
        "lessons": [],
        "note": "Chapter listing not yet implemented. Use load_lesson with specific path.",
    }


# Export tools for use in agent creation
CONTENT_TOOLS = [load_lesson, get_chapter_lessons]
