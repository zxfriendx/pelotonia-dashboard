#!/usr/bin/env python3
"""
Pelotonia Team Huntington — Fundraising Dashboard

A self-contained Flask app serving an interactive dashboard with:
  - Cumulative fundraising growth over time
  - Sub-team breakdown (bar chart + table)
  - Top fundraisers and donors
  - Member roster with search/filter
  - Donation timeline

Usage:
  python dashboard.py              # Start on port 5050
  python dashboard.py --port 8080  # Custom port

Requires: flask, sqlite3 (stdlib)
Database: pelotonia_data.db (created by pelotonia_scraper.py)
"""

import argparse
import json
import os
import sqlite3
import urllib.request
from pathlib import Path

from flask import Flask, jsonify, Response, send_from_directory

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PELOTONIA_DB", SCRIPT_DIR / "pelotonia_data.db"))
PARENT_TEAM_ID = "a0s3t00000BKX8sAAH"

app = Flask(__name__)

# mtime-based cache — rebuilt only when the DB file is modified (i.e., after scraper runs)
_cache = {"data": None, "db_mtime": 0}


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── JSON API ──────────────────────────────────────────────────────────────

def _get_overview(conn):
    parent = conn.execute(
        "SELECT name, raised, COALESCE(goal_override, goal) as goal, all_time_raised, members_count, general_peloton_funds FROM teams WHERE id=?",
        (PARENT_TEAM_ID,),
    ).fetchone()
    members = conn.execute("SELECT COUNT(*) as cnt FROM members").fetchone()["cnt"]
    donations = conn.execute("SELECT COUNT(*) as cnt FROM donations").fetchone()["cnt"]
    total_donated = conn.execute("SELECT COALESCE(SUM(amount),0) as s FROM donations").fetchone()["s"]
    survivors = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_cancer_survivor=1").fetchone()["cnt"]
    high_rollers = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE tags LIKE '%High Roller%'").fetchone()["cnt"]
    last_scraped = conn.execute("SELECT MAX(last_scraped) as ls FROM members").fetchone()["ls"]
    sig_riders = conn.execute(
        "SELECT COUNT(DISTINCT member_public_id) as cnt FROM member_routes WHERE ride_type='signature'"
    ).fetchone()["cnt"]
    grv_riders = conn.execute(
        "SELECT COUNT(DISTINCT member_public_id) as cnt FROM member_routes WHERE ride_type='gravel'"
    ).fetchone()["cnt"]
    riders = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_rider=1").fetchone()["cnt"]
    challengers = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_challenger=1").fetchone()["cnt"]
    volunteers = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_volunteer=1").fetchone()["cnt"]
    first_year = conn.execute("""SELECT COUNT(*) as cnt FROM members WHERE tags LIKE '%"1 year"%' AND is_rider=1""").fetchone()["cnt"]
    commit_row = conn.execute("""
        SELECT COALESCE(SUM(committed_amount),0) as total,
               COALESCE(SUM(CASE WHEN committed_high_roller=1 THEN committed_amount ELSE 0 END),0) as hr,
               COALESCE(SUM(CASE WHEN committed_high_roller=0 THEN committed_amount ELSE 0 END),0) as std
        FROM members WHERE team_id IS NOT NULL
    """).fetchone()
    return {
        "team_name": parent["name"] if parent else "Team Huntington Bank",
        "raised": parent["raised"] if parent else 0,
        "goal": parent["goal"] if parent else 0,
        "all_time_raised": parent["all_time_raised"] if parent else 0,
        "members_count": members,
        "donations_count": donations,
        "total_donated": total_donated,
        "cancer_survivors": survivors,
        "high_rollers": high_rollers,
        "signature_riders": sig_riders,
        "gravel_riders": grv_riders,
        "riders": riders,
        "challengers": challengers,
        "volunteers": volunteers,
        "total_committed": commit_row["total"],
        "hr_committed": commit_row["hr"],
        "std_committed": commit_row["std"],
        "general_peloton_funds": parent["general_peloton_funds"] if parent else 0,
        "first_year": first_year,
        "last_scraped": last_scraped,
    }


