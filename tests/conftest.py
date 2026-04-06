"""Shared fixtures for Pelotonia Dashboard API tests."""

import sqlite3

import pytest

PARENT_TEAM_ID = "a0s3t00000BKX8sAAH"


def _create_schema(conn):
    """Create the full database schema matching init_db from all scrapers."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level TEXT,
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
            raised REAL DEFAULT 0,
            goal REAL DEFAULT 0,
            goal_override REAL,
            goal_achieved INTEGER DEFAULT 0,
            all_time_raised REAL DEFAULT 0,
            total_raised_by_members REAL DEFAULT 0,
            general_peloton_funds REAL DEFAULT 0,
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
            first_name TEXT,
            last_name TEXT,
            registration_types TEXT,
            story TEXT,
            is_donor_list_visible INTEGER,
            all_time_raised REAL DEFAULT 0,
            tags TEXT,
            current_event_name TEXT,
            is_rider INTEGER DEFAULT 0,
            is_volunteer INTEGER DEFAULT 0,
            is_challenger INTEGER DEFAULT 0,
            ride_type TEXT,
            ride_types TEXT,
            committed_amount REAL DEFAULT 0,
            personal_goal REAL DEFAULT 0,
            committed_high_roller INTEGER DEFAULT 0,
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
            recognition_name TEXT,
            donor_name TEXT,
            donor_public_id TEXT,
            donor_profile_image_url TEXT,
            last_scraped TEXT,
            FOREIGN KEY (recipient_public_id) REFERENCES members(public_id)
        );

        CREATE TABLE IF NOT EXISTS donor_identities (
            recognition_name TEXT PRIMARY KEY,
            inferred_name TEXT,
            confidence TEXT,
            source TEXT,
            donor_public_id TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS rides (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
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
            riders_count INTEGER DEFAULT 0,
            challengers_count INTEGER DEFAULT 0,
            volunteers_count INTEGER DEFAULT 0,
            PRIMARY KEY (snapshot_date, team_id)
        );

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

        CREATE TABLE IF NOT EXISTS kids_snapshots (
            snapshot_date TEXT NOT NULL,
            campaign_id TEXT NOT NULL DEFAULT 'dbpr4x7j9x',
            fundraiser_count INTEGER DEFAULT 0,
            estimated_amount_raised REAL DEFAULT 0,
            monetary_goal REAL DEFAULT 0,
            team_count INTEGER DEFAULT 0,
            last_scraped TEXT,
            PRIMARY KEY (snapshot_date, campaign_id)
        );

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


def _seed_data(conn):
    """Insert realistic seed data for testing."""
    # Parent team
    conn.execute(
        "INSERT INTO teams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            PARENT_TEAM_ID, "Team Huntington Bank", "Super", None,
            "Captain Jane", "cap001", 5.0, "Our story", 1,
            5.0, 2.0, None, None,
            15000.0, 50000.0, None, 0, 120000.0, 14000.0, 1000.0,
            "2026-04-01T12:00:00", "Pelotonia 2026",
        ),
    )

    # Sub-teams
    conn.execute(
        "INSERT INTO teams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "sub001", "Sub-Team Alpha", "Sub", PARENT_TEAM_ID,
            "Captain A", "capa", 3.0, None, 1,
            3.0, 0.0, None, None,
            9000.0, 25000.0, None, 0, 70000.0, 8500.0, 500.0,
            "2026-04-01T12:00:00", "Pelotonia 2026",
        ),
    )
    conn.execute(
        "INSERT INTO teams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "sub002", "Sub-Team Beta", "Sub", PARENT_TEAM_ID,
            "Captain B", "capb", 2.0, None, 1,
            2.0, 0.0, None, None,
            6000.0, 25000.0, None, 0, 50000.0, 5500.0, 500.0,
            "2026-04-01T12:00:00", "Pelotonia 2026",
        ),
    )

    # Members: 3 riders, 1 challenger, 1 volunteer spread across sub-teams
    members = [
        ("m001", "Alice Rider", "sub001", 0, 0, 1, 5000.0, 0, 2000, 5000, None,
         "Alice", "Rider", '["Rider"]', None, 1, 30000.0, '["3 years", "High Roller"]',
         "Pelotonia 2026", 1, 0, 0, "signature", None, 2000.0, 5000.0, 1,
         "2026-04-01T12:00:00"),
        ("m002", "Bob Rider", "sub001", 0, 0, 0, 3000.0, 0, 1500, 3000, None,
         "Bob", "Rider", '["Rider"]', None, 1, 20000.0, '["1 year"]',
         "Pelotonia 2026", 1, 0, 0, "signature", None, 1500.0, 3000.0, 0,
         "2026-04-01T12:00:00"),
        ("m003", "Carol Rider", "sub001", 0, 0, 0, 1000.0, 0, 1000, 2000, None,
         "Carol", "Rider", '["Rider"]', None, 1, 10000.0, '["2 years"]',
         "Pelotonia 2026", 1, 0, 0, "gravel", None, 1000.0, 2000.0, 0,
         "2026-04-01T12:00:00"),
        ("m004", "Dave Challenger", "sub002", 0, 0, 0, 500.0, 0, 500, 1000, None,
         "Dave", "Challenger", '["Challenger"]', None, 1, 5000.0, '["1 year"]',
         "Pelotonia 2026", 0, 0, 1, None, None, 500.0, 1000.0, 0,
         "2026-04-01T12:00:00"),
        ("m005", "Eve Volunteer", "sub002", 0, 0, 0, 0.0, 0, 0, 0, None,
         "Eve", "Volunteer", '["Volunteer"]', None, 1, 0.0, '[]',
         "Pelotonia 2026", 0, 1, 0, None, None, 0.0, 0.0, 0,
         "2026-04-01T12:00:00"),
    ]
    for m in members:
        conn.execute(
            "INSERT INTO members VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            m,
        )

    # Donations (10 total, spread across members)
    donations = [
        ("d001", "m001", "ev1", "Pelotonia 2026", 500.0, "2026-01-15", 0, 0, 0, "Acme Corp", "John Smith", "dp001", None, "2026-04-01"),
        ("d002", "m001", "ev1", "Pelotonia 2026", 250.0, "2026-01-20", 0, 0, 0, "Acme Corp", "Jane Doe", "dp002", None, "2026-04-01"),
        ("d003", "m001", "ev1", "Pelotonia 2026", 100.0, "2026-02-01", 0, 0, 1, None, "Anonymous", None, None, "2026-04-01"),
        ("d004", "m002", "ev1", "Pelotonia 2026", 1000.0, "2026-02-10", 0, 0, 0, "Big Co", "Pat Lee", "dp003", None, "2026-04-01"),
        ("d005", "m002", "ev1", "Pelotonia 2026", 200.0, "2026-02-15", 0, 0, 0, None, "Sam Green", "dp004", None, "2026-04-01"),
        ("d006", "m003", "ev1", "Pelotonia 2026", 300.0, "2026-03-01", 0, 0, 0, None, "Kim White", "dp005", None, "2026-04-01"),
        ("d007", "m003", "ev1", "Pelotonia 2026", 150.0, "2026-03-05", 0, 0, 0, None, "Tim Black", "dp006", None, "2026-04-01"),
        ("d008", "m004", "ev1", "Pelotonia 2026", 75.0, "2026-03-10", 0, 0, 0, None, "Liz Brown", "dp007", None, "2026-04-01"),
        ("d009", "m004", "ev1", "Pelotonia 2026", 50.0, "2026-03-15", 0, 0, 0, None, "Dan Gray", "dp008", None, "2026-04-01"),
        ("d010", "m001", "ev1", "Pelotonia 2026", 25.0, "2026-03-20", 0, 0, 0, "Acme Corp", "John Smith", "dp001", None, "2026-04-01"),
    ]
    for d in donations:
        conn.execute(
            "INSERT INTO donations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            d,
        )

    # Rides: signature + gravel
    conn.execute(
        "INSERT INTO rides VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("ride_sig", "Signature Ride 2026", "signature", 1, "active",
         "2026-01-01", "2026-07-01", "2026-08-01", "2026-08-02", "2026-04-01"),
    )
    conn.execute(
        "INSERT INTO rides VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("ride_grv", "Gravel Day 2026", "gravel", 0, "active",
         "2026-01-01", "2026-07-01", "2026-09-01", "2026-09-01", "2026-04-01"),
    )

    # Routes
    conn.execute(
        "INSERT INTO routes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("route_100", "ride_sig", "100 Mile Signature", 100.0, "8h", 2000.0,
         500.0, 3.5, "2026-08-01", None, "Columbus", "Gambier", "2026-04-01"),
    )
    conn.execute(
        "INSERT INTO routes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("route_grv50", "ride_grv", "50 Mile Gravel", 50.0, "5h", 1000.0,
         200.0, 2.0, "2026-09-01", None, "Columbus", "Sunbury", "2026-04-01"),
    )

    # Member route entry (Alice on 100-mile signature)
    conn.execute(
        "INSERT INTO member_routes VALUES (?,?,?,?,?,?,?)",
        ("m001", "route_100", "100 Mile Signature", "signature", 100.0, 2000.0, "2026-04-01"),
    )

    # Daily snapshots (2 dates for timeline)
    conn.execute(
        "INSERT INTO daily_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("2026-03-30", PARENT_TEAM_ID, 12000.0, 50000.0, 115000.0, 4, 8, 2300.0, 2, 1, 3, 1, 0),
    )
    conn.execute(
        "INSERT INTO daily_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("2026-04-01", PARENT_TEAM_ID, 15000.0, 50000.0, 120000.0, 5, 10, 2650.0, 2, 1, 3, 1, 1),
    )

    # Kids snapshot
    conn.execute(
        "INSERT INTO kids_snapshots VALUES (?,?,?,?,?,?,?)",
        ("2026-04-01", "dbpr4x7j9x", 150, 45000.0, 100000.0, 12, "2026-04-01T10:00:00"),
    )

    # Org snapshots (2 orgs)
    conn.execute(
        "INSERT INTO org_snapshots VALUES (?,?,?,?,?,?,?,?,?)",
        ("2026-04-01", "org001", "Org One", 200, 10, 80000.0, 100000.0, 500000.0, "2026-04-01T10:00:00"),
    )
    conn.execute(
        "INSERT INTO org_snapshots VALUES (?,?,?,?,?,?,?,?,?)",
        ("2026-04-01", "org002", "Org Two", 150, 8, 60000.0, 80000.0, 400000.0, "2026-04-01T10:00:00"),
    )

    conn.commit()


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary SQLite database with full schema and seed data."""
    db_path = tmp_path / "test_pelotonia.db"
    conn = sqlite3.connect(str(db_path))
    _create_schema(conn)
    _seed_data(conn)
    conn.close()
    return db_path


@pytest.fixture
def client(test_db, monkeypatch):
    """Flask test client with DB_PATH patched to the test database."""
    import app.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module, "DB_PATH", test_db)
    # Reset the mtime cache so each test starts fresh
    dashboard_module._cache["data"] = None
    dashboard_module._cache["db_mtime"] = 0

    dashboard_module.app.config["TESTING"] = True
    with dashboard_module.app.test_client() as c:
        yield c
