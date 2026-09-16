from __future__ import annotations

import base64
import math
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

PAGE_W, PAGE_H = A4


def _safe(value) -> str:
    return escape(str(value or ""))


def _fmt(value, digits: int = 1) -> str:
    return "-" if value is None else f"{float(value):.{digits}f}"


def _hex(value: str | None, fallback: str) -> colors.Color:
    try:
        return HexColor(value or fallback)
    except Exception:
        return HexColor(fallback)


def _styles(primary, dark):
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("p360title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=dark, spaceAfter=2*mm),
        "subtitle": ParagraphStyle("p360subtitle", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=HexColor("#64748B")),
        "section": ParagraphStyle("p360section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=dark, spaceBefore=3*mm, spaceAfter=2*mm),
        "body": ParagraphStyle("p360body", parent=base["BodyText"], fontSize=8.3, leading=11.2, textColor=HexColor("#374151")),
        "small": ParagraphStyle("p360small", parent=base["BodyText"], fontSize=7.1, leading=9, textColor=HexColor("#64748B")),
        "white": ParagraphStyle("p360white", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=colors.white),
        "kpi": ParagraphStyle("p360kpi", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=15.5, leading=17, alignment=1, textColor=dark),
        "kpilabel": ParagraphStyle("p360kpilabel", parent=base["BodyText"], fontSize=6.8, leading=8, alignment=1, textColor=HexColor("#64748B")),
        "criterion": ParagraphStyle("p360criterion", parent=base["BodyText"], fontSize=7.6, leading=9.2, textColor=HexColor("#374151")),
    }


def _image(encoded: str | None, mime: str | None, width=18*mm, height=18*mm):
    if not encoded:
        return None
    try:
        data = base64.b64decode(encoded)
        return Image(BytesIO(data), width=width, height=height, kind="proportional")
    except Exception:
        return None


class RadarChart(Flowable):
    def __init__(self, rows: list[dict], width=76*mm, height=65*mm):
        super().__init__()
        self.rows = [r for r in rows if r.get("score") is not None][:10]
        self.width = width
        self.height = height

    def draw(self):
        if len(self.rows) < 3:
            return
        c = self.canv
        cx, cy = self.width/2, self.height/2
        radius = min(self.width, self.height) * .31
        n = len(self.rows)
        c.saveState()
        for level in range(1, 6):
            rr = radius * level/5
            pts=[]
            for i in range(n):
                a=-math.pi/2 + 2*math.pi*i/n
                pts.append((cx+rr*math.cos(a), cy+rr*math.sin(a)))
            p=c.beginPath(); p.moveTo(*pts[0])
            for point in pts[1:]: p.lineTo(*point)
            p.close(); c.setStrokeColor(HexColor("#D8DEE8")); c.setLineWidth(.45); c.drawPath(p)
        value=[]
        for i,row in enumerate(self.rows):
            a=-math.pi/2 + 2*math.pi*i/n
            x2,y2=cx+radius*math.cos(a), cy+radius*math.sin(a)
            c.setStrokeColor(HexColor("#E5E7EB")); c.line(cx,cy,x2,y2)
            vr=radius*max(0,min(10,float(row["score"])))/10
            value.append((cx+vr*math.cos(a), cy+vr*math.sin(a)))
            lr=radius*1.28; lx,ly=cx+lr*math.cos(a),cy+lr*math.sin(a)
            c.setFillColor(HexColor("#596273")); c.setFont("Helvetica",5.6)
            label=str(row["name"])[:19]
            if math.cos(a) > .25: c.drawString(lx,ly,label)
            elif math.cos(a) < -.25: c.drawRightString(lx,ly,label)
            else: c.drawCentredString(lx,ly,label)
        p=c.beginPath(); p.moveTo(*value[0])
        for point in value[1:]: p.lineTo(*point)
        p.close(); c.setFillColor(colors.Color(.145,.388,.922,alpha=.18)); c.setStrokeColor(HexColor("#2563EB")); c.setLineWidth(1.4); c.drawPath(p,fill=1,stroke=1)
        c.restoreState()


def _footer(canvas, doc, club_name: str, version: str, label: str):
    canvas.saveState()
    canvas.setStrokeColor(HexColor("#D7DEE7")); canvas.line(14*mm, 11*mm, PAGE_W-14*mm, 11*mm)
    canvas.setFillColor(HexColor("#64748B")); canvas.setFont("Helvetica", 6.5)
    canvas.drawString(14*mm, 6.5*mm, f"{club_name.upper()} · DOCUMENTO INTERNO")
    canvas.drawCentredString(PAGE_W/2, 6.5*mm, label)
    canvas.drawRightString(PAGE_W-14*mm, 6.5*mm, f"PÁGINA {doc.page}")
    canvas.restoreState()


def _doc(settings: dict, label: str):
    primary = _hex(settings.get("primary_color"), "#B91C1C")
    dark = _hex(settings.get("secondary_color"), "#111827")
    club = settings.get("club_name") or "NO NAME"
    buffer=BytesIO()
    doc=BaseDocTemplate(buffer,pagesize=A4,leftMargin=14*mm,rightMargin=14*mm,topMargin=14*mm,bottomMargin=16*mm)
    frame=Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id="main")
    doc.addPageTemplates([PageTemplate(id="main",frames=[frame],onPage=lambda c,d:_footer(c,d,club,"",label))])
    return buffer,doc,_styles(primary,dark),primary,dark,club


