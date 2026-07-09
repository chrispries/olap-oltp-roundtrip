# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Create Lakebase + synced tables
# MAGIC
# MAGIC Mirror your Unity Catalog data (from `01`) into a **Lakebase Postgres** database and
# MAGIC register it in Unity Catalog, so the app can serve it and you can query it back in SQL.
# MAGIC You run this **in your workspace** — no laptop CLI needed. Cells are safe to re-run.
# MAGIC
# MAGIC ```
# MAGIC (01) UC Delta ──▶ 👉 (02) Lakebase synced tables ──▶ (03) app ──▶ (04) round-trip
# MAGIC ```
# MAGIC
# MAGIC > Prefer the UI, or want the laptop-CLI version? See the last cell.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 0 · Install the SDK + Postgres driver
# MAGIC The workspace's default `databricks-sdk` predates the Lakebase (`postgres`) API, so we
# MAGIC upgrade it and add `psycopg` (to create the database). This restarts Python.

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.50" "psycopg[binary]>=3.1" -q
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1 · Your names
# MAGIC Everyone shares one Lakebase **project**; you get your own **database** `ws_<username>`
# MAGIC and UC catalog `lakebase_ws_<username>`.

# COMMAND ----------
import re
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())

PROJECT = "lakebase-workshop"
BRANCH = f"projects/{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
UC_CATALOG = "lakebase_workshop"       # regular UC catalog holding the Delta data (from 01)
SCHEMA = f"ws_{slug}"                   # your UC schema (from 01)
PGDB = f"ws_{slug}"                     # your Lakebase Postgres database
LBCAT = f"lakebase_ws_{slug}"          # your Lakebase → UC catalog

host = w.postgres.list_endpoints(BRANCH).__next__().as_dict()["status"]["hosts"]["host"]
print(f"user={user}\nPGDB={PGDB}  LBCAT={LBCAT}\nhost={host}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2 · Create your Postgres database
# MAGIC A short-lived OAuth token (minted by the SDK) is the Postgres password. `CREATE DATABASE`
# MAGIC can't run in a transaction, so we use autocommit. Re-running is safe (we skip if it exists).

# COMMAND ----------
import psycopg

def pg_token():
    return w.postgres.generate_database_credential(ENDPOINT).token

with psycopg.connect(host=host, port=5432, dbname="postgres", user=user,
                     password=pg_token(), sslmode="require", autocommit=True) as c:
    exists = c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (PGDB,)).fetchone()
    if exists:
        print(f"database {PGDB} already exists — skipping")
    else:
        c.execute(f'CREATE DATABASE "{PGDB}"')
        print(f"✅ created database {PGDB}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3 · Register your database as a Unity Catalog catalog
# MAGIC This is what makes the round-trip work: UC federates your **whole** Postgres database,
# MAGIC so anything in it (including tables the app creates later) is queryable from SQL.

# COMMAND ----------
from databricks.sdk.service.postgres import Catalog

try:
    w.postgres.create_catalog(
        Catalog.from_dict({"spec": {"postgres_database": PGDB, "branch": BRANCH}}),
        catalog_id=LBCAT,
    )
    print(f"✅ registered UC catalog {LBCAT}")
except Exception as e:
    print(f"create_catalog: {type(e).__name__} (likely already exists) — {str(e)[:160]}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4 · Create the snapshot synced tables
# MAGIC One **SNAPSHOT** synced table per Delta table. Each spins up a short DLT pipeline. The
# MAGIC synced-table id is `<catalog>.public.<table>`; `public` is the Postgres schema.

# COMMAND ----------
from databricks.sdk.service.postgres import SyncedTable

# metadata schema for the sync pipelines (one-time)
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.pipeline_storage")

PKS = {"machines": "machine_id", "sensor_readings": "reading_id",
       "production_orders": "order_id", "maintenance_tickets": "ticket_id"}

for tbl, pk in PKS.items():
    spec = {"spec": {
        "source_table_full_name": f"{UC_CATALOG}.{SCHEMA}.{tbl}",
        "primary_key_columns": [pk],
        "scheduling_policy": "SNAPSHOT",
        "branch": BRANCH,
        "postgres_database": PGDB,
        "create_database_objects_if_missing": True,
        "new_pipeline_spec": {"storage_catalog": UC_CATALOG, "storage_schema": "pipeline_storage"},
    }}
    try:
        w.postgres.create_synced_table(SyncedTable.from_dict(spec),
                                       synced_table_id=f"{LBCAT}.public.{tbl}")
        print(f"✅ queued synced table {tbl}")
    except Exception as e:
        print(f"{tbl}: {type(e).__name__} (likely already exists) — {str(e)[:120]}")

print("\nSnapshots take ~2–4 min to finish. Run the next cell until counts appear.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5 · Verify (via Unity Catalog — the analytics path)
# MAGIC Reading the Lakebase catalog from SQL proves both the sync landed **and** the round-trip
# MAGIC federation works. (If you get 0 rows or an error, the snapshot is still running — wait a
# MAGIC minute and re-run.)

# COMMAND ----------
for tbl in PKS:
    try:
        n = spark.table(f"{LBCAT}.public.{tbl}").count()
        print(f"OK  {LBCAT}.public.{tbl}: {n}")
    except Exception as e:
        print(f"…  {tbl} not ready yet — {str(e)[:80]}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Prefer the UI? Or the laptop CLI?
# MAGIC
# MAGIC **UI:** *Compute → Database instances → `lakebase-workshop`* to create a database; then in
# MAGIC *Catalog Explorer* use **Create → Synced table** on each `lakebase_workshop.ws_<you>.<table>`,
# MAGIC targeting your database with **Snapshot** mode; and register the catalog from the database
# MAGIC instance page. Same result, click-driven.
# MAGIC
# MAGIC **Laptop CLI:** the exact `databricks postgres …` commands are in
# MAGIC `sync/02_create_lakebase.md`.
# MAGIC
# MAGIC ➡️ **Next: `03_deploy_app`.**
