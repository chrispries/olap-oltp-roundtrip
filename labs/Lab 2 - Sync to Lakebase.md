# 🏭 Lab 2 – Sync to Lakebase

## 🎯 Learning Objectives
By the end of this lab, you will:
- Understand **Lakebase** — managed PostgreSQL (OLTP) sitting next to the lakehouse
- Create your own Postgres **database** on the shared Lakebase project
- **Register** it in Unity Catalog and create read-only **snapshot synced tables** from your Delta data
- Understand why registering it in UC is what makes the round-trip possible (federation, no copy)

## Introduction

Your analytical tables are great for scans and joins, but not for the millisecond single-row
reads and writes an app needs. **Lakebase** gives you a real Postgres database, serverless and
scale-to-zero, right next to your lakehouse.

| Piece | What it is |
|-------|------------|
| **Synced table** | A **read-only** replica of a Delta table, mirrored into Lakebase Postgres |
| **UC-registered catalog** | Registering the Lakebase database in Unity Catalog federates *every* table in it — so it's queryable from Databricks SQL with no copy |

> Read [`docs/concepts.md`](../docs/concepts.md) if you want the full mental model first.

## Instructions

Before you start, please verify:
- You completed **Lab 1** (your four Delta tables exist).
- The shared Lakebase project **`lakebase-workshop`** exists.

This lab is self-contained — run its cells in order in a serverless Python notebook; it
re-creates everything it needs, so you can run it without having run Lab 1 in the same session.

### Step 0 — Install the Lakebase SDK

The workspace's default `databricks-sdk` predates the Lakebase (`postgres`) API, so upgrade it
and add `psycopg` (to create the database). **Run this on its own — it restarts Python:**

```python
%pip install -U "databricks-sdk>=0.50" "psycopg[binary]>=3.1" -q
dbutils.library.restartPython()
```

> ⚠️ `restartPython()` wipes all variables and imports (including anything from a previous lab).
> That's expected — the next cell re-imports and re-derives everything, so **always run Step 1
> right after the restart.**

### Step 1 — Set up (run this right after the restart)

This re-imports the SDK and re-derives your identity and names — your **database**
`schema_<username>` and UC catalog `lakebase_schema_<username>`.

```python
import re
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())

PROJECT    = "lakebase-workshop"
BRANCH     = f"projects/{PROJECT}/branches/production"
ENDPOINT   = f"{BRANCH}/endpoints/primary"
UC_CATALOG = "catalog_workshop"      # the Delta data from Lab 1
SCHEMA     = f"schema_{slug}"             # your UC schema
PGDB       = f"schema_{slug}"             # your Lakebase Postgres database
LBCAT      = f"lakebase_schema_{slug}"    # your Lakebase → UC catalog

host = w.postgres.list_endpoints(BRANCH).__next__().as_dict()["status"]["hosts"]["host"]
print(f"PGDB={PGDB}  LBCAT={LBCAT}\nhost={host}")
```

### Step 2 — Create your Postgres database

A short-lived OAuth token (minted by the SDK) is the Postgres password. `CREATE DATABASE` can't
run in a transaction, so we use autocommit. Safe to re-run (skips if it exists).

```python
import psycopg

def pg_token():
    return w.postgres.generate_database_credential(ENDPOINT).token

with psycopg.connect(host=host, port=5432, dbname="postgres", user=user,
                     password=pg_token(), sslmode="require", autocommit=True) as c:
    if c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (PGDB,)).fetchone():
        print(f"database {PGDB} already exists — skipping")
    else:
        c.execute(f'CREATE DATABASE "{PGDB}"'); print(f"✅ created database {PGDB}")
```

### Step 3 — Register your database as a Unity Catalog catalog

This is what makes the round-trip work: UC federates your **whole** Postgres database, so
anything in it (including tables the app creates later) is queryable from SQL.

```python
from databricks.sdk.service.postgres import Catalog

try:
    w.postgres.create_catalog(
        Catalog.from_dict({"spec": {"postgres_database": PGDB, "branch": BRANCH}}),
        catalog_id=LBCAT)
    print(f"✅ registered UC catalog {LBCAT}")
except Exception as e:
    print(f"create_catalog: {type(e).__name__} (likely already exists) — {str(e)[:160]}")
```

### Step 4 — Create the snapshot synced tables

One **SNAPSHOT** synced table per Delta table. Each spins up a short pipeline (~2–4 min). The
synced-table id is `<catalog>.public.<table>` — `public` is the Postgres schema.

```python
from databricks.sdk.service.postgres import SyncedTable

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.pipeline_storage")  # sync metadata

PKS = {"machines": "machine_id", "sensor_readings": "reading_id",
       "production_orders": "order_id", "maintenance_tickets": "ticket_id"}
for tbl, pk in PKS.items():
    spec = {"spec": {
        "source_table_full_name": f"{UC_CATALOG}.{SCHEMA}.{tbl}",
        "primary_key_columns": [pk], "scheduling_policy": "SNAPSHOT",
        "branch": BRANCH, "postgres_database": PGDB,
        "create_database_objects_if_missing": True,
        "new_pipeline_spec": {"storage_catalog": UC_CATALOG, "storage_schema": "pipeline_storage"}}}
    try:
        w.postgres.create_synced_table(SyncedTable.from_dict(spec),
                                       synced_table_id=f"{LBCAT}.public.{tbl}")
        print(f"✅ queued synced table {tbl}")
    except Exception as e:
        print(f"{tbl}: {type(e).__name__} (likely already exists) — {str(e)[:120]}")
```

### Step 5 — Verify from the analytical side

Reading the Lakebase catalog from SQL proves both the sync landed **and** the round-trip
federation works. If you get 0 rows, the snapshot is still running — wait a minute and re-run.

```python
for tbl in PKS:
    try:
        print(f"OK  {LBCAT}.public.{tbl}: {spark.table(f'{LBCAT}.public.{tbl}').count()}")
    except Exception as e:
        print(f"…  {tbl} not ready yet — {str(e)[:80]}")
```

**✅ Check:** `machines: 50`, `sensor_readings: 10000`, etc. That query reads Postgres data
**through Unity Catalog** — proof the federation works before you've even built the app.

**💡 What just happened?**
- **Snapshot** = a one-time copy of your Delta table into Postgres (continuous sync exists too).
- Registering the database as UC catalog `lakebase_schema_<user>` federates the *whole* Postgres
  database — including tables your app will create later. That's the "back to analytics" leg,
  for free.

> **Prefer the UI?** *Compute ▸ Database instances ▸ `lakebase-workshop`* to create a database,
> then *Catalog Explorer ▸ Create ▸ Synced table* (Snapshot) per Delta table, and register the
> catalog from the database-instance page. Same result, click-driven.

➡️ **Next: [Lab 3 – Build and Deploy the App](Lab%203%20-%20Build%20and%20Deploy%20the%20App.md).**
