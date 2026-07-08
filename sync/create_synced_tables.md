# Create the snapshot synced tables

> Filled in during the live Azure FE build (Task 3) using the
> `fe-databricks-tools:databricks-lakebase` skill for exact current commands.

Create one **SNAPSHOT** synced table per Delta table, from
`lakebase_workshop.ws_${user}.<table>` into the per-user Lakebase database `ws_${user}`:

| Source Delta table | Synced table (Postgres) | Mode |
|--------------------|-------------------------|------|
| `machines` | `machines` | SNAPSHOT |
| `sensor_readings` | `sensor_readings` | SNAPSHOT |
| `production_orders` | `production_orders` | SNAPSHOT |
| `maintenance_tickets` | `maintenance_tickets` | SNAPSHOT |

Steps (UI + CLI): _to be recorded during live build_

## Lakebase catalog name in Unity Catalog

The Lakebase instance registers as a UC catalog. Record its exact name here — the
round-trip query (`analytics/roundtrip_query.sql`) reads
`<lakebase_catalog>.ws_${user}.app_maintenance_tickets`.

- Lakebase UC catalog name: _to be recorded_