@app.route("/api/overview")
def api_overview():
    conn = get_db()
    data = _get_overview(conn)
    conn.close()
    return jsonify(data)


def _get_teams(conn):
    rows = conn.execute(
        "SELECT id, name, raised, COALESCE(goal_override, goal) as goal, all_time_raised, members_count "
        "FROM teams WHERE parent_id=? ORDER BY raised DESC",
        (PARENT_TEAM_ID,),
    ).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/teams")
def api_teams():
    conn = get_db()
    data = _get_teams(conn)
    conn.close()
    return jsonify(data)


def _get_fundraising_timeline(conn):
    rows = conn.execute("""
        SELECT DATE(date) as day, COUNT(*) as cnt, SUM(amount) as total
        FROM donations
        GROUP BY DATE(date)
        ORDER BY day
    """).fetchall()
    cumulative = 0
    result = []
    for r in rows:
        cumulative += r["total"]
        result.append({
            "date": r["day"],
            "daily_count": r["cnt"],
            "daily_amount": round(r["total"], 2),
            "cumulative": round(cumulative, 2),
        })
    return result


@app.route("/api/fundraising-timeline")
def api_fundraising_timeline():
    """Cumulative donations over time."""
    conn = get_db()
    data = _get_fundraising_timeline(conn)
    conn.close()
    return jsonify(data)