def _hero(payload: dict, styles, primary, dark):
    player=payload["player"]; role=payload.get("role"); post=payload["postmatch"]
    photo=_image(player.photo_b64,player.photo_mime)
    ident=[photo or Paragraph("<b>NN</b>",styles["kpi"]), Paragraph(
        f'<font size="7" color="{primary.hexval()}"><b>PLAYER REPORT 360</b></font><br/><font size="17"><b>{_safe(player.display_name or player.full_name)}</b></font><br/>'
        f'<font size="8" color="#64748B">{_safe(player.primary_position or "Sin posición")} · {_safe(payload["team"].name if payload.get("team") else "Equipo no confirmado")}</font><br/>'
        f'<font size="7.5" color="#3730A3">{_safe((role.position+" · "+role.name) if role else "Rol No Name por definir")}</font>',styles["body"])]
    left=Table([ident],colWidths=[20*mm,78*mm]); left.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),2*mm)]))
    kpis=Table([
        [Paragraph("RENDIMIENTO",styles["kpilabel"]),Paragraph("ENCAJE",styles["kpilabel"]),Paragraph("CONFIANZA",styles["kpilabel"])],
        [Paragraph(_fmt(post["average"]),styles["kpi"]),Paragraph(_fmt(payload.get("fit_score")),styles["kpi"]),Paragraph(f'{post["confidence"]["score"]}/100' if post["confidence"]["sample"] else "No evaluable",styles["kpi"])],
        [Paragraph(f'{post["observations"]} postpartidos',styles["kpilabel"]),Paragraph(_safe(role.name if role else "sin rol"),styles["kpilabel"]),Paragraph(_safe(post["confidence"]["label"]),styles["kpilabel"])],
    ],colWidths=[26*mm]*3)
    kpis.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,HexColor("#E5E7EB")),("INNERGRID",(0,0),(-1,-1),.25,HexColor("#EEF1F4")),("BACKGROUND",(0,0),(-1,-1),HexColor("#FAFBFC")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),2*mm),("BOTTOMPADDING",(0,0),(-1,-1),2*mm)]))
    hero=Table([[left,kpis]],colWidths=[100*mm,78*mm])
    hero.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.7,HexColor("#DDE2E8")),("LINEBEFORE",(0,0),(0,-1),4,primary),("BACKGROUND",(0,0),(-1,-1),colors.white),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),4*mm),("RIGHTPADDING",(0,0),(-1,-1),4*mm),("TOPPADDING",(0,0),(-1,-1),4*mm),("BOTTOMPADDING",(0,0),(-1,-1),4*mm)]))
    return hero


def _section(title, styles):
    return Paragraph(_safe(title.upper()),styles["section"])


def _summary_block(payload, styles):
    summary=payload.get("summary") or "Sin conclusión consolidada todavía."
    table=Table([[Paragraph("<b>CONCLUSIÓN</b><br/>"+_safe(summary).replace("\n","<br/>"),styles["body"]) ]],colWidths=[178*mm])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),HexColor("#F8FAFC")),("BOX",(0,0),(-1,-1),.5,HexColor("#DDE2E8")),("LEFTPADDING",(0,0),(-1,-1),4*mm),("RIGHTPADDING",(0,0),(-1,-1),4*mm),("TOPPADDING",(0,0),(-1,-1),3*mm),("BOTTOMPADDING",(0,0),(-1,-1),3*mm)]))
    return table


