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
- **Unity Catalog** on a shared catalog (`lakebase_workshop`): **create schemas & tables**, plus
  **create catalogs on the metastore** (so each person can register their Lakebase DB in UC)
- **Lakebase**: access to a shared Lakebase project so they can **create a database, create
  synced tables, and generate DB credentials**
- **Create pipelines** (a synced table spins up a managed pipeline behind the scenes)

Two that sometimes need extra sign-off, so flagging them: **creating apps** and **CREATE CATALOG
on the metastore**. If either isn't possible, no problem — let me know and I'll adjust the setup.

Thanks!

---

**If they say no to one of the flagged items:**
- *No app creation* → the facilitator pre-creates each participant's app.
- *No `CREATE CATALOG` on the metastore* → the facilitator pre-registers one Lakebase catalog per participant.

**Verify it worked:** once access is granted, a participant can run
[`labs/preflight_check.py`](../labs/preflight_check.py) — it tries each right and prints
PASS/FAIL, so you get confirmation without waiting for the workshop day.
