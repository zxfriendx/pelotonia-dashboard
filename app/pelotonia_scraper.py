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
  python pelotonia_scraper.py                       # Full scrape, save to SQLite
  python pelotonia_scraper.py --teams-only          # Just scrape team structure
  python pelotonia_scraper.py --team-id <id>        # Scrape specific sub-team
  python pelotonia_scraper.py --summary             # Print summary from existing DB
  python pelotonia_scraper.py --export-csv           # Export DB to CSV files

Requires: requests (pip install requests) — available in system Python or venv
"""

import argparse
import csv
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "https://pelotonia-p3-middleware-production.azurewebsites.net/api"
PARENT_TEAM_ID = "a0s3t00000BKX8sAAH"  # Team Huntington Bank (Super peloton)
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PELOTONIA_DB", SCRIPT_DIR / "pelotonia_data.db"))
CSV_DIR = SCRIPT_DIR / "exports"
REQUEST_DELAY = 0.5  # seconds between API calls to be respectful

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pelotonia_scraper")


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def init_db(db_path=DB_PATH):
    """Create/upgrade the SQLite database schema."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level TEXT,              -- 'Super' or 'Sub'
            parent_id TEXT,
            captain_name TEXT,
            captain_public_id TEXT,
            years_active REAL,
            story TEXT,
            accepting_members INTEGER,
            members_count REAL,
            num_sub_pelotons REAL,
            profile_image_url TEXT,
            cover_image_url TEXT,
            -- Fundraising
            raised REAL DEFAULT 0,
            goal REAL DEFAULT 0,
            goal_override REAL,      -- Manual goal override (preserved across scrapes)
            goal_achieved INTEGER DEFAULT 0,
            all_time_raised REAL DEFAULT 0,
            total_raised_by_members REAL DEFAULT 0,
            general_peloton_funds REAL DEFAULT 0,
            -- Meta
            last_scraped TEXT,
            current_event_name TEXT
        );

        CREATE TABLE IF NOT EXISTS members (
            public_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            team_id TEXT,
            is_captain INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            is_cancer_survivor INTEGER DEFAULT 0,
            raised REAL DEFAULT 0,
            attributed REAL DEFAULT 0,
            commitment_amount REAL DEFAULT 0,
            fundraising_goal REAL DEFAULT 0,
            profile_image_url TEXT,
            -- Extended profile data (from user/{id} endpoint)
            first_name TEXT,
            last_name TEXT,
            registration_types TEXT,    -- JSON array
            story TEXT,
            is_donor_list_visible INTEGER,
            all_time_raised REAL DEFAULT 0,
            tags TEXT,                  -- JSON array
            current_event_name TEXT,
            -- Participant type details (from participantTypes)
            is_rider INTEGER DEFAULT 0,
            is_volunteer INTEGER DEFAULT 0,
            is_challenger INTEGER DEFAULT 0,
            ride_type TEXT,             -- 'signature', 'gravel', or NULL
            ride_types TEXT,            -- JSON array if multiple rides
            committed_amount REAL DEFAULT 0,
            personal_goal REAL DEFAULT 0,
            committed_high_roller INTEGER DEFAULT 0,
            -- Meta
            last_scraped TEXT,
            FOREIGN KEY (team_id) REFERENCES teams(id)
        );

        CREATE TABLE IF NOT EXISTS donations (
            opportunity_id TEXT PRIMARY KEY,
            recipient_public_id TEXT NOT NULL,
            event_id TEXT,
            event_name TEXT,
            amount REAL NOT NULL,
            date TEXT,
            is_recurring INTEGER DEFAULT 0,
            pending INTEGER DEFAULT 0,
            anonymous_to_public INTEGER DEFAULT 0,
            recognition_name TEXT,       -- ALWAYS present, even for anonymous donors
            donor_name TEXT,             -- 'Anonymous' if anonymousToPublic=true
            donor_public_id TEXT,        -- null if anonymous
            donor_profile_image_url TEXT,
            -- Meta
            last_scraped TEXT,
            FOREIGN KEY (recipient_public_id) REFERENCES members(public_id)
        );

        -- De-anonymization helper: maps recognition names to likely real identities
        -- recognitionName is leaked even when donor chooses anonymous
        CREATE TABLE IF NOT EXISTS donor_identities (
            recognition_name TEXT PRIMARY KEY,
            inferred_name TEXT,
            confidence TEXT,      -- 'high', 'medium', 'low'
            source TEXT,          -- how we inferred it
            donor_public_id TEXT,
            notes TEXT
        );

        -- Rides and routes reference data
        CREATE TABLE IF NOT EXISTS rides (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,                -- 'signature' or 'gravel'
            is_signature_ride INTEGER DEFAULT 0,
            status TEXT,
            registration_start TEXT,
            registration_end TEXT,
            ride_weekend_start TEXT,
            ride_weekend_end TEXT,
            last_scraped TEXT
        );

        CREATE TABLE IF NOT EXISTS routes (
            id TEXT PRIMARY KEY,
            ride_id TEXT,
            name TEXT NOT NULL,
            distance REAL,
            duration TEXT,
            fundraising_commitment REAL,
            capacity REAL,
            highest_incline REAL,
            start_date TEXT,
            image_url TEXT,
            starting_city TEXT,
            ending_city TEXT,
            last_scraped TEXT,
            FOREIGN KEY (ride_id) REFERENCES rides(id)
        );

        -- Daily snapshots for tracking fundraising growth over time
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            snapshot_date TEXT NOT NULL,
            team_id TEXT NOT NULL,
            raised REAL DEFAULT 0,
            goal REAL DEFAULT 0,
            all_time_raised REAL DEFAULT 0,
            members_count INTEGER DEFAULT 0,
            donations_count INTEGER DEFAULT 0,
            total_donated REAL DEFAULT 0,
            signature_riders INTEGER DEFAULT 0,
            gravel_riders INTEGER DEFAULT 0,
            PRIMARY KEY (snapshot_date, team_id)
        );

        -- Member route selections (from user/{id}/routes endpoint)
        CREATE TABLE IF NOT EXISTS member_routes (
            member_public_id TEXT NOT NULL,
            route_id TEXT NOT NULL,
            route_name TEXT,
            ride_type TEXT,
            distance REAL,
            fundraising_commitment REAL,
            last_scraped TEXT,
            PRIMARY KEY (member_public_id, route_id),
            FOREIGN KEY (member_public_id) REFERENCES members(public_id),
            FOREIGN KEY (route_id) REFERENCES routes(id)
        );

        -- Historical event metadata (from /api/events/all)
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            name TEXT,
            year INTEGER,
            total_participants REAL,
            status TEXT,
            fundraising_start TEXT,
            fundraising_end TEXT,
            ride_weekend_start TEXT,
            ride_weekend_end TEXT,
            last_scraped TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_member_routes_route ON member_routes(route_id);
        CREATE INDEX IF NOT EXISTS idx_member_routes_member ON member_routes(member_public_id);
        CREATE INDEX IF NOT EXISTS idx_members_team ON members(team_id);
        CREATE INDEX IF NOT EXISTS idx_donations_recipient ON donations(recipient_public_id);
        CREATE INDEX IF NOT EXISTS idx_donations_donor ON donations(donor_public_id);
        CREATE INDEX IF NOT EXISTS idx_donations_donor_name ON donations(donor_name);
        CREATE INDEX IF NOT EXISTS idx_donations_recognition ON donations(recognition_name);
        CREATE INDEX IF NOT EXISTS idx_donations_date ON donations(date);
        CREATE INDEX IF NOT EXISTS idx_donations_event ON donations(event_name);
        CREATE INDEX IF NOT EXISTS idx_snapshots_date ON daily_snapshots(snapshot_date);
    """)

    # Migration: add signup columns to existing daily_snapshots table
    try:
        conn.execute("ALTER TABLE daily_snapshots ADD COLUMN signature_riders INTEGER DEFAULT 0")
    except Exception:
        pass  # column already exists
    try:
        conn.execute("ALTER TABLE daily_snapshots ADD COLUMN gravel_riders INTEGER DEFAULT 0")
    except Exception:
        pass  # column already exists

    # Migration: add goal_override to teams table
    try:
        conn.execute("ALTER TABLE teams ADD COLUMN goal_override REAL")
    except Exception:
        pass  # column already exists

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
session = requests.Session()
session.headers.update({"Accept": "application/json"})


def api_get(path, retries=3, pagination_limit=None):
    """GET from the P3 API with retry logic and automatic pagination.

    Args:
        path: API endpoint path
        retries: Number of retry attempts
        pagination_limit: If set, fetches pages of this size until all results
            are retrieved.  The API uses header-based pagination with
            Pagination-Page, Pagination-Limit, Pagination-Count, Pagination-Total.
    """
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
                # Auto-paginate if this is a list endpoint with more pages
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

    # Get parent team detail
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
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
        1 if parent.get("acceptingNewMembers") else 0,
        parent.get("membersCount"), parent.get("numberOfSubPelotons"),
        parent.get("profileImageUrl"), parent.get("coverImageUrl"),
        fr.get("raised", 0), fr.get("goal", 0),
        1 if fr.get("goalAchieved") else 0,
        fr.get("allTimeRaised", 0),
        fr.get("totalRaisedByMembers", 0),
        fr.get("generalPelotonFunds", 0),
        now, parent.get("currentEventName"),
    ))

    # Search for all sub-teams
    log.info("Searching for Huntington sub-teams...")
    search_results = api_get("search/pelotons?query=huntington")
    if not search_results:
        log.error("Search failed")
        return []

    team_ids = [t["id"] for t in search_results if t["id"] != PARENT_TEAM_ID]
    log.info(f"Found {len(team_ids)} sub-teams")

    # Fetch detail for each sub-team
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
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            detail.get("captain", {}).get("name"),
            detail.get("captain", {}).get("publicId"),
            detail.get("yearsActive"), detail.get("story"),
            1 if detail.get("acceptingNewMembers") else 0,
            detail.get("membersCount"), detail.get("numberOfSubPelotons"),
            detail.get("profileImageUrl"), detail.get("coverImageUrl"),
            fr.get("raised", 0), fr.get("goal", 0),
            1 if fr.get("goalAchieved") else 0,
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
            INSERT OR REPLACE INTO rides
            (id, name, type, is_signature_ride, status,
             registration_start, registration_end,
             ride_weekend_start, ride_weekend_end, last_scraped)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            ride["id"], ride["name"], ride.get("type"),
            1 if ride.get("isSignatureRide") else 0,
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
                INSERT OR REPLACE INTO routes
                (id, ride_id, name, distance, duration, fundraising_commitment,
                 capacity, highest_incline, start_date, image_url,
                 starting_city, ending_city, last_scraped)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            INSERT OR REPLACE INTO events
            (id, name, year, total_participants, status,
             fundraising_start, fundraising_end,
             ride_weekend_start, ride_weekend_end, last_scraped)
            VALUES (?,?,?,?,?,?,?,?,?,?)
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
        team_ids = [row[0] for row in cursor]

    total_members = 0
    for tid in team_ids:
        time.sleep(REQUEST_DELAY)
        members = api_get(f"peloton/{tid}/members", pagination_limit=200)
        if not members or not isinstance(members, list):
            continue

        # Filter out sub-pelotons (they have membersCount > 0 and no commitmentAmount)
        individuals = [m for m in members if m.get("membersCount", 0) == 0]

        for m in individuals:
            conn.execute("""
                INSERT INTO members
                (public_id, name, team_id, is_captain, is_admin, is_cancer_survivor,
                 raised, attributed, commitment_amount, fundraising_goal,
                 profile_image_url, last_scraped)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
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
                1 if m.get("isCaptain") else 0,
                1 if m.get("isAdmin") else 0,
                1 if m.get("isCancerSurvivor") else 0,
                m.get("raised", 0), m.get("attributed", 0),
                m.get("commitmentAmount", 0), m.get("fundraisingGoal", 0),
                m.get("profileImageUrl"),
                now,
            ))
            total_members += 1

        team_name = conn.execute("SELECT name FROM teams WHERE id=?", (tid,)).fetchone()
        team_label = team_name[0] if team_name else tid
        log.info(f"  {team_label}: {len(individuals)} members")

    log.info(f"Total members scraped: {total_members}")
    return total_members


