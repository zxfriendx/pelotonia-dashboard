#!/usr/bin/env python3
"""
Organization Leaderboard Scraper — Pelotonia Top Teams

Fetches aggregate stats for ~31 major Pelotonia organizations (parent teams)
and stores daily snapshots for leaderboard comparison.

Data per org: name, members_count, sub_team_count, raised, goal, all_time_raised.

Usage:
  python org_scraper.py                # Scrape + store today's snapshot
  python org_scraper.py --summary      # Print leaderboard from DB

Requires: urllib.request, json, time, psycopg (via db module)
"""

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

from db import get_conn, init_schema

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "https://pelotonia-p3-middleware-production.azurewebsites.net/api"
RATE_LIMIT = 0.5  # seconds between API calls

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
            time.sleep(1 + attempt)


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
    """Insert or update today's snapshot rows for all orgs."""
    for team_id, stats in snapshots.items():
        conn.execute("""
            INSERT INTO org_snapshots
                (snapshot_date, team_id, name, members_count, sub_team_count,
                 raised, goal, all_time_raised, last_scraped)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(snapshot_date, team_id) DO UPDATE SET
                name=excluded.name, members_count=excluded.members_count,
                sub_team_count=excluded.sub_team_count,
                raised=excluded.raised, goal=excluded.goal,
                all_time_raised=excluded.all_time_raised,
                last_scraped=excluded.last_scraped
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
    row = conn.execute("SELECT MAX(snapshot_date) as max_date FROM org_snapshots").fetchone()
    if not row or not row["max_date"]:
        print("No snapshots found in database.")
        return

    latest = row["max_date"]
    rows = conn.execute("""
        SELECT name, members_count, sub_team_count, raised, goal, all_time_raised
        FROM org_snapshots
        WHERE snapshot_date = %s
        ORDER BY raised DESC
    """, (latest,)).fetchall()

    print(f"=== Pelotonia Organization Leaderboard ({latest}) ===")
    print(f"{'Rank':>4}  {'Organization':<40} {'Members':>7} {'Raised':>12} {'All-Time':>14}")
    print("-" * 85)
    for i, r in enumerate(rows, 1):
        marker = " *" if "Huntington" in (r["name"] or "") else ""
        print(f"{i:>4}  {r['name']:<40} {r['members_count']:>7} ${r['raised']:>11,.2f} ${r['all_time_raised']:>13,.2f}{marker}")
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

    init_schema()

    with get_conn() as conn:
        if args.summary:
            print_summary(conn)
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
                snapshots[team_id] = stats
                print(f"  [{i}/{total}] {stats['name']}: {stats['members_count']} members, ${stats['raised']:,.2f} raised")
            except Exception as exc:
                errors.append(f"{fallback_name}: {exc}")
                print(f"  [{i}/{total}] ERROR {fallback_name}: {exc}", file=sys.stderr)

            if i < total:
                time.sleep(RATE_LIMIT)

        min_required = int(total * 0.8)
        if len(snapshots) < min_required:
            print(f"\nOnly {len(snapshots)}/{total} orgs fetched (need {min_required}). "
                  f"Skipping storage to avoid partial data.", file=sys.stderr)
            sys.exit(1)
        elif snapshots:
            store_snapshots(conn, snapshots, today, now_iso)
            print(f"\nStored {len(snapshots)} org snapshots for {today}")
        else:
            print("No data fetched — nothing stored.", file=sys.stderr)
            sys.exit(1)

        if errors:
            print(f"\n{len(errors)} errors:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
