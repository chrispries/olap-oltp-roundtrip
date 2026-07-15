# 🏭 Lab 2 – Sync to Lakebase (with Change Data Feed)

> 📓 Prefer the notebook? This lab is also [`notebooks/Lab2 - Lakebase Postgres with CDF.ipynb`](../notebooks/Lab2%20-%20Lakebase%20Postgres%20with%20CDF.ipynb) — same code, run it top to bottom.

## 🎯 Learning Objectives
By the end of this lab, you will:
- Create your own **Lakebase Postgres** project (managed PostgreSQL) and connect to it
- Sync your Lab 1 Delta tables **into** Postgres as read-only replicas (UC → Lakebase)
- Create **operational tables** your app owns and writes to (`maintenance_actions`, `work_orders`,
  `quality_checks`, `operator_notes`)
- Enable **Change Data Feed (CDF)** so every write streams **back** into Unity Catalog as
  `lb_*_history` Delta tables (Lakebase → UC) — the true round-trip

## Overview

In Lab 1 you created Delta tables — perfect for analytics at scale. But operational apps need
low-latency row lookups, ACID writes, and real-time changes flowing back to the lake. That's
**Lakebase Postgres**. This lab wires up the **bidirectional pipeline**:

```
Unity Catalog (catalog_workshop)
  └─ schema_{your_name} (Lab1 source tables)
       ├─ machines · sensor_readings · production_orders · maintenance_tickets
                   ↓ Sync (SNAPSHOT) ↓
  Lakebase Postgres (databricks_postgres.public)
       ├─ machines · sensor_readings · production_orders · maintenance_tickets  (read-only replicas)
       ├─ maintenance_actions · work_orders · quality_checks · operator_notes    (your app writes)
                   ↓ Change Data Feed ↓
  └─ catalog_workshop.lakebase_{your_name}
       ├─ machines · sensor_readings · production_orders · maintenance_tickets  (synced, registered in UC)
       └─ lb_maintenance_actions_history · lb_work_orders_history · lb_quality_checks_history · lb_operator_notes_history
```

Everything lives in **one catalog** (`catalog_workshop`): your Lab 1 source in `schema_{your_name}`,
and the synced replicas + CDF history in `lakebase_{your_name}`.

> Read [`docs/concepts.md`](../docs/concepts.md) for the full mental model first.

## Prerequisites
- **Lab 1 completed** — the four Delta tables exist in `catalog_workshop.schema_{your_name}`.
- **Lakebase enabled** in your workspace.
- **CDF preview enabled** by a workspace admin (the *Previews* page). See
  [`docs/roles-and-permissions.md`](../docs/roles-and-permissions.md).

Run the cells below in order in a **serverless Python notebook**.

---

### Step 1 — Make sure the catalog exists

```sql
%sql
-- Ensure the Unity Catalog exists (shared catalog for workshop)
-- IF NOT EXISTS makes this safe to re-run without errors
CREATE CATALOG IF NOT EXISTS catalog_workshop;

-- Verify creation by listing all catalogs
-- You should see: main, system, hive_metastore, samples, and catalog_workshop
SHOW CATALOGS;
```

### Step 2 — Check the default SDK version

The workspace's default `databricks-sdk` predates the Lakebase APIs. Run this first — it restarts
Python and prints the version you're starting from.

```python
# Restart the Python kernel to start with a clean slate
# This clears all imported modules and variables
dbutils.library.restartPython()

# After restart, check which SDK version is currently installed
import importlib.metadata as md
print(f"databricks-sdk version: {md.version('databricks-sdk')}")
print("\n➡️  Run Cell 3 to upgrade to the required version")
```

### Step 3 — Install the Lakebase SDK + Postgres driver

Upgrade `databricks-sdk` (for the `postgres` API) and install **pure-Python `psycopg`**. The
`psycopg-binary` wheel crashes the serverless kernel, so we uninstall it first, then restart
Python so the swap takes effect.

```python
import importlib.metadata as md, subprocess, sys

# Capture the current version before upgrade
try:
    before = md.version("databricks-sdk")
except md.PackageNotFoundError:
    before = None  # Not installed yet

# ─── CRITICAL: Remove psycopg-binary ───
# psycopg-binary uses C extensions that crash on serverless compute
# We use pure-Python psycopg instead (slower but stable)
subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "psycopg-binary"])

# ─── Install required packages ───
subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade",
                       "databricks-sdk>=0.118.0",  # Lakebase Postgres API support
                       "psycopg>=3.1",              # Pure-Python Postgres client
                       "protobuf<6.0.0"])           # SDK serialization compatibility

# Show version change
after = md.version("databricks-sdk")
print(f"databricks-sdk: {before} -> {after}")
print("\n✅ Packages installed successfully")
print("Restarting Python to unload old psycopg-binary...")

# Restart again to ensure psycopg-binary is fully unloaded
dbutils.library.restartPython()
```

