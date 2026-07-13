# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Deploy the Streamlit app + write-back
# MAGIC
# MAGIC Create and deploy the app that serves your Lakebase data, then complete the one function
# MAGIC that writes tickets back. Runs **in your workspace** via the SDK — no laptop CLI. Safe to
# MAGIC re-run (create is skipped if the app exists; deploy just redeploys).
# MAGIC
# MAGIC ```
# MAGIC (01) UC ──▶ (02) Lakebase ──▶ 👉 (03) app ──▶ (04) round-trip
# MAGIC ```
# MAGIC
# MAGIC No hand-editing needed — Step 1.5 writes your database name into `app/app.yaml` for you.

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.50" "psycopg[binary]>=3.1" -q
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1 · Names + locate the app source
# MAGIC The app code lives in this repo's `app/` folder; since you opened the repo as a Workspace
# MAGIC Git folder, we can point the deploy straight at it.

# COMMAND ----------
import re
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())

PROJECT = "lakebase-workshop"
BRANCH = f"projects/{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
PGDB = f"ws_{slug}"
APP = ("lb-workshop-" + slug.replace("_", "-"))[:30].rstrip("-")

# resolve the app/ source path from this notebook's location in the repo
nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
repo_root = nb.rsplit("/notebooks/", 1)[0]
APP_SRC = f"/Workspace{repo_root}/app"

host = w.postgres.list_endpoints(BRANCH).__next__().as_dict()["status"]["hosts"]["host"]
print(f"user={user}\nPGDB={PGDB}\nAPP={APP}\nAPP_SRC={APP_SRC}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1.5 · Point the app at *your* database
# MAGIC Writes `PGDATABASE=<your ws_ db>` into `app/app.yaml` so you never hand-edit it (and can't
# MAGIC accidentally point at someone else's database). Safe to re-run.

# COMMAND ----------
import re, pathlib

yaml_path = pathlib.Path(f"{APP_SRC}/app.yaml")
txt = yaml_path.read_text()
txt = re.sub(r'(- name: PGDATABASE\n\s*value: )"[^"]*"', rf'\g<1>"{PGDB}"', txt)
yaml_path.write_text(txt)
print(f"✅ set PGDATABASE={PGDB} in {yaml_path}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2 · Read the app (this is what you're here to learn)
# MAGIC - **`app/app.yaml`** — the app config: runs Streamlit on port 8000; passes Lakebase env.
# MAGIC   No password — the app mints one.
# MAGIC - **`app/db.py`** — `get_connection()` mints a fresh OAuth token per connection with
# MAGIC   `w.postgres.generate_database_credential(ENDPOINT_NAME)`. `list_machines`/`open_tickets`
# MAGIC   `open_alerts`/`claim_alert` drive the queue; `resolve_alert` is the gap you fill in Step 6.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3 · Create the app + bind the Lakebase database
# MAGIC Binding the database as a `postgres` **resource** provisions a Postgres role for the app's
# MAGIC service principal and injects the connection env vars.

# COMMAND ----------
from databricks.sdk.service.apps import App, AppDeployment

# find YOUR database's resource id (not the human name) to bind it
dbres = next(d.as_dict()["name"] for d in w.postgres.list_databases(BRANCH)
             if d.as_dict()["status"]["postgres_database"] == PGDB)
print("database resource:", dbres)

app_spec = {
    "name": APP,
    "description": "Lakebase-in-a-Day: shop-floor maintenance app",
    "resources": [{
        "name": "lakebase-db",
        "postgres": {"branch": BRANCH, "database": dbres, "permission": "CAN_CONNECT_AND_CREATE"},
    }],
}
try:
    w.apps.get(name=APP)
    print(f"app {APP} already exists — skipping create")
except Exception:
    print(f"creating {APP} (compute takes a couple minutes)…")
    w.apps.create_and_wait(App.from_dict(app_spec))
    print("✅ app created")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4 · Grant the app's service principal access to the data
# MAGIC Binding the resource (`CAN_CONNECT_AND_CREATE`) lets the app connect and create its own
# MAGIC table — but **not** read the pre-existing synced tables. We grant that once:
# MAGIC - `USAGE, CREATE ON SCHEMA public` — so the app can create its `maintenance_actions` table
# MAGIC - `pg_read_all_data` — SELECT on **all current *and future*** tables (survives re-syncing a
# MAGIC   synced table, unlike a one-time `GRANT SELECT ON ALL TABLES`)
# MAGIC
# MAGIC The app writes only to the table it creates and owns, so it needs no extra write grants.

# COMMAND ----------
import psycopg

sp = w.apps.get(name=APP).as_dict().get("service_principal_client_id")
print("service principal:", sp)
with psycopg.connect(host=host, port=5432, dbname=PGDB, user=user,
                     password=w.postgres.generate_database_credential(ENDPOINT).token,
                     sslmode="require", autocommit=True) as c:
    c.execute(f'GRANT USAGE, CREATE ON SCHEMA public TO "{sp}"')
    c.execute(f'GRANT pg_read_all_data TO "{sp}"')
print("✅ app service principal can read all tables (now + future) and create its own")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5 · Deploy (re-run this cell any time you change the app)

# COMMAND ----------
dep = w.apps.deploy_and_wait(app_name=APP, app_deployment=AppDeployment.from_dict({"source_code_path": APP_SRC}))
print("deploy state:", dep.status.state if dep.status else dep)
print("app URL:", w.apps.get(name=APP).url)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6 · Implement the write-back (the payoff)
# MAGIC Open [`../app/db.py`](../app/db.py), find `resolve_alert()` (it raises
# MAGIC `NotImplementedError`). Make it write the resolution into `ACTIONS_TABLE` — status
# MAGIC `'resolved'`, the note, the technician, `resolved_at = now()` — using
# MAGIC `INSERT ... ON CONFLICT (ticket_id) DO UPDATE` (ticket_id is UNIQUE), then `commit()`.
# MAGIC Full answer: [`../docs/solutions/resolve_alert.py`](../docs/solutions/resolve_alert.py).
# MAGIC
# MAGIC Then **re-run Step 5** to redeploy. In the app, **claim** an alert and **resolve** it —
# MAGIC it drops off the queue and lands under "Recently resolved". (Verify the round-trip in
# MAGIC `04_explore_and_roundtrip`.)
# MAGIC
# MAGIC **Prefer the UI?** *Compute → Apps → Create app*, add a **Database** resource
# MAGIC (your Lakebase database, "can connect"), point it at this repo's `app/` folder, deploy.

# COMMAND ----------
# MAGIC %md
# MAGIC ➡️ **Next: `04_explore_and_roundtrip`.**
