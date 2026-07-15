"""Maintenance Cockpit — a Streamlit Databricks App.

A shop-floor technician's view over the factory's data: it *reads* reference data (machines,
open alerts) served from Lakebase Postgres, and *writes* the technician's work (maintenance
actions, work orders, quality checks, notes) back to Lakebase — which Change Data Feed streams
into the lakehouse (Lab 4). All data access lives in db.py; this file is only the UI.
"""
import datetime as dt

import streamlit as st

import db

st.set_page_config(page_title="Maintenance Cockpit", layout="wide")
st.title("🔧 Maintenance Cockpit")
st.caption("Reference data served from Lakebase · your writes flow straight back to the lakehouse")


def who_am_i() -> tuple[str, str]:
    """The signed-in user, taken from the SSO token — never typed in.

    Databricks Apps run as a service principal, but still forward the *signed-in* user's identity
    as request headers. We read it from there and stamp it on every write, so work is always
    attributed to the real person — you can't log under someone else's name. Returns
    (email, short_name); falls back to blank in local dev where the headers are absent.
    """
    try:
        h = st.context.headers
        email = h.get("X-Forwarded-Email") or h.get("X-Forwarded-Preferred-Username") or ""
        return email, (email.split("@")[0] or email)
    except Exception:
        return "", ""


user_email, me = who_am_i()

# --- Sidebar: who's on shift (identity comes from your SSO token, read-only) --
with st.sidebar:
    st.subheader("👷 On shift")
    if me:
        st.success(f"**{me}**")
        if user_email and user_email != me:
            st.caption(user_email)
        st.caption("From your Databricks sign-in — every entry you save is stamped with this.")
    else:
        # Only happens in local dev (no SSO headers); on Databricks you're always identified.
        st.warning("No signed-in identity found — logging is disabled.")
    st.divider()
    st.markdown("**How to use**")
    st.caption("Pick a tab, then log alerts, work orders, quality checks or notes. Everything "
               "you save appears in Databricks SQL within seconds (`lb_*_history`) — the round-trip.")

# One Lakebase connection per app run; db.py mints a fresh OAuth token for it (no password).
conn = db.get_connection()

# Machines power the dropdowns; build a friendly "#7 · Press Brake (Line-A)" label for each.
machines = db.machines(conn)
machine_ids = [m["machine_id"] for m in machines]
machine_label = {m["machine_id"]: f"#{m['machine_id']} · {m['model']} ({m['line']})" for m in machines}


def pick_machine(key: str, label: str = "Machine"):
    """A machine picker used across the create-forms."""
    return st.selectbox(label, machine_ids, format_func=lambda i: machine_label.get(i, f"#{i}"), key=key)


# Write buttons stay disabled if there's no signed-in identity — only happens in local dev.
if not me:
    st.info("👋 Sign in through Databricks to log work — the action buttons unlock once your "
            "identity is known.")

alerts_tab, wo_tab, qc_tab, notes_tab = st.tabs(
    ["🔴 Alerts & actions", "📋 Work orders", "✅ Quality checks", "📝 Operator notes"])

# --- Tab 1: Alerts & maintenance actions -------------------------------------
with alerts_tab:
    st.subheader("🔴 Open alerts")
    st.caption("High-priority tickets from the lakehouse (read-only). Log an action and mark it "
               "**Completed** to clear it from this queue.")

    # Sort/filter the queue — handled in SQL (db.open_alerts) so it scales past what's on screen.
    _SORTS = {"Priority": "priority", "Oldest first": "oldest", "Machine": "machine"}
    ctrl_l, ctrl_r = st.columns(2)
    with ctrl_l:
        sort_label = st.selectbox("Sort by", list(_SORTS), key="alert-sort")
    with ctrl_r:
        prio_label = st.selectbox("Show", ["All", "high", "medium", "low"], key="alert-prio")
    alerts = db.open_alerts(conn, sort=_SORTS[sort_label],
                            priority=None if prio_label == "All" else prio_label)

    # Cockpit counters — a quick read on the queue before you scroll it.
    counts = {p: sum(1 for a in alerts if a["priority"] == p) for p in ("high", "medium", "low")}
    m_total, m_high, m_med = st.columns(3)
    m_total.metric("Open", len(alerts))
    m_high.metric("High", counts["high"])
    m_med.metric("Medium", counts["medium"])

    if not alerts:
        st.success("No open alerts — the line is running clean. 🎉")

    for a in alerts:
        with st.container(border=True):
            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"**{a['model']} #{a['machine_id']}** · {a['line']} · "
                            f":red[{a['priority'].upper()}]")
                st.caption(a["description"])
                if a["actioned_by"]:                       # someone already picked this up
                    st.caption(f"🔧 {a['action_status']} — {a['actioned_by']}")
            with right:
                # One form per alert. The submit only gates on `me` (a sidebar value that's stable
                # across reruns) — NOT on the fields inside this form, which Streamlit only reads on
                # submit (gating on them would leave the button permanently greyed).
                with st.form(f"action-{a['ticket_id']}", clear_on_submit=True):
                    action_type = st.selectbox("Action", ["corrective", "preventive", "inspection"],
                                               key=f"type-{a['ticket_id']}")
                    note = st.text_input("What did you do?", key=f"desc-{a['ticket_id']}",
                                         placeholder="e.g. replaced coolant filter")
                    done = st.checkbox("Completed (clears the alert)", value=True,
                                       key=f"done-{a['ticket_id']}")
                    if st.form_submit_button("Log action", disabled=not me,
                                             use_container_width=True):
                        try:
                            db.log_maintenance_action(
                                conn, a["machine_id"], a["ticket_id"], action_type, note, me,
                                "completed" if done else "in_progress")
                            st.success("Logged — now flowing back to Databricks SQL.")
                            st.rerun()
                        except NotImplementedError:
                            st.warning("Write-back not implemented yet — complete "
                                       "log_maintenance_action() in db.py (see Lab 3, Step 5).")

    st.divider()
    st.subheader("🔧 Recent maintenance actions")
    st.caption("Your logged work — also queryable in Databricks SQL as `lb_maintenance_actions_history`.")
    st.dataframe(db.recent_actions(conn), use_container_width=True, hide_index=True)

