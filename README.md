# App + Lakebase in a Day

A hands-on workshop that proves the Databricks **Apps + Lakebase round-trip**: analytical
data that already lives in Unity Catalog is synced into an operational Lakebase (Postgres)
database, served through a Databricks App, edited by users in that app, and those edits
reappear in the analytical layer — all on one governed platform.

**Takeaway:** _If I have analytical data in Unity Catalog, it is easy to get it into
Lakebase, easy to build and serve an app on top, and whatever happens in the app comes
straight back to the analytical layer._

- **Format:** 90-minute hands-on build-along
- **Audience:** data/software engineers (medium group, 9–20)
- **App stack:** Streamlit (Python) — FastAPI + React is a possible advanced variant
- **Scenario:** shop-floor predictive maintenance (manufacturing / IoT)

Full design and rationale: [`docs/design.md`](docs/design.md).

## The round-trip

1. **Generate → UC (Delta)** — a script populates a per-user catalog with manufacturing/IoT
   tables (`machines`, `sensor_readings`, `production_orders`, `maintenance_tickets`).
2. **Sync → Lakebase** — create a Lakebase Postgres instance and synced tables from the
   Delta tables (read-only serving replicas).
3. **Serve → App** — a Streamlit app reads machine health and open tickets from the synced
   tables.
4. **Write-back** — the app writes new/updated maintenance tickets to an app-owned Postgres
   table in Lakebase.
5. **Back to analytics** — because Lakebase is registered in Unity Catalog, the app's writes
   are queryable live from Databricks SQL. Round-trip closed.

## 90-minute agenda

| Time | Segment | Mode |
|------|---------|------|
| 0:00–0:10 | Intro + architecture story | Presentation |
| 0:10–0:20 | Clone repo, run data-gen → UC catalog populated | Hands-on |
| 0:20–0:35 | Create Lakebase instance + synced tables | Hands-on |
| 0:35–0:50 | Deploy the provided app, explore it | Hands-on |
| 0:50–1:10 | Guided code change: complete write-back, redeploy | Hands-on |
| 1:10–1:25 | Run analytical query / dashboard, see write-back land | Hands-on |
| 1:25–1:30 | Productionization + wrap-up | Presentation |

## Repository layout (planned)

| Path | Purpose |
|------|---------|
| `data-gen/` | Script to create a per-user catalog/schema and populate synthetic Delta tables |
| `sync/` | Create the Lakebase instance and synced tables (UI walkthrough + CLI/SQL) |
| `app/` | Complete Streamlit app; write-back left as a guided gap |
| `analytics/` | The query / dashboard that shows write-back landing in UC |
| `docs/` | Design spec and facilitator notes |

## Status

Code + docs artifacts built locally (data-gen, app, analytics, runbooks). Live validation on
Azure FE (data load, Lakebase instance + synced tables, app deploy, round-trip, dry run) is
pending. Build runs on Databricks — public PyPI is firewalled locally, so all Python
execution/testing happens on the workspace (see the plan's Revision note).

- Attendee steps: [`docs/attendee-runbook.md`](docs/attendee-runbook.md)
- Facilitator: [`docs/facilitator-notes.md`](docs/facilitator-notes.md)
