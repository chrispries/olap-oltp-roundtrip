import streamlit as st

import db

st.set_page_config(page_title="Shop-Floor Maintenance", layout="wide")
st.title("🔧 Shop-Floor Maintenance")
st.caption("Reads served from Lakebase synced tables · writes flow back to the lakehouse")

conn = db.get_connection()
db.ensure_app_table(conn)

left, right = st.columns(2)
with left:
    st.subheader("Machines")
    st.dataframe(db.list_machines(conn), use_container_width=True, hide_index=True)
with right:
    st.subheader("Open tickets")
    st.dataframe(db.open_tickets(conn), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Report a maintenance ticket")
with st.form("new_ticket", clear_on_submit=True):
    machine_id = st.number_input("Machine ID", min_value=1, max_value=50, step=1)
    priority = st.selectbox("Priority", ["low", "medium", "high"])
    description = st.text_input("Description", placeholder="e.g. vibration alarm on spindle")
    submitted = st.form_submit_button("Create ticket")

if submitted:
    try:
        tid = db.create_maintenance_ticket(conn, int(machine_id), priority, description)
        st.success(f"Created ticket #{tid} — now query it from Databricks SQL to see the round-trip.")
        st.rerun()
    except NotImplementedError:
        st.warning("Write-back not implemented yet — complete create_maintenance_ticket() in app/db.py (Task 5).")
