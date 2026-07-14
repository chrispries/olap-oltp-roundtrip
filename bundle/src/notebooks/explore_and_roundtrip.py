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
# MAGIC ## Step 3 · The round-trip — read what the *technician* did
# MAGIC
# MAGIC The app can't modify the synced `maintenance_tickets` (synced tables are read-only), so
# MAGIC the technician's work — claims and resolutions — is written to the app-owned table
# MAGIC **`maintenance_actions`**. Because UC federates the whole Postgres database, that table
# MAGIC shows up here too.
# MAGIC
# MAGIC **Try it live:**
# MAGIC 1. Run the cell below — note the row count (may be 0 if nobody has worked an alert yet).
# MAGIC 2. Open your app, **claim** an alert and **resolve** it with a note.
# MAGIC 3. Re-run the cell — your resolution appears. **That's the round-trip.** 🎉

# COMMAND ----------
def show_actions():
    try:
        df = spark.sql(f"""
            SELECT machine_id, technician, status, resolution, claimed_at, resolved_at
            FROM {LBCAT}.public.maintenance_actions
            ORDER BY COALESCE(resolved_at, claimed_at) DESC
        """)
        print(f"technician actions: {df.count()}")
        display(df)
    except Exception as e:
        print("maintenance_actions not found yet — open the app once (it creates the table on "
              "first load) and work an alert, then re-run.\n", e)

show_actions()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4 · What the data team gets back (repair-time analytics)
# MAGIC
# MAGIC Join the technician's resolutions to the original alerts to compute **time-to-fix** — the
# MAGIC kind of metric (MTTR) that feeds the failure model. Operational actions, analytics-ready,
# MAGIC with no ETL.

# COMMAND ----------
display(spark.sql(f"""
  SELECT a.machine_id, m.model, a.technician, a.resolution,
         round((unix_timestamp(a.resolved_at) - unix_timestamp(t.opened_at)) / 3600.0, 1) AS hours_to_fix
  FROM {LBCAT}.public.maintenance_actions a
  JOIN {LBCAT}.public.machines m ON m.machine_id = a.machine_id
  LEFT JOIN {LBCAT}.public.maintenance_tickets t ON t.ticket_id = a.ticket_id
  WHERE a.status = 'resolved'
  ORDER BY a.resolved_at DESC
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC ### ✅ That's the whole loop
# MAGIC UC → Lakebase → app → back to UC, on one governed platform. For a dashboard over this
# MAGIC data see `docs/dashboard.md`.
# MAGIC
# MAGIC ### 🧹 Done exploring? Tear down to avoid lingering cost
# MAGIC When you're finished, clean up your resources (app, synced tables, catalog, database) —
# MAGIC the commands are in `docs/facilitator-notes.md` (**Step 05 · Teardown**). The shared
# MAGIC Lakebase project scales to zero when idle, so it's cheap to leave between sessions.
