"""Lakebase Postgres access for the shop-floor maintenance app.

Reads come from the read-only *synced tables* (machines, maintenance_tickets, ...).
Writes go to the app-owned table `app_maintenance_tickets`, because synced tables are
read-only. Because the Lakebase instance is registered in Unity Catalog, those writes are
then queryable from Databricks SQL — closing the round-trip.
"""
import os

import psycopg
from psycopg.rows import dict_row

APP_TABLE = "app_maintenance_tickets"


def get_connection() -> psycopg.Connection:
    """Connect to Lakebase Postgres.

    On Databricks Apps the bound Lakebase resource injects PGHOST/PGPORT/PGDATABASE/PGUSER
    and a short-lived PGPASSWORD (OAuth token). See sync/create_lakebase.md for the binding.
    """
    return psycopg.connect(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        sslmode="require",
    )


def ensure_app_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {APP_TABLE} (
                ticket_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                machine_id  bigint NOT NULL,
                opened_at   timestamptz NOT NULL DEFAULT now(),
                priority    text NOT NULL,
                status      text NOT NULL DEFAULT 'open',
                description text NOT NULL
            )""")
        conn.commit()


def list_machines(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT machine_id, model, line, location FROM machines ORDER BY machine_id")
        return cur.fetchall()


def open_tickets(conn: psycopg.Connection) -> list[dict]:
    """Open tickets = seeded (read-only synced) tickets UNION app-written tickets."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            SELECT machine_id, priority, description, opened_at
            FROM maintenance_tickets WHERE status = 'open'
            UNION ALL
            SELECT machine_id, priority, description, opened_at
            FROM {APP_TABLE} WHERE status = 'open'
            ORDER BY opened_at DESC""")
        return cur.fetchall()


def create_maintenance_ticket(conn: psycopg.Connection, machine_id: int,
                              priority: str, description: str) -> int:
    """WORKSHOP GAP — you implement this.

    Insert one row into APP_TABLE (machine_id, priority, description) and return the
    generated ticket_id. Tip: use `INSERT ... RETURNING ticket_id` and remember to commit.
    The completed version is in docs/solutions/create_maintenance_ticket.py.
    """
    raise NotImplementedError("TODO (workshop): implement create_maintenance_ticket")
