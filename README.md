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

Presenting it? Open with the scenario: [`docs/scenario.md`](docs/scenario.md) ("Keep the line
running"). Full design and rationale: [`docs/design.md`](docs/design.md).

![Architecture: the Apps + Lakebase round-trip](docs/architecture.svg)

## Scenario — "Keep the line running"

> Manufacturing data already sits in tables in Unity Catalog. But the people who need it most
> — the technicians keeping machines running — can't work off a data warehouse. **Lakebase +
> Apps** serve that data operationally, let those people act on it, and play their actions
> straight back into analytics.

**TRUMPF runs 50 CNC machines** (TruLaser, TruBend, TruPunch, TruMatic) across three lines in
four plants. Every machine streams telemetry — temperature, vibration, spindle load — into the
lakehouse, next to its production orders and maintenance history. The data team already mines
it for OEE reporting and a vibration-based failure model.

**But that intelligence is trapped in dashboards.** At 2 a.m. machine #7's vibration climbs
past its limit. The night-shift technician isn't going to open a BI dashboard — they need a
dead-simple tablet app: *"which of my machines need attention right now, and let me log what I
did about it."* That's an **operational** job (instant lookups and writes) the analytical
lakehouse isn't built for — and a separate Postgres would mean a second system to govern.
That's the gap Lakebase + Apps close:

1. The data's already in **Unity Catalog** → **sync** it into Lakebase for millisecond serving.
2. A **Databricks App** — the Maintenance Cockpit — shows each technician their machines + open alerts.
3. The technician logs a fix (*"replaced coolant filter on TruLaser #7"*) — a **write-back**.
4. Governed by UC, that action is **instantly queryable in SQL** — measure MTTR, retrain the model.

> **One governed platform serves both the analyst and the technician — and the technician's
> actions make the analytics smarter.** From a vibration signal to a wrench on the shop floor,
> and back to the model that predicted it.

The seed plants four machines that clearly need attention (**#7** bearing wear, **#19** coolant
low, **#31** calibration drift, **#44** spindle overheating), so the app opens like a real
cockpit. Full write-up: [`docs/scenario.md`](docs/scenario.md).

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
| `notebooks/` | All five steps **00–04** as runnable Databricks notebooks (the primary path) |
| `sync/` | Step **02** laptop-CLI alternative: `02_create_lakebase.md` |
| `app/` | Step **03** code: Streamlit app (`app.py`, `db.py`, `app.yaml`); write-back left as a guided gap |
| `docs/` | `concepts.md`, `attendee-runbook.md` (the 00→04 map), `03_deploy_app.md` (CLI alt), `facilitator-notes.md`, `design.md`, `solutions/` |
| `analytics/` | Round-trip SQL query + dashboard runbook |

## The flow — follow the numbers (00 → 04)

Read [`docs/concepts.md`](docs/concepts.md) first (10 min), then work the steps in order.
Each step is a numbered asset with ✅ checks; the map lives in
[`docs/attendee-runbook.md`](docs/attendee-runbook.md).

Every step is a **runnable notebook** — participants just "Run cell" in their own workspace,
no laptop setup. Each infra step also lists a UI path and a laptop-CLI alternative.

| # | Step | Run in a notebook | Also available as |
|---|------|-------------------|-------------------|
| **00** | Start here / orientation | [`notebooks/00_start_here`](notebooks/00_start_here.py) | — |
| **01** | Generate analytical data → Unity Catalog | [`notebooks/01_generate_data`](notebooks/01_generate_data.py) | — |
| **02** | Create Lakebase DB + UC catalog + synced tables | [`notebooks/02_create_lakebase`](notebooks/02_create_lakebase.py) | UI (in-notebook) · CLI: [`sync/02_create_lakebase.md`](sync/02_create_lakebase.md) |
| **03** | Deploy the Streamlit app + write-back | [`notebooks/03_deploy_app`](notebooks/03_deploy_app.py) + [`app/`](app/) | UI (in-notebook) · CLI: [`docs/03_deploy_app.md`](docs/03_deploy_app.md) |
| **04** | Explore Lakebase + close the round-trip | [`notebooks/04_explore_and_roundtrip`](notebooks/04_explore_and_roundtrip.py) | — |

The infra notebooks (02, 03) use the Databricks SDK, so they run entirely in-workspace; each
ends with the equivalent UI clicks and points to the laptop-CLI runbook if you prefer that.

For running it as a group: [`docs/facilitator-notes.md`](docs/facilitator-notes.md).

## Status

Built and **validated end-to-end live on Azure FE** (2026-07-08): data load → Lakebase
project + snapshot synced tables → UC catalog → deployed Streamlit app → round-trip write-back
confirmed in Databricks SQL. The repo ships the write-back **stubbed** (the attendee gap);
answer key in [`docs/solutions/`](docs/solutions/). All Python runs on Databricks (public PyPI
is firewalled locally — see the plan's Revision note).
