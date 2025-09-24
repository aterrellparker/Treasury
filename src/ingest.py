import glob
import sqlite3
import os
import hashlib
import base64
import datetime

import pandas as pd

class DataIngestor:
    def __init__(self, db_path="database.db"):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            self.create_database()
            self.ingest_data()


    # ---------------------------
    # Utility: Hash generator
    # ---------------------------
    @staticmethod
    def generate_id(data: str) -> str:
        """Generate a unique hash-based ID from input string."""
        return base64.urlsafe_b64encode(
            hashlib.md5(data.encode()).digest()
        ).decode()

    # ---------------------------
    # Create fresh database
    # ---------------------------
    def create_database(self):
        """Create a new database with base schema and initial balance."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        connection.execute("PRAGMA foreign_keys = ON")

        # Register hash function
        connection.create_function("generate_id", 1, self.generate_id)

        # Create tables
        cursor.execute(
            """
            CREATE TABLE TransactionTable (
                TransactionId TEXT PRIMARY KEY,
                Date DATE,
                Amount DECIMAL(18, 2),
                Source TEXT,
                Description TEXT
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO TransactionTable (TransactionId, Date, Amount, Source, Description)
            VALUES (
                generate_id('1941-05-23' || '0' || 'Initial Balance'),
                '1941-05-23',
                0,
                'Checking',
                'Initial Balance'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE NoteTable (
                NoteId TEXT PRIMARY KEY,
                Category TEXT,
                Notes TEXT,
                FOREIGN KEY (NoteID) REFERENCES TransactionsTable(TransactionID)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS MemberTable 
            (
                GBId TEXT PRIMARY KEY,
                MemberName TEXT,
                AlphaID TEXT,
                InitiationDate DATE,
                GraduationDate DATE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE DuesTable (
                DueID TEXT PRIMARY KEY,
                GBId TEXT NOT NULL,
                PeriodStart DATE NOT NULL,
                PeriodEnd DATE NOT NULL,
                Amount Decimal(18,2),
                FOREIGN KEY (GBId) REFERENCES MemberTable(GBId)
            );

            """
        )                 
        cursor.execute('''
            CREATE TABLE DuesPayments (
            DuesPaymentId INTEGER PRIMARY KEY AUTOINCREMENT,
            DueId TEXT NOT NULL,
            TransactionId TEXT NOT NULL,
            FOREIGN KEY (DueId) REFERENCES DuesTable(DueId),
            FOREIGN KEY (TransactionId) REFERENCES TransactionTable(TransactionId)
            );
        ''')


        connection.commit()
        connection.close()

    def load_members(self):
        # print(self.db_path)
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
      
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

        due_dates.to_sql("DueDatesTable", connection, if_exists="replace", index=False)

        # Insert dues using SQL join
        cursor.execute("""
        INSERT OR IGNORE INTO DuesTable (DueID, GBId, PeriodStart, PeriodEnd, Amount)
        SELECT 
            CAST(STRFTIME('%Y%m', d.PeriodStart) || m.GBId AS TEXT) AS DueID,
            m.GBId,
            d.PeriodStart,
            d.PeriodEnd,
            d.Amount
        FROM MemberTable m
        JOIN DueDatesTable d
            ON d.PeriodStart >= m.InitiationDate
            AND (m.GraduationDate IS NULL OR d.PeriodStart <= m.GraduationDate)
        """)
        payments = pd.read_csv("./data/raw/DuePayments.csv")  
        payments.to_sql("PaymentsTable", connection, if_exists="replace", index=False)
        


        connection.commit()
        # # df = pd.read_sql(FS, connection)#, parse_dates=['PeriodStart','PeriodEnd'])
        # print("hello")
        # print(df)


        # # Step 2: Cross join with members
        # due_dates['key'] = 1
        # members['key'] = 1
        # all_dues = due_dates.merge(members, on='key').drop(columns='key')

        # # Step 3: Filter active members in that year
        # active_dues = all_dues[
        #     (all_dues['InitiationDate'] <= all_dues['PeriodStart']) &
        #     (
        #         all_dues['GraduationDate'].isna() |
        #         (all_dues['GraduationDate'] >= all_dues['PeriodStart'])
        #     )
        # ]


        # active_dues['Amount'] = 100
        # active_dues.to_csv('dues.csv')
        # print(active_dues)

        # # Only keep columns for DuesTable (exclude DueID)
        # df_to_insert = active_dues[['GBId', 'PeriodStart', 'PeriodEnd', 'Amount']]

        # # Insert into SQLite table without replacing it
        # df_to_insert.to_sql("DuesTable", connection, if_exists="append", index=False)
        # #df.to_sql("tmp2", connection, if_exists="append", index=False)

        # # print(active_dues)
        # return df
    # Ingest data from CSVs
    # ---------------------------
    def ingest_data(self):
        """Load all CSV sources into database."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()

        for file in glob.glob("./Data/Raw/Members/*.csv"):
            df = pd.read_csv(file)
            # df['InitiationDate'] = pd.to_datetime(df['InitiationDate']).dt.strftime('%Y-%m-%d')
            # df['GraduationDate'] = pd.to_datetime(df['InitiationDate']).dt.strftime('%Y-%m-%d')
            # df['InitiationDate'] = pd.to_datetime(df['InitiationDate']).dt.strftime('%Y-%m-%d')

            df.to_sql("tmp2", connection, if_exists="append", index=False)

        cursor.execute("INSERT OR IGNORE INTO MemberTable SELECT * FROM tmp2")
        cursor.execute("DROP TABLE IF EXISTS tmp")

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
            df.to_sql("tmp", connection, if_exists="append", index=False)

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
            df.to_sql("tmp", connection, if_exists="append", index=False)

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
                    "Amount",
                    "Fee",
                    "Asset Type",
                    "Asset Price",
                    "Asset Amount",
                    "Status",
                ]
            )
            df = df.rename(columns={"Net Amount": "Amount", "Notes": "Description"})
            df["Date"] = pd.to_datetime(df["Date"].str.split(" ").str[0]).dt.strftime(
                "%Y-%m-%d"
            )
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
            df.to_sql("tmp", connection, if_exists="append", index=False)


        # Merge into main table
        cursor.execute("INSERT OR IGNORE INTO TransactionTable SELECT * FROM tmp")
        cursor.execute("DROP TABLE IF EXISTS tmp")

        # --- Notes Table (latest edits) ---
        notes_files = glob.glob("./Data/Backups/edits_*.csv")
        if notes_files:
            latest_file = max(notes_files, key=os.path.getctime)
            description_data = pd.read_csv(latest_file)
            description_data.to_sql("NoteTable", connection, if_exists="replace", index=False)

        connection.commit()
        connection.close()
