# App + Lakebase in a Day — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a 90-minute hands-on workshop proving the Databricks Apps + Lakebase round-trip (Unity Catalog → Lakebase → Streamlit app → write-back → Unity Catalog) on synthetic manufacturing/IoT data, verified live on the Azure FE workspace.

**Architecture:** A per-attendee Unity Catalog schema is populated with four Delta tables by a data-gen notebook. Those tables are snapshot-synced into per-user databases on one shared Lakebase Postgres instance as read-only synced tables. A Streamlit Databricks App reads the synced tables and writes maintenance tickets to an app-owned Postgres table. Because the Lakebase instance is registered in Unity Catalog, the app's writes are queryable live from Databricks SQL — closing the round-trip.

**Tech Stack:** Python 3.11, pandas + numpy (data generation), Databricks CLI + SDK, Spark (UC writes, in-notebook), Lakebase (Postgres 16), psycopg 3, Streamlit, Databricks Apps, Databricks SQL / AI-BI dashboards. pytest + pytest-postgresql for local tests.

## Global Constraints

- **Target workspace:** Azure FE, Databricks CLI profile `azure-demo` (`https://adb-984752964297111.11.azuredatabricks.net`). All `databricks` commands use `-p azure-demo`.
- **Authoritative CLI references (do not fabricate commands):** use the `fe-databricks-tools:databricks-authentication` skill for auth, `fe-databricks-tools:databricks-lakebase` for all Lakebase instance / synced-table / Postgres commands, `fe-databricks-tools:databricks-apps` (and the `databricks-apps-developer` agent) for app scaffolding/deploy, `fe-databricks-tools:databricks-lakeview-dashboard` for the dashboard. When a step says "per the databricks-lakebase skill", read that skill for the exact current command rather than guessing.
- **UC catalog:** `lakebase_workshop`. **Per-user schema:** `ws_${user}` where `${user}` = the sanitized local-part of the attendee email (lowercase, non-alphanumeric → `_`). Derive via `current_user()` in-notebook.
- **Delta table names (all lowercase):** `machines`, `sensor_readings`, `production_orders`, `maintenance_tickets`.
- **Lakebase instance:** `lakebase-workshop` (one shared instance). **Per-user Postgres database:** `ws_${user}`. **Synced table names** mirror the Delta names. **App-owned table:** `app_maintenance_tickets`.
- **App name:** `lakebase-workshop-${user}`.
- **Sync mode:** SNAPSHOT (one-time) for the forward sync. Continuous is a talking point only.
- **Data volume (seeded, deterministic, `SEED=42`):** 50 machines, 10,000 sensor_readings, 200 production_orders, 120 maintenance_tickets.
- **Determinism:** all generators seeded so every attendee/run produces identical data (simplifies support and screenshots).
- **Write-back is the one guided gap:** in the attendee build, `create_maintenance_ticket()` in `app/db.py` ships with its body stubbed and a `# TODO (workshop)` marker; the full implementation lives in `docs/solutions/`. All other code ships complete.
- **Commit cadence:** commit at the end of every task. Do not push until the owner (Christopher) asks.

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `pyproject.toml` | Project metadata, deps, pytest config |
| `data_gen/generate.py` | Pure functions returning pandas DataFrames for the 4 tables (locally testable, no Spark) |
| `data_gen/load_to_uc.py` | Databricks notebook: derive user, create catalog/schema, call `generate`, write Delta tables via Spark |
| `tests/test_generate.py` | Unit tests for generation (schema, row counts, determinism, referential integrity) |
| `sync/create_lakebase.md` | Runbook: create shared instance + per-user DB (UI + CLI via databricks-lakebase skill) |
| `sync/create_synced_tables.md` | Runbook: create the 4 snapshot synced tables (UI + CLI) |
| `app/app.py` | Streamlit UI: machine health, open tickets, "new ticket" form |
| `app/db.py` | Postgres access: `get_connection()`, read helpers, `create_maintenance_ticket()` (the guided gap) |
| `app/app.yaml` | Databricks App config incl. Lakebase resource binding |
| `app/requirements.txt` | App runtime deps (streamlit, psycopg[binary], databricks-sdk) |
| `tests/test_db.py` | Unit tests for `create_maintenance_ticket()` against ephemeral Postgres |
| `analytics/roundtrip_query.sql` | The "see the write-back in UC" query |
| `analytics/dashboard.md` | Runbook to build the small AI/BI dashboard (stretch) |
| `docs/attendee-runbook.md` | Step-by-step attendee instructions mirroring the agenda |
| `docs/facilitator-notes.md` | Setup, prerequisites, failure modes, timing, teardown |
| `docs/solutions/create_maintenance_ticket.py` | The completed write-back function (facilitator answer key) |