def scrape_member_profiles(conn, public_ids=None):
    """Fetch extended profile data for each member."""
    now = datetime.now(timezone.utc).isoformat()

    if public_ids is None:
        cursor = conn.execute("SELECT public_id FROM members")
        public_ids = [row[0] for row in cursor]

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
                first_name=?, last_name=?,
                registration_types=?, story=?,
                is_donor_list_visible=?, all_time_raised=?,
                tags=?, current_event_name=?,
                is_rider=?, is_volunteer=?, is_challenger=?,
                ride_type=?, ride_types=?,
                committed_amount=?, personal_goal=?,
                committed_high_roller=?,
                last_scraped=?
            WHERE public_id=?
        """, (
            profile.get("firstName"), profile.get("lastName"),
            json.dumps(profile.get("registrationTypes", [])),
            profile.get("story"),
            1 if profile.get("isDonorListVisible") else 0,
            fr.get("allTimeRaised", 0),
            json.dumps([t.get("name") for t in profile.get("tags", [])]),
            profile.get("currentEventName"),
            1 if pt.get("isRider") else 0,
            1 if pt.get("isVolunteer") else 0,
            1 if pt.get("isChallenger") else 0,
            primary_ride_type,
            json.dumps(ride_types) if ride_types else None,
            fr.get("committedAmount", 0),
            fr.get("goal", 0),
            1 if fr.get("committedHighRoller") else 0,
            now,
            pid,
        ))

        if (i + 1) % 25 == 0:
            log.info(f"  Profiles: {i+1}/{len(public_ids)}")

    log.info(f"Extended profiles complete")


def scrape_member_routes(conn, public_ids=None):
    """Fetch route selections for each member via user/{id}/routes endpoint.

    Queries ALL members because the profile API may return isRider=None even
    when a member has already selected a route.  After fetching, infers
    participant type from route data for any member whose profile flags are
    all zero/null.
    """
    now = datetime.now(timezone.utc).isoformat()

    if public_ids is None:
        cursor = conn.execute("SELECT public_id FROM members")
        public_ids = [row[0] for row in cursor]

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
                VALUES (?, ?, ?, ?, ?, ?, ?)
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

    # Infer participant type from route data for untyped members.
    # The profile API sometimes returns isRider/isChallenger as null even
    # when the member has selected a route.  Use ride_type to fix this.
    inferred = 0
    for pid in members_with_routes:
        row = conn.execute(
            "SELECT is_rider, is_challenger FROM members WHERE public_id=?", (pid,)
        ).fetchone()
        if row and row[0] == 0 and row[1] == 0:
            # Check what ride types this member has
            ride_types = conn.execute(
                "SELECT DISTINCT ride_type FROM member_routes WHERE member_public_id=?", (pid,)
            ).fetchall()
            types = {r[0] for r in ride_types if r[0]}
            if "gravel" in types:
                conn.execute("UPDATE members SET is_challenger=1 WHERE public_id=?", (pid,))
                inferred += 1
            elif "signature" in types:
                conn.execute("UPDATE members SET is_rider=1 WHERE public_id=?", (pid,))
                inferred += 1

    if inferred:
        log.info(f"Inferred participant type from routes for {inferred} members")

    log.info(f"Member routes complete — {total_routes} route selections stored")


def scrape_donations(conn, public_ids=None):
    """Scrape donations received by each member."""
    now = datetime.now(timezone.utc).isoformat()

    if public_ids is None:
        # Only scrape members who have their donor list visible
        cursor = conn.execute(
            "SELECT public_id FROM members WHERE is_donor_list_visible=1 OR is_donor_list_visible IS NULL"
        )
        public_ids = [row[0] for row in cursor]

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
                INSERT OR REPLACE INTO donations
                (opportunity_id, recipient_public_id, event_id, event_name,
                 amount, date, is_recurring, pending, anonymous_to_public,
                 recognition_name, donor_name, donor_public_id,
                 donor_profile_image_url, last_scraped)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                d["opportunityId"], pid,
                d.get("eventId"), d.get("eventName"),
                d.get("amount", 0), d.get("date"),
                1 if d.get("isRecurring") else 0,
                1 if d.get("pending") else 0,
                1 if d.get("anonymousToPublic") else 0,
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

    # Snapshot for parent team (overall totals)
    parent = conn.execute(
        "SELECT raised, goal, all_time_raised, members_count FROM teams WHERE id=?",
        (PARENT_TEAM_ID,),
    ).fetchone()
    if parent:
        total_members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        total_donations = conn.execute("SELECT COUNT(*) FROM donations").fetchone()[0]
        total_donated = conn.execute("SELECT COALESCE(SUM(amount),0) FROM donations").fetchone()[0]
        sig_riders = conn.execute(
            "SELECT COUNT(DISTINCT member_public_id) FROM member_routes WHERE ride_type='signature'"
        ).fetchone()[0]
        grv_riders = conn.execute(
            "SELECT COUNT(DISTINCT member_public_id) FROM member_routes WHERE ride_type='gravel'"
        ).fetchone()[0]
        conn.execute("""
            INSERT OR REPLACE INTO daily_snapshots
            (snapshot_date, team_id, raised, goal, all_time_raised,
             members_count, donations_count, total_donated,
             signature_riders, gravel_riders)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (today, PARENT_TEAM_ID, parent[0], parent[1], parent[2],
              total_members, total_donations, total_donated,
              sig_riders, grv_riders))

    # Snapshot for each sub-team
    rows = conn.execute(
        "SELECT id, raised, goal, all_time_raised, members_count FROM teams WHERE parent_id=?",
        (PARENT_TEAM_ID,),
    ).fetchall()
    for r in rows:
        team_donations = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(d.amount),0) FROM donations d "
            "JOIN members m ON d.recipient_public_id=m.public_id WHERE m.team_id=?",
            (r[0],),
        ).fetchone()
        conn.execute("""
            INSERT OR REPLACE INTO daily_snapshots
            (snapshot_date, team_id, raised, goal, all_time_raised,
             members_count, donations_count, total_donated)
            VALUES (?,?,?,?,?,?,?,?)
        """, (today, r[0], r[1], r[2], r[3], int(r[4] or 0),
              team_donations[0], team_donations[1]))

    log.info(f"Recorded daily snapshot for {today}")


