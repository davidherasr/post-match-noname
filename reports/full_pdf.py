from __future__ import annotations

import base64
import json
import math
import re
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from core.constants import OBSERVATION_STATUSES
from core.utils import rating_label
from models.entities import PlayerEvaluation
from repositories import scouting as repo


PAGE_W, PAGE_H = A4
CONTENT_W = 174 * mm


def _safe(value: object | None) -> str:
    return escape(str(value or ""))


def _rich_text(value: str | None, fallback: str = "No se ha registrado información.") -> str:
    text = (value or "").strip()
    if not text:
        text = fallback
    return "<br/>".join(_safe(line) for line in text.splitlines())


def _decode_strengths(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return [x.strip() for x in value.split(",") if x.strip()]


def _mix(a: Color, b: Color, ratio: float) -> Color:
    ratio = max(0.0, min(1.0, ratio))
    return Color(
        a.red * (1 - ratio) + b.red * ratio,
        a.green * (1 - ratio) + b.green * ratio,
        a.blue * (1 - ratio) + b.blue * ratio,
    )


def _hex_to_color(value: str | None, fallback: str) -> Color:
    try:
        return HexColor(value or fallback)
    except Exception:
        return HexColor(fallback)


def _rating_tone(value: float | None, primary: Color, dark: Color) -> Color:
    if value is None:
        return HexColor("#94A3B8")
    if value >= 8.0:
        return primary
    if value >= 7.0:
        return _mix(primary, dark, 0.18)
    if value >= 6.0:
        return _mix(primary, colors.white, 0.28)
    return HexColor("#64748B")


def _status_label(status: str | None) -> str:
    return OBSERVATION_STATUSES.get(status or "", status or "Sin estado")


def _minutes(participation) -> str:
    minute_in = int(participation.minute_in or 0)
    minute_out = int(participation.minute_out or 0)
    minutes = max(0, minute_out - minute_in)
    return f"{minutes}'"


def _slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return clean.strip("_") or "equipo"


def _image_reader(encoded: str | None):
    if not encoded:
        return None
    try:
        raw = base64.b64decode(encoded)
        return ImageReader(BytesIO(raw))
    except Exception:
        return None


def _draw_fitted_text(canvas, text: str, x: float, y: float, max_width: float,
                      font_name: str, font_size: float, min_size: float = 7.0,
                      align: str = "left") -> float:
    size = font_size
    while size > min_size and stringWidth(text, font_name, size) > max_width:
        size -= 0.5
    canvas.setFont(font_name, size)
    if align == "center":
        canvas.drawCentredString(x, y, text)
    elif align == "right":
        canvas.drawRightString(x, y, text)
    else:
        canvas.drawString(x, y, text)
    return size


class MatchHero(Flowable):
    """Editorial-style match masthead for the first page."""

    def __init__(self, width: float, *, club_name: str, report_subtitle: str,
                 home_name: str, away_name: str, score: str, competition: str,
                 round_name: str, match_date: str, rival_name: str,
                 primary: Color, dark: Color, logo=None):
        super().__init__()
        self.width = width
        self.height = 64 * mm
        self.club_name = club_name
        self.report_subtitle = report_subtitle
        self.home_name = home_name
        self.away_name = away_name
        self.score = score
        self.competition = competition
        self.round_name = round_name
        self.match_date = match_date
        self.rival_name = rival_name
        self.primary = primary
        self.dark = dark
        self.logo = logo

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.saveState()
        c.setFillColor(self.dark)
        c.roundRect(0, 0, w, h, 5 * mm, fill=1, stroke=0)
        c.setFillColor(self.primary)
        c.roundRect(0, 0, 8 * mm, h, 5 * mm, fill=1, stroke=0)
        c.rect(4 * mm, 0, 8 * mm, h, fill=1, stroke=0)

        logo_x = 16 * mm
        logo_y = h - 17 * mm
        if self.logo:
            try:
                c.drawImage(self.logo, logo_x, logo_y - 7 * mm, width=14 * mm,
                            height=14 * mm, preserveAspectRatio=True, anchor="c", mask="auto")
            except Exception:
                self.logo = None
        if not self.logo:
            c.setFillColor(colors.white)
            c.circle(logo_x + 7 * mm, logo_y, 6.2 * mm, fill=0, stroke=1)
            initials = "".join(word[:1] for word in self.club_name.split()[:2]).upper() or "PM"
            c.setFont("Helvetica-Bold", 7.5)
            c.drawCentredString(logo_x + 7 * mm, logo_y - 2.5, initials)

        c.setFillColor(colors.white)
        _draw_fitted_text(c, self.club_name.upper(), 34 * mm, h - 11.5 * mm,
                          w - 50 * mm, "Helvetica-Bold", 9.5, 7.5)
        c.setFillColor(_mix(colors.white, self.dark, 0.28))
        _draw_fitted_text(c, self.report_subtitle.upper(), 34 * mm, h - 17.3 * mm,
                          w - 50 * mm, "Helvetica", 7.2, 6.5)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(16 * mm, h - 27 * mm, "INFORME POSTPARTIDO")
        c.setFillColor(_mix(colors.white, self.dark, 0.32))
        c.setFont("Helvetica", 6.8)
        c.drawRightString(w - 12 * mm, h - 27 * mm, f"RIVAL ANALIZADO · {self.rival_name.upper()}")

        left_center = 48 * mm
        right_center = w - 48 * mm
        score_center = w / 2
        c.setFillColor(colors.white)
        _draw_fitted_text(c, self.home_name, left_center, h - 42 * mm, 66 * mm,
                          "Helvetica-Bold", 15, 9, "center")
        _draw_fitted_text(c, self.away_name, right_center, h - 42 * mm, 66 * mm,
                          "Helvetica-Bold", 15, 9, "center")

        c.setFillColor(self.primary)
        c.roundRect(score_center - 17 * mm, h - 49.5 * mm, 34 * mm, 19 * mm,
                    4 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        _draw_fitted_text(c, self.score, score_center, h - 43.5 * mm, 29 * mm,
                          "Helvetica-Bold", 23, 14, "center")

        c.setStrokeColor(_mix(colors.white, self.dark, 0.72))
        c.setLineWidth(0.5)
        c.line(16 * mm, 10 * mm, w - 12 * mm, 10 * mm)
        c.setFillColor(_mix(colors.white, self.dark, 0.28))
        c.setFont("Helvetica", 7.2)
        c.drawString(16 * mm, 5.5 * mm, self.competition)
        c.drawCentredString(w / 2, 5.5 * mm, self.round_name)
        c.drawRightString(w - 12 * mm, 5.5 * mm, self.match_date)
        c.restoreState()


class RatingBar(Flowable):
    def __init__(self, label: str, value: float, width: float, primary: Color,
                 dark: Color, compact: bool = False):
        super().__init__()
        self.label = label
        self.value = max(0.0, min(10.0, float(value)))
        self.width = width
        self.height = 8 * mm if compact else 10 * mm
        self.primary = primary
        self.dark = dark
        self.compact = compact

    def draw(self):
        c = self.canv
        w = self.width
        label_y = self.height - (2.9 * mm if self.compact else 3.3 * mm)
        c.saveState()
        c.setFillColor(self.dark)
        c.setFont("Helvetica-Bold", 6.8 if self.compact else 7.5)
        c.drawString(0, label_y, self.label.upper())
        c.setFillColor(self.dark)
        c.setFont("Helvetica-Bold", 7.2 if self.compact else 8.5)
        c.drawRightString(w, label_y, f"{self.value:.1f}")
        track_y = 0.8 * mm
        track_h = 2.2 * mm if self.compact else 2.8 * mm
        c.setFillColor(HexColor("#E2E8F0"))
        c.roundRect(0, track_y, w, track_h, track_h / 2, fill=1, stroke=0)
        fill_w = max(track_h, w * self.value / 10.0)
        c.setFillColor(_rating_tone(self.value, self.primary, self.dark))
        c.roundRect(0, track_y, fill_w, track_h, track_h / 2, fill=1, stroke=0)
        c.restoreState()


class ScoreDial(Flowable):
    def __init__(self, value: float | None, size: float, primary: Color, dark: Color):
        super().__init__()
        self.width = size
        self.height = size
        self.value = value
        self.primary = primary
        self.dark = dark

    def draw(self):
        c = self.canv
        cx, cy = self.width / 2, self.height / 2
        radius = min(self.width, self.height) / 2 - 1.2 * mm
        c.saveState()
        c.setStrokeColor(HexColor("#E2E8F0"))
        c.setLineWidth(3.6)
        c.circle(cx, cy, radius, fill=0, stroke=1)
        if self.value is not None:
            c.setStrokeColor(_rating_tone(self.value, self.primary, self.dark))
            c.setLineWidth(3.6)
            start = 90
            extent = -360 * max(0.0, min(10.0, self.value)) / 10.0
            c.arc(cx - radius, cy - radius, cx + radius, cy + radius, start, extent)
            c.setFillColor(self.dark)
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(cx, cy - 1.5, f"{self.value:.1f}")
            c.setFillColor(HexColor("#64748B"))
            c.setFont("Helvetica", 6.4)
            c.drawCentredString(cx, cy - 10, "SOBRE 10")
        else:
            c.setFillColor(HexColor("#94A3B8"))
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(cx, cy - 2, "-")
        c.restoreState()


class TagPills(Flowable):
    def __init__(self, tags: list[str], width: float, primary: Color, dark: Color):
        super().__init__()
        self.tags = tags
        self.width = width
        self.primary = primary
        self.dark = dark
        self.height = self._measure_height()

    def _measure_height(self) -> float:
        if not self.tags:
            return 0
        x = 0.0
        lines = 1
        for tag in self.tags:
            tw = stringWidth(tag, "Helvetica-Bold", 6.5) + 7 * mm
            if x and x + tw > self.width:
                lines += 1
                x = 0
            x += tw + 2 * mm
        return lines * 7 * mm

    def draw(self):
        if not self.tags:
            return
        c = self.canv
        x, y = 0.0, self.height - 5.2 * mm
        fill = _mix(self.primary, colors.white, 0.88)
        stroke = _mix(self.primary, colors.white, 0.55)
        c.saveState()
        for tag in self.tags:
            tw = stringWidth(tag, "Helvetica-Bold", 6.5) + 7 * mm
            if x and x + tw > self.width:
                x = 0
                y -= 7 * mm
            c.setFillColor(fill)
            c.setStrokeColor(stroke)
            c.roundRect(x, y, tw, 5.4 * mm, 2.7 * mm, fill=1, stroke=1)
            c.setFillColor(self.dark)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawCentredString(x + tw / 2, y + 1.65 * mm, tag)
            x += tw + 2 * mm
        c.restoreState()


def _section_heading(text: str, styles: dict, primary: Color, dark: Color,
                     kicker: str | None = None) -> Table:
    left = [Paragraph(_safe(text), styles["section"])]
    if kicker:
        right = Paragraph(_safe(kicker).upper(), styles["section_kicker"])
    else:
        right = ""
    table = Table([[left[0], right]], colWidths=[124 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.1, primary),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * mm),
        ("TEXTCOLOR", (0, 0), (-1, -1), dark),
    ]))
    return table