---

## Task 0: Project scaffold, dependencies, and Azure FE auth

**Files:**
- Create: `pyproject.toml`, `data_gen/__init__.py`, `app/__init__.py`, `tests/__init__.py`
- Modify: none

**Interfaces:**
- Consumes: nothing.
- Produces: a working Python env with `pytest`, `pandas`, `numpy`, `psycopg[binary]`, `pytest-postgresql`; a verified `azure-demo` CLI session.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "app-lakebase-in-a-day"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "psycopg[binary]>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-postgresql>=6"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package markers**

Create empty `data_gen/__init__.py`, `app/__init__.py`, `tests/__init__.py`.

- [ ] **Step 3: Create venv and install**

Run:
```bash
cd ~/Projects/app-lakebase-in-a-day
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```
Expected: installs without error; `pytest --version` prints a version.

- [ ] **Step 4: Verify Azure FE auth**

Follow the `fe-databricks-tools:databricks-authentication` skill, then run:
```bash
databricks -p azure-demo current-user me --output json | python3 -c "import sys,json; print(json.load(sys.stdin)['userName'])"
```
Expected: prints `christopher.pries@databricks.com` (or the logged-in user). If it fails, re-auth per the skill before continuing.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml data_gen/__init__.py app/__init__.py tests/__init__.py
git commit -m "chore: project scaffold and dependencies"
```

---

## Task 1: Synthetic data generator (pure, testable)

**Files:**
- Create: `data_gen/generate.py`
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `generate_all(seed: int = 42) -> dict[str, pandas.DataFrame]` returning keys `machines`, `sensor_readings`, `production_orders`, `maintenance_tickets`. Column contracts:
  - `machines`: `machine_id` (int, 1..50), `model` (str), `line` (str), `install_date` (date), `location` (str)
  - `sensor_readings`: `reading_id` (int), `machine_id` (int FK), `ts` (timestamp), `temperature_c` (float), `vibration_mm_s` (float), `load_pct` (float)
  - `production_orders`: `order_id` (int), `machine_id` (int FK), `product` (str), `qty` (int), `status` (str in {open, running, done}), `due_date` (date)
  - `maintenance_tickets`: `ticket_id` (int), `machine_id` (int FK), `opened_at` (timestamp), `priority` (str in {low, medium, high}), `status` (str in {open, closed}), `description` (str)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generate.py
from data_gen.generate import generate_all

EXPECTED_COUNTS = {
    "machines": 50,
    "sensor_readings": 10_000,
    "production_orders": 200,
    "maintenance_tickets": 120,
}

def test_tables_and_counts():
    data = generate_all(seed=42)
    assert set(data) == set(EXPECTED_COUNTS)
    for name, n in EXPECTED_COUNTS.items():
        assert len(data[name]) == n, name

def test_machine_columns():
    cols = list(generate_all(seed=42)["machines"].columns)
    assert cols == ["machine_id", "model", "line", "install_date", "location"]

def test_referential_integrity():
    data = generate_all(seed=42)
    machine_ids = set(data["machines"]["machine_id"])
    for child in ["sensor_readings", "production_orders", "maintenance_tickets"]:
        assert set(data[child]["machine_id"]).issubset(machine_ids), child

def test_deterministic():
    a = generate_all(seed=42)["sensor_readings"]
    b = generate_all(seed=42)["sensor_readings"]
    assert a.equals(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'data_gen.generate'`.

