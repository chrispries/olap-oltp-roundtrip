-- Close the round-trip: read the app's write-back from the analytical layer.
--
-- The Lakebase database is registered in Unity Catalog as catalog `lakebase_ws_<user>`,
-- which federates the WHOLE Postgres database. So the app-owned table
-- `app_maintenance_tickets` (created by the app, not a synced table) is queryable live
-- from Databricks SQL. Create a ticket in the deployed app, then run this — it appears.
--
-- Replace `christopher_pries` with your own ws user. Schema is always `public`.

SELECT
    ticket_id,
    machine_id,
    priority,
    status,
    description,
    opened_at
FROM lakebase_ws_christopher_pries.public.app_maintenance_tickets
ORDER BY opened_at DESC;
