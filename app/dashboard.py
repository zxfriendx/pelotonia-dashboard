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

from flask import Flask, jsonify, Response

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
    first_year = conn.execute("""SELECT COUNT(*) as cnt FROM members WHERE tags LIKE '%"1 year"%'""").fetchone()["cnt"]
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
               SUM(CASE WHEN m.tags LIKE '%"1 year"%' THEN 1 ELSE 0 END) as first_year
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
        SELECT snapshot_date, signature_riders, gravel_riders, members_count, raised
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
        SELECT COALESCE(recognition_name, donor_name, 'Anonymous') as donor,
               SUM(amount) as total, COUNT(*) as cnt
        FROM donations
        GROUP BY COALESCE(recognition_name, donor_name)
        ORDER BY SUM(amount) DESC LIMIT 25
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

def _get_ticker():
    try:
        req = urllib.request.Request(
            "https://pelotonia-p3-middleware-production.azurewebsites.net/api/ticker",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return json.loads(resp.read())
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


# ── HTML Dashboard ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return Response(DASHBOARD_HTML, mimetype="text/html")


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Team Huntington — Pelotonia Dashboard</title>
<!-- Google Analytics -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2"></script>
<style>
  :root {
    --green: #44D62C;
    --forest: #00471F;
    --black: #0E1411;
    --tread: #29322D;
    --white: #FFFFFF;
    --gray-bg: #f5f6f7;
    --card-shadow: 0 2px 8px rgba(0,0,0,.08);
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--gray-bg); color: var(--black); line-height: 1.5; }

  /* Header */
  header { background: var(--forest); color: var(--white); padding: 20px 24px;
           display: flex; align-items: center; gap: 16px; }
  header h1 { font-size: 22px; font-weight: 700; }
  header .badge { background: var(--green); color: var(--forest); padding: 3px 10px;
                  border-radius: 12px; font-size: 12px; font-weight: 700; }
  header .updated { margin-left: auto; font-size: 12px; opacity: .7; }

  /* KPI strip */
  .kpi-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
               gap: 12px; padding: 16px 24px; }
  .kpi { background: var(--white); border-radius: 8px; padding: 16px;
         box-shadow: var(--card-shadow); text-align: center; }
  .kpi .value { font-size: 28px; font-weight: 800; color: var(--forest); }
  .kpi .label { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: .5px; }

  /* Flip KPI cards */
  .kpi-flip { cursor: pointer; perspective: 600px; position: relative; }
  .kpi-flip .kpi-inner {
    position: relative; width: 100%; min-height: 72px;
    transition: transform 0.5s; transform-style: preserve-3d;
  }
  .kpi-flip.flipped .kpi-inner { transform: rotateY(180deg); }
  .kpi-front, .kpi-back {
    position: absolute; inset: 0; backface-visibility: hidden;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
  }
  .kpi-back { transform: rotateY(180deg); }
  .kpi-back .label { font-size: 11px; }
  .kpi-share { font-size: 11px; color: var(--green); font-weight: 700; margin-top: 2px; }
  .kpi-flip-hint { position: absolute; top: 4px; right: 6px; font-size: 9px; color: #bbb; pointer-events: none; }

  /* CSV export button */
  .btn-export { padding:6px 14px; border:1px solid #ddd; border-radius:6px; background:#fff;
                cursor:pointer; font-size:12px; font-weight:600; color:#555; white-space:nowrap;
                transition: all .15s; }
  .btn-export:hover { background:var(--forest); color:#fff; border-color:var(--forest); }

  /* Progress bar */
  .progress-wrap { padding: 0 24px 8px; }
  .progress-outer { background: #e0e0e0; border-radius: 8px; height: 24px; overflow: hidden; position: relative; }
  .progress-inner { background: linear-gradient(90deg, var(--green), #44D62C); height: 100%;
                    border-radius: 8px; transition: width .6s; }
  .progress-label { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
                    font-size: 12px; font-weight: 700; color: var(--forest); }

  /* Layout */
  .grid { display: grid; gap: 16px; padding: 16px 24px; }
  .grid-2 { grid-template-columns: 1fr 1fr; }
  .grid-3 { grid-template-columns: 1fr 1fr 1fr; }
  @media (max-width: 900px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }

  .card { background: var(--white); border-radius: 8px; padding: 20px;
          box-shadow: var(--card-shadow); min-width: 0; overflow: hidden; }
  .card h2 { font-size: 16px; font-weight: 700; color: var(--forest); margin-bottom: 12px;
             border-bottom: 2px solid var(--green); padding-bottom: 6px; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; font-weight: 600; color: var(--forest); padding: 6px 8px;
       border-bottom: 2px solid var(--green); font-size: 11px; text-transform: uppercase; }
  td { padding: 6px 8px; border-bottom: 1px solid #eee; }
  tr:hover td { background: #f0faf0; }
  .text-right { text-align: right; }
  .text-center { text-align: center; }
  .badge-tag { display: inline-block; background: #e8f5e9; color: var(--forest);
               padding: 1px 6px; border-radius: 4px; font-size: 11px; margin: 1px; }
  .badge-survivor { background: #fff3e0; color: #e65100; }
  .badge-hr { background: #0E1411; color: #fff; }

  /* Tabs */
  .tabs { display: flex; gap: 0; border-bottom: 2px solid #ddd; margin-bottom: 16px; }
  .tab { padding: 8px 16px; cursor: pointer; font-size: 13px; font-weight: 600;
         color: #888; border-bottom: 2px solid transparent; margin-bottom: -2px; }
  .tab.active { color: var(--forest); border-bottom-color: var(--green); }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* Search */
  .search-bar { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px;
                font-size: 14px; margin-bottom: 12px; }
  .search-bar:focus { outline: none; border-color: var(--green); box-shadow: 0 0 0 2px rgba(68,214,44,.2); }

  /* Chart container */
  .chart-container { position: relative; height: 300px; max-width: 100%; }

  /* Pelotonia goals panel — matches brand infographic */
  .goals-panel { background: #0E1411;
    border-radius: 12px; padding: 32px 40px; position: relative; overflow: visible; }
  .goals-title { font-size: 30px; font-weight: 900; color: #fff; letter-spacing: 3px;
    margin-bottom: 28px; position: relative; z-index: 1; }
  .goals-title sup { font-size: 11px; vertical-align: super; }
  .goals-asof { float:right; font-size:12px; font-weight:400; letter-spacing:.5px;
    color:rgba(255,255,255,.35); padding-top:10px; }
  .goal-row { display: grid; grid-template-columns: 200px 1fr 120px;
    align-items: center; margin-bottom: 22px; position: relative; z-index: 1; gap: 16px; overflow: visible; }
  .goal-row-label { color: var(--green); font-weight: 800; font-size: 14px;
    text-transform: uppercase; letter-spacing: 1.5px; text-align: right; white-space: nowrap; }
  .goal-bar-wrap { position: relative; height: 40px; display: flex; align-items: center; overflow: visible; margin-left: 40px; }
  .goal-bar-line { position: absolute; top: 50%; left: 0; right: 0; height: 2px;
    background: rgba(68,214,44,.25); transform: translateY(-50%); }
  .goal-bar-fill-line { position: absolute; top: 50%; left: 0; height: 2px;
    background: var(--green); transform: translateY(-50%); transition: width 1.2s ease-out; z-index: 1; }
  .goal-arrow-wrap { position: absolute; top: 50%; transform: translate(-36px,-50%);
    transition: left 1.2s ease-out; display: flex; align-items: center; gap: 6px;
    white-space: nowrap; z-index: 2; }
  .goal-arrow-wrap img { display: block; width: 36px; height: auto;
    filter: drop-shadow(0 0 6px rgba(68,214,44,.4)); }
  .goal-current-val { color: #fff; font-weight: 800; font-size: 16px;
    text-shadow: 0 0 8px rgba(68,214,44,.5); letter-spacing: .5px; }
  .goal-target { color: var(--green); font-weight: 700; font-size: 18px;
    text-align: right; letter-spacing: 1px; cursor: pointer; white-space: nowrap; }
  .goals-scale-row { margin-bottom: 0 !important; border-top: 1px solid rgba(68,214,44,.15);
    padding-top: 12px; margin-top: 4px; }
  .goals-pct-label { color: rgba(68,214,44,.4) !important; font-size: 11px !important;
    font-weight: 600 !important; letter-spacing: 1px !important; }
  .goals-scale-ticks { display: flex; justify-content: space-between; color: rgba(68,214,44,.4);
    font-size: 11px; font-weight: 600; letter-spacing: 1px; margin-left: 40px; }
  .goals-scale-goal-label { color: rgba(68,214,44,.4); font-weight: 800; font-size: 11px;
    text-align: right; letter-spacing: 1px; }
  @media (max-width: 768px) {
    .goals-panel { padding: 20px 16px; }
    .goal-row { grid-template-columns: 120px 1fr 80px; gap: 8px; }
    .goal-row-label { font-size: 11px; letter-spacing: 1px; }
    .goal-target { font-size: 14px; }
    .goals-title { font-size: 22px; }
  }

  /* Pagination */
  .pagination { display:flex; align-items:center; justify-content:space-between; padding:12px 0 4px;
    font-size:13px; color:#666; border-top:1px solid #eee; margin-top:8px; }
  .pagination button { padding:6px 14px; border:1px solid #ddd; border-radius:6px; background:#fff;
    cursor:pointer; font-size:13px; color:var(--forest); transition:all .15s; }
  .pagination button:hover:not(:disabled) { background:var(--green); color:#fff; border-color:var(--green); }
  .pagination button:disabled { opacity:.4; cursor:default; }
  .pagination .page-info { font-weight:600; }
  .pagination .page-size-wrap { display:flex; align-items:center; gap:6px; }
  .pagination .page-size-wrap select { padding:4px 8px; border:1px solid #ddd; border-radius:4px;
    font-size:12px; background:#fff; }

  /* Footer */
  footer { text-align: center; padding: 20px; font-size: 12px; color: #888; }

  /* Route drill-down modal */
  .modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%;
                   background:rgba(0,0,0,.5); z-index:1000; justify-content:center; align-items:center; }
  .modal-overlay.active { display:flex; }
  .modal { background:#fff; border-radius:12px; padding:24px; max-width:700px; width:90%;
           max-height:80vh; overflow-y:auto; box-shadow:0 8px 32px rgba(0,0,0,.3); }
  .modal h2 { margin:0 0 16px; font-size:18px; color:var(--forest); }
  .modal .close-btn { float:right; cursor:pointer; font-size:20px; color:#888; border:none;
                      background:none; padding:0 4px; }
  .modal .close-btn:hover { color:#333; }
  .first-year { background: #fff8e1 !important; }
  .badge-first-year { display:inline-block; background:#ff9800; color:#fff;
                      padding:1px 6px; border-radius:4px; font-size:10px; font-weight:700;
                      margin-left:4px; text-transform:uppercase; }
  tr.route-row { cursor:pointer; }
  tr.route-row:hover td { background: #e8f5e9; }
  .totals-row td { font-weight:700; border-top:2px solid var(--green); background:#f5f5f5 !important; }
  .clickable-row { cursor:pointer; }
  .clickable-row:hover td { background:#e8f5e9 !important; }
  .highlight-row td { background:#c8e6c9 !important; transition: background 2s ease; }
  @keyframes fadeHighlight { from { background:#c8e6c9; } to { background:transparent; } }

  /* ── Infographic cards (Concept B — bold gradient bars) ── */
  .thermo-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; padding: 24px; }
  .thermo-card {
    background: var(--white); border-radius: 14px; padding: 24px; box-shadow: var(--card-shadow);
    position: relative; overflow: hidden; transition: transform 0.2s;
  }
  .thermo-card:hover { transform: translateY(-2px); }
  .thermo-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--forest), var(--green));
  }
  .thermo-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
  .thermo-label { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #888; }
  .pct-badge {
    font-size: 13px; font-weight: 800; padding: 3px 10px; border-radius: 20px;
    background: rgba(68,214,44,0.1); color: var(--forest);
  }
  .thermo-value { font-size: 36px; font-weight: 800; color: var(--forest); line-height: 1; font-variant-numeric: tabular-nums; }
  .thermo-goal { font-size: 13px; color: #aaa; margin-top: 6px; }
  .thermo-goal strong { color: #666; }
  /* Thick progress bar */
  .thermo-bar-wrap { margin-top: 18px; }
  .thermo-bar-bg { height: 14px; border-radius: 7px; background: #e8ece9; overflow: hidden; position: relative; }
  .thermo-bar-fill {
    height: 100%; border-radius: 7px;
    background: linear-gradient(90deg, var(--forest) 0%, var(--green) 100%);
    transition: width 1.8s cubic-bezier(0.25, 0.46, 0.45, 0.94); position: relative;
  }
  .thermo-bar-fill::after {
    content: ''; position: absolute; top: 0; left: -150%; width: 150%; height: 100%;
    background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%);
    animation: ig-shimmer 3s 2s infinite;
  }
  @keyframes ig-shimmer { to { left: 150%; } }
  /* Milestone markers */
  .thermo-milestones { position: relative; height: 18px; margin-top: 4px; }
  .thermo-milestone {
    position: absolute; top: 0; font-size: 10px; color: #bbb; text-align: center;
    transform: translateX(-50%);
  }
  .thermo-milestone::before { content: ''; display: block; width: 1px; height: 5px; background: #ddd; margin: 0 auto 2px; }
  /* Stat chips row */
  .stat-chips { display: flex; gap: 4px; margin-top: 14px; }
  .stat-chip { flex: 1; text-align: center; padding: 8px 4px; background: #f7f8f9; border-radius: 8px; min-width: 0; }
  .stat-chip-val { font-size: 15px; font-weight: 800; color: var(--forest); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .stat-chip-label { font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.3px; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* Pace indicator */
  .pace-row { margin-top: 12px; font-size: 12px; color: #888; display: flex; align-items: center; gap: 6px; }
  .pace-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .pace-ahead { background: var(--green); }
  .pace-behind { background: #e74c3c; }
  /* Target edit */
  /* Controls */
  .infographic-controls { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; }
  .infographic-select { padding: 6px 12px; border: 2px solid var(--forest); border-radius: 6px;
                        font-size: 14px; font-weight: 600; color: var(--forest); background: var(--white); cursor: pointer; }
  .infographic-select:focus { outline: none; border-color: var(--green); }
  /* Summary cards */
  .infographic-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                         gap: 16px; padding: 0 24px 24px; }
  .summary-card { background: var(--white); border-radius: 10px; padding: 16px;
                  box-shadow: var(--card-shadow); text-align: center; }
  .summary-value { font-size: 26px; font-weight: 800; color: var(--forest); }
  .summary-label { font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: .5px; margin-top: 4px; }

  /* Mini progress bar for goals table */
  .mini-bar { display:inline-block; width:50px; height:8px; background:#e0e0e0; border-radius:4px;
              vertical-align:middle; margin-left:4px; overflow:hidden; }
  .mini-bar-fill { display:block; height:100%; background:var(--green); border-radius:4px; transition:width .4s; }
  .goal-cell { white-space:nowrap; }
  .goal-over { color: var(--green); font-weight:700; }
  .goal-under { color: #888; }

  /* ── Tablet breakpoint (768px) — scrollable tab bar ── */
  @media (max-width: 768px) {
    .tabs { overflow-x: auto; -webkit-overflow-scrolling: touch;
            scroll-snap-type: x mandatory; scrollbar-width: none; }
    .tabs::-webkit-scrollbar { display: none; }
    .tab { flex-shrink: 0; scroll-snap-align: start; }
  }

  /* ── Mobile breakpoint (600px) — full mobile treatment ── */
  @media (max-width: 600px) {
    /* Header: stack title / badge+timestamp */
    header { flex-wrap: wrap; padding: 16px; gap: 8px; }
    header h1 { width: 100%; font-size: 18px; }
    header .updated { margin-left: auto; }

    /* KPI strip: 2-column grid */
    .kpi-strip { grid-template-columns: repeat(2, 1fr); gap: 8px; padding: 12px 16px; }
    .kpi { padding: 10px; }
    .kpi .value { font-size: 20px; }
    .kpi .label { font-size: 10px; }
    .kpi-flip .kpi-inner { min-height: 60px; }
    .kpi-back .value { font-size: 18px; }

    /* Tabs: bigger touch targets */
    .tabs-wrap { padding: 0 16px !important; }
    .tab { min-height: 44px; display: flex; align-items: center; }

    /* Charts: shorter on mobile */
    [style*="height:450px"] { height: 300px !important; }
    .chart-container { height: 250px; }

    /* Tables/cards: horizontal scroll for wide tables */
    .card { overflow-x: auto; }
    td, th { padding: 8px; }

    /* Search: prevent iOS Safari zoom on focus */
    .search-bar { font-size: 16px; }

    /* Modal: bottom-sheet pattern */
    .modal-overlay { align-items: flex-end; }
    .modal { max-width: 100%; width: 100%; border-radius: 12px 12px 0 0;
             max-height: 85vh; padding: 20px 16px; }
    .modal .close-btn { font-size: 24px; min-width: 44px; min-height: 44px;
                        display: flex; align-items: center; justify-content: center; }

    /* Touch targets: clickable rows, buttons, selects */
    tr[onclick], tr[style*="cursor:pointer"] { padding: 10px 0; }
    button, select { min-height: 44px; }

    /* Padding: reclaim horizontal space */
    .grid { padding: 12px 16px; }
    .progress-wrap { padding: 0 16px 8px; }

    /* Infographics: 2-column, stacked controls */
    .thermo-grid { grid-template-columns: repeat(2, 1fr); gap: 16px; padding: 16px; }
    .thermo-value { font-size: 28px; }
    .stat-chips { flex-wrap: wrap; }
    .stat-chip { min-width: 60px; }
    .infographic-controls { flex-direction: column; gap: 12px; align-items: stretch; padding: 12px 16px; }
    .infographic-summary { padding: 0 16px 16px; }

    /* Route big numbers */
    [style*="font-size:48px"] { font-size: 36px !important; }
  }
  /* Data Guide button & modal */
  #guide-btn:hover { border-color:var(--green); color:var(--green); }
  #guide-modal .modal { max-width:800px; }
  #guide-modal .modal h3 { font-size:15px; font-weight:700; color:var(--forest); margin:20px 0 8px;
    border-bottom:1px solid var(--green); padding-bottom:4px; }
  #guide-modal .modal h3:first-child { margin-top:0; }
  #guide-modal .modal p, #guide-modal .modal li { font-size:13px; line-height:1.6; color:#333; }
  #guide-modal .modal ul { margin:4px 0 12px 20px; }
  #guide-modal .modal code { background:#f0f0f0; padding:1px 4px; border-radius:3px; font-size:12px; }
  #guide-modal .modal .def-table { width:100%; font-size:12px; margin:8px 0 12px; }
  #guide-modal .modal .def-table td { padding:4px 8px; vertical-align:top; border-bottom:1px solid #eee; }
  #guide-modal .modal .def-table td:first-child { font-weight:600; white-space:nowrap; color:var(--forest); width:180px; }


</style>
</head>
<body id="app-body">

<header>
  <h1>Team Huntington Bank</h1>
  <span class="badge">PELOTONIA 2026</span>
  <button id="guide-btn" style="background:none;border:1px solid rgba(255,255,255,.3);color:#fff;padding:4px 10px;border-radius:6px;font-size:11px;cursor:pointer;white-space:nowrap;" title="Data reference guide">? Data Guide</button>
  <span class="updated" id="last-updated"></span>
</header>

<!-- KPI strip -->
<div class="kpi-strip">
  <div class="kpi kpi-flip" onclick="this.classList.toggle('flipped')">
    <span class="kpi-flip-hint">&#x21c4;</span>
    <div class="kpi-inner">
      <div class="kpi-front">
        <div class="value" id="kpi-raised">—</div>
        <div class="label">Raised (2026)</div>
      </div>
      <div class="kpi-back">
        <div class="value" id="kpi-raised-all">—</div>
        <div class="label">All Pelotonia</div>
        <div class="kpi-share" id="kpi-raised-share"></div>
      </div>
    </div>
  </div>
  <div class="kpi kpi-flip" onclick="this.classList.toggle('flipped')">
    <span class="kpi-flip-hint">&#x21c4;</span>
    <div class="kpi-inner">
      <div class="kpi-front">
        <div class="value" id="kpi-alltime">—</div>
        <div class="label">All-Time Raised</div>
      </div>
      <div class="kpi-back">
        <div class="value" id="kpi-alltime-all">—</div>
        <div class="label">All Pelotonia</div>
        <div class="kpi-share" id="kpi-alltime-share"></div>
      </div>
    </div>
  </div>
  <div class="kpi kpi-flip" onclick="this.classList.toggle('flipped')">
    <span class="kpi-flip-hint">&#x21c4;</span>
    <div class="kpi-inner">
      <div class="kpi-front">
        <div class="value" id="kpi-members">—</div>
        <div class="label">Members</div>
      </div>
      <div class="kpi-back">
        <div class="value" id="kpi-members-all">—</div>
        <div class="label">All Pelotonia</div>
        <div class="kpi-share" id="kpi-members-share"></div>
      </div>
    </div>
  </div>
  <div class="kpi"><div class="value" id="kpi-first-year">—</div><div class="label">First Year Riders</div></div>
  <div class="kpi"><div class="value" id="kpi-sig-riders">—</div><div class="label">Signature Riders</div></div>
  <div class="kpi"><div class="value" id="kpi-grv-riders">—</div><div class="label">Gravel Riders</div></div>
  <div class="kpi"><div class="value" id="kpi-survivors">—</div><div class="label">Cancer Survivors</div></div>
  <div class="kpi"><div class="value" id="kpi-highrollers">—</div><div class="label">High Rollers</div></div>
</div>

<!-- Goal progress bar -->
<div class="progress-wrap">
  <div class="progress-outer">
    <div class="progress-inner" id="goal-bar" style="width:0%"></div>
    <div class="progress-label" id="goal-label">—</div>
  </div>
</div>

<!-- Tabs -->
<div class="tabs-wrap" style="padding: 0 24px;">
  <div class="tabs">
    <div class="tab active" data-tab="overview">Overview</div>
    <div class="tab" data-tab="teams">Teams</div>
    <div class="tab" data-tab="routes">Routes & Events</div>
    <div class="tab" data-tab="members">Members</div>
    <div class="tab" data-tab="donors">Donors</div>
    <div class="tab" data-tab="companies">Companies</div>
    <div class="tab" data-tab="donations">Donations</div>
    <div class="tab" data-tab="infographics">Infographics</div>
    <div class="tab" data-tab="report">Daily Report</div>
    <div class="tab" data-tab="kids">Pelotonia Kids</div>
    <div class="tab" data-tab="leaderboard">Leaderboard</div>
  </div>
</div>

<!-- Tab: Overview -->
<div class="tab-content active" id="tab-overview">
  <div style="padding: 16px 24px 0;">
    <div class="goals-panel">
      <div class="goals-title">PELOTONIA<sup>®</sup> 2026<span class="goals-asof" id="goals-asof"></span></div>
      <div id="goals-rows"></div>
      <div class="goal-row goals-scale-row">
        <div class="goal-row-label goals-pct-label">%</div>
        <div class="goals-scale-ticks" id="goals-scale-ticks"></div>
        <div class="goals-scale-goal-label">GOAL</div>
      </div>
    </div>
  </div>
  <div class="grid grid-2">
    <div class="card">
      <h2>Fundraising Growth</h2>
      <div class="chart-container"><canvas id="chart-timeline"></canvas></div>
    </div>
    <div class="card">
      <h2>Participant Signups Over Time</h2>
      <div class="chart-container"><canvas id="chart-signup-timeline"></canvas></div>
    </div>
  </div>
  <div class="grid grid-2">
    <div class="card">
      <h2>Participant Types by Sub-Team</h2>
      <div style="position:relative;height:450px;"><canvas id="chart-team-participants"></canvas></div>
    </div>
    <div class="card">
      <h2>Raised by Sub-Team</h2>
      <div style="position:relative;height:450px;"><canvas id="chart-team-raised"></canvas></div>
    </div>
  </div>
</div>

<!-- Tab: Teams -->
<div class="tab-content" id="tab-teams">
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>2026 Goals &amp; Progress by Sub-Team</h2>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr>
            <th>Sub-Team</th>
            <th class="text-center">Riders</th><th class="text-center">Goal</th>
            <th class="text-center">Challengers</th><th class="text-center">Goal</th>
            <th class="text-center">Volunteers</th><th class="text-center">Goal</th>
            <th class="text-right">Raised</th><th class="text-right">Committed</th><th class="text-right">Fund Goal</th>
            <th class="text-center">%</th>
          </tr></thead>
          <tbody id="table-team-goals-teams"></tbody>
          <tfoot id="table-team-goals-teams-totals" style="font-weight:700;border-top:2px solid #44D62C"></tfoot>
        </table>
      </div>
    </div>
  </div>
  <div class="grid grid-2">
    <div class="card">
      <h2>Participant Types by Sub-Team</h2>
      <div style="position:relative;height:450px;"><canvas id="chart-team-participants-2"></canvas></div>
    </div>
    <div class="card">
      <h2>Raised by Sub-Team</h2>
      <div style="position:relative;height:450px;"><canvas id="chart-team-raised-2"></canvas></div>
    </div>
  </div>

</div>

<!-- Tab: Routes & Events -->
<div class="tab-content" id="tab-routes">
  <div class="grid grid-2">
    <div class="card">
      <h2>Signature Ride Signups</h2>
      <div style="font-size:48px;font-weight:800;color:var(--forest)" id="sig-total">—</div>
      <div style="font-size:12px;color:#666;text-transform:uppercase">Team Members Registered</div>
      <div style="font-size:13px;color:#888;margin-top:4px">Ride Weekend: August 1-2, 2026</div>
    </div>
    <div class="card">
      <h2>Gravel Day Signups</h2>
      <div style="font-size:48px;font-weight:800;color:var(--forest)" id="grv-total">—</div>
      <div style="font-size:12px;color:#666;text-transform:uppercase">Team Members Registered</div>
      <div style="font-size:13px;color:#888;margin-top:4px">Gravel Day: October 3, 2026</div>
    </div>
  </div>
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>2026 Signature Ride Routes</h2>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr><th>Route</th><th class="text-right">Distance</th><th class="text-right">Commitment</th><th class="text-center">Signups</th><th class="text-right">Raised</th><th class="text-right">Committed</th><th>Start/End</th></tr></thead>
          <tbody id="table-signature-routes"></tbody>
        </table>
      </div>
    </div>
  </div>
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>2026 Gravel Day Routes</h2>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr><th>Route</th><th class="text-right">Distance</th><th class="text-right">Commitment</th><th class="text-center">Signups</th><th class="text-right">Raised</th><th class="text-right">Committed</th><th>Start/End</th></tr></thead>
          <tbody id="table-gravel-routes"></tbody>
        </table>
      </div>
    </div>
  </div>
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>Fundraising by Route</h2>
      <div class="chart-container"><canvas id="chart-routes"></canvas></div>
    </div>
  </div>
</div>

<!-- Tab: Members -->
<div class="tab-content" id="tab-members">
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-bottom:16px;">
    <div class="card" style="text-align:center;padding:16px;">
      <div style="font-size:13px;color:#888;margin-bottom:4px;">Members</div>
      <div style="font-size:28px;font-weight:700;" id="members-kpi-count">—</div>
    </div>
    <div class="card" style="text-align:center;padding:16px;">
      <div style="font-size:13px;color:#888;margin-bottom:4px;">Unique Donors</div>
      <div style="font-size:28px;font-weight:700;" id="members-kpi-donors">—</div>
    </div>
    <div class="card" style="text-align:center;padding:16px;">
      <div style="font-size:13px;color:#888;margin-bottom:4px;">Avg Donors / Member</div>
      <div style="font-size:28px;font-weight:700;" id="members-kpi-avg">—</div>
    </div>
  </div>
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>All Members (<span id="member-count">0</span>)</h2>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input class="search-bar" id="member-search" placeholder="Search by name, team, type, or tag..." style="margin-bottom:0;flex:1;">
        <button id="member-search-clear" style="display:none;padding:6px 14px;border:1px solid #ddd;border-radius:6px;background:#fff;cursor:pointer;font-size:13px;color:#666;white-space:nowrap;" title="Clear filter">&times; Clear</button>
        <button class="btn-export" onclick="exportMembers()" title="Export to CSV">&#x2913; CSV</button>
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr><th>#</th><th>Name</th><th>Sub-Team</th><th class="text-center">Type</th><th>Ride</th><th class="text-right">Committed</th><th class="text-right">Raised</th><th class="text-right">All-Time</th><th>Tags</th></tr></thead>
          <tbody id="table-members"></tbody>
        </table>
      </div>
      <div class="pagination" id="pag-members"></div>
    </div>
  </div>
</div>

<!-- Tab: Donors -->
<div class="tab-content" id="tab-donors">
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>All Donors</h2>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input class="search-bar" id="donor-search" placeholder="Search donors..." style="margin-bottom:0;flex:1;">
        <button class="btn-export" onclick="exportDonors()" title="Export to CSV">&#x2913; CSV</button>
      </div>
      <table>
        <thead><tr><th>#</th><th>Donor</th><th class="text-right">Total</th><th class="text-center">Txns</th></tr></thead>
        <tbody id="table-all-donors"></tbody>
      </table>
      <div class="pagination" id="pag-donors"></div>
    </div>
  </div>
</div>

<!-- Tab: Companies -->
<div class="tab-content" id="tab-companies">
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>Company / Organization Donations (<span id="company-count">0</span>)</h2>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input class="search-bar" id="company-search" placeholder="Search companies..." style="margin-bottom:0;flex:1;">
        <button class="btn-export" onclick="exportCompanies()" title="Export to CSV">&#x2913; CSV</button>
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr><th>#</th><th>Company</th><th class="text-right">Total</th><th class="text-center">Donors</th><th class="text-center">Recipients</th><th class="text-center">Txns</th></tr></thead>
          <tbody id="table-companies"></tbody>
        </table>
      </div>
      <div class="pagination" id="pag-companies"></div>
    </div>
  </div>
</div>

<!-- Tab: Donations -->
<div class="tab-content" id="tab-donations">
  <div class="grid" style="grid-template-columns:1fr">
    <div class="card">
      <h2>Donation Feed</h2>
      <div style="display:flex;gap:8px;margin-bottom:12px;">
        <input class="search-bar" id="donation-search" placeholder="Search by donor, recipient, or amount..." style="margin-bottom:0;flex:1;">
        <button class="btn-export" onclick="exportDonations()" title="Export to CSV">&#x2913; CSV</button>
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr><th>Date</th><th>Donor</th><th>Recipient</th><th>Team</th><th class="text-right">Amount</th></tr></thead>
          <tbody id="table-donations"></tbody>
        </table>
      </div>
      <div class="pagination" id="pag-donations"></div>
    </div>
  </div>
</div>

<!-- Tab: Infographics -->
<div class="tab-content" id="tab-infographics">
  <div class="infographic-controls">
    <div style="display:flex;align-items:center;gap:12px;">
      <label style="font-weight:600;color:var(--forest);">Team:</label>
      <select id="infographic-team-select" class="infographic-select"></select>
    </div>
  </div>
  <div class="thermo-grid" id="thermo-grid"></div>
  <div class="infographic-summary" id="infographic-summary"></div>
  <div style="padding:0 24px 24px;">
    <div class="card">
      <h2>2026 Goals &amp; Progress by Sub-Team</h2>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr>
            <th>Sub-Team</th>
            <th class="text-center">Riders</th><th class="text-center">Goal</th>
            <th class="text-center">Challengers</th><th class="text-center">Goal</th>
            <th class="text-center">Volunteers</th><th class="text-center">Goal</th>
            <th class="text-right">Raised</th><th class="text-right">Committed</th><th class="text-right">Fund Goal</th>
            <th class="text-center">%</th>
          </tr></thead>
          <tbody id="table-team-goals"></tbody>
          <tfoot id="table-team-goals-totals" style="font-weight:700;border-top:2px solid #44D62C"></tfoot>
        </table>
      </div>
    </div>
  </div>
</div>

<!-- Tab: Daily Report (email-style view) -->
<div class="tab-content" id="tab-report">
  <div style="max-width:680px;margin:0 auto;padding:16px;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
      <label style="font-weight:600;color:var(--forest);">View:</label>
      <select id="report-period-select" style="padding:6px 12px;border-radius:6px;border:1px solid #ccc;font-size:14px;">
        <option value="daily">Daily</option>
        <option value="weekly">Weekly (7 days)</option>
      </select>
      <label style="font-weight:600;color:var(--forest);">Sub-Team:</label>
      <select id="report-subteam-select" style="padding:6px 12px;border-radius:6px;border:1px solid #ccc;font-size:14px;max-width:280px;">
        <option value="__all__">All Sub-Teams</option>
      </select>
    </div>
    <div id="report-container"></div>
  </div>
</div>

<!-- Tab: Pelotonia Kids -->
<div class="tab-content" id="tab-kids">
  <div style="padding: 16px 24px 0;">
    <div class="card" style="text-align:center;padding:24px;">
      <h2 style="color:var(--forest);margin-bottom:16px;">Pelotonia Kids &mdash; Aggregate Stats</h2>
      <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:24px;margin-bottom:20px;">
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--green);" id="kids-kpi-raised">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">Total Raised</div>
        </div>
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--forest);" id="kids-kpi-fundraisers">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">Fundraisers</div>
        </div>
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--tread);" id="kids-kpi-goal">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">Goal</div>
        </div>
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--green);" id="kids-kpi-pct">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">% Progress</div>
        </div>
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--forest);" id="kids-kpi-teams">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">Teams</div>
        </div>
      </div>
      <!-- Progress bar -->
      <div class="progress-wrap" style="padding:0;max-width:600px;margin:0 auto 16px;">
        <div class="progress-outer">
          <div class="progress-inner" id="kids-goal-bar" style="width:0%"></div>
          <div class="progress-label" id="kids-goal-label">&mdash;</div>
        </div>
      </div>
    </div>
  </div>
  <div class="grid grid-2">
    <div class="card">
      <h2>Kids Fundraising Growth</h2>
      <div class="chart-container"><canvas id="chart-kids-raised"></canvas></div>
    </div>
    <div class="card">
      <h2>Fundraiser Signups Over Time</h2>
      <div class="chart-container"><canvas id="chart-kids-signups"></canvas></div>
    </div>
  </div>
  <div style="padding: 0 24px 16px;">
    <div class="card" style="text-align:center;padding:16px;font-size:13px;color:#888;">
      <div>Event: <strong>May 16, 2026</strong> at Easton Oval &bull; Ages 0&ndash;13 &bull; $25 registration &bull; 100% to Nationwide Children&rsquo;s Hospital</div>
      <div id="kids-last-updated" style="margin-top:4px;font-size:11px;"></div>
    </div>
  </div>
</div>

<!-- Tab: Leaderboard -->
<div class="tab-content" id="tab-leaderboard">
  <div style="padding: 16px 24px 0;">
    <div class="card" style="text-align:center;padding:24px;">
      <h2 style="color:var(--forest);margin-bottom:16px;">Pelotonia Organization Leaderboard</h2>
      <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:24px;margin-bottom:8px;">
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--green);" id="lb-kpi-orgs">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">Organizations</div>
        </div>
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--forest);" id="lb-kpi-members">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">Total Members</div>
        </div>
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--green);" id="lb-kpi-raised">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">2026 Raised</div>
        </div>
        <div>
          <div style="font-size:36px;font-weight:800;color:var(--forest);" id="lb-kpi-alltime">&mdash;</div>
          <div style="font-size:12px;color:#888;text-transform:uppercase;">All-Time Raised</div>
        </div>
      </div>
    </div>
  </div>
  <div style="padding: 0 24px;">
    <div class="card" style="padding:16px;overflow-x:auto;">
      <table class="data-table" id="lb-table">
        <thead>
          <tr>
            <th class="sortable" data-col="rank" style="width:50px;">Rank</th>
            <th class="sortable" data-col="name">Organization</th>
            <th class="sortable" data-col="members_count" style="text-align:right;">Members</th>
            <th class="sortable" data-col="sub_team_count" style="text-align:right;">Sub-Teams</th>
            <th class="sortable" data-col="raised" style="text-align:right;">2026 Raised</th>
            <th class="sortable" data-col="goal" style="text-align:right;">2026 Goal</th>
            <th class="sortable" data-col="pct" style="text-align:right;">% of Goal</th>
            <th class="sortable" data-col="all_time_raised" style="text-align:right;">All-Time</th>
          </tr>
        </thead>
        <tbody id="lb-table-body"></tbody>
      </table>
    </div>
  </div>
  <div style="padding: 0 24px 16px;">
    <div class="card">
      <h2>Top Organizations by 2026 Fundraising</h2>
      <div style="position:relative;height:500px;"><canvas id="chart-org-raised"></canvas></div>
    </div>
  </div>
</div>

<!-- Route drill-down modal -->
<div class="modal-overlay" id="route-modal">
  <div class="modal">
    <button class="close-btn" id="modal-close">&times;</button>
    <h2 id="modal-title">Route Members</h2>
    <div id="modal-body"></div>
  </div>
</div>

<!-- Data Guide modal -->
<div class="modal-overlay" id="guide-modal">
  <div class="modal">
    <button class="close-btn" id="guide-modal-close">&times;</button>
    <h2>Data Reference Guide</h2>
    <div id="guide-modal-body"></div>
  </div>
</div>

<footer>Pelotonia Team Huntington Dashboard &middot; Data from pelotonia.org API</footer>

<script>
Chart.register(ChartDataLabels);
Chart.defaults.plugins.datalabels = { display: false };
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const money = n => '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0});
const moneyFull = n => '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const shortTeam = n => n ? n.replace('Team Huntington Bank - ', '') : '—';
// Classify member type — treat anyone with a route as a rider even if API flags are missing
function memberType(m) {
  if (m.is_rider) return 'Rider';
  if (m.is_challenger) return 'Challenger';
  if (m.is_volunteer) return 'Volunteer';
  if (m.route_names) return 'Rider';
  return '—';
}

// Module-scope data for cross-tab drill-downs
let allDonations = [];
let allMembers = [];

// Tab switching
$$('.tab').forEach(t => t.addEventListener('click', () => {
  $$('.tab').forEach(x => x.classList.remove('active'));
  $$('.tab-content').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  t.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  $(`#tab-${t.dataset.tab}`).classList.add('active');
}));

// Route drill-down modal
function openRouteModal(routeId, routeName) {
  const modal = $('#route-modal');
  $('#modal-title').textContent = routeName;
  $('#modal-body').innerHTML = '<div style="text-align:center;padding:20px;color:#888">Loading...</div>';
  modal.classList.add('active');

  fetch(`/api/route-members/${routeId}`).then(r => r.json()).then(members => {
    if (!members.length) {
      $('#modal-body').innerHTML = '<p style="color:#888">No members signed up for this route.</p>';
      return;
    }
    let html = '<table><thead><tr><th>#</th><th>Name</th><th class="text-center">Years</th><th class="text-right">Raised</th><th class="text-right">Committed</th></tr></thead><tbody>';
    members.forEach((m, i) => {
      const cls = m.is_first_year ? ' class="first-year"' : '';
      const badge = m.is_first_year ? '<span class="badge-first-year">1st Year</span>' : '';
      const yearLabel = m.years > 0 ? m.years : '1st';
      html += `<tr${cls}>
        <td>${i+1}</td>
        <td>${m.name}${badge}</td>
        <td class="text-center">${yearLabel}</td>
        <td class="text-right">${money(m.raised)}</td>
        <td class="text-right">${money(m.committed_amount)}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    html += `<div style="font-size:12px;color:#888;margin-top:8px">${members.length} member${members.length!==1?'s':''} on this route</div>`;
    $('#modal-body').innerHTML = html;
  });
}
$('#modal-close').addEventListener('click', () => $('#route-modal').classList.remove('active'));
$('#route-modal').addEventListener('click', e => { if (e.target === e.currentTarget) e.currentTarget.classList.remove('active'); });

// ── Cross-tab drill-down functions ──

function navigateToMember(publicId, name) {
  // Switch to Members tab
  $$('.tab').forEach(x => x.classList.remove('active'));
  $$('.tab-content').forEach(x => x.classList.remove('active'));
  const membersTab = [...$$('.tab')].find(t => t.dataset.tab === 'members');
  membersTab.classList.add('active');
  $('#tab-members').classList.add('active');
  // Set search to the member name
  const searchBar = $('#member-search');
  searchBar.value = name;
  searchBar.dispatchEvent(new Event('input'));
  // After rendering, highlight and scroll to the matching row
  setTimeout(() => {
    const row = document.querySelector(`#table-members tr[data-public-id="${publicId}"]`);
    if (row) {
      row.classList.add('highlight-row');
      row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => row.classList.remove('highlight-row'), 2500);
    }
  }, 100);
}

function openMemberDonors(publicId, name) {
  const memberDonations = allDonations.filter(d => d.recipient_public_id === publicId);
  memberDonations.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  const modal = $('#route-modal');
  $('#modal-title').textContent = `Donations to ${name}`;
  if (!memberDonations.length) {
    $('#modal-body').innerHTML = '<p style="color:#888">No recorded donations for this member.</p>';
  } else {
    const total = memberDonations.reduce((s, d) => s + (d.amount || 0), 0);
    let html = '<table><thead><tr><th>Date</th><th>Donor</th><th class="text-right">Amount</th></tr></thead><tbody>';
    memberDonations.forEach(d => {
      const donor = d.anonymous_to_public ? `<i>${d.recognition_name || 'Anonymous'}</i>` : (d.donor_name || d.recognition_name || 'Anonymous');
      const dt = d.date ? d.date.substring(0, 10) : '—';
      html += `<tr><td>${dt}</td><td>${donor}</td><td class="text-right">${moneyFull(d.amount)}</td></tr>`;
    });
    html += '</tbody></table>';
    html += `<div style="font-size:13px;margin-top:8px;font-weight:600;color:var(--forest)">${memberDonations.length} donation${memberDonations.length !== 1 ? 's' : ''} &middot; Total: ${money(total)}</div>`;
    $('#modal-body').innerHTML = html;
  }
  modal.classList.add('active');
}

function openDonorRecipients(donorName) {
  // Match by donor_name or recognition_name
  const donorDonations = allDonations.filter(d =>
    (d.donor_name || '').toLowerCase() === donorName.toLowerCase() ||
    (d.recognition_name || '').toLowerCase() === donorName.toLowerCase()
  );
  // Group by recipient
  const byRecipient = {};
  donorDonations.forEach(d => {
    const key = d.recipient_public_id || 'unknown';
    if (!byRecipient[key]) byRecipient[key] = { name: d.recipient_name || 'Unknown', total: 0, count: 0 };
    byRecipient[key].total += d.amount || 0;
    byRecipient[key].count++;
  });
  const recipients = Object.values(byRecipient).sort((a, b) => b.total - a.total);
  const modal = $('#route-modal');
  $('#modal-title').textContent = `Donations from ${donorName}`;
  if (!recipients.length) {
    $('#modal-body').innerHTML = '<p style="color:#888">No donation records found.</p>';
  } else {
    const grandTotal = recipients.reduce((s, r) => s + r.total, 0);
    const totalCount = recipients.reduce((s, r) => s + r.count, 0);
    let html = '<table><thead><tr><th>Recipient</th><th class="text-center">Donations</th><th class="text-right">Total</th></tr></thead><tbody>';
    recipients.forEach(r => {
      html += `<tr><td>${r.name}</td><td class="text-center">${r.count}</td><td class="text-right">${money(r.total)}</td></tr>`;
    });
    html += '</tbody></table>';
    html += `<div style="font-size:13px;margin-top:8px;font-weight:600;color:var(--forest)">${totalCount} donation${totalCount !== 1 ? 's' : ''} to ${recipients.length} member${recipients.length !== 1 ? 's' : ''} &middot; Grand total: ${money(grandTotal)}</div>`;
    $('#modal-body').innerHTML = html;
  }
  modal.classList.add('active');
}

function openTeamMembers(teamName, allMembersList) {
  const teamMembers = allMembersList.filter(m => m.team_name === teamName);
  teamMembers.sort((a, b) => (b.raised || 0) - (a.raised || 0));
  const modal = $('#route-modal');
  $('#modal-title').textContent = shortTeam(teamName) + ' Members';

  if (!teamMembers.length) {
    $('#modal-body').innerHTML = '<p style="color:#888">No members found for this sub-team.</p>';
    modal.classList.add('active');
    return;
  }

  // Group counts (treat route-holders as riders)
  const rCount = teamMembers.filter(m => memberType(m) === 'Rider').length;
  const cCount = teamMembers.filter(m => memberType(m) === 'Challenger').length;
  const vCount = teamMembers.filter(m => memberType(m) === 'Volunteer').length;

  let html = `<div style="margin-bottom:12px;font-size:13px;color:#666">
    ${teamMembers.length} members &middot; ${rCount} riders &middot; ${cCount} challengers &middot; ${vCount} volunteers
  </div>`;
  html += `<table><thead><tr>
    <th>#</th><th>Name</th><th class="text-center">Type</th><th>Route</th>
    <th class="text-right">Committed</th><th class="text-right">Raised</th><th>Tags</th>
  </tr></thead><tbody>`;

  teamMembers.forEach((m, i) => {
    const ptype = memberType(m);
    const route = m.route_names || '—';
    const tags = [];
    if (m.is_cancer_survivor) tags.push('<span class="badge-tag badge-survivor">Survivor</span>');
    if (m.committed_high_roller) tags.push('<span class="badge-tag badge-hr">HR</span>');
    try {
      const parsed = JSON.parse(m.tags || '[]');
      parsed.forEach(t => {
        if (!t.includes('High Roller')) tags.push('<span class="badge-tag">' + t + '</span>');
      });
    } catch(e) {}

    html += `<tr>
      <td>${i + 1}</td>
      <td>${m.is_captain ? '&#11088; ' : ''}${m.name}</td>
      <td class="text-center">${ptype}</td>
      <td style="font-size:12px;max-width:200px">${route}</td>
      <td class="text-right">${m.committed_amount ? money(m.committed_amount) : '—'}</td>
      <td class="text-right">${money(m.raised)}</td>
      <td>${tags.join(' ')}</td>
    </tr>`;
  });

  html += '</tbody></table>';

  const totalRaised = teamMembers.reduce((s, m) => s + (m.raised || 0), 0);
  const totalCommitted = teamMembers.reduce((s, m) => s + (m.committed_amount || 0), 0);
  html += `<div style="font-size:13px;margin-top:8px;font-weight:600;color:var(--forest)">
    Total committed: ${money(totalCommitted)} &middot; Total raised: ${money(totalRaised)}
  </div>`;

  $('#modal-body').innerHTML = html;
  modal.classList.add('active');
}

// Fetch all data
async function loadDashboard() {
  const bundle = await fetch('/api/bundle').then(r => r.json());
  const { overview, teams, timeline, fundraisers, donors, members, donations,
          teamBreakdown, commitTiers, rideTypes, routes, signupTimeline, companies } = bundle;

  // Store at module scope for drill-downs
  allDonations = donations;
  allMembers = members;

  // KPIs
  $('#kpi-raised').textContent = money(overview.raised);
  $('#kpi-alltime').textContent = money(overview.all_time_raised);
  $('#kpi-members').textContent = overview.members_count;
  $('#kpi-first-year').textContent = (overview.first_year || 0).toLocaleString();
  $('#kpi-sig-riders').textContent = overview.signature_riders;
  $('#kpi-grv-riders').textContent = overview.gravel_riders;
  $('#kpi-survivors').textContent = overview.cancer_survivors;
  $('#kpi-highrollers').textContent = overview.high_rollers;

  // Ticker (Pelotonia-wide context for flip cards)
  const ticker = bundle.ticker || {};
  if (ticker.currentYearRaised) {
    $('#kpi-raised-all').textContent = money(ticker.currentYearRaised);
    const raisedPct = overview.raised > 0 ? (overview.raised / ticker.currentYearRaised * 100).toFixed(1) : '0';
    $('#kpi-raised-share').textContent = 'Huntington = ' + raisedPct + '%';
  }
  if (ticker.allTimeRaised) {
    $('#kpi-alltime-all').textContent = money(ticker.allTimeRaised);
    const alltimePct = overview.all_time_raised > 0 ? (overview.all_time_raised / ticker.allTimeRaised * 100).toFixed(1) : '0';
    $('#kpi-alltime-share').textContent = 'Huntington = ' + alltimePct + '%';
  }
  if (ticker.totalParticipants) {
    $('#kpi-members-all').textContent = Math.round(ticker.totalParticipants).toLocaleString();
    const memPct = overview.members_count > 0 ? (overview.members_count / ticker.totalParticipants * 100).toFixed(1) : '0';
    $('#kpi-members-share').textContent = 'Huntington = ' + memPct + '%';
  }

  // Goal progress
  const pct = overview.goal > 0 ? (overview.raised / overview.goal * 100) : 0;
  $('#goal-bar').style.width = Math.min(pct, 100) + '%';
  $('#goal-label').textContent = `${money(overview.raised)} / ${money(overview.goal)} (${pct.toFixed(1)}%)`;

  // ── Pelotonia Goals Panel ──
  const pGoals = { riders: GOALS_2026.riders, challengers: GOALS_2026.challengers, volunteers: GOALS_2026.volunteers, raised: overview.goal || 5990023 };
  const goalItems = [
    { key: 'riders', label: 'RIDERS', current: overview.riders || 0, target: pGoals.riders, fmt: v => v.toLocaleString() },
    { key: 'challengers', label: 'CHALLENGERS', current: overview.challengers || 0, target: pGoals.challengers, fmt: v => v.toLocaleString() },
    { key: 'volunteers', label: 'VOLUNTEERS', current: overview.volunteers || 0, target: pGoals.volunteers, fmt: v => v.toLocaleString() },
    { key: 'raised', label: '2026 FUNDS RAISED', current: overview.raised || 0, target: pGoals.raised, fmt: v => '$' + v.toLocaleString() },
  ];
  const arrowImg = '<img src="data:image/png;base64,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" alt="→">';
  const goalsContainer = $('#goals-rows');
  goalItems.forEach(g => {
    const gp = g.target > 0 ? Math.min(g.current / g.target * 100, 100) : 0;
    const curFmt = g.key === 'raised' ? money(g.current) : g.current.toLocaleString();
    goalsContainer.innerHTML += `<div class="goal-row">
      <div class="goal-row-label">${g.label}</div>
      <div class="goal-bar-wrap">
        <div class="goal-bar-line"></div>
        <div class="goal-bar-fill-line" style="width:calc(${gp}% - 36px)"></div>
        <div class="goal-arrow-wrap" style="left:${gp}%">${arrowImg}<span class="goal-current-val">${curFmt}</span></div>
      </div>
      <div class="goal-target">${g.fmt(g.target)}</div>
    </div>`;
  });
  // General peloton funds footnote
  const gpf = overview.general_peloton_funds || 0;
  if (gpf > 0) {
    const note = document.createElement('div');
    note.style.cssText = 'font-size:11px;color:#888;text-align:right;margin-top:4px;padding-right:4px;font-style:italic';
    note.textContent = `Includes ${moneyShort(gpf)} in general team donations not attributed to individual members`;
    goalsContainer.parentElement.appendChild(note);
  }
  const scaleTicks = $('#goals-scale-ticks');
  for (let i = 0; i <= 100; i += 10) {
    const s = document.createElement('span');
    s.style.cssText = 'text-align:center;display:flex;flex-direction:column;align-items:center';
    s.innerHTML = '<span style="width:1px;height:8px;background:rgba(68,214,44,.3);margin-bottom:2px"></span>' + i;
    scaleTicks.appendChild(s);
  }
  // Last updated
  if (overview.last_scraped) {
    const d = new Date(overview.last_scraped);
    $('#last-updated').textContent = `Last updated: ${d.toLocaleString()}`;
    const short = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    $('#goals-asof').textContent = `as of ${short}`;
  }

  // ── Fundraising Growth Chart ──
  new Chart($('#chart-timeline'), {
    type: 'line',
    data: {
      labels: timeline.map(t => t.date),
      datasets: [
        {
          label: 'Cumulative ($)',
          data: timeline.map(t => t.cumulative),
          borderColor: '#44D62C',
          backgroundColor: 'rgba(68,214,44,.1)',
          fill: true,
          tension: .3,
          pointRadius: 3,
          yAxisID: 'y',
        },
        {
          label: 'Daily ($)',
          data: timeline.map(t => t.daily_amount),
          borderColor: '#00471F',
          backgroundColor: '#00471F',
          type: 'bar',
          yAxisID: 'y1',
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: { position: 'left', title: { display: true, text: 'Cumulative' },
             ticks: { callback: v => money(v) } },
        y1: { position: 'right', grid: { drawOnChartArea: false },
              title: { display: true, text: 'Daily' },
              ticks: { callback: v => money(v) } },
        x: { ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 } }
      },
      plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + moneyFull(ctx.raw) } } }
    }
  });

  // ── Participant Signups Over Time Chart ──
  if (signupTimeline.length) {
    new Chart($('#chart-signup-timeline'), {
      type: 'line',
      data: {
        labels: signupTimeline.map(s => s.snapshot_date),
        datasets: [
          {
            label: 'Total Members',
            data: signupTimeline.map(s => s.members_count),
            borderColor: '#29322D',
            backgroundColor: 'rgba(41,50,45,.1)',
            fill: true,
            tension: .3,
            pointRadius: 3,
          },
          {
            label: 'Signature Riders',
            data: signupTimeline.map(s => s.signature_riders),
            borderColor: '#44D62C',
            backgroundColor: 'rgba(68,214,44,.1)',
            fill: true,
            tension: .3,
            pointRadius: 3,
          },
          {
            label: 'Gravel Riders',
            data: signupTimeline.map(s => s.gravel_riders),
            borderColor: '#00471F',
            backgroundColor: 'rgba(0,71,31,.2)',
            fill: true,
            tension: .3,
            pointRadius: 3,
          },
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { title: { display: true, text: 'Participants' }, beginAtZero: true },
          x: { ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 } }
        },
      }
    });
  } else {
    $('#chart-signup-timeline').parentElement.innerHTML = '<div style="text-align:center;padding:40px;color:#888">Signup tracking starts after the next daily scrape.<br>Current: ' + overview.signature_riders + ' Signature, ' + overview.gravel_riders + ' Gravel</div>';
  }

  // ── Team Breakdown Charts (Overview + Teams tabs) ──
  const tbSorted = [...teamBreakdown].sort((a,b) => b.total - a.total);
  const sortedTeams = [...teams].sort((a,b) => b.raised - a.raised);
  const participantsConfig = () => ({
    type: 'bar',
    data: {
      labels: tbSorted.map(t => shortTeam(t.name)),
      datasets: [
        { label: 'Riders', data: tbSorted.map(t => t.riders), backgroundColor: '#44D62C' },
        { label: 'Challengers', data: tbSorted.map(t => t.challengers), backgroundColor: '#0E1411' },
        { label: 'Registered Only', data: tbSorted.map(t => t.total - (t.riders||0) - (t.challengers||0) - (t.volunteers||0)), backgroundColor: '#bbb' },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      scales: {
        x: { stacked: true },
        y: { stacked: true, ticks: { font: { size: 11 }, autoSkip: false } }
      },
      plugins: {
        datalabels: {
          display: function(ctx) { return ctx.dataset.data[ctx.dataIndex] >= 5; },
          color: function(ctx) { return ctx.datasetIndex === 1 ? '#fff' : '#000'; },
          font: { weight: 'bold', size: 11 },
          anchor: 'center', align: 'center',
        }
      }
    }
  });
  const raisedConfig = () => ({
    type: 'bar',
    data: {
      labels: sortedTeams.map(t => shortTeam(t.name)),
      datasets: [
        { label: '2026 Raised', data: sortedTeams.map(t => t.raised), backgroundColor: '#44D62C' },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: 'y',
      layout: { padding: { right: 60 } },
      scales: {
        x: { ticks: { callback: v => money(v) } },
        y: { ticks: { font: { size: 11 }, autoSkip: false } }
      },
      plugins: {
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + moneyFull(ctx.raw) } },
        datalabels: {
          display: function(ctx) { return ctx.dataset.data[ctx.dataIndex] >= 1000; },
          color: '#333', font: { weight: 'bold', size: 11 },
          anchor: 'end', align: 'right',
          formatter: function(v) { return '$' + Math.round(v / 1000) + 'k'; },
        }
      }
    }
  });
  // Overview tab
  new Chart($('#chart-team-participants'), participantsConfig());
  new Chart($('#chart-team-raised'), raisedConfig());
  // Teams tab
  new Chart($('#chart-team-participants-2'), participantsConfig());
  new Chart($('#chart-team-raised-2'), raisedConfig());

  // ── Routes & Events Tab ──
  const sigRoutes = routes.filter(r => r.ride_type === 'signature');
  const grvRoutes = routes.filter(r => r.ride_type === 'gravel');

  // Ride totals
  if (sigRoutes.length) $('#sig-total').textContent = sigRoutes[0].ride_total_signups;
  if (grvRoutes.length) $('#grv-total').textContent = grvRoutes[0].ride_total_signups;

  function buildRouteTable(routeList, tbodyEl) {
    let totSignups = 0, totRaised = 0, totCommitted = 0;
    routeList.forEach(r => {
      totSignups += r.signups || 0;
      totRaised += r.route_raised || 0;
      totCommitted += r.route_committed || 0;
      const loc = r.starting_city || '—';
      const locStr = r.ending_city && r.ending_city !== r.starting_city ? `${loc} &rarr; ${r.ending_city}` : loc;
      tbodyEl.innerHTML += `<tr class="route-row" data-route-id="${r.id}" data-route-name="${r.name}">
        <td>${r.name}</td>
        <td class="text-right">${r.distance} mi</td>
        <td class="text-right">${money(r.fundraising_commitment)}</td>
        <td class="text-center">${r.signups || '—'}</td>
        <td class="text-right">${r.route_raised ? money(r.route_raised) : '—'}</td>
        <td class="text-right">${r.route_committed ? money(r.route_committed) : '—'}</td>
        <td>${locStr}</td>
      </tr>`;
    });
    tbodyEl.innerHTML += `<tr class="totals-row">
      <td>Total</td><td></td><td></td>
      <td class="text-center">${totSignups}</td>
      <td class="text-right">${money(totRaised)}</td>
      <td class="text-right">${money(totCommitted)}</td>
      <td></td>
    </tr>`;
  }

  buildRouteTable(sigRoutes, $('#table-signature-routes'));
  buildRouteTable(grvRoutes, $('#table-gravel-routes'));

  // Click handler for route drill-down
  $$('.route-row').forEach(row => {
    row.addEventListener('click', () => {
      openRouteModal(row.dataset.routeId, row.dataset.routeName);
    });
  });

  // All routes comparison chart — raised vs committed
  const allRoutes = [...sigRoutes, ...grvRoutes];
  new Chart($('#chart-routes'), {
    type: 'bar',
    data: {
      labels: allRoutes.map(r => r.name.replace('Saturday ','Sat ').replace('Sunday ','Sun ')),
      datasets: [
        { label: 'Raised', data: allRoutes.map(r => r.route_raised), backgroundColor: '#44D62C' },
        { label: 'Committed', data: allRoutes.map(r => r.route_committed), backgroundColor: '#00471F' },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        y: { title: { display: true, text: 'Amount ($)' }, ticks: { callback: v => money(v) } },
        x: { ticks: { maxRotation: 45, font: { size: 10 } } }
      },
      plugins: { tooltip: { callbacks: { label: ctx => moneyFull(ctx.raw) } } }
    }
  });

  // ── Members KPIs ──
  {
    const uniqueDonors = new Set(donations.map(d => d.donor_name)).size;
    const membersWithDonors = new Set(donations.map(d => d.recipient_public_id)).size;
    const avgDonorsPerMember = membersWithDonors > 0 ? (uniqueDonors / membersWithDonors).toFixed(1) : '0';
    $('#members-kpi-count').textContent = members.length.toLocaleString();
    $('#members-kpi-donors').textContent = uniqueDonors.toLocaleString();
    $('#members-kpi-avg').textContent = avgDonorsPerMember;
  }

  // ── Full Members Table ──
  renderMembers(members);
  const memberSearchInput = $('#member-search');
  const memberClearBtn = $('#member-search-clear');
  memberSearchInput.addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    memberClearBtn.style.display = q ? 'block' : 'none';
    const filtered = members.filter(m =>
      m.name.toLowerCase().includes(q) ||
      (m.team_name||'').toLowerCase().includes(q) ||
      (m.tags||'').toLowerCase().includes(q) ||
      (m.ride_type||'').toLowerCase().includes(q) ||
      (memberType(m) === 'Rider' && 'rider'.includes(q)) ||
      (memberType(m) === 'Challenger' && 'challenger'.includes(q))
    );
    if (paginators.members) paginators.members.page = 1;
    renderMembers(filtered);
  });
  memberClearBtn.addEventListener('click', () => {
    memberSearchInput.value = '';
    memberClearBtn.style.display = 'none';
    if (paginators.members) paginators.members.page = 1;
    renderMembers(members);
  });

  // ── Full Donors Table ──
  renderDonors(donors);
  $('#donor-search').addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    const filtered = donors.filter(d => d.donor.toLowerCase().includes(q));
    if (paginators.donors) paginators.donors.page = 1;
    renderDonors(filtered);
  });

  // ── Companies Table ──
  renderCompanies(companies || []);
  $('#company-search').addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    const filtered = (companies || []).filter(c => c.company.toLowerCase().includes(q));
    if (paginators.companies) paginators.companies.page = 1;
    renderCompanies(filtered);
  });

  // ── Donations Feed ──
  renderDonations(donations);
  $('#donation-search').addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    const filtered = donations.filter(d =>
      (d.recognition_name||'').toLowerCase().includes(q) ||
      (d.donor_name||'').toLowerCase().includes(q) ||
      (d.recipient_name||'').toLowerCase().includes(q) ||
      String(d.amount).includes(q)
    );
    if (paginators.donations) paginators.donations.page = 1;
    renderDonations(filtered);
  });

  // ── Infographics Tab ──
  _infographicBundle = bundle;
  _computedTargets = computeSmartTargets(bundle);
  const teamSelect = document.getElementById('infographic-team-select');
  teamSelect.innerHTML = '<option value="__all__">All of Team Huntington</option>';
  teamBreakdown.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.name;
    opt.textContent = shortTeam(t.name);
    teamSelect.appendChild(opt);
  });
  teamSelect.addEventListener('change', () => {
    renderInfographics(bundle, teamSelect.value);
  });

  renderInfographics(bundle, '__all__');

  // ── Report Tab ──
  const reportSelect = document.getElementById('report-period-select');
  const reportSubteamSelect = document.getElementById('report-subteam-select');
  if (reportSelect) {
    // Populate sub-team dropdown
    if (reportSubteamSelect && bundle.teamBreakdown) {
      const sorted = [...bundle.teamBreakdown].sort((a,b) => (b.total_committed||0) - (a.total_committed||0));
      sorted.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.name;
        opt.textContent = shortTeam(t.name);
        reportSubteamSelect.appendChild(opt);
      });
    }
    const fireReport = () => renderReport(bundle, reportSelect.value, reportSubteamSelect ? reportSubteamSelect.value : '__all__');
    reportSelect.addEventListener('change', fireReport);
    if (reportSubteamSelect) reportSubteamSelect.addEventListener('change', fireReport);
    renderReport(bundle, 'daily', '__all__');
  }

  // ── Pelotonia Kids Tab ──
  const kidsOv = bundle.kidsOverview;
  const kidsSn = bundle.kidsSnapshots || [];
  if (kidsOv) {
    const kr = kidsOv.estimated_amount_raised || 0;
    const kg = kidsOv.monetary_goal || 0;
    const kPct = kg > 0 ? (kr / kg * 100) : 0;
    $('#kids-kpi-raised').textContent = money(kr);
    $('#kids-kpi-fundraisers').textContent = (kidsOv.fundraiser_count || 0).toLocaleString();
    $('#kids-kpi-goal').textContent = money(kg);
    $('#kids-kpi-pct').textContent = kPct.toFixed(1) + '%';
    $('#kids-kpi-teams').textContent = (kidsOv.team_count || 0).toLocaleString();
    // Progress bar
    $('#kids-goal-bar').style.width = Math.min(kPct, 100) + '%';
    $('#kids-goal-label').textContent = money(kr) + ' / ' + money(kg) + ' (' + kPct.toFixed(1) + '%)';
    // Last updated
    if (kidsOv.last_scraped) {
      const kd = new Date(kidsOv.last_scraped);
      $('#kids-last-updated').textContent = 'Last updated: ' + kd.toLocaleString();
    }
  }
  // Kids Charts
  if (kidsSn.length) {
    new Chart($('#chart-kids-raised'), {
      type: 'line',
      data: {
        labels: kidsSn.map(s => s.snapshot_date),
        datasets: [{
          label: 'Amount Raised ($)',
          data: kidsSn.map(s => s.estimated_amount_raised),
          borderColor: '#44D62C',
          backgroundColor: 'rgba(68,214,44,.1)',
          fill: true,
          tension: .3,
          pointRadius: 3,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { title: { display: true, text: 'Amount Raised' }, ticks: { callback: v => money(v) }, beginAtZero: true },
          x: { ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 } }
        },
        plugins: { tooltip: { callbacks: { label: ctx => moneyFull(ctx.raw) } } }
      }
    });
    new Chart($('#chart-kids-signups'), {
      type: 'line',
      data: {
        labels: kidsSn.map(s => s.snapshot_date),
        datasets: [{
          label: 'Fundraisers',
          data: kidsSn.map(s => s.fundraiser_count),
          borderColor: '#00471F',
          backgroundColor: 'rgba(0,71,31,.15)',
          fill: true,
          tension: .3,
          pointRadius: 3,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { title: { display: true, text: 'Fundraiser Count' }, beginAtZero: true },
          x: { ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 15 } }
        },
      }
    });
  } else {
    const kMsg = '<div style="text-align:center;padding:40px;color:#888">Kids snapshot tracking starts after running pledgeit_scraper.py</div>';
    const kRaised = $('#chart-kids-raised');
    const kSignups = $('#chart-kids-signups');
    if (kRaised) kRaised.parentElement.innerHTML = kMsg;
    if (kSignups) kSignups.parentElement.innerHTML = kMsg;
  }

  // ── Organization Leaderboard Tab ──
  const orgLb = bundle.orgLeaderboard || [];
  if (orgLb.length) {
    const HUNTINGTON_ID = 'a0s3t00000BKX8sAAH';
    // KPIs
    const totalMembers = orgLb.reduce((s, o) => s + (o.members_count || 0), 0);
    const totalRaised = orgLb.reduce((s, o) => s + (o.raised || 0), 0);
    const totalAllTime = orgLb.reduce((s, o) => s + (o.all_time_raised || 0), 0);
    $('#lb-kpi-orgs').textContent = orgLb.length.toLocaleString();
    $('#lb-kpi-members').textContent = totalMembers.toLocaleString();
    $('#lb-kpi-raised').textContent = money(totalRaised);
    $('#lb-kpi-alltime').textContent = money(totalAllTime);

    // Sortable table
    let lbData = orgLb.map((o, i) => ({...o, rank: i + 1, pct: o.goal > 0 ? (o.raised / o.goal * 100) : 0}));
    let lbSortCol = 'raised';
    let lbSortAsc = false;

    function renderLbTable() {
      const body = $('#lb-table-body');
      body.innerHTML = '';
      lbData.forEach((o, i) => {
        const isH = o.team_id === HUNTINGTON_ID;
        const pctStr = o.goal > 0 ? o.pct.toFixed(1) + '%' : '—';
        body.innerHTML += '<tr style="' + (isH ? 'background:#e8fce4;font-weight:700;' : '') + '">' +
          '<td>' + (i + 1) + '</td>' +
          '<td>' + (o.name || '—') + '</td>' +
          '<td style="text-align:right;">' + (o.members_count || 0).toLocaleString() + '</td>' +
          '<td style="text-align:right;">' + (o.sub_team_count || 0).toLocaleString() + '</td>' +
          '<td style="text-align:right;">' + money(o.raised || 0) + '</td>' +
          '<td style="text-align:right;">' + (o.goal > 0 ? money(o.goal) : '—') + '</td>' +
          '<td style="text-align:right;">' + pctStr + '</td>' +
          '<td style="text-align:right;">' + money(o.all_time_raised || 0) + '</td>' +
          '</tr>';
      });
    }

    // Column sorting
    $$('#lb-table .sortable').forEach(th => {
      th.style.cursor = 'pointer';
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (col === lbSortCol) { lbSortAsc = !lbSortAsc; } else { lbSortCol = col; lbSortAsc = col === 'name'; }
        lbData.sort((a, b) => {
          let va = a[col], vb = b[col];
          if (col === 'name') { va = (va || '').toLowerCase(); vb = (vb || '').toLowerCase(); }
          if (va < vb) return lbSortAsc ? -1 : 1;
          if (va > vb) return lbSortAsc ? 1 : -1;
          return 0;
        });
        // Update sort indicators
        $$('#lb-table .sortable').forEach(h => h.textContent = h.textContent.replace(/ [▲▼]$/, ''));
        th.textContent += lbSortAsc ? ' ▲' : ' ▼';
        renderLbTable();
      });
    });

    renderLbTable();

    // Bar chart — top 15 orgs by 2026 raised
    const top15 = [...orgLb].sort((a, b) => (b.raised || 0) - (a.raised || 0)).slice(0, 15);
    const barColors = top15.map(o => o.team_id === HUNTINGTON_ID ? '#44D62C' : '#b0b0b0');
    new Chart($('#chart-org-raised'), {
      type: 'bar',
      data: {
        labels: top15.map(o => o.name || '?'),
        datasets: [{
          label: '2026 Raised',
          data: top15.map(o => o.raised || 0),
          backgroundColor: barColors,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        indexAxis: 'y',
        layout: { padding: { right: 60 } },
        scales: {
          x: { ticks: { callback: v => money(v) } },
          y: { ticks: { font: { size: 11 }, autoSkip: false } }
        },
        plugins: {
          tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + moneyFull(ctx.raw) } },
          datalabels: {
            display: function(ctx) { return ctx.dataset.data[ctx.dataIndex] >= 1000; },
            color: '#333', font: { weight: 'bold', size: 11 },
            anchor: 'end', align: 'right',
            formatter: function(v) { return '$' + Math.round(v / 1000) + 'k'; },
          }
        }
      }
    });
  } else {
    const lbMsg = '<div style="text-align:center;padding:40px;color:#888">Organization tracking starts after running org_scraper.py</div>';
    const lbChart = $('#chart-org-raised');
    if (lbChart) lbChart.parentElement.innerHTML = lbMsg;
  }
}

