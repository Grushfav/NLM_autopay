from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.calculator import PayBreakdown, format_jmd

HEADER_BG = colors.HexColor("#B4C7E7")
LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "logo.png"


def _fmt_units(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def build_payslip_pdf(
    *,
    name: str,
    trn: str,
    nis: str,
    pay_cycle: str,
    pay_date: str,
    pay: PayBreakdown,
    ytd: float,
    allowance_label: str = "Allowance",
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    label_style = ParagraphStyle("label", fontName="Helvetica", fontSize=10, leading=14)
    bold_style = ParagraphStyle("bold", fontName="Helvetica-Bold", fontSize=10, leading=14)

    header_left = [
        [Paragraph(f"<b>Name:</b> {name}", label_style)],
        [Paragraph(f"<b>TRN:</b> {trn}", label_style)],
        [Paragraph(f"<b>NIS:</b> {nis}", label_style)],
        [Paragraph(f"<b>Pay Cycle:</b> {pay_cycle}", label_style)],
        [Paragraph(f"<b>Pay Date:</b> {pay_date}", label_style)],
    ]
    left_table = Table(header_left, colWidths=[4.2 * inch])
    left_table.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    right_content = []
    if LOGO_PATH.exists():
        img = Image(str(LOGO_PATH), width=1.8 * inch, height=1.0 * inch)
        right_content.append(img)
    else:
        right_content.append(Paragraph("<b>NLM Kitchen</b>", bold_style))

    top_row = Table(
        [[left_table, right_content]],
        colWidths=[4.4 * inch, 2.4 * inch],
    )
    top_row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
            ]
        )
    )

    earnings_rows = [
        ["DESCRIPTION", "UNITS", "RATE", "AMOUNT"],
        [
            "Regular hours",
            _fmt_units(pay.regular_units),
            format_jmd(pay.regular_rate),
            format_jmd(pay.regular_amount),
        ],
    ]

    if pay.overtime_units > 0:
        earnings_rows.append(
            [
                "Overtime",
                _fmt_units(pay.overtime_units),
                format_jmd(pay.overtime_rate),
                format_jmd(pay.overtime_amount),
            ]
        )

    if pay.allowance > 0:
        earnings_rows.append([allowance_label, "", "", format_jmd(pay.allowance)])

    earnings_rows.append(["NET PAY", "", "", format_jmd(pay.net_pay)])
    earnings_rows.append(["YEAR TO DATE", "", "", format_jmd(ytd)])

    earnings_table = Table(
        earnings_rows,
        colWidths=[2.4 * inch, 1.0 * inch, 1.4 * inch, 1.6 * inch],
    )

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    earnings_table.setStyle(TableStyle(style_commands))

    doc.build([top_row, Spacer(1, 0.15 * inch), earnings_table])
    return buffer.getvalue()