def scrape_incremental(conn):
    """Incremental scrape: refresh teams + members, only fetch what changed.

    API call budget (scales with member count N):
    - Rides/routes: 3 calls (fixed)
    - Teams: ~17 calls (fixed — 1 parent + 1 search + 15 sub-teams)
    - Member lists: ~14 calls (fixed — one per sub-team)
    - Profiles: only new/stale members (0 when stable)
    - Routes: only new members without route data (0 when stable)
    - Donations: only members whose raised $ changed (0 when stable)
    Total when stable: ~34 calls regardless of team size.
    """
    start = time.time()
    log.info("Starting incremental scrape...")

    # 1. Rides & routes (always refresh — 3 calls)
    scrape_rides_and_routes(conn)

    # 2. Teams (always refresh — lightweight)
    team_ids = scrape_teams(conn)
    sub_team_ids = [tid for tid in team_ids if tid != PARENT_TEAM_ID]

    # 3. Snapshot pre-scrape state for change detection
    pre_raised = {}
    pre_team = {}
    for row in conn.execute("SELECT public_id, raised, team_id FROM members"):
        pre_raised[row[0]] = row[1]
        pre_team[row[0]] = row[2]
    pre_member_ids = set(pre_raised.keys())

    # 4. Members (always refresh — one call per sub-team)
    #    The ON CONFLICT UPDATE handles team changes automatically:
    #    if a member moved sub-teams, team_id gets updated.
    scrape_members(conn, sub_team_ids)

    # 4b. Detect disappeared members (cancelled, removed, or pending approval revoked).
    #    Members in the DB but not seen in any team roster this run.
    current_member_ids = set()
    for row in conn.execute("SELECT public_id FROM members WHERE last_scraped >= ?",
                            (datetime.now(timezone.utc).strftime("%Y-%m-%d"),)):
        current_member_ids.add(row[0])
    disappeared = pre_member_ids - current_member_ids
    if disappeared:
        log.info(f"Detected {len(disappeared)} members no longer on any roster")
        for pid in disappeared:
            old_team = pre_team.get(pid, "?")
            name = conn.execute("SELECT name FROM members WHERE public_id=?", (pid,)).fetchone()
            log.info(f"  GONE: {name[0] if name else pid} (was on team {old_team})")
        # Don't delete — just log. They may be pending re-approval or temporarily removed.
        # Their last_scraped date stays stale, making them easy to query.

    # 4c. Detect team changes
    for row in conn.execute("SELECT public_id, team_id FROM members"):
        old_tid = pre_team.get(row[0])
        if old_tid and old_tid != row[1]:
            name = conn.execute("SELECT name FROM members WHERE public_id=?", (row[0],)).fetchone()
            log.info(f"  MOVED: {name[0] if name else row[0]} from {old_tid} -> {row[1]}")

    # 5. Extended profiles — fetch for new/stale/old members.
    #    Stale = profile never fetched (first_name IS NULL)
    #    or untyped (all participation flags are 0 — may be pending approval).
    #    Old = profile not refreshed in 7+ days (catches commitment changes, etc.)
    new_member_ids = current_member_ids - pre_member_ids
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    stale_members = conn.execute("""
        SELECT public_id FROM members
        WHERE first_name IS NULL
           OR (is_rider=0 AND is_challenger=0 AND is_volunteer=0
               AND is_rider IS NOT NULL)
           OR last_scraped < ?
    """, (stale_cutoff,)).fetchall()
    stale_ids = list(set([r[0] for r in stale_members]) | new_member_ids)
    if stale_ids:
        log.info(f"Fetching profiles for {len(stale_ids)} new/stale/old members "
                 f"({len(new_member_ids)} new, {len(stale_ids) - len(new_member_ids)} stale/old)...")
        scrape_member_profiles(conn, stale_ids)
    else:
        log.info("All members have fresh profile data — skipping profile fetch")

    # 5b. Member route selections.
    #    Fetch for members without route data AND re-fetch for members whose
    #    profile was just refreshed (catches route changes).
    #    Clear old routes before re-fetching to avoid stale entries.
    members_with_routes = set()
    for row in conn.execute("SELECT DISTINCT member_public_id FROM member_routes"):
        members_with_routes.add(row[0])
    needs_routes_new = [pid for pid in current_member_ids if pid not in members_with_routes]
    needs_routes_refresh = [pid for pid in stale_ids if pid in members_with_routes]
    needs_routes = list(set(needs_routes_new + needs_routes_refresh))
    if needs_routes:
        # Clear stale routes for members being re-fetched
        if needs_routes_refresh:
            log.info(f"Clearing stale routes for {len(needs_routes_refresh)} members before re-fetch...")
            for pid in needs_routes_refresh:
                conn.execute("DELETE FROM member_routes WHERE member_public_id=?", (pid,))
        log.info(f"Fetching routes for {len(needs_routes)} members "
                 f"({len(needs_routes_new)} new, {len(needs_routes_refresh)} refresh)...")
        scrape_member_routes(conn, needs_routes)
    else:
        log.info("All members have route data — skipping route fetch")

    # 6. Donations — only for members whose raised amount changed
    changed = []
    for row in conn.execute("SELECT public_id, raised FROM members"):
        old = pre_raised.get(row[0])
        if old is None or abs(row[1] - old) > 0.01:
            changed.append(row[0])

    if changed:
        log.info(f"Fundraising changed for {len(changed)} members — fetching donations...")
        scrape_donations(conn, changed)
    else:
        log.info("No fundraising changes detected — skipping donation scrape")

    # 7. Donor identities + snapshot
    build_donor_identities(conn)
    record_daily_snapshot(conn)

    # 8. Single atomic commit — all changes visible at once to the dashboard
    conn.commit()

    elapsed = time.time() - start
    log.info(f"Incremental scrape complete in {elapsed:.0f}s")


