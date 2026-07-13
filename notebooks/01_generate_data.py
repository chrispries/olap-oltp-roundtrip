# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generate the analytical data (Unity Catalog)
# MAGIC
# MAGIC **Where this fits:** this is stage 1 of the round-trip — the *analytical data you
# MAGIC already have* in the lakehouse. Later notebooks sync it into Lakebase, serve it through
# MAGIC an app, and watch the app's writes come back here.
# MAGIC
# MAGIC ```
# MAGIC 👉 (01) UC Delta ──▶ (02) Lakebase synced tables ──▶ (03) app ──▶ (04) round-trip
# MAGIC ```
# MAGIC
# MAGIC **What you'll do here:** create your own schema and generate four seeded
# MAGIC manufacturing / IoT tables as Delta. Run the cells top to bottom.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1 · Your workspace — who am I, where does my data go?
# MAGIC
# MAGIC Everyone shares one catalog (`lakebase_workshop`) but gets their **own schema**
# MAGIC `ws_<username>`, so nobody collides. We derive it from your login.

# COMMAND ----------
import re

CATALOG = "lakebase_workshop"
user = spark.sql("SELECT current_user()").first()[0]
schema = "ws_" + re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())

print(f"You are:      {user}")
print(f"Your target:  {CATALOG}.{schema}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2 · Create your catalog + schema
# MAGIC
# MAGIC `CREATE ... IF NOT EXISTS` is safe to re-run.

# COMMAND ----------
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{schema}")
print(f"✅ {CATALOG}.{schema} ready")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3 · The data model
# MAGIC
# MAGIC A tiny shop-floor world — four related tables, all keyed on `machine_id`:
# MAGIC
# MAGIC | Table | Grain | Key columns |
# MAGIC |-------|-------|-------------|
# MAGIC | `machines` | one row per machine (50) | `machine_id`, model, line, location |
# MAGIC | `sensor_readings` | telemetry (10,000) | `reading_id`, `machine_id`, temp, vibration, load |
# MAGIC | `production_orders` | orders in flight (200) | `order_id`, `machine_id`, product, qty, status |
# MAGIC | `maintenance_tickets` | seeded tickets (120) | `ticket_id`, `machine_id`, priority, status |
# MAGIC
# MAGIC We generate deterministically (fixed seed) so everyone gets identical data.

# COMMAND ----------
import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

MODELS = ["Laser Cutter", "Press Brake", "Punch Press", "Milling Machine"]
LINES = ["Line-A", "Line-B", "Line-C"]
LOCATIONS = ["Plant North", "Plant South", "Plant East", "Plant West"]
PRODUCTS = ["bracket", "panel", "housing", "flange", "rail"]
FAULTS = ["coolant low", "vibration alarm", "laser calibration", "belt wear", "sensor fault"]

# COMMAND ----------
# MAGIC %md
# MAGIC ### 3a · Machines (the parent table)

# COMMAND ----------
n = 50
machines = pd.DataFrame({
    "machine_id": np.arange(1, n + 1),
    "model": rng.choice(MODELS, n),
    "line": rng.choice(LINES, n),
    "install_date": (pd.to_datetime("2018-01-01") + pd.to_timedelta(rng.integers(0, 2500, n), unit="D")).date,
    "location": rng.choice(LOCATIONS, n),
})
machine_ids = machines["machine_id"].to_numpy()
machines.head()

# COMMAND ----------
# MAGIC %md
# MAGIC ### 3b · Sensor readings (time-series telemetry)

# COMMAND ----------
sr = 10_000
start = pd.Timestamp("2026-06-01")
sensor_readings = pd.DataFrame({
    "reading_id": np.arange(1, sr + 1),
    "machine_id": rng.choice(machine_ids, sr),
    "ts": start + pd.to_timedelta(rng.integers(0, 30 * 24 * 60, sr), unit="m"),
    "temperature_c": np.round(rng.normal(65, 8, sr), 2),
    "vibration_mm_s": np.round(np.abs(rng.normal(2.5, 1.0, sr)), 3),
    "load_pct": np.round(rng.uniform(20, 100, sr), 1),
})
sensor_readings.head()

# COMMAND ----------
# MAGIC %md
# MAGIC ### 3c · Production orders

# COMMAND ----------
po = 200
due = pd.Timestamp("2026-07-01") + pd.to_timedelta(rng.integers(0, 60, po), unit="D")
production_orders = pd.DataFrame({
    "order_id": np.arange(1, po + 1),
    "machine_id": rng.choice(machine_ids, po),
    "product": rng.choice(PRODUCTS, po),
    "qty": rng.integers(10, 500, po),
    "status": rng.choice(["open", "running", "done"], po, p=[0.3, 0.4, 0.3]),
    "due_date": [d.date() for d in due],
})
production_orders.head()

# COMMAND ----------
# MAGIC %md
# MAGIC ### 3d · Maintenance tickets (seeded history)
# MAGIC
# MAGIC These are the *seeded* tickets. Later, the app writes **new** tickets to a separate
# MAGIC table (because synced tables are read-only) — that's the round-trip.

# COMMAND ----------
mt = 120
opened = pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.integers(0, 40 * 24 * 60, mt), unit="m")
maintenance_tickets = pd.DataFrame({
    "ticket_id": np.arange(1, mt + 1),
    "machine_id": rng.choice(machine_ids, mt),
    "opened_at": opened,
    "priority": rng.choice(["low", "medium", "high"], mt, p=[0.5, 0.35, 0.15]),
    "status": rng.choice(["open", "closed"], mt, p=[0.4, 0.6]),
    "description": rng.choice(FAULTS, mt),
})
maintenance_tickets.head()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3.5 · Seed the story — a few machines that *need attention*
# MAGIC Deterministically plant four machines with elevated vibration **and** an open,
# MAGIC high-priority ticket, so the app opens like a real maintenance cockpit ("these need a
# MAGIC technician now"). See `docs/scenario.md`.

