import os
import colorsys
import decimal
import datetime
import calendar 
import sqlite3

import pandas as pd
import streamlit as st
import altair as alt
import numpy as np

import ingest
import report_generator
import PlotlyBubbleChart


def decimal_converter(val: bytes):
    s = val.decode().strip()
    if s in ("", None):  # Handle NULL/empty
        return None
    try:
        return decimal.Decimal(s)
    except NameError:
        # Log or fallback to None
        return None


class TreasuryDashboard:
    def __init__(self, db_path="database.db"):
        st.set_page_config(page_title="Treasury Dashboard", layout="wide",
                           initial_sidebar_state="collapsed", page_icon="./gblogo.png")

        # Initialize DB connection with thread-safety
        sqlite3.register_converter("DECIMAL", decimal_converter)
        sqlite3.register_converter("DATE", lambda date: datetime.datetime.strptime(
            date.decode(), "%Y-%m-%d").date())

        self.data_manager = ingest.DataManager(db_path)
        # self.ingestor.create_database()   # create schema
        # if not os.path.exists(db_path):
        #     self.ingestor.create_database()   # create schema
        #     self.connection = sqlite3.connect(
        #         db_path, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        #     self.ingestor.ingest_data()       # load CSVs

        self.today = datetime.date.today()

        # Initialize default date range
        if "date_range" not in st.session_state:
            st.session_state.date_range = (
                self.today - datetime.timedelta(days=30), self.today)
        self.date_range = st.session_state.date_range

        if "source" not in st.session_state:
            st.session_state.source = ""
        self.source = st.session_state.source

        if "term" not in st.session_state:
            st.session_state.term = "2025-08-01"
        self.term = st.session_state.term
        if "use_custom" not in st.session_state:
            st.session_state.use_custom = False
        

        # Load initial data
        start_date, end_date  = pd.Timestamp(self.date_range[0]), pd.Timestamp(self.date_range[1])
        self.data = self.data_manager.load_data(start_date, end_date,self.source)
        self.dues_data = self.data_manager.load_dues(start_date, end_date)
    # Render dashboard
    def render_dashboard(self):
        """Function"""
        # Hide Streamlit style
        hide_streamlit_style = """
            <style>
                MainMenu {visibility: hidden;}     /* hides hamburger menu */
                footer {visibility: hidden;}        /* hides 'Made with Streamlit' footer */
                header {visibility: hidden;}        /* hides the top blank header */
                .block-container {padding-top: 0rem;}
            </style>
        """
        st.markdown(hide_streamlit_style, unsafe_allow_html=True)
        dashboard, dues, yoy, budget, editor = st.tabs(
            ["📈 Dashboard", "💵 Dues",  "📆 YoY", "📊 Budget",  "📝 Edit Transactions"])
        with editor:
            self.render_transaction_editor()
            self.render_data_buttons()
        with yoy:
            self.render_yoy_chart()
        with dashboard:
            self.render_header()
            self.render_date_selector()
            st.divider()
            self.render_balances()
            self.render_balance_chart()
            self.render_pie_chart()
        with dues:
            self.render_dues_plot()

    # Header Section (logo + title inline)
    def render_header(self):
        col1, col2 = st.columns([1, 9])
        with col1:
            st.image('./gblogo.png', width=100)
        with col2:
            st.markdown(""" <div style="display: flex; flex-direction: column; justify-content: center;"> <h1 style="margin:0">Treasury Dashboard</h1> <p style="margin:0">Alpha Phi Alpha Fraternity, Inc. - Gamma Beta Chapter</p> </div> """,
                        unsafe_allow_html=True
                        )

    # Render date selector
    def render_date_selector(self):
        st.text("")
        col1, col2,col3,= st.columns([3,1.5,3])
        with col1:
            if not st.session_state.use_custom:
                month_range = pd.date_range(start="2019-06-01", end=self.today, freq="MS")[::-1]
                month_options = ["Custom"] + [d.strftime("%B %Y") for d in month_range]

                selected_option = st.selectbox(
                    "Date Range:",
                    label_visibility="collapsed",
                    options=month_options,
                    index=1,  # Default = latest month
                    key="month_selector"
                )
                if selected_option == "Custom":
                    st.session_state.use_custom = True
                    st.rerun()
                else:
                    # Parse selected month into start/end date
                    selected_date = datetime.datetime.strptime(selected_option, "%B %Y")
                    start_date = selected_date.replace(day=1).date()
                    next_month = (selected_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
                    end_date = (next_month - datetime.timedelta(days=1)).date()
                    self.date_range = (start_date, end_date)
            else:
                self.date_range = st.date_input(
                label="Date Range:",
                label_visibility="collapsed",
                key="custom_date_range",
                format="MM.DD.YYYY",
                value=self.date_range
                )
                cola, colb = st.columns([2.5,1])
                with cola:
                    # Reuse your old radio selector
                    date_options = ["Custom", "Past Month", "Past Year", "All Time"]
                    date_selector = st.radio(
                        label="None",
                        label_visibility="collapsed",
                        options=date_options,
                        horizontal=True,
                        key="date_selector"
                    )
                    if date_selector == "Custom":  
                        pass  # Keep self.date_range as-is for a user-defined custom picker
                    elif date_selector == "Past Month":
                        self.date_range = (self.today - datetime.timedelta(days=30), self.today)
                    elif date_selector == "Past Year":
                        self.date_range = (self.today - datetime.timedelta(days=365), self.today)
                    elif date_selector == "All Time":
                        self.date_range = (datetime.date(2019, 6, 14), self.today)
                    elif date_selector == "Back":
                        st.session_state.use_custom = False
                        st.rerun()
                with colb: 
                    if st.button("↩ Month Selector"):
                        st.session_state.use_custom = False
                        st.rerun()
        with col2:
            source_options = ["Both", "Checking", "Cashapp"]
            source_selector = st.radio(
                label="Source:",
                label_visibility="collapsed",
                options=source_options,
                horizontal=True,
                key="source_selector"
            )
            if source_selector == source_options[0]:
                self.source = ""
            elif source_selector == source_options[1]:
                self.source = source_options[1]
            elif source_selector == source_options[2]:
                self.source = source_options[2]
        with col3:
            if st.button("Export Report to Word File", key="generate_report"):
                start_date, end_date  = pd.Timestamp(self.date_range[0]), pd.Timestamp(self.date_range[1])
                report = report_generator.TreasurerReport(start_date, end_date, self.data_manager)
                report.build()
                report.save()
                report.open()
                st.success("Report Generated Successfully")

        # Update session state and reload data if changed
        if self.date_range != st.session_state.date_range:
            st.session_state.date_range = self.date_range
            start_date, end_date = pd.Timestamp(self.date_range[0]), pd.Timestamp(self.date_range[1])
            self.data = self.data_manager.load_data(start_date, end_date, self.source)
            self.dues_data = self.data_manager.load_dues(start_date, end_date)
            # st.rerun()
        # Update session state and reload data if changed
        if self.source != st.session_state.source:
            st.session_state.source = self.source
            start_date, end_date = pd.Timestamp(self.date_range[0]), pd.Timestamp(self.date_range[1])
            self.data = self.data_manager.load_data(start_date, end_date, self.source)
            self.dues_data = self.data_manager.load_dues(start_date, end_date)
            # st.rerun()


    # Render balances
    def render_balances(self):
        st.subheader("Account Balances")
        col1, col2, col3, col4 = st.columns(4)
        delta = self.data["current_balance"] - self.data["initial_balance"]
        sign = '-' if delta < 0 else ''
        with col1:
            st.metric(
                label="Current Balance",
                value=f"${self.data['current_balance']:,.2f}",
                delta=f"{sign}${abs(delta):,.2f}"
            )
        with col2:
            st.metric("Initial Balance", f"${self.data['initial_balance']:,.2f}")
        with col3:
            deposits_sum = self.data["deposits_total"]
            st.metric("Total Receipts", f"${deposits_sum:,.2f}")
        with col4:
            withdrawals_sum = self.data["withdrawals_total"]
            st.metric("Total Expenditures", f"${withdrawals_sum:,.2f}")

    # Render balance chart

    def render_balance_chart(self):
        st.subheader("Balance Over Time")
        chart = alt.Chart(self.data["balance_table"]).mark_line(point=True).encode(
            x=alt.X("Date", scale=alt.Scale(domain=[
                    st.session_state.date_range[0], st.session_state.date_range[1]], clamp=True, nice=False)),
            y="Balance",
            color=alt.value("#a07400")
        )
        st.altair_chart(chart, use_container_width=True)
        # st.dataframe(self.data["balance_table"])


    # Function to lighten/darken hex colors
    def generate_shades(self, hex_color, n_shades):
        # Convert hex → RGB (0–1)
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

        # Convert RGB → HLS (hue, lightness, saturation)
        h, l, s = colorsys.rgb_to_hls(r, g, b)

        # Generate shades by adjusting lightness around l
        shades = []
        for i in np.linspace(0.3, 0.7, n_shades):  # lightness range
            r, g, b = colorsys.hls_to_rgb(h, i, s)
            shades.append('#{:02X}{:02X}{:02X}'.format(
                int(r*255), int(g*255), int(b*255)))
        return shades

    # need to fix pi chart not having anything to render
    def render_pie_chart(self):
        # Shared categories (excluding "Uncategorized") for consistent coloring
        categories = sorted(set(self.data["incomes"]["Category"]).union(
            set(self.data["expenses"]["Category"])))
        categories_no_uncat = [
            cat for cat in categories if cat != "Uncategorized"]

        # Generate dynamic shades for shared categories
        shades = self.generate_shades(
            "#a07400", n_shades=len(categories_no_uncat))

        # Append black for "Uncategorized" if it exists
        if "Uncategorized" in categories:
            shades.append("#221f20")
            categories_no_uncat.append("Uncategorized")

        # Build color scale
        color_scale = alt.Scale(domain=categories_no_uncat, range=shades)

        col1, col2 = st.columns(2)

        # Income chart
        chart1 = alt.Chart(self.data["incomes"]).mark_arc().encode(
            theta="Amount",
            color=alt.Color("Category:N", scale=color_scale),
            tooltip=["Category", "Amount"]
        )

        labels1 = (
            alt.Chart(self.data["incomes"])
            # adjust radius for placement
            .mark_text(radius=100, size=12, color="white")
            .encode(
                text="Labels",
                theta=alt.Theta("Amount", stack=True),
            )
        )

        chart1 = chart1 + labels1

        # Expense chart
        chart2 = alt.Chart(self.data["expenses"]).mark_arc().encode(
            theta="Amount",
            color=alt.Color("Category:N", scale=color_scale),
            tooltip=["Category", "Amount"]
        )

        labels2 = (
            alt.Chart(self.data["expenses"])
            .mark_text(radius=100, size=12, color="white")
            .encode(
                text="Labels",
                theta=alt.Theta("Amount", stack=True),
            )
        )

        chart2 = chart2 + labels2

        with col1:
            st.header("Receipts")
            st.altair_chart(chart1, use_container_width=True)
        with col2:
            st.header("Expenditures")
            st.altair_chart(chart2, use_container_width=True)

    def render_packed_bubble(self):
        n_cat = 10

        # Generate Old Gold shades
        hex_color = "#a07400"
        old_gold_shades = self.generate_shades(hex_color, n_cat)
        df = pd.DataFrame({'label': [f'Item {i}' for i in range(n_cat)], 'size': np.random.randint(
            2, 250, n_cat), "color": np.random.choice(old_gold_shades, n_cat)})
        fig = PlotlyBubbleChart.plot_bubble_chart_plotly(df, plot_diameter=500)
        st.plotly_chart(fig)

    def render_dues_plot(self):
        # Dropdown selector for term
        # terms = pd.read_sql(
        #     "SELECT DISTINCT PeriodStart FROM DuesTable ORDER BY PeriodStart DESC", 
        #     self.connection
        # )
        # self.term = st.selectbox("📅 Select Term", terms['PeriodStart'])
        # if self.term != st.session_state.term:
        #     st.session_state.term = self.term
        #     dues_data = self.data_manager.load_dues(self.term)

        dues_status = self.dues_data["dues_status"]
        expected_dues = self.dues_data["expected_dues"]
        total_paid = self.dues_data["total_paid"]
        missed_revenue = self.dues_data["missed_revenue"]
        status_counts = self.dues_data["status_counts"]

        # --- Streamlit metrics ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Expected Dues", f"${expected_dues:,.2f}")
        with col2:
            st.metric("Collected Dues", f"${total_paid:,.2f}")
        with col3:
            st.metric("Missed Revenue", f"${missed_revenue:,.2f}")

        # --- Pie chart ---
        color_mapping = {"Paid": "#228B22", "Partial": "#FFBF00", "Unpaid": "#D22B2B"}
        pie = alt.Chart(status_counts).mark_arc().encode(
            theta="Count",
            color=alt.Color("Status:N", scale=alt.Scale(
                domain=list(color_mapping.keys()),
                range=list(color_mapping.values())),
                title="Year"),
            tooltip=["Status", "Count"]
        )
        label = alt.Chart(status_counts).mark_text(radius=100, size=25, color="white").encode(
            text="Count",
            theta=alt.Theta("Count", stack=True),
        )
        st.altair_chart(pie + label, use_container_width=True)

        st.subheader("💳 Dues Status by Member")
    
        st.dataframe(self.dues_data["styled_df"], use_container_width=True, row_height=40, height=(40 * (len(dues_status) + 1)))


    # Transaction editor

    def render_transaction_editor(self):
        editor = st.data_editor(
            self.data["transaction_notes_table"],
            num_rows="fixed",
            column_order=('TransactionId', 'Date', 'Amount', 'Source',
                          'Description', 'Category', 'Notes'),
            disabled=['NoteId', 'Date', 'Amount', 'Source', 'Description'],
            use_container_width=True
        )
        if st.button("Save Changes"):
            # Only keep rows where Category or Notes are non-empty
            edits = editor[['TransactionId', 'Category', 'Notes']].copy()
            # drop rows where both are NaN
            edits = edits.dropna(how="all", subset=["Category", "Notes"])
            edits = edits[(edits["Category"].astype(str).str.strip() != "") |
                          # drop rows where both are empty strings
                          (edits["Notes"].astype(str).str.strip() != "")]

            if not edits.empty:
                with self.connection as conn:
                    edits.to_sql("Edits", conn, index=False,
                                 if_exists="replace")
                    edits.to_csv(
                        f"./data/Backups/edits_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", index=False)

                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        UPDATE NoteTable
                        SET Category = (SELECT Category FROM Edits WHERE Edits.TransactionId = NoteTable.NoteId),
                            Notes    = (SELECT Notes FROM Edits WHERE Edits.TransactionId = NoteTable.NoteId)
                        WHERE TransactionId IN (SELECT TransactionId FROM Edits)
                        '''
                    )
                    cursor.execute("DROP TABLE IF EXISTS Edits")
                    conn.commit()
                    st.success("Changes Saved Successfully ✅")
            else:
                st.info("No valid edits to save.")

    def render_data_buttons(self):
        # Column 2 → Load Data from CSV
        if st.button("Load Data from CSV", key="load_csv"):
            self.data_manager.read_data()
            st.success("Data Ingested Successfully")
            # st.rerun()

        # Column 3 → Reset Database with confirmation dialog
        if st.button("Reset Database", key="reset_db"):
            self.confirm_reset()

    def render_yoy_chart(self):
        df = self.data["transaction_notes_table"]

        # Ensure correct types
        df["Date"] = pd.to_datetime(df["Date"])
        df["Year"] = df["Date"].dt.year
        df["Month"] = df["Date"].dt.month
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        # Group by year + month
        monthly = (
            df.groupby(["Year", "Month"], as_index=False)["Amount"]
            .sum()
            .sort_values(["Year", "Month"])
        )

        # Get unique years, sorted
        years = sorted(monthly["Year"].unique())

        # Generate shades of gold, lightest = most recent year
        gold_shades = self.generate_shades("#a07400", len(years))
        color_mapping = {year: shade for year,
                         shade in zip(years[::-1], gold_shades)}
        # reverse so latest year gets lightest
        
        # Map colors to a new column
        monthly["Color"] = monthly["Year"].map(color_mapping)
        latest_year = max(years)

        # Build chart
        chart = (
            alt.Chart(monthly)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("Month:O", title="Month"),
                y=alt.Y("Amount:Q", title="Net Amount"),
                color=alt.Color("Year:N", scale=alt.Scale(domain=list(color_mapping.keys()),
                                                          range=list(color_mapping.values())),
                                title="Year"),
                tooltip=["Year", "Month", "Amount"]
            )
            .properties(
                title="Year-over-Year Monthly Comparison",
                width=700,
                height=400
            )
        )
        # Highlight the latest year with stronger opacity
        highlight = (
            alt.Chart(monthly[monthly["Year"] == latest_year])
            .mark_line(point=alt.MarkConfig(size=80), strokeWidth=4)
            .encode(
                x="Month:O",
                y="Amount:Q",
                color=alt.value(color_mapping[latest_year])
            )
        )

        st.altair_chart(chart + highlight, use_container_width=True)

    # Data & Reports buttons

    @st.dialog(title="Confirm Database Reset")
    def confirm_reset(self):
        st.error(
            "This will DROP all tables and recreate them! This action cannot be undone.",
            icon="🚨"
        )
        if st.button("Confirm Reset"):
            self.data_manager.create_database()
            st.rerun()
            st.success("Database Reset Successfully")
