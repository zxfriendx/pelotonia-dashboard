"""Tests for correct_team_funds_double_count() in the main scraper.

From 2026-10-22 Pelotonia's sub-team total became SUM(rider attributed) +
general funds, counting captain-assigned team funds twice. The scraper
subtracts the assigned amount only while the reported total contains it.
"""

import pytest

from app import pelotonia_scraper as scraper

PARENT = scraper.PARENT_TEAM_ID


@pytest.fixture
def conn(tmp_path):
    c = scraper.init_db(str(tmp_path / "t.db"))
    yield c
    c.close()


def _seed(conn, sub_reported, sub_all_time=1_000_000.0):
    """One parent, one sub-team with $20,000 general funds, two riders.

    Riders' own raised: 5,000 + 3,000 = 8,000.
    Assigned team funds: rider A attributed 6,000 (+1,000), rider B 5,000 (+2,000) = 3,000.
    Clean total = 8,000 + 20,000 = 28,000. Double-counted total = 31,000.
    """
    conn.execute("""INSERT INTO teams (id, name, raised, raised_reported, all_time_raised,
                    all_time_raised_reported, general_peloton_funds)
                    VALUES (?, 'Parent', ?, ?, ?, ?, 500)""",
                 (PARENT, sub_reported + 500, sub_reported + 500, sub_all_time + 500, sub_all_time + 500))
    conn.execute("""INSERT INTO teams (id, name, parent_id, raised, raised_reported, all_time_raised,
                    all_time_raised_reported, general_peloton_funds)
                    VALUES ('sub1', 'Sub One', ?, ?, ?, ?, ?, 20000)""",
                 (PARENT, sub_reported, sub_reported, sub_all_time, sub_all_time))
    for pid, raised, attributed in (("a", 5000, 6000), ("b", 3000, 5000)):
        conn.execute("INSERT INTO members (public_id, name, team_id, raised, attributed) VALUES (?,?,?,?,?)",
                     (pid, pid, "sub1", raised, attributed))


def _team(conn, tid):
    return conn.execute(
        "SELECT raised, all_time_raised, double_count_correction FROM teams WHERE id=?", (tid,)
    ).fetchone()


def test_subtracts_assigned_funds_when_double_counted(conn):
    """Current-year raised is corrected; all-time stays as reported (not inflated)."""
    _seed(conn, sub_reported=31_000)
    assert scraper.correct_team_funds_double_count(conn) == 3000
    assert _team(conn, "sub1") == (28_000, 1_000_000, 3000)
    assert _team(conn, PARENT) == (28_500, 1_000_500, 3000)


def test_leaves_clean_totals_alone(conn):
    """If Pelotonia fixes its totals, nothing is subtracted."""
    _seed(conn, sub_reported=28_000)
    assert scraper.correct_team_funds_double_count(conn) == 0
    assert _team(conn, "sub1") == (28_000, 1_000_000, 0)
    assert _team(conn, PARENT)[2] == 0


def test_parent_lagging_its_sub_teams_is_not_corrected(conn):
    """Sub-team inflated, but the parent's own figure hasn't caught up yet."""
    _seed(conn, sub_reported=31_000)
    conn.execute("UPDATE teams SET raised_reported = 28500 WHERE id = ?", (PARENT,))
    assert scraper.correct_team_funds_double_count(conn) == 3000
    assert _team(conn, "sub1")[0] == 28_000
    assert _team(conn, PARENT)[0] == 28_500
    assert _team(conn, PARENT)[2] == 0


def test_is_idempotent(conn):
    _seed(conn, sub_reported=31_000)
    scraper.correct_team_funds_double_count(conn)
    scraper.correct_team_funds_double_count(conn)
    assert _team(conn, "sub1") == (28_000, 1_000_000, 3000)