def build_donor_identities(conn):
    """Cross-reference anonymous donations with non-anonymous ones to de-anonymize."""
    log.info("Building donor identity map...")

    # Strategy 1: Same recognitionName appears in both anonymous and non-anonymous donations
    # If "Jeremy D" donated non-anonymously somewhere else, we know who they are
    conn.execute("""
        INSERT OR REPLACE INTO donor_identities (recognition_name, inferred_name, confidence, source, donor_public_id)
        SELECT
            anon.recognition_name,
            known.donor_name,
            'high',
            'same_recognition_name_matched_to_non_anonymous_donation',
            known.donor_public_id
        FROM donations anon
        JOIN donations known ON anon.recognition_name = known.recognition_name
            AND known.anonymous_to_public = 0
            AND known.donor_name IS NOT NULL
            AND known.donor_name != 'Anonymous'
        WHERE anon.anonymous_to_public = 1
        GROUP BY anon.recognition_name
    """)

    # Strategy 2: recognitionName closely matches a known donor_name
    # e.g., "Tony Farinacci" -> "Anthony Farinacci"
    conn.execute("""
        INSERT OR IGNORE INTO donor_identities (recognition_name, inferred_name, confidence, source, donor_public_id)
        SELECT DISTINCT
            d.recognition_name,
            d.recognition_name,
            'medium',
            'recognition_name_is_likely_real_name',
            NULL
        FROM donations d
        WHERE d.anonymous_to_public = 1
            AND d.recognition_name IS NOT NULL
            AND d.recognition_name != ''
            AND d.recognition_name NOT IN (SELECT recognition_name FROM donor_identities)
    """)

    # Strategy 3: Same amount + same date pattern (within same recipient) may link to known donor
    # This is lower confidence, skip for now

    count = conn.execute("SELECT COUNT(*) FROM donor_identities").fetchone()[0]
    log.info(f"Donor identity map: {count} entries")


