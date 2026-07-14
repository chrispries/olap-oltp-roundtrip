import streamlit as st

import db

st.set_page_config(page_title="Maintenance Cockpit", layout="wide")
st.title("🔧 Maintenance Cockpit")
st.caption("Alerts served from Lakebase · your fixes flow straight back to the lakehouse")


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
    tech = st.text_input("You are", value=who_am_i(), placeholder="your name")
    if not tech:
        st.warning("Enter your name to claim and resolve alerts.")

conn = db.get_connection()
db.ensure_app_table(conn)

# --- Active alert queue ------------------------------------------------------
st.subheader("🔴 Active alerts")
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
            if a["claimed_by"]:
                st.caption(f"🔧 in progress — {a['claimed_by']}")
        with right:
            if a["action_status"] != "in_progress":
                if st.button("Claim", key=f"claim-{a['ticket_id']}", disabled=not tech,
                             use_container_width=True):
                    db.claim_alert(conn, a["ticket_id"], a["machine_id"], tech)
                    st.rerun()
            with st.form(f"resolve-{a['ticket_id']}", clear_on_submit=True):
                note = st.text_input("What did you do to fix it?",
                                     key=f"note-{a['ticket_id']}",
                                     placeholder="e.g. replaced coolant filter")
                if st.form_submit_button("Resolve alert", disabled=not tech,
                                         use_container_width=True):
                    try:
                        db.resolve_alert(conn, a["ticket_id"], a["machine_id"], tech, note)
                        st.success(f"Resolved — now queryable in Databricks SQL.")
                        st.rerun()
                    except NotImplementedError:
                        st.warning("Write-back not implemented yet — complete resolve_alert() "
                                   "in db.py (workshop step).")

# --- Round-trip: resolved work, back in the lakehouse ------------------------
st.divider()
st.subheader("✅ Recently resolved")
st.caption("Every row here is also visible to the data team in Databricks SQL — that's the round-trip.")
st.dataframe(db.recent_resolutions(conn), use_container_width=True, hide_index=True)
