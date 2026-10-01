"""Fase 6 (adelantada) · Validación del juez y primera evaluación de las respuestas de la Fase 4.

1. Canaries (respuestas malas a propósito): el juez debe suspender sus criterios esperados.
   Si aprueba alguno, el juez NO es válido y sus cifras no se usan.
2. Controles (respuestas correctas): mide cuánto suspende de más.
3. Semillas del gold (respuestas reales etiquetadas; pendientes de revisión humana).
4. Las 96 respuestas de la Fase 4 (prompts v1 y v2): tasa de cumplimiento por criterio y
   acuerdo con los detectores regex.
5. Comparación por pares v1/v2 en los dos órdenes: sesgo de posición.
6. Plantilla de calibración humana: evals/gold/calibracion_humana.csv.

Uso: uv run just juez
"""

import csv
import json
from collections import Counter

from caso_uso_llm.evals.judge import JUDGE_MODEL, compare, judge
from caso_uso_llm.evals.rubric import CRITERIOS, IDS, rubric_markdown
from caso_uso_llm.generate.run import Cache
from caso_uso_llm.log import log
from caso_uso_llm.paths import RESULTS, ROOT

EVALS = ROOT / "evals"
CANARIES = EVALS / "canaries" / "respuestas_v1.json"
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


def validate_canaries(cache) -> dict:
    doc = json.loads(CANARIES.read_text(encoding="utf-8"))
    rows = []
    for it in doc["items"]:
        v = judge(doc["reviews"][it["review"]], it["response"], cache)
        got, exp = fails(v), set(it["expected_fail"])
        rows.append({
            "id": it["id"], "clase": it["clase"], "expected": sorted(exp), "got": sorted(got),
            "detected": exp <= got, "extra": sorted(got - exp),
            "invented_evidence": sorted(c for c in IDS if v[c]["evidencia_inventada"]),
            "verdict": v,
        })  # fmt: skip
        log(f"   {it['id']:<26} esperado {sorted(exp)} · juez {sorted(got)}")
    can = [r for r in rows if r["clase"] == "canary"]
    ctl = [r for r in rows if r["clase"] == "control"]
    return {
        "rows": rows,
        "canaries_detected": sum(r["detected"] for r in can),
        "canaries_total": len(can),
        "controls_clean": sum(not r["got"] for r in ctl),
        "controls_total": len(ctl),
        "control_false_fails": Counter(c for r in ctl for c in r["got"]),
        "valid": all(r["detected"] for r in can),
    }


def gold_agreement(cache) -> dict:
    doc = json.loads(GOLD.read_text(encoding="utf-8"))
    rows, agree, total = [], 0, 0
    for it in doc["items"]:
        v = judge(it["review"], it["response"], cache)
        exp = set(it["no_cumple"])
        got = fails(v)
        for cid in IDS:
            total += 1
            agree += (cid in exp) == (cid in got)
        rows.append({"id": it["id"], "expected": sorted(exp), "got": sorted(got), "verdict": v})
        log(f"   {it['id']:<24} etiqueta {sorted(exp)} · juez {sorted(got)}")
    return {"rows": rows, "agreement": agree / total, "decisions": total,
            "human_reviewed": doc["revisado_por_humano"]}  # fmt: skip


def evaluate_phase4(cache) -> dict:
    out = {}
    for version in ("v1", "v2"):
        rows = json.loads((RESULTS / f"phase4_dev_{version}.json").read_text(encoding="utf-8"))
        judged = []
        for i, r in enumerate(rows, start=1):
            v = judge(r["review"], r["response"], cache)
            judged.append({"id": r["id"], "kind": r["kind"], "verdict": v, "regex": r["checks"],
                           "review": r["review"], "response": r["response"]})  # fmt: skip
            if i % 12 == 0 or i == len(rows):
                log(f"   {version}: {i}/{len(rows)}")
        out[version] = judged
    return out


def regex_vs_judge(judged: list[dict]) -> dict:
    """Acuerdo entre detectores regex y juez en los criterios que ambos cubren."""
    res = {}
    for flag, cid in REGEX_MAP.items():
        both = Counter((r["regex"][flag], not r["verdict"][cid]["cumple"]) for r in judged)
        res[flag] = {"regex_y_juez": both[(True, True)], "solo_regex": both[(True, False)],
                     "solo_juez": both[(False, True)], "ninguno": both[(False, False)]}  # fmt: skip
    return res


