import datetime as dt

import streamlit as st

import db

st.set_page_config(page_title="Maintenance Cockpit", layout="wide")
st.title("🔧 Maintenance Cockpit")
st.caption("Reference data served from Lakebase · your operational writes flow straight back to the lakehouse")


def who_am_i() -> str:
    """The signed-in Databricks user, forwarded by Databricks Apps. Falls back to blank."""
    try:
        h = st.context.headers
        email = h.get("X-Forwarded-Email") or h.get("X-Forwarded-Preferred-Username") or ""
        return email.split("@")[0]
    except Exception:
        return ""


with st.sidebar:
    st.subheader("On shift")
    me = st.text_input("You are", value=who_am_i(), placeholder="your name")
    if not me:
        st.warning("Enter your name to log work.")
    st.divider()
    st.caption("Everything you write here lands in Unity Catalog within seconds "
               "(`lb_*_history`) — that's the round-trip.")

conn = db.get_connection()
machines = db.machines(conn)
machine_ids = [m["machine_id"] for m in machines]
machine_label = {m["machine_id"]: f"#{m['machine_id']} · {m['model']} ({m['line']})" for m in machines}


def pick_machine(key: str, label: str = "Machine"):
    return st.selectbox(label, machine_ids, format_func=lambda i: machine_label.get(i, f"#{i}"), key=key)


alerts_tab, wo_tab, qc_tab, notes_tab = st.tabs(
    ["🔴 Alerts & actions", "📋 Work orders", "✅ Quality checks", "📝 Operator notes"])

# --- Tab 1: Alerts & maintenance actions -------------------------------------
with alerts_tab:
    st.subheader("🔴 Open alerts")
    st.caption("Seeded, high-priority tickets from the lakehouse (read-only synced table).")
    alerts = db.open_alerts(conn)
    if not alerts:
        st.success("No open alerts — the line is running clean. 🎉")

    for a in alerts:
        with st.container(border=True):
            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"**{a['model']} #{a['machine_id']}** · {a['line']} · "
                            f":red[{a['priority'].upper()}]")
                st.caption(a["description"])
                if a["actioned_by"]:
                    st.caption(f"🔧 {a['action_status']} — {a['actioned_by']}")
            with right:
                with st.form(f"action-{a['ticket_id']}", clear_on_submit=True):
                    action_type = st.selectbox("Action", ["corrective", "preventive", "inspection"],
                                               key=f"type-{a['ticket_id']}")
                    note = st.text_input("What did you do?", key=f"desc-{a['ticket_id']}",
                                         placeholder="e.g. replaced coolant filter")
                    done = st.checkbox("Completed", value=True, key=f"done-{a['ticket_id']}")
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
                                       "log_maintenance_action() in db.py (see Lab 3, Step 4).")

    st.divider()
    st.subheader("🔧 Recent maintenance actions")
    st.dataframe(db.recent_actions(conn), use_container_width=True, hide_index=True)

# --- Tab 2: Work orders ------------------------------------------------------
with wo_tab:
    st.subheader("📋 Open work orders")
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
            if st.form_submit_button("Create work order", disabled=not (me and wo_title)):
                db.create_work_order(conn, wo_machine, wo_priority, wo_title, wo_desc,
                                     wo_assignee, wo_due, "assigned" if wo_assignee else "open")
                st.success("Work order created.")
                st.rerun()

# --- Tab 3: Quality checks ---------------------------------------------------
with qc_tab:
    st.subheader("✅ Recent quality checks")
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
    st.dataframe(db.recent_notes(conn), use_container_width=True, hide_index=True)

    with st.expander("➕ Add a note"):
        with st.form("new-note", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                n_machine = pick_machine("note-machine")
            with c2:
                n_type = st.selectbox("Type", ["general", "alert", "handoff", "resolution"])
            n_content = st.text_area("Note", placeholder="what happened / what to watch")
            if st.form_submit_button("Add note", disabled=not (me and n_content)):
                db.add_operator_note(conn, n_machine, n_type, n_content, me)
                st.success("Note added.")
                st.rerun()