# COMMAND ----------
# machine_id -> the fault the technician sees
WATCHLIST = {
    7:  "vibration alarm — bearing wear",
    19: "coolant low",
    31: "laser calibration drift",
    44: "spindle overheating",
}

# 1) push recent vibration for these machines well above the ~2.5 mm/s norm
alarm = sensor_readings["machine_id"].isin(WATCHLIST)
sensor_readings.loc[alarm, "vibration_mm_s"] = (sensor_readings.loc[alarm, "vibration_mm_s"] + 3.0).round(3)

# 2) make one open, high-priority ticket per watchlist machine (overwrite existing rows so
#    the row count stays 120 — nothing downstream changes)
for i, (mid, fault) in enumerate(WATCHLIST.items()):
    maintenance_tickets.loc[i, ["machine_id", "priority", "status", "description"]] = [mid, "high", "open", fault]

print("watchlist machines (open high-priority):", list(WATCHLIST))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4 · Write to Delta (Unity Catalog)
# MAGIC
# MAGIC `spark.createDataFrame(pandas_df)` turns each frame into a Spark DataFrame; `.saveAsTable`
# MAGIC persists it as a governed Delta table.

# COMMAND ----------
frames = {
    "machines": machines,
    "sensor_readings": sensor_readings,
    "production_orders": production_orders,
    "maintenance_tickets": maintenance_tickets,
}
for name, pdf in frames.items():
    (spark.createDataFrame(pdf)
        .write.mode("overwrite")
        .saveAsTable(f"{CATALOG}.{schema}.{name}"))
    print(f"wrote {CATALOG}.{schema}.{name}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5 · Verify (this is your test)
# MAGIC
# MAGIC If a count is wrong the cell fails loudly — that's the point.

# COMMAND ----------
EXPECTED = {"machines": 50, "sensor_readings": 10_000, "production_orders": 200, "maintenance_tickets": 120}
for name, expected in EXPECTED.items():
    actual = spark.table(f"{CATALOG}.{schema}.{name}").count()
    assert actual == expected, f"{name}: expected {expected}, got {actual}"
    print(f"OK  {name}: {actual}")
print(f"\n✅ All four tables loaded into {CATALOG}.{schema}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6 · Peek at your data

# COMMAND ----------
display(spark.sql(f"""
  SELECT m.line, count(DISTINCT m.machine_id) AS machines,
         count(t.ticket_id) AS tickets,
         round(avg(t.machine_id),0) AS _
  FROM {CATALOG}.{schema}.machines m
  LEFT JOIN {CATALOG}.{schema}.maintenance_tickets t USING (machine_id)
  GROUP BY m.line ORDER BY m.line
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ### ✅ Done — next: **`02_sync_to_lakebase`**
# MAGIC Your analytical data is in Unity Catalog. Next you'll mirror it into Lakebase Postgres
# MAGIC as read-only synced tables, so an app can serve it operationally.
