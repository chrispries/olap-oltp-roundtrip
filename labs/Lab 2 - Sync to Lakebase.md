# 🏭 Lab 2 – Sync to Lakebase (Bidirectional, with Change Data Feed)

## 🎯 Learning Objectives
By the end of this lab, you will:
- Create your own **Lakebase** project (managed PostgreSQL) and connect to it
- Sync your Delta tables **into** Lakebase as **CONTINUOUS** read-only serving tables (UC → Lakebase)
- Create **operational tables** your app owns and writes to (`maintenance_actions`, `work_orders`,
  `quality_checks`, `operator_notes`)
- Turn on **Change Data Feed (CDF)** so every write to those tables streams **back** into Unity
  Catalog as `lb_*_history` Delta tables (Lakebase → UC) — the true round-trip

## Overview

This lab wires up the **bidirectional data flow** between Unity Catalog (the lakehouse) and
Lakebase (operational Postgres):

```
┌─────────────────────┐         Synced Tables          ┌─────────────────────────┐
│   Unity Catalog     │ ──────────────────────────────► │   Lakebase Postgres     │
│   (Delta tables)    │    (read-only reference data)   │   (databricks_postgres) │
│                     │                                 │                         │
│  machines           │                                 │  machines (read-only)   │
│  sensor_readings    │                                 │  sensor_readings (r/o)  │
│  production_orders  │                                 │  production_orders (r/o)│
│  maintenance_tickets│                                 │  maintenance_tickets    │
└─────────────────────┘                                 └─────────────────────────┘
                                                                   │
                                                                   │ App writes
                                                                   ▼
┌─────────────────────┐     Change Data Feed (CDF)      ┌─────────────────────────┐
│   Unity Catalog     │ ◄────────────────────────────── │   Operational Tables    │
│   (lb_*_history)    │    (captures all mutations)     │   (app-owned, writable) │
│                     │                                 │                         │
│  lb_maintenance_    │                                 │  maintenance_actions    │
│    actions_history  │                                 │  work_orders            │
│  lb_work_orders_    │                                 │  quality_checks         │
│    history          │                                 │  operator_notes         │
└─────────────────────┘                                 └─────────────────────────┘
```

### The pattern
1. **Reference data** (machines, sensors, orders, tickets) is synced **from** the lakehouse
   **to** Lakebase as read-only tables your operational app queries.
2. **Operational tables** (maintenance actions, work orders, quality checks, notes) are created
   directly in Postgres — your app **writes** to these.
3. **Change Data Feed (CDF)** captures every `INSERT`/`UPDATE`/`DELETE` on the operational tables
   and streams them back to Unity Catalog as `lb_<table>_history` Delta tables (~15s batches).

> Read [`docs/concepts.md`](../docs/concepts.md) if you want the full mental model first.

## Prerequisites
- **Lab 1 completed** — the four Delta tables exist in `catalog_workshop.schema_<you>`.
- **Lakebase enabled** in your workspace.
- **CDF preview enabled** by a workspace admin (the *Previews* page). See
  [`docs/roles-and-permissions.md`](../docs/roles-and-permissions.md).

Run the cells below in order in a **serverless Python notebook**. This lab is self-contained.

---

### Step 0 — Check the default SDK version

The workspace's default `databricks-sdk` predates the Lakebase APIs. Run this first — it restarts
Python and prints the version you're starting from (you'll upgrade it in Step 1).

```python
dbutils.library.restartPython()
import importlib.metadata as md
print(f"databricks-sdk version: {md.version('databricks-sdk')}")
```

### Step 1 — Install the Lakebase SDK + Postgres driver

Upgrade `databricks-sdk` (for the `postgres` API) and install **pure-Python `psycopg`**. The
`psycopg-binary` wheel crashes the serverless kernel, so we uninstall it first, then restart
Python so the swap takes effect.

```python
import importlib.metadata as md, subprocess, sys

try:
    before = md.version("databricks-sdk")
except md.PackageNotFoundError:
    before = None

# Uninstall psycopg-binary (crashes kernel) and install pure-Python psycopg
subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "psycopg-binary"])
subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade",
                       "databricks-sdk>=0.118.0", "psycopg>=3.1", "protobuf<6.0.0"])

after = md.version("databricks-sdk")
print(f"databricks-sdk: {before} -> {after}")
print("Restarting Python to unload psycopg-binary...")
dbutils.library.restartPython()
```

