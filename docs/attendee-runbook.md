# Attendee Runbook — the 00→04 flow

Your map for the whole workshop. Read [`concepts.md`](concepts.md) first (10 min), then work
the five numbered steps in order. Each step lives in its own file and has ✅ checks so you
always know you're on track.

> **The loop you're building:** UC Delta → synced tables in Lakebase → Streamlit app reads →
> app writes its own Postgres table → that write is queryable back in Databricks SQL.

## The steps

| # | Step | Where | How you run it | ✅ Done when |
|---|------|-------|----------------|--------------|
| **00** | Start here / orientation | [`notebooks/00_start_here`](../notebooks/00_start_here.py) | Notebook | You understand the flow |
| **01** | Generate analytical data → UC | [`notebooks/01_generate_data`](../notebooks/01_generate_data.py) | Notebook (Spark) | `✅ All four tables loaded` (50/10000/200/120) |
| **02** | Create Lakebase + synced tables | [`sync/02_create_lakebase.md`](../sync/02_create_lakebase.md) | CLI | `machines 50` in Postgres **and** via UC SQL |
| **03** | Deploy the app + write-back | [`docs/03_deploy_app.md`](03_deploy_app.md) | CLI + `app/` code | App shows 50 machines; your new ticket appears |
| **04** | Explore + close the round-trip | [`notebooks/04_explore_and_roundtrip`](../notebooks/04_explore_and_roundtrip.py) | Notebook (`%sql`) | Your app-written ticket shows up in SQL 🎉 |

**Why the mix?** Data generation and querying are notebooks (Spark/`%sql`, right next to the
data). Creating the Lakebase database and deploying the app are infrastructure — you drive
them with the `databricks` CLI, which is how you'd really do it. Step 02 sets shared shell
variables that steps 03 and the CLI parts of 04 reuse.

## Prerequisites

- Access to the workshop workspace with serverless + a SQL warehouse.
- **Databricks CLI** ≥ 0.298 authenticated (this guide uses profile `azure-demo` — swap yours).
  Test: `databricks -p azure-demo current-user me`.
- **psql** for the Postgres steps: `brew install postgresql@16` then
  `export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"`.
- The shared Lakebase project `lakebase-workshop` exists (facilitator sets it up; solo
  learners: see step 02).

## Step 05 · Teardown (avoid lingering cost)

After you're done, using the variables from step 02:

```bash
databricks -p $P apps delete $APP
databricks -p $P postgres delete-catalog $LBCAT
for t in machines sensor_readings production_orders maintenance_tickets; do databricks -p $P postgres delete-synced-table $LBCAT.public.$t; done
TOKEN=$(databricks -p $P postgres generate-database-credential $ENDPOINT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=postgres user=$EMAIL sslmode=require" -c "DROP DATABASE $PGDB;"
# facilitator only: databricks -p $P postgres delete-project projects/lakebase-workshop
```
The shared Lakebase project scales to zero when idle, so leaving it between sessions is cheap.
