"""Fase 5 · Juez con ficha (rúbrica v2f) sobre las respuestas v4 (sin contexto), v5 y v6 (RAG).

1. Puerta: canaries y controles de ficha (evals/canaries/ficha_v1.json). Si el juez no suspende
   todos los canaries o suspende algún control, el resto del informe no es válido.
2. Veredicto por criterio de cada respuesta, con la ficha del hotel como fuente de verdad
   (las reseñas reales de COAH no tienen hotel: «No disponible.»).
3. Comparación por pares en los dos órdenes (A/B y B/A); solo cuenta como victoria si coincide
   en ambos, y lo inconsistente es empate (el juez prefiere la posición A, ver phase6_juez.md).

Uso: uv run just rag-juez
"""

import json

from caso_uso_llm.evals.judge import JUDGE_MODEL, compare, judge
from caso_uso_llm.evals.rubric import IDS, criterios
from caso_uso_llm.generate.run import Cache
from caso_uso_llm.log import log
from caso_uso_llm.ollama_gpu import require_gpu
from caso_uso_llm.paths import EVALS, RESULTS, ROOT
from caso_uso_llm.rag import kb
from caso_uso_llm.rag.generate_rag import BASE, results_path

RUBRIC = "v2g"  # v2f no superó la puerta (commit d257360)
CANARIES = EVALS / "canaries" / "ficha_v2.json"
CACHE = RESULTS / "phase6_judge_cache.jsonl"  # la misma caché que el juez de la Fase 6
OUT = RESULTS / "phase5_juez.json"
REPORT = ROOT / "reports" / "phase5_juez.md"
VERSIONS = (BASE, "v5", "v6")
PAIRS = ((BASE, "v6"), ("v5", "v6"))
NAMES = {c.id: c.nombre for c in criterios(RUBRIC)}


def ficha(hotel: str | None) -> str:
    return kb.ficha_texto(hotel) if hotel else "No disponible."


def failed(verdict: dict) -> list[str]:
    return [c for c in IDS if not verdict[c]["cumple"]]


def gate(cache: Cache) -> dict:
    cases = json.loads(CANARIES.read_text(encoding="utf-8"))["cases"]
    rows = []
    for c in cases:
        v = judge(c["review"], c["response"], cache, RUBRIC, ficha(c["hotel"]))
        got = failed(v)
        ok = set(c["falla"]) <= set(got) if c["falla"] else not got
        rows.append({"id": c["id"], "esperado": c["falla"], "juez": got, "ok": ok,
                     "evidencia": {k: v[k]["evidencia"] for k in got}})  # fmt: skip
    return {"rows": rows, "valid": all(r["ok"] for r in rows)}


def load_cases() -> list[dict]:
    """Une v4/v5 (de la ejecución v5) y v6 (de la ejecución v6) por id de reseña."""
    runs = {v: json.loads(results_path(v).read_text(encoding="utf-8")) for v in ("v5", "v6")}
    v6 = {r["id"]: r for r in runs["v6"]}
    out = []
    for r in runs["v5"]:
        if not r["analysis_valid"]:
            continue
        responses = {BASE: r[BASE]["response"], "v5": r["v5"]["response"]}
        responses["v6"] = v6[r["id"]]["v6"]["response"]
        out.append({k: r[k] for k in ("id", "kind", "hotel", "review")} | {"responses": responses})
    return out


