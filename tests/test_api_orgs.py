"""Tests for /api/org-leaderboard and /api/org-snapshots endpoints."""

import json


def test_org_leaderboard_returns_200(client):
    resp = client.get("/api/org-leaderboard")
    assert resp.status_code == 200


def test_org_leaderboard_returns_list(client):
    data = json.loads(client.get("/api/org-leaderboard").data)
    assert isinstance(data, list)


def test_org_leaderboard_count(client):
    """2 org_snapshots seeded for the same date."""
    data = json.loads(client.get("/api/org-leaderboard").data)
    assert len(data) == 2


def test_org_leaderboard_sorted_by_raised_desc(client):
    data = json.loads(client.get("/api/org-leaderboard").data)
    raised_values = [o["raised"] for o in data]
    assert raised_values == sorted(raised_values, reverse=True)


def test_org_leaderboard_has_fields(client):
    data = json.loads(client.get("/api/org-leaderboard").data)
    required = {
        "team_id", "name", "members_count", "sub_team_count",
        "raised", "goal", "all_time_raised", "last_scraped",
    }
    for org in data:
        assert required.issubset(set(org.keys()))


def test_org_leaderboard_values(client):
    data = json.loads(client.get("/api/org-leaderboard").data)
    org_one = next(o for o in data if o["team_id"] == "org001")
    assert org_one["name"] == "Org One"
    assert org_one["raised"] == 80000.0
    assert org_one["members_count"] == 200


def test_org_snapshots_returns_200(client):
    resp = client.get("/api/org-snapshots")
    assert resp.status_code == 200


def test_org_snapshots_returns_list(client):
    data = json.loads(client.get("/api/org-snapshots").data)
    assert isinstance(data, list)


def test_org_snapshots_count(client):
    data = json.loads(client.get("/api/org-snapshots").data)
    assert len(data) == 2
