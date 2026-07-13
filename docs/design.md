# Workshop — Databricks Apps + Lakebase Round-Trip

**Date:** 2026-07-08
**Owner:** Christopher Pries (Sr. SE, CEMEA Manufacturing)
**Target environment:** Azure Field Eng (FE) demo workspace (reuse prior Lakebase workshop setup patterns)

## Goal

A 90-minute **hands-on build-along** workshop that proves the Databricks Apps + Lakebase
**round-trip**: analytical data that already lives in Unity Catalog is synced into an
operational Lakebase (Postgres) database, served through a Databricks App, edited by
users in that app, and those edits reappear in the analytical layer — all on one governed
platform.

**Single most important takeaway:** _"If I have analytical data in Unity Catalog, it is
easy to get it into Lakebase, easy to build and serve an app on top, and whatever happens
in the app comes straight back to the analytical layer."_

## Audience & format

- **Format:** hands-on build-along.
- **Audience:** software/data engineers, medium group (9–20).
- **Language/stack:** **Streamlit (Python)** app — least code, fastest to deploy, ideal
  for a time-boxed hands-on session and a Python-oriented data audience. A **FastAPI +
  React** variant is a possible advanced follow-up (see Out of scope), not the workshop
  default.
- **Reality constraint:** the app is **pre-built** in the workshop repo. Attendees do NOT
  write the app from scratch. Hands-on = generate data → wire up Lakebase → deploy the
  app → make one guided code change (complete the write-back logic) → redeploy →
  observe the round-trip close. (Streamlit keeps this gap small and readable — a single
  function/handler rather than a full endpoint + client wiring.)

## Scenario

**Shop-floor predictive-maintenance app.** Manufacturing / IoT operational domain.

Synthetic tables (generated per-attendee into Unity Catalog):
- `machines` — machine master data (id, model, line, install date, location)
- `sensor_readings` — time-series telemetry (machine_id, ts, temperature, vibration, load)
- `production_orders` — orders in flight per machine/line
- `maintenance_tickets` — seed set of historical/open tickets

## Architecture — the round-trip

1. **Generate → UC (Delta).** A script in the repo creates a per-user catalog/schema and
   populates the four tables above. This establishes the "analytical data already exists"
   starting point.
2. **Sync → Lakebase.** Create a Lakebase Postgres instance, then create **synced tables**
   from the Delta tables. Synced tables are read-only, low-latency serving replicas
   (choice of snapshot / triggered / continuous sync mode).
3. **Serve → App.** The Streamlit app reads machine health, sensor summaries, and
   open tickets from the synced tables (fast OLTP reads).
4. **Write-back.** An operator creates/updates a maintenance ticket in the app. Because
   synced tables are read-only, the write lands in an **app-owned Postgres table** in the
   same Lakebase instance (e.g. `app_maintenance_tickets`).
5. **Back to analytics.** The Lakebase instance is **registered in Unity Catalog**, so an
   analyst queries `app_maintenance_tickets` live from Databricks SQL / a dashboard and
   sees the operator's new ticket in the lakehouse. Round-trip closed.

### Write-back mechanism decision

- **Chosen — A: Live query via Lakebase-in-UC.** App writes to its own Postgres table;
  analysts query it live through the UC-registered Lakebase catalog. No extra pipeline,
  real-time, easiest to demo and explain in the time box.
- **B: Reverse sync to Delta** (triggered CDC / Lakeflow job landing writes into a Delta
  table). More production-grade; kept as a **talking-point / slide** on productionization,
  not a hands-on step.
- **C: App writes straight to Delta.** Rejected — slow writes defeat the OLTP purpose of
  Lakebase.

## Repository structure (deliverable)

A clonable workshop repo containing:
- `data-gen/` — script to create per-user catalog/schema + populate the four Delta tables
  (synthetic manufacturing/IoT data).
- `app/` — complete Streamlit predictive-maintenance app, with the write-back logic
  left as a clearly-marked guided gap (a single function) for attendees to complete.
- `sync/` — instructions/scripts to create the Lakebase instance and synced tables
  (UI walkthrough + CLI/SQL equivalents).
- `analytics/` — the analytical query / dashboard used at the end to show write-back
  landing in UC.
- `README.md` — step-by-step attendee runbook mirroring the agenda.
- Facilitator notes (setup, prerequisites, common failure modes, timing).

## Attendee isolation (9–20 people)

- Shared Azure FE workspace.
- **Per-user namespacing:** each attendee gets their own catalog/schema (e.g. suffixed with
  username) and their own app name, to avoid collisions.
- Lakebase: decide between one shared instance with per-user Postgres schemas vs. per-user
  instances (cost/provisioning-time tradeoff) — to be finalized in the implementation plan.

## 90-minute agenda

| Time | Segment | Mode |
|------|---------|------|
| 0:00–0:10 | Intro + architecture story (round-trip diagram) | Presentation |
| 0:10–0:20 | Clone repo, run data-gen → UC catalog populated | Hands-on |
| 0:20–0:35 | Create Lakebase instance + synced tables | Hands-on |
| 0:35–0:50 | Deploy the provided app, explore it | Hands-on |
| 0:50–1:10 | Guided code change: complete write-back logic, redeploy | Hands-on (payoff) |
| 1:10–1:25 | Run analytical query / dashboard, see write-back land | Hands-on |
| 1:25–1:30 | Productionization (approach B) + wrap-up | Presentation |

## Success criteria

- Each attendee independently: populates a UC catalog, creates synced tables, deploys the
  Streamlit app, completes the write-back edit, and observes their own ticket appear in a
  Databricks SQL query.
- The session finishes within 90 minutes with buffer for one round of troubleshooting.

## Open items (resolve in implementation plan)

- Lakebase instance topology: shared vs. per-user.
- Sync mode for synced tables (snapshot vs. triggered vs. continuous) appropriate for the
  demo.
- Exact synthetic data volume (small enough to generate fast, large enough to look real).
- Whether the final analytics view is a raw SQL query or a small AI/BI dashboard.
- Reuse assessment against existing Lakebase workshop assets (DBA workshop, M8 module).

## Explicitly out of scope

- Building the Streamlit app from scratch during the session (app is pre-built; only the
  write-back gap is completed live).
- FastAPI + React variant — a possible advanced follow-up deliverable, not the default
  90-min workshop.
- Reverse-sync/CDC pipeline as a hands-on step (talking point only).
- Production security hardening, CI/CD, multi-environment promotion.
