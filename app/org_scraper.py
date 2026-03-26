#!/usr/bin/env python3
"""
Organization Leaderboard Scraper — Pelotonia Top Teams

Fetches aggregate stats for ~25 major Pelotonia organizations (parent teams)
and stores daily snapshots for leaderboard comparison.

Data per org: name, members_count, sub_team_count, raised, goal, all_time_raised.

Usage:
  python org_scraper.py                # Scrape + store today's snapshot
  python org_scraper.py --summary      # Print leaderboard from DB

Requires: stdlib only (urllib.request, json, sqlite3, time)
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "https://pelotonia-p3-middleware-production.azurewebsites.net/api"
RATE_LIMIT = 0.5  # seconds between API calls

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
    """Create the org_snapshots table if it doesn't exist."""
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
            last_scraped TEXT,
            PRIMARY KEY (snapshot_date, team_id)
        );
    """)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def api_get(path, retries=3):
    """Fetch JSON from the Pelotonia API with retry logic."""
    url = f"{API_BASE}/{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "PelotoniaOrgScraper/1.0",
        "Accept": "application/json",
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1 + attempt)  # 1s, 2s backoff


def fetch_org(team_id):
    """Fetch a single org's aggregate stats from peloton/{id} endpoint."""
    data = api_get(f"peloton/{team_id}")
    fr = data.get("fundraising", {})
    return {
        "name": data.get("name", "Unknown"),
        "members_count": int(data.get("membersCount") or 0),
        "sub_team_count": int(data.get("numberOfSubPelotons") or 0),
        "raised": fr.get("raised") or 0,
        "goal": fr.get("goal") or 0,
        "all_time_raised": fr.get("allTimeRaised") or 0,
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_snapshots(conn, snapshots, today, now_iso):
    """Insert or replace today's snapshot rows for all orgs."""
    for team_id, stats in snapshots.items():
        conn.execute("""
            INSERT OR REPLACE INTO org_snapshots
                (snapshot_date, team_id, name, members_count, sub_team_count,
                 raised, goal, all_time_raised, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today, team_id, stats["name"], stats["members_count"],
            stats["sub_team_count"], stats["raised"], stats["goal"],
            stats["all_time_raised"], now_iso,
        ))
    conn.commit()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(conn):
    """Print the latest leaderboard from the database."""
    # Get the most recent snapshot date
    row = conn.execute("SELECT MAX(snapshot_date) FROM org_snapshots").fetchone()
    if not row or not row[0]:
        print("No snapshots found in database.")
        return

    latest = row[0]
    rows = conn.execute("""
        SELECT name, members_count, sub_team_count, raised, goal, all_time_raised
        FROM org_snapshots
        WHERE snapshot_date = ?
        ORDER BY raised DESC
    """, (latest,)).fetchall()

    print(f"=== Pelotonia Organization Leaderboard ({latest}) ===")
    print(f"{'Rank':>4}  {'Organization':<40} {'Members':>7} {'Raised':>12} {'All-Time':>14}")
    print("-" * 85)
    for i, r in enumerate(rows, 1):
        marker = " *" if "Huntington" in (r[0] or "") else ""
        print(f"{i:>4}  {r[0]:<40} {r[1]:>7} ${r[3]:>11,.2f} ${r[5]:>13,.2f}{marker}")
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
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)

    if args.summary:
        print_summary(conn)
        conn.close()
        return

    # Scrape all orgs
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
            snapshots[team_id] = stats
            print(f"  [{i}/{total}] {stats['name']}: {stats['members_count']} members, ${stats['raised']:,.2f} raised")
        except Exception as exc:
            errors.append(f"{fallback_name}: {exc}")
            print(f"  [{i}/{total}] ERROR {fallback_name}: {exc}", file=sys.stderr)

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
