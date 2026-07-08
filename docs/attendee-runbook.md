# Attendee Runbook — App + Lakebase in a Day

Everything you build uses **your own** per-user schema/database `ws_${user}`, where
`${user}` is the local-part of your email (lowercase, non-alphanumeric → `_`).
Example: `christopher.pries@databricks.com` → `ws_christopher_pries`.

## 1. Load data into Unity Catalog (~10 min)

1. Open the workspace and import this repo as a Git folder (facilitator provides the URL).
2. Open `data_gen/load_to_uc.py` and **Run all** on serverless.
3. Confirm the final cell prints `✅ All tables loaded into lakebase_workshop.ws_...`
   (counts: machines 50, sensor_readings 10000, production_orders 200, maintenance_tickets 120).

## 2. Sync to Lakebase (~15 min)

Follow [`../sync/create_lakebase.md`](../sync/create_lakebase.md) and
[`../sync/create_synced_tables.md`](../sync/create_synced_tables.md) to create your
per-user database and the four **snapshot** synced tables. Verify a read returns 50 machines.

## 3. Deploy the app (~15 min)

Deploy the Streamlit app in `app/` as `lakebase-workshop-${user}` (facilitator shows the
exact `databricks apps` commands). Open the app URL: you should see 50 machines and the
open tickets. Submitting the ticket form shows a "not implemented yet" warning — that's the
gap you fill next.

## 4. Implement the write-back (~20 min — the payoff)

Open `app/db.py` and complete `create_maintenance_ticket()` (marked `TODO (workshop)`):
insert one row into `app_maintenance_tickets` and return the new `ticket_id`
(`INSERT ... RETURNING ticket_id`, then commit). Redeploy, then create a ticket in the app.
Stuck? The answer is in [`solutions/create_maintenance_ticket.py`](solutions/create_maintenance_ticket.py).

## 5. Close the round-trip (~15 min)

In Databricks SQL, run [`../analytics/roundtrip_query.sql`](../analytics/roundtrip_query.sql)
(substitute your Lakebase catalog + `ws_${user}`). Your just-created ticket appears — the
app's write is now live in the analytical layer. 🎉