def _strengths_table(payload, styles):
    def text(items, fallback):
        return "<br/>".join(f"• {_safe(x)}" for x in items) if items else fallback
    data=[[Paragraph("<b>FORTALEZAS</b><br/>"+text(payload["strengths"],"Sin fortalezas consolidadas."),styles["body"]),Paragraph("<b>DUDAS / RIESGOS</b><br/>"+text(payload["weaknesses"],"Sin riesgos registrados."),styles["body"])]]
    t=Table(data,colWidths=[89*mm,89*mm]); t.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,HexColor("#DDE2E8")),("INNERGRID",(0,0),(-1,-1),.5,HexColor("#E5E7EB")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4*mm),("RIGHTPADDING",(0,0),(-1,-1),4*mm),("TOPPADDING",(0,0),(-1,-1),3*mm),("BOTTOMPADDING",(0,0),(-1,-1),3*mm)])); return t


def _criteria_block(payload, styles):
    rows=payload["criteria"]
    radar=RadarChart(rows)
    if len([r for r in rows if r.get("score") is not None]) < 3:
        radar=Paragraph("No hay al menos 3 criterios puntuados. No se completa el radar con valores inventados.",styles["small"])
    data=[[Paragraph("<b>CRITERIO</b>",styles["small"]),Paragraph("<b>BLOQUE</b>",styles["small"]),Paragraph("<b>PESO</b>",styles["small"]),Paragraph("<b>NOTA</b>",styles["small"])]]
    for row in rows[:10]:
        data.append([Paragraph(_safe(row["name"]),styles["criterion"]),Paragraph(_safe(row["category"]),styles["criterion"]),str(row["weight"]),"-" if row.get("score") is None else f'{row["score"]:.1f}'])
    table=Table(data,colWidths=[45*mm,22*mm,12*mm,14*mm],repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#F1F5F9")),("GRID",(0,0),(-1,-1),.35,HexColor("#DDE2E8")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("FONTSIZE",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),1.8*mm),("BOTTOMPADDING",(0,0),(-1,-1),1.8*mm)]))
    return Table([[radar,table]],colWidths=[82*mm,96*mm],style=[("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),2*mm)])


def generate_player_executive_pdf(payload: dict, settings: dict) -> bytes:
    buffer,doc,styles,primary,dark,club=_doc(settings,"FICHA SCOUT EJECUTIVA")
    story=[_hero(payload,styles,primary,dark),Spacer(1,4*mm),_summary_block(payload,styles),Spacer(1,3*mm),_strengths_table(payload,styles),Spacer(1,3*mm)]
    role=payload.get("role")
    if role:
        story += [_section(f"Modelo No Name · {role.position} · {role.name}",styles),_criteria_block(payload,styles),Spacer(1,3*mm)]
    rec=payload.get("recommendation") or "Sin decidir"
    decision=Table([[Paragraph(f'<b>RECOMENDACIÓN / DECISIÓN</b><br/><font size="12">{_safe(rec)}</font>',styles["body"]),Paragraph(f'<b>Nivel actual</b><br/>{_fmt(payload.get("current_level"))}<br/><b>Proyección</b><br/>{_fmt(payload.get("potential_score"))}',styles["body"]) ]],colWidths=[122*mm,56*mm])
    decision.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),HexColor("#F8FAFC")),("BOX",(0,0),(-1,-1),.5,HexColor("#DDE2E8")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4*mm),("TOPPADDING",(0,0),(-1,-1),3*mm),("BOTTOMPADDING",(0,0),(-1,-1),3*mm)])); story.append(decision)
    doc.build(story); return buffer.getvalue()


