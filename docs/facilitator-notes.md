# Facilitator Notes

## Prerequisites

- Attendees have access to the Azure FE workspace (`azure-demo`) with permission to create
  schemas in `lakebase_workshop`, deploy apps, and use serverless + a SQL warehouse.
- Facilitator pre-creates the shared Lakebase instance `lakebase-workshop` **before** the
  session (provisioning takes minutes — don't do it live).
- Repo available to import as a workspace Git folder.

## Pre-provisioning checklist (facilitator, day before)

- [ ] Create Lakebase instance `lakebase-workshop`, record host/catalog in `sync/*.md`.
- [ ] Confirm `lakebase_workshop` catalog exists and attendees can create schemas.
- [ ] Confirm a SQL warehouse id for the round-trip query.
- [ ] Run the full attendee runbook once yourself (see Task 8 dry run).

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

- **App can read its own table but not the synced tables** — binding the Lakebase database
  resource as `CAN_CONNECT_AND_CREATE` does **not** auto-grant SELECT on the *pre-existing*
  synced tables to the app's service-principal Postgres role. Grant it explicitly (once):
  ```sql
  GRANT USAGE ON SCHEMA public TO "<sp-client-id>";
  GRANT SELECT ON ALL TABLES IN SCHEMA public TO "<sp-client-id>";
  ```
  (Run as the DB owner via psql. The `<sp-client-id>` is the app SP's client id = `PGUSER`.)
- **Data generation** — lives only in `notebooks/01_generate_data` (self-contained, no repo
  import needed). It is the single source for the synthetic data.
- **App auth (Autoscaling)** — do NOT use a static `PGPASSWORD`. `app/db.py` mints a fresh
  OAuth token per connection via `w.postgres.generate_database_credential(ENDPOINT_NAME)`.
  `ENDPOINT_NAME`, `PGHOST`, `PGDATABASE`, `PGUSER` (= SP client id) are set in `app/app.yaml`.
- **Local `pip install` fails** — expected; this repo is built/tested **on Databricks**, not
  locally (public PyPI is firewalled). Use the notebooks, not a local venv.
- **Snapshot sync shows stale data** — snapshot is one-time; re-create/refresh the synced
  table if the source changed. (Continuous sync is the production answer — talking point.)

## Validated live (2026-07-08, Azure FE `azure-demo`)

The full round-trip was built and verified on the `ws_christopher_pries` namespace:
data load (50/10000/200/120) → Lakebase project `lakebase-workshop` + 4 snapshot synced
tables → UC catalog `lakebase_ws_christopher_pries` → deployed Streamlit app
(`lb-workshop-cpries`, read path confirmed) → wrote a ticket to
`public.app_maintenance_tickets` → read it back from Databricks SQL. Round-trip closed.

- **Reference app (facilitator, write-back already solved):**
  https://lb-workshop-cpries-984752964297111.11.azure.databricksapps.com
- **Repo ships the write-back stubbed** (the attendee gap). The deployed reference app runs
  the completed version; that divergence is intentional. Answer key:
  `docs/solutions/create_maintenance_ticket.py`.

## Productionization talking point (approach B)

The workshop uses live UC-query of the Lakebase table (approach A). In production you might
add a triggered CDC/Lakeflow job to land app writes into a Delta table for long-term
analytics. Mention it; don't build it.

## Teardown

- Drop per-user schemas `lakebase_workshop.ws_*` and Lakebase databases `ws_*`.
- Delete apps `lakebase-workshop-*`.
- Stop/delete the shared Lakebase instance if no longer needed.
