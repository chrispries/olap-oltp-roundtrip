# 🏭 Lab 3 – Build and Deploy the App

## 🎯 Learning Objectives
By the end of this lab, you will:
- Understand how a **Databricks App** is configured (`app.yaml`) and authenticates to Lakebase
  (per-connection OAuth tokens)
- Deploy the **Maintenance Cockpit** and bind it to your Lakebase database
- Implement the one piece left for you — the **write-back** (`resolve_alert`) — and redeploy
- See the operational workflow: an alert queue you **claim** and **resolve**

## Introduction

A Databricks App runs next to your data and talks to Lakebase over normal Postgres. Unlike the
other labs, the app is **multi-file Python that gets deployed**, so its code lives as files in
your Git folder at **[`bundle/src/app/`](../bundle/src/app)** — you deploy that folder rather
than paste it into a cell. Two files matter:

- **`app.yaml`** — how Databricks runs it: `streamlit run app.py` on port 8000, plus the
  Lakebase coordinates. No password — see `db.py`.
- **`db.py`** — `get_connection()` mints a **fresh OAuth token per connection** via
  `w.postgres.generate_database_credential(ENDPOINT_NAME)`. `open_alerts`/`claim_alert` drive the
  alert queue; `resolve_alert` is the gap you'll fill.

Open both files in your workspace and skim them before deploying.

## Instructions

Before you start, please verify:
- You completed **Lab 2** (synced tables exist and read via UC).
- Databricks **Apps** is enabled and you can create apps.

### Step 1 — Point the deploy at your app folder

Run the cells below in a serverless notebook. First, tell it where your app code and database
are. **Set `REPO` to your Git folder's path** — copy it from the workspace sidebar (right-click
the repo folder ▸ *Copy URL/path*); it looks like `/Workspace/Users/you@co.com/app-lakebase-in-a-day`.

```python
%pip install -U "databricks-sdk>=0.50" "psycopg[binary]>=3.1" -q
dbutils.library.restartPython()
```

> ⚠️ `restartPython()` wipes all variables and imports (including anything from an earlier lab).
> That's expected — the next cell re-imports and re-derives everything, so **run it right after
> the restart.** This lab is self-contained.

```python
import re, pathlib
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import App, AppDeployment
import psycopg

REPO = "/Workspace/Users/<you>/app-lakebase-in-a-day"   # ← set to your Git folder
APP_SRC = f"{REPO}/bundle/src/app"

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())
BRANCH   = "projects/lakebase-workshop/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
PGDB = f"schema_{slug}"
APP  = ("lb-workshop-" + slug.replace("_", "-"))[:30].rstrip("-")
host = w.postgres.list_endpoints(BRANCH).__next__().as_dict()["status"]["hosts"]["host"]

# point the app at YOUR database (writes PGDATABASE into app.yaml — no hand-editing)
yaml_path = pathlib.Path(f"{APP_SRC}/app.yaml")
yaml_path.write_text(re.sub(r'(- name: PGDATABASE\n\s*value: )"[^"]*"',
                            rf'\g<1>"{PGDB}"', yaml_path.read_text()))
print(f"APP={APP}  PGDB={PGDB}\nAPP_SRC={APP_SRC}")
```

### Step 2 — Create the app + bind the Lakebase database

Binding the database as a `postgres` **resource** provisions a Postgres role for the app's
service principal and injects the connection env vars.

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

### Step 3 — Grant the app read access, then deploy

Binding lets the app connect and create its own table, but **not** read the synced tables —
grant that once. `pg_read_all_data` covers all current *and future* tables (survives a re-sync).

```python
sp = w.apps.get(name=APP).as_dict().get("service_principal_client_id")
with psycopg.connect(host=host, port=5432, dbname=PGDB, user=user,
                     password=w.postgres.generate_database_credential(ENDPOINT).token,
                     sslmode="require", autocommit=True) as c:
    c.execute(f'GRANT USAGE, CREATE ON SCHEMA public TO "{sp}"')
    c.execute(f'GRANT pg_read_all_data TO "{sp}"')

dep = w.apps.deploy_and_wait(app_name=APP,
        app_deployment=AppDeployment.from_dict({"source_code_path": APP_SRC}))
print("deploy:", dep.status.state if dep.status else dep)
print("URL:", w.apps.get(name=APP).url)
```

**✅ Check:** deploy reaches **SUCCEEDED** and prints a URL. Open it — you'll see **Recently
resolved** (empty for now) and the **alert queue** with the flagged machines (e.g. *Press Brake
#44 – spindle overheating*). The **Resolve** button shows a "not implemented yet" warning —
that's your job next.

> **💡 Permissions note.** If the app shows `insufficientPrivilege`, the `pg_read_all_data` grant
> above is the fix (the app SP couldn't read a synced table). Full detail:
> [`docs/roles-and-permissions.md`](../docs/roles-and-permissions.md).

### Step 4 — Implement the write-back (the payoff)

Open [`bundle/src/app/db.py`](../bundle/src/app/db.py) and find `resolve_alert()` — it raises
`NotImplementedError`. Replace the body so it writes the resolution into `ACTIONS_TABLE`:

```python
    with conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {ACTIONS_TABLE}
                    (ticket_id, machine_id, technician, status, resolution, resolved_at)
                VALUES (%s, %s, %s, 'resolved', %s, now())
                ON CONFLICT (ticket_id)
                DO UPDATE SET status = 'resolved', technician = EXCLUDED.technician,
                              resolution = EXCLUDED.resolution, resolved_at = now()""",
            (ticket_id, machine_id, technician, resolution))
    conn.commit()
```

(`ticket_id` is `UNIQUE`, so `ON CONFLICT … DO UPDATE` resolves an already-claimed alert. Try
writing it yourself first, then compare with the block above.)

Then **re-run the deploy cell from Step 3** to redeploy. In the app: **Claim** a flagged alert,
then **Resolve** it with a note (e.g. *"replaced coolant filter"*).

**✅ Check:** the alert drops off the active queue and appears under **"Recently resolved."**

**💡 What just happened?**
Synced tables are read-only, so the app can't "close" the seeded alert row. Instead it records
the technician's work in its **own** table `maintenance_actions` — the write that becomes
analytics in Lab 4.

> **Sharing the app:** it opens behind workspace SSO; you (the creator) have `CAN_MANAGE`. To let
> teammates open it, grant them `CAN_USE` (Compute ▸ Apps ▸ your app ▸ Permissions).

➡️ **Next: [Lab 4 – Close the Round-Trip](Lab%204%20-%20Close%20the%20Round-Trip.md).**