> ⚠️ `restartPython()` wipes all variables and imports. Run the next cells after the restart.

### Step 4 — Configuration

Define all naming conventions. Two things to note:

- **`LAKEBASE_SCHEMA = lakebase_{slug}`** is a *schema* inside `catalog_workshop` — it holds both
  the synced replicas and the CDF history, so everything stays in one catalog.
- **`PGDB = databricks_postgres`** — CDF requires the project's default database.
- `PROJECT`/`BRANCH`/`ENDPOINT` are filled in by the next step, which finds (or creates) a
  **healthy** project for you.

```python
import re
from databricks.sdk import WorkspaceClient

# Initialize the Databricks SDK workspace client
w = WorkspaceClient()

# Get current user's email and create a slug (remove special chars)
# Example: user.name@company.com -> username
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "", user.split("@")[0].lower())

# ─── Lakebase Project Variables ───
PROJECT_BASE = f"lakebase-ws-{slug}"  # Base name for Lakebase projects
# These are set by Cell 5 after finding/creating a healthy project:
PROJECT    = None  # Actual project name (e.g., lakebase-ws-{your_name}-1)
BRANCH     = None  # Branch path (e.g., projects/.../branches/production)
ENDPOINT   = None  # Endpoint path (e.g., .../endpoints/primary)

# ─── Unity Catalog Variables ───
UC_CATALOG = "catalog_workshop"           # Shared catalog (from Lab 1)
SCHEMA     = f"schema_{slug}"             # Source schema with Lab1 tables
LAKEBASE_SCHEMA = f"lakebase_{slug}"      # Target schema for synced tables + CDF history

# ─── Postgres Variables ───
PGDB       = "databricks_postgres"        # Default database (required for CDF)
host       = None  # Postgres host (resolved in Cell 6)

# Display configuration
print("\n⚙️  Configuration:")
print(f"   PROJECT_BASE     = {PROJECT_BASE}")
print(f"   UC_CATALOG       = {UC_CATALOG}")
print(f"   SCHEMA           = {SCHEMA} (source data from Lab1)")
print(f"   LAKEBASE_SCHEMA  = {LAKEBASE_SCHEMA} (synced tables + CDF history)")
print(f"   PGDB             = {PGDB}")
print(f"\n➡️  Run Cell 5 to create/find Lakebase project")
```

### Step 5 — Find or create a healthy Lakebase project

A Lakebase **project** auto-provisions a `production` branch and a `primary` endpoint. This loop
reuses an existing healthy project, or creates a fresh one — incrementing the numeric suffix to
skip any project whose branches aren't reachable (a "zombie").

```python
# Find or create a healthy Lakebase project
# This logic handles "zombie" projects by checking branch accessibility
from databricks.sdk.service.postgres import Project, ProjectSpec

MAX_ATTEMPTS = 20  # Try up to 10 different project numbers

# Try project names: lakebase-ws-{your_name}-1, -2, -3, etc.
for i in range(1, MAX_ATTEMPTS + 1):
    candidate = f"{PROJECT_BASE}-{i}"
    
    try:
        # Check if project already exists
        w.postgres.get_project(name=f"projects/{candidate}")
        
        # Project exists — verify it's healthy by listing branches
        # Zombie projects fail at this step
        try:
            branches = list(w.postgres.list_branches(parent=f"projects/{candidate}"))
            # Success! This project is healthy and usable
            PROJECT = candidate
            print(f"✅ Project '{candidate}' exists and is healthy ({len(branches)} branch(es))")
            break  # Stop searching, use this one
        except Exception:
            # Project exists but branches are inaccessible (zombie)
            print(f"⚠️  Project '{candidate}' is a zombie (branches inaccessible) — skipping")
            continue  # Try next number
    
    except Exception:
        # Project doesn't exist yet — create it!
        print(f"Creating project '{candidate}'...")
        
        # Create with Postgres 17 and default settings
        op = w.postgres.create_project(
            project=Project(spec=ProjectSpec(
                display_name=candidate,  # Display name in UI
                pg_version=17            # PostgreSQL version
            )),
            project_id=candidate,        # Unique ID (same as display name)
        )
        
        # Wait for creation to complete (async operation)
        result = op.wait()
        PROJECT = candidate
        print(f"✅ Created Lakebase project: {result.name}")
        break  # Done!

else:
    # Loop completed without finding/creating a healthy project
    raise RuntimeError(f"Could not find or create a healthy project after {MAX_ATTEMPTS} attempts")

# ─── Set up dependent variables ───
# Lakebase uses a hierarchical path structure:
# projects/{project}/branches/{branch}/endpoints/{endpoint}
BRANCH   = f"projects/{PROJECT}/branches/production"  # Production branch
ENDPOINT = f"{BRANCH}/endpoints/primary"              # Primary endpoint

print(f"\n✅ Lakebase project ready:")
print(f"   PROJECT  = {PROJECT}")
print(f"   BRANCH   = {BRANCH}")
print(f"   ENDPOINT = {ENDPOINT}")
print(f"\n➡️  Run Cell 6 to get connection details")
```