def _kpi_table(payload: dict, styles: dict, primary: Color, dark: Color) -> Table:
    report = payload["report"]
    evaluated = payload["evaluated_players"]
    noteworthy = payload["noteworthy_players"]
    standout = payload["standout_row"]
    standout_name = "No indicado"
    if standout:
        player = standout["participation"].player
        standout_name = player.display_name or player.full_name
    average_rating = (
        sum(float(row["evaluation"].general_rating) for row in evaluated) / len(evaluated)
        if evaluated else None
    )
    values = [
        ("NOTA MEDIA", f"{average_rating:.1f}" if average_rating is not None else "Sin datos"),
        ("JUGADORES EVALUADOS", str(len(evaluated))),
        ("DESTACADOS", str(len(noteworthy))),
        ("MÁS DESTACADO", standout_name),
    ]
    cells = []
    for label, value in values:
        cells.append([
            Paragraph(_safe(label), styles["kpi_label"]),
            Paragraph(_safe(value), styles["kpi_value"]),
        ])
    inner = []
    for pair in cells:
        card = Table([[pair[0]], [pair[1]]], colWidths=[39 * mm], rowHeights=[8 * mm, 17 * mm])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
            ("LINEABOVE", (0, 0), (-1, 0), 2.3, primary),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        inner.append(card)
    table = Table([inner], colWidths=[42.5 * mm] * 4, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _watchlist_table(payload: dict, styles: dict, primary: Color, dark: Color) -> Table:
    eligible = [row for row in payload["evaluated_players"] if getattr(row["evaluation"], "pdf_include", True)]
    highlighted = [row for row in payload["noteworthy_players"] if getattr(row["evaluation"], "pdf_include", True)]
    rows = highlighted[:5] or eligible[:3]
    if not rows:
        return Table([[Paragraph("Todavía no hay jugadores evaluados para destacar.", styles["body_muted"])]],
                     colWidths=[174 * mm])
    data = [[
        Paragraph("JUGADOR", styles["table_header"]),
        Paragraph("POS.", styles["table_header_center"]),
        Paragraph("NOTA", styles["table_header_center"]),
        Paragraph("OBSERVACIÓN", styles["table_header"]),
    ]]
    for row in rows:
        part = row["participation"]
        ev = row["evaluation"]
        player_name = part.player.display_name or part.player.full_name
        short_note = ev.short_note or "Sin observación adicional."
        data.append([
            Paragraph(f"<b>{_safe(player_name)}</b>", styles["table_body"]),
            Paragraph(_safe(part.position or part.player.primary_position or "-"), styles["table_center"]),
            Paragraph(f"<b>{ev.general_rating:.1f}</b>", styles["table_score"]),
            Paragraph(_rich_text(short_note, ""), styles["table_body_small"]),
        ])
    table = Table(data, colWidths=[47 * mm, 16 * mm, 18 * mm, 93 * mm], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, HexColor("#D8E0E8")),
        ("TOPPADDING", (0, 0), (-1, 0), 3.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3.5 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("ALIGN", (1, 1), (2, -1), "CENTER"),
    ]
    for idx in range(1, len(data)):
        if idx % 2 == 0:
            style.append(("BACKGROUND", (0, idx), (-1, idx), HexColor("#F8FAFC")))
        style.append(("TEXTCOLOR", (2, idx), (2, idx), _rating_tone(rows[idx - 1]["evaluation"].general_rating, primary, dark)))
    table.setStyle(TableStyle(style))
    return table


def _lineup_card(team_name: str, formation: str | None, rows: list[dict], styles: dict,
                 accent: Color, dark: Color) -> Table:
    starters = [row["participation"] for row in rows if row["participation"].starter]
    substitutes = [row["participation"] for row in rows if not row["participation"].starter]

    data = [[
        Paragraph(_safe(team_name), styles["lineup_team"]),
        Paragraph(_safe(formation or "Sistema no indicado"), styles["formation_badge"]),
    ]]
    data.append([Paragraph("TITULARES", styles["lineup_group"]), ""])
    for part in starters:
        name = part.player.display_name or part.player.full_name
        captain = " · C" if part.captain else ""
        data.append([
            Paragraph(f"<b>{part.shirt_number or '-'}</b>  {_safe(name)}{captain}", styles["lineup_player"]),
            Paragraph(f"{_safe(part.position or '-')} · {_minutes(part)}", styles["lineup_meta"]),
        ])
    if substitutes:
        data.append([Paragraph("SUPLENTES UTILIZADOS", styles["lineup_group"]), ""])
        for part in substitutes:
            name = part.player.display_name or part.player.full_name
            data.append([
                Paragraph(f"<b>{part.shirt_number or '-'}</b>  {_safe(name)}", styles["lineup_player"]),
                Paragraph(
                    f"{_safe(part.position or '-')} · entra {part.minute_in}' · {_minutes(part)}",
                    styles["lineup_meta"],
                ),
            ])
    table = Table(data, colWidths=[60 * mm, 25 * mm])
    style = [
        ("SPAN", (0, 1), (1, 1)),
        ("BACKGROUND", (0, 0), (-1, 0), dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 3.8 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3.8 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.2 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 2.15 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.15 * mm),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 2), (-1, -1), 0.25, HexColor("#E2E8F0")),
    ]
    group_rows = [1]
    cursor = 2 + len(starters)
    if substitutes:
        group_rows.append(cursor)
        style.append(("SPAN", (0, cursor), (1, cursor)))
    for row_index in group_rows:
        style.extend([
            ("BACKGROUND", (0, row_index), (-1, row_index), _mix(accent, colors.white, 0.88)),
            ("TEXTCOLOR", (0, row_index), (-1, row_index), dark),
            ("TOPPADDING", (0, row_index), (-1, row_index), 2.2 * mm),
            ("BOTTOMPADDING", (0, row_index), (-1, row_index), 2.2 * mm),
        ])
    table.setStyle(TableStyle(style))
    return table


