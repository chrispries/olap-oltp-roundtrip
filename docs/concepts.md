# Concepts — read this first (10 min)

You already know databases. This primer maps that knowledge onto Lakebase + Databricks Apps
so the hands-on steps make sense instead of feeling like magic.

## The one-sentence idea

**Your analytical data lives in the lakehouse (Delta/Unity Catalog). Lakebase gives you a
real PostgreSQL database next to it; an app serves that data operationally and writes back to
Postgres; and Change Data Feed streams those writes back into the lakehouse.** That loop —
lakehouse → Postgres → app → back to lakehouse — is the whole workshop.

## The five pieces

| Piece | What it is | Your existing mental model |
|-------|------------|----------------------------|
| **Unity Catalog (UC) + Delta** | Governed analytical tables (columnar, great for scans/joins, not for single-row lookups) | A data warehouse / lakehouse |
| **Lakebase** | Fully-managed **PostgreSQL** (OLTP: fast single-row reads/writes, transactions) | A normal Postgres server, but serverless & scale-to-zero |
| **Synced table** | A **read-only** copy of a Delta table mirrored *into* Lakebase Postgres (here a one-time `SNAPSHOT`; `CONTINUOUS` and `TRIGGERED` modes also exist) | A read replica of your reference data |
| **Change Data Feed (CDF)** | Streams every `INSERT`/`UPDATE`/`DELETE` on a Postgres table back into UC as an `lb_*_history` Delta table | Logical replication / CDC into your warehouse |
| **Databricks App** | A container (here: Streamlit) that runs next to your data and talks to Lakebase over normal Postgres | A small web app with a Postgres connection |

## Why two kinds of tables? (the key insight)

Everything lives in one Lakebase database (`databricks_postgres`), but there are two roles:

- **Reference tables** (`machines`, `sensor_readings`, `production_orders`, `maintenance_tickets`)
  are **synced tables** — read-only replicas of your Delta tables. The app *reads* these for
  context (which machine, what's the open ticket).
- **Operational tables** (`maintenance_actions`, `work_orders`, `quality_checks`, `operator_notes`)
  are ordinary Postgres tables **you own**. The app *writes* to these — the technician's actions,
  new work orders, inspection results, notes.

That's a normal pattern: replicate reference data in, own your transactional data.

## Why does the app's write show up in Databricks SQL? (the "round-trip")

You turn on **Change Data Feed (CDF)** on the operational tables. From then on, every change to
them is captured and streamed into Unity Catalog as a Delta table named `lb_<table>_history`:

```
app logs an action ──▶ Postgres public.maintenance_actions ──▶ (CDF, ~15s batches) ──▶
    SELECT ... FROM catalog_workshop.lakebase_<you>.lb_maintenance_actions_history   (Databricks SQL)
```

No bespoke connector, no manual ETL — CDF is the pipeline. The analyst sees each operational
write land in the lakehouse within seconds, as governed Delta, with full change history
(inserts, updates, and deletes).

> Everything lives in **one catalog**, `catalog_workshop`, across two schemas: **`schema_<you>`**
> holds your Lab 1 source Delta tables, and **`lakebase_<you>`** holds both the read-only synced
> reference tables *and* the `lb_*_history` CDF output. Don't confuse the two schemas.

## How the app authenticates to Lakebase (don't skip this — it's the tricky bit)

Lakebase **Autoscaling** issues **short-lived (~1h) OAuth tokens**, not a fixed password. So:

1. You bind the app to the Lakebase database as a **`postgres` resource**. That provisions a
   **Postgres role for the app's service principal (SP)** and injects `DATABRICKS_CLIENT_ID`.
2. In `bundle/src/app/db.py`, `get_connection()` calls
   `w.postgres.generate_database_credential(ENDPOINT_NAME)` to **mint a fresh token per
   connection** and uses it as the Postgres password. The SP's client id is the Postgres
   username.
3. One gotcha: binding the resource lets the SP *connect*, but does **not** grant read on the
   synced tables or write on the operational tables. You grant `pg_read_all_data`,
   `pg_write_all_data`, and sequence usage once (Lab 3, Step 3).

That's the entire model. Now do it — start at [Lab 1](../labs/Lab%201%20-%20Generate%20Analytical%20Data.md).