def position_bias(p4: dict, cache) -> dict:
    """v1 frente a v2 en los dos órdenes. Consistente = misma respuesta ganadora."""
    v1 = {r["id"]: r for r in p4["v1"]}
    counts, rows = Counter(), []
    for r2 in p4["v2"]:
        r1 = v1[r2["id"]]
        ab = compare(r2["review"], r1["response"], r2["response"], cache)  # A=v1, B=v2
        ba = compare(r2["review"], r2["response"], r1["response"], cache)  # A=v2, B=v1
        win_ab = {"A": "v1", "B": "v2"}.get(ab, "empate")
        win_ba = {"A": "v2", "B": "v1"}.get(ba, "empate")
        consistent = win_ab == win_ba
        counts["consistente" if consistent else "inconsistente"] += 1
        counts[f"elige_A_{ab}"] += 1
        counts[f"elige_A_{ba}"] += 1
        if consistent:
            counts[f"gana_{win_ab}"] += 1
        rows.append({"id": r2["id"], "orden_v1_v2": win_ab, "orden_v2_v1": win_ba})
    log(f"   pares: {counts['consistente']} consistentes de {len(rows)}")
    return {"counts": dict(counts), "rows": rows, "n": len(rows)}


def export_calibration(p4: dict) -> None:
    """Plantilla para que una persona etiquete: las respuestas v2 adversariales y 16 reales."""
    v2 = [r for r in p4["v2"] if r["kind"] == "adversarial"] + [
        r for r in p4["v2"] if r["kind"] == "real"
    ][:16]
    with CALIBRATION.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "reseña", "respuesta", *(f"humano_{c}" for c in IDS),
                    *(f"juez_{c}" for c in IDS)])  # fmt: skip
        for r in v2:
            w.writerow([r["id"], r["review"], r["response"], *([""] * len(IDS)),
                        *("1" if r["verdict"][c]["cumple"] else "0" for c in IDS)])  # fmt: skip


def main() -> None:
    (EVALS / "rubric.md").write_text(rubric_markdown(), encoding="utf-8", newline="\n")
    cache = Cache(CACHE)
    log(f"Juez {JUDGE_MODEL} · 1) canaries y controles")
    canaries = validate_canaries(cache)
    log(f"   canaries detectados {canaries['canaries_detected']}/{canaries['canaries_total']} · "
        f"controles limpios {canaries['controls_clean']}/{canaries['controls_total']}")  # fmt: skip
    if not canaries["valid"]:
        log("   ⚠ EL JUEZ NO ES VÁLIDO: ha aprobado algún canary. Sus cifras no deben usarse.")
    log("2) Semillas del gold")
    gold = gold_agreement(cache)
    log("3) Respuestas de la Fase 4")
    p4 = evaluate_phase4(cache)
    log("4) Sesgo de posición (pares v1/v2 en los dos órdenes)")
    pos = position_bias(p4, cache)
    export_calibration(p4)
    out = {"judge": JUDGE_MODEL, "canaries": canaries, "gold": gold, "position": pos,
           "phase4": {v: [{k: r[k] for k in ("id", "kind", "verdict")} for r in rows]
                      for v, rows in p4.items()},
           "regex_vs_judge": {v: regex_vs_judge(rows) for v, rows in p4.items()}}  # fmt: skip
    (RESULTS / "phase6_juez.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=dict), encoding="utf-8", newline="\n"
    )
    write_report(out, p4)
    log("OK: results/phase6_juez.json, reports/phase6_juez.md, evals/rubric.md y la plantilla")


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "—"


