"""Tests for content loader service.

Success Criteria SC-002: Cached content should be retrieved in <50ms.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from study_mode_api.services.content_loader import (
    extract_title,
    fetch_from_github,
    get_cached_content,
    load_lesson_content,
)


class TestExtractTitle:
    """Test title extraction from markdown."""

    def test_extract_title_from_frontmatter(self):
        """Test extracting title from YAML frontmatter."""
        content = '''---
title: "My Lesson Title"
description: "A description"
---

# Heading

Content here.
'''
        title = extract_title(content, "fallback")

        assert title == "My Lesson Title"

    def test_extract_title_from_heading(self):
        """Test extracting title from H1 heading."""
        content = '''# Introduction to Agents

This is the introduction.
'''
        title = extract_title(content, "fallback")

        assert title == "Introduction to Agents"

    def test_extract_title_fallback(self):
        """Test fallback title when no title found."""
        content = "Just some content without a title."

        title = extract_title(content, "path/to/lesson-name")

        assert title == "Lesson Name"

    def test_extract_title_strips_quotes(self):
        """Test title strips surrounding quotes."""
        content = "title: 'Single Quoted Title'"

        title = extract_title(content, "fallback")

        assert title == "Single Quoted Title"


class TestFetchFromGitHub:
    """Test GitHub content fetching."""

    @pytest.mark.asyncio
    async def test_fetch_from_github_success(self):
        """Test successful content fetch from GitHub."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Test Content\n\nHello world."

        with patch("study_mode_api.services.content_loader.settings") as mock_settings:
            mock_settings.github_repo = "test/repo"
            mock_settings.github_token = "test-token"

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

                content, success = await fetch_from_github("docs/01-intro/01-welcome")

        assert success is True
        assert "# Test Content" in content

    @pytest.mark.asyncio
    async def test_fetch_from_github_not_found(self):
        """Test handling of 404 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("study_mode_api.services.content_loader.settings") as mock_settings:
            mock_settings.github_repo = "test/repo"
            mock_settings.github_token = ""

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

                content, success = await fetch_from_github("nonexistent/path")

        assert success is False
        assert content == ""

    @pytest.mark.asyncio
    async def test_fetch_from_github_empty_path(self):
        """Test handling of empty path."""
        content, success = await fetch_from_github("")

        assert success is False
        assert content == ""

    @pytest.mark.asyncio
    async def test_fetch_from_github_uses_auth_header(self):
        """Test GitHub token is sent in Authorization header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "content"

        with patch("study_mode_api.services.content_loader.settings") as mock_settings:
            mock_settings.github_repo = "test/repo"
            mock_settings.github_token = "ghp_secrettoken123"

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

                await fetch_from_github("docs/test")

                # Verify Authorization header was sent
                call_args = mock_client_instance.get.call_args
                headers = call_args.kwargs.get("headers", {})
                assert headers.get("Authorization") == "token ghp_secrettoken123"


class TestLoadLessonContent:
    """Test load_lesson_content with caching."""

    @pytest.mark.asyncio
    async def test_load_lesson_content_success(self):
        """Test loading lesson content."""
        mock_content = "# Test Lesson\n\nContent here."

        with patch(
            "study_mode_api.services.content_loader.fetch_from_github",
            return_value=(mock_content, True),
        ):
            # Disable caching for this test by patching the redis_cache module
            with patch("study_mode_api.core.redis_cache._aredis", None):
                result = await load_lesson_content("docs/test-lesson")

        assert result["content"] == mock_content
        assert result["title"] == "Test Lesson"

    @pytest.mark.asyncio
    async def test_load_lesson_content_empty_path(self):
        """Test loading with empty path returns default."""
        with patch("study_mode_api.core.redis_cache._aredis", None):
            result = await load_lesson_content("")

        assert result["content"] == ""
        assert result["title"] == "Unknown Page"

    @pytest.mark.asyncio
    async def test_load_lesson_content_not_found(self):
        """Test handling of content not found."""
        with patch(
            "study_mode_api.services.content_loader.fetch_from_github",
            return_value=("", False),
        ):
            with patch("study_mode_api.core.redis_cache._aredis", None):
                result = await load_lesson_content("nonexistent/path")

        assert result["content"] == ""
        assert "nonexistent/path" in result["title"]

    @pytest.mark.asyncio
    async def test_load_lesson_content_cached_fast(self):
        """Test cached content retrieval is fast (SC-002: <50ms)."""
        import json
        import time

        cached_data = json.dumps({
            "content": "# Cached Content",
            "title": "Cached Title",
            "cached": True,
        })

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)

        with patch("study_mode_api.core.redis_cache._aredis", mock_redis):
            start = time.time()
            result = await load_lesson_content("docs/cached-lesson")
            elapsed_ms = (time.time() - start) * 1000

        # SC-002: Cached requests should be <50ms
        assert elapsed_ms < 50
        assert result["content"] == "# Cached Content"


class TestGetCachedContent:
    """Test direct cache access."""

    @pytest.mark.asyncio
    async def test_get_cached_content_hit(self):
        """Test retrieving cached content directly."""
        import json

        cached_data = json.dumps({
            "content": "# Cached",
            "title": "Cached Title",
        })

        with patch(
            "study_mode_api.services.content_loader.safe_redis_get",
            return_value=cached_data,
        ):
            result = await get_cached_content("docs/test")

        assert result is not None
        assert result["cached"] is True

    @pytest.mark.asyncio
    async def test_get_cached_content_miss(self):
        """Test cache miss returns None."""
        with patch(
            "study_mode_api.services.content_loader.safe_redis_get",
            return_value=None,
        ):
            result = await get_cached_content("docs/test")

        assert result is None
