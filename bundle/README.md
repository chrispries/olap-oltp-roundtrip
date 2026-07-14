# Bundle — deploy the workshop stack

A [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/bundles/) that packages the
workshop's runnable assets:

- `src/notebooks/` — the notebooks the labs walk through (`admin_setup`, `generate_data`,
  `create_lakebase`, `deploy_app`, `explore_and_roundtrip`).
- `src/app/` — the Streamlit Maintenance Cockpit app.
- `resources/setup_job.yml` — a job that chains generate → Lakebase → app deploy.

## Who uses this

- **Attendees** don't need the bundle — they clone the repo as a Workspace **Git folder** and
  run the labs (`labs/`) cell by cell.
- **Facilitators** can use it to stand up a full demo environment (or a per-user stack) in one
  command, and it's the "here's how you'd productionize the deploy" talking point.

## Deploy

```bash
databricks bundle validate -t dev -p <profile>
databricks bundle deploy   -t dev -p <profile>     # uploads notebooks + app to the workspace
databricks bundle run app_lakebase_setup -t dev -p <profile>   # generate -> Lakebase -> app
```

Variables (override with `--var` or per target in `databricks.yml`): `catalog`
(default `lakebase_workshop`), `lakebase_project` (default `lakebase-workshop`), `warehouse_id`
(looked up by name). The setup notebooks derive per-user names (`ws_<user>`) from the running
identity, so the deploy provisions a complete environment for whoever runs the job.