> 📌 **Note your `PROJECT`** — Lab 3 wires the app to exactly this project, re-derived the same way.

### Step 6 — Connection details & authentication

Resolve the endpoint host and set up a token helper. Lakebase uses **short-lived OAuth tokens**
(minted on demand), not a static password.

```python
# ─── Get endpoint connection details ───
# Query the endpoint to get its hostname and port
endpoint_info = w.postgres.get_endpoint(name=ENDPOINT)
host = endpoint_info.status.hosts.host  # e.g., xyz.cloud.databricks.com

print(f"✅ Endpoint host: {host}")
print(f"   Port: 5432 (standard Postgres)")
print(f"   Database: {PGDB}")
print(f"   SSL: required")

# ─── Create authentication helper ───
def pg_token():
    """
    Fetch a fresh OAuth token for Postgres authentication.
    
    Lakebase uses OAuth tokens instead of static passwords.
    Tokens expire after ~1 hour and are automatically refreshed.
    
    Returns:
        str: OAuth access token to use as Postgres password
    """
    from databricks.sdk.core import oauth_service_principal
    
    cfg = w.config
    
    # Ensure we're using OAuth M2M (machine-to-machine) authentication
    if not cfg.client_id or not cfg.client_secret:
        raise ValueError(
            "Must use OAuth M2M (client_id + client_secret).\n"
            "Set DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET environment variables."
        )
    
    # Get credentials and extract the access token
    creds = oauth_service_principal(cfg)
    return creds.token().access_token

print(f"\n✅ Authentication helper created: pg_token()")
print(f"   Call pg_token() to get a fresh OAuth token for Postgres password")
print(f"\n➡️  Run Cell 7 to create synced tables")
```

> ℹ️ `pg_token()` uses OAuth **M2M** (service-principal) credentials. On interactive serverless
> notebooks the later cells fall back to `w.postgres.generate_database_credential(...)`, which
> works with your user identity too — both mint the same kind of short-lived token.

### Step 7 — Sync the Lab 1 tables into Postgres (UC → Lakebase)

Create the `lakebase_{slug}` schema, enable **Change Data Feed on the source Delta tables**, then
create a **`SNAPSHOT`** synced table for each — a read-only Postgres replica registered in UC.

