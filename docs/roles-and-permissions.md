# Roles & permissions

What each identity needs for the workshop to work end-to-end. Postgres grants below are
**verified**; workspace / Unity Catalog / Lakebase-project ACLs vary by environment — confirm
those with your workspace admin using the pre-flight test at the bottom.

## The three identities

1. **Workspace admin** — sets up the shared resources once (only for a team setup).
2. **User** — runs the labs.
3. **App service principal (SP)** — auto-created when an app is deployed; the app runs as this.

---

> **Automate steps 1–2 + the warehouse grant:** run the admin-setup cells in [Lab 0, Step 1](../labs/Lab%200%20-%20Setup.md)
> as a workspace admin. It creates the group, adds members, sets entitlements, does the Unity
> Catalog grants, and grants `CAN_USE` on a warehouse. The two manual bits (Lakebase project
> access, Apps enablement) are called out in that notebook and in section 3 below.

## 1. Workspace admin setup (once, before the session)

- **Workspace membership** for all users, with:
  - **Serverless notebooks** enabled (the notebooks run on serverless).
  - A **running SQL warehouse** they can use (`CAN_USE`) — for the round-trip query in step 04.
  - **Databricks Apps enabled**, and users **allowed to create apps** (some workspaces
    restrict app creation to a group — add the user group).
- **Lakebase** — enabled in the workspace, and users allowed to **create their own projects**
  (each user creates `lakebase-ws-<user>-N` in Lab 2 — there is no shared project). That lets
  them create synced tables, create operational tables, and generate DB credentials.
- **Change Data Feed (CDF) preview** — enable it on the workspace **Previews** page (it's a
  preview feature). Lab 2's Lakebase → UC round-trip depends on it.
- **Unity Catalog**:
  - Create catalog **`catalog_workshop`**; grant the user group **`USE CATALOG`** +
    **`CREATE SCHEMA`** (each user creates their own `schema_<user>` **and** `lakebase_<user>`
    schemas and owns their tables). The synced replicas and the CDF `lb_*_history` output both land
    in `catalog_workshop.lakebase_<user>` — so no separate catalog and **no `CREATE CATALOG` on the
    metastore** is needed anymore.
- **Pipelines** — synced tables spin up a Lakeflow/DLT pipeline; confirm users can create pipelines
  (usually default; a restrictive cluster policy can block it).

## 2. User privileges

| Capability | Needs | Notes |
|-----------|-------|-------|
| Run Labs 1/2/4 | serverless compute | Labs 2/3 also `%pip install -U databricks-sdk` |
| Create catalog/schema + tables (Lab 1) | `USE CATALOG` + `CREATE SCHEMA` on `catalog_workshop`; owner of own schema | workspace admin grants the group |
| Create a Lakebase project, synced tables, operational tables, mint credentials (Lab 2) | permission to **create Lakebase projects** + `CREATE SCHEMA` on `catalog_workshop` + CDF preview enabled | see admin setup above |
| Deploy the app (Lab 3) | permission to **create apps** | creator automatically gets `CAN_MANAGE` on their app |
| Round-trip query (Lab 4) | `CAN_USE` on a SQL warehouse; read on their `catalog_workshop.lakebase_<user>` schema | they own the schema; CDF lands `lb_*_history` there |

## 3. App service principal (auto-provisioned at deploy)

Created automatically when you `apps create` **with the Lakebase database bound as a `postgres`
resource**. It needs, in Postgres:

| Grant | Why | Set by |
|-------|-----|--------|
| `CONNECT` on the database | connect at all | the resource binding (`CAN_CONNECT_AND_CREATE`) |
| `USAGE ON SCHEMA public` | reach the tables | **Lab 3, Step 3** |
| `pg_read_all_data` | `SELECT` on synced + operational tables — **all current *and future*** tables | **Lab 3, Step 3** |
| `pg_write_all_data` | `INSERT`/`UPDATE`/`DELETE` on the operational tables (owned by the user) | **Lab 3, Step 3** |
| `USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public` | `SERIAL` primary keys on the operational tables | **Lab 3, Step 3** |

**Opening the app:** it sits behind workspace SSO. The creator has `CAN_MANAGE`. To let *other*
people open it (e.g. a shared demo app, or teammates), grant them **`CAN_USE`**:
Compute → Apps → *app* → Permissions (or `databricks apps set-permissions`).

---

## Gotchas (learned the hard way)

- **`insufficientPrivilege` when opening the app** = the app SP lacks `SELECT` on a synced
  table. Postgres denies the read and psycopg raises `InsufficientPrivilege`, which surfaces in
  the app. Fix: the `pg_read_all_data` grant in Lab 3. **Why `pg_read_all_data` and not
  `GRANT SELECT ON ALL TABLES`:** re-creating a synced table (any re-sync) drops and recreates
  the table, and a point-in-time `GRANT SELECT` does **not** carry over — `pg_read_all_data`
  (a built-in role covering current + future tables) does.
- **Write-back fails / `permission denied`:** the operational tables are owned by the **user**
  (created in Lab 2), so the app SP needs `pg_write_all_data` *and* `USAGE, SELECT` on the schema's
  sequences (the `SERIAL` keys). Missing the sequence grant is the usual culprit — the `INSERT`
  fails on `nextval()`. All three grants are in Lab 3, Step 3.
- **`CAN_MANAGE` ≠ the app works:** having manage rights on the app lets you *open* it; a runtime
  error is almost always the SP's Postgres grants, not app ACLs.

## Pre-flight test

Run [`labs/preflight_check.py`](../labs/preflight_check.py) as a normal (non-admin) user — it
tries each right and prints PASS/FAIL, so you catch a missing grant before starting the labs
rather than partway through.