def _player_overview_table(payload: dict, styles: dict, primary: Color, dark: Color) -> Table:
    rows = [row for row in payload["evaluated_players"] if getattr(row["evaluation"], "pdf_include", True)]
    data = [[
        Paragraph("#", styles["table_header_center"]),
        Paragraph("JUGADOR", styles["table_header"]),
        Paragraph("POS.", styles["table_header_center"]),
        Paragraph("MIN.", styles["table_header_center"]),
        Paragraph("NOTA", styles["table_header_center"]),
        Paragraph("OBSERVACIÓN", styles["table_header"]),
    ]]
    for row in rows:
        part = row["participation"]
        ev = row["evaluation"]
        player_name = part.player.display_name or part.player.full_name
        flag = " ★" if ev.standout else ""
        data.append([
            Paragraph(str(part.shirt_number or "-"), styles["table_center"]),
            Paragraph(f"<b>{_safe(player_name)}</b>{flag}", styles["table_body"]),
            Paragraph(_safe(part.position or part.player.primary_position or "-"), styles["table_center"]),
            Paragraph(_minutes(part), styles["table_center"]),
            Paragraph(f"<b>{ev.general_rating:.1f}</b>", styles["table_score"]),
            Paragraph(_rich_text(ev.short_note, "Sin observación adicional."), styles["table_body_small"]),
        ])
    if len(data) == 1:
        data.append(["-", Paragraph("Sin jugadores evaluados.", styles["table_body"]), "-", "-", "-", "-"])
    table = Table(data, colWidths=[10 * mm, 45 * mm, 14 * mm, 14 * mm, 16 * mm, 75 * mm], repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#D8E0E8")),
        ("TOPPADDING", (0, 0), (-1, 0), 3.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3.2 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 2.7 * mm),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.7 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.6 * mm),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (4, -1), "CENTER"),
    ]
    for idx in range(1, len(data)):
        if idx % 2 == 0:
            commands.append(("BACKGROUND", (0, idx), (-1, idx), HexColor("#F8FAFC")))
        if idx - 1 < len(rows):
            commands.append(("TEXTCOLOR", (4, idx), (4, idx), _rating_tone(rows[idx - 1]["evaluation"].general_rating, primary, dark)))
    table.setStyle(TableStyle(commands))
    return table


