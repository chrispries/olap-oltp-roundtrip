# Create the shared Lakebase instance + per-user database

> Filled in during the live Azure FE build (Task 3) using the
> `fe-databricks-tools:databricks-lakebase` skill for exact current commands.

## Instance (facilitator, once)

- Instance name: `lakebase-workshop`
- Workspace: Azure FE (`azure-demo`)
- Steps (UI + CLI): _to be recorded during live build_

## Per-user database (each attendee)

- Database name: `ws_${user}` (sanitized email local-part)
- Steps: _to be recorded_

## Connection recipe (used by the app and the write-back test)

The deployed app receives `PGHOST` / `PGPORT` / `PGDATABASE` / `PGUSER` / `PGPASSWORD`
from the bound Lakebase resource. For manual/notebook connections, record here how to
obtain a short-lived OAuth token and the host/port/database values.

- Host: _to be recorded_
- Port: `5432`
- Auth: _OAuth token via databricks-lakebase skill — to be recorded_