```python
from databricks.sdk.service.postgres import (
    SyncedTable,
    SyncedTableSyncedTableSpec,
    SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy,
)

# ─── Step 1: Create Unity Catalog schema ───
# lakebase_{your_name}: Schema for synced table metadata and CDF history tables
#   - Synced tables: Read-only Delta replicas of Postgres tables (registered in UC)
#   - CDF history tables: Capture changes from Postgres operational tables (lb_*_history)
#   - The SDK automatically manages pipeline metadata storage internally
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.{LAKEBASE_SCHEMA}")

print(f"✅ Schema created:")
print(f"   {UC_CATALOG}.{LAKEBASE_SCHEMA} (synced tables + CDF history)")

# ─── Step 2: Define primary keys ───
# Synced tables REQUIRE primary keys to track row identity
# Without a PK, Lakebase can't determine which rows changed
PKS = {
    'machines': ['machine_id'],              # Unique machine identifier
    'sensor_readings': ['reading_id'],       # Unique reading ID
    'production_orders': ['order_id'],       # Unique order number
    'maintenance_tickets': ['ticket_id']     # Unique ticket ID
}

# ─── Step 3: Enable Change Data Feed on source tables ───
# CDF tracks all INSERT/UPDATE/DELETE operations
# Adds metadata: _change_type, _commit_version, _commit_timestamp
print(f"\nEnabling Change Data Feed on source tables...")
for tbl in PKS.keys():
    try:
        spark.sql(f"""
            ALTER TABLE {UC_CATALOG}.{SCHEMA}.{tbl} 
            SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
        """)
        print(f"   ✅ {tbl}: CDF enabled")
    except Exception as e:
        # Might already be enabled - not a fatal error
        if "already set" in str(e).lower():
            print(f"   ✅ {tbl}: CDF already enabled")
        else:
            print(f"   ⚠️  {tbl}: Could not enable CDF - {str(e)[:80]}")

# ─── Step 4: Create synced tables ───
# These are read-only Postgres replicas of your Delta tables
print(f"\nCreating synced tables (Delta → Postgres)...")
for tbl, pk in PKS.items():
    # The synced table's Unity Catalog identifier (for metadata)
    synced_table_id = f"{UC_CATALOG}.{LAKEBASE_SCHEMA}.{tbl}"
    
    try:
        # Create the synced table using the correct SDK API
        w.postgres.create_synced_table(
            synced_table=SyncedTable(
                spec=SyncedTableSyncedTableSpec(
                    # Source: Delta table in Unity Catalog
                    source_table_full_name=f"{UC_CATALOG}.{SCHEMA}.{tbl}",
                    
                    # Which Lakebase branch to sync to
                    branch=BRANCH,  # projects/{project}/branches/production
                    
                    # REQUIRED: Primary key columns (must be a list)
                    primary_key_columns=pk,
                    
                    # Sync mode: SNAPSHOT for one-time full copy
                    # Alternatives: CONTINUOUS (real-time), TRIGGERED (scheduled)
                    scheduling_policy=SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy.SNAPSHOT,
                    
                    # Destination Postgres database
                    postgres_database=PGDB,  # databricks_postgres
                    
                    # Auto-create schema and table in Postgres if missing
                    create_database_objects_if_missing=True,
                )
            ),
            # Unity Catalog identifier for the synced table metadata
            synced_table_id=synced_table_id,
        ).wait()  # Wait for sync to provision (may take 1-2 minutes)
        
        print(f"   ✅ {tbl:30s} synced (PK: {', '.join(pk)})")
    except Exception as e:
        # Already exists, or permissions issue
        if "already exists" in str(e).lower():
            print(f"   ✅ {tbl:30s} already synced")
        else:
            print(f"   ❌ {tbl:30s} {e.__class__.__name__} — {str(e)[:80]}")

print(f"\n✅ Synced tables created! Postgres now has read-only replicas.")
print(f"   Snapshot complete - tables copied once from Delta to Postgres.")
print(f"\n➡️  Run Cell 8 to verify the schemas were created")
```

### Step 8 — Check the sync landed

Sync provisioning takes a minute or two. This checks both the SDK sync status and the actual
Postgres tables.

```python
import psycopg

print("="*70)
print("🔍 SYNCED TABLE STATUS CHECK")
print("="*70)

# Expected synced tables
expected_tables = ['machines', 'sensor_readings', 'production_orders', 'maintenance_tickets']

print("\n[1] Checking sync status via SDK...\n")
for tbl in expected_tables:
    synced_table_id = f"{UC_CATALOG}.{LAKEBASE_SCHEMA}.{tbl}"
    try:
        # Get the synced table status from the SDK
        st = w.postgres.get_synced_table(name=f"synced_tables/{synced_table_id}")
        # Handle different SDK response structures
        if hasattr(st.status, 'current_state'):
            state = st.status.current_state.value if hasattr(st.status.current_state, 'value') else str(st.status.current_state)
        elif hasattr(st, 'state'):
            state = st.state.value if hasattr(st.state, 'value') else str(st.state)
        else:
            # Fallback: show the full status object
            state = str(st.status) if st.status else "UNKNOWN"
        print(f"  {tbl:30s} → {state}")
    except Exception as e:
        print(f"  {tbl:30s} → ❌ Not found or error: {str(e)[:50]}")

print("\n[2] Checking actual Postgres tables...\n")
try:
    with psycopg.connect(
        host=host,
        port=5432,
        dbname=PGDB,
        user=user,
        password=w.postgres.generate_database_credential(endpoint=ENDPOINT).token,
        sslmode="require",
        autocommit=True  # Prevent transaction abort on errors
    ) as conn:
        for tbl in expected_tables:
            try:
                # Try to query the table
                result = conn.execute(f"SELECT COUNT(*) FROM {LAKEBASE_SCHEMA}.{tbl}").fetchone()
                count = result[0] if result else 0
                print(f"  ✅ {tbl:30s} → {count:,} rows")
            except Exception as e:
                error_msg = str(e)
                if "does not exist" in error_msg:
                    print(f"  ⏳ {tbl:30s} → Table not created yet (still provisioning)")
                else:
                    print(f"  ❌ {tbl:30s} → Error: {error_msg[:50]}")
except Exception as e:
    print(f"  ❌ Connection failed: {str(e)[:100]}")

print("\n" + "="*70)
print("INTERPRETATION:")
print("="*70)
print("• ACTIVE + rows > 0     → ✅ Fully synced and ready")
print("• ACTIVE + rows = 0     → ⚠️  Sync pipeline running, data coming soon")
print("• PROVISIONING          → ⏳ Initial setup, wait 1-2 minutes")
print("• Table not found       → ⏳ Postgres table creation in progress")
print("="*70)
```