def main() -> None:
    require_gpu(JUDGE_MODEL)
    cache = Cache(CACHE)
    log(f"Juez {JUDGE_MODEL} · rúbrica {RUBRIC} (con ficha)")
    g = gate(cache)
    log(f"Puerta de canaries: {sum(r['ok'] for r in g['rows'])}/{len(g['rows'])} correctos")
    cases = load_cases()
    for i, c in enumerate(cases, 1):
        f = ficha(c["hotel"])
        c["verdicts"] = {
            v: judge(c["review"], c["responses"][v], cache, RUBRIC, f) for v in VERSIONS
        }
        c["pairs"] = {}
        for a, b in PAIRS:
            ab = compare(c["review"], c["responses"][a], c["responses"][b], cache, f)
            ba = compare(c["review"], c["responses"][b], c["responses"][a], cache, f)
            first = {"A": a, "B": b}.get(ab, "empate")
            second = {"A": b, "B": a}.get(ba, "empate")
            c["pairs"][f"{a}-{b}"] = {"ab": ab, "ba": ba,
                                      "winner": first if first == second else "empate",
                                      "consistent": first == second}  # fmt: skip
        log(f"   [{i}/{len(cases)}] {c['id']}: suspensos " + " · ".join(
            f"{v} {len(failed(c['verdicts'][v]))}" for v in VERSIONS))  # fmt: skip
    OUT.write_text(json.dumps({"gate": g, "cases": cases}, ensure_ascii=False, indent=1),
                   encoding="utf-8", newline="\n")  # fmt: skip
    write_report(g, cases)
    log(f"OK: {OUT.relative_to(ROOT)} y {REPORT.relative_to(ROOT)}")


GROUPS = (("real", "reales"), ("adversarial", "adversariales"), ("rag", "ficha vs. cliente"))


def write_report(g: dict, cases: list[dict]) -> None:
    L = [
        "# Fase 5 · Juez con ficha: v4 (sin contexto) frente a v5 y v6 (RAG)",
        "",
        f"Generado por `uv run just rag-juez` · juez `{JUDGE_MODEL}`, rúbrica `{RUBRIC}` (v2 + la "
        "ficha del hotel como fuente de verdad; v2f no superó la puerta), temperatura 0. No editar a mano.",
        "",
        "## 1. Puerta: canaries y controles de ficha",
        "",
        f"**{'VÁLIDA' if g['valid'] else 'NO VÁLIDA: el resto del informe no se puede usar'}** · "
        f"{sum(r['ok'] for r in g['rows'])}/{len(g['rows'])} casos correctos.",
        "",
        "| Caso | Debe suspender | Suspende | Correcto |",
        "|---|---|---|---|",
    ]
    for r in g["rows"]:
        L.append(f"| `{r['id']}` | {', '.join(r['esperado']) or '— (control)'} | "
                 f"{', '.join(r['juez']) or '—'} | {'✅' if r['ok'] else '❌'} |")  # fmt: skip
    L += ["", "## 2. Respuestas que cumplen todos los criterios", "",
          "| Grupo | " + " | ".join(VERSIONS) + " |", "|---|" + "---|" * len(VERSIONS)]  # fmt: skip
    for kind, label in GROUPS:
        rows = [c for c in cases if c["kind"] == kind]
        cells = [f"{sum(not failed(c['verdicts'][v]) for c in rows)}/{len(rows)}" for v in VERSIONS]
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    L += ["", "## 3. Suspensos por criterio (todos los casos)", "",
          "| Criterio | " + " | ".join(VERSIONS) + " |", "|---|" + "---|" * len(VERSIONS)]  # fmt: skip
    for cid in IDS:
        cells = [str(sum(cid in failed(c["verdicts"][v]) for c in cases)) for v in VERSIONS]
        L.append(f"| {NAMES[cid]} | " + " | ".join(cells) + " |")
    L += ["", "## 4. Comparación por pares (en los dos órdenes)", "",
          "| Par | Consistentes | Gana el primero | Gana el segundo | Empate |", "|---|---|---|---|---|"]  # fmt: skip
    for a, b in PAIRS:
        ps = [c["pairs"][f"{a}-{b}"] for c in cases]
        L.append(f"| {a} frente a {b} | {sum(p['consistent'] for p in ps)}/{len(ps)} | "
                 f"{sum(p['winner'] == a for p in ps)} | {sum(p['winner'] == b for p in ps)} | "
                 f"{sum(p['winner'] == 'empate' for p in ps)} |")  # fmt: skip
    L += ["", "## 5. Suspensos en los casos adversariales, con la evidencia del juez", ""]
    for c in [c for c in cases if c["kind"] != "real"]:
        lines = [
            f"- **{v}** · {NAMES[k]}: «{c['verdicts'][v][k]['evidencia'][:160]}»"
            for v in VERSIONS
            for k in failed(c["verdicts"][v])
        ]
        if lines:
            L += [f"**`{c['id']}`** (hotel {c['hotel']})", "", *lines, ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
