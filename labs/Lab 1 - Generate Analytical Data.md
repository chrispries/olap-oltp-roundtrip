# 🏭 Lab 1 – Generate Analytical Data

> 📓 Prefer the notebook? This lab is also [`notebooks/Lab1 - Manufacturing Data Setup.ipynb`](../notebooks/Lab1%20-%20Manufacturing%20Data%20Setup.ipynb) — same code, run it top to bottom.

## 🎯 Learning Objectives
By the end of this lab, you will:
- Create your own **Unity Catalog** schema inside the shared `catalog_workshop` catalog
- Generate a realistic, **reproducible** IoT manufacturing dataset (machines, telemetry, orders, tickets)
- Use a little **exploratory analysis** to spot the machines most at risk of failure
- Land all four tables as governed **Delta tables** — the analytical starting point of the round-trip

## Introduction

Every round-trip needs a source of truth. In this lab you create the **analytical layer** — the
Delta tables that, in a real factory, the data team already owns: machine master data, sensor
telemetry, production orders, and a history of maintenance tickets.

Everything is generated from a **fixed random seed** (`np.random.seed(42)`), so your tables look
identical on every run and match everyone else's.

```
catalog_workshop
  └─ schema_{your_name}
       ├─ machines (50 rows)
       ├─ sensor_readings (10,000 rows)
       ├─ production_orders (200 rows)
       └─ maintenance_tickets (120 rows)
```

> New to the concepts? Read [`docs/concepts.md`](../docs/concepts.md) (10 min) first.

## Instructions

Run the cells below in order in a **serverless Python notebook** in your Git folder. This lab is
self-contained — you can run it top to bottom in a fresh session.

### Step 1 — Create your catalog and schema

Everyone shares the `catalog_workshop` catalog but gets their **own schema**, derived from your
username, so nobody overwrites anyone else's tables.

```python
import re

# Define catalog and schema names
CATALOG = "catalog_workshop"  # Shared catalog for workshop
user = spark.sql("SELECT current_user()").first()[0]

# Create a unique schema name from your email (removes dots, special chars)
# Example: user.name@company.com -> username -> schema_username
slug = re.sub(r"[^a-z0-9]", "", user.split("@")[0].lower())
schema = f"schema_{slug}"

# Create the Unity Catalog structure
# IF NOT EXISTS prevents errors if already created
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema}")

print(f"✅ Your target location: {CATALOG}.{schema}")
print(f"   All tables will be created here as Delta tables")
```

> **📌 Note your schema name.** The slug strips *everything* that isn't a letter or digit
> (including dots and underscores), so `jane.doe@acme.com` → schema **`schema_janedoe`**. Every
> later lab derives the exact same name the same way, so they all line up.

### Step 2 — Generate the manufacturing dataset

Four related tables, all from one seeded generator so the output is identical every run:

- **`machines`** (50) — the equipment inventory: model, production line, install date, building.
- **`sensor_readings`** (10,000) — IoT telemetry: temperature, vibration, load, every 5 minutes.
- **`production_orders`** (200) — what each machine is scheduled to build.
- **`maintenance_tickets`** (120) — preventive and corrective maintenance history.

Notice how **`machine_id`** is the foreign key threading through all four tables.

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set random seed for reproducibility - same data every time you run this
np.random.seed(42)

# ─── 1. MACHINES TABLE ───
# 50 production machines across 3 production lines
# This is your "dimension table" - describes the equipment
machines = pd.DataFrame({
    'machine_id': range(1, 51),  # Primary key: unique ID for each machine
    'model': np.random.choice(['CNC-X1000', 'Lathe-Z500', 'Press-M200', 'Welder-A300'], 50),
    'line': np.random.choice(['Line-A', 'Line-B', 'Line-C'], 50),
    'install_date': pd.to_datetime('2020-01-01') + pd.to_timedelta(np.random.randint(0, 1000, 50), unit='D'),
    'location': np.random.choice(['Building-1', 'Building-2'], 50)
})

