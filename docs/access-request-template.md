# Organizer checklist — access to confirm before the workshop

Send this to whoever owns the workspace the workshop runs in, to confirm participants have the
rights they need. (Full technical detail: [`roles-and-permissions.md`](roles-and-permissions.md).)

---

**Subject: Access confirmation for the App + Lakebase workshop**

Hey team!

I'm running an "App + Lakebase in a Day" workshop in your workspace and just want to confirm the
participants (ideally all in one group) have the rights to do the following. Could you confirm
these are OK?

- **Run serverless notebooks** and **use a SQL warehouse** (`CAN_USE` on a running one)
- **Create Databricks Apps** (Apps enabled + app creation allowed for the group)
- **Unity Catalog** on a shared catalog (`catalog_workshop`): **create schemas & tables**, plus
  **create catalogs on the metastore** (so each person can register their Lakebase DB in UC)
- **Lakebase** enabled, with permission to **create their own project**, create synced tables,
  create operational tables, and generate DB credentials (each person makes their own project —
  there's no shared one)
- **Change Data Feed (CDF) preview** enabled on the workspace *Previews* page (the round-trip
  back to Unity Catalog depends on it)
- **Create pipelines** (a CONTINUOUS synced table spins up a managed pipeline behind the scenes)

Three that sometimes need extra sign-off, so flagging them: **creating apps**, **CREATE CATALOG
on the metastore**, and **enabling the CDF preview**. If any isn't possible, no problem — let me
know and I'll adjust the setup.

Thanks!

---

**If they say no to one of the flagged items:**
- *No app creation* → a workspace admin pre-creates each user's app.
- *No `CREATE CATALOG` on the metastore* → a workspace admin pre-registers one Lakebase catalog per user.
- *No CDF preview* → Labs 1–3 still work; Lab 4's round-trip back to UC needs it, so ask an admin to toggle it on.

**Verify it worked:** once access is granted, a participant can run
[`labs/preflight_check.py`](../labs/preflight_check.py) — it tries each right and prints
PASS/FAIL, so you get confirmation without waiting for the workshop day.
