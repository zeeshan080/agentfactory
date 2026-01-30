"""JWT Authentication for AgentFactory API.

Validates Bearer tokens from SSO using JWKS (RS256).
Extracts user_id from token for logging purposes.
"""

import asyncio
import time
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient, PyJWKClientError

from .config import get_config


# =============================================================================
# Authentication Context
# =============================================================================


@dataclass
class AuthContext:
    """Authentication context extracted from JWT token."""

    user_id: str
    email: str | None = None
    role: str | None = None


# =============================================================================
# Token Cache
# =============================================================================


@dataclass
class CachedToken:
    """Cached validated token with expiry."""

    auth_context: AuthContext
    cached_at: float
    ttl: int

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > (self.cached_at + self.ttl)


# =============================================================================
# JWKS Token Verifier
# =============================================================================


class JWKSTokenVerifier:
    """Verify JWT tokens using JWKS from SSO server.

    Features:
    - RS256 asymmetric verification (no shared secrets)
    - JWKS auto-refresh with caching (1 hour default)
    - Token validation caching (5 minutes default)
    - Key rotation handling via `kid` header

    Token Validation:
    1. Verify signature using JWKS
    2. Check exp claim hasn't passed
    3. Verify iss matches expected issuer
    4. Extract sub for user identification
    """

    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        audience: str | None = None,
        jwks_cache_ttl: int = 3600,
        token_cache_ttl: int = 300,
    ):
        """Initialize JWKS token verifier.

        Args:
            jwks_url: JWKS endpoint URL
            issuer: Expected issuer claim
            audience: Expected audience claim (OAuth client_id for id_tokens)
            jwks_cache_ttl: JWKS cache TTL in seconds (default: 1 hour)
            token_cache_ttl: Token cache TTL in seconds (default: 5 minutes)
        """
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.jwks_cache_ttl = jwks_cache_ttl
        self.token_cache_ttl = token_cache_ttl

        # JWKS client (lazy initialized)
        self._jwks_client: PyJWKClient | None = None
        self._jwks_client_lock = asyncio.Lock()

        # Token validation cache
        self._token_cache: dict[str, CachedToken] = {}
        self._cache_lock = asyncio.Lock()

    async def _get_jwks_client(self) -> PyJWKClient:
        """Get or create JWKS client with caching."""
        if self._jwks_client is None:
            async with self._jwks_client_lock:
                if self._jwks_client is None:
                    self._jwks_client = PyJWKClient(
                        self.jwks_url,
                        cache_jwk_set=True,
                        lifespan=self.jwks_cache_ttl,
                    )
        return self._jwks_client

    async def _get_cached_token(self, token: str) -> AuthContext | None:
        """Get token from cache if valid."""
        async with self._cache_lock:
            cached = self._token_cache.get(token)
            if cached and not cached.is_expired():
                return cached.auth_context
            if cached:
                del self._token_cache[token]
        return None

    async def _cache_token(self, token: str, auth_context: AuthContext) -> None:
        """Cache validated token."""
        async with self._cache_lock:
            self._token_cache[token] = CachedToken(
                auth_context=auth_context,
                cached_at=time.time(),
                ttl=self.token_cache_ttl,
            )
            # Prune cache if too large
            if len(self._token_cache) > 1000:
                entries = sorted(
                    self._token_cache.items(), key=lambda x: x[1].cached_at
                )
                for key, _ in entries[:100]:
                    del self._token_cache[key]

    async def verify_token(self, token: str) -> AuthContext | None:
        """Verify JWT using JWKS and return AuthContext if valid.

        Args:
            token: JWT string from Authorization header

        Returns:
            AuthContext if valid, None if invalid
        """
        # Check cache first
        cached = await self._get_cached_token(token)
        if cached:
            return cached

        try:
            jwks_client = await self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Decode with audience validation if specified
            decode_options = {
                "algorithms": ["RS256"],
                "issuer": self.issuer,
            }
            if self.audience:
                decode_options["audience"] = self.audience

            payload = jwt.decode(token, signing_key.key, **decode_options)

            # Extract user info from token claims
            auth_context = AuthContext(
                user_id=payload.get("sub", "unknown"),
                email=payload.get("email"),
                role=payload.get("role"),
            )

            await self._cache_token(token, auth_context)
            return auth_context

        except jwt.ExpiredSignatureError:
            print("JWT Error: Token expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"JWT Error: Invalid token - {e}")
            return None
        except PyJWKClientError as e:
            print(f"JWT Error: JWKS client error - {e}")
            return None
        except Exception as e:
            print(f"JWT Error: Unexpected - {e}")
            return None


# =============================================================================
# Global Verifier
# =============================================================================

_verifier: JWKSTokenVerifier | None = None


def get_token_verifier() -> JWKSTokenVerifier | None:
    """Get the global token verifier.

    Returns:
        JWKSTokenVerifier if auth is enabled, None otherwise.
    """
    global _verifier

    config = get_config()

    if not config.auth_enabled:
        return None

    if _verifier is None:
        _verifier = JWKSTokenVerifier(
            jwks_url=config.jwks_url,
            issuer=config.auth_server_url,
            audience=config.auth_client_id,
            jwks_cache_ttl=config.jwks_cache_ttl,
            token_cache_ttl=config.token_cache_ttl,
        )

    return _verifier


async def verify_bearer_token(authorization: str | None) -> AuthContext | None:
    """Verify Authorization header and extract auth context.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        AuthContext if valid, None if invalid or auth disabled.
    """
    verifier = get_token_verifier()

    if verifier is None:
        # Auth disabled - return anonymous context for development
        return AuthContext(user_id="anonymous", email=None, role=None)

    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix
    return await verifier.verify_token(token)
