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
        if os.path.exists(self.db_path):
            self.connection = sqlite3.connect(self.db_path)

        if not os.path.exists(self.db_path):
            self.connection = sqlite3.connect(self.db_path)
            self.create_database()
            self.read_data()


    # ---------------------------
    # Utility: Hash generator
    # ---------------------------
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
        cursor.execute(RECONCILE_CASHAPP_MARCH)
        cursor.execute(RECONCILE_CASHAPP_APRIL)
        cursor.execute(CREATE_NOTE_TABLE)
        cursor.execute(CREATE_MEMBER_TABLE)
        cursor.execute(CREATE_DUES_TABLE) 
        cursor.execute(CREATE_DUES_PAYMENTS_TABLE)


        self.connection.commit()
        self.connection.close()

    def read_data(self):
        """Load all CSV sources into database."""
        self.connection = sqlite3.connect(self.db_path)
        cursor = self.connection.cursor()
    
        for file in glob.glob("./Data/Raw/Members/*.csv"):
            df = pd.read_csv(file)
            df.to_sql("tmp", self.connection, if_exists="append", index=False)

        cursor.execute(INSERT_MEMBERS)
        cursor.execute(DROP_TMP)

        # --- Checking Data ---
        for file in glob.glob("./Data/raw/Checking/*.csv"):
            df = pd.read_csv(file, header=None)
            df.columns = ["Date", "Amount", "n/a", "Check Number", "Description"]
            df = df.drop(columns=["n/a", "Check Number"])
            df["Date"] = pd.to_datetime(df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
            df["Source"] = "Checking"
            df["TransactionId"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df = df[["TransactionId", "Date", "Amount", "Source", "Description"]]
            df.to_sql("tmp", self.connection, if_exists="append", index=False)

        # --- Statements Data ---
        for file in glob.glob("./Data/raw/Statements/*.csv"):
            df = pd.read_csv(file, header=None)
            df.columns = ["Date", "Description", "Amount"]
            df["Date"] = pd.to_datetime(df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
            df["Source"] = "Checking"
            df["TransactionId"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df = df[["TransactionId", "Date", "Amount", "Source", "Description"]]
            df.to_sql("tmp", self.connection, if_exists="append", index=False)

        # --- Cashapp Data ---
        for file in glob.glob("./Data/raw/Cashapp/*.csv"):
            df = pd.read_csv(file)
            df["Source"] = "Cashapp"
            df = df[df["Status"] == "COMPLETE"]
            df = df.drop(
                columns=[
                    "Transaction ID",
                    "Transaction Type",
                    "Currency",
                    "Fee",
                    "Amount",
                    "Asset Type",
                    "Asset Price",
                    "Asset Amount",
                    "Status",
                ]
            )
            df = df.rename(columns={"Net Amount": "Amount", "Notes": "Description"})
            df["Date"] = pd.to_datetime(df["Date"].str.split(" ").str[0]).dt.strftime("%Y-%m-%d")
            df["Amount"] = (
                df["Amount"]
                .str.replace(r"[\$,)]", "", regex=True)  # remove $ , )
                .str.replace(r"\(", "-", regex=True)  # convert ( → -
            )
            df["TransactionId"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            #Adding Extra Information After hash to preserve ID's
            df['Description'] = df[['Description', 'Name of sender/receiver', 'Account']].astype(str).agg(' - '.join, axis=1)
        
            df=df.drop(columns=["Name of sender/receiver","Account"])
            df.to_sql("tmp", self.connection, if_exists="append", index=False)

        payments = pd.read_csv("./data/raw/DuePayments.csv")  
        payments.to_sql("PaymentsTable", self.connection, if_exists="replace", index=False)
        
        # Merge into main table
        cursor.execute(INSERT_TRANSACTIONS)
        cursor.execute(DROP_TMP)

        # --- Notes Table (latest edits) ---
        notes_files = glob.glob("./Data/Backups/edits_*.csv")
        if notes_files:
            latest_file = max(notes_files, key=os.path.getctime)
            description_data = pd.read_csv(latest_file)
            description_data.to_sql("NoteTable", self.connection, if_exists="replace", index=False)

        self.connection.commit()
    
    def _create_due_dates(self):
        self.connection = sqlite3.connect(self.db_path)
        cursor = self.connection.cursor()
      
        # start_year = members['InitiationDate'].min().date()
        end_year = datetime.datetime.today()
    
        # Create a dataframe with start and end of each cycle
        due_dates = (
            pd.date_range("2019-08-01", end_year, freq="6MS")
            .to_frame(index=False, name="PeriodStart")
        ) 
        due_dates["PeriodEnd"] = due_dates["PeriodStart"]
   
        # due_dates = pd.DataFrame({
        #     'PeriodStart': pd.to_datetime(years.astype(str) + '-08-01'),
        #     'PeriodEnd':   pd.to_datetime(years.astype(str) + '-12-31')
        # })
        due_dates['Amount'] = 100

        due_dates['PeriodStart'] = pd.to_datetime(due_dates['PeriodStart']).dt.strftime('%Y-%m-%d')
        due_dates['PeriodEnd']   = pd.to_datetime(due_dates['PeriodEnd']).dt.strftime('%Y-%m-%d')

        due_dates.to_sql("DueDatesTable", self.connection, if_exists="replace", index=False)

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
    

    def load_data(self, start_date, end_date, source):
        if source:
            BASE_QUERY = TRANSACTION_NOTES_QUERY + " WHERE t.Source = ?"
        else:
            BASE_QUERY = TRANSACTION_NOTES_QUERY
        transaction_notes_table, deposits, withdrawals = self._preprocess_transactions(pd.read_sql(BASE_QUERY, self.connection, parse_dates=["Date"], params=(source,) if source else None))
        balance_table, initial_balance, current_balance = self._compute_balances(transaction_notes_table, start_date, end_date)

 
        filtered = self._apply_filters(transaction_notes_table, start_date, end_date)
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
    
    def load_dues(self, start_date, end_date):
        dues = self._load_dues()

           # Convert start/end to strings for comparison
        if not dues.empty and start_date is not None:
            start_str = pd.Timestamp(start_date).strftime("%Y-%m-%d")
            end_str = pd.Timestamp(end_date).strftime("%Y-%m-%d")
            dues = dues[dues["PeriodStart"] <= start_str]
            latest_term = dues["PeriodStart"].max()
            dues = dues[dues["PeriodStart"] == latest_term]

        dues_status = (
            dues
            .groupby(["GBId", "MemberName", "PeriodStart", "Amount" ], as_index=False)
            .agg({"AmountPaid": "sum"})   # sum all payments for the due
        )
        # --- Compute summary values ---
        expected_dues = dues_status["Amount"].sum()

        # Total actually paid (sum of PaymentAmount where not null)
        total_paid = dues_status["AmountPaid"].fillna(0).sum()

        # Missed revenue = what was expected but not collected
        missed_revenue = expected_dues - total_paid

        dues_status["Remaining"] = dues_status["Amount"] - dues_status["AmountPaid"].fillna(0)

        # Determine status based on payments vs due amount
        dues_status["Status"] = dues_status.apply(
            lambda row: "Paid" if row["Remaining"] <= 0 
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
        dues_status = dues_status.sort_values(by=["PeriodStart", "Status", "GBId"], ascending=[False, True, True])
        styled_df = dues_status[["GBId", "MemberName", "PeriodStart", "Amount", "AmountPaid", "Status"]] \
            .style.apply(highlight_status, axis=1)
            # Return everything as a dictionary
        return {
            "dues": dues,                    # raw dues
            "dues_status": dues_status,      # per-member status
            "expected_dues": expected_dues,  # total expected
            "total_paid": total_paid,        # total collected
            "missed_revenue": missed_revenue,# total missed
            "status_counts": status_counts,   # grouped counts
            "styled_df": styled_df
        }
    


    def _load_dues(self):
        self._create_due_dates()
        return pd.read_sql(DUES_QUERY, self.connection)

    def _preprocess_transactions(self, df):
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df["Category"] = df["Category"].fillna("Uncategorized")
        df.loc[df["Category"].str.strip() == "", "Category"] = "Uncategorized"
        deposits = df[df["Amount"] > 0]
        withdrawals = df[df["Amount"] < 0]
        return df, deposits, withdrawals

    def _compute_balances(self, df, start_date, end_date):
        balance_df = df.sort_values("Date").assign(
            Balance=lambda x: x["Amount"].cumsum()
        )
        balanceTable = balance_df[["Date", "Balance"]]

        initial = df.loc[df["Date"] < start_date.date(), "Amount"].sum()
        current = df.loc[df["Date"] <= end_date.date(), "Amount"].sum()
        return balanceTable, initial, current

    def _apply_filters(self, df, start_date, end_date):
        mask = df["Date"].between(start_date.date(), end_date.date())
        return df.loc[mask] 
    
    def _split_transactions(self, df):
        deposits = df[df["Amount"] > 0]
        withdrawals = df[df["Amount"] < 0]
        return deposits, withdrawals