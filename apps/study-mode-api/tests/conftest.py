"""Shared test fixtures for Study Mode API tests."""

import asyncio
import os
from unittest.mock import AsyncMock

import pytest

# Set test environment variables before importing app modules
os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = ""
os.environ["REDIS_URL"] = ""
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,http://test.com"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.evalsha = AsyncMock(return_value=[1, 60000, 0])
    mock.script_load = AsyncMock(return_value="mock_sha")
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for external API calls."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def sample_lesson_content():
    """Sample lesson content for testing."""
    return {
        "content": """---
title: "Test Lesson"
description: "A test lesson for unit testing"
---

# Test Lesson

This is test content for the lesson.

## Key Concepts

- Concept 1
- Concept 2
""",
        "title": "Test Lesson",
    }


@pytest.fixture
def sample_jwt_payload():
    """Sample JWT payload for auth testing."""
    return {
        "sub": "user-123",
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
        "tenant_id": "org-456",
        "organization_ids": ["org-456", "org-789"],
    }


@pytest.fixture
def sample_jwks():
    """Sample JWKS response for auth testing."""
    return {
        "keys": [
            {
                "kid": "test-key-1",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "test-modulus",
                "e": "AQAB",
            }
        ]
    }
