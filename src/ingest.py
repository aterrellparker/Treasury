import glob
import sqlite3
import os
import hashlib
import base64


import pandas as pd

class DataIngestor:
    def __init__(self, db_path="database.db"):
        self.db_path = db_path

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

        # Register hash function
        connection.create_function("generate_id", 1, self.generate_id)

        # Create tables
        cursor.execute(
            """
            CREATE TABLE transactionTable (
                Id TEXT PRIMARY KEY,
                Date DATE,
                Amount DECIMAL(18, 2),
                Source TEXT,
                Description TEXT
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO transactionTable (Id, Date, Amount, Source, Description)
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
            CREATE TABLE notesTable (
                Id TEXT PRIMARY KEY,
                Category TEXT,
                Notes TEXT
            )
            """
        )

        connection.commit()
        connection.close()

    # ---------------------------
    # Ingest data from CSVs
    # ---------------------------
    def ingest_data(self):
        """Load all CSV sources into database."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()

        # --- Checking Data ---
        for file in glob.glob("./Checking/*.csv"):
            df = pd.read_csv(file, header=None)
            df.columns = ["Date", "Amount", "n/a", "Check Number", "Description"]
            df = df.drop(columns=["n/a", "Check Number"])
            df["Date"] = pd.to_datetime(df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
            df["Source"] = "Checking"
            df["Id"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df = df[["Id", "Date", "Amount", "Source", "Description"]]
            df.to_sql("tmp", connection, if_exists="append", index=False)

        # --- Statements Data ---
        for file in glob.glob("./Statements/*.csv"):
            df = pd.read_csv(file, header=None)
            df.columns = ["Date", "Description", "Amount"]
            df["Date"] = pd.to_datetime(df["Date"], format="mixed").dt.strftime("%Y-%m-%d")
            df["Source"] = "Checking"
            df["Id"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df = df[["Id", "Date", "Amount", "Source", "Description"]]
            df.to_sql("tmp", connection, if_exists="append", index=False)

        # --- Cashapp Data ---
        for file in glob.glob("./Cashapp/*.csv"):
            df = pd.read_csv(file)
            df["Source"] = "Cashapp"
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
                    "Name of sender/receiver",
                    "Account",
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
            df["Id"] = (
                df[["Date", "Amount", "Description"]]
                .astype(str)
                .sum(axis=1)
                .map(self.generate_id)
            )
            df.to_sql("tmp", connection, if_exists="append", index=False)

        # Merge into main table
        cursor.execute("INSERT OR IGNORE INTO transactionTable SELECT * FROM tmp")
        cursor.execute("DROP TABLE IF EXISTS tmp")

        # --- Notes Table (latest edits) ---
        notes_files = glob.glob("./Notes/edits_*.csv")
        if notes_files:
            latest_file = max(notes_files, key=os.path.getctime)
            description_data = pd.read_csv(latest_file)
            description_data.to_sql("notesTable", connection, if_exists="replace", index=False)

        connection.commit()
        connection.close()