### Step 9 — Create the operational tables (app-owned, writable)

These are the tables **your app writes to**. Because *you* create and own them, `REPLICA IDENTITY
FULL` works immediately — which CDF needs to capture full before/after row state.

```python
import psycopg

# Connect to Postgres using OAuth token authentication
with psycopg.connect(
    host=host,              # From Cell 6
    port=5432,              # Standard Postgres port
    dbname=PGDB,            # databricks_postgres
    user=user,              # Your email (Databricks identity)
    password=w.postgres.generate_database_credential(endpoint=ENDPOINT).token,    # OAuth token (NOT a static password)
    sslmode="require",      # Enforce TLS encryption
    autocommit=True         # Each statement commits immediately
) as conn:
    print("🛠️  Creating operational tables (your app will write to these)...\n")
    
    # ─── TABLE 1: maintenance_actions ───
    # Tracks actions taken by technicians (repairs, inspections, preventive maintenance)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.maintenance_actions (
            action_id SERIAL PRIMARY KEY,              -- Auto-incrementing ID
            machine_id INTEGER NOT NULL,                -- FK to machines table
            ticket_id INTEGER,                          -- FK to maintenance_tickets (optional)
            action_type VARCHAR(50),                    -- preventive, corrective, inspection
            description TEXT,                           -- What was done
            performed_by VARCHAR(100),                  -- Technician name
            performed_at TIMESTAMPTZ DEFAULT now(),     -- When started (auto-timestamp)
            status VARCHAR(50),                         -- in_progress, completed, failed
            completed_at TIMESTAMPTZ                    -- When finished (nullable)
        );
    """)
    print("✅ maintenance_actions     (tracks repair and inspection work)")
    
    # ─── TABLE 2: work_orders ───
    # Work orders scheduled for machines (preventive or reactive)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.work_orders (
            work_order_id SERIAL PRIMARY KEY,          -- Auto-incrementing ID
            machine_id INTEGER NOT NULL,                -- FK to machines table
            order_id INTEGER,                           -- FK to production_orders (optional)
            priority VARCHAR(20),                       -- low, medium, high, critical
            title VARCHAR(200),                         -- Short description
            description TEXT,                           -- Detailed work instructions
            assigned_to VARCHAR(100),                   -- Technician assigned
            created_at TIMESTAMPTZ DEFAULT now(),       -- When created (auto-timestamp)
            due_date DATE,                              -- Target completion date
            status VARCHAR(50)                          -- open, assigned, in_progress, closed
        );
    """)
    print("✅ work_orders            (scheduled maintenance tasks)")
    
    # ─── TABLE 3: quality_checks ───
    # QA inspection results for production orders
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.quality_checks (
            check_id SERIAL PRIMARY KEY,               -- Auto-incrementing ID
            order_id INTEGER,                           -- FK to production_orders
            machine_id INTEGER,                         -- FK to machines table
            check_type VARCHAR(50),                     -- dimensional, functional, visual
            result VARCHAR(20),                         -- pass, fail, conditional
            defect_code VARCHAR(50),                    -- Defect classification (if failed)
            notes TEXT,                                 -- Inspector observations
            inspector VARCHAR(100),                     -- QA inspector name
            checked_at TIMESTAMPTZ DEFAULT now()        -- Inspection timestamp
        );
    """)
    print("✅ quality_checks         (QA inspection results)")
    
    # ─── TABLE 4: operator_notes ───
    # Operator observations, alerts, and shift handoff notes
    conn.execute("""
        CREATE TABLE IF NOT EXISTS public.operator_notes (
            note_id SERIAL PRIMARY KEY,                -- Auto-incrementing ID
            machine_id INTEGER,                         -- FK to machines (optional)
            ticket_id INTEGER,                          -- FK to maintenance_tickets (optional)
            order_id INTEGER,                           -- FK to production_orders (optional)
            note_type VARCHAR(50),                      -- alert, handoff, resolution, observation
            content TEXT,                               -- Free-form note text
            created_by VARCHAR(100),                    -- Operator name
            created_at TIMESTAMPTZ DEFAULT now()        -- Note timestamp
        );
    """)
    print("✅ operator_notes         (operator observations and handoffs)")
    
    # ─── CRITICAL: Enable REPLICA IDENTITY FULL for CDF ───
    # Without this, CDF will SKIP these tables!
    # REPLICA IDENTITY FULL tells Postgres to include all column values in the WAL (Write-Ahead Log)
    # This is required for CDF to capture the full before/after state of each row
    print("\n🔧 Enabling REPLICA IDENTITY FULL (required for CDF)...\n")
    
    for table in ['maintenance_actions', 'work_orders', 'quality_checks', 'operator_notes']:
        conn.execute(f"ALTER TABLE public.{table} REPLICA IDENTITY FULL;")
        print(f"✅ {table:25s} → REPLICA IDENTITY FULL enabled")
    
print("\n✅ All operational tables created in Postgres!")
print(f"   Tables are ready for INSERT/UPDATE/DELETE from your app.")
print(f"   REPLICA IDENTITY FULL is enabled — CDF will capture all changes.")
print(f"\n➡️  Next: Complete the manual CDF setup in Cell 10")
```

