"""Fase 6 (adelantada) · Validación del juez y primera evaluación de las respuestas de la Fase 4.

Por cada versión de la rúbrica (rubric.RUBRICS), sobre los MISMOS casos:
1. Canaries (respuestas malas a propósito, obvias y sutiles): el juez debe suspender su
   criterio. Si aprueba alguno, el juez NO es válido.
2. Controles (respuestas correctas, incluidas empáticas y paráfrasis): no debe suspender nada.
3. Semillas del gold (respuestas reales etiquetadas, pendientes de revisión humana): recall de
   los fallos etiquetados y suspensos de más.
4. Las 96 respuestas de la Fase 4 (prompts v1 y v2).
Y una vez (no depende de la rúbrica): comparación por pares v1/v2 en los dos órdenes (sesgo de
posición) y la plantilla de calibración humana.

Uso: uv run just juez
"""

import csv
import json
from collections import Counter

from caso_uso_llm.evals.judge import JUDGE_MODEL, LATEST, compare, judge
from caso_uso_llm.evals.rubric import CRITERIOS, IDS, RUBRICS, rubric_markdown
from caso_uso_llm.generate.run import Cache
from caso_uso_llm.log import log
from caso_uso_llm.paths import RESULTS, ROOT

EVALS = ROOT / "evals"
CANARIES = EVALS / "canaries" / "respuestas_v2.json"
GOLD = EVALS / "gold" / "semillas_fase4.json"
CALIBRATION = EVALS / "gold" / "calibracion_humana.csv"
CACHE = RESULTS / "phase6_judge_cache.jsonl"
REPORT = ROOT / "reports" / "phase6_juez.md"
NAMES = {c.id: c.nombre for c in CRITERIOS}
REGEX_MAP = {
    "promise": "sin_promesa",
    "liability": "sin_culpa",
    "tuteo": "registro",
    "dialect": "registro",
}


def fails(verdict: dict) -> set[str]:
    return {cid for cid in IDS if not verdict[cid]["cumple"]}


def validate_canaries(cache, version: str) -> dict:
    doc = json.loads(CANARIES.read_text(encoding="utf-8"))
    rows = []
    for it in doc["items"]:
        v = judge(doc["reviews"][it["review"]], it["response"], cache, version)
        got, exp = fails(v), set(it["expected_fail"])
        rows.append({
            "id": it["id"], "clase": it["clase"], "sutil": "sutil" in it["id"],
            "expected": sorted(exp), "got": sorted(got), "detected": exp <= got,
            "invented_evidence": sorted(c for c in IDS if v[c]["evidencia_inventada"]),
            "verdict": v,
        })  # fmt: skip
        log(f"   [{version}] {it['id']:<24} esperado {sorted(exp)} · juez {sorted(got)}")
    can = [r for r in rows if r["clase"] == "canary"]
    ctl = [r for r in rows if r["clase"] == "control"]
    return {
        "rows": rows,
        "canaries": (sum(r["detected"] for r in can), len(can)),
        "canaries_sutiles": (
            sum(r["detected"] for r in can if r["sutil"]),
            sum(r["sutil"] for r in can),
        ),
        "controls_clean": (sum(not r["got"] for r in ctl), len(ctl)),
        "valid": all(r["detected"] for r in can),
    }


def gold_metrics(cache, version: str) -> dict:
    doc = json.loads(GOLD.read_text(encoding="utf-8"))
    rows, labelled, detected, extra = [], 0, 0, 0
    for it in doc["items"]:
        v = judge(it["review"], it["response"], cache, version)
        exp, got = set(it["no_cumple"]), fails(v)
        labelled += len(exp)
        detected += len(exp & got)
        extra += len(got - exp)
        rows.append({"id": it["id"], "expected": sorted(exp), "got": sorted(got), "verdict": v})
    return {"rows": rows, "recall": (detected, labelled), "extra_fails": extra,
            "human_reviewed": doc["revisado_por_humano"]}  # fmt: skip


def phase4_responses() -> dict:
    return {
        v: json.loads((RESULTS / f"phase4_dev_{v}.json").read_text(encoding="utf-8"))
        for v in ("v1", "v2")
    }


def judge_phase4(cache, version: str, p4: dict) -> dict:
    out = {}
    for pv, rows in p4.items():
        out[pv] = [
            {"id": r["id"], "kind": r["kind"], "regex": r["checks"],
             "verdict": judge(r["review"], r["response"], cache, version)}
            for r in rows
        ]  # fmt: skip
        log(f"   [{version}] respuestas {pv}: {len(rows)} juzgadas")
    return out