def _player_card(row: dict, styles: dict, primary: Color, dark: Color) -> list:
    part = row["participation"]
    ev: PlayerEvaluation = row["evaluation"]
    player = part.player
    name = player.display_name or player.full_name
    position = part.position or player.primary_position or "-"
    standout_text = " · JUGADOR DESTACADO" if ev.standout else ""

    number_box = Table([[Paragraph(str(part.shirt_number or "-"), styles["number_box"])]],
                       colWidths=[16 * mm], rowHeights=[16 * mm])
    number_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0, primary),
    ]))
    name_block = [
        Paragraph(_safe(name).upper(), styles["player_name"]),
        Paragraph(
            f"{_safe(position)} · {_minutes(part)} · {_status_label(ev.observation_status)}{_safe(standout_text)}",
            styles["player_meta"],
        ),
    ]
    score = ScoreDial(ev.general_rating, 24 * mm, primary, dark)
    header = Table([[number_box, name_block, score]], colWidths=[19 * mm, 126 * mm, 29 * mm], rowHeights=[25 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ("LINEABOVE", (0, 0), (-1, 0), 2.2, primary),
    ]))

    metric_items: list[Flowable] = []
    if ev.general_rating is not None:
        metric_items.append(RatingBar("Nota general", ev.general_rating, 50 * mm, primary, dark))
    for label, value in (
        ("Técnica", ev.technical_rating),
        ("Táctica", ev.tactical_rating),
        ("Física", ev.physical_rating),
    ):
        if value is not None:
            metric_items.append(RatingBar(label, value, 50 * mm, primary, dark, compact=True))
    if not metric_items:
        metric_items.append(Paragraph("Sin valoración numérica.", styles["body_muted"]))

    note = Paragraph(_rich_text(ev.short_note, "Sin observación adicional."), styles["observation"])
    strengths = _decode_strengths(ev.strengths)
    right_flowables: list = [
        Paragraph("OBSERVACIÓN", styles["detail_label_accent"]),
        note,
    ]
    optional_rows = []
    if ev.recommendation:
        optional_rows.append([Paragraph("DECISIÓN", styles["detail_label"]), Paragraph(_safe(ev.recommendation), styles["detail_value_bold"])])
    if ev.confidence:
        optional_rows.append([Paragraph("CONFIANZA", styles["detail_label"]), Paragraph(_safe(ev.confidence), styles["detail_value"])])
    if optional_rows:
        decision_table = Table(optional_rows, colWidths=[24 * mm, 84 * mm])
        decision_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.3, HexColor("#E2E8F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
        ]))
        right_flowables.extend([Spacer(1, 2.2 * mm), decision_table])
    if strengths:
        right_flowables.extend([
            Spacer(1, 2 * mm),
            Paragraph("FORTALEZAS DETECTADAS", styles["detail_label_accent"]),
            Spacer(1, 1.2 * mm),
            TagPills(strengths, 108 * mm, primary, dark),
        ])

    body = Table([[metric_items, right_flowables]], colWidths=[58 * mm, 116 * mm])
    body.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#CBD5E1")),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
    ]))

    block: list = [header, body]
    if ev.detailed_note:
        detail_box = Table([[
            Paragraph("NOTA AMPLIADA", styles["detail_label_accent"]),
            Paragraph(_rich_text(ev.detailed_note, ""), styles["body"]),
        ]], colWidths=[31 * mm, 143 * mm])
        detail_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ]))
        block.append(detail_box)
    block.append(Spacer(1, 6 * mm))
    return block


