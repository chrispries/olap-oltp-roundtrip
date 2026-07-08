# Attendee Runbook — App + Lakebase in a Day

Do this yourself, start to finish. Read [`concepts.md`](concepts.md) first (10 min) so the
steps mean something. Every step has a **✅ Check** so you know you're on track.

> New to the mental model? The loop you're building is:
> **UC Delta → synced tables in Lakebase → Streamlit app reads → app writes its own PG table
> → that write is queryable back in Databricks SQL.**

## Prerequisites

- **Databricks CLI** ≥ 0.298 authenticated to the workshop workspace. This guide uses
  profile `azure-demo` — swap in yours. Test: `databricks -p azure-demo current-user me`.
- **psql** (to create your database): `brew install postgresql@16` then
  `export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"`.
- **The shared Lakebase project `lakebase-workshop` already exists** (your facilitator created
  it). Running solo? Create it once yourself:
  `databricks -p azure-demo postgres create-project lakebase-workshop --json '{"spec":{"display_name":"App + Lakebase in a Day"}}'`

## Step 0 — Set your variables (once per terminal)

Everything below reuses these. `ME` derives your per-user names so you never collide with
someone else in the shared project.

```bash
export P=azure-demo
export EMAIL=$(databricks -p $P current-user me -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['userName'])")
export USER_SLUG=$(echo "${EMAIL%@*}" | tr -c 'a-z0-9' '_' | sed 's/_*$//')   # e.g. christopher_pries
export CATALOG=lakebase_workshop                       # regular UC catalog for the Delta data
export SCHEMA=ws_$USER_SLUG                            # your UC schema
export PGDB=ws_$USER_SLUG                              # your Lakebase (Postgres) database
export LBCAT=lakebase_ws_$USER_SLUG                    # your Lakebase→UC catalog
export BRANCH=projects/lakebase-workshop/branches/production
export ENDPOINT=$BRANCH/endpoints/primary
export APP=lb-workshop-$(echo $USER_SLUG | tr '_' '-' | cut -c1-14)   # app name (lowercase/hyphens, short)
export HOST=$(databricks -p $P postgres list-endpoints $BRANCH -o json | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['status']['hosts']['host'])")
echo "EMAIL=$EMAIL  SCHEMA=$SCHEMA  PGDB=$PGDB  LBCAT=$LBCAT  APP=$APP  HOST=$HOST"
```
**✅ Check:** the echo prints your names (e.g. `SCHEMA=ws_christopher_pries`) and a real `HOST`.

## Step 1 — Load analytical data into Unity Catalog (~10 min)

Import this repo into the workspace (Git folder) and open the **notebook**
[`notebooks/01_generate_data`](../notebooks/01_generate_data.py). Run it cell by cell — it
walks you through the data model, generates the four tables, writes them as Delta, and
verifies the counts. (New here? Start at [`notebooks/00_start_here`](../notebooks/00_start_here.py).)

**✅ Check:** the verify cell prints `✅ All four tables loaded into lakebase_workshop.ws_...`
(machines 50, sensor_readings 10000, production_orders 200, maintenance_tickets 120).

*Why:* this is the "analytical data you already have" — the starting point of the story.

## Step 2 — Create your Lakebase (Postgres) database (~3 min)

```bash
TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=postgres user=$EMAIL sslmode=require" -c "CREATE DATABASE $PGDB;"
```
**✅ Check:** prints `CREATE DATABASE`. (Tokens last ~1h; re-run the `TOKEN=` line if you get
an auth error later.)

*Why:* synced tables and your app's tables live inside a Postgres database you own.

## Step 3 — Register your database as a Unity Catalog catalog (~1 min)

```bash
databricks -p $P postgres create-catalog $LBCAT --json "{\"spec\":{\"postgres_database\":\"$PGDB\",\"branch\":\"$BRANCH\"}}"
```
**✅ Check:** returns `catalogs/lakebase_ws_...`.

*Why:* this is what makes the round-trip work — UC now federates your whole Postgres DB, so
anything in it is queryable from Databricks SQL.

## Step 4 — Create the snapshot synced tables (~5 min)

One-time schema for the sync pipelines' metadata, then one SNAPSHOT synced table per Delta table:

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
Each spins up a DLT snapshot pipeline (~2–4 min). Verify from Postgres:
```bash
TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=$PGDB user=$EMAIL sslmode=require" -tc \
  "SELECT 'machines',count(*) FROM public.machines UNION ALL SELECT 'sensor_readings',count(*) FROM public.sensor_readings;"
```
**✅ Check:** `machines 50`, `sensor_readings 10000`. Also confirm the analytics path already
works: `databricks -p $P api post /api/2.0/sql/statements --json "{\"warehouse_id\":\"$WH\",\"statement\":\"SELECT count(*) FROM $LBCAT.public.machines\",\"wait_timeout\":\"30s\"}"` → 50.

*Why:* your Delta data is now serving from Postgres at low latency, and readable both from
the app (Postgres) and from SQL (UC).

## Step 5 — Understand, then deploy the app (~15 min)

**Read the app first — this is the part you're here to learn.** Two files matter:

