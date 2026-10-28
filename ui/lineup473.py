"""Read-only mobile-friendly lineup preview (no fabricated formations)."""
from html import escape

# Coordinates represent *declared* match positions, never estimated identities.
_COORDS = {
 'POR':(50,92), 'LD':(12,75), 'DCD':(38,75), 'DCC':(50,75),
 'DCI':(62,75), 'DFC':(50,75), 'LI':(88,75),
 'CAD':(12,65), 'CAI':(88,65), 'MCD':(38,53), 'MCC':(50,53),
 'MCI':(62,53), 'MC':(50,53), 'MD':(17,47), 'MI':(83,47),
 'ED':(14,28), 'EI':(86,28), 'MP':(50,31), 'SD':(57,18),
 'DC':(50,12),
}


def lineup_svg(rows: list[dict]) -> str:
    """Generate static SVG with escaped names; rows provided by reviewed XI."""
    points=[]
    occurrences={}
    for row in rows:
        pos=str(row['Posición'])
        x,y=_COORDS.get(pos,(50,50))
        seen=occurrences.get(pos,0);occurrences[pos]=seen+1
        if seen:x=min(93,max(7,x + (16*((seen+1)//2)) * (-1 if seen%2 else 1)))
        nr=escape(str(row['Dorsal']))
        original=str(row['Jugador'])
        nm=escape(original)
        caption=escape(pos)
        px=x*3.8+10;py=y*4.8+8
        # long names stay in the accessible title even if visually shortened
        short=escape(original if len(original)<=18 else original[:15]+'…')
        points.append(f'<g><title>{nm} · {caption}</title><circle cx="{px:.0f}" cy="{py:.0f}" r="18" fill="#faf8f1" stroke="#295f4a" stroke-width="2"/>'
                      f'<text x="{px:.0f}" y="{py+5:.0f}" text-anchor="middle" font-size="14" font-weight="700" fill="#183f30">{nr}</text>'
                      f'<text x="{px:.0f}" y="{py+30:.0f}" font-size="10" text-anchor="middle" fill="white">{short}</text></g>')
    return ('''<svg viewBox="0 0 400 515" role="img" aria-label="Alineación con posición por futbolista" style="width:100%;height:auto;max-width:420px;border-radius:12px;display:block;margin:0 auto;background:#236449">
    <rect x="8" y="8" width="384" height="499" rx="5" fill="none" stroke="#ffffff88" stroke-width="2"/>
    <path d="M8 258 H392 M110 8 V75 H290 V8 M110 507 V439 H290 V507" fill="none" stroke="#ffffff77" stroke-width="2" />
    <circle cx="200" cy="258" r="49" fill="none" stroke="#ffffff77" stroke-width="2"/>'''+''.join(points)+'</svg>')
