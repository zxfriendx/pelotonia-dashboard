"""Tests for /api/bundle endpoint."""

import json


BUNDLE_KEYS = {
    "overview",
    "teams",
    "timeline",
    "fundraisers",
    "donors",
    "members",
    "donations",
    "teamBreakdown",
    "commitTiers",
    "rideTypes",
    "routes",
    "signupTimeline",
    "events",
    "companies",
    "ticker",
    "subteamSnapshots",
    "kidsOverview",
    "kidsSnapshots",
    "orgLeaderboard",
    "orgSnapshots",
}


def test_bundle_returns_200(client):
    resp = client.get("/api/bundle")
    assert resp.status_code == 200


def test_bundle_has_all_keys(client):
    resp = client.get("/api/bundle")
    data = json.loads(resp.data)
    assert set(data.keys()) == BUNDLE_KEYS


def test_bundle_is_cached(client):
    """Second request should return cached data (same content)."""
    resp1 = client.get("/api/bundle")
    resp2 = client.get("/api/bundle")
    assert resp1.data == resp2.data


def test_bundle_overview_is_dict(client):
    data = json.loads(client.get("/api/bundle").data)
    assert isinstance(data["overview"], dict)


def test_bundle_teams_is_list(client):
    data = json.loads(client.get("/api/bundle").data)
    assert isinstance(data["teams"], list)


def test_bundle_members_is_list(client):
    data = json.loads(client.get("/api/bundle").data)
    assert isinstance(data["members"], list)


def test_bundle_donations_is_list(client):
    data = json.loads(client.get("/api/bundle").data)
    assert isinstance(data["donations"], list)


def test_bundle_routes_is_list(client):
    data = json.loads(client.get("/api/bundle").data)
    assert isinstance(data["routes"], list)


def test_bundle_kids_overview_is_dict(client):
    data = json.loads(client.get("/api/bundle").data)
    assert isinstance(data["kidsOverview"], dict)


def test_bundle_org_leaderboard_is_list(client):
    data = json.loads(client.get("/api/bundle").data)
    assert isinstance(data["orgLeaderboard"], list)