# ─── 2. SENSOR READINGS TABLE ───
# 10,000 IoT sensor readings over the last 30 days
# This is your "fact table" - time-series measurements
base_time = datetime.now() - timedelta(days=30)
sensor_readings = pd.DataFrame({
    'reading_id': range(1, 10001),  # Primary key
    'machine_id': np.random.randint(1, 51, 10000),  # Foreign key -> machines
    'ts': [base_time + timedelta(minutes=i*5) for i in range(10000)],  # One reading every 5 min
    'temperature_c': np.random.uniform(50, 90, 10000).round(1),  # Celsius
    'vibration_mm_s': np.random.uniform(0.5, 8.0, 10000).round(2),  # mm/s (high = bad)
    'load_pct': np.random.uniform(20, 95, 10000).round(1)  # Percentage of max capacity
})

# ─── 3. PRODUCTION ORDERS TABLE ───
# 200 manufacturing orders assigned to machines
# Links machines to what they're producing
production_orders = pd.DataFrame({
    'order_id': range(1001, 1201),  # Primary key: order number
    'machine_id': np.random.randint(1, 51, 200),  # Foreign key -> machines
    'product': np.random.choice(['Widget-A', 'Widget-B', 'Gear-X', 'Shaft-Y'], 200),
    'qty': np.random.randint(50, 500, 200),  # Quantity to manufacture
    'status': np.random.choice(['pending', 'in_progress', 'completed'], 200, p=[0.2, 0.3, 0.5]),
    'due_date': pd.to_datetime('2026-07-15') + pd.to_timedelta(np.random.randint(0, 60, 200), unit='D')
})

# ─── 4. MAINTENANCE TICKETS TABLE ───
# 120 maintenance tickets over the last 60 days
# Tracks both preventive maintenance and emergency repairs
ticket_base = datetime.now() - timedelta(days=60)
maintenance_tickets = pd.DataFrame({
    'ticket_id': range(1, 121),  # Primary key
    'machine_id': np.random.randint(1, 51, 120),  # Foreign key -> machines
    'opened_at': [ticket_base + timedelta(hours=i*12) for i in range(120)],  # One ticket every 12 hours
    'priority': np.random.choice(['low', 'medium', 'high', 'critical'], 120, p=[0.3, 0.4, 0.2, 0.1]),
    'status': np.random.choice(['open', 'in_progress', 'resolved'], 120, p=[0.3, 0.3, 0.4]),
    'description': np.random.choice([
        'Unusual vibration detected',
        'Temperature spike',
        'Scheduled maintenance',
        'Belt replacement needed',
        'Calibration required'
    ], 120)
})

# Summary of generated data
print("✅ Generated sample data:")
print(f"   • machines: {len(machines):,} rows")
print(f"   • sensor_readings: {len(sensor_readings):,} rows")
print(f"   • production_orders: {len(production_orders):,} rows")
print(f"   • maintenance_tickets: {len(maintenance_tickets):,} rows")
print(f"\n🔍 Preview the data below - notice how machine_id appears in all tables!")

# Preview each table (first 5 rows)
display(machines.head())
display(sensor_readings.head())
display(production_orders.head())
display(maintenance_tickets.head())
```

### Step 3 — Find the machines at risk

Before loading, a quick bit of **exploratory analysis**. A machine showing **both** high
vibration (> 6.0 mm/s, a mechanical warning) **and** high temperature (> 80 °C, overheating) is a
strong candidate for preventive maintenance. This is exactly the kind of early-warning signal the
operational app in Lab 3 helps people act on.

```python
# Filter for dangerous conditions: high vibration AND high temperature
# The & operator means BOTH conditions must be true
high_risk = sensor_readings[
    (sensor_readings['vibration_mm_s'] > 6.0) &   # Vibration threshold
    (sensor_readings['temperature_c'] > 80)       # Temperature threshold
]['machine_id'].unique()[:4].tolist()  # Get first 4 unique machine IDs

