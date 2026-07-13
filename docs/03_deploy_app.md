# Step 03 · Deploy the app + implement the write-back (CLI)

Deploy the Streamlit app that serves your Lakebase data, then complete the one function that
writes new tickets back. Reuses the variables you set in
[step 02's Setup](../sync/02_create_lakebase.md#setup--your-variables-run-once-per-terminal)
(`$P`, `$EMAIL`, `$PGDB`, `$LBCAT`, `$BRANCH`, `$ENDPOINT`, `$APP`, `$HOST`).

## 03.1 · Understand the app (this is what you're here to learn)

Two files in [`../app/`](../app):

- **`app.yaml`** — how a Databricks App is configured: `command` runs Streamlit on port 8000;
  `env` passes the Lakebase coordinates. Note there's **no password** — see `db.py`.
- **`db.py`** — `get_connection()` mints a **fresh OAuth token per connection** with
  `w.postgres.generate_database_credential(ENDPOINT_NAME)` (Autoscaling tokens are short-lived).
  `open_alerts`/`claim_alert` drive the alert queue; `resolve_alert` (03.3) writes the
  resolution. `PGUSER` is left unset so the app uses its own service-principal id.

Edit `app/app.yaml`: set `PGDATABASE` to **your** `$PGDB`.

## 03.2 · Create, bind, and deploy

```bash
# find YOUR database's resource id (not the human name) so we can bind it
DBRES=$(databricks -p $P postgres list-databases $BRANCH -o json | python3 -c "import sys,json;print([d['name'] for d in json.load(sys.stdin) if d['status']['postgres_database']=='$PGDB'][0])")
echo "resource=$DBRES"

cat > /tmp/app-create.json <<JSON
{ "name": "$APP",
  "description": "Lakebase-in-a-Day: shop-floor maintenance app",
  "resources": [ { "name": "lakebase-db",
    "postgres": { "branch": "$BRANCH", "database": "$DBRES", "permission": "CAN_CONNECT_AND_CREATE" } } ] }
JSON
databricks -p $P apps create --json @/tmp/app-create.json --no-wait

WS=/Workspace/Users/$EMAIL/$APP
databricks -p $P sync ./app $WS --full
databricks -p $P apps deploy $APP --source-code-path $WS
```
**✅ Check:** deploy prints `{"state":"SUCCEEDED","message":"App started successfully"}`. Get the
URL: `databricks -p $P apps get $APP -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['url'])"`.
Open it — **Machines shows 50 rows**; the ticket form shows a "not implemented yet" warning
(expected — that's 03.3).

> **If Machines is empty / permission error:** binding the resource lets the app connect and
> create, but not `SELECT` the pre-existing synced tables. Grant it once (SP id from
> `databricks -p $P apps get $APP -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['service_principal_client_id'])"`):
> ```bash
> SP=<that-client-id>
> TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
> PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=$PGDB user=$EMAIL sslmode=require" -c \
>   "GRANT USAGE, CREATE ON SCHEMA public TO \"$SP\"; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"$SP\";"
> ```
> Reload the app.

## 03.3 · Implement the write-back (the payoff)

Open `app/db.py`, find `resolve_alert()` (it raises `NotImplementedError`). Replace the body so
it writes the resolution into `ACTIONS_TABLE`:

1. `INSERT` `(ticket_id, machine_id, technician, resolution)` with `status = 'resolved'` and `resolved_at = now()`,
2. `ON CONFLICT (ticket_id) DO UPDATE` (ticket_id is UNIQUE — resolving an already-claimed alert updates its row),
3. `conn.commit()`.

Try it from the docstring hints. Stuck / want to check? Full answer:
[`solutions/resolve_alert.py`](solutions/resolve_alert.py) (the single source for the solution).
Redeploy:

```bash
databricks -p $P sync ./app $WS --full && databricks -p $P apps deploy $APP --source-code-path $WS
```
**✅ Check:** in the app, **claim** a flagged alert and **resolve** it with a note — it drops off
the active queue and appears under "Recently resolved".

➡️ **Next: [step 04 — explore + round-trip](../notebooks/04_explore_and_roundtrip.py).**
