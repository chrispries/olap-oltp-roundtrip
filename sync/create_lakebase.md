# Create the shared Lakebase instance + per-user database

Lakebase **Autoscaling** tier (`databricks postgres`, scale-to-zero). Tested on Azure FE
(`azure-demo`) 2026-07-08.

## Instance / project (facilitator, once)

One shared Autoscaling **project** for the whole room:

```bash
databricks -p azure-demo postgres create-project lakebase-workshop \
  --json '{"spec": {"display_name": "App + Lakebase in a Day workshop"}}'
```

This auto-creates a `production` branch and a `primary` read-write endpoint. Get the host:

```bash
databricks -p azure-demo postgres list-endpoints \
  projects/lakebase-workshop/branches/production -o json \
  | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['status']['hosts']['host'])"
# e.g. ep-floral-rain-e1f9l6le.database.eastus2.azuredatabricks.net
```

## Per-user database (each attendee)

Each attendee gets their own Postgres **database** `ws_${user}` on the shared endpoint.
Create it once with psql (needs `brew install postgresql@16`):

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
HOST=$(databricks -p azure-demo postgres list-endpoints projects/lakebase-workshop/branches/production -o json | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['status']['hosts']['host'])")
TOKEN=$(databricks -p azure-demo postgres generate-database-credential projects/lakebase-workshop/branches/production/endpoints/primary -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
EMAIL=$(databricks -p azure-demo current-user me -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['userName'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=postgres user=$EMAIL sslmode=require" \
  -c "CREATE DATABASE ws_christopher_pries;"   # substitute your ws_${user}
```

## Connection recipe (app + write-back test)

- Host: from `list-endpoints` (above)
- Port: `5432`
- Database: `ws_${user}`
- User: your Databricks email (`current-user me`)
- Password: **short-lived OAuth token** from
  `databricks postgres generate-database-credential .../endpoints/primary` (expires ~1h)
- `sslmode=require`

The deployed app gets these injected by the bound Lakebase resource (see
`../app/app.yaml` and the databricks-apps skill).
