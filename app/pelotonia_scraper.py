#!/usr/bin/env python3
"""
Pelotonia Data Scraper — Team Huntington

Scrapes the public Pelotonia P3 middleware API to build a structured database
of Team Huntington members, their fundraising data, and donor information.

API Base: https://pelotonia-p3-middleware-production.azurewebsites.net/api/

Discovered endpoints:
  - search/pelotons?query={term}         → Find teams
  - peloton/{id}                          → Team detail (captain, story, fundraising)
  - peloton/{id}/members                  → Team members (or sub-teams for super pelotons)
  - peloton/{id}/fundraising              → Team fundraising summary
  - user/{publicId}                       → Individual profile
  - user/{publicId}/donations             → Donations received (donor names, amounts, dates)
  - user/{publicId}/donations/all         → All-time donations (may need auth)

Usage:
  python pelotonia_scraper.py                       # Full scrape, save to DB
  python pelotonia_scraper.py --teams-only          # Just scrape team structure
  python pelotonia_scraper.py --team-id <id>        # Scrape specific sub-team
  python pelotonia_scraper.py --summary             # Print summary from existing DB
  python pelotonia_scraper.py --export-csv           # Export DB to CSV files

Requires: requests, psycopg
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

from db import get_conn, init_schema

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "https://pelotonia-p3-middleware-production.azurewebsites.net/api"
PARENT_TEAM_ID = "a0s3t00000BKX8sAAH"  # Team Huntington Bank (Super peloton)
SCRIPT_DIR = Path(__file__).resolve().parent
CSV_DIR = SCRIPT_DIR / "exports"
REQUEST_DELAY = 0.5  # seconds between API calls to be respectful

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pelotonia_scraper")


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
session = requests.Session()
session.headers.update({"Accept": "application/json"})


def api_get(path, retries=3, pagination_limit=None):
    """GET from the P3 API with retry logic and automatic pagination."""
    url = f"{API_BASE}/{path}"
    headers = {}
    if pagination_limit:
        headers["Pagination-Page"] = "1"
        headers["Pagination-Limit"] = str(pagination_limit)

    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=30, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if pagination_limit and isinstance(data, list):
                    total = int(resp.headers.get("Pagination-Total", len(data)))
                    page = 1
                    while len(data) < total:
                        page += 1
                        time.sleep(REQUEST_DELAY)
                        headers["Pagination-Page"] = str(page)
                        resp2 = session.get(url, timeout=30, headers=headers)
                        if resp2.status_code != 200:
                            break
                        page_data = resp2.json()
                        if not page_data:
                            break
                        data.extend(page_data)
                    if len(data) > total:
                        data = data[:total]
                return data
            elif resp.status_code == 404:
                log.warning(f"404: {path}")
                return None
            else:
                log.warning(f"HTTP {resp.status_code} for {path} (attempt {attempt+1})")
        except requests.RequestException as e:
            log.warning(f"Request error for {path}: {e} (attempt {attempt+1})")
        time.sleep(REQUEST_DELAY * (attempt + 1))
    log.error(f"Failed after {retries} attempts: {path}")
    return None


# ---------------------------------------------------------------------------
# Scraping functions
# ---------------------------------------------------------------------------
def scrape_teams(conn):
    """Scrape all Team Huntington sub-teams and the parent."""
    now = datetime.now(timezone.utc).isoformat()

    log.info("Fetching parent team: Team Huntington Bank")
    parent = api_get(f"peloton/{PARENT_TEAM_ID}")
    if not parent:
        log.error("Could not fetch parent team")
        return []

    fr = parent.get("fundraising", {})
    conn.execute("""
        INSERT INTO teams
        (id, name, level, parent_id, captain_name, captain_public_id,
         years_active, story, accepting_members, members_count, num_sub_pelotons,
         profile_image_url, cover_image_url,
         raised, goal, goal_achieved, all_time_raised,
         total_raised_by_members, general_peloton_funds,
         last_scraped, current_event_name)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(id) DO UPDATE SET
         name=excluded.name, level=excluded.level, parent_id=excluded.parent_id,
         captain_name=excluded.captain_name, captain_public_id=excluded.captain_public_id,
         years_active=excluded.years_active, story=excluded.story,
         accepting_members=excluded.accepting_members, members_count=excluded.members_count,
         num_sub_pelotons=excluded.num_sub_pelotons,
         profile_image_url=excluded.profile_image_url, cover_image_url=excluded.cover_image_url,
         raised=excluded.raised, goal=excluded.goal, goal_achieved=excluded.goal_achieved,
         all_time_raised=excluded.all_time_raised,
         total_raised_by_members=excluded.total_raised_by_members,
         general_peloton_funds=excluded.general_peloton_funds,
         last_scraped=excluded.last_scraped, current_event_name=excluded.current_event_name
    """, (
        parent["id"], parent["name"], parent.get("level"),
        None,
        parent.get("captain", {}).get("name"),
        parent.get("captain", {}).get("publicId"),
        parent.get("yearsActive"), parent.get("story"),
        True if parent.get("acceptingNewMembers") else False,
        parent.get("membersCount"), parent.get("numberOfSubPelotons"),
        parent.get("profileImageUrl"), parent.get("coverImageUrl"),
        fr.get("raised", 0), fr.get("goal", 0),
        True if fr.get("goalAchieved") else False,
        fr.get("allTimeRaised", 0),
        fr.get("totalRaisedByMembers", 0),
        fr.get("generalPelotonFunds", 0),
        now, parent.get("currentEventName"),
    ))

    log.info("Searching for Huntington sub-teams...")
    search_results = api_get("search/pelotons?query=huntington")
    if not search_results:
        log.error("Search failed")
        return []

    team_ids = [t["id"] for t in search_results if t["id"] != PARENT_TEAM_ID]
    log.info(f"Found {len(team_ids)} sub-teams")

    for tid in team_ids:
        time.sleep(REQUEST_DELAY)
        detail = api_get(f"peloton/{tid}")
        if not detail:
            continue

        fr = detail.get("fundraising", {})
        conn.execute("""
            INSERT INTO teams
            (id, name, level, parent_id, captain_name, captain_public_id,
             years_active, story, accepting_members, members_count, num_sub_pelotons,
             profile_image_url, cover_image_url,
             raised, goal, goal_achieved, all_time_raised,
             total_raised_by_members, general_peloton_funds,
             last_scraped, current_event_name)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, level=excluded.level, parent_id=excluded.parent_id,
             captain_name=excluded.captain_name, captain_public_id=excluded.captain_public_id,
             years_active=excluded.years_active, story=excluded.story,
             accepting_members=excluded.accepting_members, members_count=excluded.members_count,
             num_sub_pelotons=excluded.num_sub_pelotons,
             profile_image_url=excluded.profile_image_url, cover_image_url=excluded.cover_image_url,
             raised=excluded.raised, goal=excluded.goal, goal_achieved=excluded.goal_achieved,
             all_time_raised=excluded.all_time_raised,
             total_raised_by_members=excluded.total_raised_by_members,
             general_peloton_funds=excluded.general_peloton_funds,
             last_scraped=excluded.last_scraped, current_event_name=excluded.current_event_name
        """, (
            detail["id"], detail["name"], detail.get("level"),
            detail.get("parent", {}).get("id") if detail.get("parent") else None,
            (detail.get("captain") or {}).get("name"),
            (detail.get("captain") or {}).get("publicId"),
            detail.get("yearsActive"), detail.get("story"),
            True if detail.get("acceptingNewMembers") else False,
            detail.get("membersCount"), detail.get("numberOfSubPelotons"),
            detail.get("profileImageUrl"), detail.get("coverImageUrl"),
            fr.get("raised", 0), fr.get("goal", 0),
            True if fr.get("goalAchieved") else False,
            fr.get("allTimeRaised", 0),
            fr.get("totalRaisedByMembers", 0),
            fr.get("generalPelotonFunds", 0),
            now, detail.get("currentEventName"),
        ))
        log.info(f"  {detail['name']} — ${fr.get('raised', 0):,.0f} raised, {detail.get('membersCount', 0):.0f} members")

    return [PARENT_TEAM_ID] + team_ids


def scrape_rides_and_routes(conn):
    """Scrape current event rides and route details."""
    now = datetime.now(timezone.utc).isoformat()

    event = api_get("event")
    if not event:
        log.warning("Could not fetch event data")
        return

    rides = event.get("rides", [])
    log.info(f"Found {len(rides)} rides in {event.get('name', '?')}")

    for ride in rides:
        conn.execute("""
            INSERT INTO rides
            (id, name, type, is_signature_ride, status,
             registration_start, registration_end,
             ride_weekend_start, ride_weekend_end, last_scraped)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, type=excluded.type,
             is_signature_ride=excluded.is_signature_ride, status=excluded.status,
             registration_start=excluded.registration_start,
             registration_end=excluded.registration_end,
             ride_weekend_start=excluded.ride_weekend_start,
             ride_weekend_end=excluded.ride_weekend_end,
             last_scraped=excluded.last_scraped
        """, (
            ride["id"], ride["name"], ride.get("type"),
            True if ride.get("isSignatureRide") else False,
            ride.get("status"),
            ride.get("registrationStartDate"),
            ride.get("registrationEndDate"),
            ride.get("rideWeekendStartDate"),
            ride.get("rideWeekendEndDate"),
            now,
        ))

        time.sleep(REQUEST_DELAY)
        routes = api_get(f"ride/{ride['id']}/routes")
        if not routes or not isinstance(routes, list):
            continue

        for r in routes:
            segments = r.get("segments", [])
            conn.execute("""
                INSERT INTO routes
                (id, ride_id, name, distance, duration, fundraising_commitment,
                 capacity, highest_incline, start_date, image_url,
                 starting_city, ending_city, last_scraped)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET
                 ride_id=excluded.ride_id, name=excluded.name,
                 distance=excluded.distance, duration=excluded.duration,
                 fundraising_commitment=excluded.fundraising_commitment,
                 capacity=excluded.capacity, highest_incline=excluded.highest_incline,
                 start_date=excluded.start_date, image_url=excluded.image_url,
                 starting_city=excluded.starting_city, ending_city=excluded.ending_city,
                 last_scraped=excluded.last_scraped
            """, (
                r["id"], ride["id"], r["name"],
                r.get("distance"), r.get("duration"),
                r.get("fundraisingCommitment"),
                r.get("capacity"), r.get("highestIncline"),
                r.get("startDate"), r.get("imageUrl"),
                segments[0].get("startingCity") if segments else None,
                segments[0].get("endingCity") if segments else None,
                now,
            ))
        log.info(f"  {ride['name']}: {len(routes)} routes")


def fetch_events(conn):
    """Fetch historical event metadata from /api/events/all."""
    now = datetime.now(timezone.utc).isoformat()

    events = api_get("events/all")
    if not events or not isinstance(events, list):
        log.warning("Could not fetch events/all")
        return

    log.info(f"Found {len(events)} historical events")
    for ev in events:
        conn.execute("""
            INSERT INTO events
            (id, name, year, total_participants, status,
             fundraising_start, fundraising_end,
             ride_weekend_start, ride_weekend_end, last_scraped)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, year=excluded.year,
             total_participants=excluded.total_participants, status=excluded.status,
             fundraising_start=excluded.fundraising_start,
             fundraising_end=excluded.fundraising_end,
             ride_weekend_start=excluded.ride_weekend_start,
             ride_weekend_end=excluded.ride_weekend_end,
             last_scraped=excluded.last_scraped
        """, (
            ev["id"], ev.get("name"),
            ev.get("year"), ev.get("totalParticipants"),
            ev.get("status"),
            ev.get("fundraisingCampaignStartDate"),
            ev.get("fundraisingCampaignEndDate"),
            ev.get("rideWeekendStartDate"),
            ev.get("rideWeekendEndDate"),
            now,
        ))

    log.info(f"Events table updated with {len(events)} records")


def scrape_members(conn, team_ids=None):
    """Scrape members for given teams (or all teams in DB)."""
    now = datetime.now(timezone.utc).isoformat()

    if team_ids is None:
        cursor = conn.execute("SELECT id FROM teams WHERE level='Sub' OR level IS NULL")
        team_ids = [row["id"] for row in cursor]

    total_members = 0
    for tid in team_ids:
        time.sleep(REQUEST_DELAY)
        members = api_get(f"peloton/{tid}/members", pagination_limit=200)
        if not members or not isinstance(members, list):
            continue

        individuals = [m for m in members if m.get("membersCount", 0) == 0]

        for m in individuals:
            conn.execute("""
                INSERT INTO members
                (public_id, name, team_id, is_captain, is_admin, is_cancer_survivor,
                 raised, attributed, commitment_amount, fundraising_goal,
                 profile_image_url, last_scraped)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(public_id) DO UPDATE SET
                 name=excluded.name, team_id=excluded.team_id,
                 is_captain=excluded.is_captain, is_admin=excluded.is_admin,
                 is_cancer_survivor=excluded.is_cancer_survivor,
                 raised=excluded.raised, attributed=excluded.attributed,
                 commitment_amount=excluded.commitment_amount,
                 fundraising_goal=excluded.fundraising_goal,
                 profile_image_url=excluded.profile_image_url,
                 last_scraped=excluded.last_scraped
            """, (
                m["publicId"], m["name"], tid,
                True if m.get("isCaptain") else False,
                True if m.get("isAdmin") else False,
                True if m.get("isCancerSurvivor") else False,
                m.get("raised", 0), m.get("attributed", 0),
                m.get("commitmentAmount", 0), m.get("fundraisingGoal", 0),
                m.get("profileImageUrl"),
                now,
            ))
            total_members += 1

        team_name = conn.execute("SELECT name FROM teams WHERE id=%s", (tid,)).fetchone()
        team_label = team_name["name"] if team_name else tid
        log.info(f"  {team_label}: {len(individuals)} members")

    log.info(f"Total members scraped: {total_members}")
    return total_members


def scrape_member_profiles(conn, public_ids=None):
    """Fetch extended profile data for each member."""
    now = datetime.now(timezone.utc).isoformat()

    if public_ids is None:
        cursor = conn.execute("SELECT public_id FROM members")
        public_ids = [row["public_id"] for row in cursor]

    log.info(f"Fetching extended profiles for {len(public_ids)} members...")
    for i, pid in enumerate(public_ids):
        time.sleep(REQUEST_DELAY)
        profile = api_get(f"user/{pid}")
        if not profile:
            continue

        fr = profile.get("fundraising", {})
        pt = profile.get("participantTypes", {})
        registered_rides = pt.get("registeredRides", [])
        ride_types = list({r.get("rideType") for r in registered_rides if r.get("rideType")})
        primary_ride_type = ride_types[0] if len(ride_types) == 1 else (
            json.dumps(ride_types) if ride_types else None
        )

        conn.execute("""
            UPDATE members SET
                first_name=%s, last_name=%s,
                registration_types=%s, story=%s,
                is_donor_list_visible=%s, all_time_raised=%s,
                tags=%s, current_event_name=%s,
                is_rider=%s, is_volunteer=%s, is_challenger=%s,
                ride_type=%s, ride_types=%s,
                committed_amount=%s, personal_goal=%s,
                committed_high_roller=%s,
                last_scraped=%s
            WHERE public_id=%s
        """, (
            profile.get("firstName"), profile.get("lastName"),
            json.dumps(profile.get("registrationTypes", [])),
            profile.get("story"),
            True if profile.get("isDonorListVisible") else False,
            fr.get("allTimeRaised", 0),
            json.dumps([t.get("name") for t in profile.get("tags", [])]),
            profile.get("currentEventName"),
            True if pt.get("isRider") else False,
            True if pt.get("isVolunteer") else False,
            True if pt.get("isChallenger") else False,
            primary_ride_type,
            json.dumps(ride_types) if ride_types else None,
            fr.get("committedAmount", 0),
            fr.get("goal", 0),
            True if fr.get("committedHighRoller") else False,
            now,
            pid,
        ))

        if (i + 1) % 25 == 0:
            log.info(f"  Profiles: {i+1}/{len(public_ids)}")

    log.info(f"Extended profiles complete")


def scrape_member_routes(conn, public_ids=None):
    """Fetch route selections for each member via user/{id}/routes endpoint."""
    now = datetime.now(timezone.utc).isoformat()

    if public_ids is None:
        cursor = conn.execute("SELECT public_id FROM members")
        public_ids = [row["public_id"] for row in cursor]

    log.info(f"Fetching route selections for {len(public_ids)} members...")
    total_routes = 0
    members_with_routes = set()
    for i, pid in enumerate(public_ids):
        time.sleep(REQUEST_DELAY)
        routes = api_get(f"user/{pid}/routes")
        if not routes:
            continue

        members_with_routes.add(pid)
        for r in routes:
            route_id = r.get("id")
            if not route_id:
                continue
            ride = r.get("ride", {})
            conn.execute("""
                INSERT INTO member_routes
                    (member_public_id, route_id, route_name, ride_type,
                     distance, fundraising_commitment, last_scraped)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(member_public_id, route_id) DO UPDATE SET
                    route_name=excluded.route_name,
                    ride_type=excluded.ride_type,
                    distance=excluded.distance,
                    fundraising_commitment=excluded.fundraising_commitment,
                    last_scraped=excluded.last_scraped
            """, (
                pid, route_id, r.get("name"),
                ride.get("type"),
                r.get("distance"),
                r.get("fundraisingCommitment"),
                now,
            ))
            total_routes += 1

        if (i + 1) % 25 == 0:
            log.info(f"  Routes: {i+1}/{len(public_ids)}")

    inferred = 0
    for pid in members_with_routes:
        row = conn.execute(
            "SELECT is_rider, is_challenger FROM members WHERE public_id=%s", (pid,)
        ).fetchone()
        if row and row["is_rider"] is False and row["is_challenger"] is False:
            ride_types = conn.execute(
                "SELECT DISTINCT ride_type FROM member_routes WHERE member_public_id=%s", (pid,)
            ).fetchall()
            types = {r["ride_type"] for r in ride_types if r["ride_type"]}
            if "gravel" in types:
                conn.execute("UPDATE members SET is_challenger=true WHERE public_id=%s", (pid,))
                inferred += 1
            elif "signature" in types:
                conn.execute("UPDATE members SET is_rider=true WHERE public_id=%s", (pid,))
                inferred += 1

    if inferred:
        log.info(f"Inferred participant type from routes for {inferred} members")

    log.info(f"Member routes complete — {total_routes} route selections stored")


def scrape_donations(conn, public_ids=None):
    """Scrape donations received by each member."""
    now = datetime.now(timezone.utc).isoformat()

    if public_ids is None:
        cursor = conn.execute(
            "SELECT public_id FROM members WHERE is_donor_list_visible=true OR is_donor_list_visible IS NULL"
        )
        public_ids = [row["public_id"] for row in cursor]

    log.info(f"Scraping donations for {len(public_ids)} members...")
    total_donations = 0

    for i, pid in enumerate(public_ids):
        time.sleep(REQUEST_DELAY)
        donations = api_get(f"user/{pid}/donations", pagination_limit=200)
        if not donations or not isinstance(donations, list):
            continue

        for d in donations:
            donor = d.get("donor", {})
            conn.execute("""
                INSERT INTO donations
                (opportunity_id, recipient_public_id, event_id, event_name,
                 amount, date, is_recurring, pending, anonymous_to_public,
                 recognition_name, donor_name, donor_public_id,
                 donor_profile_image_url, last_scraped)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(opportunity_id) DO UPDATE SET
                 recipient_public_id=excluded.recipient_public_id,
                 event_id=excluded.event_id, event_name=excluded.event_name,
                 amount=excluded.amount, date=excluded.date,
                 is_recurring=excluded.is_recurring, pending=excluded.pending,
                 anonymous_to_public=excluded.anonymous_to_public,
                 recognition_name=excluded.recognition_name,
                 donor_name=excluded.donor_name, donor_public_id=excluded.donor_public_id,
                 donor_profile_image_url=excluded.donor_profile_image_url,
                 last_scraped=excluded.last_scraped
            """, (
                d["opportunityId"], pid,
                d.get("eventId"), d.get("eventName"),
                d.get("amount", 0), d.get("date"),
                True if d.get("isRecurring") else False,
                True if d.get("pending") else False,
                True if d.get("anonymousToPublic") else False,
                d.get("recognitionName"),
                donor.get("name"), donor.get("publicId"),
                donor.get("profileImageUrl"),
                now,
            ))
            total_donations += 1

        if (i + 1) % 25 == 0:
            log.info(f"  Donations: {i+1}/{len(public_ids)} members processed")

    log.info(f"Total donation records: {total_donations}")
    return total_donations


# ---------------------------------------------------------------------------
# Summary & export
# ---------------------------------------------------------------------------
def record_daily_snapshot(conn):
    """Record a daily snapshot of fundraising totals for historical tracking."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parent = conn.execute(
        "SELECT raised, goal, all_time_raised, members_count FROM teams WHERE id=%s",
        (PARENT_TEAM_ID,),
    ).fetchone()
    if parent:
        api_members = int(parent["members_count"] or 0)
        total_donations = conn.execute("SELECT COUNT(*) as cnt FROM donations").fetchone()["cnt"]
        total_donated = conn.execute("SELECT COALESCE(SUM(amount),0) as s FROM donations").fetchone()["s"]
        sig_riders = conn.execute(
            "SELECT COUNT(DISTINCT member_public_id) as cnt FROM member_routes WHERE ride_type='signature'"
        ).fetchone()["cnt"]
        grv_riders = conn.execute(
            "SELECT COUNT(DISTINCT member_public_id) as cnt FROM member_routes WHERE ride_type='gravel'"
        ).fetchone()["cnt"]
        riders_count = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_rider=true").fetchone()["cnt"]
        challengers_count = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_challenger=true").fetchone()["cnt"]
        volunteers_count = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_volunteer=true").fetchone()["cnt"]
        conn.execute("""
            INSERT INTO daily_snapshots
            (snapshot_date, team_id, raised, goal, all_time_raised,
             members_count, donations_count, total_donated,
             signature_riders, gravel_riders,
             riders_count, challengers_count, volunteers_count)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(snapshot_date, team_id) DO UPDATE SET
             raised=excluded.raised, goal=excluded.goal,
             all_time_raised=excluded.all_time_raised,
             members_count=excluded.members_count,
             donations_count=excluded.donations_count,
             total_donated=excluded.total_donated,
             signature_riders=excluded.signature_riders,
             gravel_riders=excluded.gravel_riders,
             riders_count=excluded.riders_count,
             challengers_count=excluded.challengers_count,
             volunteers_count=excluded.volunteers_count
        """, (today, PARENT_TEAM_ID, parent["raised"], parent["goal"], parent["all_time_raised"],
              api_members, total_donations, total_donated,
              sig_riders, grv_riders,
              riders_count, challengers_count, volunteers_count))

    rows = conn.execute(
        "SELECT id, raised, goal, all_time_raised, members_count FROM teams WHERE parent_id=%s",
        (PARENT_TEAM_ID,),
    ).fetchall()
    for r in rows:
        team_donations = conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(d.amount),0) as total FROM donations d "
            "JOIN members m ON d.recipient_public_id=m.public_id WHERE m.team_id=%s",
            (r["id"],),
        ).fetchone()
        conn.execute("""
            INSERT INTO daily_snapshots
            (snapshot_date, team_id, raised, goal, all_time_raised,
             members_count, donations_count, total_donated)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(snapshot_date, team_id) DO UPDATE SET
             raised=excluded.raised, goal=excluded.goal,
             all_time_raised=excluded.all_time_raised,
             members_count=excluded.members_count,
             donations_count=excluded.donations_count,
             total_donated=excluded.total_donated
        """, (today, r["id"], r["raised"], r["goal"], r["all_time_raised"], int(r["members_count"] or 0),
              team_donations["cnt"], team_donations["total"]))

    log.info(f"Recorded daily snapshot for {today}")