# --- Tab 2: Work orders ------------------------------------------------------
with wo_tab:
    st.subheader("📋 Open work orders")
    st.caption("Planned jobs, most urgent first. Use the form below to raise a new one.")
    st.dataframe(db.open_work_orders(conn), use_container_width=True, hide_index=True)

    with st.expander("➕ Raise a work order"):
        with st.form("new-wo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                wo_machine = pick_machine("wo-machine")
                wo_priority = st.selectbox("Priority", ["low", "medium", "high", "critical"], index=1)
                wo_due = st.date_input("Due date", value=dt.date.today() + dt.timedelta(days=3))
            with c2:
                wo_title = st.text_input("Title", placeholder="e.g. Replace spindle bearing")
                wo_assignee = st.text_input("Assign to", value=me, placeholder="technician")
            wo_desc = st.text_area("Description", placeholder="what needs doing and why")
            # Gate on `me` only; the required Title is validated after submit (see note in Tab 1).
            if st.form_submit_button("Create work order", disabled=not me):
                if not wo_title:
                    st.error("Please enter a title.")
                else:
                    db.create_work_order(conn, wo_machine, wo_priority, wo_title, wo_desc,
                                         wo_assignee, wo_due, "assigned" if wo_assignee else "open")
                    st.success("Work order created.")
                    st.rerun()

# --- Tab 3: Quality checks ---------------------------------------------------
with qc_tab:
    st.subheader("✅ Recent quality checks")
    st.caption("Inspection results per production order. Record a new check below.")
    st.dataframe(db.recent_quality_checks(conn), use_container_width=True, hide_index=True)

    with st.expander("➕ Record a quality check"):
        with st.form("new-qc", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                qc_machine = pick_machine("qc-machine")
                qc_order = st.number_input("Order ID", min_value=1, step=1, value=1001)
                qc_type = st.selectbox("Check type", ["visual", "dimensional", "functional"])
            with c2:
                qc_result = st.selectbox("Result", ["pass", "fail", "conditional"])
                qc_defect = st.text_input("Defect code", placeholder="e.g. VIB-003 (optional)")
            qc_notes = st.text_area("Notes")
            if st.form_submit_button("Record check", disabled=not me):
                db.record_quality_check(conn, int(qc_order), qc_machine, qc_type, qc_result,
                                        qc_defect, qc_notes, me)
                st.success("Quality check recorded.")
                st.rerun()

# --- Tab 4: Operator notes ---------------------------------------------------
with notes_tab:
    st.subheader("📝 Operator notes")
    st.caption("Free-text log for anything worth passing on (handoffs, observations).")
    st.dataframe(db.recent_notes(conn), use_container_width=True, hide_index=True)

    with st.expander("➕ Add a note"):
        with st.form("new-note", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                n_machine = pick_machine("note-machine")
            with c2:
                n_type = st.selectbox("Type", ["general", "alert", "handoff", "resolution"])
            n_content = st.text_area("Note", placeholder="what happened / what to watch")
            # Gate on `me` only; the required Note text is validated after submit.
            if st.form_submit_button("Add note", disabled=not me):
                if not n_content:
                    st.error("Please write something in the note.")
                else:
                    db.add_operator_note(conn, n_machine, n_type, n_content, me)
                    st.success("Note added.")
                    st.rerun()
