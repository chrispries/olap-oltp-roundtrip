"""Facilitator answer key for the workshop gap in app/db.py (`resolve_alert`).

Drop this body into resolve_alert() in app/db.py and redeploy.
"""
import psycopg

from app.db import ACTIONS_TABLE  # noqa: F401  (illustrative; ACTIONS_TABLE lives in app/db.py)


def resolve_alert(conn: psycopg.Connection, ticket_id: int, machine_id: int,
                  technician: str, resolution: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {ACTIONS_TABLE}
                    (ticket_id, machine_id, technician, status, resolution, resolved_at)
                VALUES (%s, %s, %s, 'resolved', %s, now())
                ON CONFLICT (ticket_id)
                DO UPDATE SET status = 'resolved',
                              technician = EXCLUDED.technician,
                              resolution = EXCLUDED.resolution,
                              resolved_at = now()""",
            (ticket_id, machine_id, technician, resolution),
        )
    conn.commit()
