"""Lakebase Postgres access for the shop-floor Maintenance Cockpit.

Reads (machines, open alerts) come from the read-only *synced tables* — replicas of the
lakehouse. Because those are read-only, the technician's work is written to an app-owned
table, `maintenance_actions` (claim + resolution). An alert leaves the queue once it has a
resolution. And because the Lakebase database is registered in Unity Catalog, every
resolution is queryable from Databricks SQL — closing the round-trip.
"""
import os

import psycopg
from psycopg.rows import dict_row
from databricks.sdk import WorkspaceClient

ACTIONS_TABLE = "maintenance_actions"

# Fully-qualified Autoscaling endpoint, e.g.
# "projects/<project>/branches/<branch>/endpoints/<endpoint>". Set in app.yaml.
ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME")

_ws_client: WorkspaceClient | None = None


def _workspace_client() -> WorkspaceClient:
    global _ws_client
    if _ws_client is None:
        _ws_client = WorkspaceClient()
    return _ws_client


def _fresh_token() -> str:
    """Mint a short-lived Lakebase OAuth credential for ENDPOINT_NAME via the SDK."""
    return _workspace_client().postgres.generate_database_credential(ENDPOINT_NAME).token


def get_connection() -> psycopg.Connection:
    """Connect to Lakebase (Autoscaling) Postgres with a fresh per-connection OAuth token."""
    return psycopg.connect(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["PGDATABASE"],
        user=os.environ.get("PGUSER") or os.environ["DATABRICKS_CLIENT_ID"],
        password=_fresh_token(),
        sslmode=os.environ.get("PGSSLMODE", "require"),
    )


def ensure_app_table(conn: psycopg.Connection) -> None:
    """Create the app-owned actions table (one action per alert ticket)."""
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {ACTIONS_TABLE} (
                action_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                ticket_id   bigint NOT NULL UNIQUE,
                machine_id  bigint NOT NULL,
                technician  text   NOT NULL,
                status      text   NOT NULL DEFAULT 'in_progress',  -- in_progress | resolved
                resolution  text,
                claimed_at  timestamptz NOT NULL DEFAULT now(),
                resolved_at timestamptz
            )""")
        conn.commit()


def open_alerts(conn: psycopg.Connection) -> list[dict]:
    """Open maintenance alerts not yet resolved, worst priority first.

    Alerts come from the seeded, read-only `maintenance_tickets` synced table, joined to
    `machines` for context and to `maintenance_actions` to show who (if anyone) has claimed it.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            SELECT t.ticket_id, t.machine_id, m.model, m.line, t.priority, t.description,
                   a.technician AS claimed_by, a.status AS action_status
            FROM maintenance_tickets t
            JOIN machines m ON m.machine_id = t.machine_id
            LEFT JOIN {ACTIONS_TABLE} a ON a.ticket_id = t.ticket_id
            WHERE t.status = 'open' AND (a.status IS NULL OR a.status <> 'resolved')
            ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                     t.opened_at""")
        return cur.fetchall()


def claim_alert(conn: psycopg.Connection, ticket_id: int, machine_id: int, technician: str) -> None:
    """Sign yourself onto an alert (marks it in progress under your name)."""
    with conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {ACTIONS_TABLE} (ticket_id, machine_id, technician, status)
                VALUES (%s, %s, %s, 'in_progress')
                ON CONFLICT (ticket_id)
                DO UPDATE SET technician = EXCLUDED.technician, status = 'in_progress',
                              claimed_at = now()""",
            (ticket_id, machine_id, technician),
        )
    conn.commit()


def resolve_alert(conn: psycopg.Connection, ticket_id: int, machine_id: int,
                  technician: str, resolution: str) -> None:
    """WORKSHOP GAP — you implement this.

    Close out an alert: write (or update) its row in ACTIONS_TABLE with status 'resolved',
    the `resolution` note, the `technician`, and resolved_at = now(). Because ticket_id is
    UNIQUE, use `INSERT ... ON CONFLICT (ticket_id) DO UPDATE`. Remember to commit.
    The completed version is in docs/solutions/resolve_alert.py.
    """
    raise NotImplementedError("TODO (workshop): implement resolve_alert")


def recent_resolutions(conn: psycopg.Connection, limit: int = 15) -> list[dict]:
    """Resolved alerts — the round-trip made visible in-app (also queryable in Databricks SQL)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            SELECT a.machine_id, m.model, a.technician, a.resolution,
                   a.resolved_at,
                   round(extract(epoch FROM (a.resolved_at - t.opened_at)) / 3600, 1) AS hours_to_fix
            FROM {ACTIONS_TABLE} a
            JOIN machines m ON m.machine_id = a.machine_id
            LEFT JOIN maintenance_tickets t ON t.ticket_id = a.ticket_id
            WHERE a.status = 'resolved'
            ORDER BY a.resolved_at DESC
            LIMIT %s""", (limit,))
        return cur.fetchall()
