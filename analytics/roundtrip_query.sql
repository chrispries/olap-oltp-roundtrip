-- Close the round-trip: read the app's write-back from the analytical layer.
--
-- The Lakebase instance is registered in Unity Catalog, so the app-owned Postgres table
-- app_maintenance_tickets is queryable live from Databricks SQL. Create a ticket in the
-- deployed app, then run this — the new ticket appears here.
--
-- Replace <lakebase_catalog> with the catalog name recorded in sync/create_synced_tables.md
-- and ws_<user> with your per-user schema/database.

SELECT
    ticket_id,
    machine_id,
    priority,
    status,
    description,
    opened_at
FROM <lakebase_catalog>.ws_<user>.app_maintenance_tickets
ORDER BY opened_at DESC;
