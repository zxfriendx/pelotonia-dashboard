"""Tests for /api/members endpoint."""

import json


def test_members_returns_200(client):
    resp = client.get("/api/members")
    assert resp.status_code == 200


def test_members_returns_list(client):
    data = json.loads(client.get("/api/members").data)
    assert isinstance(data, list)


def test_members_count(client):
    """Should return all 5 seeded members."""
    data = json.loads(client.get("/api/members").data)
    assert len(data) == 5


def test_members_sorted_by_raised_desc(client):
    """Members should be ordered by raised descending."""
    data = json.loads(client.get("/api/members").data)
    raised_values = [m["raised"] for m in data]
    assert raised_values == sorted(raised_values, reverse=True)


def test_member_has_required_fields(client):
    data = json.loads(client.get("/api/members").data)
    required = {
        "public_id", "name", "raised", "all_time_raised",
        "is_captain", "is_cancer_survivor", "team_name",
        "is_rider", "is_challenger", "is_volunteer",
        "committed_amount", "route_names",
    }
    for member in data:
        assert required.issubset(set(member.keys())), (
            f"Missing fields: {required - set(member.keys())}"
        )


def test_member_route_names_populated(client):
    """Alice (m001) has a route; others should have empty string."""
    data = json.loads(client.get("/api/members").data)
    alice = next(m for m in data if m["public_id"] == "m001")
    eve = next(m for m in data if m["public_id"] == "m005")
    assert alice["route_names"] == "100 Mile Signature"
    assert eve["route_names"] == ""


def test_member_team_name_joined(client):
    """Members should have their sub-team name populated."""
    data = json.loads(client.get("/api/members").data)
    alice = next(m for m in data if m["public_id"] == "m001")
    assert alice["team_name"] == "Sub-Team Alpha"