Quick confirmation of what's now in Postgres:

```python
import psycopg

# Connect and list all tables in the public schema
with psycopg.connect(
    host=host,
    port=5432,
    dbname=PGDB,
    user=user,
    password=w.postgres.generate_database_credential(endpoint=ENDPOINT).token,
    sslmode="require"
) as conn:
    result = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """).fetchall()
    
    print(f"📊 Tables in {PROJECT} → databricks_postgres.public:\n")
    
    # Expected tables
    synced_expected = {'machines', 'sensor_readings', 'production_orders', 'maintenance_tickets'}
    operational_expected = {'maintenance_actions', 'work_orders', 'quality_checks', 'operator_notes'}
    
    found_tables = {row[0] for row in result}
    
    synced_found = found_tables & synced_expected
    operational_found = found_tables & operational_expected
    
    if synced_found:
        print("🔄 Synced tables (from Unity Catalog):")
        for t in sorted(synced_found):
            print(f"   ✅ {t}")
    
    if operational_found:
        print("\n📝 Operational tables (app-writable):")
        for t in sorted(operational_found):
            print(f"   ✅ {t}")
    
    print(f"\n📊 Total user tables: {len(found_tables)}")
```

### Step 10 — ⏸️ Manual: enable Lakebase CDF in the UI

**Stop here and complete this before running Step 11.** The SDK does not yet expose a method to
start CDF, so this one step is click-driven.

1. **Open Lakebase Postgres** from the app switcher (top right).
2. **Select your project** (e.g. `lakebase-ws-{your_name}-1`) → branch `production`.
3. **Go to the Change Data Feed tab** → click **Start**.
4. **Configure**:
   - **Database**: `databricks_postgres`
   - **Schema**: `public`
   - **To Catalog**: `catalog_workshop`
   - **Schema**: `lakebase_{your_name}` (where CDF history tables will land)
5. **Review the table list** — you should see all 4 operational tables.
6. **Click Start**.

> ℹ️ Once started, every `INSERT`/`UPDATE`/`DELETE` on the operational tables streams to UC as
> `lb_<table>_history` Delta tables in `catalog_workshop.lakebase_{your_name}` (~15–30s batches).

### Step 11 — Validate: simulate app writes and watch CDF capture them

Insert, update, and delete rows across the operational tables so CDF captures **all** change
types. (In Lab 3 the app does these for real; here we prove the plumbing works.)

