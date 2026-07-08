# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Explore Lakebase + see the round-trip
# MAGIC
# MAGIC **Run this after** you've created your synced tables (`02_sync_to_lakebase`, the CLI
# MAGIC runbook) and deployed + used the app (`03`). It reads your Lakebase data **from the
# MAGIC analytical layer** (Databricks SQL over the UC-registered Lakebase catalog) and proves
# MAGIC the round-trip: a ticket you create in the app shows up right here.
# MAGIC
# MAGIC ```
# MAGIC (01) UC Delta ──▶ (02) Lakebase synced tables ──▶ (03) app ──▶ 👉 (04) round-trip
# MAGIC ```

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1 · Find your Lakebase catalog
# MAGIC
# MAGIC When you registered your database in UC you created catalog `lakebase_ws_<username>`.
# MAGIC Its schema is `public` (the Postgres schema). Let's derive the name.

# COMMAND ----------
import re

user = spark.sql("SELECT current_user()").first()[0]
slug = re.sub(r"[^a-z0-9]", "_", user.split("@")[0].lower())
LBCAT = f"lakebase_ws_{slug}"      # your Lakebase → UC catalog
print(f"Your Lakebase catalog: {LBCAT}  (schema: public)")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2 · Read the synced tables *through Unity Catalog*
# MAGIC
# MAGIC These tables physically live in Lakebase **Postgres**, but because the database is
# MAGIC registered in UC you can query them with plain Databricks SQL — no copy, no ETL. This
# MAGIC is the same data your app reads operationally.

# COMMAND ----------
display(spark.sql(f"SELECT machine_id, model, line, location FROM {LBCAT}.public.machines ORDER BY machine_id LIMIT 10"))

# COMMAND ----------
display(spark.sql(f"""
  SELECT priority, count(*) AS open_tickets
  FROM {LBCAT}.public.maintenance_tickets
  WHERE status = 'open'
  GROUP BY priority ORDER BY open_tickets DESC
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3 · The round-trip — read what the *app* wrote
# MAGIC
# MAGIC The app can't write to the synced `maintenance_tickets` (synced tables are read-only),
# MAGIC so it writes new tickets to its own table **`app_maintenance_tickets`**. Because UC
# MAGIC federates the whole Postgres database, that table shows up here too.
# MAGIC
# MAGIC **Try it live:**
# MAGIC 1. Run the cell below — note the row count (may be 0 if you haven't used the app yet).
# MAGIC 2. Open your app, create a maintenance ticket.
# MAGIC 3. Re-run the cell — your ticket appears. **That's the round-trip.** 🎉

# COMMAND ----------
def show_app_tickets():
    try:
        df = spark.sql(f"""
            SELECT ticket_id, machine_id, priority, status, description, opened_at
            FROM {LBCAT}.public.app_maintenance_tickets
            ORDER BY opened_at DESC
        """)
        print(f"app-written tickets: {df.count()}")
        display(df)
    except Exception as e:
        print("app_maintenance_tickets not found yet — start the app once (it creates the "
              "table on first load), then re-run.\n", e)

show_app_tickets()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4 · One view over both (what an analyst would build)
# MAGIC
# MAGIC Seeded tickets + app-written tickets, unified — the operational and analytical worlds
# MAGIC in one query.

# COMMAND ----------
display(spark.sql(f"""
  SELECT 'seeded' AS source, priority, count(*) AS tickets
  FROM {LBCAT}.public.maintenance_tickets WHERE status='open' GROUP BY priority
  UNION ALL
  SELECT 'app'   AS source, priority, count(*) AS tickets
  FROM {LBCAT}.public.app_maintenance_tickets WHERE status='open' GROUP BY priority
  ORDER BY source, tickets DESC
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ### ✅ That's the whole loop
# MAGIC UC → Lakebase → app → back to UC, on one governed platform. For a dashboard over this
# MAGIC data see `analytics/dashboard.md`.
