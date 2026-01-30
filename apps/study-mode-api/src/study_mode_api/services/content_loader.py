"""
Lesson content loading with GitHub fetch and Redis caching.

Features:
- Fetches content from GitHub raw URLs with authentication
- Redis caching with 30-day TTL (invalidated on git push via GitHub Action)
- Graceful degradation if Redis unavailable
- Support for .md and .mdx files

Cache invalidation:
- On git push to main, GitHub Action calls /admin/invalidate-cache endpoint
- Invalidates only changed lesson paths
"""

import logging

import httpx

from ..config import settings
from ..core.redis_cache import cache_response, safe_redis_get

logger = logging.getLogger(__name__)

# Cache TTL: 30 days (invalidated via GitHub Action on push)
CONTENT_CACHE_TTL = settings.content_cache_ttl


def extract_title(content: str, fallback: str) -> str:
    """Extract title from markdown content."""
    for line in content.split("\n"):
        if line.startswith("title:"):
            return line.replace("title:", "").strip().strip('"').strip("'")
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.split("/")[-1].replace("-", " ").title()


async def fetch_from_github(lesson_path: str) -> tuple[str, bool]:
    """
    Fetch lesson content from GitHub with authenticated requests.

    GitHub API allows 5,000 requests/hour with token (60 without).

    Args:
        lesson_path: Path to the lesson (e.g., "01-intro/01-welcome.md")

    Returns:
        Tuple of (content, success)
    """
    if not lesson_path:
        return "", False

    # Clean the path
    clean_path = lesson_path.strip("/")
    if clean_path.startswith("docs/"):
        clean_path = f"apps/learn-app/{clean_path}"
    elif not clean_path.startswith("apps/"):
        clean_path = f"apps/learn-app/docs/{clean_path}"

    # Try both .md and .mdx extensions
    extensions = [""]
    if not clean_path.endswith((".md", ".mdx")):
        extensions = [".md", ".mdx", "/index.md", "/README.md"]

    for ext in extensions:
        url = f"https://raw.githubusercontent.com/{settings.github_repo}/main/{clean_path}{ext}"

        try:
            async with httpx.AsyncClient() as client:
                headers = {}
                if settings.github_token:
                    headers["Authorization"] = f"token {settings.github_token}"

                response = await client.get(url, headers=headers, timeout=10.0)

                if response.status_code == 200:
                    logger.debug(f"Fetched content from GitHub: {url}")
                    return response.text, True

        except Exception as e:
            logger.warning(f"Failed to fetch from GitHub {url}: {e}")
            continue

    return "", False


@cache_response(ttl=CONTENT_CACHE_TTL)
async def load_lesson_content(lesson_path: str) -> dict:
    """
    Load lesson content with Redis caching.

    Cache key is based on lesson_path. Cache TTL is 30 days.
    Second request for same lesson should be <50ms (cache hit).

    Args:
        lesson_path: Path to the lesson (e.g., "01-foundations/01-intro")

    Returns:
        Dict with 'content', 'title', and 'cached' fields
    """
    if not lesson_path:
        return {
            "content": "",
            "title": "Unknown Page",
            "cached": False,
        }

    # Try to get from cache first (handled by decorator)
    # If not cached, fetch from GitHub
    content, success = await fetch_from_github(lesson_path)

    if success:
        title = extract_title(content, lesson_path)
        return {
            "content": content,
            "title": title,
            "cached": False,  # Will be True on subsequent cached requests
        }

    return {
        "content": "",
        "title": f"Page: {lesson_path}",
        "cached": False,
    }


async def get_cached_content(lesson_path: str) -> dict | None:
    """
    Get cached content without fetching from GitHub.

    Useful for checking cache status without triggering a fetch.
    """
    cache_key = f"content_loader.load_lesson_content:{lesson_path}:"
    cached_data = await safe_redis_get(cache_key)

    if cached_data:
        import json

        try:
            result = json.loads(cached_data)
            result["cached"] = True
            return result
        except Exception:
            pass

    return None


def search_book_content(query: str) -> str:
    """
    Search book content.

    Note: In Docker deployment, this searches cached content only.
    For full search, consider implementing GitHub Search API integration.
    """
    # This is a simplified version for Docker deployment
    # Full search would require GitHub Search API or local index
    logger.warning("search_book_content called but full search not available in container mode")
    return f"Search not available in container mode. Query: {query}"
