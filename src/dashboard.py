import colorsys
import decimal
import datetime
import sqlite3

import pandas as pd
import streamlit as st
import altair as alt
import numpy as np


import ingest
import report_generator
import PlotlyBubbleChart
import os


class TreasuryDashboard:
    def __init__(self, db_path="database.db"):
        st.set_page_config(page_title="Treasury Dashboard", layout="wide",
                           initial_sidebar_state="collapsed", page_icon="./gblogo.png")

        self.data_manager = ingest.DataManager(db_path)

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

        if "month_index" not in st.session_state:
            st.session_state.month_index = 0  # 0 = most recent month

        if "report_generated" not in st.session_state:
            st.session_state.report_generated = False  # 0 = most recent month

        # Load initial data
        self.start_date, self.end_date = pd.to_datetime(
            self.date_range[0]), pd.to_datetime(self.date_range[1])
        self.data = self.data_manager.load_data(
            self.start_date, self.end_date, self.source)
        self.dues_data = self.data_manager.load_dues(
            self.start_date, self.end_date)

    # Render dashboard
    def render_dashboard(self):
        """ Renders the main dashboard with tabs and components. """

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

        # Tabs
        dashboard, budget, dues, yoy, editor = st.tabs(
            ["📈 Dashboard",  "📊 Budget",  "💵 Dues", "📆 YoY", "📝 Edit Transactions"])
        with editor:
            self.render_transaction_editor()
            self.render_transaction_note_editor()
            self.render_data_buttons()
        with yoy:
            self.render_yoy_chart()
        with budget:
            self.budget()
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
        """ Renders the header with logo and title. """
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

        month_range = pd.date_range(
            start="2019-06-01", end=self.today, freq="MS")[::-1]
        month_options = ["Custom"] + [d.strftime("%B %Y") for d in month_range]
        total_months = len(month_options) - 1
        col1, col2, col3, = st.columns([3, 1.5, 3])
        with col1:
            # --- Layout with dropdown + two small buttons ---
            if not st.session_state.use_custom:
                self.date_range = self._date_interval_selector(
                    interval="month", label="Date Range:")
                # cola, colb, colc = st.columns([1, 1, 11])
                # with cola:
                #     if st.button("←", help="Previous month"):
                #         st.session_state.month_index = (
                #             st.session_state.month_index + 1) % total_months
                # with colb:
                #     if st.button("→", help="Next month"):
                #         st.session_state.month_index = (
                #             st.session_state.month_index - 1) % total_months
                #         st.rerun()
                # with colc:
                #     selected_option = st.selectbox(
                #         "Date Range:",
                #         label_visibility="collapsed",
                #         options=month_options,
                #         index=st.session_state.month_index + 1,
                #         key="month_selector"
                #     )
                #     if selected_option == "Custom":
                #         st.session_state.use_custom = True
                #         st.rerun()
                #     else:
                #         # Parse selected month into start/end date
                #         selected_date = datetime.datetime.strptime(
                #             selected_option, "%B %Y")
                #         start_date = selected_date.replace(day=1).date()
                #         next_month = (selected_date.replace(
                #             day=28) + datetime.timedelta(days=4)).replace(day=1)
                #         end_date = (
                #             next_month - datetime.timedelta(days=1)).date()
                #         self.date_range = (start_date, end_date)
            else:
                self.date_range = st.date_input(
                    label="Date Range:",
                    label_visibility="collapsed",
                    key="custom_date_range",
                    format="MM.DD.YYYY",
                    value=self.date_range
                )
                cola, colb = st.columns([2.5, 1])
                with cola:
                    date_options = ["Custom", "Past Month",
                                    "Past Year", "All Time"]
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
                        self.date_range = (
                            self.today - datetime.timedelta(days=30), self.today)
                    elif date_selector == "Past Year":
                        self.date_range = (
                            self.today - datetime.timedelta(days=365), self.today)
                    elif date_selector == "All Time":
                        self.date_range = (
                            datetime.date(2019, 6, 14), self.today)
                    elif date_selector == "Back":
                        st.session_state.use_custom = False
                        st.rerun()
                with colb:
                    if st.button("↩ Month Selector"):
                        st.session_state.use_custom = False
                        st.rerun()
        with col2:
            source_options = ["All", "Checking", "Cashapp"]
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
            self.start_date, self.end_date = pd.Timestamp(
                self.date_range[0]), pd.Timestamp(self.date_range[1])
            report = report_generator.TreasurerReport(
                self.start_date, self.end_date, self.data_manager)
            if st.session_state.report_generated is False:
                if st.button("Generate Report"):
                    report.build()
                    st.session_state.report_generated = True
            else:
                filename, buffer = report.save()
                st.download_button(
                    label="⬇ Download Report",
                    data=buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                st.session_state.report_generated = True

        # Update session state and reload data if changed
        if self.date_range != st.session_state.date_range:
            st.session_state.date_range = self.date_range
            self.start_date, self.end_date = pd.Timestamp(
                self.date_range[0]), pd.Timestamp(self.date_range[1])
            self.data = self.data_manager.load_data(
                self.start_date, self.end_date, self.source)
            self.dues_data = self.data_manager.load_dues(
                self.start_date, self.end_date)
            st.rerun()

        # Update session state and reload data if changed
        if self.source != st.session_state.source:
            st.session_state.source = self.source
            self.data = self.data_manager.load_data(
                self.start_date, self.end_date, self.source)
            self.dues_data = self.data_manager.load_dues(
                self.start_date, self.end_date)
            st.rerun()

    # Render balances
    def render_balances(self):
        st.subheader("Account Balances")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            delta = self.data["current_balance"] - self.data["initial_balance"]
            sign = '-' if delta < 0 else ''
            st.metric(
                label="Current Balance",
                value=f"${self.data['current_balance']:,.2f}",
                delta=f"{sign}${abs(delta):,.2f}"
            )
        with col2:
            st.metric("Initial Balance",
                      f"${self.data['initial_balance']:,.2f}")
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

    def render_dues_plot(self):
        st.subheader("Dues Overview")
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
        color_mapping = {"Paid": "#228B22",
                         "Partial": "#FFBF00", "Unpaid": "#D22B2B"}
        pie = alt.Chart(status_counts).mark_arc().encode(
            order=alt.Order("Status", sort="ascending"),
            theta="Count",
            color=alt.Color("Status:N", scale=alt.Scale(
                domain=list(color_mapping.keys()),
                range=list(color_mapping.values())),
                title="Year"),
            tooltip=["Status", "Count"]
        )
        label = alt.Chart(status_counts).mark_text(radius=100, size=25, color="white").encode(
            text="Count",
            order=alt.Order("Status", sort="ascending"),
            theta=alt.Theta("Count:Q", stack=True),

        )
        st.altair_chart(pie + label, use_container_width=True)

        st.subheader("💳 Dues Status by Member")

        st.dataframe(self.dues_data["styled_df"], width='stretch',
                     row_height=40, height=(40 * (len(dues_status) + 1)))

    def budget(self):
        # ---------- LOAD & DISPLAY DATA ----------
        df = self.data_manager.load_budget_data()

        st.subheader("Budget Overview")

        start_date, end_date = self.date_range

        # Get the first and last years from the selected range
        start_year = start_date.year if start_date.month >= 8 else start_date.year - 1
        end_year = end_date.year if end_date.month >= 8 else end_date.year - 1

        # Define the new August-to-August range
        august_start = pd.Timestamp(f"{start_year}-08-01")
        # ends just before next August
        august_end = pd.Timestamp(f"{end_year + 1}-07-31")

        # ---------- FILTER & PROCESS DATA ----------
        df_filtered = df[df["Date"].between(august_start, august_end)]
        df_filtered["Amount"] = pd.to_numeric(
            df_filtered["Amount"], errors="coerce").round(2)

        # Create all months in selected year range
        all_months = pd.date_range(
            start=august_start, end=august_end, freq="MS"
        ).to_period("M").astype(str)

        # Summarize expenses by month/category
        df_filtered["Month"] = df_filtered["Date"].dt.to_period(
            "M").astype(str)
        monthly_expenses = (
            df_filtered.groupby(["Month", "Category"], as_index=False)[
                "Amount"].sum()
        )

        # Merge with all_months to fill gaps
        all_months_df = pd.DataFrame({"Month": all_months})
        monthly_expenses = (
            all_months_df.merge(monthly_expenses, on="Month", how="left")
            .fillna({"Amount": 0, "Category": "No Data"})
        )

        # Create a new column for positive/negative amounts
        monthly_expenses["Color"] = monthly_expenses["Amount"].apply(lambda x: "#228B22" if x >= 0 else "#D22B2B")
        chart = (
            alt.Chart(monthly_expenses)
            .mark_bar()
            .encode(
                x=alt.X("Month:N", title="Month", sort=all_months,
                        axis=alt.Axis(labelAngle=-40)),
                y=alt.Y("sum(Amount):Q", title="Total Amount ($)"),
                color=alt.Color("Color:N", legend=None, scale=None),  # disable Altair’s auto-scaling
                tooltip=[
                    alt.Tooltip("Month:N", title="Month"),
                    alt.Tooltip("Category:N", title="Category"),
                    alt.Tooltip("sum(Amount):Q",
                                title="Amount ($)", format=",.2f")
                ]
            )
            .properties(
                width=700,
                height=400,
                title=f"Budget Overview ({august_start.strftime('%b %Y')} – {august_end.strftime('%b %Y')})"
            )
        )
        st.altair_chart(chart, use_container_width=True)

        # ---------- ADD NEW ENTRY FORM ----------
        with st.expander("➕ Add New Budget Entry", expanded=True):
            with st.form("add_budget_form"):
                col1, col2 = st.columns(2)
                date_val = col1.date_input("Date", self.today)
                amount = col2.number_input("Amount ($)", step=0.01)

                category = st.text_input(
                    "Category", placeholder="Regional Convention, Dues, etc.")
                description = st.text_input(
                    "Description", placeholder="e.g., Grocery shopping, gas, etc.")
                transaction_id = st.text_input("Transaction ID (optional)")

                submitted = st.form_submit_button("💾 Save Entry")
                if submitted:
                    self.data_manager.insert_budget(
                        date_val, amount, category, description, transaction_id or None
                    )
                    st.success("✅ Budget entry added successfully!")
                    st.rerun()

    def _date_interval_selector(self, interval="year", start_year=2019, label="Date Range:"):
        """
        Universal helper to select a date range by month, year, or day.

        Parameters
        ----------
        interval : str
            One of {"year", "month", "day"} to define selection granularity.
        start_year : int
            Earliest selectable year in dropdown.
        label : str
            Label shown above the selector.

        Returns
        -------
        (start_date, end_date) : tuple of pd.Timestamp
            Start and end dates for the selected interval.
        """
        today = pd.Timestamp(self.today)
        current_year = today.year

        # --- Build selectable options ---
        if interval == "year":
            options = [str(y) for y in range(current_year, start_year - 1, -1)]
        elif interval == "month":
            months = pd.date_range(
                start=f"{start_year}-01-01", end=today, freq="MS")[::-1]
            options = [d.strftime("%B %Y") for d in months]
        elif interval == "day":
            days = pd.date_range(
                start=f"{start_year}-01-01", end=today, freq="D")[::-1]
            options = [d.strftime("%b %d, %Y") for d in days]
        else:
            raise ValueError(
                "interval must be one of {'year', 'month', 'day'}")

        options = ["Custom"] + options
        total_options = len(options) - 1

        # --- Init session state ---
        key_prefix = f"{interval}_selector"
        index_key = f"{key_prefix}_index"
        custom_key = "use_custom"  # f"use_custom_{interval}"

        if index_key not in st.session_state:
            st.session_state[index_key] = 0
        if custom_key not in st.session_state:
            st.session_state[custom_key] = False

        cola, colb, colc = st.columns([1, 1, 11])
        with cola:
            if st.button("←", key=f"prev_{interval}", help=f"Previous {interval}"):
                st.session_state[index_key] = (
                    st.session_state[index_key] + 1) % total_options
                st.rerun()
        with colb:
            if st.button("→", key=f"next_{interval}", help=f"Next {interval}"):
                st.session_state[index_key] = (
                    st.session_state[index_key] - 1) % total_options
                st.rerun()
        with colc:
            selected_option = st.selectbox(
                label,
                label_visibility="collapsed",
                options=options,
                index=st.session_state[index_key] + 1,
                key=f"{key_prefix}_dropdown",
            )

            if selected_option == "Custom":
                st.session_state[custom_key] = True
                st.rerun()
            else:
                # --- Compute start & end based on interval ---
                if interval == "year":
                    selected_year = int(selected_option)
                    start_date = pd.Timestamp(f"{selected_year}-01-01")
                    end_date = pd.Timestamp(f"{selected_year}-12-31")
                elif interval == "month":
                    selected_date = pd.to_datetime(selected_option)
                    start_date = selected_date.replace(day=1)
                    next_month = (selected_date + pd.offsets.MonthEnd(1))
                    end_date = next_month
                elif interval == "day":
                    selected_date = pd.to_datetime(selected_option)
                    start_date = selected_date
                    end_date = selected_date
                return (start_date, end_date)

    # Transaction editor

    def render_transaction_editor(self):
        editor = st.dataframe(
            self.data["transaction_notes_table"],
            # num_rows="fixed",
            column_order=('TransactionId', 'Category', 'Notes', 'Date', 'Amount', 'Source',
                          'Description', 'Attachments'),
            # disabled=['NoteId', 'Date', 'Amount', 'Source', 'Description'],
            width='stretch'
        )

    def render_transaction_note_editor(self):
        df = self.data["transaction_notes_table"].copy()

        with st.expander("📝 Edit Transaction Note", expanded=True):
            with st.form("edit_transaction_note_form"):
                # --- Row 1: Transaction Selection ---
                transaction_id = st.selectbox(
                    "Select Transaction",
                    df["TransactionId"].tolist(),
                    format_func=lambda tid: f"{tid} — {df.loc[df['TransactionId'] == tid, 'Description'].values[0]}"
                )

                if transaction_id:
                    # Get selected transaction row
                    row = df[df["TransactionId"] == transaction_id].iloc[0]
                    current_attachment = row.get("AttachmentPath", None)
                    # --- Row 2: Display basic info ---
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_input("Date", value=str(
                            row["Date"]), disabled=True)
                        st.text_input(
                            "Amount", value=f"${row['Amount']:.2f}", disabled=True)
                    with col2:
                        st.text_input("Source", value=row.get(
                            "Source", ""), disabled=True)
                        st.text_input("Description", value=row.get(
                            "Description", ""), disabled=True)

                    st.divider()

                    # --- Row 3: Editable fields ---
                    col3, col4 = st.columns(2)
                    category = col3.text_input(
                        "Category", value=row.get("Category", ""))
                    notes = col4.text_area(
                        "Notes", value=row.get("Notes", ""), height=120)

                    st.divider()
                    uploaded_file = st.file_uploader(
                        "Attach New Document (optional)",
                        type=["pdf", "jpg", "png", "jpeg", "docx"]
                    )

                    # --- Row 4: Attachment section ---
                    if current_attachment and os.path.exists(current_attachment):
                        st.markdown("#### 📎 Current Attachment")
                        ext = os.path.splitext(current_attachment)[1].lower()

                        if ext in [".jpg", ".jpeg", ".png"]:
                            st.image(current_attachment,
                                     use_container_width=True)
                        elif ext == ".pdf":
                            with open(current_attachment, "rb") as f:
                                st.download_button(
                                    label="Download Current PDF",
                                    data=f,
                                    file_name=os.path.basename(
                                        current_attachment),
                                    mime="application/pdf"
                                )
                        else:
                            st.download_button(
                                label=f"Download {os.path.basename(current_attachment)}",
                                data=open(current_attachment, "rb"),
                                file_name=os.path.basename(current_attachment)
                            )

                        remove_attachment = st.checkbox(
                            "🗑️ Remove Attachment", value=False)
                    else:
                        st.info(
                            "No attachment currently linked to this transaction.")
                        remove_attachment = False

                    # --- Submit Button ---
                    submitted = st.form_submit_button("💾 Save Changes")

                    if submitted:
                        # Handle attachment logic
                        attachment_path = current_attachment
                        if remove_attachment:
                            attachment_path = None
                            if current_attachment and os.path.exists(current_attachment):
                                os.remove(current_attachment)
                                st.info("Attachment removed.")

                        elif uploaded_file is not None:
                            os.makedirs("./data/Attachments", exist_ok=True)
                            safe_name = f"{transaction_id}_{uploaded_file.name}".replace(
                                " ", "_")
                            attachment_path = f"./data/Attachments/{safe_name}"
                            with open(attachment_path, "wb") as f:
                                f.write(uploaded_file.read())
                            st.success(f"📎 Attached new file: {safe_name}")

                        # --- Save Changes to Database ---
                        self.data_manager.save_transaction_edits(
                            transaction_id, category, notes, attachment_path)

                        st.success("✅ Transaction note updated successfully!")
                        st.rerun()

    def render_data_buttons(self):
        # Column 2 → Load Data from CSV
        if st.button("Load Data from CSV", key="load_csv"):
            self.data_manager.read_data()
            # st.success("Data Ingested Successfully")
            # st.rerun()

        # Column 3 → Reset Database with confirmation dialog
        if st.button("Reset Database", key="reset_db"):
            self.confirm_reset()

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
        # latest_year = max(years)

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
        # highlight = (
        #     alt.Chart(monthly[monthly["Year"] == latest_year])
        #     .mark_line(point=alt.MarkConfig(size=80), strokeWidth=4)
        #     .encode(
        #         x="Month:O",
        #         y="Amount:Q",
        #         color=alt.value(color_mapping[latest_year])
        #     )
        # )

        st.altair_chart(chart, use_container_width=True)
