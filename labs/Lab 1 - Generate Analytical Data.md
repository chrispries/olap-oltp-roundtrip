# 🏭 Lab 1 – Generate Analytical Data

## 🎯 Learning Objectives
By the end of this lab, you will:
- Create your own Unity Catalog **schema** and four **Delta** tables of manufacturing / IoT data
- Understand the **data model** the rest of the workshop uses
- See how a few machines are seeded to clearly **need attention**, so the app tells a story
- Verify the result in Unity Catalog

## Introduction

This is stage 1 of the round-trip — the *analytical data you already have* in the lakehouse.
Later labs sync it into Lakebase, serve it through an app, and watch the app's writes come back.

Everyone shares one catalog (`lakebase_workshop`) but gets their **own schema** `ws_<username>`,
so nobody collides. The data model:

| Table | Grain | Key columns |
|-------|-------|-------------|
| `machines` | one row per machine (50) | `machine_id`, model, line, location |
| `sensor_readings` | telemetry (10,000) | `reading_id`, `machine_id`, temperature, vibration, load |
| `production_orders` | orders in flight (200) | `order_id`, `machine_id`, product, qty, status |
| `maintenance_tickets` | seeded tickets/alerts (120) | `ticket_id`, `machine_id`, priority, status |

## Instructions

Before you start, please verify:
- You completed **Lab 0** (repo is a Git folder in your workspace).
- You can run a **serverless** notebook.

### Step 1 — Run the data-generation notebook

1. Open [`bundle/src/notebooks/generate_data.py`](../bundle/src/notebooks/generate_data.py)
   from your Git folder.
2. Attach it to **serverless** and click **Run all**.

It derives your schema, generates the four tables, writes them as Delta, and asserts the counts.
The core write is just:

```python
for name, pdf in frames.items():
    (spark.createDataFrame(pdf)
        .write.mode("overwrite")
        .saveAsTable(f"{CATALOG}.{schema}.{name}"))
```

**✅ Check:** the last cell prints `✅ All four tables loaded into lakebase_workshop.ws_...`
with counts **50 / 10000 / 200 / 120**.

**💡 What just happened?**
- The notebook derived `ws_<your-username>` from `current_user()` so your data is isolated.
- It generated deterministic data (fixed seed) — everyone gets identical rows, which keeps the
  workshop reproducible.
- `spark.createDataFrame(pandas_df).write.saveAsTable(...)` persisted each frame as a **managed
  Delta table** in Unity Catalog.

### Step 2 — Meet the machines that need attention

Step 3.5 of the notebook deliberately plants four machines with **elevated vibration** and an
**open, high-priority ticket**, so the app opens like a real cockpit:

- **#7** — vibration alarm, bearing wear · **#19** — coolant low
- **#31** — calibration drift · **#44** — spindle overheating

### Step 3 — Verify in Unity Catalog

Open the **SQL Editor** (or a notebook cell) and run — substitute your own schema:

```sql
SELECT priority, count(*)
FROM lakebase_workshop.ws_<your_user>.maintenance_tickets
WHERE status = 'open'
GROUP BY priority ORDER BY 1;
```

**✅ Check:** you see open tickets, with several `high` (the seeded alerts among them). You can
also browse **Catalog ▸ lakebase_workshop ▸ ws_… ▸ machines** in the sidebar.

> **Note:** All labs use the catalog `lakebase_workshop` and your per-user schema
> `ws_<username>` (lowercase, non-alphanumeric → `_`). Example:
> `jane.doe@acme.com` → `ws_jane_doe`.

➡️ **Next: [Lab 2 – Sync to Lakebase](Lab%202%20-%20Sync%20to%20Lakebase.md).**
