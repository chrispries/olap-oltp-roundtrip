-- Close the round-trip: read the technician's work from the analytical layer.
--
-- The Lakebase database is registered in Unity Catalog as catalog `lakebase_ws_<user>`,
-- which federates the WHOLE Postgres database. So the app-owned table `maintenance_actions`
-- (claims + resolutions written by the Maintenance Cockpit app) is queryable live from
-- Databricks SQL. Claim/resolve an alert in the app, then run this — the action appears.
--
-- Replace `christopher_pries` with your own ws user. Schema is always `public`.

SELECT
    machine_id,
    technician,
    status,
    resolution,
    claimed_at,
    resolved_at
FROM lakebase_ws_christopher_pries.public.maintenance_actions
ORDER BY COALESCE(resolved_at, claimed_at) DESC;