> ⚠️ `restartPython()` wipes all variables and imports. That's expected — the next cells
> re-import and re-derive everything, so **run them after the restart.**

### Step 2 — Configuration

Set up all naming conventions and variables. Note two things that changed from the classic setup:

- **`PGDB = "databricks_postgres"`** — CDF requires tables to live in the project's *default*
  database, so we use it directly instead of creating a custom one.
- `PROJECT`/`BRANCH`/`ENDPOINT` are left `None` here and filled in by Step 4, which finds (or
  creates) a **healthy** project for you — the base name gets a numeric suffix to skip any
  "zombie" projects left behind by a failed earlier run.

```python
import re
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "", user.split("@")[0].lower())

PROJECT_BASE = f"lakebase-ws-{slug}"
# PROJECT, BRANCH, ENDPOINT are set by Cell 5 after finding/creating a healthy project
PROJECT    = None
BRANCH     = None
ENDPOINT   = None
UC_CATALOG = "catalog_workshop"      # the Delta data from Lab 1
SCHEMA     = f"schema_{slug}"             # your UC schema
PGDB       = "databricks_postgres"        # CDF requires the default database
LBCAT      = f"lakebase_schema_{slug}"    # your Lakebase → UC catalog

# host is resolved in Cell 6 after Cell 5 sets PROJECT/BRANCH/ENDPOINT
host = None

print(f"PROJECT_BASE={PROJECT_BASE}\nPGDB={PGDB}  LBCAT={LBCAT}")
```

Quick sanity check on your slug (this is the string appended to `schema_`, `lakebase-ws-`, etc.):

```python
print(slug)
```

### Step 3 — Find or create a healthy Lakebase project

A Lakebase **project** auto-provisions a `production` branch and a `primary` read-write endpoint.
This loop reuses an existing healthy project if it finds one, and otherwise creates a fresh one —
incrementing the numeric suffix to skip any project whose branches aren't reachable (a "zombie").

```python
# Find or create a healthy Lakebase project (skips zombies by incrementing the number)
from databricks.sdk.service.postgres import Project, ProjectSpec

MAX_ATTEMPTS = 10

for i in range(1, MAX_ATTEMPTS + 1):
    candidate = f"{PROJECT_BASE}-{i}"
    try:
        w.postgres.get_project(name=f"projects/{candidate}")
        # Project exists — check if it's healthy (branches accessible)
        try:
            branches = list(w.postgres.list_branches(parent=f"projects/{candidate}"))
            PROJECT = candidate
            print(f"✅ Project '{candidate}' exists and is healthy ({len(branches)} branch(es))")
            break
        except Exception:
            print(f"⚠️ Project '{candidate}' is a zombie (branches inaccessible) — skipping")
            continue
    except Exception:
        # Project doesn't exist — create it
        print(f"Creating project '{candidate}'...")
        op = w.postgres.create_project(
            project=Project(spec=ProjectSpec(display_name=candidate, pg_version=17)),
            project_id=candidate,
        )
        result = op.wait()
        PROJECT = candidate
        print(f"✅ Created Lakebase project: {result.name}")
        break
else:
    raise RuntimeError(f"Could not find or create a healthy project after {MAX_ATTEMPTS} attempts")

# Update dependent variables
BRANCH   = f"projects/{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
print(f"   PROJECT={PROJECT}\n   BRANCH={BRANCH}\n   ENDPOINT={ENDPOINT}")
```

> 📌 **Note your `PROJECT`, `BRANCH`, and `ENDPOINT`** — Lab 3 wires the app to exactly this
> project, and it re-derives them the same way.

### Step 4 — Connect to Postgres

Resolve the endpoint's host, then open a connection to `databricks_postgres`. The password is a
**short-lived OAuth token** minted by the SDK (`generate_database_credential`) — Autoscaling
Lakebase issues ~1h tokens rather than a static password, so we mint one per connection.

