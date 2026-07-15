# 🏭 Lab 1 – Generate Analytical Data

## 🎯 Learning Objectives
By the end of this lab, you will:
- Create your own **Unity Catalog** schema inside the shared `catalog_workshop` catalog
- Generate a realistic, **deterministic** manufacturing dataset (machines, telemetry, orders, tickets)
- Inject a handful of failing machines so the app has a real maintenance queue to work with
- Land all four tables as governed **Delta tables** — the analytical starting point of the round-trip

## Introduction

Every round-trip needs a source of truth. In this lab you create the **analytical layer** — the
Delta tables that, in a real factory, the data team already owns: machine master data, sensor
telemetry, production orders, and a history of maintenance tickets.

Everything is generated from a **fixed random seed**, so your tables look identical to everyone
else's — the same four machines will be "failing," which keeps the rest of the workshop
predictable.

> New to the concepts? Read [`docs/concepts.md`](../docs/concepts.md) (10 min) first.

## Instructions

Run the cells below in order in a **serverless Python notebook** in your Git folder. This lab is
self-contained — you can run it top to bottom in a fresh session.

### Step 1 — Create your catalog and schema

Everyone shares the `catalog_workshop` catalog but gets their **own schema**, derived from your
username, so nobody overwrites anyone else's tables.

```python
import re

CATALOG = "catalog_workshop"
user = spark.sql("SELECT current_user()").first()[0]
schema = "schema_" + re.sub(r"[^a-z0-9]", "", user.split("@")[0].lower())

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{schema}")
print(f"✅ your target is {CATALOG}.{schema}")
```

> **📌 Note your schema name.** The slug strips *everything* that isn't a letter or digit
> (including dots and underscores), so `jane.doe@acme.com` → schema **`schema_janedoe`**. Every
> later lab derives the exact same name the same way, so they all line up — just remember what
> `✅ your target is …` prints here.

### Step 2 — Generate the manufacturing dataset

Four related tables, all from one seeded random generator (`rng = np.random.default_rng(42)`),
so the output is identical on every run:

- **`machines`** (50) — the parent table: model, production line, install date, location.
- **`sensor_readings`** (10,000) — telemetry: temperature, vibration, load, timestamped.
- **`production_orders`** (200) — what each machine is scheduled to build.
- **`maintenance_tickets`** (120) — seeded repair history and open alerts.

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

### Step 3 — Flag four machines for attention

A demo where nothing is wrong is boring. This pushes four specific machines (**#7, #19, #31,
#44**) into an alarm state: their recent vibration spikes well above the ~2.5 mm/s norm, and each
gets an **open, high-priority ticket**. These are the alerts your app opens onto in Lab 3.

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

### Step 4 — Write the tables to Unity Catalog and verify

Save each DataFrame as a governed Delta table in your schema, then assert the row counts so you
catch any problem here rather than three labs later.

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

**✅ Check:** you see `OK machines: 50`, `sensor_readings: 10000`, `production_orders: 200`,
`maintenance_tickets: 120`, and the final ✅ line. Open **Catalog ▸ `catalog_workshop` ▸ your
schema** and you'll see the four tables.

**💡 What just happened?**

- **Technically:** you created a Unity Catalog schema and wrote four related Delta tables into it
  — a small but complete analytical model (a parent `machines` table plus telemetry, orders, and
  tickets that reference it). Because it's generated from a fixed seed, the data is reproducible;
  because it's Delta in Unity Catalog, it's governed, versioned, and ready to be synced.
- **In the scenario:** this is the data the factory's **data team already has** — the lakehouse
  side of the story. It's perfect for analytics (OEE reporting, a vibration-based failure model),
  but it's not yet in front of the people on the floor. Four machines are now visibly in trouble
  (#7, #19, #31, #44) — exactly the situation the operational app in Lab 3 needs to surface.

➡️ **Next: [Lab 2 – Sync to Lakebase](Lab%202%20-%20Sync%20to%20Lakebase.md).**