- [ ] **Step 3: Write minimal implementation**

```python
# data_gen/generate.py
from __future__ import annotations
import numpy as np
import pandas as pd

MODELS = ["TruLaser 3030", "TruBend 5130", "TruPunch 5000", "TruMatic 6000"]
LINES = ["Line-A", "Line-B", "Line-C"]
LOCATIONS = ["Ditzingen", "Neukirch", "Hettingen", "Grüsch"]
PRODUCTS = ["bracket", "panel", "housing", "flange", "rail"]

def _machines(rng: np.random.Generator, n: int = 50) -> pd.DataFrame:
    return pd.DataFrame({
        "machine_id": np.arange(1, n + 1),
        "model": rng.choice(MODELS, n),
        "line": rng.choice(LINES, n),
        "install_date": pd.to_datetime("2018-01-01") + pd.to_timedelta(rng.integers(0, 2500, n), unit="D"),
        "location": rng.choice(LOCATIONS, n),
    }).assign(install_date=lambda d: d["install_date"].dt.date)

def _sensor_readings(rng, machine_ids, n: int = 10_000) -> pd.DataFrame:
    start = pd.Timestamp("2026-06-01")
    return pd.DataFrame({
        "reading_id": np.arange(1, n + 1),
        "machine_id": rng.choice(machine_ids, n),
        "ts": start + pd.to_timedelta(rng.integers(0, 30 * 24 * 60, n), unit="m"),
        "temperature_c": np.round(rng.normal(65, 8, n), 2),
        "vibration_mm_s": np.round(np.abs(rng.normal(2.5, 1.0, n)), 3),
        "load_pct": np.round(rng.uniform(20, 100, n), 1),
    })

def _production_orders(rng, machine_ids, n: int = 200) -> pd.DataFrame:
    due = pd.Timestamp("2026-07-01") + pd.to_timedelta(rng.integers(0, 60, n), unit="D")
    return pd.DataFrame({
        "order_id": np.arange(1, n + 1),
        "machine_id": rng.choice(machine_ids, n),
        "product": rng.choice(PRODUCTS, n),
        "qty": rng.integers(10, 500, n),
        "status": rng.choice(["open", "running", "done"], n, p=[0.3, 0.4, 0.3]),
        "due_date": due.date if hasattr(due, "date") else [d.date() for d in due],
    })

def _maintenance_tickets(rng, machine_ids, n: int = 120) -> pd.DataFrame:
    opened = pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.integers(0, 40 * 24 * 60, n), unit="m")
    return pd.DataFrame({
        "ticket_id": np.arange(1, n + 1),
        "machine_id": rng.choice(machine_ids, n),
        "opened_at": opened,
        "priority": rng.choice(["low", "medium", "high"], n, p=[0.5, 0.35, 0.15]),
        "status": rng.choice(["open", "closed"], n, p=[0.4, 0.6]),
        "description": rng.choice(
            ["coolant low", "vibration alarm", "laser calibration", "belt wear", "sensor fault"], n),
    })

def generate_all(seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    machines = _machines(rng)
    ids = machines["machine_id"].to_numpy()
    return {
        "machines": machines,
        "sensor_readings": _sensor_readings(rng, ids),
        "production_orders": _production_orders(rng, ids),
        "maintenance_tickets": _maintenance_tickets(rng, ids),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_generate.py -v`
Expected: 4 passed. If `production_orders.due_date` fails on the `.date` branch, replace that line with `"due_date": [d.date() for d in due]` and re-run.

- [ ] **Step 5: Commit**

```bash
git add data_gen/generate.py tests/test_generate.py
git commit -m "feat: deterministic synthetic manufacturing data generator"
```

---

## Task 2: Load the data into Unity Catalog on Azure FE

**Files:**
- Create: `data_gen/load_to_uc.py` (Databricks notebook source, `# Databricks notebook source` header)

**Interfaces:**
- Consumes: `data_gen.generate.generate_all`.
- Produces: on Azure FE, catalog `lakebase_workshop`, schema `ws_${user}`, and the four Delta tables populated. Later tasks reference these fully-qualified names.

