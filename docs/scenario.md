# The scenario — "Keep the line running"

Use this to open the workshop (2–3 minutes). It frames *why* Apps + Lakebase exist, using
the exact data everyone is about to work with. It's a manufacturing example, but the pattern
— analytical data that operational people need to act on — is everywhere (logistics, retail,
fintech, healthcare). No manufacturing background needed.

## The one-liner

> Operational data usually lands in tables in Unity Catalog — great for analytics. But the
> people who need it most, working in real time, can't work off a data warehouse. **Lakebase +
> Apps** serve that data operationally, let those people act on it, and play their actions
> straight back into analytics.

## The story

Picture a factory with **50 machines** — CNC mills, lathes, presses, and welders across three
production lines in two buildings. Each machine constantly reports how it's doing — temperature,
vibration, and how hard it's working — into the lakehouse, alongside its production orders and past
repairs. The data team already uses all of this: productivity reporting (**OEE** — *Overall
Equipment Effectiveness*, the standard factory scorecard) and a model that predicts breakdowns from
rising vibration.

**But that intelligence is trapped in dashboards.** At 2 a.m., one of the machines starts vibrating
past its safe limit while running hot. The night-shift technician isn't going to open a BI
dashboard — they need a dead-simple app on a tablet: *"which of my machines need attention right
now, and let me log what I did about it."*

That's an **operational** job — instant single-record lookups and writes — and an analytical
lakehouse (built for big scans, not single-row speed) isn't the right tool. Standing up a
separate database and a custom sync would mean a second system to secure and govern. That's
the gap Lakebase + Apps close.

## How the data maps to the round-trip

| Stage | What happens | Data |
|-------|--------------|------|
| **Analytical (Unity Catalog)** | It's already here | `machines`, `sensor_readings`, `production_orders`, `maintenance_tickets` as Delta tables |
| **① Sync → Lakebase** | Serve it operationally (millisecond reads) | `SNAPSHOT` synced tables in Postgres |
| **② Read in the app** | The **Maintenance Cockpit** shows each technician their machines + open alerts | reads the synced tables |
| **③ Write-back** | Technician logs a fix: *"replaced coolant filter — vibration back to normal"* — plus work orders, quality checks, notes | rows in the app-owned operational Postgres tables |
| **④ Back to analytics** | **Change Data Feed** streams every write into the lakehouse as `lb_*_history` Delta tables — measure repair time, retrain the prediction model | CDF, ~15s batches |

## The payoff line

> **One governed platform serves both the analyst and the person on the floor — and their
> actions make the analytics smarter.** No second database to secure, no overnight data
> copying. From an early-warning signal all the way to a fix on the floor, and back to the
> model that predicted it.

## What you'll see first

The data is generated from a fixed seed (`np.random.seed(42)`), so the machines, faults, and
priorities are the same on every run (the timestamps are relative to when you run Lab 1). Two
things stand out immediately:

- **A short list of at-risk machines.** Lab 1 runs a quick check for machines showing **both** high
  vibration (> 6 mm/s) **and** high temperature (> 80 °C) — the classic pre-failure signature — and
  surfaces the first four. That's the early-warning signal the model would raise.
- **A live maintenance queue.** Of the 120 seeded tickets, the open ones (roughly a third, with a
  mix of priorities up to *critical*) are what the app opens onto — so it lands on a realistic
  queue instead of an empty screen.

Log an action against one of those tickets right away and watch it flow back to the analytical
layer via Change Data Feed.
