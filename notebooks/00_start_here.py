# Databricks notebook source
# MAGIC %md
# MAGIC # App + Lakebase in a Day — start here
# MAGIC
# MAGIC You'll build the **round-trip**: analytical data in Unity Catalog → synced into
# MAGIC Lakebase (Postgres) → served by a Streamlit app → the app's writes come back and are
# MAGIC queryable in Databricks SQL. One governed platform, no ETL between them.
# MAGIC
# MAGIC ```
# MAGIC (01) UC Delta ──▶ (02) Lakebase synced tables ──▶ (03) app ──▶ (04) round-trip
# MAGIC ```
# MAGIC
# MAGIC **First, read the concepts** (10 min): `docs/concepts.md` — what Lakebase is, why synced
# MAGIC tables are read-only, how the app authenticates, why the write reappears in SQL.

# COMMAND ----------
# MAGIC %md
# MAGIC ## The sequence
# MAGIC
# MAGIC | # | Step | How you run it | Why |
# MAGIC |---|------|----------------|-----|
# MAGIC | **00** | Orientation (you're here) | This notebook | — |
# MAGIC | **01** | Generate analytical data → UC | Notebook `01_generate_data` | Pure Spark/SQL — notebook-native |
# MAGIC | **02** | Create Lakebase DB, register UC catalog, snapshot synced tables | CLI: `sync/02_create_lakebase.md` | Infra provisioning — done with the `databricks` CLI |
# MAGIC | **03** | Deploy the Streamlit app + implement the write-back | CLI: `docs/03_deploy_app.md` (code in `app/`) | App create/deploy is a CLI/deploy workflow |
# MAGIC | **04** | Explore Lakebase + prove the round-trip | Notebook `04_explore_and_roundtrip` | SQL exploration — notebook-native |
# MAGIC
# MAGIC The full map with prerequisites and teardown: `docs/attendee-runbook.md`.
# MAGIC
# MAGIC **Why the split?** Data generation and querying live naturally in a notebook (Spark +
# MAGIC `%sql`, right next to the data). Creating a Lakebase instance and deploying an app are
# MAGIC infrastructure operations you drive with the `databricks` CLI — the runbook gives you
# MAGIC copy-paste commands with a ✅ check at every step.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Prerequisites
# MAGIC - Access to this workspace with serverless + a SQL warehouse.
# MAGIC - The Databricks CLI on your laptop for steps 02–03 (`databricks -p <profile> current-user me`).
# MAGIC - The shared Lakebase project `lakebase-workshop` exists (facilitator sets it up).
# MAGIC
# MAGIC ➡️ **Next:** open **`01_generate_data`**.
