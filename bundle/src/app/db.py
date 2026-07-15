"""Lakebase Postgres access for the shop-floor Maintenance Cockpit.

The app talks to a single Lakebase database (`databricks_postgres`) that holds two kinds of
tables, both in the `public` schema:

* **Synced reference tables** (read-only) — `machines`, `sensor_readings`, `production_orders`,
  `maintenance_tickets`. These are SNAPSHOT replicas of the lakehouse (Lab 2, UC → Lakebase).
* **Operational tables** (read + write) — `maintenance_actions`, `work_orders`, `quality_checks`,
  `operator_notes`. The app writes to these; Change Data Feed streams every write back to Unity
  Catalog as `lb_*_history` Delta tables (Lab 2, Lakebase → UC). That is the round-trip.

Auth: Lakebase Autoscaling issues short-lived (~1h) OAuth tokens, not a static password, so
`get_connection()` mints a fresh token per connection via the SDK.
"""
import os

import psycopg
from psycopg.rows import dict_row
from databricks.sdk import WorkspaceClient

# Fully-qualified Autoscaling endpoint, e.g.
# "projects/<project>/branches/<branch>/endpoints/<endpoint>". Set in app.yaml at deploy time.
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


# --- Reference data (read-only synced tables) --------------------------------

def machines(conn: psycopg.Connection) -> list[dict]:
    """All machines, for context and dropdowns."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT machine_id, model, line, location FROM machines ORDER BY machine_id")
        return cur.fetchall()


def open_alerts(conn: psycopg.Connection) -> list[dict]:
    """Open maintenance alerts (seeded tickets), worst priority first.

    Reads the read-only `maintenance_tickets` synced table, joins `machines` for context, and
    left-joins the app's own `maintenance_actions` so we can show whether anyone has logged work
    against the ticket yet.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT t.ticket_id, t.machine_id, m.model, m.line, t.priority, t.description,
                   a.performed_by AS actioned_by, a.status AS action_status
            FROM maintenance_tickets t
            JOIN machines m ON m.machine_id = t.machine_id
            LEFT JOIN LATERAL (
                SELECT performed_by, status
                FROM maintenance_actions
                WHERE ticket_id = t.ticket_id
                ORDER BY performed_at DESC
                LIMIT 1
            ) a ON true
            WHERE t.status = 'open'
            ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                     t.opened_at""")
        return cur.fetchall()


# --- Maintenance actions (operational, read + write) -------------------------

def recent_actions(conn: psycopg.Connection, limit: int = 15) -> list[dict]:
    """Latest maintenance actions — the round-trip made visible in-app.

    Every row here also lands in Unity Catalog as `lb_maintenance_actions_history` via CDF.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT a.action_id, a.machine_id, m.model, a.action_type, a.description,
                   a.performed_by, a.status, a.performed_at, a.completed_at
            FROM maintenance_actions a
            JOIN machines m ON m.machine_id = a.machine_id
            ORDER BY a.performed_at DESC
            LIMIT %s""", (limit,))
        return cur.fetchall()


def log_maintenance_action(conn: psycopg.Connection, machine_id: int, ticket_id: int | None,
                           action_type: str, description: str, performed_by: str,
                           status: str) -> None:
    """TODO — implement this (Lab 3, Step 4 walks you through it).

    Insert a row into `maintenance_actions` recording the work: the machine, the ticket it
    relates to (may be None), the `action_type` ('preventive' | 'corrective' | 'inspection'),
    a free-text `description`, who did it (`performed_by`), and its `status` ('in_progress' |
    'completed' | 'cancelled'). If status is 'completed', also set `completed_at = now()`.
    Remember to commit. The completed version is shown in Lab 3, Step 4.
    """
    raise NotImplementedError("Not implemented yet — see Lab 3, Step 4.")


# --- Work orders (operational, read + write) ---------------------------------

def open_work_orders(conn: psycopg.Connection) -> list[dict]:
    """Work orders that aren't closed yet, most urgent first."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT wo.work_order_id, wo.machine_id, m.model, wo.priority, wo.title,
                   wo.description, wo.assigned_to, wo.due_date, wo.status, wo.created_at
            FROM work_orders wo
            JOIN machines m ON m.machine_id = wo.machine_id
            WHERE wo.status <> 'closed'
            ORDER BY CASE wo.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                                      WHEN 'medium' THEN 2 ELSE 3 END,
                     wo.created_at""")
        return cur.fetchall()


def create_work_order(conn: psycopg.Connection, machine_id: int, priority: str, title: str,
                      description: str, assigned_to: str | None, due_date, status: str) -> None:
    """Raise a new work order."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO work_orders
                   (machine_id, priority, title, description, assigned_to, due_date, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (machine_id, priority, title, description, assigned_to or None, due_date, status))
    conn.commit()


def set_work_order_status(conn: psycopg.Connection, work_order_id: int, status: str) -> None:
    """Move a work order along its lifecycle (assigned → in_progress → closed)."""
    with conn.cursor() as cur:
        cur.execute("UPDATE work_orders SET status = %s WHERE work_order_id = %s",
                    (status, work_order_id))
    conn.commit()


# --- Quality checks (operational, read + write) ------------------------------

def recent_quality_checks(conn: psycopg.Connection, limit: int = 15) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT q.check_id, q.order_id, q.machine_id, m.model, q.check_type, q.result,
                   q.defect_code, q.notes, q.inspector, q.checked_at
            FROM quality_checks q
            JOIN machines m ON m.machine_id = q.machine_id
            ORDER BY q.checked_at DESC
            LIMIT %s""", (limit,))
        return cur.fetchall()


def record_quality_check(conn: psycopg.Connection, order_id: int, machine_id: int,
                         check_type: str, result: str, defect_code: str | None,
                         notes: str, inspector: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO quality_checks
                   (order_id, machine_id, check_type, result, defect_code, notes, inspector)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (order_id, machine_id, check_type, result, defect_code or None, notes, inspector))
    conn.commit()


# --- Operator notes (operational, read + write) ------------------------------

def recent_notes(conn: psycopg.Connection, limit: int = 20) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT n.note_id, n.machine_id, m.model, n.note_type, n.content,
                   n.created_by, n.created_at
            FROM operator_notes n
            LEFT JOIN machines m ON m.machine_id = n.machine_id
            ORDER BY n.created_at DESC
            LIMIT %s""", (limit,))
        return cur.fetchall()


def add_operator_note(conn: psycopg.Connection, machine_id: int | None, note_type: str,
                      content: str, created_by: str, ticket_id: int | None = None,
                      order_id: int | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO operator_notes
                   (machine_id, ticket_id, order_id, note_type, content, created_by)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (machine_id, ticket_id, order_id, note_type, content, created_by))
    conn.commit()
