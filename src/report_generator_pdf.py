from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from io import BytesIO
import os
import subprocess
import pyquotegen
import ingest
from datetime import datetime


class TreasurerReportPDF:
    def __init__(self, start_date, end_date, data_manager: ingest.DataManager):
        self.start_date = start_date
        self.end_date = end_date
        self.data_manager = data_manager
        self.data = data_manager.load_data(start_date, end_date, source="")
        self.dues = data_manager.load_dues(start_date, end_date)
        self.filename = f"./reports/automated/TreasurerReport_{start_date:%Y-%m-%d}_to_{end_date:%Y-%m-%d}.pdf"
        self.buffer = BytesIO()

        # Fonts for Unicode compatibility (important if you use symbols or foreign text)
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))

        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(name="Center", alignment=1, fontSize=14, fontName="HeiseiMin-W3"))
        self.styles.add(ParagraphStyle(name="Left", alignment=0, fontSize=12, fontName="HeiseiMin-W3"))
        self.styles.add(ParagraphStyle(name="GoldHeading", textColor=colors.gold, fontSize=14, fontName="HeiseiMin-W3", spaceAfter=6))

    # ---------------------------
    # Build Report
    # ---------------------------
    def build(self):
        doc = SimpleDocTemplate(self.buffer, pagesize=LETTER,
                                leftMargin=0.5 * inch, rightMargin=0.5 * inch,
                                topMargin=0.5 * inch, bottomMargin=0.5 * inch)

        story = []

        # Header
        story.append(Image("./gblogo.png", width=0.75 * inch, height=0.75 * inch))
        story.append(Paragraph("ALPHA PHI ALPHA FRATERNITY, INC.<br/>Gamma Beta Chapter<br/>Treasurer’s Report<br/>Bro. Emmanuel Davis, GB Chapter Treasurer", self.styles["Center"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Financial Summary Report<br/>{self.start_date:%B %d, %Y} – {self.end_date:%B %d, %Y}", self.styles["Center"]))
        story.append(PageBreak())

        # Checking & Cashapp summary
        checking = self.data_manager.load_data(self.start_date, self.end_date, "Checking")
        cashapp = self.data_manager.load_data(self.start_date, self.end_date, "Cashapp")

        story.append(Paragraph(f"Current Balance (Checking): ${checking['current_balance']:,.2f}", self.styles["Left"]))
        story.append(Paragraph(f"Initial Balance (Checking): ${checking['initial_balance']:,.2f}", self.styles["Left"]))
        story.append(Paragraph(f"Current Balance (CashApp): ${cashapp['current_balance']:,.2f}", self.styles["Left"]))
        story.append(Paragraph(f"Initial Balance (CashApp): ${cashapp['initial_balance']:,.2f}", self.styles["Left"]))
        story.append(PageBreak())

        # Deposits / Income
        story.append(Paragraph(f"Total Deposits: ${self.data['deposits_total']:,.2f}", self.styles["GoldHeading"]))
        story += self._add_table(self.data.get("incomes"), "Income Categories", ["Labels", "Amount"])
        story += self._add_table(self.data.get("deposits").drop(columns="TransactionId"), "Receipts")
        story.append(PageBreak())

        # Withdrawals / Expenses
        story.append(Paragraph(f"Total Withdrawals: ${self.data['withdrawals_total']:,.2f}", self.styles["GoldHeading"]))
        story += self._add_table(self.data.get("expenses"), "Expense Categories", ["Labels", "Amount"])
        story += self._add_table(self.data.get("withdrawals").drop(columns="TransactionId"), "Expenditures")
        story.append(PageBreak())

        # Dues
        story.append(Paragraph("Dues", self.styles["GoldHeading"]))
        dues = self.dues
        if dues.get("expected_dues") is not None:
            story.append(Paragraph(f"Expected Dues: ${dues['expected_dues']:,.2f}", self.styles["Left"]))
            story.append(Paragraph(f"Total Paid: ${dues['total_paid']:,.2f}", self.styles["Left"]))
            story.append(Paragraph(f"Missed Revenue: ${dues['missed_revenue']:,.2f}", self.styles["Left"]))
        else:
            story.append(Paragraph("No dues data recorded.", self.styles["Left"]))

        if (counts := dues.get("status_counts")) is not None and not counts.empty:
            story += self._add_table(counts, "Member Dues Status Counts")

        if (dues_status := dues.get("dues_status")) is not None and not dues_status.empty:
            story += self._add_table(dues_status[["MemberName", "PeriodStart", "Amount", "AmountPaid", "Status"]],
                                     "Per-Member Dues Status")

        # Footer / Quote
        inspirational_quote = pyquotegen.get_quote("inspirational")
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"<i>{inspirational_quote}</i>", self.styles["Center"]))
        story.append(Paragraph("This report has been automatically generated by the Treasury Dashboard ©2025 Terrell Parker",
                               self.styles["Center"]))

        doc.build(story)
        with open(self.filename, "wb") as f:
            f.write(self.buffer.getvalue())
        return self.buffer

    # ---------------------------
    # Helpers
    # ---------------------------
    def _add_table(self, df, title, columns=None):
        story = [Paragraph(title, self.styles["GoldHeading"])]
        if df is None or df.empty:
            story.append(Paragraph(f"No {title.lower()} recorded.", self.styles["Left"]))
            return story

        if columns:
            df = df[columns]

        data = [list(df.columns)] + df.values.tolist()
        table = Table(data, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.gold),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "HeiseiMin-W3"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]))
        story.append(table)
        story.append(Spacer(1, 12))
        return story

    def open(self):
        subprocess.run(["open", self.filename])
