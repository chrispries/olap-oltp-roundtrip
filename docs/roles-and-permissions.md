# Roles & permissions

What each identity needs for the workshop to work end-to-end. Postgres grants below are
**verified**; workspace / Unity Catalog / Lakebase-project ACLs vary by environment — confirm
those with your workspace admin using the pre-flight test at the bottom.

## The three identities

1. **Facilitator / workspace admin** — sets up the shared resources once.
2. **Attendee** — a workspace user who runs the notebooks (9–20 of them).
3. **App service principal (SP)** — auto-created when an app is deployed; the app runs as this.

---

## 1. Facilitator setup (once, before the session)

- **Workspace membership** for all attendees, with:
  - **Serverless notebooks** enabled (the notebooks run on serverless).
  - A **running SQL warehouse** they can use (`CAN_USE`) — for the round-trip query in step 04.
  - **Databricks Apps enabled**, and attendees **allowed to create apps** (some workspaces
    restrict app creation to a group — add the attendee group).
- **Lakebase** — create the shared **project `lakebase-workshop`** (autoscaling) ahead of time
  (provisioning takes minutes). Grant attendees access to the project/branch so they can:
  create a database, create synced tables, register a UC catalog, and generate DB credentials.
- **Unity Catalog**:
  - Create catalog **`lakebase_workshop`**; grant the attendee group **`USE CATALOG`** +
    **`CREATE SCHEMA`** (each attendee creates their own `ws_<user>` schema and owns its tables).
  - Registering the Lakebase database as a UC catalog (`create-catalog`) needs
    **`CREATE CATALOG` on the metastore**. If you can't grant that to attendees, either grant it
    to the group for the session, or pre-register a per-user Lakebase catalog for each attendee.
  - The sync pipelines need a metadata schema — pre-create **`lakebase_workshop.pipeline_storage`**
    (or rely on attendees having `CREATE SCHEMA`).
- **Pipelines** — snapshot synced tables spin up a Lakeflow/DLT pipeline; confirm attendees can
  create pipelines (usually default; a restrictive cluster policy can block it).

## 2. Attendee privileges

| Capability | Needs | Notes |
|-----------|-------|-------|
| Run notebooks 00/01/04 | serverless compute | 02/03 also `%pip install -U databricks-sdk` |
| Create catalog/schema + tables (01) | `USE CATALOG` + `CREATE SCHEMA` on `lakebase_workshop`; owner of own schema | facilitator grants the group |
| Create their Postgres DB, synced tables, register catalog, mint credentials (02) | access to the `lakebase-workshop` project + `CREATE CATALOG` on the metastore | see facilitator notes above |
| Deploy the app (03) | permission to **create apps** | creator automatically gets `CAN_MANAGE` on their app |
| Round-trip query (04) | `CAN_USE` on a SQL warehouse; read on their Lakebase UC catalog | they own the catalog they registered |

## 3. App service principal (auto-provisioned at deploy)

Created automatically when you `apps create` **with the Lakebase database bound as a `postgres`
resource**. It needs, in Postgres:

| Grant | Why | Set by |
|-------|-----|--------|
| `CONNECT` on the database | connect at all | the resource binding (`CAN_CONNECT_AND_CREATE`) |
| `USAGE, CREATE ON SCHEMA public` | create its `maintenance_actions` table | **notebook 03, Step 4** |
| `pg_read_all_data` | `SELECT` on the synced tables — **all current *and future*** tables | **notebook 03, Step 4** |
| INSERT on `maintenance_actions` | write-back | **implicit** — the app creates & owns that table |

**Opening the app:** it sits behind workspace SSO. The creator has `CAN_MANAGE`. To let *other*
people open it (e.g. a shared demo app, or teammates), grant them **`CAN_USE`**:
Compute → Apps → *app* → Permissions (or `databricks apps set-permissions`).

---

## Gotchas (learned the hard way)

- **`insufficientPrivilege` when opening the app** = the app SP lacks `SELECT` on a synced
  table. Postgres denies the read and psycopg raises `InsufficientPrivilege`, which surfaces in
  the app. Fix: the `pg_read_all_data` grant in notebook 03. **Why `pg_read_all_data` and not
  `GRANT SELECT ON ALL TABLES`:** re-creating a synced table (any re-sync) drops and recreates
  the table, and a point-in-time `GRANT SELECT` does **not** carry over — `pg_read_all_data`
  (a built-in role covering current + future tables) does.
- **App-table ownership:** the app must create `maintenance_actions` itself so it *owns* it
  and can `INSERT`. If a human pre-creates that table, the SP can read it (via `pg_read_all_data`)
  but **cannot write** — the write-back fails. Let the app create it.
- **`CAN_MANAGE` ≠ the app works:** having manage rights on the app lets you *open* it; a runtime
  error is almost always the SP's Postgres grants, not app ACLs.

## Pre-flight test (do this before the room arrives)

Run the whole flow **as a normal (non-admin) test user**, not as yourself-the-admin — that's
the only way to catch a missing attendee grant. Success = 01 loads data, 02's synced tables
return rows via UC SQL, 03's app opens and shows the flagged machines, and an alert you claim
and resolve in the app appears in the step-04 query.
