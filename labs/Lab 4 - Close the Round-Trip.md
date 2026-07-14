# 🏭 Lab 4 – Close the Round-Trip

## 🎯 Learning Objectives
By the end of this lab, you will:
- Read the technician's work back from the **analytical layer** (Databricks SQL)
- Compute a real metric — **time-to-fix** — by joining resolutions to the original alerts
- See the whole loop closed: UC → Lakebase → app → back to UC, one governed platform, no ETL
- (Optional) Build a small AI/BI dashboard over it

## Introduction

In Lab 3 the app wrote the technician's resolutions to `maintenance_actions` in Postgres.
Because your Lakebase database is registered in Unity Catalog, that table is queryable from
Databricks SQL **live** — no pipeline, no copy. That's the "back to analytics" leg, and it's
what lets the data team measure repair time and feed the failure model.

## Instructions

Before you start, please verify:
- You completed **Lab 3** and resolved at least one alert in the app.

### Step 1 — Read what the technician did, from Databricks SQL

Run [`labs/artifacts/roundtrip_query.sql`](artifacts/roundtrip_query.sql) in the SQL Editor
(substitute your user), or the cell below:

```sql
SELECT machine_id, technician, status, resolution, claimed_at, resolved_at
FROM lakebase_ws_<your_user>.public.maintenance_actions
ORDER BY COALESCE(resolved_at, claimed_at) DESC;
```

**✅ Check:** the resolution you wrote in the app appears here. **That's the round-trip** — an
operational write, live in the lakehouse, with no ETL. 🎉

### Step 2 — The metric the data team gets back: time-to-fix

Run the explore notebook [`bundle/src/notebooks/explore_and_roundtrip.py`](../bundle/src/notebooks/explore_and_roundtrip.py),
or this query — it joins resolutions to the original alerts:

```sql
SELECT a.machine_id, m.model, a.technician, a.resolution,
       round((unix_timestamp(a.resolved_at) - unix_timestamp(t.opened_at)) / 3600.0, 1) AS hours_to_fix
FROM lakebase_ws_<your_user>.public.maintenance_actions a
JOIN lakebase_ws_<your_user>.public.machines m ON m.machine_id = a.machine_id
LEFT JOIN lakebase_ws_<your_user>.public.maintenance_tickets t ON t.ticket_id = a.ticket_id
WHERE a.status = 'resolved'
ORDER BY a.resolved_at DESC;
```

**💡 What just happened?**
The technician's action — captured operationally in the app — is instantly analytics-ready.
This is the metric (MTTR / time-to-fix) that would feed the OEE report and retrain the
vibration-based failure model. The loop is closed.

### Step 3 (optional) — Visualize it

Build a one-page AI/BI dashboard over the same data — see [`docs/dashboard.md`](../docs/dashboard.md).

### 🧹 Teardown (when you're done)

To avoid lingering cost, clean up your resources — delete your app, synced tables, catalog, and
database (the shared Lakebase project scales to zero when idle, so it's cheap to leave). The
exact commands are in [`docs/facilitator-notes.md`](../docs/facilitator-notes.md).

---

🎉 **That's the workshop.** You built the Apps + Lakebase round-trip end to end: analytical
data → operational serving → an app people actually use → back to analytics, all on one
governed platform.
