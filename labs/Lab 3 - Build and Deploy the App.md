# 🏭 Lab 3 – Build and Deploy the App

## 🎯 Learning Objectives
By the end of this lab, you will:
- Understand how a **Databricks App** is configured (`app.yaml`) and authenticates to Lakebase
  (per-connection OAuth tokens)
- Deploy the **Maintenance Cockpit** and bind it to *your* Lakebase database
- Grant the app's service principal read **and write** access to your Postgres tables
- Implement the one piece left for you — the **write-back** (`log_maintenance_action`) — and redeploy
- See the operational workflow: alerts, maintenance actions, work orders, quality checks, notes

## Introduction

A Databricks App runs next to your data and talks to Lakebase over normal Postgres. Unlike the
other labs, the app is **multi-file Python that gets deployed**, so its code lives as files in
your Git folder at **[`bundle/src/app/`](../bundle/src/app)** — you deploy that folder rather
than paste it into a cell. Two files matter:

- **`app.yaml`** — how Databricks runs it: `streamlit run app.py` on port 8000, plus the Lakebase
  coordinates (`ENDPOINT_NAME`, `PGHOST`, `PGDATABASE`). No password — see `db.py`.
- **`db.py`** — `get_connection()` mints a **fresh OAuth token per connection** via
  `w.postgres.generate_database_credential(ENDPOINT_NAME)`. It reads the read-only synced tables
  (`machines`, `maintenance_tickets`, …) and reads/writes the operational tables you created in
  Lab 2 (`maintenance_actions`, `work_orders`, `quality_checks`, `operator_notes`).
  `log_maintenance_action` is the gap you'll fill.

Open both files in your workspace and skim them before deploying.

## Instructions

Before you start, please verify:
- You completed **Lab 2** — your Lakebase project, synced tables, and the four operational tables
  exist, and you started **CDF** from the UI.
- Databricks **Apps** is enabled and you can create apps.

### Step 1 — Resolve your project and point the deploy at your app folder

Run the cells below in a serverless notebook. First install the SDK, then resolve **your**
Lakebase project (the `lakebase-ws-<you>-N` you created in Lab 2) and write its coordinates into
`app.yaml`. **Set `REPO` to your Git folder's path** — copy it from the workspace sidebar
(right-click the repo folder ▸ *Copy URL/path*); it looks like
`/Workspace/Users/you@co.com/app-lakebase-in-a-day`.

```python
%pip install -U "databricks-sdk>=0.118.0" "psycopg[binary]>=3.1" -q
dbutils.library.restartPython()
```

> ⚠️ `restartPython()` wipes all variables and imports. Run the next cell right after the restart.

```python
import re, pathlib
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import App, AppDeployment
import psycopg

REPO = "/Workspace/Users/<you>/app-lakebase-in-a-day"   # ← set to your Git folder
APP_SRC = f"{REPO}/bundle/src/app"

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "", user.split("@")[0].lower())
PGDB = "databricks_postgres"
APP  = ("lb-workshop-" + slug)[:30].rstrip("-")

# Find your healthy Lakebase project from Lab 2 (lakebase-ws-<slug>-N)
PROJECT = None
for i in range(1, 11):
    candidate = f"lakebase-ws-{slug}-{i}"
    try:
        w.postgres.get_project(name=f"projects/{candidate}")
        list(w.postgres.list_branches(parent=f"projects/{candidate}"))   # health check
        PROJECT = candidate
        break
    except Exception:
        continue
if PROJECT is None:
    raise RuntimeError("No healthy Lakebase project found — run Lab 2 first.")

BRANCH   = f"projects/{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
endpoint = next((ep for ep in w.postgres.list_endpoints(parent=BRANCH) if ep.name == ENDPOINT), None)
host = endpoint.status.hosts.host

# Write ENDPOINT_NAME + PGHOST into app.yaml (PGDATABASE is already databricks_postgres)
def set_env(text, name, val):
    return re.sub(rf'(- name: {name}\n\s*value: )"[^"]*"', rf'\g<1>"{val}"', text)
yaml_path = pathlib.Path(f"{APP_SRC}/app.yaml")
t = yaml_path.read_text()
t = set_env(t, "ENDPOINT_NAME", ENDPOINT)
t = set_env(t, "PGHOST", host)
yaml_path.write_text(t)
print(f"APP={APP}  PROJECT={PROJECT}\nENDPOINT={ENDPOINT}\nhost={host}")
```

