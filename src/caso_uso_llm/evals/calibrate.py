"""Calibración del juez frente a una persona: acuerdo y kappa de Cohen por criterio.

Lee evals/gold/calibracion_humana.csv (generado por `just juez`) después de que una persona
rellene las columnas humano_* (1 = cumple, 0 = no cumple). Kappa corrige el acuerdo que se daría
por azar: con criterios que casi siempre se cumplen, un 95 % de acuerdo puede ser kappa ≈ 0.

Uso: uv run just calibrar
"""

import csv

from sklearn.metrics import cohen_kappa_score

from caso_uso_llm.evals.rubric import CRITERIOS, IDS
from caso_uso_llm.paths import ROOT

CALIBRATION = ROOT / "evals" / "gold" / "calibracion_humana.csv"
REPORT = ROOT / "reports" / "phase6_calibracion.md"


def main() -> None:
    with CALIBRATION.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    filled = [r for r in rows if all(r[f"humano_{c}"].strip() in ("0", "1") for c in IDS)]
    if not filled:
        print(f"Sin etiquetas humanas todavía: rellena las columnas humano_* de {CALIBRATION.name} "
              "(1 = cumple, 0 = no cumple).")  # fmt: skip
        return
    names = {c.id: c.nombre for c in CRITERIOS}
    L = [
        "# Calibración del juez frente a revisión humana",
        "",
        f"Generado por `uv run just calibrar` · {len(filled)} de {len(rows)} respuestas etiquetadas. "
        "No editar a mano.",
        "",
        "| Criterio | Acuerdo | Kappa | Humano suspende | Juez suspende | Ambos |",
        "|---|---|---|---|---|---|",
    ]
    for c in IDS:
        h = [int(r[f"humano_{c}"]) for r in filled]
        j = [int(r[f"juez_{c}"]) for r in filled]
        agree = sum(a == b for a, b in zip(h, j, strict=True)) / len(h)
        kappa = cohen_kappa_score(h, j) if len(set(h)) > 1 or len(set(j)) > 1 else float("nan")
        both = sum(a == 0 and b == 0 for a, b in zip(h, j, strict=True))
        L.append(
            f"| {names[c]} | {agree:.0%} | {kappa:.2f} | {h.count(0)} | {j.count(0)} | {both} |"
        )
    L += ["", "Kappa: < 0,4 pobre · 0,4–0,6 moderado · 0,6–0,8 bueno · > 0,8 muy bueno. "
          "«nan»: nadie suspendió nada en ese criterio (no se puede calcular)."]  # fmt: skip
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"OK: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
