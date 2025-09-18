from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import datetime
import subprocess


class TreasurerReport:
    GOLD = RGBColor(160, 116, 0)   # Old Gold
    BLACK = RGBColor(34, 31, 32)   # Black

    def __init__(self, startDate, endDate, table,
                 initialBalance, currentBalance,
                 deposits, depositsSum,
                 withdrawals, withdrawalSum):
        self.startDate = startDate
        self.endDate = endDate
        self.table = table
        self.initialBalance = initialBalance
        self.currentBalance = currentBalance
        self.deposits = deposits
        self.depositsSum = depositsSum
        self.withdrawals = withdrawals
        self.withdrawalSum = withdrawalSum
        self.document = Document()

    # ---------------------------
    # Helpers
    # ---------------------------
    def _add_heading(self, text, level=0, color=None, align="center"):
        para = self.document.add_heading(text, level=level)
        run = para.runs[0]
        run.font.size = Pt(16 if level == 0 else 14)
        if color:
            run.font.color.rgb = color
        if align == "center":
            para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        return para

    def _add_table(self, df, title, total=None):
        self.document.add_heading(title, level=2)
        table = self.document.add_table(rows=df.shape[0] + 1, cols=df.shape[1])
        table.style = "Light Grid Accent 1"

        # Header row
        for j, col in enumerate(df.columns):
            cell = table.cell(0, j)
            cell.text = col
            run = cell.paragraphs[0].runs[0]
            run.font.bold = True
            run.font.color.rgb = self.GOLD

        # Data rows
        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                cell = table.cell(i + 1, j)
                value = df.values[i, j]
                if isinstance(value, (float, int)):
                    cell.text = f"${value:,.2f}"
                else:
                    cell.text = str(value)

        if total is not None:
            para = self.document.add_paragraph(f"Total {title}: ${total:,.2f}")
            para.runs[0].bold = True
            para.runs[0].font.color.rgb = self.GOLD

    # ---------------------------
    # Build Report
    # ---------------------------
    def build(self):
        # Cover/Header
        self._add_heading("ALPHA PHI ALPHA FRATERNITY, INC.", level=0, color=self.GOLD)
        self._add_heading("Gamma Beta Chapter", level=1, color=self.BLACK)
        self._add_heading("Treasurer's Report", level=1, color=self.GOLD)
        self._add_heading(
            f"{self.startDate.strftime('%B %d, %Y')} – {self.endDate.strftime('%B %d, %Y')}",
            level=2,
            color=self.BLACK
        )

        # Financial summary
        self.document.add_heading("Financial Summary", level=2)
        self.document.add_paragraph(f"Initial Balance: ${self.initialBalance:,.2f}")
        self.document.add_paragraph(f"Current Balance: ${self.currentBalance:,.2f}")
        
        # Receipts
        self._add_table(self.deposits, "Receipts", total=self.depositsSum)

        # Expenditures (Withdrawals)
        self._add_table(self.withdrawals, "Expenditures", total=self.withdrawalSum)

        # Outstanding Expenditures (placeholder section)
        self.document.add_heading("Outstanding Expenditures", level=2)
        self.document.add_paragraph("No outstanding expenditures recorded.")  # can be filled later


        # Dues (placeholder section)
        self.document.add_heading("Dues", level=2)
        self.document.add_paragraph("No dues updates recorded.")  # can be filled later

        # Save file
        filename = f"./reports/automated/TreasurerReport_{self.endDate.strftime('%B%Y')}.docx"
        self.document.save(filename)

        # Auto-open
        subprocess.run(["open", filename])
        return filename
