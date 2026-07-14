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
- **Lakebase** — create the shared **project `lakebase-workshop`** (autoscaling) ahead of time
  (provisioning takes minutes). Grant users access to the project/branch so they can:
  create a database, create synced tables, register a UC catalog, and generate DB credentials.
- **Unity Catalog**:
  - Create catalog **`catalog_workshop`**; grant the user group **`USE CATALOG`** +
    **`CREATE SCHEMA`** (each user creates their own `schema_<user>` schema and owns its tables).
  - Registering the Lakebase database as a UC catalog (`create-catalog`) needs
    **`CREATE CATALOG` on the metastore**. If you can't grant that to users, either grant it
    to the group for the session, or pre-register a per-user Lakebase catalog for each user.
  - The sync pipelines need a metadata schema — pre-create **`catalog_workshop.pipeline_storage`**
    (or rely on users having `CREATE SCHEMA`).
- **Pipelines** — snapshot synced tables spin up a Lakeflow/DLT pipeline; confirm users can
  create pipelines (usually default; a restrictive cluster policy can block it).

## 2. User privileges

| Capability | Needs | Notes |
|-----------|-------|-------|
| Run Labs 1/2/4 | serverless compute | Labs 2/3 also `%pip install -U databricks-sdk` |
| Create catalog/schema + tables (Lab 1) | `USE CATALOG` + `CREATE SCHEMA` on `catalog_workshop`; owner of own schema | workspace admin grants the group |
| Create a Postgres DB, synced tables, register catalog, mint credentials (Lab 2) | access to the `lakebase-workshop` project + `CREATE CATALOG` on the metastore | see admin setup above |
| Deploy the app (Lab 3) | permission to **create apps** | creator automatically gets `CAN_MANAGE` on their app |
| Round-trip query (Lab 4) | `CAN_USE` on a SQL warehouse; read on their Lakebase UC catalog | they own the catalog they registered |

## 3. App service principal (auto-provisioned at deploy)

Created automatically when you `apps create` **with the Lakebase database bound as a `postgres`
resource**. It needs, in Postgres:

| Grant | Why | Set by |
|-------|-----|--------|
| `CONNECT` on the database | connect at all | the resource binding (`CAN_CONNECT_AND_CREATE`) |
| `USAGE, CREATE ON SCHEMA public` | create its `maintenance_actions` table | **Lab 3, Step 3** |
| `pg_read_all_data` | `SELECT` on the synced tables — **all current *and future*** tables | **Lab 3, Step 3** |
| INSERT on `maintenance_actions` | write-back | **implicit** — the app creates & owns that table |

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
- **App-table ownership:** the app must create `maintenance_actions` itself so it *owns* it
  and can `INSERT`. If a human pre-creates that table, the SP can read it (via `pg_read_all_data`)
  but **cannot write** — the write-back fails. Let the app create it.
- **`CAN_MANAGE` ≠ the app works:** having manage rights on the app lets you *open* it; a runtime
  error is almost always the SP's Postgres grants, not app ACLs.

## Pre-flight test

Run [`labs/preflight_check.py`](../labs/preflight_check.py) as a normal (non-admin) user — it
tries each right and prints PASS/FAIL, so you catch a missing grant before starting the labs
rather than partway through.
