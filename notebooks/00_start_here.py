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
# MAGIC Each step is a **notebook** you run cell by cell. Steps 02 & 03 also show a UI path and
# MAGIC have a laptop-CLI alternative.
# MAGIC
# MAGIC | # | Step | Notebook |
# MAGIC |---|------|----------|
# MAGIC | **00** | Orientation (you're here) | this notebook |
# MAGIC | **01** | Generate analytical data → UC | `01_generate_data` |
# MAGIC | **02** | Create Lakebase DB + UC catalog + snapshot synced tables | `02_create_lakebase` |
# MAGIC | **03** | Deploy the Streamlit app + implement the write-back | `03_deploy_app` |
# MAGIC | **04** | Explore Lakebase + prove the round-trip | `04_explore_and_roundtrip` |
# MAGIC
# MAGIC The full map with prerequisites and teardown: `docs/attendee-runbook.md`.
# MAGIC
# MAGIC **How it runs:** every step is a notebook you execute cell by cell in this workspace —
# MAGIC no laptop setup. The infra steps (02, 03) use the Databricks SDK, and each also shows the
# MAGIC equivalent UI clicks; if you'd rather drive them from a laptop, the `databricks` CLI
# MAGIC versions are in `sync/02_create_lakebase.md` and `docs/03_deploy_app.md`.

# COMMAND ----------
# MAGIC %md
# MAGIC ## Prerequisites
# MAGIC - Access to this workspace with serverless + a SQL warehouse.
# MAGIC - This repo opened as a **Workspace Git folder** (so the notebooks and `app/` code are here).
# MAGIC - The shared Lakebase project `lakebase-workshop` exists (facilitator sets it up; solo
# MAGIC   learners: notebook 02 shows how to create it).
# MAGIC
# MAGIC ➡️ **Next:** open **`01_generate_data`**.
