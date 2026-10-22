"""Fase 5 · Evaluación de la recuperación: BM25 frente a bge-m3 frente a la fusión híbrida (RRF).

Consultas: evals/retrieval/consultas_v1.json (8 casos adversariales + 22 reseñas sintéticas),
cada una con sus políticas relevantes y sus respuestas aprobadas parecidas. Se evalúan por
separado los dos índices, porque el prompt toma k de cada uno.

Métricas por consulta, promediadas:
- recall@k: fracción de los documentos relevantes que aparecen entre los k primeros.
- MRR: 1 / posición del primer relevante.
IC 95 % por bootstrap sobre las consultas (son pocas: el intervalo es ancho a propósito).

Uso: uv run just rag
"""

import json

import numpy as np

from caso_uso_llm.log import log
from caso_uso_llm.paths import EVALS, RESULTS, ROOT
from caso_uso_llm.rag import kb
from caso_uso_llm.rag.retrieve import EMBED_MODEL, METHODS, Embedder, Retriever
from caso_uso_llm.seed import DEFAULT_SEED

QUERIES = EVALS / "retrieval" / "consultas_v1.json"
ADVERSARIAL = EVALS / "adversarial" / "generacion_v1.json"
OUT = RESULTS / "phase5_retrieval.json"
REPORT = ROOT / "reports" / "phase5_rag.md"
KS = (1, 3, 5)
INDICES = {"politicas": kb.politicas, "respuestas": kb.respuestas}
N_BOOT = 2000


def load_queries() -> list[dict]:
    adv = {
        c["id"]: c["review"] for c in json.loads(ADVERSARIAL.read_text(encoding="utf-8"))["cases"]
    }
    out = []
    for q in json.loads(QUERIES.read_text(encoding="utf-8"))["consultas"]:
        if "adversarial" in q:
            q = {**q, "id": q["adversarial"], "texto": adv[q["adversarial"]]}
        out.append(q)
    return out


def per_query(ranking: list[str], relevant: list[str]) -> dict:
    m = {f"recall@{k}": len(set(ranking[:k]) & set(relevant)) / len(relevant) for k in KS}
    first = next(i for i, d in enumerate(ranking) if d in relevant)
    m["mrr"] = 1 / (first + 1)
    return m


def ci(values: list[float], seed: int = DEFAULT_SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    v = np.array(values)
    boots = rng.choice(v, size=(N_BOOT, len(v))).mean(axis=1)
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def main() -> None:
    queries = load_queries()
    log(f"{len(queries)} consultas · embeddings {EMBED_MODEL} vía Ollama")
    embedder = Embedder()
    results: dict = {"embed_model": EMBED_MODEL, "n_queries": len(queries), "indices": {}}
    for index, loader in INDICES.items():
        docs = loader()
        retriever = Retriever(docs, embedder)
        labelled = [q for q in queries if q[index]]
        log(f"Índice {index}: {len(docs)} documentos, {len(labelled)} consultas con relevantes")
        by_method = {}
        for method in METHODS:
            rows = []
            for q in labelled:
                ranking = [d.id for d in retriever.rank(q["texto"], method)]
                rows.append({"id": q["id"], "relevant": q[index], "top5": ranking[:5],
                             **per_query(ranking, q[index])})  # fmt: skip
            by_method[method] = rows
            r3 = [r["recall@3"] for r in rows]
            log(
                f"   {method}: recall@3 {np.mean(r3):.2f} · MRR {np.mean([r['mrr'] for r in rows]):.2f}"
            )
        results["indices"][index] = {
            "n_docs": len(docs),
            "n_queries": len(labelled),
            "methods": by_method,
        }
    OUT.write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report(results)
    log(f"OK: {OUT.relative_to(ROOT)} y {REPORT.relative_to(ROOT)}")


def write_report(results: dict) -> None:
    L = [
        "# Fase 5 · RAG: evaluación de la recuperación",
        "",
        f"Generado por `uv run just rag` · embeddings `{results['embed_model']}` vía Ollama · "
        f"{results['n_queries']} consultas ([`consultas_v1.json`](../evals/retrieval/consultas_v1.json)). "
        "No editar a mano.",
        "",
        "Base de conocimiento **sintética** ([`kb/`](../kb/)): la ficha del hotel se selecciona por id "
        "(no se busca); se recuperan las políticas aplicables y las respuestas aprobadas a reseñas "
        "parecidas. Las etiquetas de relevancia son de Claude, pendientes de revisión humana.",
        "",
    ]
    for index, res in results["indices"].items():
        L += [
            f"## Índice de {index} ({res['n_docs']} documentos, {res['n_queries']} consultas)",
            "",
            "| Método | recall@1 | recall@3 (IC 95 %) | recall@5 | MRR |",
            "|---|---|---|---|---|",
        ]
        for method, rows in res["methods"].items():
            mean = {
                m: np.mean([r[m] for r in rows])
                for m in ("recall@1", "recall@3", "recall@5", "mrr")
            }
            lo, hi = ci([r["recall@3"] for r in rows])
            L.append(
                f"| {method} | {mean['recall@1']:.2f} | {mean['recall@3']:.2f} ({lo:.2f}–{hi:.2f}) | "
                f"{mean['recall@5']:.2f} | {mean['mrr']:.2f} |"
            )
        misses = [r for r in res["methods"]["hibrida"] if r["recall@3"] < 1]
        L += [
            "",
            f"Consultas donde la híbrida deja fuera de los 3 primeros algún relevante: {len(misses)}.",
            "",
        ]
        if misses:
            L += ["| Consulta | Relevantes | Top 3 híbrida |", "|---|---|---|"]
            for r in misses:
                L.append(
                    f"| `{r['id']}` | {', '.join(r['relevant'])} | {', '.join(r['top5'][:3])} |"
                )
            L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
