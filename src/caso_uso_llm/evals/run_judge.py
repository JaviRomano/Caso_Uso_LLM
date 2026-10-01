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
        p.stem.removeprefix("phase4_dev_"): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(RESULTS.glob("phase4_dev_v*.json"))
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


def position_bias(p4: dict, cache, a: str, b: str) -> dict:
    """Versión a frente a b en los dos órdenes. Consistente = elige la misma respuesta en ambos."""
    ra = {r["id"]: r for r in p4[a]}
    counts = Counter()
    for rb in p4[b]:
        r1 = ra[rb["id"]]
        ab = compare(rb["review"], r1["response"], rb["response"], cache)  # A=a, B=b
        ba = compare(rb["review"], rb["response"], r1["response"], cache)  # A=b, B=a
        win_ab = {"A": a, "B": b}.get(ab, "empate")
        win_ba = {"A": b, "B": a}.get(ba, "empate")
        counts["consistente" if win_ab == win_ba else "inconsistente"] += 1
        counts[f"posicion_{ab}"] += 1
        counts[f"posicion_{ba}"] += 1
        if win_ab == win_ba:
            counts[f"gana_{win_ab}"] += 1
    log(f"   {a} vs {b}: {counts['consistente']} pares consistentes de {len(p4[b])}")
    return {"a": a, "b": b, "counts": dict(counts), "n": len(p4[b])}


CALIBRATION_COLS = ["id", "reseña", "respuesta", *(f"humano_{c}" for c in IDS), "notas"]


def export_calibration(p4: dict) -> None:
    """Plantilla A CIEGAS (sin el veredicto del juez): 24 respuestas v2, 8 adversariales + 16 reales.

    Nunca borra trabajo hecho: si el fichero ya tiene etiquetas o notas, se conservan. El cruce con
    el juez lo hace `just calibrar`, leyendo results/phase6_juez.json.
    """
    previous = {}
    if CALIBRATION.exists():
        with CALIBRATION.open(encoding="utf-8-sig", newline="") as f:
            previous = {r["id"]: r for r in csv.DictReader(f, delimiter=";")}
    rows = [r for r in p4["v2"] if r["kind"] == "adversarial"] + [
        r for r in p4["v2"] if r["kind"] == "real"
    ][:16]
    with CALIBRATION.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(CALIBRATION_COLS)
        for r in rows:
            old = previous.get(r["id"], {})
            kept = [old.get(col, "") for col in CALIBRATION_COLS[3:]]
            w.writerow([r["id"], r["review"], r["response"], *kept])


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
    log("Sesgo de posición (cada versión del prompt frente a la anterior, en los dos órdenes)")
    versions = list(p4)
    pos = [position_bias(p4, cache, a, b) for a, b in zip(versions, versions[1:], strict=False)]
    export_calibration(p4)
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
    ]
    prompt_versions = list(R[versions[-1]]["phase4"])
    rows += [
        (
            f"Fase 4, prompt {pv}: respuestas que cumplen todo",
            lambda r, pv=pv: _frac(_all_ok(r["phase4"][pv])),
        )
        for pv in prompt_versions
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
          "| Criterio | " + " | ".join(f"{pv} reales | {pv} advers." for pv in prompt_versions) + " |",
          "|---|" + "---|---|" * len(prompt_versions)]  # fmt: skip
    for cid in IDS:
        cells = []
        for pv in prompt_versions:
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
    L += ["", "## 5. Comparación por pares y sesgo de posición", "",
          "Cada par se juzga dos veces cambiando el orden; solo cuenta como victoria si coincide en los dos.", "",
          "| Comparación | Consistente | Elige posición A / B / empate | Gana (consistentes) |",
          "|---|---|---|---|"]  # fmt: skip
    for p in pos:
        k, a, b = p["counts"], p["a"], p["b"]
        L.append(
            f"| {a} frente a {b} | {_pct(k.get('consistente', 0), p['n'])} | {k.get('posicion_A', 0)} / "
            f"{k.get('posicion_B', 0)} / {k.get('posicion_empate', 0)} | {b} {k.get(f'gana_{b}', 0)} · "
            f"{a} {k.get(f'gana_{a}', 0)} · empate {k.get('gana_empate', 0)} |"
        )
    L += [
        "",
        "## 6. Calibración humana (pendiente)",
        "",
        "Plantilla A CIEGAS: [`evals/gold/calibracion_humana.csv`](../evals/gold/calibracion_humana.csv) "
        "(24 respuestas "
        "del prompt v2; columnas `humano_*`: 1 = cumple, 0 = no cumple; `notas` para dudas). No muestra el veredicto "
        "del juez; `uv run just calibrar` lo cruza después. No se ha usado para ajustar nada.",
    ]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