- **`app/app.yaml`** — how a Databricks App is configured. `command` runs Streamlit on
  port 8000. `env` passes the Lakebase coordinates. Note there's no password — see db.py.
- **`app/db.py`** — `get_connection()` mints a **fresh OAuth token per connection** with
  `w.postgres.generate_database_credential(ENDPOINT_NAME)` (Autoscaling tokens are short-lived).
  `list_machines`/`open_tickets` read the synced tables; `create_maintenance_ticket` (Step 6)
  writes your own table. `PGUSER` is left unset so the app uses its own service-principal id.

Edit `app/app.yaml`: set `PGDATABASE` to **your** `$PGDB`. Then create + bind + deploy:

```bash
# 1) create the app, binding the Lakebase DB as a `postgres` resource.
#    First find YOUR database's resource id (not the human name):
DBRES=$(databricks -p $P postgres list-databases $BRANCH -o json | python3 -c "import sys,json;print([d['name'] for d in json.load(sys.stdin) if d['status']['postgres_database']=='$PGDB'][0])")
echo "resource=$DBRES"
cat > /tmp/app-create.json <<JSON
{ "name": "$APP",
  "description": "Lakebase-in-a-Day: shop-floor maintenance app",
  "resources": [ { "name": "lakebase-db",
    "postgres": { "branch": "$BRANCH", "database": "$DBRES", "permission": "CAN_CONNECT_AND_CREATE" } } ] }
JSON
databricks -p $P apps create --json @/tmp/app-create.json --no-wait

# 2) sync the app/ folder to your workspace, then deploy
WS=/Workspace/Users/$EMAIL/$APP
databricks -p $P sync ./app $WS --full
databricks -p $P apps deploy $APP --source-code-path $WS
```
**✅ Check:** deploy prints `{"state":"SUCCEEDED","message":"App started successfully"}`.
Get the URL: `databricks -p $P apps get $APP -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['url'])"`.

Open it — **Machines shows 50 rows**, Open tickets renders. Submitting the ticket form shows a
"not implemented yet (Step 6)" warning. That's expected — the write-back is your job next.

> **If Machines is empty / permission error:** binding the resource lets the app connect and
> create, but not `SELECT` the pre-existing synced tables. Grant it once (SP id = the app's
> `DATABRICKS_CLIENT_ID`, shown by `databricks -p $P apps get $APP -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['service_principal_client_id'])"`):
> ```bash
> SP=<that-client-id>
> TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
> PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=$PGDB user=$EMAIL sslmode=require" -c \
>   "GRANT USAGE, CREATE ON SCHEMA public TO \"$SP\"; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"$SP\";"
> ```
> Reload the app.

## Step 6 — Implement the write-back (the payoff, ~15 min)

Open `app/db.py`, find `create_maintenance_ticket()` (it raises `NotImplementedError`). Replace
the body so it inserts a row and returns the new id:

```python
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {APP_TABLE} (machine_id, priority, description) "
            f"VALUES (%s, %s, %s) RETURNING ticket_id",
            (machine_id, priority, description),
        )
        ticket_id = cur.fetchone()[0]
    conn.commit()
    return ticket_id
```
Redeploy: `databricks -p $P sync ./app $WS --full && databricks -p $P apps deploy $APP --source-code-path $WS`.
Stuck? Full answer: [`solutions/create_maintenance_ticket.py`](solutions/create_maintenance_ticket.py).

**✅ Check:** in the app, create a ticket (machine 7, high, "vibration alarm") → you see
`Created ticket #N`, and it appears under Open tickets.

## Step 7 — Close the round-trip (~10 min) 🎉

The ticket you just created in the **app** is now in Postgres. Read it from the **analytical
layer** — the friendliest way is the notebook
[`notebooks/04_explore_and_roundtrip`](../notebooks/04_explore_and_roundtrip.py) (explore the
synced tables, then re-run the round-trip cell after creating a ticket). Or from the CLI —
edit `analytics/roundtrip_query.sql` to use your `$LBCAT`, or run:
```bash
databricks -p $P api post /api/2.0/sql/statements --json \
  "{\"warehouse_id\":\"$WH\",\"statement\":\"SELECT ticket_id,machine_id,priority,status,description FROM $LBCAT.public.app_maintenance_tickets ORDER BY opened_at DESC\",\"wait_timeout\":\"30s\"}"
```
**✅ Check:** your ticket is in the result. **That's the round-trip: an app write, live in the
lakehouse, with no pipeline.** (Optional: build the AI/BI dashboard in `analytics/dashboard.md`.)

## Step 8 — Teardown (avoid lingering cost)

```bash
databricks -p $P apps delete $APP
databricks -p $P postgres delete-catalog $LBCAT
# drop your synced tables + database:
for t in machines sensor_readings production_orders maintenance_tickets; do databricks -p $P postgres delete-synced-table $LBCAT.public.$t; done
TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=postgres user=$EMAIL sslmode=require" -c "DROP DATABASE $PGDB;"
# optional (facilitator only): databricks -p $P postgres delete-project projects/lakebase-workshop
```
The shared Lakebase project scales to zero when idle, so leaving it between sessions is cheap.
