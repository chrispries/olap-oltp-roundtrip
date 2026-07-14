# Concepts — read this first (10 min)

You already know databases. This primer maps that knowledge onto Lakebase + Databricks Apps
so the hands-on steps make sense instead of feeling like magic.

## The one-sentence idea

**Your analytical data lives in the lakehouse (Delta/Unity Catalog). Lakebase gives you a
real PostgreSQL database next to it; an app serves that data operationally; and because
Lakebase is registered in Unity Catalog, whatever the app writes is instantly queryable back
in SQL.** That loop — lakehouse → Postgres → app → back to lakehouse — is the whole workshop.

## The four pieces

| Piece | What it is | Your existing mental model |
|-------|------------|----------------------------|
| **Unity Catalog (UC) + Delta** | Governed analytical tables (columnar, great for scans/joins, not for single-row lookups) | A data warehouse / lakehouse |
| **Lakebase** | Fully-managed **PostgreSQL** (OLTP: fast single-row reads/writes, transactions) | A normal Postgres server, but serverless & scale-to-zero |
| **Synced table** | A **read-only** copy of a Delta table, continuously/one-time mirrored *into* Lakebase Postgres | A materialized replica / read replica |
| **Databricks App** | A container (here: Streamlit) that runs next to your data and talks to Lakebase over normal Postgres | A small web app with a Postgres connection |

## Why two tables? (the key insight)

Synced tables are **read-only** in Postgres — they're replicas of Delta, so you can't
`INSERT`/`UPDATE` them. So the app *reads* the seeded alerts from `maintenance_tickets` (a
synced table) but *writes* the technician's work — who claimed an alert and how they resolved
it — to its **own** ordinary Postgres table, `maintenance_actions`. An alert leaves the queue
once it has a resolution. That's a normal pattern: replicate reference data in, own your
transactional data.

## Why does the app's write show up in Databricks SQL? (the "round-trip")

When you run `databricks postgres create-catalog`, you **register the whole Lakebase
database as a Unity Catalog catalog**. UC then federates *every* table in that Postgres
database — including tables the app creates at runtime. So:

```
app writes resolution ──▶ Postgres public.maintenance_actions ──▶ (UC federation) ──▶
    SELECT ... FROM lakebase_ws_<you>.public.maintenance_actions   (Databricks SQL)
```

No pipeline, no ETL, no copy. The analyst sees the operational write **live**. (In
production you might *also* land it into Delta via CDC for long-term history — that's the
"approach B" talking point, not something we build.)

## How the app authenticates to Lakebase (don't skip this — it's the tricky bit)

Lakebase **Autoscaling** issues **short-lived (~1h) OAuth tokens**, not a fixed password. So:

1. You bind the app to the Lakebase database as a **`postgres` resource**. That provisions a
   **Postgres role for the app's service principal (SP)** and injects `DATABRICKS_CLIENT_ID`.
2. In `bundle/src/app/db.py`, `get_connection()` calls
   `w.postgres.generate_database_credential(ENDPOINT_NAME)` to **mint a fresh token per
   connection** and uses it as the Postgres password. The SP's client id is the Postgres
   username.
3. One gotcha: binding the resource lets the SP *connect and create*, but does **not** grant
   `SELECT` on the pre-existing synced tables — you grant that once (the runbook shows how).

That's the entire model. Now do it — start at [Lab 1](../labs/Lab%201%20-%20Generate%20Analytical%20Data.md).
