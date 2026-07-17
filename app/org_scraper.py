#!/usr/bin/env python3
"""
Organization Leaderboard Scraper — Pelotonia Top Teams

Fetches aggregate stats for ~31 major Pelotonia organizations (parent teams)
and stores daily snapshots for leaderboard comparison.

Per org: name, members_count, sub_team_count, raised, goal, all_time_raised,
plus participant breakdown (riders, challengers, volunteers).

Rider/challenger/volunteer counts are derived by walking each org's member
tree and reading `participantTypes` from the per-user profile endpoint.
Profiles are cached in `org_member_profiles` so most subsequent runs only
fetch newcomers and entries that have aged past the staleness window.

Usage:
  python org_scraper.py                # Scrape + store today's snapshot
  python org_scraper.py --summary      # Print leaderboard from DB
  python org_scraper.py --skip-profiles  # Skip participant-type scrape
  python org_scraper.py --refresh-all-profiles  # Force re-fetch of every cached profile

Requires: stdlib only (urllib.request, json, sqlite3, time)
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "https://pelotonia-p3-middleware-production.azurewebsites.net/api"
RATE_LIMIT = 0.3  # seconds between API calls
PROFILE_STALE_DAYS = 14  # re-fetch participant types older than this
PAGE_SIZE = 200
MAX_DEPTH = 4  # safety cap on recursive sub-peloton walk

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PELOTONIA_DB", SCRIPT_DIR / "pelotonia_data.db"))

# Hardcoded parent team IDs — these are stable year to year.
# Discovered via API search; only parent orgs (no sub-teams).
ORGS = {
    "a0s3t00000BKX8sAAH": "Team Huntington Bank",
    "a0s3t00000BKX8tAAH": "Team Buckeye",
    "a0s3t00000BKXNOAA5": "JPMorgan Chase",
    "a0s3t00000BKXc9AAH": "Victoria's Secret & PINK",
    "a0s3t00000BKXcBAAX": "Bath and Body Works",
    "a0s3t00000BKY81AAH": "Cardinal Health Peloton",
    "a0s3t00000BKXMmAAP": "AEP Energizers For A Cure",
    "a0s3t00000EKh23AAD": "M/I Homes, Inc",
    "a0s3t00000BKXSmAAP": "Team Safelite",
    "a0s3t00000BKXRlAAP": "Bread Financial",
    "a0s3t00000BKXTbAAP": "The Worthington Companies Foundation",
    "a0s3t00000BKXOBAA5": "Nationwide Children's Hospital",
    "a0s3t00000BKXQgAAP": "Abbott Nutrition",
    "a0s3t00000BKXVaAAP": "Honda Cycling",
    "a0s3t00000BKXQiAAP": "Team ScottsMiracle-Gro",
    "a0s3t00000BKXU7AAP": "Abercrombie and Fitch",
    "a0s3t00000FH4NjAAL": "Adrenal Team Maria",
    "a0s3t00000BKXVCAA5": "Quantum Health Warriors",
    "a0s3t00000BKXR3AAP": "Team Grange",
    "a0s3t00000BKY8AAAX": "Team Honda Marysville",
    "a0s3t00000BKXU1AAP": "WHITE CASTLE CRAVERS",
    "a0s3t00000BKXToAAP": "Owens Corning",
    "a0s3t00000BKXWRAA5": "White Oak Partners Peloton",
    "a0s3t00000BKXSiAAP": "BIG LOTS",
    "a0s3t00000BKXTUAA5": "Coldwell Banker Realty",
    "a0s3t00000BKXWuAAP": "Team Wendy",
    "a0s3t00000EKxVLAA1": "Donaldson Health",
    "a0s3t00000EmmKUAAZ": "Littler Mendelson Team",
    "a0sQj00000DSgWHIA1": "Park National Bank",
    "a0sQj00000Am2plIAB": "Northwest Bank",
    "a0sQj00000DUFOjIAP": "Fahey Bank",
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db(conn):
    """Create tables and run lightweight migrations."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS org_snapshots (
            snapshot_date TEXT NOT NULL,
            team_id TEXT NOT NULL,
            name TEXT,
            members_count INTEGER DEFAULT 0,
            sub_team_count INTEGER DEFAULT 0,
            raised REAL DEFAULT 0,
            goal REAL DEFAULT 0,
            all_time_raised REAL DEFAULT 0,
            riders_count INTEGER DEFAULT 0,
            challengers_count INTEGER DEFAULT 0,
            volunteers_count INTEGER DEFAULT 0,
            last_scraped TEXT,
            PRIMARY KEY (snapshot_date, team_id)
        );

        CREATE TABLE IF NOT EXISTS org_member_profiles (
            public_id TEXT PRIMARY KEY,
            is_rider INTEGER DEFAULT 0,
            is_challenger INTEGER DEFAULT 0,
            is_volunteer INTEGER DEFAULT 0,
            last_scraped TEXT
        );
    """)
    # Add participant columns to org_snapshots if missing (pre-existing DBs).
    for col in ("riders_count", "challengers_count", "volunteers_count"):
        try:
            conn.execute(f"ALTER TABLE org_snapshots ADD COLUMN {col} INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def api_get(path, retries=3, page_size=None):
    """Fetch JSON from the Pelotonia API.

    When `page_size` is set, follows the API's header-based pagination
    (Pagination-Page / Pagination-Limit / Pagination-Total) and returns
    a single concatenated list.
    """
    url = f"{API_BASE}/{path}"

    def _build_request(page):
        headers = {
            "User-Agent": "PelotoniaOrgScraper/2.0",
            "Accept": "application/json",
        }
        if page_size:
            headers["Pagination-Page"] = str(page)
            headers["Pagination-Limit"] = str(page_size)
        return urllib.request.Request(url, headers=headers)

    def _fetch(page):
        last_exc = None
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(_build_request(page), timeout=20) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    total = int(resp.headers.get("Pagination-Total", 0) or 0)
                    return body, total
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None, 0
                last_exc = exc
            except Exception as exc:
                last_exc = exc
            time.sleep(1 + attempt)
        raise last_exc if last_exc else RuntimeError(f"Failed: {path}")

    if not page_size:
        body, _ = _fetch(1)
        return body

    aggregate, total = _fetch(1)
    if not isinstance(aggregate, list):
        return aggregate
    page = 1
    while total and len(aggregate) < total:
        page += 1
        time.sleep(RATE_LIMIT)
        chunk, _ = _fetch(page)
        if not chunk:
            break
        aggregate.extend(chunk)
    return aggregate[:total] if total else aggregate


def reconstruct_raised(team_id, fr):
    """Robust official raised = SUM(direct child raised) + generalPelotonFunds.

    Mirrors dashboard.py `_get_overview`. The API's parent `fundraising.raised`
    field is unreliable (it can collapse to just generalPelotonFunds when it
    stops aggregating sub-pelotons), so we reconstruct from the direct children.
    The child list from `peloton/{id}/members` reports each direct sub-peloton's
    (or individual member's) `raised`, which already rolls up its descendants.
    Falls back to the raw parent `raised` if the child list is unavailable.
    """
    raw = fr.get("raised") or 0
    gpf = fr.get("generalPelotonFunds") or 0
    time.sleep(RATE_LIMIT)
    children = api_get(f"peloton/{team_id}/members", page_size=PAGE_SIZE)
    if not isinstance(children, list) or not children:
        return raw
    child_sum = sum(c.get("raised") or 0 for c in children)
    return child_sum + gpf


def fetch_org(team_id):
    """Fetch a single org's aggregate stats from peloton/{id}."""
    data = api_get(f"peloton/{team_id}")
    fr = data.get("fundraising", {})
    return {
        "name": data.get("name", "Unknown"),
        "members_count": int(data.get("membersCount") or 0),
        "sub_team_count": int(data.get("numberOfSubPelotons") or 0),
        "raised": reconstruct_raised(team_id, fr),
        "goal": fr.get("goal") or 0,
        "all_time_raised": fr.get("allTimeRaised") or 0,
    }


def collect_leaf_member_ids(team_id, depth=0, seen=None):
    """Recurse through sub-pelotons to collect leaf member publicIds.

    Members with `membersCount > 0` are sub-pelotons; recurse into them.
    Members with `membersCount == 0` are leaves (individuals or virtual
    fundraisers); we collect their publicId.
    """
    if seen is None:
        seen = set()
    if depth > MAX_DEPTH:
        return []
    members = api_get(f"peloton/{team_id}/members", page_size=PAGE_SIZE)
    if not isinstance(members, list):
        return []
    leaves = []
    for m in members:
        pid = m.get("publicId")
        if not pid:
            continue
        if (m.get("membersCount") or 0) > 0:
            time.sleep(RATE_LIMIT)
            leaves.extend(collect_leaf_member_ids(pid, depth + 1, seen))
        elif pid not in seen:
            seen.add(pid)
            leaves.append(pid)
    return leaves


def fetch_participant_types(public_id):
    """Read participantTypes from the user profile endpoint."""
    profile = api_get(f"user/{public_id}")
    if not profile:
        return None
    pt = profile.get("participantTypes") or {}
    return {
        "is_rider": 1 if pt.get("isRider") else 0,
        "is_challenger": 1 if pt.get("isChallenger") else 0,
        "is_volunteer": 1 if pt.get("isVolunteer") else 0,
    }


# ---------------------------------------------------------------------------
# Participant-type cache
# ---------------------------------------------------------------------------

def _is_stale(last_scraped, max_age_days):
    if not last_scraped:
        return True
    try:
        ts = datetime.fromisoformat(last_scraped.replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - ts > timedelta(days=max_age_days)


def get_cached_participant_types(conn, public_id, refresh_all=False):
    """Return participant-type flags for a member, using cached data when fresh.

    Looks first at the existing `members` table (populated by the Huntington
    scraper), then `org_member_profiles`. Falls back to an API fetch if both
    are missing or stale, writing the result into `org_member_profiles`.
    Returns None on fetch failure.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    if not refresh_all:
        # Reuse Huntington member rows when they look fresh enough.
        try:
            row = conn.execute(
                "SELECT is_rider, is_challenger, is_volunteer, last_scraped "
                "FROM members WHERE public_id=?",
                (public_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row and not _is_stale(row[3], PROFILE_STALE_DAYS):
            return {
                "is_rider": row[0] or 0,
                "is_challenger": row[1] or 0,
                "is_volunteer": row[2] or 0,
            }

        row = conn.execute(
            "SELECT is_rider, is_challenger, is_volunteer, last_scraped "
            "FROM org_member_profiles WHERE public_id=?",
            (public_id,),
        ).fetchone()
        if row and not _is_stale(row[3], PROFILE_STALE_DAYS):
            return {
                "is_rider": row[0] or 0,
                "is_challenger": row[1] or 0,
                "is_volunteer": row[2] or 0,
            }

    time.sleep(RATE_LIMIT)
    pt = fetch_participant_types(public_id)
    if pt is None:
        return None
    conn.execute(
        "INSERT OR REPLACE INTO org_member_profiles "
        "(public_id, is_rider, is_challenger, is_volunteer, last_scraped) "
        "VALUES (?, ?, ?, ?, ?)",
        (public_id, pt["is_rider"], pt["is_challenger"], pt["is_volunteer"], now_iso),
    )
    return pt


def aggregate_org_participants(conn, team_id, refresh_all=False):
    """Walk the org's members and tally participant types."""
    leaf_ids = collect_leaf_member_ids(team_id)
    counts = {"riders": 0, "challengers": 0, "volunteers": 0, "fetched": 0, "missed": 0}
    for pid in leaf_ids:
        pt = get_cached_participant_types(conn, pid, refresh_all=refresh_all)
        if pt is None:
            counts["missed"] += 1
            continue
        counts["fetched"] += 1
        counts["riders"] += pt["is_rider"]
        counts["challengers"] += pt["is_challenger"]
        counts["volunteers"] += pt["is_volunteer"]
    conn.commit()
    return counts, len(leaf_ids)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_snapshots(conn, snapshots, today, now_iso):
    """Insert or replace today's snapshot rows for all orgs."""
    for team_id, stats in snapshots.items():
        conn.execute("""
            INSERT OR REPLACE INTO org_snapshots
                (snapshot_date, team_id, name, members_count, sub_team_count,
                 raised, goal, all_time_raised,
                 riders_count, challengers_count, volunteers_count,
                 last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today, team_id, stats["name"], stats["members_count"],
            stats["sub_team_count"], stats["raised"], stats["goal"],
            stats["all_time_raised"],
            stats.get("riders_count", 0),
            stats.get("challengers_count", 0),
            stats.get("volunteers_count", 0),
            now_iso,
        ))
    conn.commit()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(conn):
    """Print the latest leaderboard from the database."""
    row = conn.execute("SELECT MAX(snapshot_date) FROM org_snapshots").fetchone()
    if not row or not row[0]:
        print("No snapshots found in database.")
        return

    latest = row[0]
    rows = conn.execute("""
        SELECT name, members_count, riders_count, sub_team_count, raised, goal, all_time_raised
        FROM org_snapshots
        WHERE snapshot_date = ?
        ORDER BY raised DESC
    """, (latest,)).fetchall()

    print(f"=== Pelotonia Organization Leaderboard ({latest}) ===")
    print(f"{'Rank':>4}  {'Organization':<40} {'Members':>7} {'Riders':>7} {'Raised':>12} {'All-Time':>14}")
    print("-" * 95)
    for i, r in enumerate(rows, 1):
        marker = " *" if "Huntington" in (r[0] or "") else ""
        print(f"{i:>4}  {r[0]:<40} {r[1]:>7} {r[2]:>7} ${r[4]:>11,.2f} ${r[6]:>13,.2f}{marker}")
    print(f"\n  {len(rows)} organizations tracked  |  * = Team Huntington")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape aggregate stats for top Pelotonia organizations"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print latest leaderboard from the database (no scraping)"
    )
    parser.add_argument(
        "--skip-profiles", action="store_true",
        help="Skip participant-type (rider/challenger/volunteer) scrape"
    )
    parser.add_argument(
        "--refresh-all-profiles", action="store_true",
        help="Force re-fetch of every cached profile (ignores staleness)"
    )
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    init_db(conn)

    if args.summary:
        print_summary(conn)
        conn.close()
        return

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    total = len(ORGS)
    snapshots = {}
    errors = []

    print(f"Fetching {total} organizations...")
    for i, (team_id, fallback_name) in enumerate(ORGS.items(), 1):
        try:
            stats = fetch_org(team_id)
        except Exception as exc:
            errors.append(f"{fallback_name}: {exc}")
            print(f"  [{i}/{total}] ERROR {fallback_name}: {exc}", file=sys.stderr)
            if i < total:
                time.sleep(RATE_LIMIT)
            continue

        if not args.skip_profiles:
            try:
                counts, leaves = aggregate_org_participants(
                    conn, team_id, refresh_all=args.refresh_all_profiles,
                )
                stats["riders_count"] = counts["riders"]
                stats["challengers_count"] = counts["challengers"]
                stats["volunteers_count"] = counts["volunteers"]
                profile_note = (
                    f", {counts['riders']}R/{counts['challengers']}C/"
                    f"{counts['volunteers']}V across {leaves} leaves"
                )
                if counts["missed"]:
                    profile_note += f" ({counts['missed']} profile fetches failed)"
            except Exception as exc:
                errors.append(f"{stats['name']} participants: {exc}")
                profile_note = f" — participant scrape failed: {exc}"
        else:
            profile_note = ""

        snapshots[team_id] = stats
        print(
            f"  [{i}/{total}] {stats['name']}: {stats['members_count']} members, "
            f"${stats['raised']:,.2f} raised{profile_note}"
        )

        if i < total:
            time.sleep(RATE_LIMIT)

    # Store — refuse to save partial results (>20% failure likely means
    # transient API issue; storing would overwrite good data for today)
    min_required = int(total * 0.8)
    if len(snapshots) < min_required:
        print(f"\nOnly {len(snapshots)}/{total} orgs fetched (need {min_required}). "
              f"Skipping storage to avoid partial data.", file=sys.stderr)
        conn.close()
        sys.exit(1)
    elif snapshots:
        store_snapshots(conn, snapshots, today, now_iso)
        print(f"\nStored {len(snapshots)} org snapshots for {today}")
    else:
        print("No data fetched — nothing stored.", file=sys.stderr)
        conn.close()
        sys.exit(1)

    if errors:
        print(f"\n{len(errors)} errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
