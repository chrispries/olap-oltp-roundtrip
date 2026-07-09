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

## Repository layout

| Path | Purpose |
|------|---------|
| `notebooks/` | Steps **00**, **01**, **04** as Databricks notebooks (`01_generate_data` is the single source for the synthetic data) |
| `sync/` | Step **02**: `02_create_lakebase.md` — CLI runbook (Lakebase DB + UC catalog + synced tables) |
| `app/` | Step **03** code: Streamlit app (`app.py`, `db.py`, `app.yaml`); write-back left as a guided gap |
| `docs/` | `concepts.md`, `attendee-runbook.md` (the 00→04 map), `03_deploy_app.md`, `facilitator-notes.md`, `design.md`, `solutions/` |
| `analytics/` | Round-trip SQL query + dashboard runbook |

## The flow — follow the numbers (00 → 04)

Read [`docs/concepts.md`](docs/concepts.md) first (10 min), then work the steps in order.
Each step is a numbered asset with ✅ checks; the map lives in
[`docs/attendee-runbook.md`](docs/attendee-runbook.md).

| # | Step | Asset | Run via |
|---|------|-------|---------|
| **00** | Start here / orientation | [`notebooks/00_start_here`](notebooks/00_start_here.py) | Notebook |
| **01** | Generate analytical data → Unity Catalog | [`notebooks/01_generate_data`](notebooks/01_generate_data.py) | Notebook |
| **02** | Create Lakebase DB + UC catalog + synced tables | [`sync/02_create_lakebase.md`](sync/02_create_lakebase.md) | `databricks` CLI |
| **03** | Deploy the Streamlit app + write-back | [`docs/03_deploy_app.md`](docs/03_deploy_app.md) + [`app/`](app/) | `databricks` CLI |
| **04** | Explore Lakebase + close the round-trip | [`notebooks/04_explore_and_roundtrip`](notebooks/04_explore_and_roundtrip.py) | Notebook |

**Why the mix?** Data generation and querying live in notebooks (Spark/`%sql`, next to the
data). Creating the Lakebase instance and deploying the app are infrastructure — driven with
the `databricks` CLI, as you'd really do it. Step 02 sets shell variables that 03 and 04 reuse.

For running it as a group: [`docs/facilitator-notes.md`](docs/facilitator-notes.md).

## Status

Built and **validated end-to-end live on Azure FE** (2026-07-08): data load → Lakebase
project + snapshot synced tables → UC catalog → deployed Streamlit app → round-trip write-back
confirmed in Databricks SQL. The repo ships the write-back **stubbed** (the attendee gap);
answer key in [`docs/solutions/`](docs/solutions/). All Python runs on Databricks (public PyPI
is firewalled locally — see the plan's Revision note).
