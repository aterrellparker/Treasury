import cProfile
import pstats
import pandas as pd
import ingest

import streamlit as st

from dashboard import TreasuryDashboard


DB_PATH = "./data/db/database.db"

def main():
    # Check if the dashboard is already in session_state
    if "dashboard" not in st.session_state:
        st.session_state.dashboard = TreasuryDashboard(db_path="./data/db/database.db")

    # Access the persistent instance
    dashboard = st.session_state.dashboard

    # Render the dashboard
    dashboard.render_dashboard()

if __name__ == "__main__":
    main()
    # cProfile.run("main()", "profile_output.prof")
    # p = pstats.Stats('profile_output.prof')
    # p.sort_stats('cumulative').print_stats(20) # Sort by cumulative time and print top 20

    # date = "2024-09-29 19:32:00+00:00"
    # amount = "97.25"
    # description = "Chapter Dues - Terrell Parker - Cash Balance"
    # print(ingest.DataManager.generate_id(date + amount + description))
    # date = "2024-09-29 13:29:32+00:00"
    # amount = "25.00"
    # description = "$25 Payment From Sean Hall - Sean Hall - Cash Balance"
    # print(ingest.DataManager.generate_id(date + amount + description))