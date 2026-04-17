"""Shared fixtures for Pelotonia Dashboard API tests.

Requires a Postgres instance. Set TEST_DATABASE_DSN or defaults to:
  postgresql://localhost:5432/pelotonia_test

Tests are skipped if the database is unreachable.
"""

import os

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

PARENT_TEAM_ID = "a0s3t00000BKX8sAAH"
TEST_DSN = os.environ.get("TEST_DATABASE_DSN", "postgresql://localhost:5432/pelotonia_test")


def _pg_available():
    try:
        conn = psycopg.connect(TEST_DSN, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_available(),
    reason=f"Postgres not reachable at {TEST_DSN}"
)


def _create_schema(conn):
    """Create the full database schema from schema.sql."""
    import pathlib
    schema_path = pathlib.Path(__file__).resolve().parent.parent / "app" / "schema.sql"
    with open(schema_path) as f:
        conn.execute(f.read())
    conn.commit()


def _drop_all_tables(conn):
    """Drop all known tables (cleanup between tests)."""
    tables = [
        "member_routes", "donations", "donor_identities",
        "daily_snapshots", "kids_snapshots", "org_snapshots",
        "events", "routes", "rides", "members", "teams",
    ]
    for t in tables:
        conn.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    conn.commit()


def _seed_data(conn):
    """Insert realistic seed data for testing."""
    conn.execute(
        """INSERT INTO teams (id, name, level, parent_id, captain_name, captain_public_id,
           years_active, story, accepting_members, members_count, num_sub_pelotons,
           profile_image_url, cover_image_url, raised, goal, goal_override, goal_achieved,
           all_time_raised, total_raised_by_members, general_peloton_funds,
           last_scraped, current_event_name)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (PARENT_TEAM_ID, "Team Huntington Bank", "Super", None,
         "Captain Jane", "cap001", 5.0, "Our story", True,
         5.0, 2.0, None, None,
         15000.0, 50000.0, None, False, 120000.0, 14000.0, 1000.0,
         "2026-04-01T12:00:00", "Pelotonia 2026"),
    )

    for tid, name in [("sub001", "Sub-Team Alpha"), ("sub002", "Sub-Team Beta")]:
        raised = 9000.0 if tid == "sub001" else 6000.0
        members_cnt = 3.0 if tid == "sub001" else 2.0
        at_raised = 70000.0 if tid == "sub001" else 50000.0
        trm = 8500.0 if tid == "sub001" else 5500.0
        conn.execute(
            """INSERT INTO teams (id, name, level, parent_id, captain_name, captain_public_id,
               years_active, story, accepting_members, members_count, num_sub_pelotons,
               profile_image_url, cover_image_url, raised, goal, goal_override, goal_achieved,
               all_time_raised, total_raised_by_members, general_peloton_funds,
               last_scraped, current_event_name)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (tid, name, "Sub", PARENT_TEAM_ID,
             f"Captain {tid}", f"cap{tid}", 3.0, None, True,
             members_cnt, 0.0, None, None,
             raised, 25000.0, None, False, at_raised, trm, 500.0,
             "2026-04-01T12:00:00", "Pelotonia 2026"),
        )

    members = [
        ("m001", "Alice Rider", "sub001", False, False, True, 5000.0, 0, 2000, 5000, None,
         "Alice", "Rider", '["Rider"]', None, True, 30000.0, '["3 years", "High Roller"]',
         "Pelotonia 2026", True, False, False, "signature", None, 2000.0, 5000.0, True,
         "2026-04-01T12:00:00"),
        ("m002", "Bob Rider", "sub001", False, False, False, 3000.0, 0, 1500, 3000, None,
         "Bob", "Rider", '["Rider"]', None, True, 20000.0, '["1 year"]',
         "Pelotonia 2026", True, False, False, "signature", None, 1500.0, 3000.0, False,
         "2026-04-01T12:00:00"),
        ("m003", "Carol Rider", "sub001", False, False, False, 1000.0, 0, 1000, 2000, None,
         "Carol", "Rider", '["Rider"]', None, True, 10000.0, '["2 years"]',
         "Pelotonia 2026", True, False, False, "gravel", None, 1000.0, 2000.0, False,
         "2026-04-01T12:00:00"),
        ("m004", "Dave Challenger", "sub002", False, False, False, 500.0, 0, 500, 1000, None,
         "Dave", "Challenger", '["Challenger"]', None, True, 5000.0, '["1 year"]',
         "Pelotonia 2026", False, False, True, None, None, 500.0, 1000.0, False,
         "2026-04-01T12:00:00"),
        ("m005", "Eve Volunteer", "sub002", False, False, False, 0.0, 0, 0, 0, None,
         "Eve", "Volunteer", '["Volunteer"]', None, True, 0.0, '[]',
         "Pelotonia 2026", False, True, False, None, None, 0.0, 0.0, False,
         "2026-04-01T12:00:00"),
    ]
    for m in members:
        conn.execute(
            """INSERT INTO members (public_id, name, team_id, is_captain, is_admin,
               is_cancer_survivor, raised, attributed, commitment_amount, fundraising_goal,
               profile_image_url, first_name, last_name, registration_types, story,
               is_donor_list_visible, all_time_raised, tags, current_event_name,
               is_rider, is_volunteer, is_challenger, ride_type, ride_types,
               committed_amount, personal_goal, committed_high_roller, last_scraped)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            m,
        )

    donations = [
        ("d001", "m001", "ev1", "Pelotonia 2026", 500.0, "2026-01-15", False, False, False, "Acme Corp", "John Smith", "dp001", None, "2026-04-01"),
        ("d002", "m001", "ev1", "Pelotonia 2026", 250.0, "2026-01-20", False, False, False, "Acme Corp", "Jane Doe", "dp002", None, "2026-04-01"),
        ("d003", "m001", "ev1", "Pelotonia 2026", 100.0, "2026-02-01", False, False, True, None, "Anonymous", None, None, "2026-04-01"),
        ("d004", "m002", "ev1", "Pelotonia 2026", 1000.0, "2026-02-10", False, False, False, "Big Co", "Pat Lee", "dp003", None, "2026-04-01"),
        ("d005", "m002", "ev1", "Pelotonia 2026", 200.0, "2026-02-15", False, False, False, None, "Sam Green", "dp004", None, "2026-04-01"),
        ("d006", "m003", "ev1", "Pelotonia 2026", 300.0, "2026-03-01", False, False, False, None, "Kim White", "dp005", None, "2026-04-01"),
        ("d007", "m003", "ev1", "Pelotonia 2026", 150.0, "2026-03-05", False, False, False, None, "Tim Black", "dp006", None, "2026-04-01"),
        ("d008", "m004", "ev1", "Pelotonia 2026", 75.0, "2026-03-10", False, False, False, None, "Liz Brown", "dp007", None, "2026-04-01"),
        ("d009", "m004", "ev1", "Pelotonia 2026", 50.0, "2026-03-15", False, False, False, None, "Dan Gray", "dp008", None, "2026-04-01"),
        ("d010", "m001", "ev1", "Pelotonia 2026", 25.0, "2026-03-20", False, False, False, "Acme Corp", "John Smith", "dp001", None, "2026-04-01"),
    ]
    for d in donations:
        conn.execute(
            """INSERT INTO donations (opportunity_id, recipient_public_id, event_id,
               event_name, amount, date, is_recurring, pending, anonymous_to_public,
               recognition_name, donor_name, donor_public_id, donor_profile_image_url,
               last_scraped)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            d,
        )

    conn.execute(
        """INSERT INTO rides (id, name, type, is_signature_ride, status,
           registration_start, registration_end, ride_weekend_start, ride_weekend_end, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("ride_sig", "Signature Ride 2026", "signature", True, "active",
         "2026-01-01", "2026-07-01", "2026-08-01", "2026-08-02", "2026-04-01"),
    )
    conn.execute(
        """INSERT INTO rides (id, name, type, is_signature_ride, status,
           registration_start, registration_end, ride_weekend_start, ride_weekend_end, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("ride_grv", "Gravel Day 2026", "gravel", False, "active",
         "2026-01-01", "2026-07-01", "2026-09-01", "2026-09-01", "2026-04-01"),
    )

    conn.execute(
        """INSERT INTO routes (id, ride_id, name, distance, duration, fundraising_commitment,
           capacity, highest_incline, start_date, image_url, starting_city, ending_city, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("route_100", "ride_sig", "100 Mile Signature", 100.0, "8h", 2000.0,
         500.0, 3.5, "2026-08-01", None, "Columbus", "Gambier", "2026-04-01"),
    )
    conn.execute(
        """INSERT INTO routes (id, ride_id, name, distance, duration, fundraising_commitment,
           capacity, highest_incline, start_date, image_url, starting_city, ending_city, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("route_grv50", "ride_grv", "50 Mile Gravel", 50.0, "5h", 1000.0,
         200.0, 2.0, "2026-09-01", None, "Columbus", "Sunbury", "2026-04-01"),
    )

    conn.execute(
        """INSERT INTO member_routes (member_public_id, route_id, route_name, ride_type,
           distance, fundraising_commitment, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        ("m001", "route_100", "100 Mile Signature", "signature", 100.0, 2000.0, "2026-04-01"),
    )

    conn.execute(
        """INSERT INTO daily_snapshots (snapshot_date, team_id, raised, goal, all_time_raised,
           members_count, donations_count, total_donated, signature_riders, gravel_riders,
           riders_count, challengers_count, volunteers_count)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("2026-03-30", PARENT_TEAM_ID, 12000.0, 50000.0, 115000.0, 4, 8, 2300.0, 2, 1, 3, 1, 0),
    )
    conn.execute(
        """INSERT INTO daily_snapshots (snapshot_date, team_id, raised, goal, all_time_raised,
           members_count, donations_count, total_donated, signature_riders, gravel_riders,
           riders_count, challengers_count, volunteers_count)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("2026-04-01", PARENT_TEAM_ID, 15000.0, 50000.0, 120000.0, 5, 10, 2650.0, 2, 1, 3, 1, 1),
    )

    conn.execute(
        """INSERT INTO kids_snapshots (snapshot_date, campaign_id, fundraiser_count,
           estimated_amount_raised, monetary_goal, team_count, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        ("2026-04-01", "dbpr4x7j9x", 150, 45000.0, 100000.0, 12, "2026-04-01T10:00:00"),
    )

    conn.execute(
        """INSERT INTO org_snapshots (snapshot_date, team_id, name, members_count,
           sub_team_count, raised, goal, all_time_raised, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("2026-04-01", "org001", "Org One", 200, 10, 80000.0, 100000.0, 500000.0, "2026-04-01T10:00:00"),
    )
    conn.execute(
        """INSERT INTO org_snapshots (snapshot_date, team_id, name, members_count,
           sub_team_count, raised, goal, all_time_raised, last_scraped)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        ("2026-04-01", "org002", "Org Two", 150, 8, 60000.0, 80000.0, 400000.0, "2026-04-01T10:00:00"),
    )

    conn.commit()


@pytest.fixture
def test_db():
    """Create a test Postgres database with full schema and seed data."""
    conn = psycopg.connect(TEST_DSN, row_factory=dict_row)
    _drop_all_tables(conn)
    _create_schema(conn)
    _seed_data(conn)
    yield conn
    _drop_all_tables(conn)
    conn.close()


@pytest.fixture
def client(test_db, monkeypatch):
    """Flask test client with db module patched to use the test database."""
    import app.db as db_module
    import app.dashboard as dashboard_module

    test_pool = ConnectionPool(
        TEST_DSN,
        min_size=1,
        max_size=2,
        kwargs={"row_factory": dict_row},
    )
    monkeypatch.setattr(db_module, "_pool", test_pool)
    monkeypatch.setattr(db_module, "get_pool", lambda: test_pool)

    dashboard_module._cache.clear()
    dashboard_module.app.config["TESTING"] = True
    with dashboard_module.app.test_client() as c:
        yield c

    test_pool.close()
