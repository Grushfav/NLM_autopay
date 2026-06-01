import os
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

# NLM Kitchen brand palette
BRAND_GREEN = colors.HexColor("#2d6a4f")
BRAND_GREEN_DARK = colors.HexColor("#1b4332")
BRAND_GREEN_LIGHT = colors.HexColor("#d8f3dc")
BRAND_ACCENT = colors.HexColor("#40916c")
BRAND_WARM = colors.HexColor("#bc6c25")
SURFACE = colors.HexColor("#f8faf9")
BORDER = colors.HexColor("#c8d5ce")
TEXT_MUTED = colors.HexColor("#5c6b63")
TEXT_DARK = colors.HexColor("#1a1a1a")

_ROOT = Path(__file__).resolve().parent.parent


def _resolve_logo_path() -> Path | None:
    env = os.getenv("NLM_LOGO_PATH", "").strip()
    candidates = (
        [Path(env)] if env else []
    ) + [
        _ROOT / "assets" / "nlm_logo.png",
        _ROOT / "static" / "logo.png",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _fmt_units(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _info_row(label: str, value: str, label_style: ParagraphStyle, value_style: ParagraphStyle):
    return [
        Paragraph(label, label_style),
        Paragraph(value, value_style),
    ]


def build_payslip_pdf(
    *,
    name: str,
    trn: str,
    nis: str,
    pay_cycle: str,
    pay_date: str,
    pay: PayBreakdown,
    ytd: float,
    site: str = "",
    allowance_label: str = "Incentive",
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.5 * inch,
    )

    title_style = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.white,
    )
    subtitle_style = ParagraphStyle(
        "subtitle",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#b7e4c7"),
    )
    section_style = ParagraphStyle(
        "section",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=BRAND_GREEN_DARK,
        spaceBefore=4,
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "info_label",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=TEXT_MUTED,
    )
    value_style = ParagraphStyle(
        "info_value",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=TEXT_DARK,
    )
    footer_style = ParagraphStyle(
        "footer",
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=TEXT_MUTED,
        alignment=1,
    )

    # —— Top banner ——
    banner_left = [
        Paragraph("PAYSLIP", title_style),
        Paragraph("NLM Kitchen · Confidential", subtitle_style),
    ]
    banner_right = []
    logo_path = _resolve_logo_path()
    if logo_path:
        banner_right.append(Image(str(logo_path), width=2.0 * inch))
    else:
        banner_right.append(
            Paragraph(
                '<font size="14"><b>NLM Kitchen</b></font>',
                ParagraphStyle("logo_text", fontName="Helvetica-Bold", textColor=colors.white),
            )
        )

    banner = Table(
        [[banner_left, banner_right]],
        colWidths=[4.2 * inch, 2.5 * inch],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_GREEN),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (0, 0), 16),
                ("RIGHTPADDING", (1, 0), (1, 0), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("ROUNDEDCORNERS", [6, 6, 0, 0]),
            ]
        )
    )

    # —— Employee details card ——
    info_pairs: list[tuple[str, str]] = [("Employee", name)]
    if site:
        info_pairs.append(("Site", site))
    if trn:
        info_pairs.append(("TRN", trn))
    if nis:
        info_pairs.append(("NIS", nis))
    info_pairs.extend([("Pay cycle", pay_cycle), ("Pay date", pay_date)])

    info_rows = [_info_row(lbl, val, label_style, value_style) for lbl, val in info_pairs]
    mid = (len(info_rows) + 1) // 2
    left_col = info_rows[:mid]
    right_col = info_rows[mid:]
    while len(right_col) < len(left_col):
        right_col.append(["", ""])

    detail_table = Table(
        [[left_col, right_col]],
        colWidths=[3.25 * inch, 3.25 * inch],
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("LINEBELOW", (0, 0), (-1, 0), 2, BRAND_ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    # Flatten nested tables for info columns
    def _col_table(rows: list) -> Table:
        t = Table(rows, colWidths=[1.1 * inch, 2.0 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return t

    detail_table = Table(
        [[_col_table(left_col), _col_table(right_col)]],
        colWidths=[3.35 * inch, 3.35 * inch],
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("LINEBELOW", (0, 0), (-1, 0), 2, BRAND_ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 14),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    # —— Earnings table ——
    cell_header = ParagraphStyle(
        "th", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, alignment=1
    )
    cell_body = ParagraphStyle("td", fontName="Helvetica", fontSize=10, textColor=TEXT_DARK)
    cell_body_r = ParagraphStyle("td_r", fontName="Helvetica", fontSize=10, textColor=TEXT_DARK, alignment=2)
    cell_desc = ParagraphStyle("td_desc", fontName="Helvetica", fontSize=10, textColor=TEXT_DARK)

    earnings_rows: list[list] = [
        [
            Paragraph("DESCRIPTION", cell_header),
            Paragraph("UNITS", cell_header),
            Paragraph("RATE", cell_header),
            Paragraph("AMOUNT", cell_header),
        ],
        [
            Paragraph("Regular hours", cell_desc),
            Paragraph(_fmt_units(pay.regular_units), cell_body_r),
            Paragraph(format_jmd(pay.regular_rate), cell_body_r),
            Paragraph(format_jmd(pay.regular_amount), cell_body_r),
        ],
    ]

    if pay.overtime_units > 0:
        earnings_rows.append(
            [
                Paragraph("Overtime", cell_desc),
                Paragraph(_fmt_units(pay.overtime_units), cell_body_r),
                Paragraph(format_jmd(pay.overtime_rate), cell_body_r),
                Paragraph(format_jmd(pay.overtime_amount), cell_body_r),
            ]
        )

    if pay.allowance > 0:
        earnings_rows.append(
            [
                Paragraph(allowance_label, cell_desc),
                Paragraph("—", cell_body_r),
                Paragraph("—", cell_body_r),
                Paragraph(format_jmd(pay.allowance), cell_body_r),
            ]
        )

    net_style = ParagraphStyle(
        "net", fontName="Helvetica-Bold", fontSize=11, textColor=BRAND_GREEN_DARK, alignment=2
    )
    net_label = ParagraphStyle(
        "net_l", fontName="Helvetica-Bold", fontSize=11, textColor=BRAND_GREEN_DARK
    )
    ytd_style = ParagraphStyle(
        "ytd", fontName="Helvetica-Bold", fontSize=10, textColor=TEXT_DARK, alignment=2
    )

    earnings_rows.append(
        [
            Paragraph("NET PAY", net_label),
            Paragraph("", cell_body),
            Paragraph("", cell_body),
            Paragraph(format_jmd(pay.net_pay), net_style),
        ]
    )
    earnings_rows.append(
        [
            Paragraph("Year to date", cell_desc),
            Paragraph("", cell_body),
            Paragraph("", cell_body),
            Paragraph(format_jmd(ytd), ytd_style),
        ]
    )

    earnings_table = Table(
        earnings_rows,
        colWidths=[2.55 * inch, 0.95 * inch, 1.35 * inch, 1.55 * inch],
        repeatRows=1,
    )

    last_row = len(earnings_rows) - 1
    net_row = last_row - 1
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, net_row - 1), 0.4, BORDER),
        ("LINEBELOW", (0, net_row - 1), (-1, net_row - 1), 0.4, BORDER),
        ("BACKGROUND", (0, net_row), (-1, net_row), BRAND_GREEN_LIGHT),
        ("LINEABOVE", (0, net_row), (-1, net_row), 1.2, BRAND_GREEN),
        ("LINEBELOW", (0, net_row), (-1, net_row), 1.2, BRAND_GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, net_row), (-1, net_row), 10),
        ("BOTTOMPADDING", (0, net_row), (-1, net_row), 10),
    ]
    # Zebra striping on data rows (not header, net, or ytd)
    data_end = net_row - 1
    for i in range(1, data_end + 1):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.white))
        else:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), SURFACE))

    earnings_table.setStyle(TableStyle(style_commands))

    footer = Paragraph(
        "This payslip was generated electronically by NLM Kitchen payroll. "
        "Please retain for your records. For questions, contact your payroll administrator.",
        footer_style,
    )

    story = [
        banner,
        Spacer(1, 0.12 * inch),
        detail_table,
        Spacer(1, 0.18 * inch),
        Paragraph("Earnings summary", section_style),
        earnings_table,
        Spacer(1, 0.22 * inch),
        footer,
    ]

    doc.build(story)
    return buffer.getvalue()