- [ ] **Step 1: Write the notebook**

```python
# Databricks notebook source
# MAGIC %md # Data-gen → Unity Catalog
# COMMAND ----------
import re
from data_gen.generate import generate_all  # if repo synced as workspace files; else paste generate.py inline

user = spark.sql("select current_user()").first()[0]
schema = "ws_" + re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())
catalog = "lakebase_workshop"

spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"USE {catalog}.{schema}")

data = generate_all(seed=42)
for name, pdf in data.items():
    spark.createDataFrame(pdf).write.mode("overwrite").saveAsTable(f"{catalog}.{schema}.{name}")
    print(name, spark.table(f"{catalog}.{schema}.{name}").count())
```

Note for the executor: Databricks Apps/Repos can import the repo as workspace files so `from data_gen.generate import generate_all` resolves. If import is unavailable in the target runtime, inline the contents of `generate.py` into a cell above (the facilitator-notes task documents this fallback).

- [ ] **Step 2: Import repo into the workspace and run the notebook**

Per the `fe-databricks-tools:databricks-workspace-files` and `databricks-resource-deployment` skills, sync the repo to the workspace (Git folder or `databricks sync`) and run `data_gen/load_to_uc.py` on serverless with profile `azure-demo`.

- [ ] **Step 3: Verify the tables exist with correct counts**

Run:
```bash
databricks -p azure-demo sql query --warehouse-id <WH_ID> \
  --query "SELECT 'machines' t, count(*) c FROM lakebase_workshop.ws_christopher_pries.machines
           UNION ALL SELECT 'sensor_readings', count(*) FROM lakebase_workshop.ws_christopher_pries.sensor_readings
           UNION ALL SELECT 'production_orders', count(*) FROM lakebase_workshop.ws_christopher_pries.production_orders
           UNION ALL SELECT 'maintenance_tickets', count(*) FROM lakebase_workshop.ws_christopher_pries.maintenance_tickets"
```
(Use `databricks -p azure-demo warehouses list` to get `<WH_ID>`; substitute your own `ws_...` schema.)
Expected: counts 50 / 10000 / 200 / 120.

- [ ] **Step 4: Commit**

```bash
git add data_gen/load_to_uc.py
git commit -m "feat: notebook to load synthetic data into Unity Catalog"
```

---

## Task 3: Provision shared Lakebase instance, per-user DB, and snapshot synced tables

**Files:**
- Create: `sync/create_lakebase.md`, `sync/create_synced_tables.md`

**Interfaces:**
- Consumes: the UC tables from Task 2.
- Produces: Lakebase instance `lakebase-workshop`; per-user database `ws_${user}`; four read-only snapshot synced tables mirroring the Delta tables; the instance registered as a UC catalog (record its catalog name — needed by Task 6). Record the Postgres host/port/database and the OAuth-based connection method the app will use (Task 4/5).

- [ ] **Step 1: Create the shared Lakebase instance**

Follow the `fe-databricks-tools:databricks-lakebase` skill to create instance `lakebase-workshop` on `azure-demo`. Write the exact commands you used into `sync/create_lakebase.md` (both UI walkthrough and CLI), plus how to create the per-user database `ws_${user}`.

- [ ] **Step 2: Create the four snapshot synced tables**

Per the databricks-lakebase skill, create SNAPSHOT synced tables from each `lakebase_workshop.ws_${user}.<table>` into the per-user Postgres database. Document exact steps (UI + CLI) in `sync/create_synced_tables.md`.

- [ ] **Step 3: Verify serving reads from Postgres**

Connect to the Lakebase Postgres per the skill and run:
```sql
SELECT count(*) FROM machines;
SELECT count(*) FROM sensor_readings;
```
Expected: 50 and 10000. Record the connection recipe in `sync/create_lakebase.md`.

- [ ] **Step 4: Confirm the Lakebase instance is registered as a UC catalog**

Run:
```bash
databricks -p azure-demo catalogs list --output json | python3 -c "import sys,json;[print(c['name']) for c in json.load(sys.stdin)]"
```
Expected: the Lakebase-backed catalog appears. Record its exact name in `sync/create_synced_tables.md` (Task 6 queries `<lakebase_catalog>.ws_${user}.app_maintenance_tickets`).

