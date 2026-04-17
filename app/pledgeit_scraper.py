#!/usr/bin/env python3
"""
PledgeIt Kids Scraper — Pelotonia Kids (Team Huntington)

Scrapes AGGREGATE-ONLY stats from the public PledgeIt campaign page.
No children's names, emails, or PII are collected — only totals:
fundraiser count, amount raised, goal, team count.

Source: https://charity.pledgeit.org/PelotoniaKids-TeamHuntington

The page is a Next.js app. Aggregate stats live in the __NEXT_DATA__
JSON blob embedded in the HTML.

Usage:
  python pledgeit_scraper.py                # Scrape + store today's snapshot
  python pledgeit_scraper.py --summary      # Print latest stats from DB

Requires: urllib.request, json, re, psycopg (via db module)
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

from db import get_conn, init_schema

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CAMPAIGN_URL = "https://charity.pledgeit.org/PelotoniaKids-TeamHuntington"
CAMPAIGN_ID = "dbpr4x7j9x"


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

def fetch_page(url):
    """Fetch raw HTML from the PledgeIt campaign page."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "PelotoniaKidsScraper/1.0",
        "Accept": "text/html",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_aggregate_stats(html):
    """Extract aggregate stats from __NEXT_DATA__ JSON in page HTML."""
    m = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        raise ValueError("Could not find __NEXT_DATA__ script tag in page HTML")

    raw_json = m.group(1)
    data = json.loads(raw_json)

    campaign = None
    try:
        apollo_data = data["props"]["apolloState"]["data"]
        campaign = apollo_data.get(f"Campaign:{CAMPAIGN_ID}")
    except (KeyError, TypeError):
        pass

    if campaign:
        stats_obj = campaign.get("stats") or {}
        return {
            "fundraiser_count": _extract_int(campaign, "fundraiserCount"),
            "estimated_amount_raised": _extract_float(stats_obj, "estimatedAmountRaised"),
            "monetary_goal": _extract_float(campaign, "monetaryGoal"),
            "team_count": _extract_int(campaign, "teamCount"),
        }

    fc = re.search(r'"fundraiserCount":\s*(\d+)', raw_json)
    ear = re.search(r'"estimatedAmountRaised":\s*"?([\d.]+)', raw_json)
    mg = re.search(r'"monetaryGoal":\s*(\d+)', raw_json)
    tc = re.search(r'"teamCount":\s*(\d+)', raw_json)

    if not fc and not ear and not mg:
        raise ValueError("Could not find campaign stats in __NEXT_DATA__")

    return {
        "fundraiser_count": int(fc.group(1)) if fc else 0,
        "estimated_amount_raised": float(ear.group(1)) if ear else 0.0,
        "monetary_goal": float(mg.group(1)) if mg else 0.0,
        "team_count": int(tc.group(1)) if tc else 0,
    }


def _extract_int(obj, key):
    val = obj.get(key)
    if val is not None:
        return int(val)
    return 0


def _extract_float(obj, key):
    val = obj.get(key)
    if val is not None:
        return float(val)
    return 0.0


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_snapshot(conn, stats):
    """Insert or update today's snapshot row."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    conn.execute("""
        INSERT INTO kids_snapshots
            (snapshot_date, campaign_id, fundraiser_count,
             estimated_amount_raised, monetary_goal, team_count, last_scraped)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(snapshot_date, campaign_id) DO UPDATE SET
            fundraiser_count=excluded.fundraiser_count,
            estimated_amount_raised=excluded.estimated_amount_raised,
            monetary_goal=excluded.monetary_goal,
            team_count=excluded.team_count,
            last_scraped=excluded.last_scraped
    """, (
        today,
        CAMPAIGN_ID,
        stats["fundraiser_count"],
        stats["estimated_amount_raised"],
        stats["monetary_goal"],
        stats["team_count"],
        now.isoformat(),
    ))
    conn.commit()
    return today


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(conn):
    """Print the latest snapshot from the database."""
    row = conn.execute("""
        SELECT * FROM kids_snapshots
        WHERE campaign_id = %s
        ORDER BY snapshot_date DESC
        LIMIT 1
    """, (CAMPAIGN_ID,)).fetchone()
    if not row:
        print("No snapshots found in database.")
        return
    print("=== Pelotonia Kids — Latest Snapshot ===")
    print(f"  Date:        {row['snapshot_date']}")
    print(f"  Fundraisers: {row['fundraiser_count']}")
    raised = row["estimated_amount_raised"]
    goal = row["monetary_goal"]
    pct = (raised / goal * 100) if goal > 0 else 0
    print(f"  Raised:      ${raised:,.2f}")
    print(f"  Goal:        ${goal:,.2f}")
    print(f"  Progress:    {pct:.1f}%")
    print(f"  Teams:       {row['team_count']}")
    print(f"  Scraped:     {row['last_scraped']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape aggregate Pelotonia Kids stats from PledgeIt"
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Print latest stats from the database (no scraping)"
    )
    args = parser.parse_args()

    init_schema()

    with get_conn() as conn:
        if args.summary:
            print_summary(conn)
            return

        print(f"Fetching {CAMPAIGN_URL} ...")
        try:
            html = fetch_page(CAMPAIGN_URL)
        except Exception as exc:
            print(f"ERROR fetching page: {exc}", file=sys.stderr)
            sys.exit(1)

        try:
            stats = parse_aggregate_stats(html)
        except ValueError as exc:
            print(f"ERROR parsing stats: {exc}", file=sys.stderr)
            sys.exit(1)

        today = store_snapshot(conn, stats)
        print(f"Stored snapshot for {today}:")
        print(f"  Fundraisers: {stats['fundraiser_count']}")
        print(f"  Raised:      ${stats['estimated_amount_raised']:,.2f}")
        print(f"  Goal:        ${stats['monetary_goal']:,.2f}")
        print(f"  Teams:       {stats['team_count']}")


if __name__ == "__main__":
    main()