```python
import psycopg

# Resolve host if Cell 3 couldn't (project didn't exist yet)
if host is None:
    endpoint = next((ep for ep in w.postgres.list_endpoints(parent=BRANCH) if ep.name == ENDPOINT), None)
    host = endpoint.status.hosts.host if endpoint else None
    print(f"Resolved host: {host}")

def pg_token():
    return w.postgres.generate_database_credential(ENDPOINT).token

# 'databricks_postgres' is the default database auto-created with every project.
# CDF requires tables to be in this database, so we use it directly.
# Verify it's accessible:
with psycopg.connect(
    host=host, port=5432, dbname=PGDB, user=user,
    password=pg_token(), sslmode="require", autocommit=True
) as conn:
    conn.execute("SELECT 1")
    print(f"✅ Connected to database '{PGDB}' on {host}")
```

### Step 5 — Sync reference tables (UC → Lakebase)

Now the first direction. This:
1. creates a `pipeline_storage` schema (for sync-pipeline metadata) and the `lakebase_schema_<you>`
   catalog + `public` schema where the synced tables register,
2. enables **Change Data Feed on the source Delta tables** (required for `CONTINUOUS` sync),
3. creates a **`CONTINUOUS`** synced table for each of the four reference tables — a live,
   read-only replica in Postgres that your app queries.

```python
from databricks.sdk.service.postgres import SyncedTable

# Create the storage schema for pipeline metadata
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.pipeline_storage")

# Create the Lakebase catalog and schema (synced tables will be registered here)
spark.sql(f"CREATE CATALOG IF NOT EXISTS {LBCAT}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {LBCAT}.public")
print(f"✅ Catalog {LBCAT} and schema public ready")

PKS = {"machines": "machine_id", "sensor_readings": "reading_id",
       "production_orders": "order_id", "maintenance_tickets": "ticket_id"}

# Enable Change Data Feed on source tables (required for CONTINUOUS sync)
for tbl in PKS.keys():
    table_name = f"{UC_CATALOG}.{SCHEMA}.{tbl}"
    try:
        spark.sql(f"ALTER TABLE {table_name} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
        print(f"✅ Enabled CDF on {tbl}")
    except Exception as e:
        print(f"⚠️ Could not enable CDF on {tbl}: {str(e)[:80]}")

for tbl, pk in PKS.items():
    synced_table_id = f"{LBCAT}.public.{tbl}"
    
    # Check if table is already synced
    try:
        existing = w.postgres.get_synced_table(name=f"synced_tables/{synced_table_id}")
        state = existing.status.detailed_state if existing.status else "UNKNOWN"
        print(f"{tbl}: already synced ({state}) — skipping")
        continue
    except Exception as e:
        # NotFound is expected for new synced tables
        if "NotFound" not in str(type(e).__name__):
            print(f"{tbl}: Unexpected error during check: {type(e).__name__} — {str(e)[:100]}")
            continue

    # Create the synced table
    spec = {"spec": {
        "source_table_full_name": f"{UC_CATALOG}.{SCHEMA}.{tbl}",
        "primary_key_columns": [pk], "scheduling_policy": "CONTINUOUS",
        "branch": BRANCH, "postgres_database": PGDB,
        "create_database_objects_if_missing": True,
        "new_pipeline_spec": {"storage_catalog": UC_CATALOG, "storage_schema": "pipeline_storage"}}}
    try:
        w.postgres.create_synced_table(SyncedTable.from_dict(spec), synced_table_id=synced_table_id)
        print(f"✅ Created synced table {tbl}")
    except Exception as e:
        error_msg = str(e)
        if "AlreadyExists" in error_msg or "already exists" in error_msg.lower():
            print(f"{tbl}: Already exists — skipping")
        else:
            print(f"❌ {tbl}: {type(e).__name__} — {error_msg[:150]}")
```

> The pipelines take a couple of minutes to reach a running state. Because they're `CONTINUOUS`,
> any later change to the source Delta table flows into Postgres automatically.

### Step 6 — Create the operational tables (app-owned, writable)

