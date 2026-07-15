# Round-trip dashboard (stretch / optional)

A one-page AI/BI (Lakeview) dashboard that visualizes the `lb_maintenance_actions_history`
data CDF streams back — proving the round-trip visually. Build per the
`fe-databricks-tools:databricks-lakeview-dashboard` skill.

Suggested widgets (source: `catalog_workshop.schema_<you>.lb_maintenance_actions_history`, joined
to the seeded `maintenance_tickets` / `machines` in the same schema for context):

1. **Open alerts remaining** — counter: open `maintenance_tickets` with no completed action.
2. **Actions over time** — line chart, count by day of `completed_at` (app writes appear live).
3. **Avg time-to-fix by machine model** — bar chart of `completed_at − opened_at`, joined to `machines`.

Mark as optional; only build if the core round-trip finishes with time to spare.
