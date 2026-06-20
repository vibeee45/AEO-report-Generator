"""
AEO (Answer Engine Optimization) Audit Report Generator
========================================================
Production-ready ReportLab PDF generator.
Fully data-driven — no hardcoded content.
Works for any website type: blog, ecommerce, SaaS, enterprise, etc.
"""

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────
import io
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether, CondPageBreak,
    HRFlowable, ListFlowable, ListItem
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF


# ─────────────────────────────────────────────
# COLOR PALETTE
# ─────────────────────────────────────────────
C_PRIMARY   = colors.HexColor("#0F172A")   # Deep navy
C_SECONDARY = colors.HexColor("#2563EB")   # Blue
C_SUCCESS   = colors.HexColor("#22C55E")   # Green
C_WARNING   = colors.HexColor("#F59E0B")   # Amber
C_DANGER    = colors.HexColor("#EF4444")   # Red
C_LIGHT     = colors.HexColor("#F8FAFC")   # Near-white
C_MUTED     = colors.HexColor("#94A3B8")   # Slate
C_BORDER    = colors.HexColor("#E2E8F0")   # Light border
C_CARD_BG   = colors.HexColor("#1E293B")   # Dark card
C_TEXT      = colors.HexColor("#1E293B")   # Body text
C_WHITE     = colors.white
C_ACCENT    = colors.HexColor("#7C3AED")   # Purple accent
C_INFO      = colors.HexColor("#0EA5E9")   # Sky blue

# Priority colours
PRIORITY_COLORS = {
    "High":   C_DANGER,
    "Medium": C_WARNING,
    "Low":    C_SUCCESS,
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


# ─────────────────────────────────────────────
# CUSTOM FLOWABLES
# ─────────────────────────────────────────────

class ColorRect(Flowable):
    """A filled rectangle with optional rounded corners and a label."""

    def __init__(self, width, height, fill_color, label="", label_color=colors.white,
                 label_size=10, radius=4):
        super().__init__()
        self.width = width
        self.height = height
        self.fill_color = fill_color
        self.label = label
        self.label_color = label_color
        self.label_size = label_size
        self.radius = radius

    def draw(self):
        self.canv.saveState()
        self.canv.setFillColor(self.fill_color)
        self.canv.roundRect(0, 0, self.width, self.height, self.radius, fill=1, stroke=0)
        if self.label:
            self.canv.setFillColor(self.label_color)
            self.canv.setFont("Helvetica-Bold", self.label_size)
            self.canv.drawCentredString(self.width / 2, self.height / 2 - self.label_size / 3,
                                        self.label)
        self.canv.restoreState()

    def wrap(self, *args):
        return self.width, self.height


class KPICard(Flowable):
    """
    A KPI card with title, value, subtitle, and a coloured accent bar on the left.
    """

    def __init__(self, title, value, subtitle="", accent_color=None, width=80 * mm, height=28 * mm):
        super().__init__()
        self.title = title
        self.value = value
        self.subtitle = subtitle
        self.accent_color = accent_color or C_SECONDARY
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.saveState()

        # Card background
        c.setFillColor(C_LIGHT)
        c.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)

        # Accent bar (left side)
        c.setFillColor(self.accent_color)
        c.rect(0, 0, 5, self.height, fill=1, stroke=0)

        # Title
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica", 7)
        c.drawString(10, self.height - 10, self.title.upper())

        # Value
        c.setFillColor(C_PRIMARY)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(10, self.height - 26, str(self.value))

        # Subtitle
        if self.subtitle:
            c.setFillColor(C_MUTED)
            c.setFont("Helvetica", 7)
            c.drawString(10, 5, self.subtitle)

        c.restoreState()

    def wrap(self, *args):
        return self.width, self.height


class ScoreBadge(Flowable):
    """Large circular score badge for the cover page."""

    def __init__(self, score, grade, color=None, size=110):
        super().__init__()
        self.score = score
        self.grade = grade
        self.color = color or C_SECONDARY
        self.size = size

    def draw(self):
        c = self.canv
        c.saveState()
        r = self.size / 2

        # Outer ring
        c.setStrokeColor(self.color)
        c.setLineWidth(6)
        c.setFillColor(C_CARD_BG)
        c.circle(r, r, r - 3, fill=1, stroke=1)

        # Score text
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 34)
        c.drawCentredString(r, r + 4, str(self.score))

        # Grade text
        c.setFillColor(self.color)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(r, r - 20, self.grade)

        c.restoreState()

    def wrap(self, *args):
        return self.size, self.size


class SectionDivider(Flowable):
    """A thin horizontal rule with a label."""

    def __init__(self, label, width, color=None):
        super().__init__()
        self.label = label
        self.width = width
        self.color = color or C_SECONDARY
        self.height = 14

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(self.color)
        c.setLineWidth(0.5)
        c.line(0, 7, self.width, 7)
        c.setFillColor(self.color)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(0, 0, self.label.upper())
        c.restoreState()

    def wrap(self, *args):
        return self.width, self.height


# ─────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────

def build_styles():
    """Build and return a dictionary of ParagraphStyles."""
    base = getSampleStyleSheet()

    styles = {
        # Cover
        "cover_site":   ParagraphStyle("cover_site",   fontName="Helvetica-Bold",
                                       fontSize=28, textColor=C_WHITE,
                                       alignment=TA_CENTER, spaceAfter=6),
        "cover_url":    ParagraphStyle("cover_url",    fontName="Helvetica",
                                       fontSize=12, textColor=C_INFO,
                                       alignment=TA_CENTER, spaceAfter=4),
        "cover_date":   ParagraphStyle("cover_date",   fontName="Helvetica",
                                       fontSize=10, textColor=C_MUTED,
                                       alignment=TA_CENTER, spaceAfter=4),
        "cover_label":  ParagraphStyle("cover_label",  fontName="Helvetica-Bold",
                                       fontSize=11, textColor=C_MUTED,
                                       alignment=TA_CENTER, spaceAfter=2),
        # Section headings
        "h1":           ParagraphStyle("h1",           fontName="Helvetica-Bold",
                                       fontSize=18, textColor=C_PRIMARY,
                                       spaceBefore=6, spaceAfter=6,
                                       borderPad=4),
        "h2":           ParagraphStyle("h2",           fontName="Helvetica-Bold",
                                       fontSize=13, textColor=C_SECONDARY,
                                       spaceBefore=8, spaceAfter=4),
        "h3":           ParagraphStyle("h3",           fontName="Helvetica-Bold",
                                       fontSize=10, textColor=C_PRIMARY,
                                       spaceBefore=6, spaceAfter=3),
        # Body text
        "body":         ParagraphStyle("body",         fontName="Helvetica",
                                       fontSize=9, textColor=C_TEXT,
                                       leading=14, spaceAfter=4),
        "body_sm":      ParagraphStyle("body_sm",      fontName="Helvetica",
                                       fontSize=8, textColor=C_TEXT,
                                       leading=12, spaceAfter=3),
        "body_justify": ParagraphStyle("body_justify", fontName="Helvetica",
                                       fontSize=9, textColor=C_TEXT,
                                       leading=14, alignment=TA_JUSTIFY,
                                       spaceAfter=4),
        "muted":        ParagraphStyle("muted",        fontName="Helvetica",
                                       fontSize=8, textColor=C_MUTED,
                                       leading=12, spaceAfter=2),
        # Table cells
        "cell":         ParagraphStyle("cell",         fontName="Helvetica",
                                       fontSize=8, textColor=C_TEXT, leading=11),
        "cell_bold":    ParagraphStyle("cell_bold",    fontName="Helvetica-Bold",
                                       fontSize=8, textColor=C_TEXT, leading=11),
        "cell_header":  ParagraphStyle("cell_header",  fontName="Helvetica-Bold",
                                       fontSize=8, textColor=C_WHITE, leading=11,
                                       alignment=TA_CENTER),
        # TOC
        "toc_title":    ParagraphStyle("toc_title",    fontName="Helvetica-Bold",
                                       fontSize=20, textColor=C_PRIMARY,
                                       spaceAfter=12),
        "toc_item":     ParagraphStyle("toc_item",     fontName="Helvetica",
                                       fontSize=10, textColor=C_TEXT,
                                       leading=18),
        "toc_sub":      ParagraphStyle("toc_sub",      fontName="Helvetica",
                                       fontSize=9, textColor=C_MUTED,
                                       leading=15, leftIndent=12),
        # Verdict
        "verdict_title":ParagraphStyle("verdict_title",fontName="Helvetica-Bold",
                                       fontSize=14, textColor=C_WHITE,
                                       alignment=TA_CENTER, spaceAfter=2),
        "verdict_text": ParagraphStyle("verdict_text", fontName="Helvetica",
                                       fontSize=9, textColor=C_WHITE,
                                       alignment=TA_CENTER, leading=14),
        # Search preview
        "sp_title":     ParagraphStyle("sp_title",     fontName="Helvetica-Bold",
                                       fontSize=10, textColor=C_SECONDARY,
                                       spaceAfter=1),
        "sp_url":       ParagraphStyle("sp_url",       fontName="Helvetica",
                                       fontSize=8, textColor=C_SUCCESS,
                                       spaceAfter=2),
        "sp_desc":      ParagraphStyle("sp_desc",      fontName="Helvetica",
                                       fontSize=8, textColor=C_TEXT, leading=12),
    }
    return styles


