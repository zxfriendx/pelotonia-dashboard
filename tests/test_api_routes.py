"""Tests for /api/routes and /api/route-members endpoints."""

import json


def test_routes_returns_200(client):
    resp = client.get("/api/routes")
    assert resp.status_code == 200


def test_routes_returns_list(client):
    data = json.loads(client.get("/api/routes").data)
    assert isinstance(data, list)


def test_routes_count(client):
    """2 routes seeded (signature 100mi + gravel 50mi)."""
    data = json.loads(client.get("/api/routes").data)
    assert len(data) == 2


def test_route_has_required_fields(client):
    data = json.loads(client.get("/api/routes").data)
    required = {
        "id", "name", "distance", "fundraising_commitment",
        "ride_name", "ride_type", "signups",
        "route_raised", "route_committed",
    }
    for route in data:
        assert required.issubset(set(route.keys())), (
            f"Missing fields: {required - set(route.keys())}"
        )


def test_route_signup_count(client):
    """route_100 has 1 member_route entry; route_grv50 has 0."""
    data = json.loads(client.get("/api/routes").data)
    sig_route = next(r for r in data if r["id"] == "route_100")
    grv_route = next(r for r in data if r["id"] == "route_grv50")
    assert sig_route["signups"] == 1
    assert grv_route["signups"] == 0


def test_route_ride_total_signups(client):
    """ride_total_signups counts distinct members per ride type."""
    data = json.loads(client.get("/api/routes").data)
    sig_route = next(r for r in data if r["id"] == "route_100")
    assert sig_route["ride_total_signups"] == 1


def test_route_members_returns_200(client):
    resp = client.get("/api/route-members/route_100")
    assert resp.status_code == 200


def test_route_members_for_signature(client):
    """Alice is on route_100."""
    data = json.loads(client.get("/api/route-members/route_100").data)
    assert len(data) == 1
    assert data[0]["public_id"] == "m001"
    assert data[0]["name"] == "Alice Rider"


def test_route_members_years_field(client):
    """Alice has '3 years' tag, so years should be 3."""
    data = json.loads(client.get("/api/route-members/route_100").data)
    assert data[0]["years"] == 3
    assert data[0]["is_first_year"] == 0


def test_route_members_empty_route(client):
    """Gravel route has no members signed up."""
    data = json.loads(client.get("/api/route-members/route_grv50").data)
    assert data == []
