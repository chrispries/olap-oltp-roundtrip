# The scenario — "Keep the line running"

Use this to open the workshop (2–3 minutes). It frames *why* Apps + Lakebase exist, using
the exact data everyone is about to work with.

## The one-liner

> Manufacturing data already sits in tables in Unity Catalog. But the people who need it most
> — the technicians keeping machines running — can't work off a data warehouse. **Lakebase +
> Apps** serve that data operationally, let those people act on it, and play their actions
> straight back into analytics.

## The story

**TRUMPF runs 50 CNC machines** — TruLaser, TruBend, TruPunch, TruMatic — across three
production lines in four plants. Every machine streams telemetry (temperature, vibration,
spindle load) into the lakehouse, next to its production orders and years of maintenance
history. The data team already mines all of it: OEE reporting, and a vibration-based
failure-prediction model.

**But that intelligence is trapped in dashboards.** At 2 a.m., machine #7's vibration
climbs past its limit. The night-shift technician isn't going to open a BI dashboard — they
need a dead-simple app on a tablet: *"Which of my machines need attention right now, and let
me log what I did about it."*

That's an **operational** job — instant single-row lookups and writes — and the analytical
lakehouse isn't built for it. Standing up a separate Postgres and a bespoke sync would mean a
second system to secure and govern. That's the gap Lakebase + Apps close.

## How the data maps to the round-trip

| Stage | What happens | Data |
|-------|--------------|------|
| **Analytical (UC)** | It's already here | `machines`, `sensor_readings`, `production_orders`, `maintenance_tickets` as Delta |
| **① Sync → Lakebase** | Serve it operationally (ms reads) | synced tables in Postgres |
| **② Read in the app** | The **Maintenance Cockpit** shows each technician their machines + open alerts | reads synced tables |
| **③ Write-back** | Technician logs a fix: *"replaced coolant filter on TruLaser #7 — vibration back to normal"* | new row in the app's Postgres table |
| **④ Back to analytics** | Governed by UC, that action is instantly queryable in SQL — measure MTTR, retrain the failure model | UC federation, no copy |

## The payoff line

> **One governed platform serves both the analyst and the technician — and the technician's
> actions make the analytics smarter.** No second database to secure, no nightly ETL. From a
> vibration signal all the way to a wrench on the shop floor, and back to the model that
> predicted it.

## The demo hook (what they'll see first)

The seeded data plants four machines that clearly **need attention** — open, high-priority
tickets with vivid faults and elevated vibration:

- **TruLaser #7** — vibration alarm, bearing wear
- **#19** — coolant low
- **#31** — laser calibration drift
- **#44** — spindle overheating

So when the app opens, it immediately reads as a real cockpit: "these machines need a
technician now." (Seeded deterministically in `notebooks/01_generate_data`, Step 3.5.)