# ─────────────────────────────────────────────
# HELPER: SCORE → COLOR
# ─────────────────────────────────────────────

def score_color(score):
    """Return a color based on a 0-100 score."""
    if score >= 80:
        return C_SUCCESS
    elif score >= 60:
        return C_WARNING
    else:
        return C_DANGER


def score_grade(score):
    """Return a letter grade for a 0-100 score."""
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    else:
        return "F"


def score_status(score):
    """Return a status string for a 0-100 score."""
    if score >= 80:
        return "EXCELLENT"
    elif score >= 65:
        return "GOOD"
    elif score >= 50:
        return "NEEDS WORK"
    else:
        return "CRITICAL"


# ─────────────────────────────────────────────
# TABLE STYLE HELPERS
# ─────────────────────────────────────────────

def standard_table_style(header_color=None):
    """Return a standard TableStyle for report tables."""
    hc = header_color or C_PRIMARY
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  hc),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8),
        ("ALIGN",         (0, 0), (-1, 0),  "CENTER"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, C_LIGHT]),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("TEXTCOLOR",     (0, 1), (-1, -1), C_TEXT),
        ("GRID",          (0, 0), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0, 0), (-1, 0),  [hc]),
    ])


def verdict_box_style(verdict_color):
    """Return a TableStyle for verdict boxes."""
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), verdict_color),
        ("TEXTCOLOR",     (0, 0), (-1, -1), colors.white),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS",(0, 0), (-1, -1), [4, 4, 4, 4]),
    ])


# ─────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────

def build_bar_chart(category_scores, width=380, height=160):
    """
    Build a vertical bar chart from a dict of {category: score}.
    Returns a Drawing flowable.
    """
    d = Drawing(width, height)

    bc = VerticalBarChart()
    bc.x = 40
    bc.y = 20
    bc.width = width - 60
    bc.height = height - 40
    bc.data = [list(category_scores.values())]
    bc.strokeColor = None
    bc.groupSpacing = 15
    bc.bars[0].fillColor = C_SECONDARY
    bc.bars[0].strokeColor = None

    # Colour bars by value
    for i, v in enumerate(category_scores.values()):
        bc.bars[0, i].fillColor = score_color(v)

    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 100
    bc.valueAxis.valueStep = 20
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.labels.fillColor = C_MUTED

    bc.categoryAxis.categoryNames = list(category_scores.keys())
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.fillColor = C_TEXT
    bc.categoryAxis.labels.angle = 0
    bc.categoryAxis.labels.dy = -8

    d.add(bc)
    return d


def build_pie_chart(category_scores, width=200, height=180):
    """
    Build a pie chart from a dict of {category: score}.
    Returns a Drawing flowable.
    """
    d = Drawing(width, height)

    pie = Pie()
    pie.x = 10
    pie.y = 10
    pie.width = 120
    pie.height = 120
    pie.data = list(category_scores.values())
    pie.labels = list(category_scores.keys())
    pie.sideLabels = True
    pie.sideLabelsOffset = 0.1

    chart_colors = [C_SECONDARY, C_SUCCESS, C_WARNING, C_ACCENT, C_INFO, C_DANGER]
    for i in range(len(pie.data)):
        pie.slices[i].fillColor = chart_colors[i % len(chart_colors)]
        pie.slices[i].strokeColor = colors.white
        pie.slices[i].strokeWidth = 1
        pie.slices[i].labelRadius = 1.25
        pie.slices[i].fontName = "Helvetica"
        pie.slices[i].fontSize = 7

    d.add(pie)
    return d


# ─────────────────────────────────────────────
# SECTION BUILDERS
# ─────────────────────────────────────────────

# ── COVER PAGE ──────────────────────────────

def build_cover_page(story, report_data, styles):
    """
    Build the cover page (Page 1).
    Full-page dark background with score badge.
    Always ends with PageBreak.
    """
    site_name  = report_data.get("site_name",  "Website Audit")
    site_url   = report_data.get("site_url",   "https://example.com")
    audit_date = report_data.get("audit_date", datetime.now().strftime("%B %d, %Y"))
    overall    = report_data.get("overall_score", 0)
    grade      = score_grade(overall)
    status     = score_status(overall)
    color      = score_color(overall)

    # ── Full dark background banner ──
    banner_w = PAGE_W - 2 * MARGIN
    banner_h = PAGE_H - 2 * MARGIN

    cover_elems = []

    # Top accent stripe
    cover_elems.append(ColorRect(banner_w, 6, C_SECONDARY))
    cover_elems.append(Spacer(1, 16))

    # Report type label
    cover_elems.append(Paragraph(
        '<font color="#94A3B8">AEO AUDIT REPORT</font>',
        ParagraphStyle("cl", fontName="Helvetica", fontSize=9,
                       textColor=C_MUTED, alignment=TA_CENTER)))
    cover_elems.append(Spacer(1, 8))

    # Site name
    cover_elems.append(Paragraph(site_name, styles["cover_site"]))
    cover_elems.append(Paragraph(site_url,  styles["cover_url"]))
    cover_elems.append(Spacer(1, 4))
    cover_elems.append(Paragraph(f"Audit Date: {audit_date}", styles["cover_date"]))
    cover_elems.append(Spacer(1, 24))

    # Score badge (centered via a 1-col table)
    badge = ScoreBadge(overall, grade, color=color, size=120)
    badge_table = Table([[badge]], colWidths=[banner_w])
    badge_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    cover_elems.append(badge_table)
    cover_elems.append(Spacer(1, 16))

    # Status badge
    status_color = color
    cover_elems.append(Table(
        [[Paragraph(status, ParagraphStyle("st", fontName="Helvetica-Bold",
                                           fontSize=12, textColor=colors.white,
                                           alignment=TA_CENTER))]],
        colWidths=[120],
        style=TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), status_color),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 18),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 18),
        ]),
        hAlign="CENTER"
    ))
    cover_elems.append(Spacer(1, 32))

    # Score description line
    cover_elems.append(Paragraph(
        f"Overall AEO Score: <b>{overall}/100</b> — Grade: <b>{grade}</b>",
        ParagraphStyle("sc", fontName="Helvetica", fontSize=11,
                       textColor=C_MUTED, alignment=TA_CENTER)))

    cover_elems.append(Spacer(1, 36))

    # Confidential footer
    cover_elems.append(HRFlowable(width=banner_w, thickness=0.5,
                                   color=C_MUTED, spaceAfter=6))
    cover_elems.append(Paragraph(
        "CONFIDENTIAL — For Internal Use Only",
        ParagraphStyle("cf", fontName="Helvetica", fontSize=7,
                       textColor=C_MUTED, alignment=TA_CENTER)))

    story.extend(cover_elems)
    story.append(PageBreak())


# ── TABLE OF CONTENTS ───────────────────────

def build_toc(story, report_data, styles):
    """
    Build the Table of Contents (Page 2).
    Dynamic list of sections with page estimates.
    Always ends with PageBreak.
    """
    toc_entries = report_data.get("toc_entries", [
        ("1", "Executive Dashboard",         "3"),
        ("2", "Content Analysis",            "5"),
        ("3", "Technical Analysis",          "6"),
        ("4", "Brand Authority",             "7"),
        ("5", "AEO Readiness",               "8"),
        ("6", "Recommendations",             "9"),
        ("7", "Final Verdict",               "10"),
        ("8", "Action Plan",                 "11"),
        ("9", "Appendix",                    "12"),
    ])

    story.append(Paragraph("Table of Contents", styles["toc_title"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=12))

    for num, section, page in toc_entries:
        dot_leader = "." * max(3, 90 - len(section) - len(page) - 4)
        story.append(Paragraph(
            f"<b>{num}.</b> &nbsp; {section} "
            f'<font color="#94A3B8">{dot_leader}</font> '
            f"<b>{page}</b>",
            styles["toc_item"]
        ))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Note: Page numbers are approximate and may vary based on content volume.",
        styles["muted"]
    ))
    story.append(PageBreak())


