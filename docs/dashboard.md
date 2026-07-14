# Round-trip dashboard (stretch / optional)

A one-page AI/BI (Lakeview) dashboard that visualizes the same `maintenance_actions`
data the app writes back — proving the round-trip visually. Build per the
`fe-databricks-tools:databricks-lakeview-dashboard` skill.

Suggested widgets (join `<lakebase_catalog>.schema_${user}.maintenance_actions` to the seeded
`maintenance_tickets` for context):

1. **Open alerts remaining** — counter: open `maintenance_tickets` with no `resolved` action.
2. **Resolutions over time** — line chart, count by day of `resolved_at` (app writes appear live).
3. **Avg time-to-fix by machine model** — bar chart of `resolved_at − opened_at`, joined to `machines`.

Mark as optional; only build if the core round-trip finishes with time to spare.