These are the tables **your app writes to**. Because *you* create and own them, `REPLICA IDENTITY
FULL` works immediately (no permission issues), and CDF will be able to capture every change.
Four tables model the shop-floor workflow:

- **`maintenance_actions`** — work performed on a machine (preventive / corrective / inspection).
- **`work_orders`** — jobs raised when an anomaly or schedule triggers.
- **`quality_checks`** — inspection results during production runs.
- **`operator_notes`** — free-form annotations by operators.

```python
# ── Create operational tables (app-owned, writable, CDF-ready) ──
# These tables are written to BY YOUR APP based on the synced reference data.
# Since YOU own them, REPLICA IDENTITY FULL works immediately.
# CDF captures every INSERT/UPDATE/DELETE back to UC as lb_<table>_history.

import psycopg
from datetime import datetime

with psycopg.connect(
    host=host, port=5432, dbname=PGDB, user=user,
    password=pg_token(), sslmode="require", autocommit=True
) as conn:

    # 1. maintenance_actions — tracks work done on machines
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.maintenance_actions (
            action_id       SERIAL PRIMARY KEY,
            machine_id      INTEGER NOT NULL,
            ticket_id       INTEGER,
            action_type     TEXT NOT NULL,  -- 'preventive', 'corrective', 'inspection'
            description     TEXT,
            performed_by    TEXT NOT NULL,
            started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at    TIMESTAMPTZ,
            status          TEXT NOT NULL DEFAULT 'in_progress'  -- 'in_progress', 'completed', 'cancelled'
        );
    """)
    conn.execute("ALTER TABLE public.maintenance_actions REPLICA IDENTITY FULL")
    print("✅ Created public.maintenance_actions")

    # 2. work_orders — generated by app when sensor anomalies or schedules trigger
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.work_orders (
            work_order_id   SERIAL PRIMARY KEY,
            machine_id      INTEGER NOT NULL,
            order_id        INTEGER,
            priority        TEXT NOT NULL DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
            title           TEXT NOT NULL,
            description     TEXT,
            assigned_to     TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            due_date        DATE,
            status          TEXT NOT NULL DEFAULT 'open'  -- 'open', 'assigned', 'in_progress', 'closed'
        );
    """)
    conn.execute("ALTER TABLE public.work_orders REPLICA IDENTITY FULL")
    print("✅ Created public.work_orders")

    # 3. quality_checks — inspection results during production runs
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.quality_checks (
            check_id        SERIAL PRIMARY KEY,
            order_id        INTEGER NOT NULL,
            machine_id      INTEGER NOT NULL,
            check_type      TEXT NOT NULL,  -- 'visual', 'dimensional', 'functional'
            result          TEXT NOT NULL,  -- 'pass', 'fail', 'conditional'
            defect_code     TEXT,
            notes           TEXT,
            inspector       TEXT NOT NULL,
            checked_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    conn.execute("ALTER TABLE public.quality_checks REPLICA IDENTITY FULL")
    print("✅ Created public.quality_checks")

    # 4. operator_notes — free-form annotations by operators
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.operator_notes (
            note_id         SERIAL PRIMARY KEY,
            machine_id      INTEGER,
            ticket_id       INTEGER,
            order_id        INTEGER,
            note_type       TEXT NOT NULL DEFAULT 'general',  -- 'general', 'alert', 'handoff', 'resolution'
            content         TEXT NOT NULL,
            created_by      TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    conn.execute("ALTER TABLE public.operator_notes REPLICA IDENTITY FULL")
    print("✅ Created public.operator_notes")

    # Verify ownership and replica identity
    print("\n" + "-"*60)
    print("Operational tables (you own these → CDF-ready):")
    print("-"*60)
    rows = conn.execute("""
        SELECT c.relname AS table_name,
               pg_catalog.pg_get_userbyid(c.relowner) AS owner,
               CASE c.relreplident
                   WHEN 'f' THEN '✅ full' ELSE '❌ ' || c.relreplident::text
               END AS replica_identity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r' AND n.nspname = 'public'
          AND c.relname IN ('maintenance_actions', 'work_orders', 'quality_checks', 'operator_notes')
        ORDER BY c.relname;
    """).fetchall()
    for tbl, owner, ri in rows:
        print(f"  {tbl:25s} owner={owner:30s} replica={ri}")

print("\n✅ All operational tables created with REPLICA IDENTITY FULL.")
print("   CDF will capture all INSERTs/UPDATEs/DELETEs on these tables.")
print("   → lb_maintenance_actions_history")
print("   → lb_work_orders_history")
print("   → lb_quality_checks_history")
print("   → lb_operator_notes_history")
```