print(f"⚠️  High-risk machines (need immediate attention): {high_risk}")
print(f"   These {len(high_risk)} machines showed both high vibration and temperature")
print(f"\n🔍 Try this: Change the thresholds above and re-run to find different machines!")
```

### Step 4 — Write the tables to Unity Catalog

Save each pandas DataFrame as a governed **Delta table** in your schema, verifying the row count
as you go.

```python
# Write all tables to Unity Catalog as Delta tables
# Loop through each DataFrame and save it
for name, df in [
    ('machines', machines),
    ('sensor_readings', sensor_readings),
    ('production_orders', production_orders),
    ('maintenance_tickets', maintenance_tickets)
]:
    # Convert pandas DataFrame to Spark DataFrame (required for Delta tables)
    sdf = spark.createDataFrame(df)
    
    # Write to Unity Catalog as a Delta table
    # mode('overwrite') replaces the table if it exists
    sdf.write.mode('overwrite').saveAsTable(f"{CATALOG}.{schema}.{name}")
    
    # Verify the write succeeded by counting rows
    count = spark.table(f"{CATALOG}.{schema}.{name}").count()
    print(f"✅ {name:25s} {count:,} rows")

print(f"\n✅ All four tables loaded into {CATALOG}.{schema}")
print(f"   Tables are now stored as Delta format with full ACID guarantees")

# Preview one of the tables to confirm it's readable
print(f"\n🔍 Sample from maintenance_tickets:")
pdf = spark.table(f"{CATALOG}.{schema}.maintenance_tickets").limit(5).toPandas()
display(pdf)
```

### Step 5 — Verify the structure

```python
# Display the Unity Catalog structure we just created
print("="*70)
print(f"✅ LAB 1 COMPLETE - UNITY CATALOG STRUCTURE")
print("="*70)

print(f"\n💾 Your data location: {CATALOG}.{schema}\n")

# Show all schemas in the catalog
schemas = spark.sql(f"SHOW SCHEMAS IN {CATALOG}").collect()
print(f"📁 Catalog: {CATALOG}")

for s in schemas:
    schema_name = s.databaseName
    # Skip system schemas
    if schema_name not in ['default', 'information_schema']:
        tables = spark.sql(f"SHOW TABLES IN {CATALOG}.{schema_name}").collect()
        
        # Highlight YOUR schema
        if schema_name == schema:
            print(f"\n  ✅ {schema_name} (YOUR SCHEMA - your source tables from Lab1)")
        else:
            print(f"\n  📂 {schema_name}")
        
        if tables:
            for t in tables:
                count = spark.table(f"{CATALOG}.{schema_name}.{t.tableName}").count()
                print(f"     ├─ {t.tableName:30s} {count:,} rows")
        else:
            print(f"     └─ (empty)")

print(f"\n" + "="*70)
print(f"✅ SUCCESS! All 4 tables created and ready for Lab2.")
print("="*70)
```

**✅ Check:** you see `machines: 50`, `sensor_readings: 10,000`, `production_orders: 200`,
`maintenance_tickets: 120`. Open **Catalog ▸ `catalog_workshop` ▸ your schema** and you'll see the
four tables.

**💡 What just happened?**

- **Technically:** you created a Unity Catalog schema and wrote four related Delta tables into it
  — a small but complete analytical model (a parent `machines` table plus telemetry, orders, and
  tickets that reference it via `machine_id`). Because it's generated from a fixed seed, the data
  is reproducible; because it's Delta in Unity Catalog, it's governed, versioned, and ready to be
  synced.
- **In the scenario:** this is the data the factory's **data team already has** — the lakehouse
  side of the story. It's perfect for analytics (OEE reporting, a vibration-based failure model),
  but it's not yet in front of the people on the floor. Your quick EDA already surfaced the
  machines running hot and shaking — exactly what the operational app in Lab 3 needs to make
  visible.

➡️ **Next: [Lab 2 – Sync to Lakebase](Lab%202%20-%20Sync%20to%20Lakebase.md).**