def _other_observations_table(payload: dict, styles: dict, dark: Color) -> Table | None:
    rows = []
    for row in payload["rival_players"]:
        ev = row["evaluation"]
        if not ev or ev.observation_status == "evaluated" or not getattr(ev, "pdf_include", True):
            continue
        part = row["participation"]
        rows.append((part, ev))
    if not rows:
        return None
    data = [[
        Paragraph("JUGADOR", styles["table_header"]),
        Paragraph("ESTADO", styles["table_header"]),
        Paragraph("ANOTACIÓN", styles["table_header"]),
    ]]
    for part, ev in rows:
        name = part.player.display_name or part.player.full_name
        data.append([
            Paragraph(f"<b>{_safe(name)}</b>", styles["table_body"]),
            Paragraph(_safe(_status_label(ev.observation_status)), styles["table_body_small"]),
            Paragraph(_rich_text(ev.short_note, "Sin anotación."), styles["table_body_small"]),
        ])
    table = Table(data, colWidths=[48 * mm, 46 * mm, 80 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#D8E0E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    return table


def _own_team_table(payload: dict, styles: dict, dark: Color) -> Table | None:
    own_evaluated = [
        row for row in payload["own_players"]
        if row["evaluation"] is not None
        and row["evaluation"].observation_status == "evaluated"
        and row["evaluation"].general_rating is not None
        and row["evaluation"].pdf_include
    ]
    if not own_evaluated:
        return None
    data = [[
        Paragraph("JUGADOR", styles["table_header"]),
        Paragraph("POS.", styles["table_header_center"]),
        Paragraph("MIN.", styles["table_header_center"]),
        Paragraph("NOTA", styles["table_header_center"]),
        Paragraph("OBSERVACIÓN", styles["table_header"]),
    ]]
    for row in own_evaluated:
        part = row["participation"]
        ev = row["evaluation"]
        name = part.player.display_name or part.player.full_name
        data.append([
            Paragraph(f"<b>{_safe(name)}</b>", styles["table_body"]),
            Paragraph(_safe(part.position or "-"), styles["table_center"]),
            Paragraph(_minutes(part), styles["table_center"]),
            Paragraph("-" if ev.general_rating is None else f"<b>{ev.general_rating:.1f}</b>", styles["table_score"]),
            Paragraph(_rich_text(ev.short_note, ""), styles["table_body_small"]),
        ])
    table = Table(data, colWidths=[44 * mm, 15 * mm, 15 * mm, 16 * mm, 84 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), dark),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#D8E0E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("ALIGN", (1, 1), (3, -1), "CENTER"),
    ]))
    return table


def _styles(primary: Color, dark: Color) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "PMBody", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2,
            leading=13, textColor=dark, spaceAfter=0,
        ),
        "body_muted": ParagraphStyle(
            "PMBodyMuted", parent=base["BodyText"], fontName="Helvetica", fontSize=8.7,
            leading=12, textColor=HexColor("#64748B"),
        ),
        "section": ParagraphStyle(
            "PMSection", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16,
            leading=19, textColor=dark,
        ),
        "section_kicker": ParagraphStyle(
            "PMSectionKicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.8,
            leading=8, textColor=HexColor("#64748B"), alignment=TA_RIGHT,
        ),
        "kpi_label": ParagraphStyle(
            "PMKpiLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.3,
            leading=7.5, textColor=HexColor("#64748B"),
        ),
        "kpi_value": ParagraphStyle(
            "PMKpiValue", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.2,
            leading=12, textColor=dark,
        ),
        "callout_label": ParagraphStyle(
            "PMCalloutLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.7,
            leading=8, textColor=primary,
        ),
        "callout_text": ParagraphStyle(
            "PMCalloutText", parent=base["BodyText"], fontName="Helvetica", fontSize=10,
            leading=14.2, textColor=dark,
        ),
        "table_header": ParagraphStyle(
            "PMTableHeader", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.7,
            leading=8, textColor=colors.white,
        ),
        "table_header_center": ParagraphStyle(
            "PMTableHeaderCenter", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.7,
            leading=8, textColor=colors.white, alignment=TA_CENTER,
        ),
        "table_body": ParagraphStyle(
            "PMTableBody", parent=base["Normal"], fontName="Helvetica", fontSize=7.8,
            leading=10.2, textColor=dark,
        ),
        "table_body_small": ParagraphStyle(
            "PMTableBodySmall", parent=base["Normal"], fontName="Helvetica", fontSize=7.2,
            leading=9.4, textColor=dark,
        ),
        "table_center": ParagraphStyle(
            "PMTableCenter", parent=base["Normal"], fontName="Helvetica", fontSize=7.6,
            leading=9.5, textColor=dark, alignment=TA_CENTER,
        ),
        "table_score": ParagraphStyle(
            "PMTableScore", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9.2,
            leading=10.5, textColor=primary, alignment=TA_CENTER,
        ),
        "lineup_team": ParagraphStyle(
            "PMLineupTeam", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10,
            leading=12, textColor=colors.white,
        ),
        "formation_badge": ParagraphStyle(
            "PMFormation", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.4,
            leading=9, textColor=colors.white, alignment=TA_RIGHT,
        ),
        "lineup_group": ParagraphStyle(
            "PMLineupGroup", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.6,
            leading=8, textColor=dark,
        ),
        "lineup_player": ParagraphStyle(
            "PMLineupPlayer", parent=base["Normal"], fontName="Helvetica", fontSize=7.2,
            leading=8.5, textColor=dark,
        ),
        "lineup_meta": ParagraphStyle(
            "PMLineupMeta", parent=base["Normal"], fontName="Helvetica", fontSize=6.8,
            leading=8.2, textColor=HexColor("#64748B"), alignment=TA_RIGHT,
        ),
        "player_name": ParagraphStyle(
            "PMPlayerName", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=14.5,
            leading=16.5, textColor=dark,
        ),
        "player_meta": ParagraphStyle(
            "PMPlayerMeta", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.8,
            leading=8.4, textColor=HexColor("#64748B"),
        ),
        "number_box": ParagraphStyle(
            "PMNumberBox", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=15,
            leading=16, textColor=colors.white, alignment=TA_CENTER,
        ),
        "detail_label": ParagraphStyle(
            "PMDetailLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.5,
            leading=8, textColor=HexColor("#64748B"),
        ),
        "detail_label_accent": ParagraphStyle(
            "PMDetailLabelAccent", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.6,
            leading=8, textColor=primary,
        ),
        "detail_value": ParagraphStyle(
            "PMDetailValue", parent=base["Normal"], fontName="Helvetica", fontSize=8,
            leading=10, textColor=dark,
        ),
        "detail_value_bold": ParagraphStyle(
            "PMDetailValueBold", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
            leading=10, textColor=dark,
        ),
        "observation": ParagraphStyle(
            "PMObservation", parent=base["BodyText"], fontName="Helvetica", fontSize=9.1,
            leading=13, textColor=dark,
        ),
        "small_note": ParagraphStyle(
            "PMSmallNote", parent=base["BodyText"], fontName="Helvetica", fontSize=7.4,
            leading=9.4, textColor=HexColor("#64748B"),
        ),
    }


