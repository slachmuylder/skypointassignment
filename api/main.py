"""Pinewood Gold API.

Run: uvicorn api.main:app --reload
Docs: http://127.0.0.1:8000/docs (FastAPI's auto-generated OpenAPI/Swagger UI)

Every endpoint requires a bearer JWT (see api/auth.py) and every endpoint's
community/region scope is resolved server-side via api/scope.py -- a client
passing a community_id or region outside what their token grants gets a 403,
never a silently-filtered response.
"""
from fastapi import Depends, FastAPI
from api.auth import get_claims
from api.scope import resolve_communities
from api import queries

app = FastAPI(title="Pinewood Gold API", version="1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/occupancy")
def get_occupancy(
    community_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    claims: dict = Depends(get_claims),
):
    scope = resolve_communities(claims, community_id=community_id)
    return queries.occupancy(scope, start, end).to_dict(orient="records")


@app.get("/move-outs/reasons")
def get_moveout_reasons(
    community_id: str | None = None,
    period: str | None = None,
    claims: dict = Depends(get_claims),
):
    """`period` is the trailing-12-months reference date (YYYY-MM-DD,
    defaults to the latest move-out date in the data) -- matches
    sql/views/03_top_moveout_reasons.sql's trailing-12-month window."""
    scope = resolve_communities(claims, community_id=community_id)
    return queries.moveout_reasons(scope, period).to_dict(orient="records")


@app.get("/incidents/summary")
def get_incidents_summary(
    region: str | None = None,
    start: str | None = None,
    end: str | None = None,
    claims: dict = Depends(get_claims),
):
    scope = resolve_communities(claims, region=region)
    return queries.incidents_summary(scope, start, end).to_dict(orient="records")


@app.get("/labor/cost")
def get_labor_cost(
    community_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    claims: dict = Depends(get_claims),
):
    scope = resolve_communities(claims, community_id=community_id)
    return queries.labor_cost(scope, start, end).to_dict(orient="records")


@app.get("/reviews/summary")
def get_reviews_summary(
    community_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    claims: dict = Depends(get_claims),
):
    scope = resolve_communities(claims, community_id=community_id)
    return queries.reviews_summary(scope, start, end).to_dict(orient="records")