def write_report(o: dict, p4: dict) -> None:
    c, g, pos = o["canaries"], o["gold"], o["position"]
    L = [
        "# Fase 6 (adelantada) · Validación del juez",
        "",
        f"Generado por `uv run just juez` · juez `{o['judge']}` (otra familia que el generador "
        "`qwen3.6:27b`), temperatura 0, rúbrica de 8 criterios binarios con evidencia literal "
        "([`evals/rubric.md`](../evals/rubric.md)). No editar a mano.",
        "",
        "## 1. ¿Es válido el juez? Canaries y controles",
        "",
        f"- **Canaries detectados: {_pct(c['canaries_detected'], c['canaries_total'])}** "
        "(respuestas malas a propósito; deben suspender su criterio).",
        f"- **Controles sin ningún suspenso: {_pct(c['controls_clean'], c['controls_total'])}** "
        "(respuestas correctas; no deberían suspender nada).",
        "- Veredicto: " + ("**válido** para usarse como señal." if c["valid"] else
                           "**NO VÁLIDO**: ha aprobado algún canary; sus cifras no se usan para decidir."),
        "",
        "| Caso | Clase | Debe suspender | El juez suspende | ¿Detectado? | Evidencia no literal |",
        "|---|---|---|---|---|---|",
    ]  # fmt: skip
    for r in c["rows"]:
        det = "—" if r["clase"] == "control" else ("✅" if r["detected"] else "❌")
        L.append(f"| `{r['id']}` | {r['clase']} | {', '.join(r['expected']) or '—'} | "
                 f"{', '.join(r['got']) or '—'} | {det} | {', '.join(r['invented_evidence']) or '—'} |")  # fmt: skip
    L += [
        "",
        f"## 2. Semillas del gold (respuestas reales, {len(g['rows'])} casos)",
        "",
        f"Acuerdo juez–etiqueta por decisión (caso × criterio): **{g['agreement']:.0%}** de "
        f"{g['decisions']}. "
        + ("Etiquetas revisadas por una persona." if g["human_reviewed"] else
           "**Las etiquetas son una propuesta de Claude pendiente de revisión humana**: este "
           "acuerdo no es todavía una calibración."),
        "",
        "| Caso | Etiqueta: no cumple | Juez: no cumple |",
        "|---|---|---|",
    ]  # fmt: skip
    L += [
        f"| `{r['id']}` | {', '.join(r['expected']) or '—'} | {', '.join(r['got']) or '—'} |"
        for r in g["rows"]
    ]
    L += ["", "## 3. Respuestas de la Fase 4 según el juez", "",
          "Cumplimiento por criterio (48 respuestas por versión: 40 reales + 8 adversariales).", "",
          "| Criterio | v1 reales | v1 advers. | v2 reales | v2 advers. |", "|---|---|---|---|---|"]  # fmt: skip
    for cid in IDS:
        cells = []
        for v in ("v1", "v2"):
            for kind in ("real", "adversarial"):
                rows = [r for r in p4[v] if r["kind"] == kind]
                cells.append(_pct(sum(r["verdict"][cid]["cumple"] for r in rows), len(rows)))
        L.append(f"| {NAMES[cid]} | " + " | ".join(cells) + " |")
    L += ["", "Acuerdo con los detectores regex de la Fase 4 (v2):", "",
          "| Detector regex | Criterio del juez | Ambos | Solo regex | Solo juez |",
          "|---|---|---|---|---|"]  # fmt: skip
    for flag, d in o["regex_vs_judge"]["v2"].items():
        L.append(
            f"| {flag} | {REGEX_MAP[flag]} | {d['regex_y_juez']} | {d['solo_regex']} | {d['solo_juez']} |"
        )
    k = pos["counts"]
    L += [
        "",
        "## 4. Sesgo de posición (comparación por pares v1 frente a v2)",
        "",
        f"Cada par se juzga dos veces, cambiando el orden. **Consistente** (elige la misma "
        f"respuesta en los dos órdenes): **{_pct(k.get('consistente', 0), pos['n'])}**.",
        f"Elecciones por posición: A {k.get('elige_A_A', 0)} · B {k.get('elige_A_B', 0)} · "
        f"empate {k.get('elige_A_empate', 0)} (de {2 * pos['n']}). Entre los consistentes: "
        f"gana v2 {k.get('gana_v2', 0)}, gana v1 {k.get('gana_v1', 0)}, empate {k.get('gana_empate', 0)}.",
        "",
        "## 5. Calibración humana (pendiente)",
        "",
        "Plantilla en [`evals/gold/calibracion_humana.csv`](../evals/gold/calibracion_humana.csv): "
        "24 respuestas v2 con las columnas `humano_*` vacías (1 = cumple, 0 = no cumple) junto al "
        "veredicto del juez. Hasta que se rellene, el juez es una señal, no una medida.",
    ]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