# ── EXECUTIVE DASHBOARD ──────────────────────

def build_executive_dashboard(story, report_data, styles):
    """
    Build the Executive Dashboard (Pages 3-4).
    KPI cards, bar chart, pie chart, summary table, search preview.
    """
    story.append(Paragraph("Executive Dashboard", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    # ── KPI Cards ──
    overall  = report_data.get("overall_score", 0)
    scores   = report_data.get("category_scores", {})
    content  = scores.get("Content",   0)
    tech     = scores.get("Technical", 0)
    brand    = scores.get("Brand",     0)

    card_w = (PAGE_W - 2 * MARGIN - 3 * 6 * mm) / 4
    card_h = 28 * mm

    kpi_cards = [
        KPICard("Overall Score",   f"{overall}",  score_status(overall),   score_color(overall),   card_w, card_h),
        KPICard("Content Score",   f"{content}",  score_grade(content),    score_color(content),   card_w, card_h),
        KPICard("Technical Score", f"{tech}",     score_grade(tech),       score_color(tech),      card_w, card_h),
        KPICard("Brand Score",     f"{brand}",    score_grade(brand),      score_color(brand),     card_w, card_h),
    ]

    kpi_row = Table([[c for c in kpi_cards]],
                    colWidths=[card_w] * 4)
    kpi_row.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 3 * mm),
    ]))

    story.append(KeepTogether([kpi_row]))
    story.append(Spacer(1, 12))

    # ── Charts Row ──
    chart_title_bar = Paragraph("Category Score Breakdown", styles["h2"])
    chart_title_pie = Paragraph("Score Distribution",       styles["h2"])

    bar_chart = build_bar_chart(scores, width=340, height=150)
    pie_chart = build_pie_chart(scores, width=190, height=150)

    chart_table = Table(
        [[chart_title_bar, chart_title_pie],
         [bar_chart,       pie_chart]],
        colWidths=[355, 205]
    )
    chart_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    story.append(KeepTogether([chart_table]))
    story.append(Spacer(1, 12))

    # ── Executive KPI Summary Table ──
    story.append(CondPageBreak(60))
    kpi_summary_data = [
        [Paragraph("Category",          styles["cell_header"]),
         Paragraph("Score",             styles["cell_header"]),
         Paragraph("Grade",             styles["cell_header"]),
         Paragraph("Status",            styles["cell_header"]),
         Paragraph("Priority",          styles["cell_header"])],
    ]
    for cat, sc in scores.items():
        kpi_summary_data.append([
            Paragraph(cat,              styles["cell_bold"]),
            Paragraph(f"{sc}/100",      styles["cell"]),
            Paragraph(score_grade(sc),  styles["cell"]),
            Paragraph(score_status(sc), styles["cell"]),
            Paragraph("High" if sc < 50 else ("Medium" if sc < 70 else "Low"),
                      styles["cell"]),
        ])

    kpi_tbl = Table(kpi_summary_data,
                    colWidths=[130, 60, 60, 90, 70])
    kpi_tbl.setStyle(standard_table_style())

    story.append(KeepTogether([
        Paragraph("Executive KPI Summary", styles["h2"]),
        kpi_tbl
    ]))
    story.append(Spacer(1, 12))

    # ── Search Preview ──
    _build_search_preview(story, report_data, styles)

    # ── Executive Summary ──
    story.append(Spacer(1, 8))
    exec_summary = report_data.get("executive_summary", "")
    if exec_summary:
        story.append(KeepTogether([
            Paragraph("Executive Summary", styles["h2"]),
            Paragraph(exec_summary, styles["body_justify"])
        ]))


def _build_search_preview(story, report_data, styles):
    """Render a Google-style search result preview card."""
    preview = report_data.get("search_preview", {})
    if not preview:
        return

    title = preview.get("title", "")
    url   = preview.get("url", "")
    desc  = preview.get("description", "")

    if not title and not url:
        return

    inner = [
        Paragraph("Search Preview",                            styles["h2"]),
        Paragraph("How this site may appear in AI answers:",   styles["muted"]),
        Spacer(1, 6),
    ]

    preview_content = []
    if title:
        preview_content.append(Paragraph(title, styles["sp_title"]))
    if url:
        preview_content.append(Paragraph(url,   styles["sp_url"]))
    if desc:
        preview_content.append(Paragraph(desc,  styles["sp_desc"]))

    preview_tbl = Table(
        [[ [Spacer(1, 4)] + preview_content + [Spacer(1, 4)] ]],
        colWidths=[PAGE_W - 2 * MARGIN - 24]
    )
    preview_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX",           (0, 0), (-1, -1), 1, C_BORDER),
        ("LINEAFTER",     (0, 0), (0, -1),  4, C_SECONDARY),
    ]))

    inner.append(preview_tbl)
    story.append(KeepTogether(inner))


# ── STRENGTHS / WEAKNESSES BUILDER ──────────

def build_sw_section(story, strengths, weaknesses, styles):
    """
    Generic builder for Strengths and Weaknesses.
    strengths / weaknesses = list of strings.
    """
    if not strengths and not weaknesses:
        return

    rows = []
    max_len = max(len(strengths), len(weaknesses))

    for i in range(max_len):
        s_text = _xml_escape(strengths[i])  if i < len(strengths)  else ""
        w_text = _xml_escape(weaknesses[i]) if i < len(weaknesses) else ""

        s_cell = Paragraph(
            f'<font color="#22C55E">&#9679;</font> {s_text}' if s_text else "",
            styles["cell"]
        )
        w_cell = Paragraph(
            f'<font color="#EF4444">&#9679;</font> {w_text}' if w_text else "",
            styles["cell"]
        )
        rows.append([s_cell, w_cell])

    col_w = (PAGE_W - 2 * MARGIN) / 2

    header = [
        [Paragraph("Strengths",  styles["cell_header"]),
         Paragraph("Weaknesses", styles["cell_header"])],
    ]

    tbl = Table(header + rows, colWidths=[col_w, col_w])
    tbl.setStyle(standard_table_style(C_PRIMARY))
    story.append(tbl)
    story.append(Spacer(1, 8))


# ── VERDICT BUILDER ──────────────────────────

def build_verdict(story, title, verdict_text, score, styles):
    """
    Build a coloured verdict box that always stays together.
    """
    vcolor = score_color(score)
    vgrade = score_grade(score)

    verdict_elems = [
        Paragraph(title, styles["h2"]),
        Spacer(1, 4),
        Table(
            [[Paragraph(f"{score_status(score)} — Grade {vgrade}",
                        styles["verdict_title"])],
             [Paragraph(verdict_text, styles["verdict_text"])]],
            colWidths=[PAGE_W - 2 * MARGIN - 2],
            style=TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), vcolor),
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING",   (0, 0), (-1, -1), 14),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
                ("ROWBACKGROUNDS",(0, 0), (-1, -1), [vcolor]),
            ])
        ),
        Spacer(1, 10),
    ]
    story.append(KeepTogether(verdict_elems))


# ── GENERIC METRICS TABLE ────────────────────

def build_metrics_table(story, title, metrics, styles, header_color=None):
    """
    Build a labelled metrics table.
    metrics = list of (label, value, notes) tuples.
    """
    if not metrics:
        return

    hc = header_color or C_SECONDARY
    rows = [
        [Paragraph("Metric",      styles["cell_header"]),
         Paragraph("Value",       styles["cell_header"]),
         Paragraph("Notes",       styles["cell_header"])],
    ]
    for label, value, note in metrics:
        rows.append([
            Paragraph(str(label), styles["cell_bold"]),
            Paragraph(str(value), styles["cell"]),
            Paragraph(str(note),  styles["cell"]),
        ])

    tbl = Table(rows, colWidths=[160, 80, 220])
    tbl.setStyle(standard_table_style(hc))

    story.append(KeepTogether([
        Paragraph(title, styles["h2"]),
        tbl,
        Spacer(1, 8)
    ]))


# ── CONTENT ANALYSIS ────────────────────────

