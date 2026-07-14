# 🏭 Lab 0 – Setup

## 🎯 Learning Objectives
By the end of this lab, you will:
- Understand the workshop **scenario** and the round-trip you'll build
- Have the repository in your Databricks workspace as a **Git folder**
- Have the access you need (for facilitators: provisioned it for the whole group)
- Know where to start

## Introduction

You're going to build the **Apps + Lakebase round-trip**: analytical data in Unity Catalog,
served operationally through Lakebase (Postgres) and a Databricks App, with the app's writes
flowing straight back to the analytical layer — one governed platform, no ETL in between.

The example is a shop-floor **Maintenance Cockpit** (see [`docs/scenario.md`](../docs/scenario.md)),
but the pattern fits anywhere operational people need to act on analytical data. The
architecture at a glance:

![Architecture](../docs/architecture.svg)

New to the concepts? Read [`docs/concepts.md`](../docs/concepts.md) (10 min) — Lakebase vs the
lakehouse, synced tables, and why the app's write reappears in SQL.

## Instructions

### Step 1 — (Facilitator / workspace admin, once) Provision access

> Skip this step if you're an attendee — your facilitator has done it.

A workspace admin runs [`bundle/src/notebooks/admin_setup.py`](../bundle/src/notebooks/admin_setup.py)
once. It creates a `lakebase-workshop-participants` group and grants it everything participants
need: workspace + SQL entitlements, `USE CATALOG` + `CREATE SCHEMA` on `lakebase_workshop`,
`CREATE CATALOG` on the metastore, and `CAN_USE` on a SQL warehouse.

1. Open `bundle/src/notebooks/admin_setup.py`.
2. Edit the config cell — the group name and the list of participant emails.
3. **Run all**. Then complete the two manual steps it prints (Lakebase project access, Apps
   creation). Full reference: [`docs/roles-and-permissions.md`](../docs/roles-and-permissions.md).

**💡 What just happened?**
Every participant is now in one group with all the rights the labs need, so nobody hits a
permission wall mid-workshop.

### Step 2 — Add the repo to your workspace (Git folder)

1. In the Databricks sidebar, click **Workspace**.
2. Navigate to your home folder → **Create ▸ Git folder**.
3. Paste the repository URL and click **Create**.
4. Expand the folder — you'll see `labs/`, `bundle/`, and `docs/`. This brings both the lab
   guides **and** the app code into your workspace (Lab 3 needs both).

### Step 3 — Confirm your prerequisites

Before you start, please verify:
- You can run **serverless** notebooks.
- You have access to a **SQL Warehouse** (a running one — for the queries in Labs 2 & 4).
- The shared Lakebase project **`lakebase-workshop`** exists (facilitator sets it up; if you're
  going solo, Lab 2 shows how to create it).

### Step 4 — Choose your starting point

The labs run in order and build on each other. Start at Lab 1.

| Lab | Topic | Guide |
|-----|-------|-------|
| **Lab 1** | Generate the analytical data in Unity Catalog | [guide](Lab%201%20-%20Generate%20Analytical%20Data.md) |
| **Lab 2** | Sync it into Lakebase (Postgres) as read-only serving tables | [guide](Lab%202%20-%20Sync%20to%20Lakebase.md) |
| **Lab 3** | Build & deploy the Maintenance Cockpit app; implement the write-back | [guide](Lab%203%20-%20Build%20and%20Deploy%20the%20App.md) |
| **Lab 4** | Close the round-trip — the app's writes, live in Databricks SQL | [guide](Lab%204%20-%20Close%20the%20Round-Trip.md) |

> **Facilitator shortcut:** instead of running the labs by hand, you can deploy the whole
> stack with the bundle — see [`bundle/README.md`](../bundle/README.md).

➡️ **Next: [Lab 1 – Generate Analytical Data](Lab%201%20-%20Generate%20Analytical%20Data.md).**
