# 🏭 Lab 4 – Close the Round-Trip

## 🎯 Learning Objectives
By the end of this lab, you will:
- Read the technician's work back from the **analytical layer** (Databricks SQL) via the CDF
  history tables
- Compute a real metric — **time-to-fix** — by joining actions to the original alerts
- See the whole loop closed: UC → Lakebase → app → **CDF** → back to UC, one governed platform

## Introduction

In Lab 3 the app wrote to the operational Postgres tables (`maintenance_actions`, and via the
other tabs `work_orders`, `quality_checks`, `operator_notes`). Because you started **Change Data
Feed** in Lab 2, every one of those writes streams back into Unity Catalog as an
`lb_<table>_history` Delta table — landing in **`catalog_workshop.schema_<you>`** (the CDF
destination you chose), within ~15 seconds. That's the "back to analytics" leg, and it's a real
change-data pipeline, not a manual copy.

## Instructions

Before you start, please verify:
- You completed **Lab 3** and logged at least one maintenance action in the app.
- CDF has been running (Lab 2, Step 7) — give it ~15–30s after your last write.

Run these in the **SQL Editor** (or a notebook `%sql` cell). Replace `<you>` with your slug —
e.g. `jane.doe@acme.com` → `janedoe`, so the schema is `catalog_workshop.schema_janedoe`.

### Step 1 — See the history tables CDF produced

```sql
SHOW TABLES IN catalog_workshop.schema_<you> LIKE 'lb_*';
```

**✅ Check:** you see `lb_maintenance_actions_history` (and, once you've used the other tabs,
`lb_work_orders_history`, `lb_quality_checks_history`, `lb_operator_notes_history`).

### Step 2 — Read what the technician did, from Databricks SQL

```sql
SELECT * FROM catalog_workshop.schema_<you>.lb_maintenance_actions_history
ORDER BY started_at DESC;
```

**✅ Check:** the action you logged in the app appears here. **That's the round-trip** — an
operational write, captured into the lakehouse by CDF, no hand-written ETL. 🎉

> Empty result? Open the app, log an action, wait ~15s, then re-run. CDF flushes in ~15s batches.

### Step 3 — The metric the data team gets back: time-to-fix

Join the completed actions to the original alerts to compute how long each fix took:

```sql
SELECT h.machine_id, m.model, h.performed_by, h.action_type, h.description,
       round((unix_timestamp(h.completed_at) - unix_timestamp(t.opened_at)) / 3600.0, 1) AS hours_to_fix
FROM catalog_workshop.schema_<you>.lb_maintenance_actions_history h
JOIN catalog_workshop.schema_<you>.machines m            ON m.machine_id = h.machine_id
LEFT JOIN catalog_workshop.schema_<you>.maintenance_tickets t ON t.ticket_id = h.ticket_id
WHERE h.status = 'completed'
ORDER BY h.completed_at DESC;
```

**💡 What just happened?**
The technician's action — captured operationally in the app — is instantly analytics-ready.
This is the metric (MTTR / time-to-fix) that would feed the OEE report and retrain the
vibration-based failure model. The loop is closed: the lakehouse handed data to the floor, and
the floor handed its actions back to the lakehouse, all on one governed platform.

### Step 4 (optional) — Visualize it

Build a one-page AI/BI dashboard over the same data — see [`docs/dashboard.md`](../docs/dashboard.md).

### Going further

CDF gives you full change history (`INSERT`/`UPDATE`/`DELETE`) for every operational table, so you
can build audit trails, SCD-style analytics, or trigger downstream Lakeflow jobs — all from Delta,
with no bespoke connector to maintain.

### 🧹 Teardown

To avoid lingering cost, remove what you created (Lakebase scales to zero when idle, so it's cheap
to leave if you'll come back). **First stop CDF** from the Lakebase UI (project ▸ Change Data Feed
▸ Stop), then run this in a serverless notebook (or delete via the UI: Compute ▸ Apps, Catalog
Explorer, and the Lakebase project page):

```python
import re
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
slug = re.sub(r"[^a-z0-9]", "", w.current_user.me().user_name.split("@")[0].lower())
app   = ("lb-workshop-" + slug)[:30].rstrip("-")
lbcat = f"lakebase_schema_{slug}"

# find your project
PROJECT = None
for i in range(1, 11):
    c = f"lakebase-ws-{slug}-{i}"
    try:
        w.postgres.get_project(name=f"projects/{c}"); PROJECT = c; break
    except Exception:
        continue

try: w.apps.delete(name=app)
except Exception as e: print("app:", e)
for t in ["machines", "sensor_readings", "production_orders", "maintenance_tickets"]:
    try: w.postgres.delete_synced_table(name=f"synced_tables/{lbcat}.public.{t}")
    except Exception as e: print(t, e)
try: w.postgres.delete_catalog(name=f"catalogs/{lbcat}")
except Exception as e: print("catalog:", e)
if PROJECT:
    try: w.postgres.delete_project(name=f"projects/{PROJECT}"); print(f"deleted project {PROJECT}")
    except Exception as e: print("project:", e)
print("done")
```

---

🎉 **You built the Apps + Lakebase round-trip end to end:** analytical data → operational serving
→ an app people use → **Change Data Feed** → back to analytics, all on one governed platform.
