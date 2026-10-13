from __future__ import annotations

import time
import uuid
import math
from dataclasses import dataclass

import anyio
import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.models import OAuthBinding
from backend.app.models.enums import UserRole


class VerifiedAccessToken(AccessToken):
    issuer: str


def bound_user(db: Session, issuer: str, subject: str):
    binding = db.scalar(select(OAuthBinding).where(
        OAuthBinding.issuer == issuer, OAuthBinding.subject == subject, OAuthBinding.is_active.is_(True),
    ))
    if binding is None or not binding.user.is_active:
        return None
    return binding.user


class JWTVerifier:
    """Validate only the configured issuer's access tokens; never discover URLs from a token."""

    def __init__(self, config: Settings, session_factory):
        if not config.mcp_enabled:
            raise ValueError("MCP is disabled")
        self.config = config
        self.session_factory = session_factory
        self.jwks = jwt.PyJWKClient(config.oauth_jwks_url, timeout=5, lifespan=60, cache_keys=False)

    def _verify(self, token: str) -> VerifiedAccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in self.config.oauth_algorithms or not isinstance(header.get("kid"), str):
                return None
            # Token jku/x5u and unverified claims cannot select the key source.
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token, key.key, algorithms=self.config.oauth_algorithms,
                issuer=self.config.oauth_issuer, audience=self.config.oauth_resource_url,
                options={"require": ["iss", "sub", "aud", "exp", "nbf"]},
            )
            if not isinstance(claims["sub"], str) or not claims["sub"].strip():
                return None
            if any(isinstance(claims[c], bool) or not isinstance(claims[c], (int, float)) or not math.isfinite(claims[c]) for c in ("exp", "nbf")):
                return None
            scope = claims.get("scope", "")
            if not isinstance(scope, str):
                return None
            scopes = scope.split()
            if "legalize:read" not in scopes:
                return None
            with self.session_factory() as db:
                if bound_user(db, claims["iss"], claims["sub"]) is None:
                    return None
            return VerifiedAccessToken(
                token=token, client_id=str(claims.get("client_id") or claims.get("azp") or claims["sub"]),
                subject=claims["sub"], issuer=claims["iss"], scopes=scopes,
                expires_at=int(claims["exp"]), resource=self.config.oauth_resource_url,
                claims={"iss": claims["iss"]},
            )
        except (jwt.PyJWTError, ValueError, OSError):
            return None

    async def verify_token(self, token: str) -> VerifiedAccessToken | None:
        return await anyio.to_thread.run_sync(self._verify, token)


@dataclass(frozen=True)
class Capabilities:
    actor_id: uuid.UUID
    can_read: bool
    can_release: bool


def invocation_capabilities(db: Session) -> Capabilities:
    token = get_access_token()
    if not isinstance(token, VerifiedAccessToken) or token.expires_at is None or token.expires_at <= time.time():
        raise ToolError("Authenticated HTTP context required")
    user = bound_user(db, token.issuer, token.subject)
    if user is None:
        raise ToolError("Active local user binding required")
    return Capabilities(
        actor_id=user.id,
        can_read="legalize:read" in token.scopes,
        can_release="legalize:release" in token.scopes and user.role in {UserRole.REVIEWER, UserRole.ADMIN},
    )