@app.route("/api/snapshots")
def api_snapshots():
    """Historical daily snapshots for tracking fundraising growth over time."""
    conn = get_db()
    rows = conn.execute("""
        SELECT snapshot_date, team_id, raised, goal, all_time_raised,
               members_count, donations_count, total_donated
        FROM daily_snapshots
        WHERE team_id=?
        ORDER BY snapshot_date
    """, (PARENT_TEAM_ID,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/snapshots/teams")
def api_snapshots_teams():
    """Historical daily snapshots per sub-team."""
    conn = get_db()
    rows = conn.execute("""
        SELECT s.snapshot_date, s.team_id, t.name as team_name,
               s.raised, s.all_time_raised, s.members_count
        FROM daily_snapshots s
        JOIN teams t ON s.team_id=t.id
        WHERE s.team_id != ?
        ORDER BY s.snapshot_date, s.raised DESC
    """, (PARENT_TEAM_ID,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


def _get_top_fundraisers(conn):
    rows = conn.execute("""
        SELECT m.public_id, m.name, m.raised, m.all_time_raised,
               m.is_cancer_survivor, m.tags, t.name as team_name,
               m.is_rider, m.is_challenger, m.ride_type,
               m.committed_amount, m.personal_goal, m.committed_high_roller
        FROM members m LEFT JOIN teams t ON m.team_id=t.id
        ORDER BY m.raised DESC LIMIT 25
    """).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/top-fundraisers")
def api_top_fundraisers():
    conn = get_db()
    data = _get_top_fundraisers(conn)
    conn.close()
    return jsonify(data)


def _get_team_breakdown(conn):
    # Mutually exclusive classification: rider > challenger > volunteer > registered only.
    # Untyped members with a route count as riders.
    rows = conn.execute("""
        SELECT t.name,
               SUM(CASE WHEN m.is_rider=1 OR (m.is_rider=0 AND m.is_challenger=0 AND m.is_volunteer=0 AND mr.member_public_id IS NOT NULL) THEN 1 ELSE 0 END) as riders,
               SUM(CASE WHEN m.is_challenger=1 AND m.is_rider=0 THEN 1 ELSE 0 END) as challengers,
               SUM(CASE WHEN m.is_volunteer=1 AND m.is_rider=0 AND m.is_challenger=0 THEN 1 ELSE 0 END) as volunteers,
               COUNT(DISTINCT m.public_id) as total,
               SUM(m.committed_amount) as total_committed,
               SUM(m.raised) as total_raised,
               SUM(m.all_time_raised) as total_all_time,
               SUM(m.committed_high_roller) as high_rollers,
               SUM(m.is_cancer_survivor) as survivors,
               SUM(CASE WHEN m.committed_high_roller=1 THEN m.committed_amount ELSE 0 END) as hr_committed,
               SUM(CASE WHEN m.committed_high_roller=0 THEN m.committed_amount ELSE 0 END) as std_committed,
               SUM(CASE WHEN m.tags LIKE '%"1 year"%' AND m.is_rider=1 THEN 1 ELSE 0 END) as first_year
        FROM members m
        JOIN teams t ON m.team_id=t.id
        LEFT JOIN (SELECT DISTINCT member_public_id FROM member_routes) mr
            ON m.public_id=mr.member_public_id
        GROUP BY t.name
        ORDER BY SUM(m.committed_amount) DESC
    """).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/team-breakdown")
def api_team_breakdown():
    """Team breakdown with participant types and commitment subtotals."""
    conn = get_db()
    data = _get_team_breakdown(conn)
    conn.close()
    return jsonify(data)


def _get_commitment_tiers(conn):
    rows = conn.execute("""
        SELECT committed_amount as tier,
               COUNT(*) as count,
               SUM(is_rider) as riders,
               SUM(is_challenger) as challengers,
               SUM(raised) as total_raised,
               SUM(all_time_raised) as total_all_time,
               SUM(committed_high_roller) as high_rollers
        FROM members
        GROUP BY committed_amount
        ORDER BY committed_amount
    """).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/commitment-tiers")
def api_commitment_tiers():
    """Members grouped by commitment amount tier."""
    conn = get_db()
    data = _get_commitment_tiers(conn)
    conn.close()
    return jsonify(data)


def _get_ride_type_breakdown(conn):
    rows = conn.execute("""
        SELECT
            CASE
                WHEN ride_type LIKE '%gravel%' AND ride_type LIKE '%signature%' THEN 'Both'
                WHEN ride_type = 'signature' THEN 'Signature'
                WHEN ride_type = 'gravel' THEN 'Gravel'
                ELSE 'None/Challenger'
            END as ride_category,
            COUNT(*) as count,
            SUM(is_rider) as riders,
            SUM(is_challenger) as challengers,
            SUM(committed_amount) as total_committed,
            SUM(raised) as total_raised
        FROM members
        GROUP BY ride_category
        ORDER BY count DESC
    """).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/ride-type-breakdown")
def api_ride_type_breakdown():
    """Members grouped by ride type (signature, gravel, both, none)."""
    conn = get_db()
    data = _get_ride_type_breakdown(conn)
    conn.close()
    return jsonify(data)


def _get_routes(conn):
    rows = conn.execute("""
        SELECT r.id, r.name, r.distance, r.fundraising_commitment,
               r.capacity, r.starting_city, r.ending_city, r.image_url,
               ri.name as ride_name, ri.type as ride_type,
               ri.ride_weekend_start, ri.ride_weekend_end,
               COALESCE(mr.signups, 0) as signups
        FROM routes r
        JOIN rides ri ON r.ride_id=ri.id
        LEFT JOIN (
            SELECT route_id, COUNT(*) as signups FROM member_routes GROUP BY route_id
        ) mr ON mr.route_id=r.id
        ORDER BY ri.type, r.fundraising_commitment, r.distance
    """).fetchall()

    member_funds = conn.execute("""
        SELECT mr.route_id,
               SUM(m.raised / member_route_count) as route_raised,
               SUM(m.committed_amount / member_route_count) as route_committed
        FROM member_routes mr
        JOIN members m ON m.public_id = mr.member_public_id
        JOIN (
            SELECT member_public_id, COUNT(*) as member_route_count
            FROM member_routes GROUP BY member_public_id
        ) mc ON mc.member_public_id = mr.member_public_id
        GROUP BY mr.route_id
    """).fetchall()
    funds_by_route = {r["route_id"]: (r["route_raised"], r["route_committed"]) for r in member_funds}

    ride_totals = {}
    for rt_key in ("signature", "gravel"):
        row = conn.execute(
            "SELECT COUNT(DISTINCT member_public_id) as cnt FROM member_routes WHERE ride_type=?",
            (rt_key,),
        ).fetchone()
        ride_totals[rt_key] = row["cnt"]

    result = []
    for r in rows:
        d = dict(r)
        d["ride_total_signups"] = ride_totals.get(d["ride_type"], 0)
        raised, committed = funds_by_route.get(d["id"], (0, 0))
        d["route_raised"] = round(raised or 0, 2)
        d["route_committed"] = round(committed or 0, 2)
        result.append(d)
    return result


@app.route("/api/routes")
def api_routes():
    """All routes with actual signups and fundraising totals (split across routes)."""
    conn = get_db()
    data = _get_routes(conn)
    conn.close()
    return jsonify(data)


@app.route("/api/route-members/<route_id>")
def api_route_members(route_id):
    """Members signed up for a specific route, with years riding."""
    conn = get_db()
    rows = conn.execute("""
        SELECT m.public_id, m.name, m.raised, m.committed_amount,
               m.tags, m.is_cancer_survivor, m.profile_image_url
        FROM member_routes mr
        JOIN members m ON m.public_id = mr.member_public_id
        WHERE mr.route_id = ?
        ORDER BY m.raised DESC
    """, (route_id,)).fetchall()
    conn.close()

    import json as _json
    result = []
    for r in rows:
        d = dict(r)
        tags = _json.loads(d.get("tags") or "[]")
        year_tags = [t for t in tags if "year" in t.lower()]
        years = 0
        if year_tags:
            try:
                years = int(year_tags[0].split()[0])
            except (ValueError, IndexError):
                pass
        d["years"] = years
        d["is_first_year"] = 1 if years <= 1 else 0
        result.append(d)
    return jsonify(result)


def _get_signup_timeline(conn):
    rows = conn.execute("""
        SELECT snapshot_date, signature_riders, gravel_riders, members_count, raised,
               riders_count, challengers_count, volunteers_count
        FROM daily_snapshots
        WHERE team_id = ?
        ORDER BY snapshot_date
    """, (PARENT_TEAM_ID,)).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/signup-timeline")
def api_signup_timeline():
    """Participant signup counts over time from daily snapshots."""
    conn = get_db()
    data = _get_signup_timeline(conn)
    conn.close()
    return jsonify(data)


def _get_events(conn):
    rows = conn.execute("SELECT * FROM events ORDER BY year DESC").fetchall()
    return [dict(r) for r in rows]


@app.route("/api/events")
def api_events():
    conn = get_db()
    data = _get_events(conn)
    conn.close()
    return jsonify(data)


def _get_top_donors(conn):
    rows = conn.execute("""
        SELECT
            COALESCE(NULLIF(donor_name, ''), recognition_name, 'Anonymous') as donor,
            SUM(amount) as total,
            COUNT(*) as cnt,
            COUNT(DISTINCT recipient_public_id) as recipient_count,
            MAX(date) as last_donation,
            MIN(date) as first_donation,
            CASE
                WHEN COALESCE(NULLIF(donor_name, ''), recognition_name, 'Anonymous') = 'Anonymous'
                    THEN NULL
                ELSE GROUP_CONCAT(DISTINCT CASE
                    WHEN recognition_name IS NOT NULL
                     AND recognition_name != ''
                     AND recognition_name != COALESCE(donor_name, '')
                    THEN recognition_name END)
            END as affiliations
        FROM donations
        GROUP BY COALESCE(NULLIF(donor_name, ''), recognition_name, 'Anonymous')
        ORDER BY SUM(amount) DESC
    """).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/top-donors")
def api_top_donors():
    conn = get_db()
    data = _get_top_donors(conn)
    conn.close()
    return jsonify(data)


def _get_members(conn):
    rows = conn.execute("""
        SELECT m.public_id, m.name, m.raised, m.all_time_raised,
               m.is_captain, m.is_cancer_survivor, m.commitment_amount,
               m.fundraising_goal, m.registration_types, m.tags,
               t.name as team_name,
               m.is_rider, m.is_challenger, m.is_volunteer,
               m.ride_type, m.committed_amount, m.personal_goal,
               m.committed_high_roller
        FROM members m LEFT JOIN teams t ON m.team_id=t.id
        ORDER BY m.raised DESC
    """).fetchall()
    route_rows = conn.execute("""
        SELECT member_public_id, GROUP_CONCAT(route_name, ', ') as route_names
        FROM member_routes
        GROUP BY member_public_id
    """).fetchall()
    route_map = {r["member_public_id"]: r["route_names"] for r in route_rows}
    result = []
    for r in rows:
        d = dict(r)
        d["route_names"] = route_map.get(d["public_id"], "")
        result.append(d)
    return result


@app.route("/api/members")
def api_members():
    conn = get_db()
    data = _get_members(conn)
    conn.close()
    return jsonify(data)


def _get_donations(conn):
    rows = conn.execute("""
        SELECT d.opportunity_id, d.recipient_public_id, d.amount, d.date,
               d.anonymous_to_public, d.recognition_name, d.donor_name,
               m.name as recipient_name, t.name as team_name
        FROM donations d
        LEFT JOIN members m ON d.recipient_public_id=m.public_id
        LEFT JOIN teams t ON m.team_id=t.id
        ORDER BY d.date DESC
    """).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/donations")
def api_donations():
    conn = get_db()
    data = _get_donations(conn)
    conn.close()
    return jsonify(data)


def _get_company_donations(conn):
    rows = conn.execute("""
        SELECT recognition_name as company,
               SUM(amount) as total,
               COUNT(*) as donation_count,
               COUNT(DISTINCT donor_name) as donor_count,
               COUNT(DISTINCT recipient_public_id) as recipient_count,
               GROUP_CONCAT(DISTINCT donor_name) as donors
        FROM donations
        WHERE recognition_name IS NOT NULL
          AND donor_name IS NOT NULL
          AND recognition_name != donor_name
          AND anonymous_to_public = 0
        GROUP BY recognition_name
        ORDER BY SUM(amount) DESC
    """).fetchall()
    return [dict(r) for r in rows]


@app.route("/api/companies")
def api_companies():
    conn = get_db()
    data = _get_company_donations(conn)
    conn.close()
    return jsonify(data)


# ── Ticker (Pelotonia-wide stats) ────────────────────────────────────────

TICKER_CACHE_PATH = SCRIPT_DIR / ".ticker_cache.json"

def _get_ticker():
    try:
        req = urllib.request.Request(
            "https://pelotonia-p3-middleware-production.azurewebsites.net/api/ticker",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                raw = json.loads(resp.read())
                data = {
                    "pelotonia_total_raised": raw.get("currentYearRaised", 0),
                    "pelotonia_member_count": raw.get("totalParticipants", 0),
                    "pelotonia_all_time_raised": raw.get("allTimeRaised", 0),
                }
                try:
                    with open(TICKER_CACHE_PATH, "w") as f:
                        json.dump(data, f)
                except Exception:
                    pass
                return data
    except Exception as e:
        app.logger.warning("Ticker API failed: %s", e)
    # Fall back to cached value
    try:
        with open(TICKER_CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        pass
    return {}


def _get_subteam_snapshots(conn):
    """Recent daily snapshots for each sub-team (last 8 days for weekly delta)."""
    cutoff = (__import__('datetime').datetime.now() - __import__('datetime').timedelta(days=8)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT ds.snapshot_date, t.name, ds.raised, ds.members_count
        FROM daily_snapshots ds
        JOIN teams t ON ds.team_id=t.id
        WHERE t.parent_id=? AND ds.snapshot_date>=?
        ORDER BY ds.snapshot_date
    """, (PARENT_TEAM_ID, cutoff)).fetchall()
    return [dict(r) for r in rows]


# ── Pelotonia Kids (PledgeIt) helpers ──────────────────────────────────

def _get_kids_overview(conn):
    """Latest row from kids_snapshots (aggregate-only, no PII)."""
    try:
        row = conn.execute("""
            SELECT snapshot_date, campaign_id, fundraiser_count,
                   estimated_amount_raised, monetary_goal, team_count, last_scraped
            FROM kids_snapshots
            ORDER BY snapshot_date DESC
            LIMIT 1
        """).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return dict(row)


def _get_kids_snapshots(conn):
    """All kids_snapshots rows ordered by date (for trend charts)."""
    try:
        rows = conn.execute("""
            SELECT snapshot_date, fundraiser_count, estimated_amount_raised,
                   monetary_goal, team_count
            FROM kids_snapshots
            ORDER BY snapshot_date
        """).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


# ── Organization Leaderboard helpers ───────────────────────────────────────

def _get_org_leaderboard(conn):
    """Latest org_snapshots rows sorted by raised DESC."""
    try:
        latest = conn.execute("SELECT MAX(snapshot_date) FROM org_snapshots").fetchone()[0]
    except Exception:
        return []
    if not latest:
        return []
    rows = conn.execute("""
        SELECT team_id, name, members_count, sub_team_count, raised, goal,
               all_time_raised, last_scraped
        FROM org_snapshots
        WHERE snapshot_date = ?
        ORDER BY raised DESC
    """, (latest,)).fetchall()
    return [dict(r) for r in rows]


def _get_org_snapshots(conn):
    """All org_snapshots rows ordered by date (for trend charts)."""
    try:
        rows = conn.execute("""
            SELECT snapshot_date, team_id, name, members_count, sub_team_count,
                   raised, goal, all_time_raised
            FROM org_snapshots
            ORDER BY snapshot_date, raised DESC
        """).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


# ── Bundle endpoint (single fetch for the dashboard) ─────────────────────

def _build_bundle():
    conn = get_db()
    bundle = {
        "overview": _get_overview(conn),
        "teams": _get_teams(conn),
        "timeline": _get_fundraising_timeline(conn),
        "fundraisers": _get_top_fundraisers(conn),
        "donors": _get_top_donors(conn),
        "members": _get_members(conn),
        "donations": _get_donations(conn),
        "teamBreakdown": _get_team_breakdown(conn),
        "commitTiers": _get_commitment_tiers(conn),
        "rideTypes": _get_ride_type_breakdown(conn),
        "routes": _get_routes(conn),
        "signupTimeline": _get_signup_timeline(conn),
        "events": _get_events(conn),
        "companies": _get_company_donations(conn),
        "ticker": _get_ticker(),
        "subteamSnapshots": _get_subteam_snapshots(conn),
        "kidsOverview": _get_kids_overview(conn),
        "kidsSnapshots": _get_kids_snapshots(conn),
        "orgLeaderboard": _get_org_leaderboard(conn),
        "orgSnapshots": _get_org_snapshots(conn),
    }
    conn.close()
    return bundle


@app.route("/api/bundle")
def api_bundle():
    """All dashboard data in one response. Cached until DB file mtime changes."""
    try:
        current_mtime = DB_PATH.stat().st_mtime
    except OSError:
        return jsonify({"error": "database not found"}), 500

    if _cache["data"] is not None and _cache["db_mtime"] == current_mtime:
        return Response(_cache["data"], mimetype="application/json")

    bundle = _build_bundle()
    raw = json.dumps(bundle)
    _cache["data"] = raw
    _cache["db_mtime"] = current_mtime
    return Response(raw, mimetype="application/json")


# ── Pelotonia Kids API endpoints ───────────────────────────────────────────

@app.route("/api/kids-overview")
def api_kids_overview():
    conn = get_db()
    data = _get_kids_overview(conn)
    conn.close()
    return jsonify(data)


@app.route("/api/kids-snapshots")
def api_kids_snapshots():
    conn = get_db()
    data = _get_kids_snapshots(conn)
    conn.close()
    return jsonify(data)


# ── Organization Leaderboard API endpoints ─────────────────────────────────

@app.route("/api/org-leaderboard")
def api_org_leaderboard():
    conn = get_db()
    data = _get_org_leaderboard(conn)
    conn.close()
    return jsonify(data)


@app.route("/api/org-snapshots")
def api_org_snapshots():
    conn = get_db()
    data = _get_org_snapshots(conn)
    conn.close()
    return jsonify(data)


# ── React Frontend (SPA) ──────────────────────────────────────────────────

FRONTEND_DIR = SCRIPT_DIR.parent / "frontend" / "dist"


@app.route("/")
@app.route("/<path:path>")
def serve_frontend(path=""):
    """Serve React SPA — try static file first, fall back to index.html."""
    file_path = FRONTEND_DIR / path
    if path and file_path.is_file():
        return send_from_directory(str(FRONTEND_DIR), path)
    return send_from_directory(str(FRONTEND_DIR), "index.html")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pelotonia Dashboard Server")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    print(f"\n  Pelotonia Dashboard → http://localhost:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=False)
