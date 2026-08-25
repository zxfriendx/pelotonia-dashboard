"""Tests for /api/commitment-gap endpoint."""

import json


def test_commitment_gap_returns_200(client):
    assert client.get("/api/commitment-gap").status_code == 200


def test_commitment_gap_structure(client):
    data = json.loads(client.get("/api/commitment-gap").data)
    assert set(data.keys()) == {"summary", "members", "timeline"}


def test_commitment_gap_summary(client):
    """Fixture: m001..m004 have commitments (2000/1500/1000/500), all met by raised."""
    s = json.loads(client.get("/api/commitment-gap").data)["summary"]
    assert s["committed_members"] == 4
    assert s["met_count"] == 4
    assert s["below_count"] == 0
    assert s["zero_count"] == 0
    assert s["total_committed"] == 5000.0
    assert s["shortfall_total"] == 0
    # surplus: (5000-2000) + (3000-1500) + (1000-1000) + (500-500)
    assert s["surplus_total"] == 4500.0


def test_commitment_gap_member_fields(client):
    members = json.loads(client.get("/api/commitment-gap").data)["members"]
    assert len(members) == 4
    required = {
        "public_id", "name", "team_name", "committed_amount", "raised",
        "shortfall", "pct_fulfilled", "committed_high_roller",
    }
    for m in members:
        assert required.issubset(set(m.keys()))
    alice = next(m for m in members if m["public_id"] == "m001")
    assert alice["shortfall"] == 0
    assert alice["pct_fulfilled"] == 100.0


def test_commitment_gap_timeline(client):
    """Timeline replays tracked donations: dates ascend, shortfall never increases."""
    timeline = json.loads(client.get("/api/commitment-gap").data)["timeline"]
    assert timeline, "expected timeline points from fixture donations"
    dates = [t["date"] for t in timeline]
    assert dates == sorted(dates)
    shortfalls = [t["shortfall"] for t in timeline]
    assert all(a >= b for a, b in zip(shortfalls, shortfalls[1:]))
    assert all(t["below_count"] >= 0 for t in timeline)