// ── Pagination helper ──
const PAGE_SIZE = 50;
const paginators = {};

function renderPagination(key, total, page, el) {
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (total <= PAGE_SIZE) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <button class="pag-prev" ${page <= 1 ? 'disabled' : ''}>&#8592; Prev</button>
    <span class="page-info">Page ${page} of ${totalPages} &middot; ${total.toLocaleString()} rows</span>
    <button class="pag-next" ${page >= totalPages ? 'disabled' : ''}>Next &#8594;</button>`;
  el.querySelector('.pag-prev').addEventListener('click', () => {
    if (paginators[key].page > 1) { paginators[key].page--; paginators[key].render(); }
  });
  el.querySelector('.pag-next').addEventListener('click', () => {
    if (paginators[key].page < totalPages) { paginators[key].page++; paginators[key].render(); }
  });
}

function renderMembers(members) {
  const key = 'members';
  if (!paginators[key]) paginators[key] = { page: 1, data: members, render: () => renderMembers(paginators[key].data) };
  paginators[key].data = members;
  const page = paginators[key].page;
  const start = (page - 1) * PAGE_SIZE;
  const slice = members.slice(start, start + PAGE_SIZE);
  $('#member-count').textContent = members.length;
  const body = $('#table-members');
  body.innerHTML = '';
  slice.forEach((m, i) => {
    const tags = [];
    if (m.is_cancer_survivor) tags.push('<span class="badge-tag badge-survivor">Survivor</span>');
    if (m.committed_high_roller) tags.push('<span class="badge-tag badge-hr">High Roller</span>');
    try {
      const parsed = JSON.parse(m.tags||'[]');
      parsed.forEach(t => { if (!t.includes('High Roller')) tags.push(`<span class="badge-tag">${t}</span>`); });
    } catch(e){}
    const ptype = memberType(m);
    const rtype = m.route_names || m.ride_type || '—';
    body.innerHTML += `<tr class="clickable-row" data-public-id="${m.public_id}" data-name="${m.name}" title="Click to see donations">
      <td>${start+i+1}</td>
      <td>${m.is_captain ? '&#11088; ' : ''}${m.name}</td>
      <td>${shortTeam(m.team_name)}</td>
      <td class="text-center">${ptype}</td>
      <td>${rtype}</td>
      <td class="text-right">${m.committed_amount ? money(m.committed_amount) : '—'}</td>
      <td class="text-right">${money(m.raised)}</td>
      <td class="text-right">${money(m.all_time_raised)}</td>
      <td>${tags.join(' ')}</td>
    </tr>`;
  });
  body.querySelectorAll('.clickable-row').forEach(row => {
    row.addEventListener('click', () => openMemberDonors(row.dataset.publicId, row.dataset.name));
  });
  renderPagination(key, members.length, page, $('#pag-members'));
}

