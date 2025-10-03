# sql_queries.py


# Table Creation

CREATE_TRANSACTION_TABLE = """
    CREATE TABLE TransactionTable (
        TransactionId TEXT PRIMARY KEY,
        Date DATE,
        Amount DECIMAL(18, 2),
        Source TEXT,
        Description TEXT
    )
"""

INSERT_INITIAL_BALANCE = """
    INSERT INTO TransactionTable (TransactionId, Date, Amount, Source, Description)
    VALUES (
        generate_id('1941-05-23' || '0' || 'Initial Balance'),
        '1941-05-23',
        0,
        'Checking',
        'Initial Balance'
    )
"""

RECONCILE_CASHAPP_APRIL = """
    INSERT INTO TransactionTable (TransactionId, Date, Amount, Source, Description)
    VALUES (
        generate_id('2025-04-01' || '512.00' || 'Cash App discrepancy April'),
        '2025-04-01',
        512.00,
        'Cashapp',
        'Cash App discrepancy April'
    )
"""

RECONCILE_CASHAPP_MARCH = """
    INSERT INTO TransactionTable (TransactionId, Date, Amount, Source, Description)
    VALUES (
        generate_id('2025-03-01' || '414.00' || 'Cash App discrepancy March'),
        '2025-03-01',
        414.00,
        'Cashapp',
        'Cash App discrepancy March'
    )
"""

CREATE_NOTE_TABLE = """
    CREATE TABLE NoteTable (
        NoteId TEXT PRIMARY KEY,
        Category TEXT,
        Notes TEXT,
        FOREIGN KEY (NoteID) REFERENCES TransactionTable(TransactionID)
    )
"""

CREATE_MEMBER_TABLE = """
    CREATE TABLE IF NOT EXISTS MemberTable (
        GBId TEXT PRIMARY KEY,
        MemberName TEXT,
        AlphaID TEXT,
        InitiationDate DATE,
        GraduationDate DATE
    )
"""

CREATE_DUES_TABLE = """
    CREATE TABLE DuesTable (
        DueId TEXT PRIMARY KEY,
        GBId TEXT NOT NULL,
        PeriodStart DATE NOT NULL,
        PeriodEnd DATE NOT NULL,
        Amount DECIMAL(18,2),
        FOREIGN KEY (GBId) REFERENCES MemberTable(GBId)
    )
"""

CREATE_DUES_PAYMENTS_TABLE = """
    CREATE TABLE DuesPayments (
        DuesPaymentId INTEGER PRIMARY KEY AUTOINCREMENT,
        DueId TEXT NOT NULL,
        TransactionId TEXT NOT NULL,
        FOREIGN KEY (DueId) REFERENCES DuesTable(DueId),
        FOREIGN KEY (TransactionId) REFERENCES TransactionTable(TransactionId)
    )
"""

CREATE_BUDGET_TABLE = """
    CREATE TABLE BudgetTable
    (
    BudgetId INTEGER PRIMARY KEY AUTOINCREMENT,
    Date DATE,
    Amount Decimal(18,2),
    TransactionId TEXT,
    FOREIGN KEY (TransactionId) REFERENCES TransactionTable(TransactionId)
    )
"""


# Inserts / Merges

INSERT_MEMBERS = "INSERT OR IGNORE INTO MemberTable SELECT * FROM tmp"

INSERT_TRANSACTIONS = "INSERT OR IGNORE INTO TransactionTable SELECT * FROM tmp"

DROP_TMP = "DROP TABLE IF EXISTS tmp"


# Queries

TRANSACTION_NOTES_QUERY = """
    SELECT
        t.TransactionId,
        t.Date,
        t.Amount,
        t.Source,
        t.Description,
        n.Category,
        n.Notes
    FROM TransactionTable t
    LEFT JOIN NoteTable n
        ON t.TransactionId = n.NoteId
"""

DUES_QUERY = """
    SELECT
        d.DueId,
        d.GBId,
        t.TransactionId,
        m.MemberName,
        d.PeriodStart,
        t.Date,
        d.Amount,
        t.Amount AS AmountPaid
    FROM DuesTable d
    LEFT JOIN PaymentsTable p
        ON d.DueId = p.DueId
    LEFT JOIN MemberTable m
        ON m.GBId = d.GBId
    LEFT JOIN TransactionTable t
        ON t.TransactionId = p.TransactionId 
        AND t.Date <= ?
"""

INSERT_DUES_FROM_MEMBERS = """
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
"""