def scrape_incremental(conn):
    """Incremental scrape: refresh teams + members, only fetch what changed."""
    start = time.time()
    log.info("Starting incremental scrape...")

    scrape_rides_and_routes(conn)
    team_ids = scrape_teams(conn)
    sub_team_ids = [tid for tid in team_ids if tid != PARENT_TEAM_ID]

    pre_raised = {}
    pre_team = {}
    for row in conn.execute("SELECT public_id, raised, team_id FROM members"):
        pre_raised[row["public_id"]] = row["raised"]
        pre_team[row["public_id"]] = row["team_id"]
    pre_member_ids = set(pre_raised.keys())

    scrape_members(conn, sub_team_ids)

    current_member_ids = set()
    for row in conn.execute("SELECT public_id FROM members WHERE last_scraped >= %s",
                            (datetime.now(timezone.utc).strftime("%Y-%m-%d"),)):
        current_member_ids.add(row["public_id"])
    disappeared = pre_member_ids - current_member_ids
    if disappeared:
        log.info(f"Detected {len(disappeared)} members no longer on any roster")
        for pid in disappeared:
            old_team = pre_team.get(pid, "?")
            name = conn.execute("SELECT name FROM members WHERE public_id=%s", (pid,)).fetchone()
            log.info(f"  GONE: {name['name'] if name else pid} (was on team {old_team})")

    for row in conn.execute("SELECT public_id, team_id FROM members"):
        old_tid = pre_team.get(row["public_id"])
        if old_tid and old_tid != row["team_id"]:
            name = conn.execute("SELECT name FROM members WHERE public_id=%s", (row["public_id"],)).fetchone()
            log.info(f"  MOVED: {name['name'] if name else row['public_id']} from {old_tid} -> {row['team_id']}")

    new_member_ids = current_member_ids - pre_member_ids
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    stale_members = conn.execute("""
        SELECT public_id FROM members
        WHERE first_name IS NULL
           OR (is_rider=false AND is_challenger=false AND is_volunteer=false
               AND is_rider IS NOT NULL)
           OR last_scraped < %s
    """, (stale_cutoff,)).fetchall()
    stale_ids = list(set([r["public_id"] for r in stale_members]) | new_member_ids)
    if stale_ids:
        log.info(f"Fetching profiles for {len(stale_ids)} new/stale/old members "
                 f"({len(new_member_ids)} new, {len(stale_ids) - len(new_member_ids)} stale/old)...")
        scrape_member_profiles(conn, stale_ids)
    else:
        log.info("All members have fresh profile data — skipping profile fetch")

    members_with_routes = set()
    for row in conn.execute("SELECT DISTINCT member_public_id FROM member_routes"):
        members_with_routes.add(row["member_public_id"])
    needs_routes_new = [pid for pid in current_member_ids if pid not in members_with_routes]
    needs_routes_refresh = [pid for pid in stale_ids if pid in members_with_routes]
    needs_routes = list(set(needs_routes_new + needs_routes_refresh))
    if needs_routes:
        if needs_routes_refresh:
            log.info(f"Clearing stale routes for {len(needs_routes_refresh)} members before re-fetch...")
            for pid in needs_routes_refresh:
                conn.execute("DELETE FROM member_routes WHERE member_public_id=%s", (pid,))
        log.info(f"Fetching routes for {len(needs_routes)} members "
                 f"({len(needs_routes_new)} new, {len(needs_routes_refresh)} refresh)...")
        scrape_member_routes(conn, needs_routes)
    else:
        log.info("All members have route data — skipping route fetch")

    changed = []
    for row in conn.execute("SELECT public_id, raised FROM members"):
        old = pre_raised.get(row["public_id"])
        if old is None or abs(row["raised"] - old) > 0.01:
            changed.append(row["public_id"])

    if changed:
        log.info(f"Fundraising changed for {len(changed)} members — fetching donations...")
        scrape_donations(conn, changed)
    else:
        log.info("No fundraising changes detected — skipping donation scrape")

    build_donor_identities(conn)
    record_daily_snapshot(conn)

    conn.commit()

    elapsed = time.time() - start
    log.info(f"Incremental scrape complete in {elapsed:.0f}s")