function renderDonors(donors) {
  const key = 'donors';
  if (!paginators[key]) paginators[key] = { page: 1, data: donors, render: () => renderDonors(paginators[key].data) };
  paginators[key].data = donors;
  const page = paginators[key].page;
  const start = (page - 1) * PAGE_SIZE;
  const slice = donors.slice(start, start + PAGE_SIZE);
  const body = $('#table-all-donors');
  body.innerHTML = '';
  slice.forEach((d, i) => {
    body.innerHTML += `<tr class="clickable-row" data-donor-name="${d.donor}" title="Click to see recipients">
      <td>${start+i+1}</td><td>${d.donor}</td>
      <td class="text-right">${money(d.total)}</td>
      <td class="text-center">${d.cnt}</td>
    </tr>`;
  });
  body.querySelectorAll('.clickable-row').forEach(row => {
    row.addEventListener('click', () => openDonorRecipients(row.dataset.donorName));
  });
  renderPagination(key, donors.length, page, $('#pag-donors'));
}

function renderCompanies(companies) {
  const key = 'companies';
  if (!paginators[key]) paginators[key] = { page: 1, data: companies, render: () => renderCompanies(paginators[key].data) };
  paginators[key].data = companies;
  const page = paginators[key].page;
  const start = (page - 1) * PAGE_SIZE;
  const slice = companies.slice(start, start + PAGE_SIZE);
  $('#company-count').textContent = companies.length;
  const body = $('#table-companies');
  body.innerHTML = '';
  slice.forEach((c, i) => {
    body.innerHTML += `<tr class="clickable-row" data-company="${c.company.replace(/"/g, '&quot;')}" title="Click to see donations">
      <td>${start+i+1}</td>
      <td>${c.company}</td>
      <td class="text-right">${money(c.total)}</td>
      <td class="text-center">${c.donor_count}</td>
      <td class="text-center">${c.recipient_count}</td>
      <td class="text-center">${c.donation_count}</td>
    </tr>`;
  });
  body.querySelectorAll('.clickable-row').forEach(row => {
    row.addEventListener('click', () => openCompanyDetail(row.dataset.company));
  });
  renderPagination(key, companies.length, page, $('#pag-companies'));
}

