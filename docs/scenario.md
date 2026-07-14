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

Picture a factory with **50 machines** — laser cutters, press brakes, punch presses, milling
machines. (They're "CNC" machines: *Computer Numerical Control*, meaning computer-controlled
tools.) Each machine constantly reports how it's doing — temperature, vibration, and how hard
it's working — into the lakehouse, alongside its production orders and past repairs. The data
team already uses all of this: productivity reporting (**OEE** — *Overall Equipment
Effectiveness*, the standard factory scorecard) and a model that predicts breakdowns from
rising vibration.

**But that intelligence is trapped in dashboards.** At 2 a.m., machine #7 starts vibrating
past its safe limit. The night-shift technician isn't going to open a BI dashboard — they need
a dead-simple app on a tablet: *"which of my machines need attention right now, and let me log
what I did about it."*

That's an **operational** job — instant single-record lookups and writes — and an analytical
lakehouse (built for big scans, not single-row speed) isn't the right tool. Standing up a
separate database and a custom sync would mean a second system to secure and govern. That's
the gap Lakebase + Apps close.

## How the data maps to the round-trip

| Stage | What happens | Data |
|-------|--------------|------|
| **Analytical (Unity Catalog)** | It's already here | `machines`, `sensor_readings`, `production_orders`, `maintenance_tickets` as Delta tables |
| **① Sync → Lakebase** | Serve it operationally (millisecond reads) | synced tables in Postgres |
| **② Read in the app** | The **Maintenance Cockpit** shows each technician their machines + open alerts | reads the synced tables |
| **③ Write-back** | Technician logs a fix: *"replaced coolant filter on machine #7 — vibration back to normal"* | new row in the app's Postgres table |
| **④ Back to analytics** | Because it's governed by Unity Catalog, that action is instantly queryable in SQL — measure repair time, retrain the prediction model | UC federation, no copy |

## The payoff line

> **One governed platform serves both the analyst and the person on the floor — and their
> actions make the analytics smarter.** No second database to secure, no overnight data
> copying. From an early-warning signal all the way to a fix on the floor, and back to the
> model that predicted it.

## What you'll see first

The sample data includes four machines flagged for attention — each with elevated vibration and
an open, high-priority maintenance ticket:

| Machine | Alert |
|---------|-------|
| **#7** | vibration alarm (bearing wear) |
| **#19** | coolant low |
| **#31** | calibration drift |
| **#44** | spindle (rotating tool) overheating |

So the app opens onto a realistic maintenance queue instead of an empty screen — you can claim
and resolve one of these alerts right away and watch it flow back to the analytical layer. This
data is generated deterministically (Lab 1, Step 3), so every run looks the same.
