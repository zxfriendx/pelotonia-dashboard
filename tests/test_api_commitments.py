"""Tests for /api/commitment-gap endpoint."""

import json
import sqlite3


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


def test_commitment_gap_uses_credited_and_sub_dollar_tolerance(test_db, client):
    """Commitments are measured against max(raised, attributed), and Pelotonia
    treats a shortfall under $1 as met (2026-10-18 audit against committedMet)."""
    conn = sqlite3.connect(str(test_db))
    # m002: raised short of $1,500 but team funds bring attributed to the commitment
    conn.execute("UPDATE members SET raised=1000, attributed=1500 WHERE public_id='m002'")
    # m003: 50 cents short of $1,000 -> met
    conn.execute("UPDATE members SET raised=999.5, attributed=999.5 WHERE public_id='m003'")
    # m004: genuinely short ($200 of $500, nothing attributed)
    conn.execute("UPDATE members SET raised=200, attributed=0 WHERE public_id='m004'")
    conn.commit()
    conn.close()

    data = json.loads(client.get("/api/commitment-gap").data)
    by_id = {m["public_id"]: m for m in data["members"]}
    assert by_id["m002"]["credited"] == 1500
    assert by_id["m002"]["shortfall"] == 0
    assert by_id["m003"]["shortfall"] == 0
    assert by_id["m004"]["credited"] == 200
    assert by_id["m004"]["shortfall"] == 300
    s = data["summary"]
    assert s["below_count"] == 1
    assert s["shortfall_total"] == 300