function openCompanyDetail(companyName) {
  const companyDonations = allDonations.filter(d =>
    !d.anonymous_to_public && d.recognition_name === companyName && d.donor_name !== companyName
  );
  companyDonations.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  const modal = $('#route-modal');
  $('#modal-title').textContent = companyName;
  if (!companyDonations.length) {
    $('#modal-body').innerHTML = '<p style="color:#888">No donation records found.</p>';
  } else {
    const total = companyDonations.reduce((s, d) => s + (d.amount || 0), 0);
    const donors = [...new Set(companyDonations.map(d => d.donor_name))];
    let html = `<div style="margin-bottom:12px;font-size:13px;color:#666">${donors.length} donor${donors.length!==1?'s':''} &middot; ${companyDonations.length} donation${companyDonations.length!==1?'s':''} &middot; Total: ${money(total)}</div>`;
    html += '<table><thead><tr><th>Date</th><th>Donor</th><th>Recipient</th><th class="text-right">Amount</th></tr></thead><tbody>';
    companyDonations.forEach(d => {
      const dt = d.date ? d.date.substring(0, 10) : '—';
      html += `<tr>
        <td>${dt}</td>
        <td>${d.donor_name || '—'}</td>
        <td>${d.recipient_name || '—'}</td>
        <td class="text-right">${moneyFull(d.amount)}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    $('#modal-body').innerHTML = html;
  }
  modal.classList.add('active');
}

function renderDonations(donations) {
  const key = 'donations';
  if (!paginators[key]) paginators[key] = { page: 1, data: donations, render: () => renderDonations(paginators[key].data) };
  paginators[key].data = donations;
  const page = paginators[key].page;
  const start = (page - 1) * PAGE_SIZE;
  const slice = donations.slice(start, start + PAGE_SIZE);
  const body = $('#table-donations');
  body.innerHTML = '';
  slice.forEach(d => {
    const donor = d.anonymous_to_public ? `<i>${d.recognition_name || 'Anonymous'}</i>` : (d.donor_name || d.recognition_name || '—');
    const dt = d.date ? d.date.substring(0, 10) : '—';
    body.innerHTML += `<tr>
      <td>${dt}</td>
      <td>${donor}</td>
      <td>${d.recipient_name || '—'}</td>
      <td>${shortTeam(d.team_name)}</td>
      <td class="text-right">${moneyFull(d.amount)}</td>
    </tr>`;
  });
  renderPagination(key, donations.length, page, $('#pag-donations'));
}

// ── CSV Export ──

function downloadCSV(rows, headers, filename) {
  const escape = v => {
    const s = String(v == null ? '' : v);
    return s.includes(',') || s.includes('"') || s.includes('\n') ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const lines = [headers.map(escape).join(',')];
  rows.forEach(r => lines.push(r.map(escape).join(',')));
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportMembers() {
  const data = paginators.members ? paginators.members.data : [];
  if (!data.length) return;
  const headers = ['Name', 'Sub-Team', 'Type', 'Ride', 'Committed', 'Raised (2026)', 'All-Time Raised', 'Tags', 'Captain'];
  const rows = data.map(m => [
    m.name,
    shortTeam(m.team_name),
    memberType(m),
    m.route_names || m.ride_type || '',
    m.committed_amount || 0,
    m.raised || 0,
    m.all_time_raised || 0,
    (() => { try { return JSON.parse(m.tags||'[]').join(', '); } catch(e) { return ''; } })(),
    m.is_captain ? 'Yes' : ''
  ]);
  downloadCSV(rows, headers, 'huntington-members.csv');
}

function exportDonors() {
  const data = paginators.donors ? paginators.donors.data : [];
  if (!data.length) return;
  const headers = ['Donor', 'Total', 'Transactions'];
  const rows = data.map(d => [d.donor, d.total || 0, d.cnt || 0]);
  downloadCSV(rows, headers, 'huntington-donors.csv');
}

function exportCompanies() {
  const data = paginators.companies ? paginators.companies.data : [];
  if (!data.length) return;
  const headers = ['Company', 'Total', 'Donors', 'Recipients', 'Transactions'];
  const rows = data.map(c => [c.company, c.total || 0, c.donor_count || 0, c.recipient_count || 0, c.donation_count || 0]);
  downloadCSV(rows, headers, 'huntington-companies.csv');
}

function exportDonations() {
  const data = paginators.donations ? paginators.donations.data : [];
  if (!data.length) return;
  const headers = ['Date', 'Donor', 'Recipient', 'Team', 'Amount'];
  const rows = data.map(d => [
    d.date ? d.date.substring(0, 10) : '',
    d.anonymous_to_public ? (d.recognition_name || 'Anonymous') : (d.donor_name || d.recognition_name || ''),
    d.recipient_name || '',
    shortTeam(d.team_name),
    d.amount || 0
  ]);
  downloadCSV(rows, headers, 'huntington-donations.csv');
}

// ── Infographic helpers ──
const LAST_YEAR_TOTAL = 5009310;  // Team Huntington 2025 final raised (from impact report)
const REGISTRATION_OPEN = new Date(2026, 2, 4);  // Mar 4, 2026 — opening registration day
const RIDE_WEEKEND = new Date(2026, 7, 1);        // Aug 1, 2026 — Ride Weekend
const FUNDRAISING_CLOSE = new Date(2026, 9, 15);  // Oct 15, 2026 — fundraising close date
const CAMPAIGN_START = REGISTRATION_OPEN;
const CAMPAIGN_END = FUNDRAISING_CLOSE;
let _computedTargets = {};

// 2025 actual sub-team participant data (for prior-year benchmarking display)
const LAST_YEAR_SUBTEAMS = {
  'Audit': { riders: 15, challengers: 7, volunteers: 6, total: 28 },
  'Commercial, CRE, and Capital Markets': { riders: 177, challengers: 62, volunteers: 82, total: 321 },
  'Communications': { riders: 9, challengers: 2, volunteers: 1, total: 12 },
  'Consumer Regional Bank': { riders: 813, challengers: 241, volunteers: 632, total: 1686 },
  'Corporate Operations': { riders: 106, challengers: 48, volunteers: 71, total: 225 },
  'Credit, Collections, and Financial Recovery Group': { riders: 49, challengers: 18, volunteers: 24, total: 91 },
  'Finance and Strategy': { riders: 73, challengers: 16, volunteers: 42, total: 131 },
  'Friends, Family, Retirees, and Alumni': { riders: 118, challengers: 4, volunteers: 25, total: 147 },
  'Human Resources': { riders: 40, challengers: 17, volunteers: 51, total: 108 },
  'Legal & Public Affairs': { riders: 14, challengers: 5, volunteers: 26, total: 45 },
  'Office of Inclusion': { riders: 4, challengers: 1, volunteers: 1, total: 6 },
  'Payments & TM': { riders: 54, challengers: 26, volunteers: 46, total: 126 },
  'Risk': { riders: 47, challengers: 18, volunteers: 54, total: 119 },
  'Tech/M&A and Cyber': { riders: 185, challengers: 86, volunteers: 173, total: 444 },
};
// 2026 goals set by team leadership (from BU goals spreadsheet):
const GOALS_2026 = { riders: 2100, challengers: 547, volunteers: 1500 };

// 2026 per-sub-team goals (rider funds + challenger funds + vendor funds = total BU fundraising)
const GOALS_2026_SUBTEAMS = {
  'Audit': { riders: 19, challengers: 7, funds: 57651 },
  'Commercial, CRE, and Capital Markets': { riders: 221, challengers: 64, funds: 726864 },
  'Communications': { riders: 11, challengers: 2, funds: 22182 },
  'Consumer Regional Bank': { riders: 1016, challengers: 236, funds: 1958856 },
  'Corporate Operations': { riders: 133, challengers: 49, funds: 735662 },
  'Credit, Collections, and Financial Recovery Group': { riders: 61, challengers: 17, funds: 192489 },
  'Finance and Strategy': { riders: 91, challengers: 17, funds: 316231 },
  'Friends, Family, Retirees, and Alumni': { riders: 117, challengers: 4, funds: 171647 },
  'Human Resources': { riders: 50, challengers: 17, funds: 158489 },
  'Legal & Public Affairs': { riders: 18, challengers: 4, funds: 199233 },
  'Office of Inclusion': { riders: 5, challengers: 1, funds: 16605 },
  'Payments & TM': { riders: 68, challengers: 27, funds: 161571 },
  'Risk': { riders: 59, challengers: 19, funds: 127397 },
  'Tech/M&A and Cyber': { riders: 231, challengers: 82, funds: 1145146 },
};

function computeSmartTargets(bundle) {
  const { overview, teamBreakdown, teams } = bundle;
  const parentGoal = overview.goal || 5990023;

  // Overall Team Huntington 2026 goals
  const allTargets = { funds: null, riders: GOALS_2026.riders, challengers: GOALS_2026.challengers, volunteers: GOALS_2026.volunteers };

  // 2025 grand totals for proportional volunteer distribution (no volunteer goals per BU yet)
  const LY_TOTALS = { volunteers: 1240 };

  const targets = { '__all__': allTargets };

  teamBreakdown.forEach(t => {
    const short = shortTeam(t.name);
    const buGoal = GOALS_2026_SUBTEAMS[short];
    const ly = LAST_YEAR_SUBTEAMS[short];

    if (buGoal) {
      // Use actual 2026 BU goals for riders, challengers, and funds
      targets[t.name] = {
        funds: buGoal.funds,
        riders: buGoal.riders,
        challengers: buGoal.challengers,
        // Distribute volunteer goal proportionally from 2025 data (no per-BU volunteer goals yet)
        volunteers: ly ? Math.max(Math.round(GOALS_2026.volunteers * (ly.volunteers / LY_TOTALS.volunteers)), ly.volunteers > 0 ? 1 : 0) : 0,
      };
    } else {
      // Fallback for unknown sub-teams
      targets[t.name] = {
        funds: 0, riders: 1, challengers: 0, volunteers: 0,
      };
    }
  });

  // Fix rounding so volunteer sub-team goals sum exactly to the parent goal
  const teamKeys = teamBreakdown.map(t => t.name);
  ['volunteers'].forEach(cat => {
    const goal = GOALS_2026[cat];
    if (!goal) return;
    let sum = 0;
    teamKeys.forEach(k => { sum += targets[k][cat]; });
    let diff = goal - sum;
    const sorted = [...teamKeys].sort((a, b) => targets[b][cat] - targets[a][cat]);
    let i = 0;
    while (diff !== 0) {
      const step = diff > 0 ? 1 : -1;
      targets[sorted[i % sorted.length]][cat] += step;
      diff -= step;
      i++;
    }
  });

  return targets;
}

function getLastYearEstimate(selectedTeam, bundle) {
  if (selectedTeam === '__all__') {
    return { funds: LAST_YEAR_TOTAL, riders: 1707, challengers: 556, volunteers: 1240, isEstimate: false };
  }
  const short = shortTeam(selectedTeam);
  const ly = LAST_YEAR_SUBTEAMS[short];

  const { teamBreakdown, teams } = bundle;
  let totalPrior = 0;
  const teamPriors = {};
  teamBreakdown.forEach(t => {
    const td = teams.find(x => x.name === t.name);
    const allTime = td ? td.all_time_raised : 0;
    const current = t.total_raised || 0;
    const prior = Math.max(allTime - current, 0);
    teamPriors[t.name] = prior;
    totalPrior += prior;
  });
  const share = totalPrior > 0 ? (teamPriors[selectedTeam] || 0) / totalPrior : 0;
  const fundsEst = Math.round(LAST_YEAR_TOTAL * share);

  if (ly) {
    return { funds: fundsEst, riders: ly.riders, challengers: ly.challengers, volunteers: ly.volunteers, isEstimate: false, fundsIsEstimate: true };
  }
  return { funds: fundsEst, riders: 0, challengers: 0, volunteers: 0, isEstimate: true, fundsIsEstimate: true };
}

function moneyShort(n) {
  n = Number(n);
  if (n >= 1000000) return '$' + (n/1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 10000) return '$' + Math.round(n/1000) + 'K';
  if (n >= 1000) return '$' + (n/1000).toFixed(1).replace(/\.0$/, '') + 'K';
  return '$' + n.toLocaleString();
}

let _infographicBundle = null;

function renderInfographics(bundle, selectedTeam) {
  const { overview, teamBreakdown, teams, donations } = bundle;
  let fundsRaised, fundsGoal, riders, challengers, volunteers, survivors, avgDonation;

  if (selectedTeam === '__all__') {
    fundsRaised = overview.raised;
    fundsGoal = overview.goal;
    riders = overview.riders || 0;
    challengers = overview.challengers || 0;
    volunteers = overview.volunteers || 0;
    survivors = overview.cancer_survivors;
    avgDonation = overview.donations_count > 0 ? overview.total_donated / overview.donations_count : 0;
  } else {
    const team = teamBreakdown.find(t => t.name === selectedTeam);
    if (team) {
      fundsRaised = team.total_raised;
      const teamData = teams.find(t => t.name === selectedTeam);
      fundsGoal = teamData ? teamData.goal : 0;
      riders = team.riders;
      challengers = team.challengers;
      volunteers = team.volunteers;
      survivors = team.survivors;
      const teamDons = donations.filter(d => d.team_name === selectedTeam);
      const teamDonTotal = teamDons.reduce((s, d) => s + (d.amount || 0), 0);
      avgDonation = teamDons.length > 0 ? teamDonTotal / teamDons.length : 0;
    } else {
      fundsRaised = 0; fundsGoal = 0; riders = 0;
      challengers = 0; volunteers = 0; survivors = 0; avgDonation = 0;
    }
  }

  const targets = _computedTargets[selectedTeam] || _computedTargets['__all__'] || { funds: null, riders: 2100, challengers: 547, volunteers: 1500 };
  const fundsTarget = targets.funds || fundsGoal;

  const ly = getLastYearEstimate(selectedTeam, bundle);

  // ── Timeline calculations ──
  const today = new Date();
  const regDay = Math.max(1, Math.ceil((today - REGISTRATION_OPEN) / (1000*60*60*24)) + 1);
  const daysToRide = Math.max(0, Math.ceil((RIDE_WEEKEND - today) / (1000*60*60*24)));
  const daysToClose = Math.max(0, Math.ceil((FUNDRAISING_CLOSE - today) / (1000*60*60*24)));
  const campaignLength = Math.ceil((FUNDRAISING_CLOSE - REGISTRATION_OPEN) / (1000*60*60*24));
  const campaignDayNum = Math.max(0, Math.ceil((today - CAMPAIGN_START) / (1000*60*60*24)));
  const expectedPct = (regDay / campaignLength * 100);

  // ── Build stat chips per metric ──
  function buildChips(key, selectedTeam, bundle) {
    const { overview, teamBreakdown, donations } = bundle;
    if (selectedTeam === '__all__') {
      if (key === 'funds') {
        // Show commitment breakdown: total, high rollers, standard
        return [
          {v: moneyShort(overview.total_committed||0), l: 'Committed'},
          {v: moneyShort(overview.hr_committed||0), l: 'High Rollers'},
          {v: moneyShort(overview.std_committed||0), l: 'Standard'},
        ];
      }
      // Show top 3 sub-teams for other metrics
      const sorted = [...teamBreakdown].sort((a,b) => {
        if (key === 'riders') return (b.riders||0) - (a.riders||0);
        if (key === 'challengers') return (b.challengers||0) - (a.challengers||0);
        return (b.volunteers||0) - (a.volunteers||0);
      });
      return sorted.slice(0,3).map(t => {
        const short = shortTeam(t.name).replace(/^Team Huntington Bank - /,'');
        const abbr = short.length > 12 ? short.substring(0,11) + '…' : short;
        let val;
        if (key === 'riders') val = (t.riders||0).toLocaleString();
        else if (key === 'challengers') val = (t.challengers||0).toLocaleString();
        else val = (t.volunteers||0).toLocaleString();
        return {v: val, l: abbr};
      });
    }
    // Per-team: show context chips matching each metric
    if (key === 'funds') {
      const team = teamBreakdown.find(t => t.name === selectedTeam);
      return [
        {v: moneyShort(team ? team.total_committed||0 : 0), l: 'Committed'},
        {v: moneyShort(team ? team.hr_committed||0 : 0), l: 'High Rollers'},
        {v: moneyShort(team ? team.std_committed||0 : 0), l: 'Standard'},
      ];
    }
    return [
      {v: 'Day ' + regDay, l: 'Campaign'},
      {v: daysToRide + 'd', l: 'To Ride'},
      {v: (riders + challengers + volunteers).toLocaleString(), l: 'Total'},
    ];
  }

  // Per-metric deadlines: funds → Oct 15, participation → Ride Weekend Aug 1
  const fundsDaysTotal = Math.ceil((FUNDRAISING_CLOSE - REGISTRATION_OPEN) / (1000*60*60*24));
  const rideDaysTotal = Math.ceil((RIDE_WEEKEND - REGISTRATION_OPEN) / (1000*60*60*24));
  const fundsDaysLeft = daysToClose;
  const rideDaysLeft = daysToRide;
  const fundsExpectedPct = (regDay / fundsDaysTotal * 100);
  const rideExpectedPct = (regDay / rideDaysTotal * 100);

  const thermos = [
    { key: 'funds', label: 'Funds Raised', current: fundsRaised, goal: fundsTarget, format: moneyShort,
      deadline: 'Fundraising closes Oct 15', daysTotal: fundsDaysTotal, daysLeft: fundsDaysLeft, expected: fundsExpectedPct },
    { key: 'riders', label: 'Riders', current: riders, goal: targets.riders, format: v => v.toLocaleString(),
      deadline: '', daysTotal: rideDaysTotal, daysLeft: rideDaysLeft, expected: rideExpectedPct },
    { key: 'challengers', label: 'Challengers', current: challengers, goal: targets.challengers, format: v => v.toLocaleString(),
      deadline: '', daysTotal: rideDaysTotal, daysLeft: rideDaysLeft, expected: rideExpectedPct },
    { key: 'volunteers', label: 'Volunteers', current: volunteers, goal: targets.volunteers, format: v => v.toLocaleString(),
      deadline: '', daysTotal: rideDaysTotal, daysLeft: rideDaysLeft, expected: rideExpectedPct },
  ];

  const grid = document.getElementById('thermo-grid');
  grid.innerHTML = '';

  thermos.forEach(t => {
    const pct = t.goal > 0 ? (t.current / t.goal * 100) : 0;
    const fillPct = Math.min(pct, 100);
    const ahead = pct > t.expected;
    const chips = buildChips(t.key, selectedTeam, bundle);

    const card = document.createElement('div');
    card.className = 'thermo-card';
    card.innerHTML = `
      <div class="thermo-card-header">
        <div class="thermo-label">${t.label}</div>
        <div class="pct-badge">${pct.toFixed(1)}%</div>
      </div>
      <div class="thermo-value">${t.format(t.current)}</div>
      <div class="thermo-goal">of <strong>${t.goal > 0 ? t.format(t.goal) : '—'}</strong> goal</div>
      <div class="thermo-bar-wrap">
        <div class="thermo-bar-bg">
          <div class="thermo-bar-fill" style="width:0%" data-target="${fillPct}%"></div>
        </div>
        <div class="thermo-milestones">
          <div class="thermo-milestone" style="left:25%">25%</div>
          <div class="thermo-milestone" style="left:50%">50%</div>
          <div class="thermo-milestone" style="left:75%">75%</div>
        </div>
      </div>
      <div class="stat-chips">
        ${chips.map(c => `<div class="stat-chip"><div class="stat-chip-val">${c.v}</div><div class="stat-chip-label">${c.l}</div></div>`).join('')}
      </div>
      <div class="pace-row">
        <span class="pace-dot ${ahead ? 'pace-ahead' : 'pace-behind'}"></span>
        <span>${ahead ? 'Ahead of pace' : 'Building momentum'}</span>
        <span style="color:#bbb">· ${t.daysLeft}d left</span>
      </div>
      <div style="margin-top:8px;font-size:11px;color:#aaa;font-style:italic;">${t.deadline}</div>
    `;
    grid.appendChild(card);
  });

  // Animate bars on render
  requestAnimationFrame(() => {
    setTimeout(() => {
      grid.querySelectorAll('.thermo-bar-fill').forEach(bar => {
        bar.style.width = bar.dataset.target;
      });
    }, 50);
  });

  // ── Summary stat cards ──
  const summary = document.getElementById('infographic-summary');
  summary.innerHTML = `
    <div class="summary-card">
      <div class="summary-value">${survivors}</div>
      <div class="summary-label">Cancer Survivors</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">${overview.high_rollers}</div>
      <div class="summary-label">High Rollers</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">${daysToRide > 0 ? daysToRide : 'Ride Day!'}</div>
      <div class="summary-label">Days to Ride Weekend</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">${daysToClose}</div>
      <div class="summary-label">Days to Fundraising Close</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">${moneyShort(Math.round(avgDonation))}</div>
      <div class="summary-label">Avg Donation</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">Day ${regDay}</div>
      <div class="summary-label">of Campaign</div>
    </div>
  `;

  // ── Team Goals Summary Table ──
  renderTeamGoalsTable(bundle);
}

function miniBar(current, goal) {
  if (!goal || goal <= 0) return '';
  const pct = Math.min(Math.round(current / goal * 100), 100);
  return `<span class="mini-bar"><span class="mini-bar-fill" style="width:${pct}%"></span></span>`;
}

function goalCell(current, goal) {
  if (!goal) return `<td class="text-center goal-cell">—</td><td class="text-center goal-cell">—</td>`;
  const pct = goal > 0 ? Math.round(current / goal * 100) : 0;
  const cls = pct >= 100 ? 'goal-over' : 'goal-under';
  return `<td class="text-center goal-cell"><span class="${cls}">${current}</span> ${miniBar(current, goal)}</td><td class="text-center goal-cell">${goal}</td>`;
}

function renderTeamGoalsTable(bundle) {
  const { teamBreakdown, teams } = bundle;
  const targets = [
    { tbody: document.getElementById('table-team-goals'), tfoot: document.getElementById('table-team-goals-totals') },
    { tbody: document.getElementById('table-team-goals-teams'), tfoot: document.getElementById('table-team-goals-teams-totals') },
  ];

  let totR=0, totRG=0, totC=0, totCG=0, totV=0, totVG=0, totFunds=0, totCommit=0, totFG=0;
  let rowsHtml = '';

  const sorted = [...teamBreakdown].sort((a,b) => (b.total || 0) - (a.total || 0));
  sorted.forEach(t => {
    const tgt = _computedTargets[t.name] || {};
    const r = t.riders || 0, c = t.challengers || 0, v = t.volunteers || 0;
    const rg = tgt.riders || 0, cg = tgt.challengers || 0, vg = tgt.volunteers || 0;
    const funds = t.total_raised || 0;
    const committed = t.total_committed || 0;
    const fg = tgt.funds || 0;
    const fundPct = fg > 0 ? Math.round(funds / fg * 100) : 0;

    totR += r; totRG += rg; totC += c; totCG += cg; totV += v; totVG += vg;
    totFunds += funds; totCommit += committed; totFG += fg;

    rowsHtml += `<tr>
      <td>${shortTeam(t.name)}</td>
      ${goalCell(r, rg)}
      ${goalCell(c, cg)}
      ${goalCell(v, vg)}
      <td class="text-right">${moneyShort(funds)}</td>
      <td class="text-right">${moneyShort(committed)}</td>
      <td class="text-right">${moneyShort(fg)}</td>
      <td class="text-center">${fundPct}%</td>
    </tr>`;
  });

  const allFundPct = totFG > 0 ? Math.round(totFunds / totFG * 100) : 0;
  const footHtml = `<tr>
    <td>TOTAL</td>
    <td class="text-center">${totR}</td><td class="text-center">${totRG}</td>
    <td class="text-center">${totC}</td><td class="text-center">${totCG}</td>
    <td class="text-center">${totV}</td><td class="text-center">${totVG}</td>
    <td class="text-right">${moneyShort(totFunds)}</td>
    <td class="text-right">${moneyShort(totCommit)}</td>
    <td class="text-right">${moneyShort(totFG)}</td>
    <td class="text-center">${allFundPct}%</td>
  </tr>`;

  targets.forEach(({ tbody, tfoot }) => {
    if (tbody) { tbody.innerHTML = rowsHtml; }
    if (tfoot) { tfoot.innerHTML = footHtml; }
  });
}

loadDashboard();

// ── Data Guide modal ──
(function() {
  const DATA_GUIDE_HTML = `
<h3>Data Pipeline</h3>
<ul>
  <li><strong>Source:</strong> Pelotonia public API (<code>pelotonia-p3-middleware-production.azurewebsites.net</code>)</li>
  <li><strong>Scraper:</strong> Runs daily at ~6:00 AM UTC in incremental mode (~30 API calls, ~19 seconds)</li>
  <li><strong>Storage:</strong> SQLite database with tables: <code>teams</code>, <code>members</code>, <code>donations</code>, <code>member_routes</code>, <code>daily_snapshots</code>, <code>events</code>, <code>routes</code>, <code>rides</code>, <code>donor_identities</code></li>
  <li><strong>Cache:</strong> Dashboard bundle rebuilds only when the database file modification time changes</li>
</ul>

<h3>Why Rider Counts Differ</h3>
<p>You may notice different rider numbers in different places. Here's why:</p>
<ul>
  <li><strong>"Signature Riders" KPI</strong> = distinct members with a route selection in the <code>member_routes</code> table (ride_type='signature')</li>
  <li><strong>"RIDERS" goal</strong> = members with <code>is_rider=1</code> flag from their profile API data</li>
  <li><strong>Team breakdown charts</strong> = mutually exclusive classification: rider &gt; challenger &gt; volunteer &gt; registered only</li>
  <li>A member can be flagged <code>is_rider</code> without selecting a route yet, or vice versa</li>
  <li><strong>Challengers overlap:</strong> Some members have both <code>is_rider</code> and <code>is_challenger</code> flags. Raw challenger count may differ from mutually exclusive count</li>
</ul>

<h3>Metric Glossary</h3>
<table class="def-table">
  <tr><td>Raised (2026)</td><td>Sum of all donation records for team members in 2026</td></tr>
  <tr><td>All-Time Raised</td><td>Cumulative fundraising from member profiles across all Pelotonia years</td></tr>
  <tr><td>Members</td><td>Total registered members across all sub-teams</td></tr>
  <tr><td>First Year Riders</td><td>Members tagged with &ldquo;1 year&rdquo; &mdash; participating in Pelotonia for the first time</td></tr>
  <tr><td>Signature Riders</td><td>Distinct members who selected a Signature Ride route</td></tr>
  <tr><td>Gravel Riders</td><td>Distinct members who selected a Gravel Day route</td></tr>
  <tr><td>Cancer Survivors</td><td>Members with <code>is_cancer_survivor=1</code> in their profile</td></tr>
  <tr><td>High Rollers</td><td>Members with High Roller tag ($4,000+ commitment)</td></tr>
  <tr><td>RIDERS (goal)</td><td>Members with <code>is_rider=1</code> profile flag</td></tr>
  <tr><td>CHALLENGERS (goal)</td><td>Members with <code>is_challenger=1</code> profile flag (raw count, not mutually exclusive)</td></tr>
  <tr><td>VOLUNTEERS (goal)</td><td>Members with <code>is_volunteer=1</code> profile flag</td></tr>
  <tr><td>Funds Raised (goal)</td><td>Team raised amount vs fundraising goal from API (or override)</td></tr>
  <tr><td>Avg Donation</td><td>Total donated divided by number of donation records</td></tr>
  <tr><td>Days Until Ride</td><td>Calendar days until Ride Weekend (August 1, 2026)</td></tr>
</table>

<h3>Data Quality Notes</h3>
<ul>
  <li><strong>Donation totals vs profile raised:</strong> Sum of donation records may not exactly match a member's "raised" amount on their profile due to timing, offline donations, or matching gifts</li>
  <li><strong>Multi-route riders:</strong> When a member selects multiple routes, their fundraising is split proportionally across routes in the routes table</li>
  <li><strong>New members:</strong> Recently registered members may show all flags as 0 until their team captain approves them</li>
  <li><strong>Stale members:</strong> Members who leave the team are retained in the database with a stale <code>last_scraped</code> date</li>
  <li><strong>Goal overrides:</strong> The default team fundraising goal comes from the API. Overrides set in the database may be reset after a full scraper run (known issue)</li>
</ul>
`;

  const guideBtn = document.getElementById('guide-btn');
  const guideModal = document.getElementById('guide-modal');
  const guideClose = document.getElementById('guide-modal-close');
  const guideBody = document.getElementById('guide-modal-body');

  if (guideBtn && guideModal) {
    guideBtn.addEventListener('click', () => {
      guideBody.innerHTML = DATA_GUIDE_HTML;
      guideModal.classList.add('active');
    });
    guideClose.addEventListener('click', () => guideModal.classList.remove('active'));
    guideModal.addEventListener('click', e => {
      if (e.target === e.currentTarget) guideModal.classList.remove('active');
    });
  }
})();

// ── Report Tab Renderer ──
function renderReport(bundle, period, subteamFilter) {
  const el = document.getElementById('report-container');
  if (!el) return;
  const isWeekly = period === 'weekly';
  const lookbackDays = isWeekly ? 7 : 1;
  const filterAll = !subteamFilter || subteamFilter === '__all__';

  const { overview, teamBreakdown, signupTimeline, subteamSnapshots } = bundle;

  // When filtering by sub-team, derive KPIs from teamBreakdown + subteamSnapshots
  const filteredTeam = !filterAll ? teamBreakdown.find(t => t.name === subteamFilter) : null;

  const snap = signupTimeline || [];
  const today = snap.length ? snap[snap.length - 1] : null;

  // Find comparison snapshot
  let compare = null;
  if (snap.length > lookbackDays) {
    compare = snap[snap.length - 1 - lookbackDays];
  } else if (snap.length > 1) {
    compare = snap[0];
  }

  // Sub-team deltas from subteamSnapshots
  const stSnaps = subteamSnapshots || [];
  const dates = [...new Set(stSnaps.map(s => s.snapshot_date))].sort();
  const latestDate = dates.length ? dates[dates.length - 1] : null;
  let compareDate = null;
  if (dates.length > lookbackDays) {
    compareDate = dates[dates.length - 1 - lookbackDays];
  } else if (dates.length > 1) {
    compareDate = dates[0];
  }

  const moversMap = {};
  stSnaps.forEach(s => {
    if (s.snapshot_date === latestDate) {
      if (!moversMap[s.name]) moversMap[s.name] = {};
      moversMap[s.name].raised_now = s.raised || 0;
      moversMap[s.name].members_now = s.members_count || 0;
    }
    if (compareDate && s.snapshot_date === compareDate) {
      if (!moversMap[s.name]) moversMap[s.name] = {};
      moversMap[s.name].raised_prev = s.raised || 0;
      moversMap[s.name].members_prev = s.members_count || 0;
    }
  });

  // Compute deltas — use sub-team snapshot if filtering
  let raisedDelta = 0, membersDelta = 0;
  if (!filterAll && moversMap[subteamFilter]) {
    const d = moversMap[subteamFilter];
    raisedDelta = (d.raised_now || 0) - (d.raised_prev || 0);
    membersDelta = (d.members_now || 0) - (d.members_prev || 0);
  } else if (filterAll) {
    raisedDelta = today && compare ? (today.raised || 0) - (compare.raised || 0) : 0;
    membersDelta = today && compare ? (today.members_count || 0) - (compare.members_count || 0) : 0;
  }

  const movers = Object.entries(moversMap)
    .map(([name, d]) => ({
      name,
      raised_delta: (d.raised_now || 0) - (d.raised_prev || 0),
      members_delta: (d.members_now || 0) - (d.members_prev || 0),
    }))
    .filter(m => m.raised_delta > 0)
    .sort((a, b) => b.raised_delta - a.raised_delta)
    .slice(0, isWeekly ? 5 : 3);

  // Participation data — from sub-team if filtered, else from overview
  let riders, challengers, volunteers, membersTotal, highRollers, survivors, firstYear, raised, goal, committed, hrCommitted, stdCommitted;
  if (filteredTeam) {
    riders = filteredTeam.riders || 0;
    challengers = filteredTeam.challengers || 0;
    volunteers = filteredTeam.volunteers || 0;
    membersTotal = filteredTeam.total || 0;
    highRollers = filteredTeam.high_rollers || 0;
    survivors = filteredTeam.survivors || 0;
    firstYear = filteredTeam.first_year || 0;
    raised = filteredTeam.total_raised || 0;
    const sn = shortTeam(subteamFilter);
    const stGoals = GOALS_2026_SUBTEAMS[sn] || {};
    goal = stGoals.funds || 0;
    committed = filteredTeam.total_committed || 0;
    hrCommitted = filteredTeam.hr_committed || 0;
    stdCommitted = filteredTeam.std_committed || 0;
  } else {
    riders = overview.riders || 0;
    challengers = overview.challengers || 0;
    volunteers = overview.volunteers || 0;
    membersTotal = overview.members_count || 0;
    highRollers = overview.high_rollers || 0;
    survivors = overview.cancer_survivors || 0;
    firstYear = overview.first_year || 0;
    raised = overview.raised || 0;
    goal = overview.goal || 6000000;
    committed = overview.total_committed || 0;
    hrCommitted = overview.hr_committed || 0;
    stdCommitted = overview.std_committed || 0;
  }

  const campaignStart = new Date(2026, 2, 4);
  const rideDay = new Date(2026, 7, 1);
  const now = new Date();
  const campaignDay = Math.max(Math.floor((now - campaignStart) / 86400000), 0);
  const daysToRide = Math.max(Math.floor((rideDay - now) / 86400000), 0);

  const pctFmt = (cur, g) => g ? Math.min(cur / g * 100, 100).toFixed(1) : '0.0';
  const deltaHtml = (val, isMoney) => {
    if (val > 0) return '<span style="color:#44D62C;font-weight:700">+' + (isMoney ? moneyShort(val) : val.toLocaleString()) + '</span>';
    if (val < 0) return '<span style="color:#e74c3c;font-weight:700">-' + (isMoney ? moneyShort(Math.abs(val)) : Math.abs(val).toLocaleString()) + '</span>';
    return '<span style="color:#888">&mdash;</span>';
  };

  const periodLabel = isWeekly ? 'Weekly Report' : 'Daily Report';
  const teamLabel = filterAll ? 'Team Huntington' : shortTeam(subteamFilter);
  let dateStr;
  if (isWeekly) {
    const ws = new Date(now - 7 * 86400000);
    dateStr = 'Week of ' + ws.toLocaleDateString('en-US',{month:'short',day:'numeric'}) + ' &mdash; ' + now.toLocaleDateString('en-US',{month:'short',day:'numeric'}) + ', ' + now.getFullYear();
  } else {
    dateStr = now.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'});
  }

  function cardHtml(label, current, goalStr, pct, delta, chips) {
    const barColor = pct >= 10 ? '#44D62C' : '#6EF056';
    return '<td style="width:50%;padding:8px;vertical-align:top"><table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#fff;border-radius:12px;border:1px solid #e8ece9;overflow:hidden"><tr><td style="padding:0"><div style="height:3px;background:linear-gradient(90deg,#00471F,#44D62C)"></div></td></tr><tr><td style="padding:20px 20px 16px"><table cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#888;font-weight:600">' + label + '</td><td align="right" style="font-size:13px;font-weight:800;color:#00471F;background:rgba(68,214,44,0.1);padding:2px 8px;border-radius:12px">' + pct.toFixed(1) + '%</td></tr></table><div style="font-size:36px;font-weight:800;color:#00471F;line-height:1.1;margin-top:8px">' + current + '</div><div style="font-size:12px;color:#aaa;margin-top:4px">of <b style="color:#666">' + goalStr + '</b> goal ' + delta + '</div><div style="margin-top:14px;height:10px;border-radius:5px;background:#e8ece9;overflow:hidden"><div style="height:100%;width:' + pct.toFixed(1) + '%;border-radius:5px;background:linear-gradient(90deg,#00471F,' + barColor + ')"></div></div><table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:12px"><tr>' + chips.map(([l,v]) => '<td style="text-align:center;padding:6px 2px;background:#f7f8f9;border-radius:6px"><div style="font-size:14px;font-weight:800;color:#00471F">' + v + '</div><div style="font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.3px;margin-top:1px">' + l + '</div></td>').join('') + '</tr></table></td></tr></table></td>';
  }

  // Use sub-team goals if filtered, else parent goals
  let ridersGoal = GOALS_2026.riders, challGoal = GOALS_2026.challengers, volGoal = GOALS_2026.volunteers;
  if (filteredTeam) {
    const sn = shortTeam(subteamFilter);
    const stG = GOALS_2026_SUBTEAMS[sn] || {};
    ridersGoal = stG.riders || riders;
    challGoal = stG.challengers || challengers;
    volGoal = volunteers || 1;
  }
  const fundsPct = parseFloat(pctFmt(raised, goal));
  const ridersPct = parseFloat(pctFmt(riders, ridersGoal));
  const challPct = parseFloat(pctFmt(challengers, challGoal));
  const volPct = parseFloat(pctFmt(volunteers, volGoal));

  let moversHtml = '';
  if (movers.length) {
    const moversLabel = isWeekly ? 'Top Movers This Week' : 'Top Movers Today';
    moversHtml = '<div style="margin-top:24px"><div style="font-size:16px;font-weight:700;color:#00471F;margin-bottom:8px">' + moversLabel + '</div><table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#fff;border:1px solid #e8ece9;border-radius:8px;overflow:hidden"><tr style="background:#f7f8f9"><th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#888;font-weight:600">Sub-Team</th><th style="padding:8px 12px;text-align:right;font-size:11px;text-transform:uppercase;color:#888;font-weight:600">Raised</th><th style="padding:8px 12px;text-align:right;font-size:11px;text-transform:uppercase;color:#888;font-weight:600">Members</th></tr>';
    movers.forEach(m => {
      moversHtml += '<tr><td style="padding:6px 12px;font-size:13px;color:#333">' + shortTeam(m.name) + '</td><td align="right" style="padding:6px 12px;font-size:13px;font-weight:700;color:#00471F">' + deltaHtml(m.raised_delta, true) + '</td><td align="right" style="padding:6px 12px;font-size:13px;color:#555">' + deltaHtml(m.members_delta, false) + '</td></tr>';
    });
    moversHtml += '</table></div>';
  }

  // Sub-team table
  let teamTableHtml = '<div style="margin-top:24px"><div style="font-size:16px;font-weight:700;color:#00471F;margin-bottom:8px">Participation by Sub-Team</div><table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#fff;border:1px solid #e8ece9;border-radius:8px;overflow:hidden;border-collapse:collapse"><tr style="background:#f7f8f9"><th style="padding:8px 10px;text-align:left;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Sub-Team</th><th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Riders</th><th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Chall</th><th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Vol</th><th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">1st Yr</th><th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Total</th><th style="padding:8px 6px;text-align:right;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Raised</th><th style="padding:8px 6px;text-align:right;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Goal</th><th style="padding:8px 6px;text-align:right;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Committed</th><th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">% Goal</th></tr>';

  // Sort teamBreakdown by committed desc, filter if sub-team selected
  const tbFiltered = filterAll ? teamBreakdown : teamBreakdown.filter(t => t.name === subteamFilter);
  const tbSorted = [...tbFiltered].sort((a,b) => (b.total_committed||0) - (a.total_committed||0));
  tbSorted.forEach(t => {
    const sn = shortTeam(t.name);
    const stGoals = GOALS_2026_SUBTEAMS[sn] || {};
    const fundGoal = stGoals.funds || 0;
    const fundPct = fundGoal ? Math.round((t.total_raised||0)/fundGoal*100)+'%' : '&mdash;';
    const fundGoalStr = fundGoal ? moneyShort(fundGoal) : '&mdash;';
    teamTableHtml += '<tr style="border-bottom:1px solid #f0f0f0"><td style="padding:8px 10px;font-size:12px;color:#333;white-space:nowrap">' + sn + '</td><td align="center" style="padding:8px 6px;font-size:12px;color:#333">' + (t.riders||0) + '</td><td align="center" style="padding:8px 6px;font-size:12px;color:#333">' + (t.challengers||0) + '</td><td align="center" style="padding:8px 6px;font-size:12px;color:#333">' + (t.volunteers||0) + '</td><td align="center" style="padding:8px 6px;font-size:12px;color:#888">' + (t.first_year||0) + '</td><td align="center" style="padding:8px 6px;font-size:12px;color:#333;font-weight:600">' + (t.total||0) + '</td><td align="right" style="padding:8px 6px;font-size:12px;color:#00471F;font-weight:600">' + moneyShort(t.total_raised||0) + '</td><td align="right" style="padding:8px 6px;font-size:12px;color:#888">' + fundGoalStr + '</td><td align="right" style="padding:8px 6px;font-size:12px;color:#00471F;font-weight:600">' + moneyShort(t.total_committed||0) + '</td><td align="center" style="padding:8px 6px;font-size:11px;color:#888">' + fundPct + '</td></tr>';
  });
  teamTableHtml += '</table></div>';

  el.innerHTML = '<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f4f5f7"><tr><td align="center"><table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px">' +
    // Header
    '<tr><td style="background:linear-gradient(135deg,#00471F,#0E1411);border-radius:12px 12px 0 0;padding:24px 28px;text-align:center"><div style="font-size:22px;font-weight:800;color:#44D62C;margin-bottom:4px">' + teamLabel + ' ' + periodLabel + '</div><div style="font-size:13px;color:rgba(255,255,255,0.6)">' + dateStr + ' &middot; Day ' + campaignDay + ' of Campaign</div></td></tr>' +
    // Summary bar
    '<tr><td style="background:#00471F;padding:12px 28px"><table cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td align="center" style="padding:4px 8px"><div style="font-size:20px;font-weight:800;color:#44D62C">' + money(raised) + '</div><div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Raised ' + deltaHtml(raisedDelta, true) + '</div></td><td align="center" style="padding:4px 8px"><div style="font-size:20px;font-weight:800;color:rgba(255,255,255,0.8)">' + money(goal) + '</div><div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Goal</div></td><td align="center" style="padding:4px 8px"><div style="font-size:20px;font-weight:800;color:#44D62C">' + membersTotal.toLocaleString() + '</div><div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Members ' + deltaHtml(membersDelta, false) + '</div></td><td align="center" style="padding:4px 8px"><div style="font-size:20px;font-weight:800;color:#44D62C">' + highRollers + '</div><div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">High Rollers</div></td><td align="center" style="padding:4px 8px"><div style="font-size:20px;font-weight:800;color:#44D62C">' + survivors + '</div><div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Survivors</div></td><td align="center" style="padding:4px 8px"><div style="font-size:20px;font-weight:800;color:#44D62C">' + firstYear + '</div><div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">1st Year</div></td></tr></table></td></tr>' +
    // Cards
    '<tr><td style="background:#f4f5f7;padding:16px 12px 0"><table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>' + cardHtml('Funds Raised', money(raised), money(goal), fundsPct, deltaHtml(raisedDelta, true), [['Committed', moneyShort(committed)], ['High Rollers', moneyShort(hrCommitted)], ['Standard', moneyShort(stdCommitted)]]) + cardHtml('Riders', riders.toLocaleString(), ridersGoal.toLocaleString(), ridersPct, deltaHtml(membersDelta, false), [['Day', ''+campaignDay], ['To Ride', daysToRide+'d'], ['Total', membersTotal.toLocaleString()]]) + '</tr><tr><td colspan="2" style="height:8px"></td></tr><tr>' + cardHtml('Challengers', challengers.toLocaleString(), challGoal.toLocaleString(), challPct, '', [['Day', ''+campaignDay], ['To Ride', daysToRide+'d'], ['Total', membersTotal.toLocaleString()]]) + cardHtml('Volunteers', volunteers.toLocaleString(), volGoal.toLocaleString(), volPct, '', [['Day', ''+campaignDay], ['To Ride', daysToRide+'d'], ['Total', membersTotal.toLocaleString()]]) + '</tr></table></td></tr>' +
    // Movers + Sub-team table
    '<tr><td style="background:#f4f5f7;padding:0 16px 24px">' + moversHtml + teamTableHtml + '</td></tr>' +
    '</table></td></tr></table>';
}
</script>
</body>
</html>
"""




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pelotonia Dashboard Server")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    print(f"\n  Pelotonia Dashboard → http://localhost:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=False)