def generate_player_360_pdf(payload: dict, settings: dict) -> bytes:
    buffer,doc,styles,primary,dark,club=_doc(settings,"DOSSIER PLAYER REPORT 360")
    story=[_hero(payload,styles,primary,dark),Spacer(1,4*mm),_summary_block(payload,styles),Spacer(1,3*mm),_strengths_table(payload,styles)]
    role=payload.get("role")
    if role:
        story += [_section(f"Modelo No Name · {role.position} · {role.name}",styles),_criteria_block(payload,styles)]
    if payload.get("is_own_player"):
        story += [_section("Rendimiento de la plantilla", styles)]
        own = payload["own_postmatch"]
        story.append(Paragraph(
            f"Postpartidos evaluados: {own['observations']} · Informadores: {own['reporters']} · "
            f"Media: {_fmt(own['average'])}. No corresponde a seguimiento de mercado.", styles["body"]))
    else:
        story += [_section("Seguimiento de jugador externo",styles)]
        blocks=payload["block_scores"]
        profile_data=[["Técnico",_fmt(blocks.get("Técnico")),"Táctico",_fmt(blocks.get("Táctico")),"Físico",_fmt(blocks.get("Físico")),"Mental",_fmt(blocks.get("Mental"))],
                      ["Nivel actual",_fmt(payload.get("current_level")),"Proyección",_fmt(payload.get("potential_score")),"Media seguimiento",_fmt(payload.get("scout_average")),"Evidencia",payload["evidence"]["specific_strength"]]]
        pt=Table(profile_data,colWidths=[22*mm,20*mm]*4); pt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.35,HexColor("#DDE2E8")),("BACKGROUND",(0,0),(-1,-1),colors.white),("FONTSIZE",(0,0),(-1,-1),7.2),("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("TOPPADDING",(0,0),(-1,-1),2*mm),("BOTTOMPADDING",(0,0),(-1,-1),2*mm)])); story.append(pt)

    story += [_section("Posiciones observadas",styles)]
    if payload["positions"]:
        pos=Table([["Posición","Observaciones"]]+[[r["position"],r["observations"]] for r in payload["positions"]],colWidths=[60*mm,40*mm]); pos.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.35,HexColor("#DDE2E8")),("BACKGROUND",(0,0),(-1,0),HexColor("#F1F5F9")),("FONTSIZE",(0,0),(-1,-1),7.4)])); story.append(pos)

    story += [PageBreak(),_section("Evolución de observaciones",styles)]
    timeline=payload["timeline"]
    if timeline:
        data=[["Fecha","Fuente","Partido","POS","Nota","Observador","Apunte"]]
        for row in reversed(timeline):
            data.append([str(row["date"]),row["source"],row["match"],row["position"] or "-",f'{row["rating"]:.1f}',row["observer"],Paragraph(_safe(row["note"] or ""),styles["small"])])
        t=Table(data,colWidths=[18*mm,25*mm,40*mm,14*mm,12*mm,28*mm,41*mm],repeatRows=1)
        t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.25,HexColor("#DDE2E8")),("BACKGROUND",(0,0),(-1,0),HexColor("#F1F5F9")),("FONTSIZE",(0,0),(-1,-1),6.3),("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),1.4*mm),("BOTTOMPADDING",(0,0),(-1,-1),1.4*mm)])); story.append(t)
    else: story.append(Paragraph("Sin evolución disponible.",styles["body"]))

    story += [_section("Comparación contextual",styles)]
    for title,key in [("Nuestra plantilla","own_comparison"),("Perfiles similares de nuestra liga","comparables")]:
        story.append(Paragraph(f"<b>{_safe(title)}</b>",styles["body"]))
        rows=payload[key]
        if rows:
            data=[["Jugador","Encaje","Nivel","Proyección","Estado","Similitud"]]+[[r["name"],_fmt(r["fit"]),_fmt(r["current_level"]),_fmt(r["potential"]),r["status"],"-" if r.get("similarity") is None else f'{r["similarity"]}%'] for r in rows]
            t=Table(data,colWidths=[50*mm,20*mm,20*mm,22*mm,32*mm,22*mm]); t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.25,HexColor("#DDE2E8")),("BACKGROUND",(0,0),(-1,0),HexColor("#F1F5F9")),("FONTSIZE",(0,0),(-1,-1),6.8)])); story.append(t)
        else: story.append(Paragraph("Sin perfiles comparables con datos suficientes.",styles["small"]))
        story.append(Spacer(1,2*mm))

    story += [_section("Datos disponibles",styles)]
    p=payload["player"]
    data=[
        ["Nombre",p.display_name or p.full_name,"Equipo",payload["team"].name if payload.get("team") else "-"],
        ["Posición",p.primary_position or "-","Edad",payload.get("age") if payload.get("age") is not None else "-"],
        ["Fecha nacimiento",p.date_of_birth.strftime("%d/%m/%Y") if p.date_of_birth else "-","Pie",p.preferred_foot or "-"],
        ["Nacionalidad",p.nationality or "-","Decisión",payload.get("recommendation") or "Sin decidir"],
    ]
    dt=Table(data,colWidths=[28*mm,61*mm,28*mm,61*mm]); dt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.25,HexColor("#DDE2E8")),("BACKGROUND",(0,0),(-1,-1),colors.white),("FONTSIZE",(0,0),(-1,-1),7.2),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),("TOPPADDING",(0,0),(-1,-1),2*mm),("BOTTOMPADDING",(0,0),(-1,-1),2*mm)])); story.append(dt)
    story.append(Spacer(1,2*mm)); story.append(Paragraph("Solo se incluyen los datos registrados por el cuerpo técnico; no se estiman datos no observados.",styles["small"]))
    doc.build(story); return buffer.getvalue()


def player_report_filename(payload: dict, kind: str = "executive") -> str:
    name=(payload["player"].display_name or payload["player"].full_name).strip().replace(" ","_")
    suffix="Ficha_Scout" if kind == "executive" else "Player_Report_360"
    return f"{suffix}_{name}.pdf"