def build_content_analysis(story, report_data, styles):
    """Build the Content Analysis section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("Content Analysis", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    content = report_data.get("content_analysis", {})

    # ── Content Metrics ──
    metrics = content.get("metrics", [])
    build_metrics_table(story, "Content Metrics", metrics, styles, C_SECONDARY)

    # ── Strengths & Weaknesses ──
    story.append(CondPageBreak(50))
    story.append(Paragraph("Content Strengths & Weaknesses", styles["h2"]))
    build_sw_section(story,
                     content.get("strengths", []),
                     content.get("weaknesses", []),
                     styles)

    # ── Verdict ──
    story.append(CondPageBreak(60))
    build_verdict(story, "Content Verdict",
                  content.get("verdict_text", "No verdict available."),
                  content.get("score", 0), styles)


# ── TECHNICAL ANALYSIS ──────────────────────

def build_technical_analysis(story, report_data, styles):
    """Build the Technical Analysis section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("Technical Analysis", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    tech = report_data.get("technical_analysis", {})

    # ── Technical Metrics ──
    metrics = tech.get("metrics", [])
    build_metrics_table(story, "Technical Metrics", metrics, styles, C_PRIMARY)

    # ── Schema Audit ──
    story.append(CondPageBreak(70))
    schema_data = tech.get("schema_audit", [])
    if schema_data:
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["Schema Type", "Present", "Valid", "Issues"]]]
        for row in schema_data:
            present = row.get("present", False)
            valid   = row.get("valid",   False)
            rows.append([
                Paragraph(row.get("type",   "N/A"), styles["cell_bold"]),
                Paragraph("Yes" if present else "No",
                          ParagraphStyle("yesno", fontName="Helvetica-Bold",
                                         fontSize=8,
                                         textColor=C_SUCCESS if present else C_DANGER)),
                Paragraph("Yes" if valid else "N/A",
                          ParagraphStyle("yesno2", fontName="Helvetica-Bold",
                                         fontSize=8,
                                         textColor=C_SUCCESS if valid else C_WARNING)),
                Paragraph(row.get("issues", "None"), styles["cell"]),
            ])

        schema_tbl = Table(rows, colWidths=[130, 60, 60, 210])
        schema_tbl.setStyle(standard_table_style(C_ACCENT))

        story.append(KeepTogether([
            Paragraph("Schema Markup Audit", styles["h2"]),
            schema_tbl,
            Spacer(1, 8)
        ]))

    # ── Metadata Audit ──
    story.append(CondPageBreak(50))
    meta_data = tech.get("metadata_audit", [])
    if meta_data:
        build_metrics_table(story, "Metadata Audit", meta_data, styles, C_INFO)

    # ── Crawlability Audit ──
    story.append(CondPageBreak(50))
    crawl_data = tech.get("crawlability_audit", [])
    if crawl_data:
        build_metrics_table(story, "Crawlability Audit", crawl_data, styles, C_WARNING)

    # ── Strengths & Weaknesses ──
    story.append(CondPageBreak(50))
    story.append(Paragraph("Technical Strengths & Weaknesses", styles["h2"]))
    build_sw_section(story,
                     tech.get("strengths", []),
                     tech.get("weaknesses", []),
                     styles)

    # ── Verdict ──
    story.append(CondPageBreak(60))
    build_verdict(story, "Technical Verdict",
                  tech.get("verdict_text", "No verdict available."),
                  tech.get("score", 0), styles)


# ── BRAND AUTHORITY ──────────────────────────

def build_brand_authority(story, report_data, styles):
    """Build the Brand Authority section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("Brand Authority", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    brand = report_data.get("brand_authority", {})

    # ── Brand Metrics ──
    metrics = brand.get("metrics", [])
    build_metrics_table(story, "Brand Metrics", metrics, styles, C_ACCENT)

    # ── Contact Signals ──
    story.append(CondPageBreak(50))
    _build_signal_table(story, "Contact Signals",
                        brand.get("contact_signals", []), styles)

    # ── Trust Signals ──
    story.append(CondPageBreak(50))
    _build_signal_table(story, "Trust Signals",
                        brand.get("trust_signals", []), styles)

    # ── Authority Signals ──
    story.append(CondPageBreak(50))
    _build_signal_table(story, "Authority Signals",
                        brand.get("authority_signals", []), styles)

    # ── Strengths & Weaknesses ──
    story.append(CondPageBreak(50))
    story.append(Paragraph("Brand Strengths & Weaknesses", styles["h2"]))
    build_sw_section(story,
                     brand.get("strengths", []),
                     brand.get("weaknesses", []),
                     styles)

    # ── Verdict ──
    story.append(CondPageBreak(60))
    build_verdict(story, "Brand Verdict",
                  brand.get("verdict_text", "No verdict available."),
                  brand.get("score", 0), styles)


def _build_signal_table(story, title, signals, styles):
    """
    Build a two-column signal table (signal, status).
    signals = list of {signal, status, notes} dicts.
    """
    if not signals:
        return

    rows = [[Paragraph("Signal",  styles["cell_header"]),
             Paragraph("Status",  styles["cell_header"]),
             Paragraph("Notes",   styles["cell_header"])]]

    for s in signals:
        status = s.get("status", "Unknown")
        status_color = (C_SUCCESS if status in ("Present", "Yes", "Active", "Verified")
                        else C_DANGER if status in ("Missing", "No", "Inactive")
                        else C_WARNING)
        rows.append([
            Paragraph(s.get("signal", ""), styles["cell_bold"]),
            Paragraph(status,
                      ParagraphStyle("sig", fontName="Helvetica-Bold",
                                     fontSize=8, textColor=status_color)),
            Paragraph(s.get("notes", ""), styles["cell"]),
        ])

    tbl = Table(rows, colWidths=[160, 80, 220])
    tbl.setStyle(standard_table_style(C_PRIMARY))

    story.append(KeepTogether([
        Paragraph(title, styles["h2"]),
        tbl,
        Spacer(1, 8)
    ]))


# ── AEO READINESS ────────────────────────────

def build_aeo_readiness(story, report_data, styles):
    """Build the AEO Readiness section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("AEO Readiness", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    aeo = report_data.get("aeo_readiness", {})

    # ── Platform Readiness Table ──
    platforms = aeo.get("platforms", [])
    if platforms:
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["Platform", "Readiness Score", "Status", "Key Gaps"]]]
        for p in platforms:
            sc = p.get("score", 0)
            rows.append([
                Paragraph(p.get("name", ""),  styles["cell_bold"]),
                Paragraph(f"{sc}/100",         styles["cell"]),
                Paragraph(score_status(sc),
                          ParagraphStyle("rs", fontName="Helvetica-Bold",
                                         fontSize=8, textColor=score_color(sc))),
                Paragraph(p.get("key_gaps", ""), styles["cell"]),
            ])

        plat_tbl = Table(rows, colWidths=[130, 80, 90, 160])
        plat_tbl.setStyle(standard_table_style(C_SECONDARY))

        story.append(KeepTogether([
            Paragraph("Platform Readiness Overview", styles["h2"]),
            plat_tbl,
            Spacer(1, 10)
        ]))

    # ── Individual platform sections ──
    for platform in platforms:
        story.append(CondPageBreak(50))
        details = platform.get("details", [])
        if details:
            build_metrics_table(story,
                                f"{platform.get('name', '')} Readiness Details",
                                details, styles, C_INFO)

    # ── Strengths & Weaknesses ──
    story.append(CondPageBreak(50))
    story.append(Paragraph("AEO Strengths & Weaknesses", styles["h2"]))
    build_sw_section(story,
                     aeo.get("strengths", []),
                     aeo.get("weaknesses", []),
                     styles)

    # ── Verdict ──
    story.append(CondPageBreak(60))
    build_verdict(story, "AEO Verdict",
                  aeo.get("verdict_text", "No verdict available."),
                  aeo.get("score", 0), styles)


# ── RECOMMENDATIONS ──────────────────────────

