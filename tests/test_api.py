"""API auth/RBAC tests. Requires the pipeline to have been run at least once
(so pipeline/data/gold/*.parquet exists) -- see README for setup.
"""
from fastapi.testclient import TestClient

from api.auth import Role, create_token
from api.main import app

client = TestClient(app)

admin_token = create_token(Role.CORPORATE_ADMIN)
regional_token = create_token(Role.REGIONAL_DIRECTOR, region="Pacific Northwest")
ed_token = create_token(Role.COMMUNITY_EXECUTIVE_DIRECTOR, community_id="C001")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_request_rejected():
    resp = client.get("/occupancy")
    assert resp.status_code == 401


def test_invalid_token_rejected():
    resp = client.get("/occupancy", headers=auth("not-a-real-token"))
    assert resp.status_code == 401


def test_admin_sees_all_communities():
    resp = client.get("/occupancy", headers=auth(admin_token))
    assert resp.status_code == 200
    assert {r["community_id"] for r in resp.json()} == {f"C{i:03d}" for i in range(1, 15)}


def test_regional_director_scoped_to_region():
    resp = client.get("/occupancy", headers=auth(regional_token))
    assert resp.status_code == 200
    assert {r["community_id"] for r in resp.json()} == {"C001", "C002", "C003", "C004", "C005"}


def test_regional_director_blocked_from_other_region_community():
    resp = client.get("/occupancy?community_id=C011", headers=auth(regional_token))
    assert resp.status_code == 403


def test_community_ed_scoped_to_own_community():
    resp = client.get("/occupancy", headers=auth(ed_token))
    assert resp.status_code == 200
    assert {r["community_id"] for r in resp.json()} == {"C001"}


def test_community_ed_blocked_from_other_community():
    resp = client.get("/occupancy?community_id=C002", headers=auth(ed_token))
    assert resp.status_code == 403


def test_community_ed_can_request_own_community_explicitly():
    resp = client.get("/occupancy?community_id=C001", headers=auth(ed_token))
    assert resp.status_code == 200


def test_regional_director_blocked_from_other_region_param():
    resp = client.get("/incidents/summary?region=South", headers=auth(regional_token))
    assert resp.status_code == 403


def test_all_five_endpoints_respond_for_admin():
    for path in ["/occupancy", "/move-outs/reasons", "/incidents/summary", "/labor/cost", "/reviews/summary"]:
        resp = client.get(path, headers=auth(admin_token))
        assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text}"
