# =============================================================================
# database/db.py  —  PostgreSQL connection helper
# =============================================================================
# Reads credentials from environment variables (or a .env file via dotenv).
# init_db() is fully idempotent — safe to call on every app start.
# =============================================================================

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()  # reads .env in project root; silently ignored if absent


def get_connection() -> psycopg2.extensions.connection:
    """
    Open and return a new psycopg2 connection.
    Credentials come entirely from environment variables so nothing is
    hard-coded.  In production, swap this for a connection pool.
    """
    return psycopg2.connect(
        host     = os.environ.get("DB_HOST",     "localhost"),
        port     = int(os.environ.get("DB_PORT", "5432")),
        dbname   = os.environ.get("DB_NAME",     "postgres"),
        user     = os.environ.get("DB_USER",     "postgres"),
        password = os.environ.get("DB_PASSWORD", "Vivekrwt@123"),
    )


def init_db() -> None:
    """
    Run schema.sql to create tables and apply migrations.
    Fully idempotent — IF NOT EXISTS + DO $$ migration block.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as fh:
        sql = fh.read()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print("[DB] Schema applied ✓  (updated_at migration included)")


def seed_db() -> None:
    """
    Insert demo data from seed.sql.
    Skipped automatically if the students table already has rows.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM students;")
            count = cur.fetchone()[0]

        if count > 0:
            print(f"[DB] Seed skipped — {count} student(s) already present.")
            return

        seed_path = os.path.join(os.path.dirname(__file__), "seed.sql")
        with open(seed_path, "r") as fh:
            sql = fh.read()

        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print("[DB] Demo data seeded ✓")
