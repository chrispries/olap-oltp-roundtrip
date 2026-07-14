# 🏭 Lab 3 – Build and Deploy the App

## 🎯 Learning Objectives
By the end of this lab, you will:
- Understand how a **Databricks App** is configured (`app.yaml`) and how it authenticates to
  Lakebase (per-connection OAuth tokens)
- Deploy the **Maintenance Cockpit** and bind it to your Lakebase database
- Implement the one piece left for you — the **write-back** (`resolve_alert`) — and redeploy
- See the operational workflow: an alert queue you **claim** and **resolve**

## Introduction

A Databricks App runs next to your data and talks to Lakebase over normal Postgres. The
Maintenance Cockpit reads the open **alert queue** from your synced tables, lets a technician
**claim** an alert and **resolve** it with a note, and writes that work to its own table.

Two files matter (in [`bundle/src/app/`](../bundle/src/app)):
- **`app.yaml`** — how Databricks runs the app: `streamlit run app.py` on port 8000, plus the
  Lakebase coordinates. No password — see `db.py`.
- **`db.py`** — `get_connection()` mints a **fresh OAuth token per connection** via
  `w.postgres.generate_database_credential(ENDPOINT_NAME)` (Autoscaling tokens are short-lived).
  `open_alerts`/`claim_alert` drive the queue; `resolve_alert` is the gap you'll fill.

## Instructions

Before you start, please verify:
- You completed **Lab 2** (synced tables exist and read via UC).
- Databricks **Apps** is enabled and you can create apps.

### Step 1 — Deploy the app

1. Open [`bundle/src/notebooks/deploy_app.py`](../bundle/src/notebooks/deploy_app.py) and **Run all**.

It writes your database name into `app.yaml`, creates the app with the Lakebase database bound
as a resource, grants the app's service principal read access, and deploys:

```python
w.apps.create_and_wait(App.from_dict({
    "name": APP,
    "resources": [{"name": "lakebase-db",
        "postgres": {"branch": BRANCH, "database": dbres, "permission": "CAN_CONNECT_AND_CREATE"}}]}))
# grant the app SP read on all tables (now + future) — see the permissions note below
w.apps.deploy_and_wait(app_name=APP, app_deployment=AppDeployment.from_dict({"source_code_path": APP_SRC}))
```

**✅ Check:** the last cells print the app URL and it reaches state **SUCCEEDED**. Open the URL —
you should see the **alert queue** (flagged machines like *Press Brake #44 – spindle
overheating*). The **Resolve** button shows a "not implemented yet" warning — that's your job next.

> **💡 Permissions note.** Binding the database (`CAN_CONNECT_AND_CREATE`) lets the app connect
> and create its own table, but **not** read the synced tables. The notebook grants
> `pg_read_all_data` to the app's service principal — a built-in role that covers all current
> *and future* tables (so it survives a re-sync). If the app shows `insufficientPrivilege`,
> that grant is the fix. Full detail: [`docs/roles-and-permissions.md`](../docs/roles-and-permissions.md).

### Step 2 — Implement the write-back (the payoff)

Open [`bundle/src/app/db.py`](../bundle/src/app/db.py) and find `resolve_alert()` — it raises
`NotImplementedError`. Make it write the resolution into `ACTIONS_TABLE`:

1. `INSERT (ticket_id, machine_id, technician, resolution)` with `status = 'resolved'` and `resolved_at = now()`,
2. `ON CONFLICT (ticket_id) DO UPDATE` (ticket_id is `UNIQUE` — resolving an already-claimed alert updates its row),
3. `conn.commit()`.

Stuck or want to check? Full answer:
[`labs/artifacts/solutions/resolve_alert.py`](artifacts/solutions/resolve_alert.py).

Then **re-run the deploy cell** in `deploy_app`. In the app: **Claim** a flagged alert, then
**Resolve** it with a note (e.g. *"replaced coolant filter"*).

**✅ Check:** the alert drops off the active queue and appears under **"Recently resolved."**

**💡 What just happened?**
Synced tables are read-only, so the app can't "close" the seeded alert row. Instead it records
the technician's work in its **own** table `maintenance_actions`. That's the write that becomes
analytics in Lab 4.

> **Sharing the app:** it opens behind workspace SSO; you (the creator) have `CAN_MANAGE`. To let
> teammates open it, grant them `CAN_USE` (Compute ▸ Apps ▸ your app ▸ Permissions).

➡️ **Next: [Lab 4 – Close the Round-Trip](Lab%204%20-%20Close%20the%20Round-Trip.md).**
