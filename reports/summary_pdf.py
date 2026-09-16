from __future__ import annotations

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

from reports.full_pdf import _hex_to_color, _mix, _rich_text, _safe, _section_heading, _styles_v2, _summary_rows, _FONT_BOLD, _FONT_REGULAR, PAGE_H, PAGE_W

def generate_summary_pdf(payload: dict, *, current_version: int) -> bytes:
    """Daily 1-2 page PDF. No methodology, no player cards, no large cover."""
    report, match, settings = payload["report"], payload["match"], payload["settings"]
    primary = _hex_to_color(settings.get("primary_color"), "#B91C1C")
    dark = _hex_to_color(settings.get("secondary_color"), "#111827")
    club_name = settings.get("club_name") or "NO NAME"
    confidentiality = settings.get("report_confidentiality") or "Documento interno"
    styles = _styles_v2(primary, dark)
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=15*mm,
        title=f"Resumen postpartido · {match.home_team.name} - {match.away_team.name}",
        author=report.reporter.full_name, creator=f"{club_name} · No Name · Área Técnica",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="summary")

    def footer(canvas, current_doc):
        canvas.saveState()
        canvas.setStrokeColor(HexColor("#CBD5E1")); canvas.line(14*mm, 12*mm, PAGE_W-14*mm, 12*mm)
        canvas.setFillColor(HexColor("#64748B")); canvas.setFont(_FONT_REGULAR, 6.5)
        canvas.drawString(14*mm, 7.5*mm, confidentiality.upper())
        canvas.drawCentredString(PAGE_W/2, 7.5*mm, f"V{current_version} · RESUMEN · {report.reporter.full_name}")
        canvas.drawRightString(PAGE_W-14*mm, 7.5*mm, f"PÁGINA {current_doc.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="summary", frames=[frame], onPage=footer)])
    score = "-" if match.home_score is None or match.away_score is None else f"{match.home_score} - {match.away_score}"
    meta = f"{match.competition.name} · {match.round_name} · {match.match_date.strftime('%d/%m/%Y') if hasattr(match.match_date, 'strftime') else match.match_date}"
    header = Table([
        [Paragraph(f"<b>{_safe(club_name.upper())}</b> · RESUMEN POSTPARTIDO", styles["table_header"]), Paragraph(_safe(meta), styles["small_note"])],
        [Paragraph(f"<b>{_safe(match.home_team.name)}</b>", styles["section"]), Paragraph(f"<b>{_safe(score)}</b>", styles["table_score"])],
        [Paragraph(f"<b>{_safe(match.away_team.name)}</b>", styles["section"]), Paragraph(f"Informador · {_safe(report.reporter.full_name)}", styles["small_note"])],
    ], colWidths=[112*mm, 70*mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), dark), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("LINEBEFORE", (0,0), (0,-1), 4, primary), ("BOX", (0,0), (-1,-1), .5, HexColor("#CBD5E1")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 4*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 4*mm), ("TOPPADDING", (0,0), (-1,-1), 2.5*mm),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2.5*mm),
    ]))
    story = [header, Spacer(1, 5*mm)]

    own_table = _summary_rows(payload["own_players"], styles, primary, dark)
    rival_table = _summary_rows(payload["rival_players"], styles, primary, dark)
    if own_table:
        story += [_section_heading(f"{report.own_team.name}", styles, primary, dark, "Valoración interna"), Spacer(1,2*mm), own_table, Spacer(1,5*mm)]
    if rival_table:
        story += [_section_heading(f"{report.rival_team.name}", styles, primary, dark, "Observación rival"), Spacer(1,2*mm), rival_table]

    highlights = [
        row for row in payload["rival_players"] + payload["own_players"]
        if row.get("evaluation") and row["evaluation"].observation_status == "evaluated"
        and row["evaluation"].general_rating is not None and row["evaluation"].standout
    ]
    highlights.sort(key=lambda row: float(row["evaluation"].general_rating or 0), reverse=True)
    if highlights:
        story += [Spacer(1,5*mm), _section_heading("Destacados", styles, primary, dark, "Solo lo relevante"), Spacer(1,2*mm)]
        hdata = []
        for row in highlights[:6]:
            part, ev = row["participation"], row["evaluation"]
            name = part.player.display_name or part.player.full_name
            note = (ev.short_note or "Sin observación adicional.").strip()
            hdata.append([
                Paragraph(f"<b>{_safe(name)} · {float(ev.general_rating):.1f}</b>", styles["table_body"]),
                Paragraph(_rich_text(note, ""), styles["table_body"]),
            ])
        htable = Table(hdata, colWidths=[58*mm, 124*mm])
        htable.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), .25, HexColor("#D8E0E8")), ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("BACKGROUND", (0,0), (0,-1), _mix(primary, colors.white, .90)),
            ("TOPPADDING", (0,0), (-1,-1), 2.5*mm), ("BOTTOMPADDING", (0,0), (-1,-1), 2.5*mm),
            ("LEFTPADDING", (0,0), (-1,-1), 3*mm), ("RIGHTPADDING", (0,0), (-1,-1), 3*mm),
        ]))
        story.append(htable)

    doc.build(story)
    return buffer.getvalue()
