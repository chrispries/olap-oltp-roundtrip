# Register the Lakebase catalog + create snapshot synced tables

Tested on Azure FE (`azure-demo`) 2026-07-08. Order matters: **register the UC catalog
first**, then create synced tables.

## 1. Register the Lakebase database as a UC catalog (once per database)

```bash
databricks -p azure-demo postgres create-catalog lakebase_ws_christopher_pries \
  --json '{"spec":{"postgres_database":"ws_christopher_pries","branch":"projects/lakebase-workshop/branches/production"}}'
```

- Catalog name `lakebase_ws_${user}` encodes the attendee (federates the whole Postgres
  database, so app-created tables like `app_maintenance_tickets` are queryable too).
- The catalog's **schema is the Postgres schema** — synced tables land in `public`.

## 2. Create a storage schema for the sync pipelines (once)

```bash
databricks -p azure-demo api post /api/2.0/sql/statements --json \
  '{"warehouse_id":"<WH_ID>","statement":"CREATE SCHEMA IF NOT EXISTS lakebase_workshop.pipeline_storage","wait_timeout":"30s"}'
```

## 3. Create the four SNAPSHOT synced tables

Synced table ID = `<lakebase_catalog>.public.<table>`; source = the Delta table.

```bash
mk() { local tbl=$1 pk=$2
  databricks -p azure-demo postgres create-synced-table lakebase_ws_christopher_pries.public.$tbl \
    --json "{\"spec\":{\"source_table_full_name\":\"lakebase_workshop.ws_christopher_pries.$tbl\",\"primary_key_columns\":[\"$pk\"],\"scheduling_policy\":\"SNAPSHOT\",\"branch\":\"projects/lakebase-workshop/branches/production\",\"postgres_database\":\"ws_christopher_pries\",\"create_database_objects_if_missing\":true,\"new_pipeline_spec\":{\"storage_catalog\":\"lakebase_workshop\",\"storage_schema\":\"pipeline_storage\"}}}"
}
mk machines machine_id
mk sensor_readings reading_id
mk production_orders order_id
mk maintenance_tickets ticket_id
```

Each kicks off a DLT snapshot pipeline (~2-4 min to spin up).

## 4. Verify

Via Postgres:
```bash
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=ws_christopher_pries user=$EMAIL sslmode=require" \
  -tc "SELECT 'machines',count(*) FROM public.machines UNION ALL SELECT 'sensor_readings',count(*) FROM public.sensor_readings UNION ALL SELECT 'production_orders',count(*) FROM public.production_orders UNION ALL SELECT 'maintenance_tickets',count(*) FROM public.maintenance_tickets;"
# expect 50 / 10000 / 200 / 120
```

Via Databricks SQL (the "back to analytics" path):
```sql
SELECT count(*) FROM lakebase_ws_christopher_pries.public.machines;  -- 50
```

## Lakebase UC catalog name (used by the round-trip query)

- **Catalog:** `lakebase_ws_${user}` · **schema:** `public`
- Round-trip target: `lakebase_ws_${user}.public.app_maintenance_tickets`