# ===========================================================================
# No Name PostMatch 3.6 - immutable versions, executive/full modes and visual XI
# ===========================================================================
from datetime import date as _date
from pathlib import Path as _Path
from types import SimpleNamespace as _NS

from reportlab.pdfbase import pdfmetrics as _pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as _TTFont

_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
for _regular, _bold in [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
]:
    if _Path(_regular).exists() and _Path(_bold).exists():
        try:
            _pdfmetrics.registerFont(_TTFont("PMUnicode", _regular))
            _pdfmetrics.registerFont(_TTFont("PMUnicode-Bold", _bold))
            _FONT_REGULAR, _FONT_BOLD = "PMUnicode", "PMUnicode-Bold"
            break
        except Exception:
            pass










class MatchHeroV2(Flowable):
    def __init__(self, width: float, *, club_name: str, report_subtitle: str, home_name: str, away_name: str,
                 score: str, competition: str, round_name: str, match_date: str, rival_name: str,
                 primary: Color, dark: Color, club_logo=None, home_logo=None, away_logo=None):
        super().__init__()
        self.width, self.height = width, 61 * mm
        self.club_name, self.report_subtitle = club_name, report_subtitle
        self.home_name, self.away_name, self.score = home_name, away_name, score
        self.competition, self.round_name, self.match_date, self.rival_name = competition, round_name, match_date, rival_name
        self.primary, self.dark = primary, dark
        self.club_logo, self.home_logo, self.away_logo = club_logo, home_logo, away_logo

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.saveState(); c.setFillColor(self.dark); c.roundRect(0, 0, w, h, 4 * mm, fill=1, stroke=0)
        c.setFillColor(self.primary); c.roundRect(0, 0, 7 * mm, h, 4 * mm, fill=1, stroke=0); c.rect(4 * mm, 0, 7 * mm, h, fill=1, stroke=0)
        if self.club_logo:
            try: c.drawImage(self.club_logo, 14 * mm, h - 17 * mm, 13 * mm, 13 * mm, preserveAspectRatio=True, mask="auto")
            except Exception: pass
        c.setFillColor(colors.white); c.setFont(_FONT_BOLD, 9.5); c.drawString(31 * mm, h - 9.5 * mm, self.club_name.upper())
        c.setFont(_FONT_REGULAR, 6.8); c.setFillColor(_mix(colors.white, self.dark, .3)); c.drawString(31 * mm, h - 15 * mm, self.report_subtitle.upper())
        c.setFont(_FONT_BOLD, 8.2); c.setFillColor(colors.white); c.drawRightString(w - 10 * mm, h - 10 * mm, "INFORME POSTPARTIDO")
        c.setFont(_FONT_REGULAR, 6.2); c.setFillColor(_mix(colors.white, self.dark, .3)); c.drawRightString(w - 10 * mm, h - 15 * mm, f"RIVAL · {self.rival_name.upper()}")
        centers = [46 * mm, w - 46 * mm]
        for logo, x in [(self.home_logo, centers[0]), (self.away_logo, centers[1])]:
            if logo:
                try: c.drawImage(logo, x - 6 * mm, h - 34 * mm, 12 * mm, 12 * mm, preserveAspectRatio=True, mask="auto")
                except Exception: pass
        c.setFillColor(colors.white)
        _draw_fitted_text(c, self.home_name, centers[0], h - 40 * mm, 61 * mm, _FONT_BOLD, 13, 8, "center")
        _draw_fitted_text(c, self.away_name, centers[1], h - 40 * mm, 61 * mm, _FONT_BOLD, 13, 8, "center")
        c.setFillColor(self.primary); c.roundRect(w / 2 - 15 * mm, h - 46 * mm, 30 * mm, 17 * mm, 3.5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white); _draw_fitted_text(c, self.score, w / 2, h - 40.5 * mm, 26 * mm, _FONT_BOLD, 20, 13, "center")
        c.setStrokeColor(_mix(colors.white, self.dark, .7)); c.line(14 * mm, 9 * mm, w - 10 * mm, 9 * mm)
        c.setFillColor(_mix(colors.white, self.dark, .25)); c.setFont(_FONT_REGULAR, 6.5)
        c.drawString(14 * mm, 4.5 * mm, self.competition); c.drawCentredString(w / 2, 4.5 * mm, self.round_name); c.drawRightString(w - 10 * mm, 4.5 * mm, self.match_date)
        c.restoreState()


