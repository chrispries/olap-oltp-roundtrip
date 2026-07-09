# Step 02 · Create Lakebase + synced tables (CLI)

Mirror your Unity Catalog data (from step 01) into a Lakebase Postgres database, and register
it in UC so it's queryable from SQL. This is infrastructure — you drive it with the
`databricks` CLI. Every command has a **✅ Check**.

**Prereqs:** Databricks CLI ≥ 0.298 authenticated (this guide uses profile `azure-demo`);
`psql` (`brew install postgresql@16`); the shared project `lakebase-workshop` exists.

## Setup — your variables (run once per terminal)

These derive your own per-user names so you never collide in the shared project. **Steps 02,
03, and the CLI parts of 04 all reuse these**, so set them here first.

```bash
export P=azure-demo
export EMAIL=$(databricks -p $P current-user me -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['userName'])")
export USER_SLUG=$(echo "${EMAIL%@*}" | tr -c 'a-z0-9' '_' | sed 's/_*$//')   # e.g. christopher_pries
export CATALOG=lakebase_workshop                       # UC catalog holding the Delta data (step 01)
export SCHEMA=ws_$USER_SLUG                            # your UC schema
export PGDB=ws_$USER_SLUG                              # your Lakebase (Postgres) database
export LBCAT=lakebase_ws_$USER_SLUG                    # your Lakebase→UC catalog
export BRANCH=projects/lakebase-workshop/branches/production
export ENDPOINT=$BRANCH/endpoints/primary
export APP=lb-workshop-$(echo $USER_SLUG | tr '_' '-' | cut -c1-14)
export HOST=$(databricks -p $P postgres list-endpoints $BRANCH -o json | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['status']['hosts']['host'])")
echo "EMAIL=$EMAIL  SCHEMA=$SCHEMA  PGDB=$PGDB  LBCAT=$LBCAT  APP=$APP  HOST=$HOST"
```
**✅ Check:** the echo prints your names and a real `HOST`.

*Running solo (no facilitator)?* Create the shared project once:
`databricks -p $P postgres create-project lakebase-workshop --json '{"spec":{"display_name":"App + Lakebase in a Day"}}'`

## 02.1 · Create your Postgres database

```bash
TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=postgres user=$EMAIL sslmode=require" -c "CREATE DATABASE $PGDB;"
```
**✅ Check:** prints `CREATE DATABASE`. (OAuth tokens last ~1h; re-run the `TOKEN=` line if you
later hit an auth error.)

*Why:* synced tables and your app's tables live inside a Postgres database you own.

## 02.2 · Register your database as a Unity Catalog catalog

```bash
databricks -p $P postgres create-catalog $LBCAT --json "{\"spec\":{\"postgres_database\":\"$PGDB\",\"branch\":\"$BRANCH\"}}"
```
**✅ Check:** returns `catalogs/lakebase_ws_...`.

*Why:* this is what makes the round-trip work — UC now federates your whole Postgres DB, so
anything in it (including tables the app creates later) is queryable from Databricks SQL.

## 02.3 · Create the snapshot synced tables

One-time metadata schema for the sync pipelines, then one SNAPSHOT synced table per Delta table:

```bash
WH=$(databricks -p $P warehouses list -o json | python3 -c "import sys,json;print([w['id'] for w in json.load(sys.stdin) if w['state']=='RUNNING'][0])")
databricks -p $P api post /api/2.0/sql/statements --json "{\"warehouse_id\":\"$WH\",\"statement\":\"CREATE SCHEMA IF NOT EXISTS $CATALOG.pipeline_storage\",\"wait_timeout\":\"30s\"}" >/dev/null

mk() { databricks -p $P postgres create-synced-table $LBCAT.public.$1 --no-wait --json \
  "{\"spec\":{\"source_table_full_name\":\"$CATALOG.$SCHEMA.$1\",\"primary_key_columns\":[\"$2\"],\"scheduling_policy\":\"SNAPSHOT\",\"branch\":\"$BRANCH\",\"postgres_database\":\"$PGDB\",\"create_database_objects_if_missing\":true,\"new_pipeline_spec\":{\"storage_catalog\":\"$CATALOG\",\"storage_schema\":\"pipeline_storage\"}}}" >/dev/null && echo "queued $1"; }
mk machines machine_id
mk sensor_readings reading_id
mk production_orders order_id
mk maintenance_tickets ticket_id
```
Each spins up a DLT snapshot pipeline (~2–4 min).

## 02.4 · Verify

```bash
TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=$PGDB user=$EMAIL sslmode=require" -tc \
  "SELECT 'machines',count(*) FROM public.machines UNION ALL SELECT 'sensor_readings',count(*) FROM public.sensor_readings;"
```
**✅ Check:** `machines 50`, `sensor_readings 10000`. And the analytics path already works:
```bash
databricks -p $P api post /api/2.0/sql/statements --json "{\"warehouse_id\":\"$WH\",\"statement\":\"SELECT count(*) FROM $LBCAT.public.machines\",\"wait_timeout\":\"30s\"}"
```
→ 50.

➡️ **Next: [step 03 — deploy the app](../docs/03_deploy_app.md).**
