# Databricks notebook source
# MAGIC %md
# MAGIC # Write-back integration test
# MAGIC Validates `create_maintenance_ticket()` against the **real** Lakebase Postgres
# MAGIC (replaces the local ephemeral-Postgres unit test — see plan Revision 2026-07-08).
# MAGIC Run on serverless with the repo synced as workspace files.

# COMMAND ----------
# MAGIC %pip install "psycopg[binary]>=3.1"
# MAGIC %restart_python

# COMMAND ----------
# Provide the Lakebase connection the same way the deployed app does. Fill these from
# sync/02_create_lakebase.md (host, per-user database, and an OAuth/instance credential).
import os

os.environ.setdefault("PGHOST", "<lakebase-host>")
os.environ.setdefault("PGPORT", "5432")
os.environ.setdefault("PGDATABASE", "<ws_user_db>")
os.environ.setdefault("PGUSER", "<pg-user>")
os.environ.setdefault("PGPASSWORD", "<oauth-token>")

import sys
sys.path.append("..")  # so `from app import db` resolves when repo is synced
from app import db

# COMMAND ----------
conn = db.get_connection()
db.ensure_app_table(conn)

tid = db.create_maintenance_ticket(conn, machine_id=7, priority="high", description="vibration alarm")
assert isinstance(tid, int) and tid > 0, f"expected positive int, got {tid!r}"

with conn.cursor(row_factory=db.dict_row if hasattr(db, "dict_row") else None) as cur:
    cur.execute(f"SELECT machine_id, priority, status FROM {db.APP_TABLE} WHERE ticket_id = %s", (tid,))
    row = cur.fetchone()
assert row is not None, "row not found after insert"
print(f"✅ created ticket {tid}: {row}")

# COMMAND ----------
# Two inserts get distinct ids.
a = db.create_maintenance_ticket(conn, 1, "low", "coolant low")
b = db.create_maintenance_ticket(conn, 1, "low", "coolant low")
assert a != b, "ticket ids should be distinct"
print(f"✅ distinct ids: {a} != {b}")
print("\n✅ write-back integration test passed")