class FormationPitch(Flowable):
    def __init__(self, width: float, rows: list[dict], team_name: str, formation: str | None, primary: Color, dark: Color):
        super().__init__(); self.width = width; self.height = 82 * mm
        self.rows, self.team_name, self.formation, self.primary, self.dark = rows, team_name, formation or "Sistema no indicado", primary, dark

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.saveState(); c.setFillColor(HexColor("#EEF4EF")); c.roundRect(0, 0, w, h, 3 * mm, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#A8B8AA")); c.setLineWidth(.6); c.rect(4 * mm, 5 * mm, w - 8 * mm, h - 17 * mm, fill=0, stroke=1)
        c.line(4 * mm, (h - 7 * mm) / 2, w - 4 * mm, (h - 7 * mm) / 2); c.circle(w / 2, (h - 7 * mm) / 2, 8 * mm, fill=0, stroke=1)
        c.setFillColor(self.dark); c.setFont(_FONT_BOLD, 7.5); c.drawString(4 * mm, h - 8 * mm, self.team_name)
        c.setFont(_FONT_REGULAR, 6.5); c.drawRightString(w - 4 * mm, h - 8 * mm, self.formation)
        starters = [r["participation"] for r in self.rows if r["participation"].starter][:11]
        bands = {"POR": 0, "LD": 1, "DFC": 1, "LI": 1, "CAD": 1, "CAI": 1, "MCD": 2, "MC": 2, "MP": 3, "ED": 3, "EI": 3, "SD": 3, "DC": 4, "Otro": 2}
        grouped: dict[int, list] = {i: [] for i in range(5)}
        for p in starters:
            grouped[bands.get(p.position or getattr(p.player, "primary_position", None) or "Otro", 2)].append(p)
        y_positions = [11 * mm, 25 * mm, 39 * mm, 53 * mm, 66 * mm]
        for band, players in grouped.items():
            count = len(players)
            for idx, p in enumerate(players):
                x = (idx + 1) * w / (count + 1)
                y = y_positions[band]
                c.setFillColor(self.primary); c.circle(x, y, 4.2 * mm, fill=1, stroke=0)
                c.setFillColor(colors.white); c.setFont(_FONT_BOLD, 6.5); c.drawCentredString(x, y - 2, str(p.shirt_number or "-"))
                name = (p.player.display_name or p.player.full_name).split()[-1]
                c.setFillColor(self.dark)
                _draw_fitted_text(c, name, x, y - 7 * mm, 18 * mm, _FONT_REGULAR, 5.7, 4.5, "center")
        c.restoreState()


def _styles_v2(primary: Color, dark: Color) -> dict:
    styles = _styles(primary, dark)
    for style in styles.values():
        if getattr(style, "fontName", "") == "Helvetica-Bold":
            style.fontName = _FONT_BOLD
        elif getattr(style, "fontName", "") == "Helvetica":
            style.fontName = _FONT_REGULAR
    return styles


def _consensus_table(payload: dict, styles: dict, dark: Color) -> Table | None:
    consensus = payload.get("consensus") or []
    if not consensus or max((r["sample_size"] for r in consensus), default=0) < 2:
        return None
    data = [[Paragraph("JUGADOR", styles["table_header"]), Paragraph("MUESTRA", styles["table_header_center"]), Paragraph("MEDIA", styles["table_header_center"]), Paragraph("DESACUERDO", styles["table_header_center"])]]
    for row in consensus[:6]:
        data.append([Paragraph(_safe(row["player_name"]), styles["table_body"]), Paragraph(str(row["sample_size"]), styles["table_center"]), Paragraph(f"{row['average']:.1f}", styles["table_score"]), Paragraph(f"{row['dispersion']:.2f}", styles["table_center"])])
    table = Table(data, colWidths=[85 * mm, 25 * mm, 25 * mm, 39 * mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), dark), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, HexColor("#D8E0E8")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("TOPPADDING", (0,0), (-1,-1), 2.5 * mm), ("BOTTOMPADDING", (0,0), (-1,-1), 2.5 * mm)]))
    return table



def _summary_rows(rows: list[dict], styles: dict, primary: Color, dark: Color) -> Table | None:
    visible = [
        row for row in rows
        if row.get("evaluation")
        and row["evaluation"].observation_status == "evaluated"
        and row["evaluation"].general_rating is not None
        and getattr(row["evaluation"], "pdf_include", True)
    ]
    if not visible:
        return None
    data = [[
        Paragraph("JUGADOR", styles["table_header"]),
        Paragraph("POS", styles["table_header_center"]),
        Paragraph("MIN", styles["table_header_center"]),
        Paragraph("NOTA", styles["table_header_center"]),
        Paragraph("OBSERVACIÓN", styles["table_header"]),
    ]]
    for row in visible:
        part, ev = row["participation"], row["evaluation"]
        name = part.player.display_name or part.player.full_name
        note = (ev.short_note or "").strip()
        if len(note) > 120:
            note = note[:117].rstrip() + "…"
        star = " ★" if ev.standout else ""
        data.append([
            Paragraph(_safe(name) + star, styles["table_body"]),
            Paragraph(_safe(part.position or getattr(part.player, "primary_position", "") or "—"), styles["table_center"]),
            Paragraph(_minutes(part), styles["table_center"]),
            Paragraph(f"<b>{float(ev.general_rating):.1f}</b>", styles["table_score"]),
            Paragraph(_safe(note) if note else "—", styles["table_body"]),
        ])
    table = Table(data, colWidths=[49*mm, 16*mm, 16*mm, 18*mm, 75*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), dark),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), .25, HexColor("#D8E0E8")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 2.2*mm),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.2*mm),
        ("LEFTPADDING", (0,0), (-1,-1), 2.2*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 2.2*mm),
    ]))
    return table