def regex_vs_judge(judged: list[dict]) -> dict:
    res = {}
    for flag, cid in REGEX_MAP.items():
        both = Counter((r["regex"][flag], not r["verdict"][cid]["cumple"]) for r in judged)
        res[flag] = {
            "ambos": both[(True, True)],
            "solo_regex": both[(True, False)],
            "solo_juez": both[(False, True)],
        }
    return res


def position_bias(p4: dict, cache) -> dict:
    """v1 frente a v2 en los dos órdenes. Consistente = elige la misma respuesta en ambos."""
    v1 = {r["id"]: r for r in p4["v1"]}
    counts = Counter()
    for r2 in p4["v2"]:
        r1 = v1[r2["id"]]
        ab = compare(r2["review"], r1["response"], r2["response"], cache)  # A=v1, B=v2
        ba = compare(r2["review"], r2["response"], r1["response"], cache)  # A=v2, B=v1
        win_ab = {"A": "v1", "B": "v2"}.get(ab, "empate")
        win_ba = {"A": "v2", "B": "v1"}.get(ba, "empate")
        counts["consistente" if win_ab == win_ba else "inconsistente"] += 1
        counts[f"posicion_{ab}"] += 1
        counts[f"posicion_{ba}"] += 1
        if win_ab == win_ba:
            counts[f"gana_{win_ab}"] += 1
    log(f"   pares consistentes: {counts['consistente']} de {len(p4['v2'])}")
    return {"counts": dict(counts), "n": len(p4["v2"])}


def export_calibration(p4: dict, judged_v2: list[dict]) -> None:
    """24 respuestas v2 (8 adversariales + 16 reales) para etiquetar a mano, con el juez al lado."""
    verdicts = {r["id"]: r["verdict"] for r in judged_v2}
    rows = [r for r in p4["v2"] if r["kind"] == "adversarial"] + [
        r for r in p4["v2"] if r["kind"] == "real"
    ][:16]
    with CALIBRATION.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(
            [
                "id",
                "reseña",
                "respuesta",
                *(f"humano_{c}" for c in IDS),
                *(f"juez_{c}" for c in IDS),
            ]
        )
        for r in rows:
            v = verdicts[r["id"]]
            w.writerow([r["id"], r["review"], r["response"], *([""] * len(IDS)),
                        *("1" if v[c]["cumple"] else "0" for c in IDS)])  # fmt: skip


