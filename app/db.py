"""Central database connection module for AlloyDB (Postgres).

Replaces scattered sqlite3.connect() calls with a pooled psycopg connection.
"""

import os

from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DSN = os.environ.get(
    "ALLOYDB_DSN",
    os.environ.get("PELOTONIA_DB_DSN", "postgresql://localhost:5432/pelotonia"),
)

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DSN,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
        )
    return _pool


def get_conn():
    """Return a connection from the pool (use as context manager)."""
    return get_pool().connection()


def get_cursor():
    """Convenience: return a cursor from a pooled connection (use as context manager)."""
    return get_pool().connection().cursor()


def init_schema():
    """Run schema.sql against the database (idempotent)."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema_sql = f.read()
    with get_conn() as conn:
        conn.execute(schema_sql)
        conn.commit()