def generate_full_pdf(payload: dict, *, current_version: int) -> bytes:
    report, match, settings = payload["report"], payload["match"], payload["settings"]
    primary = _hex_to_color(settings.get("primary_color"), "#B91C1C"); dark = _hex_to_color(settings.get("secondary_color"), "#111827")
    club_name = settings.get("club_name") or "NO NAME"
    report_subtitle = settings.get("report_subtitle") or "No Name · Informe postpartido"
    confidentiality = settings.get("report_confidentiality") or "Documento interno y confidencial"
    styles = _styles_v2(primary, dark)
    score = "-" if match.home_score is None or match.away_score is None else f"{match.home_score}  -  {match.away_score}"
    cards = [r for r in payload["evaluated_players"] if getattr(r["evaluation"], "pdf_include", True)]
    buffer = BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm,
                          title=f"Informe postpartido · {match.home_team.name} - {match.away_team.name}", author=report.reporter.full_name,
                          subject=f"Postpartido · {report.rival_team.name}", creator=f"{club_name} · No Name PostMatch 3.6")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    def header_footer(canvas, current_doc):
        canvas.saveState(); page = current_doc.page
        if page > 1:
            canvas.setFillColor(dark); canvas.setFont(_FONT_BOLD, 7.3); canvas.drawString(18*mm, PAGE_H-11.5*mm, club_name.upper())
            canvas.setFillColor(HexColor("#64748B")); canvas.setFont(_FONT_REGULAR, 6.8); canvas.drawRightString(PAGE_W-18*mm, PAGE_H-11.5*mm, f"{match.home_team.name} - {match.away_team.name}")
            canvas.setStrokeColor(primary); canvas.line(18*mm, PAGE_H-14.5*mm, PAGE_W-18*mm, PAGE_H-14.5*mm)
        canvas.setStrokeColor(HexColor("#CBD5E1")); canvas.line(18*mm, 14.5*mm, PAGE_W-18*mm, 14.5*mm)
        canvas.setFillColor(dark); canvas.setFont(_FONT_BOLD, 6.2); canvas.drawString(18*mm, 9.5*mm, confidentiality.upper())
        canvas.setFillColor(HexColor("#64748B")); canvas.setFont(_FONT_REGULAR, 6.2); canvas.drawCentredString(PAGE_W/2, 9.5*mm, f"V{current_version} · FULL · {report.reporter.full_name}"); canvas.drawRightString(PAGE_W-18*mm, 9.5*mm, f"PÁGINA {page}")
        canvas.restoreState()
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=header_footer)])

    story = [MatchHeroV2(doc.width, club_name=club_name, report_subtitle=report_subtitle, home_name=match.home_team.name, away_name=match.away_team.name,
                         score=score, competition=match.competition.name, round_name=match.round_name,
                         match_date=match.match_date.strftime("%d/%m/%Y") if hasattr(match.match_date, "strftime") else str(match.match_date), rival_name=report.rival_team.name,
                         primary=primary, dark=dark, club_logo=_image_reader(settings.get("logo_b64")), home_logo=_image_reader(getattr(match.home_team, "logo_b64", None)), away_logo=_image_reader(getattr(match.away_team, "logo_b64", None))),
             Spacer(1, 5*mm), _kpi_table(payload, styles, primary, dark)]
    if report.opponent_overview or report.key_takeaways:
        story += [Spacer(1, 5*mm), _section_heading("Notas generales", styles, primary, dark, "Bloque opcional"), Spacer(1, 3*mm)]
        if report.opponent_overview:
            box = Table([[Paragraph("IMPRESIÓN GENERAL", styles["callout_label"]), Paragraph(_rich_text(report.opponent_overview, ""), styles["callout_text"])]], colWidths=[31*mm, 143*mm])
            box.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), HexColor("#F8FAFC")), ("BOX", (0,0), (-1,-1), .6, HexColor("#CBD5E1")), ("LINEBEFORE", (0,0), (0,0), 3.2, primary), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 5*mm), ("RIGHTPADDING", (0,0), (-1,-1), 5*mm), ("TOPPADDING", (0,0), (-1,-1), 3.5*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 3.5*mm)]))
            story.append(box)
        if report.key_takeaways:
            story += [Spacer(1, 3*mm), Paragraph(f"<b>IDEAS O NOMBRES A CONSERVAR</b><br/>{_rich_text(report.key_takeaways, '')}", styles["body"])]
    story += [Spacer(1, 5*mm), _section_heading("Jugadores destacados", styles, primary, dark, "Selección automática y manual"), Spacer(1, 3*mm), _watchlist_table(payload, styles, primary, dark)]
    consensus = _consensus_table(payload, styles, dark)
    if consensus:
        story += [Spacer(1, 5*mm), _section_heading("Consenso del cuerpo técnico", styles, primary, dark, "Informes aprobados"), Spacer(1, 3*mm), consensus]

    story += [PageBreak(), _section_heading("Contexto del partido", styles, primary, dark, "Onces iniciales y cambios"), Spacer(1, 4*mm)]
    pitches = Table([[FormationPitch(84*mm, payload["own_players"], report.own_team.name, match.home_formation if report.own_team_id == match.home_team_id else match.away_formation, primary, dark), FormationPitch(84*mm, payload["rival_players"], report.rival_team.name, match.home_formation if report.rival_team_id == match.home_team_id else match.away_formation, primary, dark)]], colWidths=[87*mm,87*mm])
    pitches.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 3*mm)])); story.append(pitches)
    story += [Spacer(1, 4*mm), Table([[_lineup_card(report.own_team.name, "Suplentes y minutos", payload["own_players"], styles, primary, dark), _lineup_card(report.rival_team.name, "Suplentes y minutos", payload["rival_players"], styles, primary, dark)]], colWidths=[86*mm,86*mm], style=[("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 2*mm)])]

    story += [PageBreak()]
    own = _own_team_table(payload, styles, dark)
    if own:
        story += [_section_heading(f"Valoraciones · {report.own_team.name}", styles, primary, dark, "Solo jugadores seleccionados para PDF"), Spacer(1,3*mm), own, Spacer(1,5*mm)]
    story += [_section_heading(f"Valoraciones · {report.rival_team.name}", styles, primary, dark, "Solo jugadores seleccionados para PDF"), Spacer(1, 3*mm), _player_overview_table(payload, styles, primary, dark)]
    if cards:
        story += [Spacer(1, 6*mm), _section_heading("Fichas individuales", styles, primary, dark, f"{len(cards)} perfiles seleccionados"), Spacer(1, 4*mm)]
        for row in cards:
            story.append(CondPageBreak(65*mm)); parts = _player_card(row, styles, primary, dark)
            story.append(KeepTogether(parts[:2])); story.extend(parts[2:])
    other = _other_observations_table(payload, styles, dark)
    if other:
        story.append(CondPageBreak(52*mm))
        story += [_section_heading("Registro de observación", styles, primary, dark, "Solo jugadores incluidos en PDF"), Spacer(1,3*mm), other, Spacer(1,5*mm)]
    story += [Spacer(1, 6*mm), Paragraph(f"Generado por <b>{_safe(report.reporter.full_name)}</b> · versión inmutable V{current_version} · modo full", styles["small_note"])]
    doc.build(story)
    return buffer.getvalue()