def build_donor_identities(conn):
    """Cross-reference anonymous donations with non-anonymous ones to de-anonymize."""
    log.info("Building donor identity map...")

    conn.execute("""
        INSERT INTO donor_identities (recognition_name, inferred_name, confidence, source, donor_public_id)
        SELECT
            anon.recognition_name,
            known.donor_name,
            'high',
            'same_recognition_name_matched_to_non_anonymous_donation',
            known.donor_public_id
        FROM donations anon
        JOIN donations known ON anon.recognition_name = known.recognition_name
            AND known.anonymous_to_public = false
            AND known.donor_name IS NOT NULL
            AND known.donor_name != 'Anonymous'
        WHERE anon.anonymous_to_public = true
        GROUP BY anon.recognition_name, known.donor_name, known.donor_public_id
        ON CONFLICT(recognition_name) DO UPDATE SET
            inferred_name=excluded.inferred_name,
            confidence=excluded.confidence,
            source=excluded.source,
            donor_public_id=excluded.donor_public_id
    """)

    conn.execute("""
        INSERT INTO donor_identities (recognition_name, inferred_name, confidence, source, donor_public_id)
        SELECT DISTINCT
            d.recognition_name,
            d.recognition_name,
            'medium',
            'recognition_name_is_likely_real_name',
            NULL
        FROM donations d
        WHERE d.anonymous_to_public = true
            AND d.recognition_name IS NOT NULL
            AND d.recognition_name != ''
            AND d.recognition_name NOT IN (SELECT recognition_name FROM donor_identities)
        ON CONFLICT(recognition_name) DO NOTHING
    """)

    count = conn.execute("SELECT COUNT(*) as cnt FROM donor_identities").fetchone()["cnt"]
    log.info(f"Donor identity map: {count} entries")


