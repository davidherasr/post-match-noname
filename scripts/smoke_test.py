from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_sample import main as generate_sample


def main() -> None:
    generate_sample()
    full_pdf = ROOT / "sample" / "informe_demo_postmatch_scout_2_0_completo.pdf"
    executive_pdf = ROOT / "sample" / "informe_demo_postmatch_scout_2_0_ejecutivo.pdf"
    if not full_pdf.exists() or full_pdf.stat().st_size < 10_000:
        raise RuntimeError("No se generó correctamente el PDF completo.")
    if not executive_pdf.exists() or executive_pdf.stat().st_size < 10_000:
        raise RuntimeError("No se generó correctamente el PDF ejecutivo.")
    print(f"OK · Smoke test 2.0 · completo={full_pdf.stat().st_size} bytes · ejecutivo={executive_pdf.stat().st_size} bytes")


if __name__ == "__main__":
    main()
