# 🏭 Lab 0 – Setup

## 🎯 Learning Objectives
By the end of this lab, you will:
- Understand the **scenario** and the round-trip you'll build
- Have the repository in your Databricks workspace as a **Git folder**
- (When setting up for a team) provisioned access for the group
- Know where to start

## Introduction

You're going to build the **Apps + Lakebase round-trip**: analytical data in Unity Catalog,
served operationally through Lakebase (Postgres) and a Databricks App, with the app's writes
flowing straight back to the analytical layer — one governed platform, no ETL in between.

The example is a shop-floor **Maintenance Cockpit** (see [`docs/scenario.md`](../docs/scenario.md)),
but the pattern fits anywhere operational people act on analytical data.

![Architecture](../docs/architecture.svg)

New to the concepts? Read [`docs/concepts.md`](../docs/concepts.md) (10 min).

## Instructions

### Step 1 — Provision access (team setup: workspace admin, once)

> Running this on your own? Skip to Step 2 — this step is only for a workspace admin setting the labs up for a team.

A workspace admin runs the cells below once. It creates a `lakebase-workshop-participants`
group and grants it everything participants need. (Full reference:
[`docs/roles-and-permissions.md`](../docs/roles-and-permissions.md); access-request template:
[`docs/access-request-template.md`](../docs/access-request-template.md).)

```python
%pip install -U "databricks-sdk>=0.50" -q
dbutils.library.restartPython()
```

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import iam
from databricks.sdk.service import sql as dbsql

# ⚙️ EDIT THESE
GROUP_NAME     = "lakebase-workshop-participants"
MEMBER_EMAILS  = ["participant1@example.com", "participant2@example.com"]
CATALOG        = "catalog_workshop"
WAREHOUSE_NAME = "Shared Endpoint"   # a running SQL warehouse to grant CAN_USE

w = WorkspaceClient()

# 1) group + workspace/SQL entitlements
groups = list(w.groups.list(filter=f'displayName eq "{GROUP_NAME}"'))
group = groups[0] if groups else w.groups.create(
    display_name=GROUP_NAME,
    entitlements=[iam.ComplexValue(value="workspace-access"),
                  iam.ComplexValue(value="databricks-sql-access")])
print("group id:", group.id)

# 2) add members (they must already exist as users in the workspace/account)
ids = []
for email in MEMBER_EMAILS:
    us = list(w.users.list(filter=f'userName eq "{email}"'))
    ids.append(us[0].id) if us else print("⚠️  user not found:", email)
if ids:
    w.groups.patch(group.id,
        schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
        operations=[iam.Patch(op=iam.PatchOp.ADD, path="members",
                              value=[{"value": i} for i in ids])])
    print(f"✅ added {len(ids)} member(s)")

# 3) Unity Catalog grants
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.pipeline_storage")
spark.sql(f"GRANT USE CATALOG, CREATE SCHEMA ON CATALOG {CATALOG} TO `{GROUP_NAME}`")
try:
    spark.sql(f"GRANT CREATE CATALOG ON METASTORE TO `{GROUP_NAME}`")
    print("✅ granted CREATE CATALOG on metastore")
except Exception as e:
    print("⚠️  CREATE CATALOG ON METASTORE needs a metastore admin:", str(e)[:140])

# 4) SQL warehouse CAN_USE
wh_id = next((x.id for x in w.warehouses.list() if x.name == WAREHOUSE_NAME), None)
if wh_id:
    w.warehouses.update_permissions(wh_id, access_control_list=[
        dbsql.WarehouseAccessControlRequest(group_name=GROUP_NAME,
            permission_level=dbsql.WarehousePermissionLevel.CAN_USE)])
    print(f"✅ granted CAN_USE on warehouse {wh_id}")
else:
    print(f"⚠️  warehouse '{WAREHOUSE_NAME}' not found — set WAREHOUSE_NAME")
```

**Steps that stay manual** (environment/preview-specific): confirm users can **create their own
Lakebase projects**, enable the **Change Data Feed (CDF) preview** on the *Previews* page, and
confirm **Apps creation** is allowed for the group.

**💡 What just happened?**
Every participant is now in one group with the rights the labs need, so nobody hits a
permission wall mid-workshop.

### Step 2 — Add the repo to your workspace (Git folder)

1. In the Databricks sidebar, click **Workspace**.
2. Navigate to your home folder → **Create ▸ Git folder**.
3. Paste the repository URL and click **Create**.
4. Expand the folder — you'll see `labs/`, `bundle/`, and `docs/`. This brings both the lab
   guides **and** the app code into your workspace (Lab 3 deploys the app from `bundle/src/app`).

### Step 3 — Confirm your prerequisites

Open **[`labs/preflight_check.py`](preflight_check.py)**, set the two values at the top, and
**Run all**. It actually tries each right (and cleans up after itself) and prints PASS/FAIL:
serverless, SQL warehouse, Unity Catalog create, `CREATE CATALOG` on the metastore, Lakebase
project access, and Apps. Any FAIL → share it with your workspace admin
([`docs/access-request-template.md`](../docs/access-request-template.md)).

You should also have:
- **Lakebase enabled** and permission to **create a project** — you'll create your own
  `lakebase-ws-<you>-N` in Lab 2. No shared project to set up.
- The **CDF preview** enabled (a workspace admin toggles it on the *Previews* page).

### Step 4 — Choose your starting point

The labs run in order and build on each other. Start at Lab 1.

| Lab | Topic | Guide |
|-----|-------|-------|
| **Lab 1** | Generate the analytical data in Unity Catalog | [guide](Lab%201%20-%20Generate%20Analytical%20Data.md) |
| **Lab 2** | Sync into Lakebase, add operational tables, stream writes back via CDF | [guide](Lab%202%20-%20Sync%20to%20Lakebase.md) |
| **Lab 3** | Build & deploy the Maintenance Cockpit app; implement the write-back | [guide](Lab%203%20-%20Build%20and%20Deploy%20the%20App.md) |
| **Lab 4** | Close the round-trip — the app's writes, live in Databricks SQL | [guide](Lab%204%20-%20Close%20the%20Round-Trip.md) |

> **One-command deploy:** instead of Lab 3, you can deploy the app with the bundle — see
> [`bundle/README.md`](../bundle/README.md).

➡️ **Next: [Lab 1 – Generate Analytical Data](Lab%201%20-%20Generate%20Analytical%20Data.md).**
