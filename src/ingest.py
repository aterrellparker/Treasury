import glob
import sqlite3
import os
import hashlib
import base64
import datetime

import pandas as pd

from sql_queries import *


class DataManager:
    def __init__(self, db_path="database.db"):
        self.db_path = db_path
        os.remove(self.db_path) if os.path.exists(self.db_path) else None
        # self.fix_hash()
        if os.path.exists(self.db_path):
            self.connection = sqlite3.connect(
                self.db_path, check_same_thread=False)
        else:
            print("Creating new database...")
            self.connection = sqlite3.connect(
                self.db_path, check_same_thread=False)
            self.create_database()
            self.read_data()

    @staticmethod
    def generate_id(data: str) -> str:
        """Generate a unique hash-based ID from input string."""
        return base64.urlsafe_b64encode(
            hashlib.md5(data.encode()).digest()
        ).decode()

    def create_database(self):
        """Create a new database with base schema and initial balance."""
        # if os.path.exists(self.db_path):
        #     os.remove(self.db_path)

        cursor = self.connection.cursor()
        self.connection.execute("PRAGMA foreign_keys = ON")

        # Register hash function
        self.connection.create_function("generate_id", 1, self.generate_id)

        # Create tables
        cursor.execute(CREATE_TRANSACTION_TABLE)
        cursor.execute(INSERT_INITIAL_BALANCE)
        cursor.execute(CREATE_NOTE_TABLE)
        cursor.execute(CREATE_MEMBER_TABLE)
        cursor.execute(CREATE_DUES_TABLE)
        cursor.execute(CREATE_DUES_PAYMENTS_TABLE)
        cursor.execute(CREATE_BUDGET_TABLE)

        self.connection.commit()
      # === Cash App ===

    def read_data(self):
        """Load all CSV sources into database."""
        cursor = self.connection.cursor()

        # === Placeholder transaction ===
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        today_str = now_utc.isoformat(sep=' ', timespec='seconds')

        cursor.execute(f"""
            INSERT INTO TransactionTable (TransactionId, Date, Amount, Source, Description)
            VALUES (
                generate_id('{today_str}||0||Placeholder'),
                '{today_str}',
                0,
                'Placeholder',
                'End-of-range placeholder'
            )
        """)
            
        #=== Checking 1 ===
        self._insert_csv_data(
            "./Data/raw/Checking1/*.csv",
            "Checking",
            columns=["Date", "Amount", "n/a", "Check Number", "Description"],
            drop=["n/a", "Check Number"],
            date_format="%m/%d/%y",
        )

        # === Checking 2 ===
        self._insert_csv_data(
            "./Data/raw/Checking2/*.csv",
            "Checking",
            columns=["Date", "Amount", "n/a", "Check Number", "Description"],
            drop=["n/a", "Check Number"],
            date_format="%m/%d/%Y",
        )

        # === Statements ===
        self._insert_csv_data(
            "./Data/raw/Statements/*.csv",
            "Checking",
            columns=["Date", "Description", "Amount"],
            date_format="%Y-%m-%d",
        )

        self._insert_csv_data("./Data/raw/Cashapp/*.csv", "Cashapp", columns=None, drop=["Transaction ID",
                              "Transaction Type", "Currency", "Fee", "Amount",
                              "Asset Type", "Asset Price", "Asset Amount"], preprocess=self._preprocess_cashapp)
        
        cursor.execute(RECONCILE_CASHAPP_MARCH)
        cursor.execute(RECONCILE_CASHAPP_APRIL)

        # === Merge ===
        cursor.execute(INSERT_TRANSACTIONS)
        cursor.execute(DROP_TMP)


        # === Notes Table ===f
        notes_files = glob.glob("./Data/Backups/edits_*.csv")
        if notes_files:
            latest_file = max(notes_files, key=os.path.getctime)
            pd.read_csv(latest_file).to_sql(
                "NoteTable", self.connection, if_exists="replace", index=False)

        # === Load members ===
        for file in glob.glob("./Data/Raw/Members/*.csv"):
            df = pd.read_csv(file)
            df.to_sql("tmp", self.connection, if_exists="append", index=False)
        cursor.execute(INSERT_MEMBERS)
        cursor.execute(DROP_TMP)

        # === Payments ===
        payments = pd.read_csv("./data/raw/DuePayments.csv")
        payments.to_sql("PaymentsTable", self.connection,
                        if_exists="replace",  index=False)
           
        # === Due Dates & Dues ===
        self._create_due_dates()
        budget = pd.read_csv("./data/raw/budget.csv")
        budget.to_sql("tmp", self.connection, if_exists="append", index=False)

        cursor.execute(INSERT_BUDGET)
        cursor.execute(DROP_TMP)
        cursor.execute(DUES_TO_BUDGET)
   
        self.connection.commit()
    
    def _insert_csv_data(self, path, source, columns, drop=None, date_format=None, preprocess=None):
            for file in glob.glob(path):
                df = pd.read_csv(file, header= None if columns else 0)            
                if columns:
                    df.columns = columns
                if drop:
                    df = df.drop(columns=drop, errors="ignore")
                
                # Optional custom preprocessing for special cases
                if preprocess:
                    df = preprocess(df)

                # Date parsing
                if date_format:
                    df["Date"] = (
                        pd.to_datetime(df["Date"].astype(
                            str).str.strip(), format=date_format, errors="coerce")
                        .dt.tz_localize("America/New_York")
                        .dt.tz_convert("UTC")
                    )
                # Generate TransactionId
                df["Source"] = source
                df["TransactionId"] = (
                    df[["Date", "Amount", "Description"]]
                    .astype(str)
                    .sum(axis=1)
                    .map(self.generate_id)
                )

                # Final clean-up and insert
                df = df[["TransactionId", "Date",
                        "Amount", "Source", "Description"]]
                df.to_sql("tmp", self.connection,
                        if_exists="append", index=False)

    def _preprocess_cashapp(self, df):
        df = df[df["Status"] == "COMPLETE"]

        df["Date"] = (
            pd.to_datetime(df["Date"].replace({"EDT": "", "EST": ""}, regex=True).str.strip(),
                        format="%Y-%m-%d %H:%M:%S", errors="coerce")
            .dt.tz_localize("America/New_York")
            .dt.tz_convert("UTC")
        )
        df["Net Amount"] = (
            df["Net Amount"]
            .str.replace(r"[\$,)]", "", regex=True)
            .str.replace(r"\(", "-", regex=True)
        )

        df["Notes"] = df[
            ["Notes", "Name of sender/receiver", "Account"]
        ].astype(str).agg(" - ".join, axis=1)
        df = df.rename(columns={"Net Amount": "Amount", "Notes": "Description"})
        return df
    
    def load_data(self, start_date, end_date, source):
        if source:
            BASE_QUERY = TRANSACTION_NOTES_QUERY + " WHERE t.Source = ?"
        else:
            BASE_QUERY = TRANSACTION_NOTES_QUERY
        transaction_notes_table, deposits, withdrawals = self._preprocess_transactions(
            pd.read_sql(BASE_QUERY, self.connection, parse_dates={"Date": "%Y-%m-%d %H:%M:%S%z"}, params=(source,) if source else None))
        balance_table, initial_balance, current_balance = self._compute_balances(
            transaction_notes_table, start_date, end_date)

        filtered = self._apply_filters(
            transaction_notes_table, start_date, end_date)
        transaction_notes_table = filtered
        deposits, withdrawals = self._split_transactions(filtered)
        deposits_total = deposits['Amount'].sum()
        withdrawals_total = withdrawals['Amount'].sum()

        incomes = deposits.groupby(
            "Category", as_index=False)["Amount"].sum()
        incomes["Labels"] = incomes["Category"] + " – " + \
            (incomes["Amount"] / incomes["Amount"].sum()
             * 100).round(1).astype(str) + "%"
        expenses = withdrawals.groupby(
            "Category", as_index=False)["Amount"].sum()
        expenses["Labels"] = expenses["Category"] + " - " + (expenses["Amount"].abs(
        ) / expenses["Amount"].abs().sum() * 100).round(1).astype(str) + "%"
        # Set options to display all rows and columns
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)

        return {
            "transaction_notes_table": transaction_notes_table,
            "deposits": deposits,
            "deposits_total": deposits_total,
            "incomes": incomes,
            "withdrawals": withdrawals,
            "withdrawals_total": withdrawals_total,
            "expenses": expenses,
            "balance_table": balance_table,
            "initial_balance": initial_balance,
            "current_balance": current_balance,
            # "dues": dues,
        }
    
    def _preprocess_transactions(self, df):
        df = df.copy()
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").round(2)
        df["Category"] = df["Category"].fillna("Uncategorized")
        df.loc[df["Category"].str.strip() == "", "Category"] = "Uncategorized"
        deposits = df[df["Amount"] > 0]
        withdrawals = df[df["Amount"] < 0]
        return df, deposits, withdrawals

    def _compute_balances(self, df, start_date, end_date):
        start_date = pd.to_datetime(start_date).tz_localize("UTC")
        end_date = pd.to_datetime(end_date).tz_localize("UTC")
        balance_df = df.sort_values("Date").assign(
            Balance=lambda x: x["Amount"].cumsum()
        )
        balanceTable = balance_df[["Date", "Balance"]]

        initial = df.loc[df["Date"] < start_date, "Amount"].sum()
        current = df.loc[df["Date"] <= end_date, "Amount"].sum()
        return balanceTable, initial, current

    def _apply_filters(self, df, start_date, end_date):
        start_date = pd.to_datetime(start_date).tz_localize("UTC")
        end_date = pd.to_datetime(end_date).tz_localize("UTC")
        mask = df["Date"].between(start_date, end_date)
        return df.loc[mask]

    def _split_transactions(self, df):
        deposits = df[df["Amount"] > 0]
        withdrawals = df[df["Amount"] < 0]
        return deposits, withdrawals
    
    def save_transaction_edits(self, transaction_id, category, notes, attachment_path, ):
       with self.connection as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE NoteTable
                SET Category = ?, Notes = ?, AttachmentPath = ?
                WHERE TransactionId = ?
                """,
                (category, notes, attachment_path, transaction_id)
            )
            conn.commit()
            
    # def save_transaction_edits(self, editor_df: pd.DataFrame):
    #     """
    #     Handles cleaning, validation, SQL update, and CSV backup
    #     for transaction edits submitted from the Streamlit editor.
    #     """

    #     # Keep only relevant columns
    #     edits = editor_df[['TransactionId', 'Category', 'Notes']].copy()
    #     print(edits)
    #     # Drop rows with no Category or Notes (NaN or empty)
    #     edits = edits.dropna(how="all", subset=["Category", "Notes"])
    #     edits = edits[
    #         (edits["Category"].astype(str).str.strip() != "") |
    #         (edits["Notes"].astype(str).str.strip() != "")
    #     ]

    #     # --- Save Edits Temporarily ---
    #     timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    #     backup_path = f"./data/Backups/edits_{timestamp}.csv"

    #     with self.connection as conn:
    #         edits.to_sql("Edits", conn, index=False, if_exists="replace")
    #         # edits.to_csv(backup_path, index=False)

    #         # --- Apply Updates to NoteTable ---
    #         cursor = conn.cursor()
    #         cursor.execute("""
    #             UPDATE NoteTable
    #             SET 
    #                 Category = (
    #                     SELECT Category FROM Edits WHERE Edits.TransactionId = NoteTable.TransactionId
    #                 ),
    #                 Notes = (
    #                     SELECT Notes FROM Edits WHERE Edits.TransactionId = NoteTable.TransactionId
    #                 )
    #             WHERE TransactionId IN (SELECT TransactionId FROM Edits)
    #         """)

    #         cursor.execute("DROP TABLE IF EXISTS Edits")
    #         conn.commit()

    def load_dues(self, start_date, end_date):
        start_str = pd.to_datetime(start_date).strftime('%Y-%m-%d')
        end_str = pd.to_datetime(end_date).strftime('%Y-%m-%d')

        dues = pd.read_sql(DUES_QUERY, self.connection,
                           params=(end_str, start_str, end_str,))
        
        dues_status = ( 
            dues
            .groupby(["DueId", "MemberName", "PeriodStart", "PeriodEnd", "Amount", "Waived"], as_index=False)
            .agg({
                "AmountPaid": "sum",
                "Date": "max"
            })
        )
        dues_status["LateFee"] = dues_status.apply(
            lambda row: 10 if row["AmountPaid"] != row["Amount"] and pd.to_datetime(row["PeriodEnd"]) < pd.to_datetime(end_str) and row["Waived"] == 0 else 0,
            axis=1
        )
        
        # --- Compute summary values ---
        dues_status["Amount"] = pd.to_numeric(dues_status["Amount"], errors="coerce").round(2)
        expected_dues = dues_status["Amount"].sum()

        # Total actually paid (sum of PaymentAmount where not null)
        dues_status["AmountPaid"] = pd.to_numeric(dues_status["AmountPaid"], errors="coerce").round(2)  
        total_paid = dues_status["AmountPaid"].fillna(0).sum()

        # Missed revenue = what was expected but not collected
        missed_revenue = expected_dues - total_paid

        dues_status["Remaining"] = dues_status["Amount"] - \
            dues_status["AmountPaid"].fillna(0)

        # Determine status based on payments vs due amount
        dues_status["Status"] = dues_status.apply(
            lambda row: "Paid" if row["Remaining"] <= 0 or row["Waived"] == 1
                        else "Partial" if row["AmountPaid"] > 0
                        else "Unpaid",
            axis=1
        )

        status_counts = dues_status.groupby(
            "Status").size().reset_index(name="Count")

        # --- Styled DataFrame ---
        def highlight_status(row):
            if row["Status"] == "Paid":
                return ["color: white; background-color: #228B22"] * len(row)
            elif row["Status"] == "Partial":
                return ["color: white; background-color: #FFBF00"] * len(row)
            else:
                return ["color: white; background-color: #D22B2B"] * len(row)
        dues_status = dues_status.sort_values(
            by=["PeriodStart", "Status", "DueId",], ascending=[False, True, True])
        styled_df = dues_status[["MemberName", "Status", "PeriodStart", "PeriodEnd", "Amount", "AmountPaid", "LateFee"]] \
            .style.apply(highlight_status, axis=1)
        # Return everything as a dictionary
        return {
            "dues": dues,                    # raw dues
            "dues_status": dues_status,      # per-member status
            "expected_dues": expected_dues,  # total expected
            "total_paid": total_paid,        # total collected
            "missed_revenue": missed_revenue,  # total missed
            "status_counts": status_counts,   # grouped counts
            "styled_df": styled_df
        }
    
    def _create_due_dates(self):
        cursor = self.connection.cursor()

        # start_year = members['InitiationDate'].min().date()
        end_year = datetime.datetime.today().year

        # Create list of period ranges for each year
        periods = []
        for year in range(2019, end_year + 1):
            # Spring Term: Jan 1 – Jul 30
            periods.append({
                "PeriodStart": f"{year}-01-01",
                "PeriodEnd": f"{year}-07-30",
                "Amount": 100
            })
            # Fall Term: Aug 1 – Dec 31
            periods.append({
                "PeriodStart": f"{year}-08-01",
                "PeriodEnd": f"{year}-12-31",
                "Amount": 100
            })

        # Convert to DataFrame
        due_dates = pd.DataFrame(periods)
        due_dates["PeriodStart"] = pd.to_datetime(
            due_dates["PeriodStart"]).dt.strftime('%Y-%m-%d')
        due_dates["PeriodEnd"] = pd.to_datetime(
            due_dates["PeriodEnd"]).dt.strftime('%Y-%m-%d')

        due_dates.to_sql("DueDatesTable", self.connection,
                         if_exists="replace", index=False)

        # Insert dues using SQL join
        cursor.execute("""
        INSERT OR IGNORE INTO DuesTable (DueId, GBId, PeriodStart, PeriodEnd, Amount)
        SELECT 
            CAST(STRFTIME('%Y%m', d.PeriodStart) || m.GBId AS TEXT) AS DueId,
            m.GBId,
            d.PeriodStart,
            d.PeriodEnd,
            d.Amount
        FROM MemberTable m
        JOIN DueDatesTable d
            ON d.PeriodStart >= m.InitiationDate
            AND (m.GraduationDate IS NULL OR d.PeriodStart <= m.GraduationDate)
        """)
        self.connection.commit()

    def load_budget_data(self):
    
        df = pd.read_sql_query(
            "SELECT * FROM BudgetTable", self.connection, parse_dates=["Date"])

        return df
 

    def fix_hash(self):
        print("Fixing hashes...")
        hashmap = dict()
        for file in glob.glob("./Data/raw/Checking1/*.csv"):
            print(f"Processing {file}...")
            df = pd.read_csv(file, header=None)
            df.columns = ["Date", "Amount", "n/a",
                          "Check Number", "Description"]
            df["Date"] = pd.to_datetime(
                df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
            df["TransactionId"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df["NewDate"] = (
                pd.to_datetime(df["Date"].astype(
                    str).str.strip(), format="%Y-%m-%d", errors="coerce")
                .dt.tz_localize("America/New_York")
                .dt.tz_convert("UTC")
            )
            for m in self.map_old_to_new_hash(
                df["Date"], df["Amount"], df["Description"],
                df["NewDate"], df["Amount"], df["Description"]
            ):
                hashmap.update(m)

        for file in glob.glob("./Data/raw/Checking2/*.csv"):
            print(f"Processing {file}...")
            df = pd.read_csv(file, header=None)
            df.columns = ["Date", "Amount", "n/a",
                          "Check Number", "Description"]
            df["Date"] = pd.to_datetime(
                df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
            df["TransactionId"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df["NewDate"] = (
                pd.to_datetime(df["Date"].astype(
                    str).str.strip(), format="%Y-%m-%d", errors="coerce")
                .dt.tz_localize("America/New_York")
                .dt.tz_convert("UTC")
            )
            for m in self.map_old_to_new_hash(
                df["Date"], df["Amount"], df["Description"],
                df["NewDate"], df["Amount"], df["Description"]
            ):
                hashmap.update(m)

        for file in glob.glob("./Data/raw/Statements/*.csv"):
            print(f"Processing {file}...")
            df = pd.read_csv(file, header=None)
            df.columns = ["Date", "Amount", "Description",]
            df["Date"] = pd.to_datetime(
                df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
            df["TransactionId"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df["NewDate"] = (
                pd.to_datetime(df["Date"].astype(
                    str).str.strip(), format="%Y-%m-%d", errors="coerce")
                .dt.tz_localize("America/New_York")
                .dt.tz_convert("UTC")
            )
            for m in self.map_old_to_new_hash(
                df["Date"], df["Amount"], df["Description"],
                df["NewDate"], df["Amount"], df["Description"]
            ):
                hashmap.update(m)

        for file in glob.glob("./Data/raw/Cashapp/*.csv"):
            print(f"Processing {file}...")

            df = pd.read_csv(file)

            df = df[df["Status"] == "COMPLETE"]
            df = df.drop(columns=["Status", "Transaction ID",
                                    "Transaction Type", "Currency", "Fee", "Amount",
                                    "Asset Type", "Asset Price", "Asset Amount"], errors="ignore")
            df = df.rename(
                columns={"Net Amount": "Amount", "Notes": "Description"})
            
            df["OldDate"] = pd.to_datetime(df["Date"].str.split(" ").str[0]).dt.strftime("%Y-%m-%d")
            
            df["NewDate"] = (
                    pd.to_datetime(df["Date"].replace({"EDT": "", "EST": ""}, regex=True).str.strip(),
                                format="%Y-%m-%d %H:%M:%S", errors="coerce")
                    .dt.tz_localize("America/New_York")
                    .dt.tz_convert("UTC")
                )

            df["Amount"] = (
                df["Amount"]
                .str.replace(r"[\$,)]", "", regex=True)
                .str.replace(r"\(", "-", regex=True)
            )

            df["NewDescription"] = df[
                ["Description", "Name of sender/receiver", "Account"]
            ].astype(str).agg(" - ".join, axis=1)
            df = df.drop(columns=["Name of sender/receiver", "Account"])
            for m in self.map_old_to_new_hash(
                df["OldDate"], df["Amount"], df["Description"],
                df["NewDate"], df["Amount"], df["NewDescription"]
            ):
                hashmap.update(m)

        
        # df = pd.read_csv("./Data/Backups/edits_20250925_230954.csv")
        # df["TransactionId"] = df["TransactionId"].replace(hashmap)
        # df.to_csv(
        #     f"./data/Backups/edits_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", index=False)
        df = pd.read_csv("./data/raw/DuePayments1.csv")
        df["TransactionId"] = df["TransactionId"].replace(hashmap)
        df.to_csv(
            f"./data/raw/DuePayments.csv", index=False)

    def map_old_to_new_hash(self, old_date, old_amount, old_description,
                            new_date, new_amount, new_description):
        """
        Generate mapping(s) between old and new transaction hashes.

        Compatible with both single values and pandas Series/DataFrames.
        """

        # Match DataFrame behavior exactly
        old_df = pd.DataFrame({
            "Date": old_date.astype(str),
            "Amount": old_amount.astype(str),
            "Description": old_description.astype(str)
        })
        old_hash = old_df.sum(axis=1).map(self.generate_id)

        new_df = pd.DataFrame({
            "Date": new_date.astype(str),
            "Amount": new_amount.astype(str),
            "Description": new_description.astype(str)
        })
        new_hash = new_df.sum(axis=1).map(self.generate_id)

        return pd.Series([{o: n} for o, n in zip(old_hash, new_hash)])

    def insert_budget(self, date, amount, category, description, transaction_id=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO BudgetTable (Date, Amount, Category, Description, TransactionId) VALUES (?, ?, ?, ?, ?)",
                (date, amount, category, description, transaction_id)
            )
            conn.commit()

    