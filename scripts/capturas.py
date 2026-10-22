"""Capturas de la demo para el README (Playwright; no es dependencia del proyecto).

Con la app en marcha (`uv run just app`), procesa un caso sintético cuya respuesta ya está en
caché y captura las dos pestañas en docs/img/.

Uso:
    uv run --with playwright playwright install chromium     # una vez
    uv run --with playwright python scripts/capturas.py
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
URL = "http://127.0.0.1:7860/?__theme=light"
CASE = "rag-carteles"  # la ficha tienta a negar al cliente; va a revisión humana


def main() -> None:
    rag = json.loads((ROOT / "evals" / "adversarial" / "rag_v1.json").read_text(encoding="utf-8"))
    case = next(c for c in rag["cases"] if c["id"] == CASE)
    with sync_playwright() as p:
        page = p.chromium.launch().new_page(viewport={"width": 1400, "height": 1000})
        page.goto(URL)
        hotel = page.get_by_label("Hotel")
        hotel.click()
        page.get_by_role("option", name=case["hotel"], exact=False).first.click()
        page.get_by_label("Reseña", exact=True).fill(case["review"])
        page.get_by_role("button", name="Generar respuesta").click()
        page.get_by_text("revisión humana", exact=False).first.wait_for(timeout=600_000)
        page.get_by_text("Detalle del pipeline").click()
        page.wait_for_timeout(800)
        page.screenshot(path=OUT / "demo_respuesta.png", full_page=True)

        page.get_by_role("tab", name="Cola de revisión").click()
        page.wait_for_timeout(1500)
        selector = page.get_by_label("Reseña a revisar")
        selector.click()
        page.get_by_role("option", name=CASE, exact=False).first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "demo_cola.png", full_page=True)
    print(sorted(p.name for p in OUT.glob("demo_*.png")))


if __name__ == "__main__":
    main()
