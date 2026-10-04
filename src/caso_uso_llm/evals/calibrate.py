"""Calibración del juez frente a una persona: acuerdo y kappa de Cohen por criterio y por rúbrica.

Lee evals/gold/calibracion_humana.csv (plantilla a ciegas generada por `just juez`) después de
que una persona rellene las columnas humano_* (1 = cumple, 0 = no cumple), y la cruza por id con
el veredicto del juez de CADA versión de la rúbrica (results/phase6_juez.json). Así la calibración
decide qué rúbrica se usa, en vez de suponerlo.

Kappa corrige el acuerdo que se daría por azar: con criterios que casi siempre se cumplen, un
95 % de acuerdo puede ser kappa ≈ 0.

Uso: uv run just calibrar
"""

import csv
import json
import math

from sklearn.metrics import cohen_kappa_score

from caso_uso_llm.evals.rubric import CRITERIOS, IDS, RUBRICS
from caso_uso_llm.paths import RESULTS, ROOT

CALIBRATION = ROOT / "evals" / "gold" / "calibracion_humana.csv"
CALIBRATION_MAP = ROOT / "evals" / "gold" / "calibracion_mapa.json"  # r01 -> "v1:coah-118"
REPORT = ROOT / "reports" / "phase6_calibracion.md"
NAMES = {c.id: c.nombre for c in CRITERIOS}


def _kappa(h: list[int], j: list[int]) -> float:
    if len(set(h)) == 1 and len(set(j)) == 1:
        return float("nan")  # nadie suspende (o todos): kappa no está definida
    return float(cohen_kappa_score(h, j))


def _fmt(k: float) -> str:
    return "nan" if math.isnan(k) else f"{k:.2f}"


def main() -> None:
    with CALIBRATION.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    filled = [r for r in rows if all(r[f"humano_{c}"].strip() in ("0", "1") for c in IDS)]
    pending = len(rows) - len(filled)
    if not filled:
        print(f"Sin etiquetas humanas todavía: rellena las columnas humano_* de {CALIBRATION.name} "
              "(1 = cumple, 0 = no cumple).")  # fmt: skip
        return
    judged = json.loads((RESULTS / "phase6_juez.json").read_text(encoding="utf-8"))
    versions = [v for v in RUBRICS if v in judged["rubrics"]]
    # El id de la plantilla es "<versión del prompt>:<id de la reseña>"
    verdicts = {
        v: {
            f"{pv}:{r['id']}": r["verdict"]
            for pv, rs in judged["rubrics"][v]["phase4"].items()
            for r in rs
        }
        for v in versions
    }
    mapping = json.loads(CALIBRATION_MAP.read_text(encoding="utf-8"))
    for r in filled:
        r["id"] = mapping[r["id"]]
    human = {c: [int(r[f"humano_{c}"]) for r in filled] for c in IDS}

    L = [
        "# Calibración del juez frente a revisión humana",
        "",
        f"Generado por `uv run just calibrar` · {len(filled)} de {len(rows)} respuestas etiquetadas"
        + (f" ({pending} sin terminar, no cuentan)" if pending else "")
        + ". No editar a mano.",
        "",
        "Kappa de Cohen por criterio y por versión de la rúbrica (más alto = más acuerdo con la "
        "persona). Entre paréntesis: cuántas respuestas suspende la persona / el juez.",
        "",
        "| Criterio | Humano suspende | " + " | ".join(f"Rúbrica {v}" for v in versions) + " |",
        "|---|---|" + "---|" * len(versions),
    ]
    summary = {v: [] for v in versions}
    for c in IDS:
        cells = []
        for v in versions:
            j = [0 if not verdicts[v][r["id"]][c]["cumple"] else 1 for r in filled]
            k = _kappa(human[c], j)
            summary[v].append(k)
            agree = sum(a == b for a, b in zip(human[c], j, strict=True)) / len(j)
            cells.append(f"{_fmt(k)} · {agree:.0%} ({j.count(0)})")
        L.append(f"| {NAMES[c]} | {human[c].count(0)} | " + " | ".join(cells) + " |")
    L += ["", "| Resumen | " + " | ".join(versions) + " |", "|---|" + "---|" * len(versions)]
    for label, fn in (
        (
            "Criterios con kappa ≥ 0,6 (fiables)",
            lambda ks: sum(k >= 0.6 for k in ks if not math.isnan(k)),
        ),
        (
            "Criterios con kappa < 0,4 (no fiables)",
            lambda ks: sum(k < 0.4 for k in ks if not math.isnan(k)),
        ),
        ("Criterios sin kappa (nadie suspende)", lambda ks: sum(math.isnan(k) for k in ks)),
    ):
        L.append(f"| {label} | " + " | ".join(str(fn(summary[v])) for v in versions) + " |")
    disagreements = []
    best = max(versions, key=lambda v: sum(k for k in summary[v] if not math.isnan(k)))
    for r in filled:
        for c in IDS:
            jv = verdicts[best][r["id"]][c]
            if int(r[f"humano_{c}"]) != int(jv["cumple"]):
                disagreements.append(
                    (r["id"], c, r[f"humano_{c}"], jv["evidencia"], r.get("notas", ""))
                )
    L += ["", f"## Desacuerdos con la rúbrica {best} (la de más acuerdo)", "",
          "| Respuesta | Criterio | Humano | Evidencia del juez | Notas humanas |",
          "|---|---|---|---|---|"]  # fmt: skip
    for i, c, h, e, n in disagreements:
        verdict = "cumple" if h == "1" else "no cumple"
        L.append(f"| `{i}` | {NAMES[c]} | {verdict} | {e[:120] or '—'} | {n or '—'} |")
    L += ["", "Kappa: < 0,4 pobre · 0,4–0,6 moderado · 0,6–0,8 bueno · > 0,8 muy bueno. Con 24 "
          "respuestas el intervalo es amplio: sirve para separar criterios claramente fiables de "
          "claramente no fiables."]  # fmt: skip
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"OK: reports/{REPORT.name} · rúbrica con más acuerdo: {best}")


if __name__ == "__main__":
    main()
