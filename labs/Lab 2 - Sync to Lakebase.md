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

### Step 1 — Run the Lakebase setup notebook

1. Open [`bundle/src/notebooks/create_lakebase.py`](../bundle/src/notebooks/create_lakebase.py).
2. **Run all** on serverless. (Its first cell does `%pip install -U databricks-sdk` and restarts
   Python — the workspace's default SDK predates the Lakebase API.)

It runs three steps against the shared project, all keyed to your own `ws_<user>` names:

```python
# 1) create your Postgres database  (psql: CREATE DATABASE ws_<user>)
# 2) register it in Unity Catalog
w.postgres.create_catalog(Catalog.from_dict(
    {"spec": {"postgres_database": PGDB, "branch": BRANCH}}), catalog_id=LBCAT)
# 3) one SNAPSHOT synced table per Delta table
w.postgres.create_synced_table(SyncedTable.from_dict({"spec": {
    "source_table_full_name": f"{UC_CATALOG}.{SCHEMA}.{tbl}",
    "primary_key_columns": [pk], "scheduling_policy": "SNAPSHOT",
    "branch": BRANCH, "postgres_database": PGDB,
    "create_database_objects_if_missing": True,
    "new_pipeline_spec": {"storage_catalog": UC_CATALOG, "storage_schema": "pipeline_storage"}}}),
    synced_table_id=f"{LBCAT}.public.{tbl}")
```

Each synced table spins up a short snapshot pipeline (~2–4 min).

**💡 What just happened?**
- **Snapshot** = a one-time copy of your Delta table into Postgres. (Continuous sync exists too;
  snapshot keeps the workshop simple.)
- Registering the database as UC catalog `lakebase_ws_<user>` means UC now federates the *whole*
  Postgres database — including tables your app will create later. That's the "back to
  analytics" leg of the round-trip, for free.

### Step 2 — Verify from the analytical side

Run in the SQL Editor (substitute your user):

```sql
SELECT count(*) FROM lakebase_ws_<your_user>.public.machines;   -- 50
```

**✅ Check:** you get `50`. That query reads Postgres data **through Unity Catalog** — proof
the federation works before you've even built the app.

> **Prefer the UI or laptop CLI?** In the UI: *Compute ▸ Database instances ▸ `lakebase-workshop`*
> to create a database, then *Catalog Explorer ▸ Create ▸ Synced table* (Snapshot) per Delta
> table. The exact `databricks postgres …` CLI commands are in the last cell of the notebook.

➡️ **Next: [Lab 3 – Build and Deploy the App](Lab%203%20-%20Build%20and%20Deploy%20the%20App.md).**
