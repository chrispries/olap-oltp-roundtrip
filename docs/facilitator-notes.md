# Facilitator Notes

## Prerequisites

- Attendees have access to the Azure FE workspace (`azure-demo`) with permission to create
  schemas in `lakebase_workshop`, deploy apps, and use serverless + a SQL warehouse.
- Facilitator pre-creates the shared Lakebase instance `lakebase-workshop` **before** the
  session (provisioning takes minutes — don't do it live).
- Repo available to import as a workspace Git folder.

## Pre-provisioning checklist (facilitator, day before)

- [ ] Create Lakebase instance `lakebase-workshop`, record host/catalog in `sync/*.md`.
- [ ] **Run `bundle/src/notebooks/admin_setup.py` (workspace admin)** — creates the participant group and grants
      workspace/SQL entitlements, UC `USE CATALOG`+`CREATE SCHEMA`, `CREATE CATALOG` on metastore,
      and warehouse `CAN_USE`. See [`roles-and-permissions.md`](roles-and-permissions.md).
- [ ] Grant the participant group access to the Lakebase project + confirm Apps creation is
      allowed (the two manual steps `admin_setup.py` prints).
- [ ] Run the full attendee flow once as a **non-admin** test user (pre-flight, see roles doc).

## Per-user namespacing (9–20 attendees)

- Each attendee: UC schema `lakebase_workshop.ws_${user}`, Lakebase database `ws_${user}`,
  app `lakebase-workshop-${user}`. Derivation shown in the attendee runbook.
- One shared Lakebase **instance**; isolation is by per-user database.

## Timing (target 90 min)

| Segment | Budget |
|---------|--------|
| Intro + architecture | 10 |
| Load → UC | 10 |
| Lakebase + synced tables | 15 |
| Deploy app | 15 |
| Write-back (payoff) | 20 |
| Round-trip query | 15 |
| Productionization + wrap | 5 |

Actual dry-run timings: _recorded in Task 8_.

## Common failure modes

- **`insufficientPrivilege` when opening the app** — the app SP lacks `SELECT` on a synced
  table (Postgres denies the read → psycopg raises `InsufficientPrivilege`). Notebook 03 grants
  `pg_read_all_data` to the SP, which covers all current **and future** tables (survives a
  re-sync, unlike a one-time `GRANT SELECT`). Full breakdown of every role/right:
  [`roles-and-permissions.md`](roles-and-permissions.md).
- **Data generation** — lives only in `bundle/src/notebooks/generate_data` (self-contained, no repo
  import needed). It is the single source for the synthetic data.
- **App auth (Autoscaling)** — do NOT use a static `PGPASSWORD`. `bundle/src/app/db.py` mints a fresh
  OAuth token per connection via `w.postgres.generate_database_credential(ENDPOINT_NAME)`.
  `ENDPOINT_NAME`, `PGHOST`, `PGDATABASE`, `PGUSER` (= SP client id) are set in `bundle/src/app/app.yaml`.
- **Local `pip install` fails** — expected; this repo is built/tested **on Databricks**, not
  locally (public PyPI is firewalled). Use the notebooks, not a local venv.
- **Snapshot sync shows stale data** — snapshot is one-time; re-create/refresh the synced
  table if the source changed. (Continuous sync is the production answer — talking point.)

## Validated live (Azure FE `azure-demo`)

The full round-trip was built and verified on the `ws_christopher_pries` namespace:
data load (50/10000/200/120) → Lakebase project `lakebase-workshop` + 4 snapshot synced
tables → UC catalog `lakebase_ws_christopher_pries` → deployed Streamlit app → technician
resolves an alert (write to `public.maintenance_actions`) → read it back from Databricks SQL.
Round-trip closed.

- **Reference app (facilitator, write-back already solved):**
  https://lb-workshop-christopher-pries-984752964297111.11.azure.databricksapps.com
- **Repo ships the write-back stubbed** (`resolve_alert`, the attendee gap). The deployed
  reference app runs the completed version; that divergence is intentional. Answer key:
  `labs/artifacts/solutions/resolve_alert.py`.

## Productionization talking point (approach B)

The workshop uses live UC-query of the Lakebase table (approach A). In production you might
add a triggered CDC/Lakeflow job to land app writes into a Delta table for long-term
analytics. Mention it; don't build it.

## Teardown

- Drop per-user schemas `lakebase_workshop.ws_*` and Lakebase databases `ws_*`.
- Delete apps `lakebase-workshop-*`.
- Stop/delete the shared Lakebase instance if no longer needed.
