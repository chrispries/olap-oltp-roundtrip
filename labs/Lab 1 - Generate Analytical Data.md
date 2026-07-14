# 🏭 Lab 1 – Generate Analytical Data

## 🎯 Learning Objectives
By the end of this lab, you will:
- Create your own Unity Catalog **schema** and four **Delta** tables of manufacturing / IoT data
- Understand the **data model** the rest of the workshop uses
- See how a few machines are seeded to clearly **need attention**, so the app tells a story

## Introduction

This is stage 1 of the round-trip — the *analytical data you already have* in the lakehouse.
Everyone shares one catalog (`catalog_workshop`) but gets their **own schema** `schema_<username>`,
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

Create a new Python notebook, attach it to **serverless**, and run each cell below in order.

### Step 1 — Create your catalog + schema

Everyone shares the `catalog_workshop` catalog; you get your own `schema_<username>` schema,
derived from your login. `CREATE ... IF NOT EXISTS` is safe to re-run.

```python
import re

CATALOG = "catalog_workshop"
user = spark.sql("SELECT current_user()").first()[0]
schema = "schema_" + re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{schema}")
print(f"✅ your target is {CATALOG}.{schema}")
```

**✅ Check:** it prints your target, e.g. `catalog_workshop.schema_jane_doe`.

### Step 2 — Generate the four tables (deterministic)

It uses a fixed seed, so every participant gets the same results.

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
MODELS   = ["Laser Cutter", "Press Brake", "Punch Press", "Milling Machine"]
LINES    = ["Line-A", "Line-B", "Line-C"]
LOCATIONS= ["Plant North", "Plant South", "Plant East", "Plant West"]
PRODUCTS = ["bracket", "panel", "housing", "flange", "rail"]
FAULTS   = ["coolant low", "vibration alarm", "laser calibration", "belt wear", "sensor fault"]

# machines (parent)
machines = pd.DataFrame({
    "machine_id": np.arange(1, 51),
    "model": rng.choice(MODELS, 50), "line": rng.choice(LINES, 50),
    "install_date": (pd.to_datetime("2018-01-01") + pd.to_timedelta(rng.integers(0, 2500, 50), unit="D")).date,
    "location": rng.choice(LOCATIONS, 50),
})
ids = machines["machine_id"].to_numpy()

# sensor telemetry
sensor_readings = pd.DataFrame({
    "reading_id": np.arange(1, 10_001), "machine_id": rng.choice(ids, 10_000),
    "ts": pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.integers(0, 30*24*60, 10_000), unit="m"),
    "temperature_c": np.round(rng.normal(65, 8, 10_000), 2),
    "vibration_mm_s": np.round(np.abs(rng.normal(2.5, 1.0, 10_000)), 3),
    "load_pct": np.round(rng.uniform(20, 100, 10_000), 1),
})

# production orders
due = pd.Timestamp("2026-07-01") + pd.to_timedelta(rng.integers(0, 60, 200), unit="D")
production_orders = pd.DataFrame({
    "order_id": np.arange(1, 201), "machine_id": rng.choice(ids, 200),
    "product": rng.choice(PRODUCTS, 200), "qty": rng.integers(10, 500, 200),
    "status": rng.choice(["open","running","done"], 200, p=[0.3,0.4,0.3]),
    "due_date": [d.date() for d in due],
})

# maintenance tickets (seeded history / alerts)
opened = pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.integers(0, 40*24*60, 120), unit="m")
maintenance_tickets = pd.DataFrame({
    "ticket_id": np.arange(1, 121), "machine_id": rng.choice(ids, 120), "opened_at": opened,
    "priority": rng.choice(["low","medium","high"], 120, p=[0.5,0.35,0.15]),
    "status": rng.choice(["open","closed"], 120, p=[0.4,0.6]),
    "description": rng.choice(FAULTS, 120),
})
print("generated:", {k: len(v) for k, v in
      dict(machines=machines, sensor_readings=sensor_readings,
           production_orders=production_orders, maintenance_tickets=maintenance_tickets).items()})
```

### Step 3 — Seed the story: machines that *need attention*

Deterministically plant four machines with elevated vibration **and** an open, high-priority
ticket, so the app opens like a real maintenance cockpit.

```python
WATCHLIST = {7: "vibration alarm — bearing wear", 19: "coolant low",
             31: "laser calibration drift",       44: "spindle overheating"}

# 1) push their recent vibration well above the ~2.5 mm/s norm
alarm = sensor_readings["machine_id"].isin(WATCHLIST)
sensor_readings.loc[alarm, "vibration_mm_s"] = (sensor_readings.loc[alarm, "vibration_mm_s"] + 3.0).round(3)

# 2) give each an open, high-priority ticket (overwrite rows so the count stays 120)
for i, (mid, fault) in enumerate(WATCHLIST.items()):
    maintenance_tickets.loc[i, ["machine_id", "priority", "status", "description"]] = [mid, "high", "open", fault]

print("watchlist:", list(WATCHLIST))
```

### Step 4 — Write to Delta and verify

`spark.createDataFrame(pandas_df).write.saveAsTable(...)` persists each frame as a governed
Delta table. The assertion *is* your test — a wrong count fails loudly.

```python
frames = {"machines": machines, "sensor_readings": sensor_readings,
          "production_orders": production_orders, "maintenance_tickets": maintenance_tickets}
for name, pdf in frames.items():
    spark.createDataFrame(pdf).write.mode("overwrite").saveAsTable(f"{CATALOG}.{schema}.{name}")

EXPECTED = {"machines": 50, "sensor_readings": 10_000, "production_orders": 200, "maintenance_tickets": 120}
for name, expected in EXPECTED.items():
    actual = spark.table(f"{CATALOG}.{schema}.{name}").count()
    assert actual == expected, f"{name}: expected {expected}, got {actual}"
    print(f"OK  {name}: {actual}")
print(f"\n✅ All four tables loaded into {CATALOG}.{schema}")
```

**✅ Check:** you see `OK` for each table and `✅ All four tables loaded …` (50 / 10000 / 200 / 120).

**💡 What just happened?**
- **Technically:** you created a schema in Unity Catalog for your data to live in, then loaded
  the plant's data into it as governed **Delta tables** — the machines themselves, the sensor
  telemetry they stream, and their production orders — plus a set of maintenance tickets that
  includes current failures on four machines.
- **In the scenario:** this is the analytical picture the business already has. You now know
  your fleet of machines, what their sensors are reporting, and which machines have open issues
  right now. That's the foundation the rest of the round-trip builds on — serving this data to
  the people on the floor and feeding their actions back.

> **Note:** All labs use the catalog `catalog_workshop` and your per-user schema
> `schema_<username>` (lowercase, non-alphanumeric → `_`). Example:
> `jane.doe@acme.com` → `schema_jane_doe`.

➡️ **Next: [Lab 2 – Sync to Lakebase](Lab%202%20-%20Sync%20to%20Lakebase.md).**
