# Databricks notebook source
# MAGIC %md
# MAGIC # Data-gen → Unity Catalog
# MAGIC Populates a per-user schema in the `lakebase_workshop` catalog with four synthetic
# MAGIC manufacturing/IoT tables. Self-contained (no repo import needed). Run on serverless.

# COMMAND ----------
import re
import numpy as np
import pandas as pd

SEED = 42
CATALOG = "lakebase_workshop"

MODELS = ["TruLaser 3030", "TruBend 5130", "TruPunch 5000", "TruMatic 6000"]
LINES = ["Line-A", "Line-B", "Line-C"]
LOCATIONS = ["Ditzingen", "Neukirch", "Hettingen", "Grüsch"]
PRODUCTS = ["bracket", "panel", "housing", "flange", "rail"]
FAULTS = ["coolant low", "vibration alarm", "laser calibration", "belt wear", "sensor fault"]

EXPECTED_COUNTS = {
    "machines": 50,
    "sensor_readings": 10_000,
    "production_orders": 200,
    "maintenance_tickets": 120,
}


def generate_all(seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    n = 50
    machines = pd.DataFrame({
        "machine_id": np.arange(1, n + 1),
        "model": rng.choice(MODELS, n),
        "line": rng.choice(LINES, n),
        "install_date": (pd.to_datetime("2018-01-01") + pd.to_timedelta(rng.integers(0, 2500, n), unit="D")).date,
        "location": rng.choice(LOCATIONS, n),
    })
    machines["install_date"] = pd.to_datetime(machines["install_date"]).dt.date
    ids = machines["machine_id"].to_numpy()

    sr = 10_000
    start = pd.Timestamp("2026-06-01")
    sensor_readings = pd.DataFrame({
        "reading_id": np.arange(1, sr + 1),
        "machine_id": rng.choice(ids, sr),
        "ts": start + pd.to_timedelta(rng.integers(0, 30 * 24 * 60, sr), unit="m"),
        "temperature_c": np.round(rng.normal(65, 8, sr), 2),
        "vibration_mm_s": np.round(np.abs(rng.normal(2.5, 1.0, sr)), 3),
        "load_pct": np.round(rng.uniform(20, 100, sr), 1),
    })

    po = 200
    due = pd.Timestamp("2026-07-01") + pd.to_timedelta(rng.integers(0, 60, po), unit="D")
    production_orders = pd.DataFrame({
        "order_id": np.arange(1, po + 1),
        "machine_id": rng.choice(ids, po),
        "product": rng.choice(PRODUCTS, po),
        "qty": rng.integers(10, 500, po),
        "status": rng.choice(["open", "running", "done"], po, p=[0.3, 0.4, 0.3]),
        "due_date": [d.date() for d in due],
    })

    mt = 120
    opened = pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.integers(0, 40 * 24 * 60, mt), unit="m")
    maintenance_tickets = pd.DataFrame({
        "ticket_id": np.arange(1, mt + 1),
        "machine_id": rng.choice(ids, mt),
        "opened_at": opened,
        "priority": rng.choice(["low", "medium", "high"], mt, p=[0.5, 0.35, 0.15]),
        "status": rng.choice(["open", "closed"], mt, p=[0.4, 0.6]),
        "description": rng.choice(FAULTS, mt),
    })

    return {
        "machines": machines,
        "sensor_readings": sensor_readings,
        "production_orders": production_orders,
        "maintenance_tickets": maintenance_tickets,
    }


# COMMAND ----------
# Derive a per-user schema so 9-20 attendees don't collide.
user = spark.sql("select current_user()").first()[0]
schema = "ws_" + re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())
print(f"user={user}  ->  target = {CATALOG}.{schema}")

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema}")

# COMMAND ----------
data = generate_all()
for name, pdf in data.items():
    spark.createDataFrame(pdf).write.mode("overwrite").saveAsTable(f"{CATALOG}.{schema}.{name}")

# COMMAND ----------
# Inline assertion = the data-gen test (see plan Revision 2026-07-08).
for name, expected in EXPECTED_COUNTS.items():
    actual = spark.table(f"{CATALOG}.{schema}.{name}").count()
    assert actual == expected, f"{name}: expected {expected}, got {actual}"
    print(f"OK {name}: {actual}")
print(f"\n✅ All tables loaded into {CATALOG}.{schema}")
