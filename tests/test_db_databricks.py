# Databricks notebook source
# MAGIC %md
# MAGIC # Write-back integration test
# MAGIC Validates `log_maintenance_action()` against the **real** Lakebase Postgres (there's no
# MAGIC local test runner — public PyPI is firewalled). Run on serverless with the repo synced as
# MAGIC a Workspace Git folder, after Lab 2 has created your project + operational tables.

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.118.0" "psycopg[binary]>=3.1" -q
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# Point db.py at your Lakebase database. The connection mints its own OAuth token via the SDK,
# so no password is needed here — just host / database / user / endpoint. We connect as the human
# user (the table owner), so no service-principal grants are required for the test.
import os, re
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "", user.split("@")[0].lower())

# Find your healthy Lakebase project from Lab 2 (lakebase-ws-<slug>-N)
PROJECT = None
for i in range(1, 11):
    candidate = f"lakebase-ws-{slug}-{i}"
    try:
        w.postgres.get_project(name=f"projects/{candidate}")
        list(w.postgres.list_branches(parent=f"projects/{candidate}"))
        PROJECT = candidate
        break
    except Exception:
        continue
assert PROJECT, "No healthy Lakebase project found — run Lab 2 first."
branch = f"projects/{PROJECT}/branches/production"

os.environ["ENDPOINT_NAME"] = f"{branch}/endpoints/primary"
os.environ["PGHOST"] = next(
    ep for ep in w.postgres.list_endpoints(parent=branch)
    if ep.name == f"{branch}/endpoints/primary").status.hosts.host
os.environ["PGDATABASE"] = "databricks_postgres"
os.environ["PGUSER"] = user

import sys
sys.path.append("../bundle/src")  # so `from app import db` resolves in the Git folder
from app import db

# COMMAND ----------
conn = db.get_connection()
TAG = "integration-test"

try:
    db.log_maintenance_action(conn, machine_id=7, ticket_id=None, action_type="inspection",
                              description="unit-test fix", performed_by=TAG, status="completed")
except NotImplementedError:
    print("⏭️  log_maintenance_action() is still the stub — implement it (Lab 3, Step 4) then re-run.")
    dbutils.notebook.exit("SKIPPED: write-back not implemented yet")

with conn.cursor(row_factory=db.dict_row) as cur:
    cur.execute("SELECT performed_by, status, description FROM maintenance_actions "
                "WHERE performed_by = %s ORDER BY action_id DESC LIMIT 1", (TAG,))
    row = cur.fetchone()
assert row and row["status"] == "completed" and row["description"] == "unit-test fix", f"unexpected: {row}"
print(f"✅ log_maintenance_action persisted: {row}")

# COMMAND ----------
# cleanup the synthetic row(s)
with conn.cursor() as cur:
    cur.execute("DELETE FROM maintenance_actions WHERE performed_by = %s", (TAG,))
conn.commit()
print("✅ write-back integration test passed")
