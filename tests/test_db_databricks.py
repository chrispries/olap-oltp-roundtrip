# Databricks notebook source
# MAGIC %md
# MAGIC # Write-back integration test
# MAGIC Validates `resolve_alert()` against the **real** Lakebase Postgres (there's no local
# MAGIC test runner — public PyPI is firewalled). Run on serverless with the repo synced as a
# MAGIC Workspace Git folder.

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.50" "psycopg[binary]>=3.1" -q
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# Point db.py at your Lakebase database. The connection mints its own OAuth token via the SDK,
# so no password is needed here — just host / database / user / endpoint.
import os, re
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())
branch = "projects/lakebase-workshop/branches/production"

os.environ["ENDPOINT_NAME"] = f"{branch}/endpoints/primary"
os.environ["PGHOST"] = w.postgres.list_endpoints(branch).__next__().as_dict()["status"]["hosts"]["host"]
os.environ["PGDATABASE"] = f"ws_{slug}"
os.environ["PGUSER"] = user

import sys
sys.path.append("..")  # so `from app import db` resolves in a Git folder
from app import db

# COMMAND ----------
conn = db.get_connection()
db.ensure_app_table(conn)

TEST_TICKET = 999001  # synthetic id — won't collide with the seeded alerts
db.resolve_alert(conn, ticket_id=TEST_TICKET, machine_id=7,
                 technician="integration-test", resolution="unit-test fix")

with conn.cursor(row_factory=db.dict_row) as cur:
    cur.execute(f"SELECT technician, status, resolution FROM {db.ACTIONS_TABLE} WHERE ticket_id = %s",
                (TEST_TICKET,))
    row = cur.fetchone()
assert row and row["status"] == "resolved" and row["resolution"] == "unit-test fix", f"unexpected: {row}"
print(f"✅ resolve_alert persisted: {row}")

# COMMAND ----------
# cleanup the synthetic row
with conn.cursor() as cur:
    cur.execute(f"DELETE FROM {db.ACTIONS_TABLE} WHERE ticket_id = %s", (TEST_TICKET,))
conn.commit()
print("✅ write-back integration test passed")