def main() -> None:
    cache = Cache(CACHE)
    p4 = phase4_responses()
    results = {}
    for version in RUBRICS:
        log(f"Juez {JUDGE_MODEL} · rúbrica {version}")
        can = validate_canaries(cache, version)
        log(f"   [{version}] canaries {can['canaries'][0]}/{can['canaries'][1]} "
            f"(sutiles {can['canaries_sutiles'][0]}/{can['canaries_sutiles'][1]}) · "
            f"controles limpios {can['controls_clean'][0]}/{can['controls_clean'][1]}")  # fmt: skip
        gold = gold_metrics(cache, version)
        judged = judge_phase4(cache, version, p4)
        results[version] = {"canaries": can, "gold": gold, "phase4": judged,
                            "regex_vs_judge": regex_vs_judge(judged["v2"])}  # fmt: skip
    log("Sesgo de posición (pares v1/v2 en los dos órdenes)")
    pos = position_bias(p4, cache)
    export_calibration(p4, results[LATEST]["phase4"]["v2"])
    (EVALS / "rubric.md").write_text(rubric_markdown(LATEST), encoding="utf-8", newline="\n")
    out = {"judge": JUDGE_MODEL, "rubrics": results, "position": pos}
    (RESULTS / "phase6_juez.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report(out)
    log("OK: results/phase6_juez.json, reports/phase6_juez.md, evals/rubric.md y la plantilla")


# --- Informe ------------------------------------------------------------------------------------


def _frac(t: tuple[int, int]) -> str:
    n, d = t
    return f"{n}/{d}" if d else "—"


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "—"


def _all_ok(rows: list[dict]) -> tuple[int, int]:
    return sum(not fails(r["verdict"]) for r in rows), len(rows)


def write_report(o: dict) -> None:
    R, pos = o["rubrics"], o["position"]
    versions = list(R)
    L = [
        "# Fase 6 (adelantada) · Validación del juez",
        "",
        f"Generado por `uv run just juez` · juez `{o['judge']}` (otra familia que el generador "
        "`qwen3.6:27b`), temperatura 0, criterios binarios con evidencia literal. Rúbricas: "
        f"{', '.join(versions)} (vigente: [`evals/rubric.md`](../evals/rubric.md)). No editar a mano.",
        "",
        "## 1. Resumen por versión de la rúbrica",
        "",
        "| Métrica | " + " | ".join(versions) + " |",
        "|---|" + "---|" * len(versions),
    ]
    rows = [
        ("Canaries detectados (todos)", lambda r: _frac(r["canaries"]["canaries"])),
        ("— de ellos, sutiles", lambda r: _frac(r["canaries"]["canaries_sutiles"])),
        ("Controles sin ningún suspenso", lambda r: _frac(r["canaries"]["controls_clean"])),
        (
            "¿Juez válido? (todos los canaries detectados)",
            lambda r: "sí" if r["canaries"]["valid"] else "**no**",
        ),
        ("Gold: fallos etiquetados que detecta (recall)", lambda r: _frac(r["gold"]["recall"])),
        ("Gold: suspensos no etiquetados", lambda r: str(r["gold"]["extra_fails"])),
        ("Fase 4 v1: respuestas que cumplen todo", lambda r: _frac(_all_ok(r["phase4"]["v1"]))),
        ("Fase 4 v2: respuestas que cumplen todo", lambda r: _frac(_all_ok(r["phase4"]["v2"]))),
    ]
    for label, fn in rows:
        L.append(f"| {label} | " + " | ".join(fn(R[v]) for v in versions) + " |")
    if not R[versions[-1]]["gold"]["human_reviewed"]:
        L += ["", "Las etiquetas del gold son una **propuesta de Claude pendiente de revisión humana**: el recall "
              "frente a ellas orienta, no calibra."]  # fmt: skip

    last = R[versions[-1]]
    L += ["", f"## 2. Canaries y controles caso a caso ({versions[-1]})", "",
          "| Caso | Clase | Debe suspender | El juez suspende | ¿Detectado? | Evidencia no literal |",
          "|---|---|---|---|---|---|"]  # fmt: skip
    for r in last["canaries"]["rows"]:
        det = "—" if r["clase"] == "control" else ("✅" if r["detected"] else "❌")
        L.append(f"| `{r['id']}` | {r['clase']} | {', '.join(r['expected']) or '—'} | {', '.join(r['got']) or '—'} "
                 f"| {det} | {', '.join(r['invented_evidence']) or '—'} |")  # fmt: skip
    L += ["", f"## 3. Semillas del gold ({versions[-1]})", "", "| Caso | Etiqueta: no cumple | Juez: no cumple |",
          "|---|---|---|"]  # fmt: skip
    L += [
        f"| `{r['id']}` | {', '.join(r['expected']) or '—'} | {', '.join(r['got']) or '—'} |"
        for r in last["gold"]["rows"]
    ]
    L += ["", f"## 4. Respuestas de la Fase 4 según el juez ({versions[-1]})", "",
          "| Criterio | v1 reales | v1 advers. | v2 reales | v2 advers. |", "|---|---|---|---|---|"]  # fmt: skip
    for cid in IDS:
        cells = []
        for pv in ("v1", "v2"):
            for kind in ("real", "adversarial"):
                rs = [r for r in last["phase4"][pv] if r["kind"] == kind]
                cells.append(_pct(sum(r["verdict"][cid]["cumple"] for r in rs), len(rs)))
        L.append(f"| {NAMES[cid]} | " + " | ".join(cells) + " |")
    L += ["", "Acuerdo con los detectores regex de la Fase 4 (respuestas v2):", "",
          "| Detector | Criterio del juez | Ambos | Solo regex | Solo juez |", "|---|---|---|---|---|"]  # fmt: skip
    for flag, d in last["regex_vs_judge"].items():
        L.append(
            f"| {flag} | {REGEX_MAP[flag]} | {d['ambos']} | {d['solo_regex']} | {d['solo_juez']} |"
        )
    k = pos["counts"]
    L += [
        "",
        "## 5. Sesgo de posición (comparación por pares v1 frente a v2)",
        "",
        f"Cada par se juzga dos veces cambiando el orden. **Consistente: {_pct(k.get('consistente', 0), pos['n'])}**. "
        f"Elige la posición A {k.get('posicion_A', 0)} veces y la B {k.get('posicion_B', 0)} "
        f"(empate {k.get('posicion_empate', 0)}) de {2 * pos['n']}. Entre los pares consistentes: gana v2 "
        f"{k.get('gana_v2', 0)}, gana v1 {k.get('gana_v1', 0)}, empate {k.get('gana_empate', 0)}.",
        "",
        "## 6. Calibración humana (pendiente)",
        "",
        "Plantilla: [`evals/gold/calibracion_humana.csv`](../evals/gold/calibracion_humana.csv) (24 respuestas v2; "
        "columnas `humano_*` vacías, 1 = cumple, 0 = no cumple; al lado, el veredicto del juez). No se ha usado para "
        "ajustar nada: es la prueba independiente del juez.",
    ]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
