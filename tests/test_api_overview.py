"""Tests for /api/overview endpoint."""

import json


EXPECTED_FIELDS = {
    "team_name",
    "raised",
    "goal",
    "all_time_raised",
    "members_count",
    "donations_count",
    "total_donated",
    "cancer_survivors",
    "high_rollers",
    "signature_riders",
    "gravel_riders",
    "riders",
    "challengers",
    "volunteers",
    "total_committed",
    "hr_committed",
    "std_committed",
    "general_peloton_funds",
    "first_year",
    "last_scraped",
}


def test_overview_returns_200(client):
    resp = client.get("/api/overview")
    assert resp.status_code == 200


def test_overview_has_all_fields(client):
    data = json.loads(client.get("/api/overview").data)
    assert set(data.keys()) == EXPECTED_FIELDS


def test_overview_team_name(client):
    data = json.loads(client.get("/api/overview").data)
    assert data["team_name"] == "Team Huntington Bank"


def test_overview_members_count(client):
    """Should count all 5 seeded members."""
    data = json.loads(client.get("/api/overview").data)
    assert data["members_count"] == 5


def test_overview_riders_count(client):
    """3 members have is_rider=1."""
    data = json.loads(client.get("/api/overview").data)
    assert data["riders"] == 3


def test_overview_challengers_count(client):
    data = json.loads(client.get("/api/overview").data)
    assert data["challengers"] == 1


def test_overview_volunteers_count(client):
    data = json.loads(client.get("/api/overview").data)
    assert data["volunteers"] == 1


def test_overview_donations_count(client):
    """10 seeded donations."""
    data = json.loads(client.get("/api/overview").data)
    assert data["donations_count"] == 10


def test_overview_total_donated(client):
    """Sum of all 10 donation amounts."""
    data = json.loads(client.get("/api/overview").data)
    expected = 500 + 250 + 100 + 1000 + 200 + 300 + 150 + 75 + 50 + 25
    assert data["total_donated"] == expected


def test_overview_cancer_survivors(client):
    """Only Alice (m001) is a cancer survivor."""
    data = json.loads(client.get("/api/overview").data)
    assert data["cancer_survivors"] == 1


def test_overview_high_rollers(client):
    """Only Alice has committed_high_roller=1."""
    data = json.loads(client.get("/api/overview").data)
    assert data["high_rollers"] == 1


def test_overview_raised_matches_parent(client):
    """Raised should come from the parent team row."""
    data = json.loads(client.get("/api/overview").data)
    assert data["raised"] == 15000.0


def test_overview_signature_riders(client):
    """One member_route entry with ride_type=signature."""
    data = json.loads(client.get("/api/overview").data)
    assert data["signature_riders"] == 1


def test_overview_first_year(client):
    """Bob (m002) has '1 year' tag and is_rider=1."""
    data = json.loads(client.get("/api/overview").data)
    assert data["first_year"] == 1
