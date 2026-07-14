# Databricks notebook source
# MAGIC %md
# MAGIC # ✅ Preflight — do I have the access to run the workshop?
# MAGIC Run all cells. Each check actually *tries* the thing (and cleans up after itself — no
# MAGIC lasting changes) and prints **PASS / FAIL**. Share any FAILs with your workspace admin
# MAGIC (see `docs/organizer-checklist.md`).

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.50" -q
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# ⚙️ Set these to the workshop's values, then Run all.
CATALOG          = "lakebase_workshop"   # the Unity Catalog you'll create your schema in
LAKEBASE_PROJECT = "lakebase-workshop"   # the shared Lakebase (Postgres) project

# COMMAND ----------
import re, uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
user = w.current_user.me().user_name
slug = re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())
tag  = uuid.uuid4().hex[:6]
results = []

def check(name, fn):
    try:
        detail = fn() or ""
        results.append((True, name)); print(f"✅ {name}\n     {detail}")
    except Exception as e:
        results.append((False, name)); print(f"❌ {name}\n     {str(e)[:200]}")

print("running as:", user)

# COMMAND ----------
# 1 — Workspace access + serverless (you're running this notebook, so this works)
check("Workspace access + serverless notebook", lambda: "you ran this notebook on serverless")

# 2 — Unity Catalog: use catalog + create schema/table + select (Lab 1)
def uc_write():
    sch = f"{CATALOG}.preflight_{slug}_{tag}"
    spark.sql(f"CREATE SCHEMA {sch}")
    spark.sql(f"CREATE TABLE {sch}.t (x INT)")
    spark.sql(f"INSERT INTO {sch}.t VALUES (1)")
    spark.table(f"{sch}.t").count()
    spark.sql(f"DROP SCHEMA {sch} CASCADE")
    return f"created, wrote, read and dropped a temp schema in {CATALOG}"
check(f"Unity Catalog — create schema/table/select in '{CATALOG}'", uc_write)

# 3 — CREATE CATALOG on the metastore (Lab 2 registers a Lakebase database as a UC catalog)
def create_catalog():
    c = f"preflight_cat_{slug}_{tag}"
    spark.sql(f"CREATE CATALOG {c}")          # the real test
    try:
        spark.sql(f"DROP CATALOG {c} CASCADE")  # best-effort cleanup (fresh catalog isn't empty)
    except Exception as drop_err:
        print(f"   (note: created OK; cleanup left {c} — drop it manually: {str(drop_err)[:80]})")
    return "can create a catalog"
check("CREATE CATALOG on the metastore", create_catalog)

# 4 — A SQL warehouse you can use (Labs 2 & 4)
def warehouse():
    whs = list(w.warehouses.list())
    if not whs:
        raise Exception("no SQL warehouse visible — you need CAN_USE on one")
    running = [x.name for x in whs if "RUNNING" in str(x.state).upper()]
    return f"{len(whs)} warehouse(s) visible; running: {running or 'none (start one before Lab 2/4)'}"
check("SQL warehouse available", warehouse)

# 5 — Lakebase project access (Labs 2 & 3)
def lakebase():
    branch = f"projects/{LAKEBASE_PROJECT}/branches/production"
    eps = list(w.postgres.list_endpoints(branch))
    if not eps:
        raise Exception(f"no endpoint found on project '{LAKEBASE_PROJECT}'")
    w.postgres.generate_database_credential(f"{branch}/endpoints/primary")  # can you mint a DB token?
    return f"reached project '{LAKEBASE_PROJECT}' and minted a database credential"
check("Lakebase project access", lakebase)

# 6 — Databricks Apps reachable (creating an app is exercised for real in Lab 3)
def apps():
    list(w.apps.list())
    return "Apps API reachable — confirm 'create app' is allowed with your admin if unsure"
check("Databricks Apps reachable", apps)

# COMMAND ----------
# MAGIC %md ## Summary

# COMMAND ----------
fails = [n for ok, n in results if not ok]
if not fails:
    summary = "🎉 All checks passed — you're ready for the workshop."
    print(summary)
else:
    print("⚠️  Not ready yet. Ask your workspace admin about:")
    for n in fails:
        print(f"   • {n}")
    print("\nDetails + the exact grants: docs/organizer-checklist.md")
    summary = "MISSING: " + ", ".join(fails)

try:
    dbutils.notebook.exit(summary)   # surfaces the result if run headless
except Exception:
    pass