### Step 2 — Create the app + bind the Lakebase database

Binding `databricks_postgres` as a `postgres` **resource** provisions a Postgres role for the
app's service principal and injects the connection env vars.

```python
dbres = next(d.as_dict()["name"] for d in w.postgres.list_databases(BRANCH)
             if d.as_dict()["status"]["postgres_database"] == PGDB)
try:
    w.apps.get(name=APP); print(f"app {APP} already exists — skipping create")
except Exception:
    print(f"creating {APP} (compute takes a couple minutes)…")
    w.apps.create_and_wait(App.from_dict({
        "name": APP, "description": "Lakebase-in-a-Day: shop-floor maintenance app",
        "resources": [{"name": "lakebase-db",
            "postgres": {"branch": BRANCH, "database": dbres, "permission": "CAN_CONNECT_AND_CREATE"}}]}))
    print("✅ app created")
```

### Step 3 — Grant the app read + write access, then deploy

Binding lets the app connect, but not read the synced tables or write the operational ones you
own. Grant both once. `pg_read_all_data`/`pg_write_all_data` cover all current *and future* tables
(so they survive a re-sync), and the sequence grant lets the app's inserts use the `SERIAL`
primary keys.

```python
sp = w.apps.get(name=APP).as_dict().get("service_principal_client_id")
with psycopg.connect(host=host, port=5432, dbname=PGDB, user=user,
                     password=w.postgres.generate_database_credential(ENDPOINT).token,
                     sslmode="require", autocommit=True) as c:
    c.execute(f'GRANT USAGE ON SCHEMA public TO "{sp}"')
    c.execute(f'GRANT pg_read_all_data TO "{sp}"')
    c.execute(f'GRANT pg_write_all_data TO "{sp}"')
    c.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{sp}"')

dep = w.apps.deploy_and_wait(app_name=APP,
        app_deployment=AppDeployment.from_dict({"source_code_path": APP_SRC}))
print("deploy:", dep.status.state if dep.status else dep)
print("URL:", w.apps.get(name=APP).url)
```

**✅ Check:** deploy reaches **SUCCEEDED** and prints a URL. Open it — the **Alerts & actions**
tab shows the flagged machines (e.g. *Press Brake #44 – spindle overheating*), plus tabs for
**Work orders**, **Quality checks**, and **Operator notes**. The **Log action** button shows a
"not implemented yet" warning — that's your job next.

> **💡 Permissions note.** If the app shows `insufficientPrivilege`, the grants above are the fix.
> Full detail: [`docs/roles-and-permissions.md`](../docs/roles-and-permissions.md).

### Step 4 — Implement the write-back (the payoff)

Open [`bundle/src/app/db.py`](../bundle/src/app/db.py) and find `log_maintenance_action()` — it
raises `NotImplementedError`. Replace the body so it inserts the technician's work into
`maintenance_actions`:

```python
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO maintenance_actions
                   (machine_id, ticket_id, action_type, description, performed_by, status, completed_at)
               VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s = 'completed' THEN now() END)""",
            (machine_id, ticket_id, action_type, description, performed_by, status, status))
    conn.commit()
```

(A plain `INSERT` — `action_id` is a `SERIAL`, so Postgres assigns it. `completed_at` is set only
when the action is marked completed. Try writing it yourself first, then compare.)

Then **re-run the deploy cell from Step 3** to redeploy. In the app: pick an alert, choose an
action type, describe the fix, and **Log action**.

**✅ Check:** the action appears under **"Recent maintenance actions."** Because CDF is running,
it also lands in Unity Catalog as `lb_maintenance_actions_history` within ~15s — which is exactly
what Lab 4 queries.

**💡 What just happened?**
The synced `maintenance_tickets` table is read-only, so the app can't "close" a seeded ticket
row. Instead it records the technician's work in the app-owned `maintenance_actions` table — the
write that CDF streams back into the lakehouse in Lab 4. The other tabs (work orders, quality
checks, notes) exercise the same write path against the other operational tables.

> **Sharing the app:** it opens behind workspace SSO; you (the creator) have `CAN_MANAGE`. To let
> teammates open it, grant them `CAN_USE` (Compute ▸ Apps ▸ your app ▸ Permissions).

➡️ **Next: [Lab 4 – Close the Round-Trip](Lab%204%20-%20Close%20the%20Round-Trip.md).**
