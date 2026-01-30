"""Tests for authentication module.

Tests JWT/JWKS verification, opaque token fallback, and dev mode bypass.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from study_mode_api.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_optional,
    get_jwks,
    verify_jwt,
    verify_opaque_token,
)


class TestCurrentUser:
    """Test CurrentUser class."""

    def test_current_user_from_payload(self, sample_jwt_payload):
        """Test CurrentUser extraction from JWT payload."""
        user = CurrentUser(sample_jwt_payload)

        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.role == "user"
        assert user.tenant_id == "org-456"
        assert user.organization_ids == ["org-456", "org-789"]

    def test_current_user_tenant_fallback(self):
        """Test tenant_id fallback priority."""
        # Priority 1: tenant_id
        user1 = CurrentUser({"sub": "1", "tenant_id": "t1"})
        assert user1.tenant_id == "t1"

        # Priority 2: organization_id
        user2 = CurrentUser({"sub": "2", "organization_id": "o1"})
        assert user2.tenant_id == "o1"

        # Priority 3: first organization_ids
        user3 = CurrentUser({"sub": "3", "organization_ids": ["oid1", "oid2"]})
        assert user3.tenant_id == "oid1"

    def test_current_user_repr(self):
        """Test CurrentUser string representation."""
        user = CurrentUser({
            "sub": "user-123",
            "email": "test@example.com",
            "client_name": "Test Client",
        })

        repr_str = repr(user)
        assert "user-123" in repr_str
        assert "test@example.com" in repr_str
        assert "Test Client" in repr_str


class TestJWKS:
    """Test JWKS fetching and caching."""

    @pytest.mark.asyncio
    async def test_get_jwks_fetches_from_sso(self, sample_jwks):
        """Test JWKS is fetched from SSO."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_jwks
        mock_response.raise_for_status = MagicMock()

        with patch("study_mode_api.auth.settings") as mock_settings:
            mock_settings.sso_url = "https://sso.example.com"

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

                # Clear cache
                import study_mode_api.auth as auth_module
                auth_module._jwks_cache = None
                auth_module._jwks_cache_time = 0

                result = await get_jwks()

        assert result == sample_jwks
        assert len(result["keys"]) == 1

    @pytest.mark.asyncio
    async def test_get_jwks_uses_cache(self, sample_jwks):
        """Test JWKS cache is used within TTL."""
        import time

        import study_mode_api.auth as auth_module

        # Set cache
        auth_module._jwks_cache = sample_jwks
        auth_module._jwks_cache_time = time.time()

        with patch("httpx.AsyncClient") as mock_client:
            result = await get_jwks()

            # Should not make HTTP request
            mock_client.assert_not_called()

        assert result == sample_jwks

    @pytest.mark.asyncio
    async def test_get_jwks_raises_when_sso_not_configured(self):
        """Test error when SSO URL not configured."""
        import study_mode_api.auth as auth_module

        auth_module._jwks_cache = None
        auth_module._jwks_cache_time = 0

        with patch("study_mode_api.auth.settings") as mock_settings:
            mock_settings.sso_url = ""

            with pytest.raises(HTTPException) as exc_info:
                await get_jwks()

        assert exc_info.value.status_code == 503


class TestVerifyJWT:
    """Test JWT verification."""

    @pytest.mark.asyncio
    async def test_verify_jwt_success(self, sample_jwt_payload, sample_jwks):
        """Test successful JWT verification."""
        with patch("study_mode_api.auth.get_jwks", return_value=sample_jwks):
            with patch("study_mode_api.auth.jwt.get_unverified_header") as mock_header:
                mock_header.return_value = {"kid": "test-key-1", "alg": "RS256"}

                with patch("study_mode_api.auth.jwt.decode") as mock_decode:
                    mock_decode.return_value = sample_jwt_payload

                    result = await verify_jwt("test.jwt.token")

        assert result["sub"] == "user-123"
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_verify_jwt_key_not_found(self, sample_jwks):
        """Test error when signing key not in JWKS."""
        with patch("study_mode_api.auth.get_jwks", return_value=sample_jwks):
            with patch("study_mode_api.auth.jwt.get_unverified_header") as mock_header:
                mock_header.return_value = {"kid": "unknown-key", "alg": "RS256"}

                with pytest.raises(HTTPException) as exc_info:
                    await verify_jwt("test.jwt.token")

        assert exc_info.value.status_code == 401
        assert "not found" in str(exc_info.value.detail)


class TestVerifyOpaqueToken:
    """Test opaque token verification."""

    @pytest.mark.asyncio
    async def test_verify_opaque_token_success(self, sample_jwt_payload):
        """Test successful opaque token verification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_jwt_payload

        with patch("study_mode_api.auth.settings") as mock_settings:
            mock_settings.sso_url = "https://sso.example.com"

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await verify_opaque_token("opaque-token-123")

        assert result["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_verify_opaque_token_invalid(self):
        """Test error for invalid opaque token."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("study_mode_api.auth.settings") as mock_settings:
            mock_settings.sso_url = "https://sso.example.com"

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

                with pytest.raises(HTTPException) as exc_info:
                    await verify_opaque_token("invalid-token")

        assert exc_info.value.status_code == 401


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_dev_mode_bypass(self):
        """Test dev mode bypasses authentication (T028)."""
        with patch("study_mode_api.auth.settings") as mock_settings:
            mock_settings.dev_mode = True
            mock_settings.dev_user_id = "dev-123"
            mock_settings.dev_user_email = "dev@test.com"
            mock_settings.dev_user_name = "Dev User"

            mock_request = MagicMock()
            user = await get_current_user(mock_request, None)

        assert user.id == "dev-123"
        assert user.email == "dev@test.com"

    @pytest.mark.asyncio
    async def test_requires_auth_in_production(self):
        """Test authentication required when not in dev mode."""
        with patch("study_mode_api.auth.settings") as mock_settings:
            mock_settings.dev_mode = False

            mock_request = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_optional_auth_returns_none(self):
        """Test optional auth returns None without credentials."""
        with patch("study_mode_api.auth.settings") as mock_settings:
            mock_settings.dev_mode = False

            mock_request = MagicMock()
            result = await get_current_user_optional(mock_request, None)

        assert result is None