- [ ] **Step 5: Commit**

```bash
git add sync/create_lakebase.md sync/create_synced_tables.md
git commit -m "docs: Lakebase instance and snapshot synced-table runbooks"
```

---

## Task 4: Streamlit app — read path, deployed on Databricks Apps

**Files:**
- Create: `app/app.py`, `app/db.py`, `app/app.yaml`, `app/requirements.txt`

**Interfaces:**
- Consumes: synced tables in Postgres (Task 3).
- Produces: `db.get_connection()` returning a live `psycopg.Connection`; `db.list_machines(conn)`, `db.open_tickets(conn)` returning `list[dict]`; a deployed app `lakebase-workshop-${user}` showing machine health and open tickets. `db.ensure_app_table(conn)` creates `app_maintenance_tickets` if absent.

- [ ] **Step 1: Write `app/requirements.txt`**

```
streamlit>=1.40
psycopg[binary]>=3.1
databricks-sdk>=0.40
```

- [ ] **Step 2: Write `app/db.py` (read path + table bootstrap; write-back stubbed)**

```python
import os
import psycopg

APP_TABLE = "app_maintenance_tickets"

def get_connection() -> psycopg.Connection:
    """Connect to Lakebase Postgres. On Databricks Apps the Lakebase resource
    injects PGHOST/PGPORT/PGDATABASE/PGUSER and a short-lived PGPASSWORD (OAuth token).
    See sync/create_lakebase.md for the exact resource binding."""
    return psycopg.connect(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        sslmode="require",
    )

def ensure_app_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {APP_TABLE} (
                ticket_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                machine_id  bigint NOT NULL,
                opened_at   timestamptz NOT NULL DEFAULT now(),
                priority    text NOT NULL,
                status      text NOT NULL DEFAULT 'open',
                description text NOT NULL
            )""")
        conn.commit()

def list_machines(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT machine_id, model, line, location FROM machines ORDER BY machine_id")
        return cur.fetchall()

def open_tickets(conn: psycopg.Connection) -> list[dict]:
    """Union of seeded (read-only synced) tickets and app-written tickets that are open."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(f"""
            SELECT machine_id, priority, description, opened_at FROM maintenance_tickets WHERE status='open'
            UNION ALL
            SELECT machine_id, priority, description, opened_at FROM {APP_TABLE} WHERE status='open'
            ORDER BY opened_at DESC""")
        return cur.fetchall()

def create_maintenance_ticket(conn: psycopg.Connection, machine_id: int,
                              priority: str, description: str) -> int:
    """WORKSHOP GAP — attendees implement this in Task 5.
    Insert a row into APP_TABLE and return the new ticket_id."""
    raise NotImplementedError("TODO (workshop): implement create_maintenance_ticket")
```

- [ ] **Step 3: Write `app/app.py`**

```python
import streamlit as st
import db

st.set_page_config(page_title="Shop-Floor Maintenance", layout="wide")
st.title("🔧 Shop-Floor Maintenance")

conn = db.get_connection()
db.ensure_app_table(conn)

left, right = st.columns(2)
with left:
    st.subheader("Machines")
    st.dataframe(db.list_machines(conn), use_container_width=True)
with right:
    st.subheader("Open tickets")
    st.dataframe(db.open_tickets(conn), use_container_width=True)

st.divider()
st.subheader("Report a maintenance ticket")
with st.form("new_ticket"):
    machine_id = st.number_input("Machine ID", min_value=1, max_value=50, step=1)
    priority = st.selectbox("Priority", ["low", "medium", "high"])
    description = st.text_input("Description")
    submitted = st.form_submit_button("Create ticket")
    if submitted:
        try:
            tid = db.create_maintenance_ticket(conn, int(machine_id), priority, description)
            st.success(f"Created ticket #{tid}")
        except NotImplementedError:
            st.warning("Write-back not implemented yet — complete create_maintenance_ticket() (Task 5).")
```