**✅ Check:** each table prints `replica=✅ full`.

### Step 7 — ⏸️ Manual: enable Lakebase CDF in the UI

**Stop here and complete this before running Step 8.** The SDK does not yet expose a method to
start CDF, so this one step is click-driven.

1. Open **Lakebase Postgres** from the app switcher (top right).
2. Select your project (e.g. `lakebase-ws-<you>-1`) → branch **production**.
3. Go to the **Change Data Feed** tab → click **Start**.
4. Configure:
   - Database: `databricks_postgres`
   - Schema: `public`
   - To Catalog: **`catalog_workshop`** (your destination UC catalog)
   - Schema: **`schema_<you>`** (your destination UC schema — same one from Lab 1)
5. Click **Start**.

> ℹ️ Once started, every `INSERT`/`UPDATE`/`DELETE` on the operational tables streams to UC as
> `lb_<table>_history` Delta tables (~15s batches). Pointing the destination at
> `catalog_workshop.schema_<you>` is what makes Lab 4's queries line up.

### Step 8 — Validate: simulate app writes and watch CDF capture them

Insert, update, and delete rows across the operational tables so CDF captures **all** change
types. (In Lab 3 the app does these writes for real; here we prove the plumbing works first.)

```python
# ── Simulate operational app writes to test CDF sync ──
# Performs INSERTs, UPDATEs, and DELETEs so CDF captures all change types.

import psycopg
from datetime import date, timedelta

with psycopg.connect(
    host=host, port=5432, dbname=PGDB, user=user,
    password=pg_token(), sslmode="require", autocommit=True
) as conn:

    # ── INSERTs ──
    print("Inserting sample data...")

    # maintenance_actions
    conn.execute("""
        INSERT INTO public.maintenance_actions (machine_id, ticket_id, action_type, description, performed_by, status)
        VALUES
            (1, 101, 'preventive', 'Replaced hydraulic fluid and filters', 'operator_jones', 'completed'),
            (2, NULL, 'inspection', 'Routine vibration analysis on spindle', 'tech_smith', 'completed'),
            (3, 205, 'corrective', 'Replaced worn bearing on conveyor belt', 'tech_martinez', 'in_progress'),
            (1, 102, 'preventive', 'Calibrated temperature sensors', 'operator_jones', 'completed');
    """)
    print("  ✅ 4 rows → maintenance_actions")

    # work_orders
    conn.execute(f"""
        INSERT INTO public.work_orders (machine_id, order_id, priority, title, description, assigned_to, due_date, status)
        VALUES
            (2, 1001, 'high', 'Spindle replacement needed', 'Vibration exceeded threshold by 40%%', 'tech_smith', '{date.today() + timedelta(days=2)}', 'assigned'),
            (3, 1002, 'critical', 'Conveyor emergency stop triggered', 'Belt misalignment detected by sensor', 'tech_martinez', '{date.today()}', 'in_progress'),
            (1, 1003, 'low', 'Scheduled lubrication', 'Monthly lubrication per maintenance plan', 'operator_jones', '{date.today() + timedelta(days=7)}', 'open');
    """)
    print("  ✅ 3 rows → work_orders")

    # quality_checks
    conn.execute("""
        INSERT INTO public.quality_checks (order_id, machine_id, check_type, result, defect_code, notes, inspector)
        VALUES
            (1001, 2, 'dimensional', 'pass', NULL, 'All tolerances within spec', 'qc_nguyen'),
            (1001, 2, 'functional', 'fail', 'VIB-003', 'Excessive vibration at 3000rpm', 'qc_nguyen'),
            (1002, 3, 'visual', 'conditional', 'ALN-001', 'Minor belt wear observed, monitor closely', 'qc_park'),
            (1003, 1, 'functional', 'pass', NULL, 'Operating within normal parameters', 'qc_nguyen');
    """)
    print("  ✅ 4 rows → quality_checks")

    # operator_notes
    conn.execute("""
        INSERT INTO public.operator_notes (machine_id, ticket_id, order_id, note_type, content, created_by)
        VALUES
            (2, NULL, 1001, 'alert', 'Hearing unusual grinding noise from spindle during high-speed operation', 'operator_jones'),
            (3, 205, 1002, 'handoff', 'Shift handoff: conveyor belt realignment in progress, do not restart', 'tech_martinez'),
            (1, 102, NULL, 'resolution', 'Temperature sensors recalibrated, readings now within 0.5C tolerance', 'operator_jones');
    """)
    print("  ✅ 3 rows → operator_notes")

    # ── UPDATEs (simulate app modifying operational state) ──
    print("\nSimulating status updates...")

    conn.execute("""
        UPDATE public.maintenance_actions
        SET status = 'completed', completed_at = now()
        WHERE machine_id = 3 AND status = 'in_progress';
    """)
    print("  ✅ Updated maintenance_actions: machine 3 action → completed")

    conn.execute("""
        UPDATE public.work_orders
        SET status = 'closed'
        WHERE machine_id = 2 AND priority = 'high';
    """)
    print("  ✅ Updated work_orders: spindle replacement → closed")

    # ── DELETE (simulate cancellation) ──
    print("\nSimulating a cancellation (DELETE)...")

    conn.execute("""
        DELETE FROM public.work_orders
        WHERE priority = 'low' AND status = 'open';
    """)
    print("  ✅ Deleted work_orders: cancelled low-priority scheduled lubrication")

    # ── Verify final state ──
    print("\n" + "="*60)
    print("Final table row counts:")
    print("="*60)
    for tbl in ['maintenance_actions', 'work_orders', 'quality_checks', 'operator_notes']:
        count = conn.execute(f"SELECT COUNT(*) FROM public.{tbl}").fetchone()[0]
        print(f"  {tbl:25s} → {count} rows")

    # ── Check CDF status ──
    print("\n" + "="*60)
    print("CDF status (wal2delta.tables):")
    print("="*60)
    try:
        cdf_rows = conn.execute("SELECT * FROM wal2delta.tables").fetchall()
        if cdf_rows:
            for row in cdf_rows:
                print(f"  {row}")
        else:
            print("  (no tables in CDF yet — start CDF from the UI if not done)")
    except Exception as e:
        print(f"  ⚠️ Could not query wal2delta.tables: {str(e).split(chr(10))[0]}")

print("\n✅ Done! Check your UC destination schema for lb_*_history tables.")
print("   CDF flushes every ~15 seconds — tables may take a moment to appear.")
```

**✅ Check:** the row counts print (maintenance_actions 4, work_orders 2 after the delete,
quality_checks 4, operator_notes 3), and after ~15–30s the `lb_*_history` tables appear under
`catalog_workshop.schema_<you>` in Catalog Explorer. You can confirm from SQL:

```sql
SELECT * FROM catalog_workshop.schema_<you>.lb_maintenance_actions_history ORDER BY 1;
```

**💡 What just happened?**

- **Technically:** you stood up a full **bidirectional** bridge. `CONTINUOUS` synced tables give
  Lakebase a live, read-only copy of your Delta reference data (UC → Lakebase). Four app-owned
  operational tables give the app somewhere to write. And **CDF** replays every write on those
  tables into Delta `lb_*_history` tables (Lakebase → UC) — a real change-data pipeline, not a
  point-in-time snapshot.
- **In the scenario:** the shop-floor app can now read the reference data at millisecond latency
  *and* record what technicians do — and the data team sees each of those actions land back in
  the lakehouse within seconds, ready for MTTR reporting and model retraining. That closed loop is
  what Labs 3 and 4 exercise for real.

➡️ **Next: [Lab 3 – Build and Deploy the App](Lab%203%20-%20Build%20and%20Deploy%20the%20App.md).**
