# Round-trip dashboard (stretch / optional)

A one-page AI/BI (Lakeview) dashboard that visualizes the same `app_maintenance_tickets`
data the app writes back — proving the round-trip visually. Build per the
`fe-databricks-tools:databricks-lakeview-dashboard` skill.

Suggested widgets (dataset = `<lakebase_catalog>.ws_${user}.app_maintenance_tickets`,
optionally UNION with the seeded `maintenance_tickets`):

1. **Open tickets by priority** — bar chart, count by `priority` where `status='open'`.
2. **Tickets over time** — line chart, count by day of `opened_at` (app writes appear live).
3. **Machines** — table of `machines` for reference.

Mark as optional; only build if the core round-trip finishes with time to spare.