- [ ] **Step 4: Write `app/app.yaml`**

Use the `fe-databricks-tools:databricks-apps` skill for the current schema. Minimum: command to run Streamlit, and a **Lakebase resource** binding the app to instance `lakebase-workshop` / database `ws_${user}` so PG env vars are injected.

```yaml
command: ["streamlit", "run", "app.py"]
```

(Add the `resources:` Lakebase database block exactly as the databricks-apps skill specifies; record the final YAML.)

- [ ] **Step 5: Deploy and verify the read path**

Per the databricks-apps skill / `databricks-apps-developer` agent, deploy `lakebase-workshop-${user}` to `azure-demo`. Open the app URL.
Expected: Machines table shows 50 rows; Open tickets shows seeded open tickets; the "Create ticket" form shows the "not implemented yet" warning on submit.

- [ ] **Step 6: Commit**

```bash
git add app/app.py app/db.py app/app.yaml app/requirements.txt
git commit -m "feat: Streamlit app read path deployed on Databricks Apps"
```

---

## Task 5: The write-back (guided gap) — TDD against ephemeral Postgres

**Files:**
- Modify: `app/db.py` (implement `create_maintenance_ticket`)
- Test: `tests/test_db.py`
- Create: `docs/solutions/create_maintenance_ticket.py`

**Interfaces:**
- Consumes: `db.ensure_app_table`, `db.APP_TABLE`.
- Produces: `create_maintenance_ticket(conn, machine_id, priority, description) -> int` inserts one row into `app_maintenance_tickets` and returns the generated `ticket_id`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
import psycopg
import pytest
from app import db

@pytest.fixture
def conn(postgresql):  # pytest-postgresql provides `postgresql`
    dsn = f"host={postgresql.info.host} port={postgresql.info.port} dbname={postgresql.info.dbname} user={postgresql.info.user}"
    with psycopg.connect(dsn) as c:
        db.ensure_app_table(c)
        yield c

def test_create_returns_id_and_persists(conn):
    tid = db.create_maintenance_ticket(conn, machine_id=7, priority="high", description="vibration alarm")
    assert isinstance(tid, int) and tid > 0
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(f"SELECT * FROM {db.APP_TABLE} WHERE ticket_id=%s", (tid,))
        row = cur.fetchone()
    assert row["machine_id"] == 7 and row["priority"] == "high" and row["status"] == "open"

def test_two_tickets_distinct_ids(conn):
    a = db.create_maintenance_ticket(conn, 1, "low", "coolant low")
    b = db.create_maintenance_ticket(conn, 1, "low", "coolant low")
    assert a != b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `NotImplementedError: TODO (workshop): implement create_maintenance_ticket`.
(If pytest-postgresql cannot find a local `pg_ctl`, install Postgres client tools per facilitator-notes; the fixture needs a local Postgres binary.)

- [ ] **Step 3: Implement `create_maintenance_ticket`**

