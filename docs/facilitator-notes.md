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

- **Notebook import of `generate.py` fails** — `load_to_uc.py` is self-contained; no import
  needed. Ignore any `data_gen.generate` import in the reference module.
- **PG env vars not injected** — the app's Lakebase resource binding is missing/misconfigured;
  re-check `app/app.yaml` `resources` block against the databricks-apps skill.
- **Local `pip install` fails** — expected; this repo is built/tested **on Databricks**, not
  locally (public PyPI is firewalled). Use the notebooks, not a local venv.
- **Snapshot sync shows stale data** — snapshot is one-time; re-create/refresh the synced
  table if the source changed. (Continuous sync is the production answer — talking point.)

## Productionization talking point (approach B)

The workshop uses live UC-query of the Lakebase table (approach A). In production you might
add a triggered CDC/Lakeflow job to land app writes into a Delta table for long-term
analytics. Mention it; don't build it.

## Teardown

- Drop per-user schemas `lakebase_workshop.ws_*` and Lakebase databases `ws_*`.
- Delete apps `lakebase-workshop-*`.
- Stop/delete the shared Lakebase instance if no longer needed.