def print_summary(conn):
    """Print a summary of the database contents."""
    print("\n" + "=" * 60)
    print("PELOTONIA DATABASE SUMMARY")
    print("=" * 60)

    teams = conn.execute("SELECT COUNT(*) as cnt FROM teams").fetchone()["cnt"]
    members = conn.execute("SELECT COUNT(*) as cnt FROM members").fetchone()["cnt"]
    donations = conn.execute("SELECT COUNT(*) as cnt FROM donations").fetchone()["cnt"]

    print(f"\nTotals: {teams} teams | {members} members | {donations} donation records")

    parent = conn.execute(
        "SELECT name, raised, goal, all_time_raised, members_count FROM teams WHERE id=%s",
        (PARENT_TEAM_ID,)
    ).fetchone()
    if parent:
        print(f"\n{parent['name']}:")
        print(f"  2026 Raised:  ${parent['raised']:>12,.2f} / ${parent['goal']:>12,.2f} goal ({parent['raised']/parent['goal']*100 if parent['goal'] else 0:.1f}%)")
        print(f"  All-time:     ${parent['all_time_raised']:>12,.2f}")

    print("\nSub-team breakdown:")
    rows = conn.execute(
        "SELECT name, raised, goal, all_time_raised, members_count "
        "FROM teams WHERE parent_id=%s ORDER BY raised DESC",
        (PARENT_TEAM_ID,)
    ).fetchall()
    for r in rows:
        pct = f"{r['raised']/r['goal']*100:.0f}%" if r['goal'] and r['goal'] > 0 else "N/A"
        print(f"  {r['name']:55s} ${r['raised']:>10,.0f}  ({pct:>4s} of ${r['goal']:>10,.0f})  {r['members_count']:.0f} members  all-time: ${r['all_time_raised']:>12,.0f}")

    print("\nTop 15 fundraisers (current year):")
    rows = conn.execute(
        "SELECT m.name, m.raised, m.all_time_raised, t.name as team_name "
        "FROM members m LEFT JOIN teams t ON m.team_id=t.id "
        "ORDER BY m.raised DESC LIMIT 15"
    ).fetchall()
    for i, r in enumerate(rows, 1):
        team_short = r["team_name"].replace("Team Huntington Bank - ", "") if r["team_name"] else "?"
        print(f"  {i:2d}. {r['name']:25s} ${r['raised']:>10,.0f}  (all-time: ${r['all_time_raised']:>12,.0f})  [{team_short}]")

    print("\nTop 15 donors (by total donated this year):")
    rows = conn.execute(
        "SELECT COALESCE(recognition_name, donor_name, 'Anonymous') as donor_label, "
        "       SUM(amount) as total, COUNT(*) as cnt "
        "FROM donations "
        "WHERE anonymous_to_public=false "
        "GROUP BY COALESCE(recognition_name, donor_name) "
        "ORDER BY SUM(amount) DESC LIMIT 15"
    ).fetchall()
    for i, r in enumerate(rows, 1):
        print(f"  {i:2d}. {r['donor_label']:35s} ${r['total']:>10,.0f}  ({r['cnt']} donations)")

    survivors = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_cancer_survivor=true").fetchone()["cnt"]
    high_rollers = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE tags LIKE '%%High Roller%%'").fetchone()["cnt"]
    print(f"\nCancer survivors on team: {survivors}")
    print(f"High Rollers: {high_rollers}")

    date_range = conn.execute(
        "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT event_name) as event_cnt FROM donations"
    ).fetchone()
    if date_range and date_range["min_date"]:
        print(f"\nDonation date range: {date_range['min_date'][:10]} to {date_range['max_date'][:10]}")
        print(f"Event years covered: {date_range['event_cnt']}")

    totals = conn.execute(
        "SELECT SUM(amount) as total, COUNT(*) as cnt, COUNT(DISTINCT recognition_name) as unique_donors FROM donations"
    ).fetchone()
    if totals:
        print(f"Total donated: ${totals['total']:,.2f} across {totals['cnt']} transactions from {totals['unique_donors']} unique donors")

    anon = conn.execute(
        "SELECT COUNT(*) as cnt, SUM(amount) as total FROM donations WHERE anonymous_to_public=true"
    ).fetchone()
    if anon and anon["cnt"]:
        print(f"Anonymous donations: {anon['cnt']} totaling ${anon['total']:,.2f}")

    identities = conn.execute("SELECT COUNT(*) as cnt FROM donor_identities").fetchone()["cnt"]
    high_conf = conn.execute("SELECT COUNT(*) as cnt FROM donor_identities WHERE confidence='high'").fetchone()["cnt"]
    if identities:
        print(f"De-anonymized donors: {identities} ({high_conf} high confidence)")
        print("\nDe-anonymized anonymous donors:")
        rows = conn.execute(
            "SELECT di.recognition_name, di.inferred_name, di.confidence, d.amount "
            "FROM donor_identities di "
            "JOIN donations d ON d.recognition_name = di.recognition_name AND d.anonymous_to_public=true "
            "ORDER BY d.amount DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print(f"  {r['recognition_name']:30s} -> {r['inferred_name']:25s} ({r['confidence']})  ${r['amount']:,.0f}")

    last = conn.execute("SELECT MAX(last_scraped) as ls FROM members").fetchone()["ls"]
    last_str = last.isoformat() if hasattr(last, "isoformat") else last
    print(f"\nLast scraped: {last_str}")
    print("=" * 60 + "\n")


def export_csv(conn):
    """Export all tables to CSV files."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    for table in ["teams", "members", "donations"]:
        cursor = conn.execute(f"SELECT * FROM {table}")
        cols = [desc.name for desc in cursor.description]
        rows = cursor.fetchall()

        path = CSV_DIR / f"{table}_{timestamp}.csv"
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for row in rows:
                writer.writerow([row[c] for c in cols])
        log.info(f"Exported {len(rows)} rows to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pelotonia Team Huntington data scraper")
    parser.add_argument("--teams-only", action="store_true", help="Only scrape team structure")
    parser.add_argument("--team-id", help="Scrape a specific sub-team ID")
    parser.add_argument("--summary", action="store_true", help="Print DB summary only")
    parser.add_argument("--export-csv", action="store_true", help="Export DB to CSV files")
    parser.add_argument("--skip-donations", action="store_true", help="Skip donation scraping (faster)")
    parser.add_argument("--skip-profiles", action="store_true", help="Skip extended profile scraping")
    parser.add_argument("--incremental", action="store_true",
                        help="Incremental scrape: only fetch new data (ideal for daily cron)")
    parser.add_argument("--backfill-donations", action="store_true",
                        help="Fetch donations for members with raised > 0 but no donation records")
    args = parser.parse_args()

    init_schema()

    with get_conn() as conn:
        if args.summary:
            print_summary(conn)
            return

        if args.export_csv:
            export_csv(conn)
            return

        if args.backfill_donations:
            missing = conn.execute("""
                SELECT m.public_id, m.name, m.raised FROM members m
                WHERE m.raised > 0
                  AND NOT EXISTS (SELECT 1 FROM donations d WHERE d.recipient_public_id = m.public_id)
            """).fetchall()
            if not missing:
                log.info("No members need donation backfill — all members with raised > 0 have donation records")
            else:
                log.info(f"Backfilling donations for {len(missing)} members with raised > 0 but no donation records...")
                for row in missing[:5]:
                    log.info(f"  e.g. {row['name']}: ${row['raised']:,.0f} raised, 0 donation records")
                pids = [r["public_id"] for r in missing]
                scrape_donations(conn, pids)
                build_donor_identities(conn)
                conn.commit()
            print_summary(conn)
            return

        if args.incremental:
            scrape_incremental(conn)
            print_summary(conn)
            return

        start = time.time()
        log.info("Starting Pelotonia scrape...")

        fetch_events(conn)
        scrape_rides_and_routes(conn)

        if args.team_id:
            team_ids = [args.team_id]
        else:
            team_ids = scrape_teams(conn)

        if args.teams_only:
            conn.commit()
            print_summary(conn)
            return

        sub_team_ids = [tid for tid in team_ids if tid != PARENT_TEAM_ID]
        scrape_members(conn, sub_team_ids)

        if not args.skip_profiles:
            scrape_member_profiles(conn)

        scrape_member_routes(conn)

        if not args.skip_donations:
            scrape_donations(conn)

        build_donor_identities(conn)
        record_daily_snapshot(conn)

        conn.commit()

        elapsed = time.time() - start
        log.info(f"Scrape complete in {elapsed:.0f}s")

        print_summary(conn)


if __name__ == "__main__":
    main()