def build_recommendations(story, report_data, styles):
    """Build the Recommendations section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("Recommendations", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    recs = report_data.get("recommendations", [])
    if not recs:
        story.append(Paragraph("No recommendations available.", styles["body"]))
        return

    # Legend
    legend_items = [
        Paragraph('<font color="#EF4444">&#9632;</font> High Priority',   styles["body_sm"]),
        Paragraph('<font color="#F59E0B">&#9632;</font> Medium Priority', styles["body_sm"]),
        Paragraph('<font color="#22C55E">&#9632;</font> Low Priority',    styles["body_sm"]),
    ]
    legend_tbl = Table([[legend_items[0], legend_items[1], legend_items[2]]],
                       colWidths=[(PAGE_W - 2 * MARGIN) / 3] * 3)
    legend_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
    ]))
    story.append(legend_tbl)

    # Build table rows
    headers = ["#", "Recommendation", "Priority", "Impact", "Effort", "Expected Outcome"]
    col_widths = [18, 165, 52, 45, 45, 130]

    header_row = [Paragraph(h, styles["cell_header"]) for h in headers]
    rows = [header_row]

    for i, rec in enumerate(recs, 1):
    # Normalize: handle str, None, or any non-dict value
        if not isinstance(rec, dict):
            rec = {"recommendation": str(rec), "priority": "Medium",
               "impact": "N/A", "effort": "N/A", "outcome": "N/A"}
        priority = rec.get("priority") or "Medium"
        p_color  = PRIORITY_COLORS.get(priority, C_WARNING)
        rows.append([
            Paragraph(str(i), styles["cell"]),
            Paragraph(rec.get("recommendation", ""), styles["cell"]),
            Paragraph(priority,
                      ParagraphStyle("pr", fontName="Helvetica-Bold",
                                     fontSize=8, textColor=p_color)),
            Paragraph(rec.get("impact", ""),   styles["cell"]),
            Paragraph(rec.get("effort", ""),   styles["cell"]),
            Paragraph(rec.get("outcome", ""),  styles["cell"]),
        ])

    rec_tbl = Table(rows, colWidths=col_widths)
    rec_tbl.setStyle(standard_table_style(C_PRIMARY))

    # Keep header + first row together to avoid orphaned header
    story.append(KeepTogether([Table(rows[:2], colWidths=col_widths,
                                     style=standard_table_style(C_PRIMARY))]))
    if len(rows) > 2:
        rest_tbl = Table(rows[2:], colWidths=col_widths)
        rest_tbl.setStyle(TableStyle([
            ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.white, C_LIGHT]),
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("TEXTCOLOR",     (0, 0), (-1, -1), C_TEXT),
            ("GRID",          (0, 0), (-1, -1), 0.4, C_BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(rest_tbl)


# ── FINAL VERDICT ────────────────────────────

def build_final_verdict(story, report_data, styles):
    """Build the Final Verdict section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("Final Verdict", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    overall = report_data.get("overall_score", 0)
    vcolor  = score_color(overall)
    grade   = score_grade(overall)
    status  = score_status(overall)

    # ── Large verdict box ──
    verdict_title   = report_data.get("final_verdict_title",   f"{status} — Grade {grade}")
    verdict_summary = report_data.get("final_verdict_summary", "")

    large_verdict = Table(
        [[Paragraph(verdict_title,   styles["verdict_title"])],
         [Paragraph(f"Overall Score: {overall}/100", styles["verdict_text"])],
         [Spacer(1, 6)],
         [Paragraph(verdict_summary, styles["verdict_text"])]],
        colWidths=[PAGE_W - 2 * MARGIN - 2],
        style=TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), vcolor),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("LEFTPADDING",   (0, 0), (-1, -1), 18),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 18),
        ])
    )
    story.append(KeepTogether([large_verdict]))
    story.append(Spacer(1, 12))

    # ── Category Score Summary ──
    scores = report_data.get("category_scores", {})
    if scores:
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["Category", "Score", "Grade", "Status"]]]
        for cat, sc in scores.items():
            rows.append([
                Paragraph(cat,              styles["cell_bold"]),
                Paragraph(f"{sc}/100",      styles["cell"]),
                Paragraph(score_grade(sc),  styles["cell"]),
                Paragraph(score_status(sc),
                          ParagraphStyle("fvs", fontName="Helvetica-Bold",
                                         fontSize=8, textColor=score_color(sc))),
            ])

        score_tbl = Table(rows, colWidths=[160, 80, 80, 140])
        score_tbl.setStyle(standard_table_style(C_PRIMARY))

        story.append(KeepTogether([
            Paragraph("Category Score Summary", styles["h2"]),
            score_tbl,
            Spacer(1, 10)
        ]))

    # ── AEO Readiness Matrix ──
    aeo_matrix = report_data.get("aeo_readiness_matrix", [])
    if aeo_matrix:
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["Platform", "Ready?", "Score", "Notes"]]]
        for item in aeo_matrix:
            sc = item.get("score", 0)
            rows.append([
                Paragraph(item.get("platform", ""),  styles["cell_bold"]),
                Paragraph("Yes" if sc >= 60 else "No",
                          ParagraphStyle("m", fontName="Helvetica-Bold",
                                         fontSize=8,
                                         textColor=C_SUCCESS if sc >= 60 else C_DANGER)),
                Paragraph(f"{sc}/100",                styles["cell"]),
                Paragraph(item.get("notes", ""),      styles["cell"]),
            ])

        matrix_tbl = Table(rows, colWidths=[130, 60, 60, 210])
        matrix_tbl.setStyle(standard_table_style(C_ACCENT))

        story.append(KeepTogether([
            Paragraph("AEO Readiness Matrix", styles["h2"]),
            matrix_tbl,
            Spacer(1, 10)
        ]))

    # ── Executive Conclusion ──
    conclusion = report_data.get("executive_conclusion", "")
    if conclusion:
        story.append(CondPageBreak(50))
        story.append(KeepTogether([
            Paragraph("Executive Conclusion", styles["h2"]),
            Paragraph(conclusion, styles["body_justify"])
        ]))


# ── ACTION PLAN ──────────────────────────────

