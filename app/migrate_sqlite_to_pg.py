#!/usr/bin/env python3
"""
One-shot migration: SQLite → AlloyDB (Postgres).

Reads the current pelotonia_data.db, creates the Postgres schema, and bulk-inserts
all rows. Run once from a workstation with the AlloyDB Auth Proxy running.

Usage:
  ALLOYDB_DSN="postgresql://user:pass@localhost:5432/pelotonia" \
    python app/migrate_sqlite_to_pg.py [--sqlite app/pelotonia_data.db]
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE = SCRIPT_DIR / "pelotonia_data.db"

TABLES = [
    "teams",
    "members",
    "donations",
    "donor_identities",
    "rides",
    "routes",
    "daily_snapshots",
    "member_routes",
    "events",
    "kids_snapshots",
    "org_snapshots",
]

BOOLEAN_COLS = {
    "teams": {"accepting_members", "goal_achieved"},
    "members": {
        "is_captain", "is_admin", "is_cancer_survivor",
        "is_donor_list_visible", "is_rider", "is_volunteer",
        "is_challenger", "committed_high_roller",
    },
    "donations": {"is_recurring", "pending", "anonymous_to_public"},
    "rides": {"is_signature_ride"},
}


def migrate(sqlite_path, pg_dsn):
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg.connect(pg_dsn, row_factory=dict_row)

    schema_path = SCRIPT_DIR / "schema.sql"
    print(f"Applying schema from {schema_path}...")
    with open(schema_path) as f:
        pg_conn.execute(f.read())
    pg_conn.commit()

    for table in TABLES:
        print(f"\nMigrating {table}...")
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  (empty, skipping)")
            continue

        cols = rows[0].keys()
        bool_cols = BOOLEAN_COLS.get(table, set())

        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(cols)
        insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        batch = []
        for row in rows:
            values = []
            for col in cols:
                val = row[col]
                if col in bool_cols and val is not None:
                    val = bool(val)
                values.append(val)
            batch.append(tuple(values))

        with pg_conn.cursor() as cur:
            cur.executemany(insert_sql, batch)
        pg_conn.commit()

        pg_count = pg_conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()["cnt"]
        print(f"  SQLite: {len(rows)} rows → Postgres: {pg_count} rows")
        if pg_count != len(rows):
            print(f"  WARNING: row count mismatch (conflicts skipped)")

    sqlite_conn.close()
    pg_conn.close()
    print("\nMigration complete.")


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to AlloyDB (Postgres)")
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE), help="Path to SQLite DB")
    parser.add_argument("--dsn", default=os.environ.get("ALLOYDB_DSN", ""),
                        help="Postgres DSN (or set ALLOYDB_DSN env var)")
    args = parser.parse_args()

    if not args.dsn:
        print("ERROR: No Postgres DSN provided. Set ALLOYDB_DSN or use --dsn.")
        sys.exit(1)

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        print(f"ERROR: SQLite database not found: {sqlite_path}")
        sys.exit(1)

    print(f"Source: {sqlite_path}")
    print(f"Target: {args.dsn.split('@')[0]}@...")
    migrate(sqlite_path, args.dsn)


if __name__ == "__main__":
    main()
