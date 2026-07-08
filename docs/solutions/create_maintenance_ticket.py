"""Facilitator answer key for the workshop gap in app/db.py.

Drop this body into create_maintenance_ticket() in app/db.py and redeploy.
"""
import psycopg

from app.db import APP_TABLE  # noqa: F401  (illustrative import; APP_TABLE lives in app/db.py)


def create_maintenance_ticket(conn: psycopg.Connection, machine_id: int,
                              priority: str, description: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {APP_TABLE} (machine_id, priority, description) "
            f"VALUES (%s, %s, %s) RETURNING ticket_id",
            (machine_id, priority, description),
        )
        ticket_id = cur.fetchone()[0]
    conn.commit()
    return ticket_id
