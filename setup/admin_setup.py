# Databricks notebook source
# MAGIC %md
# MAGIC # Admin setup — provision the workshop group (run ONCE, before the session)
# MAGIC
# MAGIC **Who runs this:** a **workspace admin** (this creates a group and grants privileges).
# MAGIC It gives every participant the access they need so they can run notebooks 00→04 without
# MAGIC hitting permission errors.
# MAGIC
# MAGIC **What it does**
# MAGIC 1. Create a group `lakebase-workshop-participants` and add the participants.
# MAGIC 2. Give the group workspace + SQL entitlements.
# MAGIC 3. Unity Catalog: create the `lakebase_workshop` catalog and grant the group
# MAGIC    `USE CATALOG` + `CREATE SCHEMA`, plus `CREATE CATALOG` on the metastore (to register
# MAGIC    their Lakebase database as a catalog).
# MAGIC 4. Grant the group `CAN_USE` on a SQL warehouse.
# MAGIC 5. Print the two steps that stay manual (Lakebase project access, Apps creation) — those
# MAGIC    are environment/preview-specific; see the notes at the bottom.
# MAGIC
# MAGIC Idempotent — safe to re-run. Participants must already exist as users in the account/
# MAGIC workspace (this adds them to the group, it doesn't create logins).

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.50" -q
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# ⚙️ CONFIG — edit these
GROUP_NAME     = "lakebase-workshop-participants"
MEMBER_EMAILS  = [
    # "participant1@example.com",
    # "participant2@example.com",
]
CATALOG        = "lakebase_workshop"
WAREHOUSE_NAME = ""          # e.g. "Shared Endpoint" — or set WAREHOUSE_ID
WAREHOUSE_ID   = ""          # takes precedence over WAREHOUSE_NAME if set
LAKEBASE_PROJECT = "lakebase-workshop"   # the shared Lakebase project (create separately)

# COMMAND ----------
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import iam
from databricks.sdk.service import sql as dbsql

w = WorkspaceClient()
print("running as:", w.current_user.me().user_name)

# COMMAND ----------
# MAGIC %md ## 1 · Group + entitlements

# COMMAND ----------
existing = list(w.groups.list(filter=f'displayName eq "{GROUP_NAME}"'))
if existing:
    group = existing[0]
    print(f"group '{GROUP_NAME}' already exists (id={group.id})")
else:
    group = w.groups.create(
        display_name=GROUP_NAME,
        entitlements=[iam.ComplexValue(value="workspace-access"),
                      iam.ComplexValue(value="databricks-sql-access")],
    )
    print(f"✅ created group '{GROUP_NAME}' (id={group.id})")

# ensure entitlements even if the group pre-existed
try:
    w.groups.patch(
        group.id,
        schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        operations=[iam.Patch(op=iam.PatchOp.ADD, path="entitlements",
                              value=[{"value": "workspace-access"},
                                     {"value": "databricks-sql-access"}])],
    )
    print("✅ entitlements ensured: workspace-access, databricks-sql-access")
except Exception as e:
    print("entitlements patch:", str(e)[:160])

# COMMAND ----------
# MAGIC %md ## 2 · Add participants to the group

# COMMAND ----------
member_ids = []
for email in MEMBER_EMAILS:
    users = list(w.users.list(filter=f'userName eq "{email}"'))
    if users:
        member_ids.append(users[0].id)
    else:
        print(f"⚠️  user not found (add them to the account/workspace first): {email}")

if member_ids:
    w.groups.patch(
        group.id,
        schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        operations=[iam.Patch(op=iam.PatchOp.ADD, path="members",
                              value=[{"value": uid} for uid in member_ids])],
    )
    print(f"✅ added {len(member_ids)} member(s) to '{GROUP_NAME}'")
else:
    print("no members added — fill in MEMBER_EMAILS")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3 · Unity Catalog grants
# MAGIC Standard `GRANT` SQL (version-stable). `CREATE CATALOG ON METASTORE` needs **metastore
# MAGIC admin** — if you're not one, run that line as a metastore admin, or pre-register each
# MAGIC attendee's Lakebase catalog yourself.

# COMMAND ----------
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.pipeline_storage")
spark.sql(f"GRANT USE CATALOG, CREATE SCHEMA ON CATALOG {CATALOG} TO `{GROUP_NAME}`")
spark.sql(f"GRANT USE SCHEMA, CREATE TABLE ON SCHEMA {CATALOG}.pipeline_storage TO `{GROUP_NAME}`")
print(f"✅ granted USE CATALOG + CREATE SCHEMA on {CATALOG} to '{GROUP_NAME}'")

try:
    spark.sql(f"GRANT CREATE CATALOG ON METASTORE TO `{GROUP_NAME}`")
    print("✅ granted CREATE CATALOG on the metastore (needed to register Lakebase catalogs)")
except Exception as e:
    print("⚠️  CREATE CATALOG ON METASTORE failed (need metastore admin):", str(e)[:160])

# COMMAND ----------
# MAGIC %md ## 4 · SQL warehouse access (`CAN_USE`)

# COMMAND ----------
wh_id = WAREHOUSE_ID
if not wh_id and WAREHOUSE_NAME:
    wh_id = next((wh.id for wh in w.warehouses.list() if wh.name == WAREHOUSE_NAME), None)

if wh_id:
    w.warehouses.update_permissions(
        wh_id,
        access_control_list=[dbsql.WarehouseAccessControlRequest(
            group_name=GROUP_NAME, permission_level=dbsql.WarehousePermissionLevel.CAN_USE)],
    )
    print(f"✅ granted CAN_USE on warehouse {wh_id} to '{GROUP_NAME}'")
else:
    print("⚠️  set WAREHOUSE_NAME or WAREHOUSE_ID to grant warehouse access")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5 · Two steps that stay manual (environment / preview specific)
# MAGIC
# MAGIC - **Lakebase project access** — grant `{LAKEBASE_PROJECT}` to the group so participants
# MAGIC   can create databases, synced tables, register catalogs, and mint credentials. Do this
# MAGIC   from the project's **Permissions** in the UI (Compute → Database instances → the
# MAGIC   project), or your workspace's Lakebase permissions API. (No stable SDK call across
# MAGIC   versions yet — verify in your workspace.)
# MAGIC - **Databricks Apps** — ensure Apps is **enabled** for the workspace and the group is
# MAGIC   **allowed to create apps** (Settings → Developer / Apps). Each participant's app is
# MAGIC   theirs; they automatically get `CAN_MANAGE` on it.
# MAGIC
# MAGIC Then run the **pre-flight test** in `docs/roles-and-permissions.md` as a non-admin test
# MAGIC user to confirm nothing is missing.

# COMMAND ----------
print(f"""
Setup summary
  group:      {GROUP_NAME}  ({len(MEMBER_EMAILS)} member(s) configured)
  catalog:    {CATALOG}  (USE CATALOG + CREATE SCHEMA granted)
  warehouse:  {'granted' if (WAREHOUSE_ID or WAREHOUSE_NAME) else 'NOT SET — see step 4'}
  still manual: Lakebase project access + Apps creation (step 5)
""")