```python
# ─── Simulate operational app writes to test CDF sync ───
# Performs INSERTs, UPDATEs, and DELETEs so CDF captures all change types.
# This is what a real manufacturing app would do when operators interact with it.

import psycopg
from datetime import date, timedelta

# Connect to Postgres
with psycopg.connect(
    host=host, port=5432, dbname=PGDB, user=user,
    password=w.postgres.generate_database_credential(endpoint=ENDPOINT).token, sslmode="require", autocommit=True
) as conn:

    # ─── STEP 1: INSERTs (Create New Records) ───
    print("📝 Inserting sample operational data...\n")

    # maintenance_actions - Technician work log
    conn.execute("""
        INSERT INTO public.maintenance_actions (machine_id, ticket_id, action_type, description, performed_by, status)
        VALUES
            (1, 101, 'preventive', 'Replaced hydraulic fluid and filters', 'operator_jones', 'completed'),
            (2, NULL, 'inspection', 'Routine vibration analysis on spindle', 'tech_smith', 'completed'),
            (3, 205, 'corrective', 'Replaced worn bearing on conveyor belt', 'tech_martinez', 'in_progress'),
            (1, 102, 'preventive', 'Calibrated temperature sensors', 'operator_jones', 'completed');
    """)
    print("✅ maintenance_actions:  4 rows inserted")

    # work_orders - Scheduled maintenance work
    conn.execute(f"""
        INSERT INTO public.work_orders (machine_id, order_id, priority, title, description, assigned_to, due_date, status)
        VALUES
            (2, 1001, 'high', 'Spindle replacement needed', 'Vibration exceeded threshold by 40%%', 'tech_smith', '{date.today() + timedelta(days=2)}', 'assigned'),
            (3, 1002, 'critical', 'Conveyor emergency stop triggered', 'Belt misalignment detected by sensor', 'tech_martinez', '{date.today()}', 'in_progress'),
            (1, 1003, 'low', 'Scheduled lubrication', 'Monthly lubrication per maintenance plan', 'operator_jones', '{date.today() + timedelta(days=7)}', 'open');
    """)
    print("✅ work_orders:          3 rows inserted")

    # quality_checks - QA inspection results
    conn.execute("""
        INSERT INTO public.quality_checks (order_id, machine_id, check_type, result, defect_code, notes, inspector)
        VALUES
            (1001, 2, 'dimensional', 'pass', NULL, 'All tolerances within spec', 'qc_nguyen'),
            (1001, 2, 'functional', 'fail', 'VIB-003', 'Excessive vibration at 3000rpm', 'qc_nguyen'),
            (1002, 3, 'visual', 'conditional', 'ALN-001', 'Minor belt wear observed, monitor closely', 'qc_park'),
            (1003, 1, 'functional', 'pass', NULL, 'Operating within normal parameters', 'qc_nguyen');
    """)
    print("✅ quality_checks:       4 rows inserted")

    # operator_notes - Shift notes and observations
    conn.execute("""
        INSERT INTO public.operator_notes (machine_id, ticket_id, order_id, note_type, content, created_by)
        VALUES
            (2, NULL, 1001, 'alert', 'Hearing unusual grinding noise from spindle during high-speed operation', 'operator_jones'),
            (3, 205, 1002, 'handoff', 'Shift handoff: conveyor belt realignment in progress, do not restart', 'tech_martinez'),
            (1, 102, NULL, 'resolution', 'Temperature sensors recalibrated, readings now within 0.5C tolerance', 'operator_jones');
    """)
    print("✅ operator_notes:       3 rows inserted")

    # ─── STEP 2: UPDATEs (Modify Existing Records) ───
    print("\n🔄 Simulating status updates (what happens when work is completed)...\n")

    # Mark maintenance action as completed
    conn.execute("""
        UPDATE public.maintenance_actions
        SET status = 'completed', completed_at = now()
        WHERE machine_id = 3 AND status = 'in_progress';
    """)
    print("✅ maintenance_actions:  Updated machine 3 action → completed")

    # Close work order
    conn.execute("""
        UPDATE public.work_orders
        SET status = 'closed'
        WHERE machine_id = 2 AND priority = 'high';
    """)
    print("✅ work_orders:          Updated spindle replacement → closed")

    # ─── STEP 3: DELETE (Remove Records) ───
    print("\n🗑️  Simulating a cancellation (DELETE operation)...\n")

    # Cancel low-priority work order
    conn.execute("""
        DELETE FROM public.work_orders
        WHERE priority = 'low' AND status = 'open';
    """)
    print("✅ work_orders:          Deleted 1 row (low priority, cancelled)")

print("\n" + "="*70)
print("✅ All operational writes complete!")
print("="*70)
print("\n🕒 Wait ~30 seconds for CDF to process these changes...")
print("\n📊 CDF will create history tables in Unity Catalog:")
print("   • lb_maintenance_actions_history")
print("   • lb_work_orders_history")
print("   • lb_quality_checks_history")
print("   • lb_operator_notes_history")
print("\n➡️  Run Cell 12 to verify the end-to-end pipeline")
```

### Step 12 — End-to-end verification