def build_action_plan(story, report_data, styles):
    """Build the Action Plan section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("Action Plan", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    action_plan = report_data.get("action_plan", {})

    def _build_action_table(title, actions, accent_color, story, styles):
        if not actions:
            return
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["#", "Action", "Category", "Expected Impact"]]]
        for i, a in enumerate(actions, 1):
            rows.append([
                Paragraph(str(i),               styles["cell"]),
                Paragraph(a.get("action", ""),  styles["cell_bold"]),
                Paragraph(a.get("category", ""),styles["cell"]),
                Paragraph(a.get("impact", ""),  styles["cell"]),
            ])

        tbl = Table(rows, colWidths=[25, 210, 120, 105])
        tbl.setStyle(standard_table_style(accent_color))

        story.append(KeepTogether([
            Paragraph(title, styles["h2"]),
            tbl,
            Spacer(1, 10)
        ]))

    _build_action_table("Top 5 Actions This Week",
                        action_plan.get("this_week", [])[:5],
                        C_DANGER, story, styles)

    story.append(CondPageBreak(60))
    _build_action_table("Top 5 Actions This Month",
                        action_plan.get("this_month", [])[:5],
                        C_WARNING, story, styles)

    story.append(CondPageBreak(60))
    _build_action_table("Long-Term Improvements",
                        action_plan.get("long_term", []),
                        C_SUCCESS, story, styles)


# ── APPENDIX ─────────────────────────────────

def build_appendix(story, report_data, styles):
    """Build the Appendix section. Always starts on new page."""
    story.append(PageBreak())
    story.append(Paragraph("Appendix", styles["h1"]))
    story.append(HRFlowable(width=PAGE_W - 2 * MARGIN, thickness=2,
                             color=C_SECONDARY, spaceAfter=10))

    appendix = report_data.get("appendix", {})

    # ── Raw Metrics ──
    raw_metrics = appendix.get("raw_metrics", [])
    if raw_metrics:
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["Metric", "Value", "Source", "Notes"]]]
        for m in raw_metrics:
            rows.append([
                Paragraph(str(m.get("metric", "")),  styles["cell_bold"]),
                Paragraph(str(m.get("value",  "")),  styles["cell"]),
                Paragraph(str(m.get("source", "")),  styles["cell"]),
                Paragraph(str(m.get("notes",  "")),  styles["cell"]),
            ])

        tbl = Table(rows, colWidths=[130, 80, 100, 150])
        tbl.setStyle(standard_table_style(C_PRIMARY))

        story.append(KeepTogether([
            Paragraph("Raw Metrics", styles["h2"]),
            tbl,
            Spacer(1, 10)
        ]))

    # ── Technical Flags ──
    flags = appendix.get("technical_flags", [])
    if flags:
        story.append(CondPageBreak(50))
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["Flag", "Severity", "Description", "Recommendation"]]]
        for f in flags:
            sev = f.get("severity", "Medium")
            sev_color = PRIORITY_COLORS.get(sev, C_WARNING)
            rows.append([
                Paragraph(f.get("flag", ""),        styles["cell_bold"]),
                Paragraph(sev,
                          ParagraphStyle("fl", fontName="Helvetica-Bold",
                                         fontSize=8, textColor=sev_color)),
                Paragraph(f.get("description", ""), styles["cell"]),
                Paragraph(f.get("recommendation", ""), styles["cell"]),
            ])

        tbl = Table(rows, colWidths=[100, 60, 170, 130])
        tbl.setStyle(standard_table_style(C_DANGER))

        story.append(KeepTogether([
            Paragraph("Technical Flags", styles["h2"]),
            tbl,
            Spacer(1, 10)
        ]))

    # ── Schema Results ──
    schema_results = appendix.get("schema_results", [])
    if schema_results:
        story.append(CondPageBreak(50))
        rows = [[Paragraph(h, styles["cell_header"])
                 for h in ["Type", "Count", "Status", "Errors"]]]
        for sr in schema_results:
            rows.append([
                Paragraph(sr.get("type",   ""), styles["cell_bold"]),
                Paragraph(str(sr.get("count", 0)), styles["cell"]),
                Paragraph(sr.get("status", ""), styles["cell"]),
                Paragraph(sr.get("errors", ""), styles["cell"]),
            ])

        tbl = Table(rows, colWidths=[130, 60, 100, 170])
        tbl.setStyle(standard_table_style(C_ACCENT))

        story.append(KeepTogether([
            Paragraph("Schema Results", styles["h2"]),
            tbl,
            Spacer(1, 10)
        ]))

    # ── Audit Metadata ──
    audit_meta = appendix.get("audit_metadata", [])
    if audit_meta:
        story.append(CondPageBreak(50))
        rows = [[Paragraph(h, styles["cell_header"]) for h in ["Key", "Value"]]]
        for key, val in audit_meta:
            rows.append([
                Paragraph(str(key), styles["cell_bold"]),
                Paragraph(str(val), styles["cell"]),
            ])

        tbl = Table(rows, colWidths=[200, 260])
        tbl.setStyle(standard_table_style(C_PRIMARY))

        story.append(KeepTogether([
            Paragraph("Audit Metadata", styles["h2"]),
            tbl,
            Spacer(1, 10)
        ]))


# ─────────────────────────────────────────────
# PAGE NUMBER CALLBACK
# ─────────────────────────────────────────────

def _add_page_number(canvas, doc):
    """Draw header and footer on every page (except the cover)."""
    canvas.saveState()
    page_num = doc.page

    if page_num == 1:
        canvas.restoreState()
        return

    # Header line
    canvas.setStrokeColor(C_SECONDARY)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_H - MARGIN + 4, PAGE_W - MARGIN, PAGE_H - MARGIN + 4)

    # Report title in header
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_MUTED)
    site_name = getattr(doc, "_site_name", "AEO Audit Report")
    canvas.drawString(MARGIN, PAGE_H - MARGIN + 7, f"AEO Audit Report — {site_name}")
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 7, "CONFIDENTIAL")

    # Footer line
    canvas.line(MARGIN, MARGIN - 4, PAGE_W - MARGIN, MARGIN - 4)

    # Page number
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 13,
                           f"Page {page_num}")
    canvas.drawString(MARGIN, MARGIN - 13,
                      f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    canvas.restoreState()


# ─────────────────────────────────────────────
# MAIN REPORT BUILDER
# ─────────────────────────────────────────────

def generate_aeo_report(report_data: dict, output_path: str = "aeo_audit_report.pdf") -> str:
    """
    Generate the full AEO Audit Report PDF.

    Parameters
    ----------
    report_data : dict
        All report content.  See SAMPLE_REPORT_DATA for the expected schema.
    output_path : str
        File path for the output PDF.

    Returns
    -------
    str
        Absolute path of the generated PDF.
    """
    styles = build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 4 * mm,
        bottomMargin=MARGIN,
        title=f"AEO Audit Report — {report_data.get('site_name', 'Website')}",
        author="AEO Audit Engine",
        subject="Answer Engine Optimization Audit",
    )
    # Attach site name so header callback can use it
    doc._site_name = report_data.get("site_name", "AEO Audit Report")

    story = []

    # ── Page 1: Cover ──
    build_cover_page(story, report_data, styles)

    # ── Page 2: TOC ──
    build_toc(story, report_data, styles)

    # ── Pages 3-4: Executive Dashboard ──
    build_executive_dashboard(story, report_data, styles)

    # ── Pages 5+: Content Analysis ──
    build_content_analysis(story, report_data, styles)

    # ── Technical Analysis ──
    build_technical_analysis(story, report_data, styles)

    # ── Brand Authority ──
    build_brand_authority(story, report_data, styles)

    # ── AEO Readiness ──
    build_aeo_readiness(story, report_data, styles)

    # ── Recommendations ──
    build_recommendations(story, report_data, styles)

    # ── Final Verdict ──
    build_final_verdict(story, report_data, styles)

    # ── Action Plan ──
    build_action_plan(story, report_data, styles)

    # ── Appendix ──
    build_appendix(story, report_data, styles)

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return output_path


# ─────────────────────────────────────────────
# SAMPLE REPORT DATA (demonstrates full schema)
# ─────────────────────────────────────────────

SAMPLE_REPORT_DATA = {
    # ── Identity ──
    "site_name":    "TechNova Solutions",
    "site_url":     "https://www.technovasolutions.com",
    "audit_date":   "June 13, 2025",

    # ── Scores ──
    "overall_score": 67,
    "category_scores": {
        "Content":   72,
        "Technical": 58,
        "Brand":     63,
        "AEO":       74,
    },

    # ── TOC ── (optional; auto-generated default if omitted)
    "toc_entries": [
        ("1", "Executive Dashboard",     "3"),
        ("2", "Content Analysis",        "5"),
        ("3", "Technical Analysis",      "6"),
        ("4", "Brand Authority",         "7"),
        ("5", "AEO Readiness",           "8"),
        ("6", "Recommendations",         "9"),
        ("7", "Final Verdict",           "10"),
        ("8", "Action Plan",             "11"),
        ("9", "Appendix",                "12"),
    ],

    # ── Executive Summary ──
    "executive_summary": (
        "TechNova Solutions demonstrates a solid foundation for AEO performance with "
        "particular strength in content structure and AI answer readiness. However, "
        "critical gaps in schema markup implementation and missing metadata are limiting "
        "visibility in AI-powered search surfaces. The technical infrastructure requires "
        "immediate attention to close the gap between current performance and industry-leading "
        "AEO benchmarks. With targeted improvements over the next 90 days, an AEO score of "
        "85+ is achievable."
    ),

    # ── Search Preview ──
    "search_preview": {
        "title":       "TechNova Solutions — Enterprise Technology Services",
        "url":         "https://www.technovasolutions.com",
        "description": (
            "TechNova Solutions provides enterprise-grade technology consulting, "
            "cloud migration, and digital transformation services to Fortune 500 companies."
        ),
    },

    # ── Content Analysis ──
    "content_analysis": {
        "score": 72,
        "metrics": [
            ("Average Word Count",         "1,240",   "Recommended: 1,500+ for AEO"),
            ("Question-Based Headings",    "34%",     "Target: 60%+"),
            ("Conversational Score",       "68/100",  "Above average"),
            ("Featured Snippet Score",     "71/100",  "Good optimization"),
            ("FAQ Sections",               "Present", "6 pages with FAQ schema"),
            ("Long-Form Content Pages",    "18",      "Covers key topics"),
            ("Thin Content Pages",         "12",      "Under 300 words — needs expansion"),
            ("Readability Score",          "Grade 9", "Target Grade 7 for broad reach"),
        ],
        "strengths": [
            "Strong topic cluster structure around core service areas",
            "Well-organized FAQ sections on product pages",
            "Good use of numbered lists and step-by-step content",
            "Content covers high-intent commercial queries",
        ],
        "weaknesses": [
            "Insufficient question-based heading usage (34% vs 60% target)",
            "12 pages with thin content under 300 words",
            "Limited conversational phrasing for AI extraction",
            "No 'How to' or 'What is' structured guides found",
        ],
        "verdict_text": (
            "Content is well-structured but lacks the conversational depth and "
            "question-driven format required for optimal AEO performance. Expanding "
            "thin content and restructuring headings as questions are the highest-impact "
            "immediate actions."
        ),
    },

    # ── Technical Analysis ──
    "technical_analysis": {
        "score": 58,
        "metrics": [
            ("Page Speed (Mobile)",        "51/100",  "Core Web Vital: LCP 4.2s"),
            ("Page Speed (Desktop)",       "78/100",  "Good desktop performance"),
            ("HTTPS",                      "Yes",     "SSL valid until 2026-03-15"),
            ("Mobile Friendly",            "Yes",     "Responsive design confirmed"),
            ("Core Web Vitals",            "Failed",  "LCP and CLS issues detected"),
            ("XML Sitemap",                "Present", "sitemap.xml found and valid"),
            ("Robots.txt",                 "Present", "No critical blocks detected"),
            ("Canonical Tags",             "Partial", "Missing on 23 pages"),
            ("Hreflang",                   "Absent",  "No international targeting"),
            ("Structured Data (Overall)",  "Partial", "3 of 8 recommended types present"),
        ],
        "schema_audit": [
            {"type": "Organization", "present": True,  "valid": True,  "issues": "None"},
            {"type": "WebSite",      "present": True,  "valid": True,  "issues": "None"},
            {"type": "BreadcrumbList","present": True, "valid": False, "issues": "Missing @id on 4 pages"},
            {"type": "FAQPage",      "present": True,  "valid": True,  "issues": "None"},
            {"type": "Article",      "present": False, "valid": False, "issues": "Not implemented"},
            {"type": "Product",      "present": False, "valid": False, "issues": "Required for service pages"},
            {"type": "LocalBusiness","present": False, "valid": False, "issues": "Not implemented"},
            {"type": "SiteLinksSearchBox","present": False,"valid": False,"issues": "Not implemented"},
        ],
        "metadata_audit": [
            ("Title Tags",         "94% complete",  "8 pages missing title tags"),
            ("Meta Descriptions",  "71% complete",  "41 pages missing descriptions"),
            ("Open Graph Tags",    "Partial",       "Missing on blog posts"),
            ("Twitter Cards",      "Absent",        "Not implemented sitewide"),
            ("Canonical Tags",     "77% complete",  "23 pages without canonicals"),
        ],
        "crawlability_audit": [
            ("Robots.txt",         "Valid",         "No problematic disallow rules"),
            ("XML Sitemap",        "Valid",         "142 URLs indexed"),
            ("Crawl Errors",       "14 errors",     "Mix of 404 and 301 chains"),
            ("Internal Links",     "Good",          "Average 6.2 internal links/page"),
            ("Redirect Chains",    "7 found",       "Chains longer than 2 hops detected"),
            ("Broken Links",       "11 found",      "External links returning 404"),
        ],
        "strengths": [
            "HTTPS implemented correctly with valid SSL certificate",
            "XML sitemap present and correctly formatted",
            "Mobile-friendly responsive design confirmed",
            "Strong internal linking architecture",
        ],
        "weaknesses": [
            "Core Web Vitals failing — LCP at 4.2s on mobile",
            "41% of pages missing meta descriptions",
            "5 of 8 recommended schema types not implemented",
            "14 crawl errors requiring resolution",
        ],
        "verdict_text": (
            "Technical foundations are partially sound but significant gaps exist in "
            "schema markup and metadata completeness. Core Web Vitals failure is limiting "
            "both search ranking and AI answer eligibility. Immediate technical remediation "
            "is critical to unlock AEO potential."
        ),
    },

    # ── Brand Authority ──
    "brand_authority": {
        "score": 63,
        "metrics": [
            ("Domain Authority",       "42/100",  "Above average for industry"),
            ("Referring Domains",      "312",     "Moderate backlink profile"),
            ("Brand Mentions (Est.)",  "1,800/mo","Based on industry keywords"),
            ("Social Signals",         "Moderate","Active LinkedIn and Twitter"),
            ("Press Coverage",         "8 articles","Past 12 months"),
            ("Wikipedia Presence",     "Absent",  "No Wikipedia page found"),
            ("Knowledge Panel",        "Partial", "Claimed but incomplete"),
        ],
        "contact_signals": [
            {"signal": "Phone Number",    "status": "Present", "notes": "In footer and contact page"},
            {"signal": "Email Address",   "status": "Present", "notes": "Contact form + address listed"},
            {"signal": "Physical Address","status": "Present", "notes": "Full address on contact page"},
            {"signal": "Live Chat",       "status": "Missing", "notes": "No live chat widget found"},
            {"signal": "Support Hours",   "status": "Present", "notes": "Monday–Friday 9–5 EST"},
        ],
        "trust_signals": [
            {"signal": "SSL Certificate",   "status": "Verified", "notes": "Valid until 2026"},
            {"signal": "Privacy Policy",    "status": "Present",  "notes": "Up-to-date GDPR compliant"},
            {"signal": "Terms of Service",  "status": "Present",  "notes": "Linked in footer"},
            {"signal": "Customer Reviews",  "status": "Present",  "notes": "G2 and Trustpilot widgets"},
            {"signal": "Case Studies",      "status": "Present",  "notes": "7 detailed case studies"},
            {"signal": "Security Badges",   "status": "Missing",  "notes": "No security certifications shown"},
        ],
        "authority_signals": [
            {"signal": "LinkedIn Company Page","status": "Active",  "notes": "2.4K followers"},
            {"signal": "Clutch Profile",       "status": "Present", "notes": "4.7 stars, 23 reviews"},
            {"signal": "Industry Awards",      "status": "Present", "notes": "2 recent awards featured"},
            {"signal": "Thought Leadership",   "status": "Partial", "notes": "Blog active but infrequent"},
            {"signal": "Speaking/Events",      "status": "Missing", "notes": "No event appearances listed"},
            {"signal": "Wikipedia",            "status": "Missing", "notes": "Not present"},
        ],
        "strengths": [
            "Solid domain authority of 42 — above industry average",
            "Comprehensive contact information across all touchpoints",
            "Verified trust signals including reviews and case studies",
        ],
        "weaknesses": [
            "No Wikipedia presence — critical for AI entity recognition",
            "Knowledge Panel incomplete — missing key business attributes",
            "No security certifications or trust badges displayed",
        ],
        "verdict_text": (
            "Brand authority is moderate with a sound foundation in trust signals and "
            "contact information. The absence of a Wikipedia presence and an incomplete "
            "Knowledge Panel are significant barriers to AI entity recognition. Establishing "
            "an authoritative online entity footprint is the highest-priority brand action."
        ),
    },

    # ── AEO Readiness ──
    "aeo_readiness": {
        "score": 74,
        "platforms": [
            {
                "name":     "ChatGPT",
                "score":    71,
                "key_gaps": "Missing structured Q&A, thin entity data",
                "details":  [
                    ("Conversational Content",  "Moderate",  "Some Q&A present but not structured"),
                    ("Entity Recognition",      "Partial",   "Brand known but details sparse"),
                    ("Citation Potential",      "Medium",    "Some linkable long-form content"),
                    ("Plug-in / Action Ready",  "No",        "No API or action schema found"),
                ],
            },
            {
                "name":     "Google AI Overview",
                "score":    78,
                "key_gaps": "Missing FAQ schema on key pages",
                "details":  [
                    ("Featured Snippet Optimization", "Good",    "71/100 snippet score"),
                    ("FAQ Schema",                    "Partial", "Present on 6 pages only"),
                    ("EEAT Signals",                  "Moderate","Author bios missing on blog"),
                    ("People Also Ask Coverage",      "Good",    "38% of PAA queries covered"),
                ],
            },
            {
                "name":     "Perplexity",
                "score":    69,
                "key_gaps": "Low citation volume, limited structured data",
                "details":  [
                    ("Source Credibility",    "Moderate", "DA42 — borderline for citations"),
                    ("Structured Data",       "Partial",  "3/8 schema types implemented"),
                    ("Content Freshness",     "Low",      "Average content age: 14 months"),
                    ("Direct Answer Format",  "Partial",  "Some pages have direct answers"),
                ],
            },
            {
                "name":     "Gemini",
                "score":    76,
                "key_gaps": "Missing Merchant Center data, no local schema",
                "details":  [
                    ("Knowledge Graph Entity", "Partial",  "Google Business partially claimed"),
                    ("Search Integration",     "Good",     "Ranks for 40% of target queries"),
                    ("Multimodal Content",     "Low",      "Limited images with alt text"),
                    ("Merchant/Service Data",  "Missing",  "No service schema implemented"),
                ],
            },
        ],
        "strengths": [
            "Good baseline Google AI Overview readiness from existing SEO work",
            "FAQ schema correctly implemented on core product pages",
            "Conversational content beginning to emerge in blog section",
        ],
        "weaknesses": [
            "Low citation volume limits Perplexity and ChatGPT inclusion",
            "Author E-E-A-T signals missing from all blog content",
            "No AI-specific structured data implemented",
            "Content freshness below benchmark for AI answer selection",
        ],
        "verdict_text": (
            "AEO readiness is the strongest category, reflecting the team's existing SEO "
            "investments paying dividends in AI search. With targeted improvements to author "
            "authority signals, structured data, and content freshness, a score of 90+ is "
            "realistic within 90 days."
        ),
    },

    # ── Recommendations ──
    "recommendations": [
        {
            "recommendation": "Implement FAQ schema markup across all primary service and product pages",
            "priority":       "High",
            "impact":         "Very High",
            "effort":         "Medium",
            "outcome":        "Increased eligibility for Google AI Overview and ChatGPT citations",
        },
        {
            "recommendation": "Add author bio pages with credentials, LinkedIn profiles, and expertise signals",
            "priority":       "High",
            "impact":         "High",
            "effort":         "Low",
            "outcome":        "Improved E-E-A-T score and Gemini/ChatGPT entity recognition",
        },
        {
            "recommendation": "Resolve Core Web Vitals — target LCP under 2.5s on mobile",
            "priority":       "High",
            "impact":         "High",
            "effort":         "High",
            "outcome":        "Google ranking improvement and AI Overview eligibility boost",
        },
        {
            "recommendation": "Complete meta descriptions for all 41 pages currently missing them",
            "priority":       "High",
            "impact":         "Medium",
            "effort":         "Low",
            "outcome":        "Better CTR from search and improved AI snippet extraction",
        },
        {
            "recommendation": "Create a Wikipedia page for the company entity",
            "priority":       "Medium",
            "impact":         "Very High",
            "effort":         "Medium",
            "outcome":        "Knowledge Panel enrichment and stronger AI entity recognition",
        },
        {
            "recommendation": "Expand thin content pages to 800+ words with structured Q&A format",
            "priority":       "Medium",
            "impact":         "High",
            "effort":         "High",
            "outcome":        "Better People Also Ask coverage and featured snippet eligibility",
        },
        {
            "recommendation": "Implement Article and BreadcrumbList schema sitewide",
            "priority":       "Medium",
            "impact":         "Medium",
            "effort":         "Medium",
            "outcome":        "Enhanced rich results and improved content classification by AI",
        },
        {
            "recommendation": "Set up a content refresh calendar targeting content over 12 months old",
            "priority":       "Low",
            "impact":         "Medium",
            "effort":         "Medium",
            "outcome":        "Improved freshness signals for Perplexity and AI answer selection",
        },
    ],

    # ── Final Verdict ──
    "final_verdict_title":   "GOOD — Solid Foundation, Targeted Improvements Needed",
    "final_verdict_summary": (
        "TechNova Solutions scores 67/100 overall, reflecting a solid SEO-informed base "
        "with clear and actionable gaps in technical implementation and entity authority. "
        "The site is well-positioned to achieve an AEO score of 85+ within 90 days by "
        "executing the high-priority recommendations in this report."
    ),
    "aeo_readiness_matrix": [
        {"platform": "ChatGPT",          "score": 71, "notes": "Add Q&A structure + entity signals"},
        {"platform": "Google AI Overview","score": 78, "notes": "Expand FAQ schema coverage"},
        {"platform": "Perplexity",        "score": 69, "notes": "Boost DA and content freshness"},
        {"platform": "Gemini",            "score": 76, "notes": "Complete Knowledge Panel"},
    ],
    "executive_conclusion": (
        "This audit identifies TechNova Solutions as a strong candidate for rapid AEO "
        "improvement. The existing content architecture and brand reputation provide a "
        "reliable foundation. The 8 recommendations in this report represent a clear "
        "90-day roadmap that is expected to lift the overall AEO score from 67 to 85+, "
        "materially increasing the site's presence in AI-generated answers across ChatGPT, "
        "Google AI Overview, Perplexity, and Gemini."
    ),

    # ── Action Plan ──
    "action_plan": {
        "this_week": [
            {"action": "Add FAQ schema to top 10 service pages",      "category": "Technical",  "impact": "High — immediate AI eligibility"},
            {"action": "Write meta descriptions for all 41 missing pages","category": "Content", "impact": "Medium — CTR and AI snippet lift"},
            {"action": "Fix 14 crawl errors in Google Search Console","category": "Technical",  "impact": "Medium — crawl health"},
            {"action": "Add author name and bio to all blog posts",   "category": "Brand",      "impact": "High — E-E-A-T signals"},
            {"action": "Compress and lazy-load images on top 5 pages","category": "Technical",  "impact": "High — LCP improvement"},
        ],
        "this_month": [
            {"action": "Implement Article schema across all blog posts",  "category": "Technical",  "impact": "High — AI content classification"},
            {"action": "Expand 12 thin content pages to 800+ words",     "category": "Content",    "impact": "High — snippet eligibility"},
            {"action": "Claim and complete Google Business Profile",     "category": "Brand",      "impact": "High — Gemini entity signals"},
            {"action": "Add canonical tags to 23 uncovered pages",       "category": "Technical",  "impact": "Medium — duplicate content resolution"},
            {"action": "Create 4 new 'How to' guides targeting PAA gaps","category": "Content",    "impact": "Medium — People Also Ask coverage"},
        ],
        "long_term": [
            {"action": "Create Wikipedia company page",                      "category": "Brand",    "impact": "Very High — entity recognition"},
            {"action": "Build PR campaign for 20+ high-DA backlinks",       "category": "Brand",    "impact": "High — authority and citation potential"},
            {"action": "Develop interactive tools for AI citation potential","category": "Content",  "impact": "High — linkability and citation"},
            {"action": "Establish thought leadership content series",        "category": "Brand",    "impact": "Medium — E-E-A-T over time"},
            {"action": "Implement full ecommerce/service schema suite",     "category": "Technical","impact": "Medium — rich results expansion"},
        ],
    },

    # ── Appendix ──
    "appendix": {
        "raw_metrics": [
            {"metric": "Total Pages Crawled",     "value": "142",         "source": "Screaming Frog", "notes": "Full site crawl"},
            {"metric": "Indexed Pages (GSC)",     "value": "138",         "source": "GSC",            "notes": "4 pages not indexed"},
            {"metric": "Organic Keywords",        "value": "2,840",       "source": "Ahrefs",         "notes": "All positions"},
            {"metric": "Top 3 Keywords",          "value": "47",          "source": "Ahrefs",         "notes": ""},
            {"metric": "Monthly Organic Traffic", "value": "9,200 est.",  "source": "Ahrefs",         "notes": "Estimated"},
            {"metric": "Backlinks",               "value": "4,112",       "source": "Ahrefs",         "notes": "Referring: 312 domains"},
            {"metric": "Domain Rating",           "value": "42",          "source": "Ahrefs",         "notes": ""},
        ],
        "technical_flags": [
            {"flag": "LCP Failure",       "severity": "High",   "description": "LCP 4.2s on mobile — above 2.5s threshold", "recommendation": "Optimize images and server response time"},
            {"flag": "Missing Meta Desc", "severity": "High",   "description": "41 pages without meta descriptions",         "recommendation": "Write and deploy meta descriptions"},
            {"flag": "Redirect Chains",   "severity": "Medium", "description": "7 redirect chains over 2 hops",             "recommendation": "Update internal links to final destination"},
            {"flag": "Broken Links",      "severity": "Medium", "description": "11 external 404 links",                    "recommendation": "Remove or update broken external links"},
            {"flag": "Missing Canonicals","severity": "Medium", "description": "23 pages without canonical tags",           "recommendation": "Add canonical tags to all affected pages"},
        ],
        "schema_results": [
            {"type": "FAQPage",        "count": 6,  "status": "Valid",   "errors": "None"},
            {"type": "Organization",   "count": 1,  "status": "Valid",   "errors": "None"},
            {"type": "WebSite",        "count": 1,  "status": "Valid",   "errors": "None"},
            {"type": "BreadcrumbList", "count": 18, "status": "Warning", "errors": "Missing @id on 4 instances"},
            {"type": "Article",        "count": 0,  "status": "Missing", "errors": "Not implemented"},
        ],
        "audit_metadata": [
            ("Audit Tool Version",    "AEO Engine v3.1"),
            ("Audit Date",            "June 13, 2025"),
            ("Auditor",               "AEO Audit Engine"),
            ("Pages Audited",         "142"),
            ("Crawl Duration",        "8 minutes 42 seconds"),
            ("Screaming Frog Version","20.1"),
            ("GSC Data Range",        "Last 90 days"),
            ("Ahrefs Data Date",      "June 12, 2025"),
        ],
    },
}

generate_pdf_report = generate_aeo_report