def print_summary(conn):
    """Print a summary of the database contents."""
    print("\n" + "=" * 60)
    print("PELOTONIA DATABASE SUMMARY")
    print("=" * 60)

    teams = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    donations = conn.execute("SELECT COUNT(*) FROM donations").fetchone()[0]

    print(f"\nTotals: {teams} teams | {members} members | {donations} donation records")

    # Parent team stats
    parent = conn.execute(
        "SELECT name, raised, goal, all_time_raised, members_count FROM teams WHERE id=?",
        (PARENT_TEAM_ID,)
    ).fetchone()
    if parent:
        print(f"\n{parent[0]}:")
        print(f"  2026 Raised:  ${parent[1]:>12,.2f} / ${parent[2]:>12,.2f} goal ({parent[1]/parent[2]*100 if parent[2] else 0:.1f}%)")
        print(f"  All-time:     ${parent[3]:>12,.2f}")

    # Sub-team breakdown
    print("\nSub-team breakdown:")
    rows = conn.execute(
        "SELECT name, raised, goal, all_time_raised, members_count "
        "FROM teams WHERE parent_id=? ORDER BY raised DESC",
        (PARENT_TEAM_ID,)
    ).fetchall()
    for r in rows:
        pct = f"{r[1]/r[2]*100:.0f}%" if r[2] and r[2] > 0 else "N/A"
        print(f"  {r[0]:55s} ${r[1]:>10,.0f}  ({pct:>4s} of ${r[2]:>10,.0f})  {r[4]:.0f} members  all-time: ${r[3]:>12,.0f}")

    # Top fundraisers
    print("\nTop 15 fundraisers (current year):")
    rows = conn.execute(
        "SELECT m.name, m.raised, m.all_time_raised, t.name "
        "FROM members m LEFT JOIN teams t ON m.team_id=t.id "
        "ORDER BY m.raised DESC LIMIT 15"
    ).fetchall()
    for i, r in enumerate(rows, 1):
        team_short = r[3].replace("Team Huntington Bank - ", "") if r[3] else "?"
        print(f"  {i:2d}. {r[0]:25s} ${r[1]:>10,.0f}  (all-time: ${r[2]:>12,.0f})  [{team_short}]")

    # Top donors
    print("\nTop 15 donors (by total donated this year):")
    rows = conn.execute(
        "SELECT COALESCE(recognition_name, donor_name, 'Anonymous'), "
        "       SUM(amount), COUNT(*) "
        "FROM donations "
        "WHERE anonymous_to_public=0 "
        "GROUP BY COALESCE(recognition_name, donor_name) "
        "ORDER BY SUM(amount) DESC LIMIT 15"
    ).fetchall()
    for i, r in enumerate(rows, 1):
        print(f"  {i:2d}. {r[0]:35s} ${r[1]:>10,.0f}  ({r[2]} donations)")

    # Cancer survivors
    survivors = conn.execute("SELECT COUNT(*) FROM members WHERE is_cancer_survivor=1").fetchone()[0]
    high_rollers = conn.execute("SELECT COUNT(*) FROM members WHERE tags LIKE '%High Roller%'").fetchone()[0]
    print(f"\nCancer survivors on team: {survivors}")
    print(f"High Rollers: {high_rollers}")

    # Donation date range
    date_range = conn.execute(
        "SELECT MIN(date), MAX(date), COUNT(DISTINCT event_name) FROM donations"
    ).fetchone()
    if date_range and date_range[0]:
        print(f"\nDonation date range: {date_range[0][:10]} to {date_range[1][:10]}")
        print(f"Event years covered: {date_range[2]}")

    # Donation totals
    totals = conn.execute(
        "SELECT SUM(amount), COUNT(*), COUNT(DISTINCT recognition_name) FROM donations"
    ).fetchone()
    if totals:
        print(f"Total donated: ${totals[0]:,.2f} across {totals[1]} transactions from {totals[2]} unique donors")

    # Anonymous stats
    anon = conn.execute(
        "SELECT COUNT(*), SUM(amount) FROM donations WHERE anonymous_to_public=1"
    ).fetchone()
    if anon and anon[0]:
        print(f"Anonymous donations: {anon[0]} totaling ${anon[1]:,.2f}")

    # De-anonymization stats
    identities = conn.execute("SELECT COUNT(*) FROM donor_identities").fetchone()[0]
    high_conf = conn.execute("SELECT COUNT(*) FROM donor_identities WHERE confidence='high'").fetchone()[0]
    if identities:
        print(f"De-anonymized donors: {identities} ({high_conf} high confidence)")
        print("\nDe-anonymized anonymous donors:")
        rows = conn.execute(
            "SELECT di.recognition_name, di.inferred_name, di.confidence, d.amount "
            "FROM donor_identities di "
            "JOIN donations d ON d.recognition_name = di.recognition_name AND d.anonymous_to_public=1 "
            "ORDER BY d.amount DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print(f"  {r[0]:30s} -> {r[1]:25s} ({r[2]})  ${r[3]:,.0f}")

    # Scrape freshness
    last = conn.execute("SELECT MAX(last_scraped) FROM members").fetchone()[0]
    print(f"\nLast scraped: {last}")
    print("=" * 60 + "\n")


def export_csv(conn):
    """Export all tables to CSV files."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    for table in ["teams", "members", "donations"]:
        cursor = conn.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()

        path = CSV_DIR / f"{table}_{timestamp}.csv"
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)
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
    parser.add_argument("--db", default=str(DB_PATH), help="Database path")
    parser.add_argument("--skip-donations", action="store_true", help="Skip donation scraping (faster)")
    parser.add_argument("--skip-profiles", action="store_true", help="Skip extended profile scraping")
    parser.add_argument("--incremental", action="store_true",
                        help="Incremental scrape: only fetch new data (ideal for daily cron)")
    parser.add_argument("--backfill-donations", action="store_true",
                        help="Fetch donations for members with raised > 0 but no donation records")
    args = parser.parse_args()

    conn = init_db(args.db)

    if args.summary:
        print_summary(conn)
        conn.close()
        return

    if args.export_csv:
        export_csv(conn)
        conn.close()
        return

    # Backfill donations for members with raised > 0 but no donation records
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
            for pid, name, raised in missing[:5]:
                log.info(f"  e.g. {name}: ${raised:,.0f} raised, 0 donation records")
            pids = [r[0] for r in missing]
            scrape_donations(conn, pids)
            build_donor_identities(conn)
            conn.commit()
        print_summary(conn)
        conn.close()
        return

    # Incremental mode (for daily cron jobs)
    if args.incremental:
        scrape_incremental(conn)
        print_summary(conn)
        conn.close()
        return

    # Full scrape
    start = time.time()
    log.info("Starting Pelotonia scrape...")

    # 0. Historical event metadata (static, lightweight)
    fetch_events(conn)

    # 1. Rides & routes
    scrape_rides_and_routes(conn)

    # 2. Teams
    if args.team_id:
        team_ids = [args.team_id]
    else:
        team_ids = scrape_teams(conn)

    if args.teams_only:
        conn.commit()
        print_summary(conn)
        conn.close()
        return

    # 3. Members
    sub_team_ids = [tid for tid in team_ids if tid != PARENT_TEAM_ID]
    scrape_members(conn, sub_team_ids)

    # 4. Extended profiles
    if not args.skip_profiles:
        scrape_member_profiles(conn)

    # 4b. Member route selections
    scrape_member_routes(conn)

    # 5. Donations
    if not args.skip_donations:
        scrape_donations(conn)

    # 6. Build donor identity map + daily snapshot
    build_donor_identities(conn)
    record_daily_snapshot(conn)

    # Single atomic commit — all changes visible at once
    conn.commit()

    elapsed = time.time() - start
    log.info(f"Scrape complete in {elapsed:.0f}s")

    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
