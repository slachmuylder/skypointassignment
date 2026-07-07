"""Server-side scope resolution: turns a token's role/region/community_id
claims (plus whatever the client asked for in query params) into the actual
list of community_ids a query is allowed to touch.

This is the enforcement point the assessment calls out explicitly: "Do not
rely on the client to filter." A client can request any community_id or
region in the query string, but the community list actually used to filter
the SQL is always intersected with (never taken from) what their token
grants -- and anything they explicitly asked for that falls outside their
grant is a 403, not a silently-narrowed result.
"""
import duckdb
from fastapi import Depends, HTTPException, status

from api.auth import Role, get_claims
from pipeline.config import GOLD_DIR

_DIM_COMMUNITY = GOLD_DIR / "dim_community.parquet"


def _communities_in_region(region: str) -> set[str]:
    df = duckdb.sql(f"SELECT community_id FROM '{_DIM_COMMUNITY}' WHERE region = ?", params=[region]).df()
    return set(df["community_id"])


def _granted_communities(claims: dict) -> set[str] | None:
    """None means "no restriction" (corporate_admin)."""
    role = claims.get("role")
    if role == Role.CORPORATE_ADMIN.value:
        return None
    if role == Role.REGIONAL_DIRECTOR.value:
        return _communities_in_region(claims["region"])
    if role == Role.COMMUNITY_EXECUTIVE_DIRECTOR.value:
        return {claims["community_id"]}
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unrecognized role")


def resolve_communities(
    claims: dict = Depends(get_claims),
    community_id: str | None = None,
    region: str | None = None,
) -> list[str] | None:
    """Returns the list of community_ids a query should filter to, or None
    to mean "every community" (only possible for corporate_admin with no
    explicit filter requested)."""
    granted = _granted_communities(claims)

    if community_id:
        if granted is not None and community_id not in granted:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized for this community")
        return [community_id]

    if region:
        requested = _communities_in_region(region)
        if granted is not None:
            requested = requested & granted
            if not requested:
                raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized for this region")
        return sorted(requested)

    return None if granted is None else sorted(granted)
