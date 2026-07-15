# Bundle — deploy the app

A [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/bundles/) that packages the
Streamlit **Maintenance Cockpit** (`src/app/`) as a deployable app resource.

Everything else in the workshop is run from the **labs** (`../labs/`) — the code lives inline in
each lab, so there are no separate notebooks to deploy. This bundle exists for workspace admins who
want to push the app with one command instead of the hands-on Lab 3 flow.

## Deploy

```bash
databricks bundle validate -t dev -p <profile>
databricks bundle deploy   -t dev -p <profile>     # uploads app/ + creates the app
databricks bundle run maintenance_cockpit -t dev -p <profile>   # (optional) start it
```

Override the app name with `--var app_name=<name>` (default `lb-workshop-cockpit`).

## After deploy — bind the database (per user)

The app needs to be bound to a Lakebase database and its service principal granted read + write
access. That's per-user, so it's not in the bundle — do it once after deploy, either:
- via **Lab 3, Steps 1–3** (resolve your project + write `app.yaml`, the `apps` resource binding,
  and the `pg_read_all_data` / `pg_write_all_data` / sequence grants), or
- in the app's UI: **Compute ▸ Apps ▸ your app ▸ Edit ▸ Resources ▸ add Database**, then grant
  the app SP `pg_read_all_data`, `pg_write_all_data`, and sequence usage on your database.

See [`../docs/roles-and-permissions.md`](../docs/roles-and-permissions.md) for the full detail.
