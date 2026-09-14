from __future__ import annotations

from html import escape

import streamlit as st

from core.formations import slots_for

# Coordinates are percentages inside a vertical pitch (our goal at the bottom).
# The sequence matches core.formations.slots_for for each supported system.
_FORMATION_COORDS: dict[str, list[tuple[float, float]]] = {
    "4-3-3": [(50,90),(86,72),(62,74),(38,74),(14,72),(50,55),(67,45),(33,45),(82,24),(50,16),(18,24)],
    "4-2-3-1": [(50,90),(86,72),(62,74),(38,74),(14,72),(63,55),(37,55),(82,34),(50,31),(18,34),(50,13)],
    "4-4-2": [(50,90),(86,72),(62,74),(38,74),(14,72),(84,45),(62,48),(38,48),(16,45),(62,17),(38,17)],
    "4-1-4-1": [(50,90),(86,72),(62,74),(38,74),(14,72),(50,59),(84,40),(62,43),(38,43),(16,40),(50,13)],
    "4-3-1-2": [(50,90),(86,72),(62,74),(38,74),(14,72),(50,58),(66,46),(34,46),(50,31),(62,14),(38,14)],
    "4-4-1-1": [(50,90),(86,72),(62,74),(38,74),(14,72),(84,47),(62,49),(38,49),(16,47),(50,29),(50,12)],
    "3-4-3": [(50,90),(70,73),(50,76),(30,73),(88,49),(61,50),(39,50),(12,49),(82,22),(50,13),(18,22)],
    "3-4-2-1": [(50,90),(70,73),(50,76),(30,73),(88,49),(61,50),(39,50),(12,49),(66,28),(34,28),(50,11)],
    "3-5-2": [(50,90),(70,73),(50,76),(30,73),(90,49),(50,58),(65,44),(35,44),(10,49),(62,14),(38,14)],
    "3-1-4-2": [(50,90),(70,73),(50,76),(30,73),(50,61),(88,47),(62,45),(38,45),(12,47),(62,14),(38,14)],
    "5-4-1": [(50,90),(90,68),(70,73),(50,76),(30,73),(10,68),(84,43),(62,46),(38,46),(16,43),(50,12)],
    "5-3-2": [(50,90),(90,68),(70,73),(50,76),(30,73),(10,68),(50,55),(65,42),(35,42),(62,14),(38,14)],
}


def render_campogram(formation: str, players_by_slot: list[dict], *, title: str | None = None) -> None:
    slots = slots_for(formation)
    coords = _FORMATION_COORDS.get(formation)
    if not slots or not coords or len(coords) != len(slots):
        st.info("No hay campograma disponible para esta formación.")
        return
    nodes = []
    for idx, (slot, (x, y)) in enumerate(zip(slots, coords)):
        row = players_by_slot[idx] if idx < len(players_by_slot) else {}
        name = escape(str(row.get("name") or "—"))
        shirt = row.get("shirt_number")
        dorsal = f"#{int(shirt)} · " if shirt is not None else ""
        label = escape(slot.code)
        nodes.append(
            f'<div class="nn-player" style="left:{x}%;top:{y}%">'
            f'<span class="nn-dot">{escape(str(shirt)) if shirt is not None else label}</span>'
            f'<span class="nn-name">{dorsal}{name}</span></div>'
        )
    heading = f'<div class="nn-pitch-title">{escape(title)}</div>' if title else ""
    html = f"""
    {heading}
    <div class="nn-pitch">
      <div class="nn-half"></div><div class="nn-circle"></div>
      <div class="nn-box nn-box-top"></div><div class="nn-box nn-box-bottom"></div>
      {''.join(nodes)}
    </div>
    <style>
      .nn-pitch-title{{font-weight:700;margin:.2rem 0 .55rem 0}}
      .nn-pitch{{position:relative;width:100%;height:560px;border:2px solid rgba(120,120,120,.55);border-radius:18px;background:linear-gradient(180deg,rgba(43,118,67,.15),rgba(43,118,67,.06));overflow:hidden}}
      .nn-half{{position:absolute;left:0;right:0;top:50%;border-top:1px solid rgba(120,120,120,.45)}}
      .nn-circle{{position:absolute;left:42%;top:42%;width:16%;height:16%;border:1px solid rgba(120,120,120,.45);border-radius:50%}}
      .nn-box{{position:absolute;left:25%;width:50%;height:14%;border:1px solid rgba(120,120,120,.45)}}
      .nn-box-top{{top:-1px}} .nn-box-bottom{{bottom:-1px}}
      .nn-player{{position:absolute;transform:translate(-50%,-50%);width:28%;text-align:center;z-index:2}}
      .nn-dot{{display:inline-flex;width:34px;height:34px;align-items:center;justify-content:center;border-radius:50%;background:var(--primary-color,#1f77b4);color:white;font-size:.78rem;font-weight:800;border:2px solid rgba(255,255,255,.9);box-shadow:0 2px 6px rgba(0,0,0,.2)}}
      .nn-name{{display:block;margin-top:3px;padding:2px 5px;background:rgba(255,255,255,.88);color:#111;border-radius:7px;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 1px 4px rgba(0,0,0,.12)}}
      @media(max-width:700px){{.nn-pitch{{height:470px}}.nn-player{{width:34%}}.nn-name{{font-size:.66rem}}}}
    </style>
    """
    st.markdown(html, unsafe_allow_html=True)
