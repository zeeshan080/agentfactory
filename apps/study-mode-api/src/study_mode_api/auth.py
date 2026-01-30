"""JWT/JWKS authentication against SSO.

Supports two token types:
1. JWT (id_token) - Verified locally using JWKS public keys
2. Opaque (access_token) - Verified via SSO userinfo endpoint

Dev mode bypass available for local development.
"""

import logging
import time
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)  # Don't auto-error, we handle it

# JWKS cache - fetched once, reused for 1 hour
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_time: float = 0
JWKS_CACHE_TTL = 3600  # 1 hour


async def get_jwks() -> dict[str, Any]:
    """Fetch and cache JWKS public keys from SSO.

    Called once per hour, not per request.
    Keys are used to verify JWT signatures locally.
    """
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time) < JWKS_CACHE_TTL:
        logger.debug("[AUTH] Using cached JWKS (age: %.0fs)", now - _jwks_cache_time)
        return _jwks_cache

    if not settings.sso_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO not configured",
        )

    jwks_url = f"{settings.sso_url}/api/auth/jwks"
    logger.info("[AUTH] Fetching JWKS from %s", jwks_url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_cache_time = now
            key_count = len(_jwks_cache.get("keys", []))
            logger.info("[AUTH] JWKS fetched successfully: %d keys", key_count)
            return _jwks_cache
    except httpx.HTTPError as e:
        logger.error("[AUTH] JWKS fetch failed: %s", e)
        # If we have cached keys, use them even if expired
        if _jwks_cache:
            logger.warning("[AUTH] Using expired JWKS cache as fallback")
            return _jwks_cache
        logger.error("[AUTH] No cached JWKS available, auth will fail")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Authentication service unavailable: {e}",
        ) from e


async def verify_jwt(token: str) -> dict[str, Any]:
    """Verify JWT signature using JWKS public keys.

    This is done locally - no SSO call per request.
    """
    token_preview = f"{token[:10]}...{token[-10:]}" if len(token) > 25 else "[short]"
    logger.debug("[AUTH] Verifying JWT: %s", token_preview)

    try:
        jwks = await get_jwks()

        # Get key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg")
        logger.debug("[AUTH] JWT header - kid: %s, alg: %s", kid, alg)

        # Find matching public key
        rsa_key: dict[str, Any] | None = None
        available_kids = []
        for key in jwks.get("keys", []):
            available_kids.append(key.get("kid"))
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            logger.error(
                "[AUTH] Key not found - token kid: %s, available kids: %s",
                kid,
                available_kids,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signing key not found in JWKS",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug("[AUTH] Found matching key, verifying signature...")

        # Verify signature and decode payload
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Audience varies by client
        )

        logger.info(
            "[AUTH] JWT verified - sub: %s, email: %s",
            payload.get("sub"),
            payload.get("email"),
        )
        return payload

    except JWTError as e:
        logger.error("[AUTH] JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def verify_opaque_token(token: str) -> dict[str, Any]:
    """Verify opaque access token via SSO userinfo endpoint.

    When OAuth clients send opaque access_tokens instead of JWTs,
    we validate them by calling the SSO's userinfo endpoint.
    """
    if not settings.sso_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO not configured",
        )

    userinfo_url = f"{settings.sso_url}/api/auth/oauth2/userinfo"
    token_preview = f"{token[:10]}...{token[-10:]}" if len(token) > 25 else "[short]"
    logger.info("[AUTH] Validating opaque token via userinfo: %s", token_preview)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 401:
                logger.warning("[AUTH] Userinfo returned 401 - token invalid or expired")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token invalid or expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if response.status_code != 200:
                logger.error("[AUTH] Userinfo returned %d", response.status_code)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Userinfo request failed: {response.status_code}",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            data = response.json()
            logger.info(
                "[AUTH] Opaque token verified - sub: %s, email: %s",
                data.get("sub"),
                data.get("email"),
            )
            return data

    except httpx.RequestError as e:
        logger.error("[AUTH] Userinfo request failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Authentication service unavailable: {e}",
        ) from e


class CurrentUser:
    """Authenticated user extracted from JWT claims."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.id: str = payload.get("sub", "")
        self.email: str = payload.get("email", "")
        self.name: str = payload.get("name", "")
        self.role: str = payload.get("role", "user")
        org_ids = payload.get("organization_ids") or []
        self.tenant_id: str | None = (
            payload.get("tenant_id")
            or payload.get("organization_id")
            or (org_ids[0] if org_ids else None)
        )
        self.organization_ids: list[str] = org_ids if isinstance(org_ids, list) else []
        self.client_id: str | None = payload.get("client_id")
        self.client_name: str | None = payload.get("client_name")

    def __repr__(self) -> str:
        client_info = f", client={self.client_name!r}" if self.client_name else ""
        return f"CurrentUser(id={self.id!r}, email={self.email!r}{client_info})"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """FastAPI dependency to get authenticated user from token.

    Dev mode bypass available for local development.
    """
    # Dev mode bypass (T028)
    if settings.dev_mode:
        logger.debug("[AUTH] Dev mode enabled, bypassing token verification")
        return CurrentUser(
            {
                "sub": settings.dev_user_id,
                "email": settings.dev_user_email,
                "name": settings.dev_user_name,
                "role": "admin",
            }
        )

    # In production, require authentication
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    token_parts = token.count(".")

    logger.debug(
        "[AUTH] Token validation - segments: %d, type: %s",
        token_parts + 1,
        "JWT" if token_parts == 2 else "opaque",
    )

    # Try JWT first if it looks like a JWT
    if token_parts == 2:
        try:
            payload = await verify_jwt(token)
            user = CurrentUser(payload)
            logger.info("[AUTH] Authenticated via JWT: %s", user)
            return user
        except HTTPException:
            logger.debug("[AUTH] JWT validation failed, trying opaque token...")

    # Opaque token validation via userinfo endpoint
    payload = await verify_opaque_token(token)
    user = CurrentUser(payload)
    logger.info("[AUTH] Authenticated via opaque token: %s", user)
    return user


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser | None:
    """Optional authentication - returns None if no credentials provided.

    Useful for endpoints that work both authenticated and anonymous.
    """
    if settings.dev_mode:
        return CurrentUser(
            {
                "sub": settings.dev_user_id,
                "email": settings.dev_user_email,
                "name": settings.dev_user_name,
                "role": "admin",
            }
        )

    if not credentials:
        return None

    return await get_current_user(request, credentials)
