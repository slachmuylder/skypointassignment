"""JWT auth + server-side RBAC.

Scheme: JWT (HS256), chosen over a raw API key because it lets the role and
scope (region / community_id) travel inside the signed token itself, so the
API never has to look anything up in a separate credentials store to know
what a caller is allowed to see -- it just verifies the signature and reads
the claims. For a single-service demo like this, HS256 (shared secret) is
simpler to defend than RS256 (asymmetric) since there's no second service
that needs to verify tokens without holding the signing key.

The secret is a hard-coded dev default so the API and generate_tokens.py
work out of the box for reviewers; in a real deployment it would come from
an environment variable / secrets manager instead (see README "Assumptions").
"""
import datetime as dt
import os
from enum import Enum

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.environ.get("PINEWOOD_JWT_SECRET", "dev-only-secret-do-not-use-in-production")
ALGORITHM = "HS256"
TOKEN_TTL_DAYS = 30

# auto_error=False so a missing Authorization header reaches get_claims and
# gets a 401 like an invalid/expired token would, instead of HTTPBearer's
# default 403 for "no credentials at all".
_bearer = HTTPBearer(auto_error=False)


class Role(str, Enum):
    CORPORATE_ADMIN = "corporate_admin"
    REGIONAL_DIRECTOR = "regional_director"
    COMMUNITY_EXECUTIVE_DIRECTOR = "community_executive_director"


def create_token(role: Role, region: str | None = None, community_id: str | None = None) -> str:
    if role == Role.REGIONAL_DIRECTOR and not region:
        raise ValueError("regional_director token requires a region")
    if role == Role.COMMUNITY_EXECUTIVE_DIRECTOR and not community_id:
        raise ValueError("community_executive_director token requires a community_id")

    payload = {
        "role": role.value,
        "region": region,
        "community_id": community_id,
        "iat": dt.datetime.now(dt.timezone.utc),
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_claims(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """FastAPI dependency: verifies the bearer token and returns its claims.
    Every endpoint depends on this (directly or via resolve_scope), so an
    unauthenticated request always gets a 401 before any data is touched."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