```python
# ─── Comprehensive status check ───
# Verifies the complete data pipeline from Lab1 source tables
# through Postgres synced/operational tables to CDF history tables

import psycopg

print("="*80)
print("🔍 LAB 2 - FINAL STATUS CHECK")
print("="*80)
print("\nVerifying the complete bidirectional data pipeline...")

# 1. Unity Catalog structure
print("\n[1] Unity Catalog Structure:")
print(f"\n  ✅ Catalog: {UC_CATALOG}")

try:
    schemas = spark.sql(f"SHOW SCHEMAS IN {UC_CATALOG}").collect()
    for s in schemas:
        schema_name = s.databaseName
        if schema_name == SCHEMA:
            print(f"    ├─ {SCHEMA} (Lab1 source tables)")
            try:
                tables = spark.sql(f"SHOW TABLES IN {UC_CATALOG}.{SCHEMA}").collect()
                if tables:
                    print(f"      └─ {len(tables)} table(s): {', '.join([t.tableName for t in tables[:4]])}")
                else:
                    print(f"      └─ ❌ NO TABLES - Run Lab1 first!")
            except:
                print(f"      └─ ❌ Schema doesn't exist yet - Run Lab1 first!")
        elif schema_name == LAKEBASE_SCHEMA:
            print(f"    ├─ {LAKEBASE_SCHEMA} (synced tables + CDF history)")
            try:
                tables = spark.sql(f"SHOW TABLES IN {UC_CATALOG}.{LAKEBASE_SCHEMA}").collect()
                if tables:
                    print(f"      └─ {len(tables)} table(s): {', '.join([t.tableName for t in tables])}")
                else:
                    print(f"      └─ (empty - synced tables may still be provisioning)")
            except:
                print(f"      └─ (not accessible)")
        elif schema_name == 'pipeline_storage':
            print(f"    ├─ pipeline_storage (sync metadata)")
except Exception as e:
    print(f"  ❌ Error: {str(e)[:100]}")

# 2. Lakebase Project
print(f"\n[2] Lakebase Postgres Project:")
if PROJECT:
    print(f"  ✅ Project: {PROJECT}")
    print(f"  ✅ Branch: {BRANCH}")
    print(f"  ✅ Endpoint: {ENDPOINT}")
    print(f"  ✅ Host: {host}")
    print(f"  ✅ Database: {PGDB}")
else:
    print(f"  ❌ Not created yet - run Cell 5")

# 3. Postgres Tables
if host:
    print(f"\n[3] Postgres Tables (public schema):")
    try:
        with psycopg.connect(
            host=host, port=5432, dbname=PGDB, user=user,
            password=pg_token(), sslmode="require", autocommit=True
        ) as conn:
            # Synced tables (read-only)
            synced = conn.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                  AND tablename IN ('machines', 'sensor_readings', 'production_orders', 'maintenance_tickets')
                ORDER BY tablename;
            """).fetchall()
            print(f"\n  Synced tables (read-only from UC):")
            if synced:
                for (tbl,) in synced:
                    count = conn.execute(f"SELECT COUNT(*) FROM public.{tbl}").fetchone()[0]
                    print(f"    ✅ {tbl:30s} ({count} rows)")
            else:
                print(f"    ❌ None synced yet - check sync status")
            
            # Operational tables (your app writes)
            operational = conn.execute("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                  AND tablename IN ('maintenance_actions', 'work_orders', 'quality_checks', 'operator_notes')
                ORDER BY tablename;
            """).fetchall()
            print(f"\n  Operational tables (app-owned, CDF-enabled):")
            if operational:
                for (tbl,) in operational:
                    count = conn.execute(f"SELECT COUNT(*) FROM public.{tbl}").fetchone()[0]
                    print(f"    ✅ {tbl:30s} ({count} rows)")
            else:
                print(f"    ❌ None created yet - run Cell 9")
    except Exception as e:
        print(f"  ❌ Could not connect: {str(e)[:100]}")

# 4. CDF Status
print(f"\n[4] Change Data Feed Status:")
try:
    cdf_tables = spark.sql(f"SHOW TABLES IN {UC_CATALOG}.{LAKEBASE_SCHEMA}").collect()
    history_tables = [t.tableName for t in cdf_tables if t.tableName.startswith('lb_') and t.tableName.endswith('_history')]
    if history_tables:
        print(f"  ✅ CDF is running! Found {len(history_tables)} history table(s):")
        for tbl in history_tables:
            count = spark.sql(f"SELECT COUNT(*) FROM {UC_CATALOG}.{LAKEBASE_SCHEMA}.{tbl}").collect()[0][0]
            print(f"    ✅ {tbl:40s} ({count} change events)")
    else:
        print(f"  ❌ No CDF history tables yet")
        print(f"     ➡️  Complete the manual step in Cell 10 to enable CDF")
except Exception as e:
    print(f"  ❌ Could not check: {str(e)[:100]}")

print("\n" + "="*80)
```

**✅ Check:** all four synced tables and all four operational tables show row counts, and the four
`lb_*_history` tables appear in `catalog_workshop.lakebase_{your_name}` with change events.

**💡 What just happened?**

- **Technically:** you stood up a full **bidirectional** bridge. `SNAPSHOT` synced tables gave
  Lakebase a read-only copy of your Delta reference data (UC → Lakebase). Four app-owned
  operational tables give the app somewhere to write. And **CDF** replays every write on those
  tables into Delta `lb_*_history` tables (Lakebase → UC) — a real change-data pipeline. Both the
  replicas and the history live in one schema, `catalog_workshop.lakebase_{your_name}`.
- **In the scenario:** the shop-floor app can now read reference data at millisecond latency *and*
  record what technicians do — and the data team sees each action land back in the lakehouse
  within seconds, ready for MTTR reporting and model retraining. That's the loop Labs 3 and 4
  exercise for real.

➡️ **Next: [Lab 3 – Build and Deploy the App](Lab%203%20-%20Build%20and%20Deploy%20the%20App.md).**
