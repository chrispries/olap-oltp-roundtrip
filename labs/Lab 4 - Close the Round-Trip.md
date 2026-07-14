# 🏭 Lab 4 – Close the Round-Trip

## 🎯 Learning Objectives
By the end of this lab, you will:
- Read the technician's work back from the **analytical layer** (Databricks SQL)
- Compute a real metric — **time-to-fix** — by joining resolutions to the original alerts
- See the whole loop closed: UC → Lakebase → app → back to UC, one governed platform, no ETL

## Introduction

In Lab 3 the app wrote the technician's resolutions to `maintenance_actions` in Postgres.
Because your Lakebase database is registered in Unity Catalog, that table is queryable from
Databricks SQL **live** — no pipeline, no copy. That's the "back to analytics" leg.

## Instructions

Before you start, please verify:
- You completed **Lab 3** and resolved at least one alert in the app.

Run these in the **SQL Editor** (or a notebook `%sql` cell). Replace `<your_user>` with your
slug — e.g. `jane.doe@acme.com` → `jane_doe`, so the catalog is `lakebase_ws_jane_doe`.

### Step 1 — Read what the technician did, from Databricks SQL

```sql
SELECT machine_id, technician, status, resolution, claimed_at, resolved_at
FROM lakebase_ws_<your_user>.public.maintenance_actions
ORDER BY COALESCE(resolved_at, claimed_at) DESC;
```

**✅ Check:** the resolution you wrote in the app appears here. **That's the round-trip** — an
operational write, live in the lakehouse, with no ETL. 🎉

> Empty result? Open the app, **claim** and **resolve** an alert first (the app creates the
> `maintenance_actions` table on first load), then re-run.

### Step 2 — The metric the data team gets back: time-to-fix

Join resolutions to the original alerts to compute how long each fix took:

```sql
SELECT a.machine_id, m.model, a.technician, a.resolution,
       round((unix_timestamp(a.resolved_at) - unix_timestamp(t.opened_at)) / 3600.0, 1) AS hours_to_fix
FROM lakebase_ws_<your_user>.public.maintenance_actions a
JOIN lakebase_ws_<your_user>.public.machines m           ON m.machine_id = a.machine_id
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

### Going further

In production you might also land the app's writes into a Delta table (via a triggered CDC /
Lakeflow job) for long-term history — while the live UC-federated query you just ran stays the
low-latency path. Same platform, same governance.

### 🧹 Teardown

To avoid lingering cost, remove what you created (the Lakebase project scales to zero when idle,
so it's cheap to leave if you'll come back). Run in a serverless notebook, or delete via the UI
(Compute ▸ Apps, Catalog Explorer, Compute ▸ Database instances):

```python
import re
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
slug = re.sub(r"[^a-z0-9]", "_", w.current_user.me().user_name.split("@")[0].lower())
app   = ("lb-workshop-" + slug.replace("_", "-"))[:30].rstrip("-")
lbcat = f"lakebase_ws_{slug}"
branch = "projects/lakebase-workshop/branches/production"

try: w.apps.delete(name=app)
except Exception as e: print("app:", e)
for t in ["machines", "sensor_readings", "production_orders", "maintenance_tickets"]:
    try: w.postgres.delete_synced_table(name=f"synced_tables/{lbcat}.public.{t}")
    except Exception as e: print(t, e)
try: w.postgres.delete_catalog(name=f"catalogs/{lbcat}")
except Exception as e: print("catalog:", e)
print("done — drop your Postgres database ws_%s from the SQL/psql side if you want it gone too" % slug)
```

---

🎉 **You built the Apps + Lakebase round-trip end to end:** analytical data → operational
serving → an app people use → back to analytics, all on one governed platform.
