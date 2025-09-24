import streamlit as st
from dashboard import TreasuryDashboard
import ingest

DB_PATH = "./data/db/database.db"

if __name__ == "__main__":
    # Check if the dashboard is already in session_state
    if "dashboard" not in st.session_state:
        st.session_state.dashboard = TreasuryDashboard(db_path="./data/db/database.db")

    # Access the persistent instance
    dashboard = st.session_state.dashboard

    # Render the dashboard
    dashboard.render_dashboard()