```python
def create_maintenance_ticket(conn: psycopg.Connection, machine_id: int,
                              priority: str, description: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {APP_TABLE} (machine_id, priority, description) "
            f"VALUES (%s, %s, %s) RETURNING ticket_id",
            (machine_id, priority, description),
        )
        ticket_id = cur.fetchone()[0]
    conn.commit()
    return ticket_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: 2 passed.

- [ ] **Step 5: Save the answer key and redeploy**

Copy the finished function into `docs/solutions/create_maintenance_ticket.py`. Redeploy the app (Task 4 method) and submit a ticket in the UI.
Expected: "Created ticket #N"; the new ticket appears under Open tickets.

- [ ] **Step 6: Commit**

```bash
git add app/db.py tests/test_db.py docs/solutions/create_maintenance_ticket.py
git commit -m "feat: implement maintenance-ticket write-back (workshop solution)"
```

---

## Task 6: Close the round-trip — query the write-back from Databricks SQL

**Files:**
- Create: `analytics/roundtrip_query.sql`, `analytics/dashboard.md`

**Interfaces:**
- Consumes: the Lakebase UC catalog name recorded in Task 3; `app_maintenance_tickets` written in Task 5.
- Produces: a query that returns app-written tickets from the analytical layer; a stretch dashboard runbook.

- [ ] **Step 1: Write `analytics/roundtrip_query.sql`**

```sql
-- Replace <lakebase_catalog> with the catalog recorded in sync/create_synced_tables.md
-- and ws_${user} with your schema/database.
SELECT ticket_id, machine_id, priority, status, description, opened_at
FROM <lakebase_catalog>.ws_christopher_pries.app_maintenance_tickets
ORDER BY opened_at DESC;
```

- [ ] **Step 2: Verify the round-trip in Databricks SQL**

Create a ticket in the deployed app, then run the query via `databricks -p azure-demo sql query --warehouse-id <WH_ID> --query "$(cat analytics/roundtrip_query.sql | sed 's/<lakebase_catalog>/<real>/')"`.
Expected: the just-created ticket appears — proving app writes are live in the analytical layer.

- [ ] **Step 3: Write the stretch dashboard runbook**

In `analytics/dashboard.md`, document (per the `fe-databricks-tools:databricks-lakeview-dashboard` skill) a one-page AI/BI dashboard with: open-tickets-by-priority bar, tickets-over-time line (including app writes), and a machines table. Mark it clearly as optional/stretch.

- [ ] **Step 4: Commit**

```bash
git add analytics/roundtrip_query.sql analytics/dashboard.md
git commit -m "feat: round-trip analytics query and dashboard runbook"
```

---

## Task 7: Attendee runbook and facilitator notes

**Files:**
- Create: `docs/attendee-runbook.md`, `docs/facilitator-notes.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: the documents attendees and the facilitator follow on the day.

- [ ] **Step 1: Write `docs/attendee-runbook.md`**

Step-by-step mirroring the agenda: (1) clone/import repo, run `load_to_uc.py`; (2) create per-user Lakebase DB + synced tables (link `sync/*.md`); (3) deploy the app; (4) implement `create_maintenance_ticket` (the gap) and redeploy; (5) run `analytics/roundtrip_query.sql`. Every command uses the attendee's own `ws_${user}` — show how to derive it.

- [ ] **Step 2: Write `docs/facilitator-notes.md`**

Cover: prerequisites (workspace access, warehouse id, serverless, Postgres client for local tests), pre-provisioning (shared instance created ahead by facilitator), per-user namespacing, timing per segment, common failure modes (import fallback for `generate.py`, PG env not injected, pytest-postgresql needing local `pg_ctl`, snapshot sync needing manual refresh), the approach-B productionization talking point, and teardown (drop per-user DBs/schemas, delete apps, stop instance).

- [ ] **Step 3: Update `README.md` status**

Change the Status section to reflect assets built and verified on Azure FE; link the runbook and facilitator notes.

- [ ] **Step 4: Commit**

```bash
git add docs/attendee-runbook.md docs/facilitator-notes.md README.md
git commit -m "docs: attendee runbook and facilitator notes"
```

---

## Task 8: End-to-end dry run and timing

**Files:**
- Modify: `docs/facilitator-notes.md` (record timings + fixes)

**Interfaces:**
- Consumes: everything.
- Produces: a validated, timed, single-pass run of the whole workshop on Azure FE from a fresh per-user namespace.

- [ ] **Step 1: Fresh-namespace dry run**

Using a throwaway schema/DB (e.g. `ws_dryrun`), execute the attendee runbook end-to-end on `azure-demo`: load → sync → deploy → implement gap → redeploy → round-trip query. Time each segment.

- [ ] **Step 2: Record results and fix blockers**

In `docs/facilitator-notes.md`, record actual timings vs. the 90-min budget and any fixes made. If any segment blows its budget, note the scope cut (e.g. pre-create synced tables for attendees).

- [ ] **Step 3: Teardown the dry-run artifacts**

Drop `ws_dryrun` schema/DB, delete the dry-run app. Confirm removal.

- [ ] **Step 4: Commit**

```bash
git add docs/facilitator-notes.md
git commit -m "test: end-to-end dry run timings and fixes"
```
