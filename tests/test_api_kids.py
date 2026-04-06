"""Tests for /api/kids-overview and /api/kids-snapshots endpoints."""

import json


def test_kids_overview_returns_200(client):
    resp = client.get("/api/kids-overview")
    assert resp.status_code == 200


def test_kids_overview_has_fields(client):
    data = json.loads(client.get("/api/kids-overview").data)
    expected = {
        "snapshot_date", "campaign_id", "fundraiser_count",
        "estimated_amount_raised", "monetary_goal", "team_count",
        "last_scraped",
    }
    assert set(data.keys()) == expected


def test_kids_overview_values(client):
    data = json.loads(client.get("/api/kids-overview").data)
    assert data["fundraiser_count"] == 150
    assert data["estimated_amount_raised"] == 45000.0
    assert data["monetary_goal"] == 100000.0
    assert data["team_count"] == 12


def test_kids_snapshots_returns_200(client):
    resp = client.get("/api/kids-snapshots")
    assert resp.status_code == 200


def test_kids_snapshots_returns_list(client):
    data = json.loads(client.get("/api/kids-snapshots").data)
    assert isinstance(data, list)


def test_kids_snapshots_count(client):
    """1 kids_snapshot seeded."""
    data = json.loads(client.get("/api/kids-snapshots").data)
    assert len(data) == 1


def test_kids_snapshots_fields(client):
    data = json.loads(client.get("/api/kids-snapshots").data)
    expected = {
        "snapshot_date", "fundraiser_count",
        "estimated_amount_raised", "monetary_goal", "team_count",
    }
    assert set(data[0].keys()) == expected
