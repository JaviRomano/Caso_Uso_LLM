"""Acuerdo entre anotadores y con el juez: humano (calibracion_humana.csv) frente a un segundo
anotador a ciegas (CSV con el mismo formato) y frente a cada rúbrica del juez.

El segundo anotador por defecto (calibracion_segundo_anotador.csv) es un LLM (Claude Opus en un
contexto limpio) que solo vio la guía, las reseñas y las respuestas: ni las etiquetas humanas ni
el juez. Las etiquetas humanas se corrigieron después a partir de sus desacuerdos, así que el
acuerdo humano-segundo anotador ya no es independiente; la primera pasada humana está en
calibracion_primera_pasada.csv.

Uso: python scripts/acuerdo_anotadores.py [RUTA_CSV]
"""

import csv
import json
import math
import sys
from pathlib import Path

from sklearn.metrics import cohen_kappa_score

from caso_uso_llm.evals.rubric import IDS, RUBRICS
from caso_uso_llm.paths import RESULTS, ROOT

HUMAN = ROOT / "evals" / "gold" / "calibracion_humana.csv"
MAPPING = ROOT / "evals" / "gold" / "calibracion_mapa.json"
SECOND = ROOT / "evals" / "gold" / "calibracion_segundo_anotador.csv"


def read(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f, delimiter=";")}


def kappa(a: list[int], b: list[int]) -> str:
    if len(set(a)) == 1 and len(set(b)) == 1:
        return "nan"  # nadie suspende (o todos): kappa no está definida
    k = float(cohen_kappa_score(a, b))
    return "nan" if math.isnan(k) else f"{k:.2f}"


def main(blind_path: str) -> None:
    human, blind = read(HUMAN), read(Path(blind_path))
    ids = sorted(human)
    assert ids == sorted(blind), "los ids no coinciden"
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    judged = json.loads((RESULTS / "phase6_juez.json").read_text(encoding="utf-8"))
    versions = [v for v in RUBRICS if v in judged["rubrics"]]
    verdicts = {
        v: {
            f"{pv}:{r['id']}": r["verdict"]
            for pv, rs in judged["rubrics"][v]["phase4"].items()
            for r in rs
        }
        for v in versions
    }
    col = lambda src, c: [int(src[i][f"humano_{c}"]) for i in ids]  # noqa: E731
    print("criterio | suspende Javier / ciego | acuerdo | kappa J-ciego | "
          + " | ".join(f"kappa ciego-juez {v}" for v in versions))  # fmt: skip
    for c in IDS:
        h, b = col(human, c), col(blind, c)
        agree = sum(x == y for x, y in zip(h, b, strict=True)) / len(ids)
        jk = []
        for v in versions:
            j = [int(verdicts[v][mapping[i]][c]["cumple"]) for i in ids]
            jk.append(kappa(b, j))
        print(
            f"{c} | {h.count(0)} / {b.count(0)} | {agree:.0%} | {kappa(h, b)} | " + " | ".join(jk)
        )
    print("\nDesacuerdos Javier vs ciego:")
    for i in ids:
        for c in IDS:
            if human[i][f"humano_{c}"] != blind[i][f"humano_{c}"]:
                print(f"- {i} ({mapping[i]}) {c}: Javier={human[i][f'humano_{c}']} "
                      f"ciego={blind[i][f'humano_{c}']} | nota ciego: {blind[i]['notas'][:300]}")  # fmt: skip


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(SECOND))
