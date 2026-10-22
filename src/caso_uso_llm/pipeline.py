"""Pipeline completo (pasos [1]–[7] de la arquitectura) y cola de revisión humana.

reseña + hotel → [1] normalización y PII → [2] sentimiento y confianza (mRoBERTa, CPU)
→ [3] aspectos en JSON → [4] RAG (ficha por id, políticas, respuestas aprobadas)
→ [5] respuesta (prompt v6) → [6] guardarraíles (comprobaciones deterministas + juez v2g con ficha)
→ [7] «publicable» o «revisión humana», con los motivos.

Va a revisión humana si se cumple CUALQUIERA de estas condiciones:
- la reseña es negativa, o la confianza del clasificador es menor que el umbral elegido en
  validación (0,85; results/phase3b_realista.json);
- el cliente pide algo (reembolso, compensación, respuesta…): solo una persona puede decidir;
- el análisis no es un JSON válido;
- salta alguna comprobación determinista (promesa, culpa expresa, tuteo, plazo, importe, dato
  fuera de la ficha, contradice al cliente, nombra la ficha, longitud o firma);
- el juez suspende algún criterio.

Se ejecuta por etapas (clasificar todo, recuperar todo, generar todo, juzgar todo) porque el
generador de 27B y el juez de 12B no caben juntos en la VRAM con contexto: alternarlos por
reseña obligaría a recargarlos cada vez.

Uso: uv run just pipeline                         # demostración: casos sintéticos + 40 del AHR
     uv run just pipeline --csv entrada.csv       # columnas: id, hotel (opcional), title, text
"""

import argparse
import json
from collections import Counter

import pandas as pd

from caso_uso_llm.classify.datasets import load_ahr_ood
from caso_uso_llm.classify.infer import SentimentEnsemble, prepare
from caso_uso_llm.evals.judge import JUDGE_MODEL, judge
from caso_uso_llm.evals.rubric import IDS, criterios
from caso_uso_llm.generate import checks as C
from caso_uso_llm.generate.prompts import RESPONSE_PROMPTS
from caso_uso_llm.generate.run import CACHE, MODEL, Cache, analyze, respond
from caso_uso_llm.log import log
from caso_uso_llm.ollama_gpu import require_gpu
from caso_uso_llm.paths import EVALS, RESULTS, ROOT
from caso_uso_llm.rag import kb
from caso_uso_llm.rag.generate_rag import (
    K_EXAMPLES,
    K_POLICIES,
    RAG_CASES,
    context_user,
    ficha_checks,
)
from caso_uso_llm.rag.retrieve import Embedder, Retriever
from caso_uso_llm.seed import DEFAULT_SEED

PROMPT = "v6"
RUBRIC = "v2g"
JUDGE_CACHE = RESULTS / "phase6_judge_cache.jsonl"
THRESHOLD = json.loads((RESULTS / "phase3b_realista.json").read_text(encoding="utf-8"))["coverage"][
    "solo_confianza"
]["threshold"]
QUEUE = RESULTS / "pipeline_cola.json"
REPORT = ROOT / "reports" / "phase5_pipeline.md"
AHR_PER_RATING = 8

# Comprobaciones deterministas que mandan la respuesta a revisión (nombre legible -> función).
ALERTS = {
    "promesa (regla)": lambda c: c["promise"],
    "culpa expresa (regla)": lambda c: c["liability"],
    "tuteo o dialecto": lambda c: c["tuteo"] or c["dialect"],
    "plazo o acción dada por hecha": lambda c: c["plazo"],
    "servicio que la ficha dice que no existe": lambda c: bool(c["servicio_inexistente"]),
    "precio u horario fuera de la ficha": lambda c: bool(c["cifra_inventada"]),
    "contradice al cliente": lambda c: c["contradice"],
    "da un importe": lambda c: bool(c["importe"]),
    "nombra la ficha o las políticas": lambda c: c["nombra_fuente"],
    "longitud o firma": lambda c: not (c["length_ok"] and c["signature_ok"]),
}
NAMES = {c.id: c.nombre for c in criterios(RUBRIC)}


def ficha(hotel: str | None) -> str:
    return kb.ficha_texto(hotel) if hotel else "No disponible."


def run(items: list[dict]) -> list[dict]:
    """items: dicts con id, text y opcionalmente title, hotel y meta (se copia tal cual)."""
    log(f"{len(items)} reseñas · umbral de confianza {THRESHOLD} · prompt {PROMPT} · juez {RUBRIC}")
    out = [{**it, "hotel": it.get("hotel") or None, "reasons": []} for it in items]

    log("[2] Sentimiento (mRoBERTa, 3 semillas, CPU)")
    texts = [prepare(it["text"], it.get("title", "")) for it in out]
    for it, text, p in zip(out, texts, SentimentEnsemble().predict(texts), strict=True):
        it.update(review=text, sentiment=p.label, confidence=p.confidence, probs=p.probs)

    log("[4] Recuperación (políticas híbrida, ejemplos densa)")
    embedder = Embedder(keep_alive=0)
    pols, exs = Retriever(kb.politicas(), embedder), Retriever(kb.respuestas(), embedder)
    ctx = {it["id"]: (pols.search(it["review"], K_POLICIES, "hibrida"),
                      exs.search(it["review"], K_EXAMPLES, "densa")) for it in out}  # fmt: skip

    log(f"[3][5] Aspectos y respuesta ({MODEL})")
    require_gpu(MODEL)
    cache = Cache(CACHE)
    for i, it in enumerate(out, 1):
        analysis, error = analyze(it["review"], cache)
        if analysis is None:
            it.update(analysis=None, response=None, reasons=["análisis inválido"])
            continue
        p, e = ctx[it["id"]]
        user = context_user(it["review"], analysis, it["hotel"], p, e)
        response = respond(RESPONSE_PROMPTS[PROMPT], user, cache)
        checks = C.run_checks(response, analysis["aspectos"])
        checks.update(ficha_checks(response, it["review"], it["hotel"]))
        it.update(analysis=analysis, response=response, checks=checks,
                  politicas=[d.id for d in p], ejemplos=[d.id for d in e])  # fmt: skip
        if i % 10 == 0:
            log(f"   {i}/{len(out)}")

    log(f"[6] Juez {JUDGE_MODEL} (rúbrica {RUBRIC}, con ficha)")
    require_gpu(JUDGE_MODEL)
    jcache = Cache(JUDGE_CACHE)
    for it in out:
        if it["response"] is not None:
            v = judge(it["review"], it["response"], jcache, RUBRIC, ficha(it["hotel"]))
            it["judge"] = {k: v[k] for k in IDS}

    log("[7] Enrutado")
    for it in out:
        it["reasons"] += route(it)
        it["decision"] = "revisión humana" if it["reasons"] else "publicable"
    return out


def route(it: dict) -> list[str]:
    if it["response"] is None:
        return []
    r = []
    if it["sentiment"] == "negativo":
        r.append("reseña negativa")
    if it["confidence"] < THRESHOLD:
        r.append(f"confianza {it['confidence']:.2f} < {THRESHOLD}")
    if it["analysis"]["peticiones"]:
        r.append("el cliente pide: " + "; ".join(it["analysis"]["peticiones"]))
    r += [name for name, fn in ALERTS.items() if fn(it["checks"])]
    r += [f"juez: {NAMES[k]}" for k in IDS if not it["judge"][k]["cumple"]]
    return r


def demo_items(seed: int = DEFAULT_SEED) -> list[dict]:
    """Casos sintéticos con hotel (adversariales y de ficha) + reseñas reales del AHR.

    El AHR no se usó para entrenar el clasificador ni para desarrollar los prompts: es el test de
    referencia fuera de distribución. Sus hoteles no están en kb/, así que van sin ficha.
    """
    adv = json.loads((EVALS / "adversarial" / "generacion_v1.json").read_text(encoding="utf-8"))
    rag = json.loads(RAG_CASES.read_text(encoding="utf-8"))
    hotels = rag["hoteles_generacion_v1"]
    items = [{"id": c["id"], "hotel": hotels[c["id"]], "text": c["review"],
              "meta": {"grupo": "sintético", "tipo": c["tipo"]}} for c in adv["cases"]]  # fmt: skip
    items += [{"id": c["id"], "hotel": c["hotel"], "text": c["review"],
               "meta": {"grupo": "sintético", "tipo": c["tipo"]}} for c in rag["cases"]]  # fmt: skip
    ahr = (
        load_ahr_ood().groupby("rating", group_keys=False).sample(AHR_PER_RATING, random_state=seed)
    )
    items += [{"id": f"ahr-{r.id}", "title": r.title, "text": r.text,
               "meta": {"grupo": "AHR", "rating": int(r.rating), "label3": r.label3}}
              for r in ahr.itertuples()]  # fmt: skip
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="CSV con columnas id, hotel (opcional), title, text")
    args = ap.parse_args()
    if args.csv:
        df = pd.read_csv(args.csv).fillna("")
        items = [{"id": str(r["id"]), "hotel": r.get("hotel") or None, "title": r.get("title", ""),
                  "text": r["text"], "meta": {}} for _, r in df.iterrows()]  # fmt: skip
    else:
        items = demo_items()
    out = run(items)
    queue = [it for it in out if it["decision"] == "revisión humana"]
    QUEUE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    if not args.csv:
        write_report(out)
    log(
        f"OK: {len(out) - len(queue)} publicables, {len(queue)} a revisión → {QUEUE.relative_to(ROOT)}"
    )


def reason_kind(reason: str) -> str:
    """Agrupa motivos para contarlos: «confianza 0.71 < 0.85» -> «confianza baja»."""
    if reason.startswith("confianza"):
        return f"confianza < {THRESHOLD}"
    if reason.startswith("el cliente pide"):
        return "el cliente pide algo"
    return reason


def write_report(out: list[dict]) -> None:
    syn = [it for it in out if it["meta"]["grupo"] == "sintético"]
    ahr = [it for it in out if it["meta"]["grupo"] == "AHR"]
    L = [
        "# Fase 5 · Pipeline completo y cola de revisión humana",
        "",
        f"Generado por `uv run just pipeline` · clasificador mRoBERTa (ensamble de 3 semillas, CPU), "
        f"umbral {THRESHOLD} · generador `{MODEL}` con prompt {PROMPT} y RAG · juez `{JUDGE_MODEL}` "
        f"con rúbrica {RUBRIC} y ficha. No editar a mano.",
        "",
        f"Entrada: {len(syn)} casos **sintéticos** con hotel de `kb/` (adversariales y de ficha contra "
        f"cliente) y {len(ahr)} reseñas **reales** del AHR ({AHR_PER_RATING} por puntuación), que no "
        "se usaron para entrenar ni para desarrollar los prompts; sus hoteles no están en `kb/` y van "
        "sin ficha.",
        "",
        "## Decisión",
        "",
        "| Grupo | Publicables | A revisión humana |",
        "|---|---|---|",
    ]
    for label, rows in (
        ("sintéticos", syn),
        *((f"AHR {k}★", [it for it in ahr if it["meta"]["rating"] == k]) for k in range(1, 6)),
    ):
        pub = sum(it["decision"] == "publicable" for it in rows)
        L.append(f"| {label} | {pub}/{len(rows)} | {len(rows) - pub}/{len(rows)} |")
    reasons = Counter(reason_kind(r) for it in out for r in it["reasons"])
    L += [
        "",
        "## Motivos de revisión (una reseña puede tener varios)",
        "",
        "| Motivo | Reseñas |",
        "|---|---|",
    ]
    L += [f"| {m} | {n} |" for m, n in reasons.most_common()]
    hits = sum(it["sentiment"] == it["meta"]["label3"] for it in ahr)
    L += ["", f"Clasificador en estas {len(ahr)} reseñas del AHR: acierta {hits}/{len(ahr)} "
          "(muestra pequeña: la cifra de referencia es el F1 de la Fase 3).", ""]  # fmt: skip
    L += [
        "## Casos sintéticos",
        "",
        "| Caso | Hotel | Sentimiento (confianza) | Decisión | Motivos |",
        "|---|---|---|---|---|",
    ]
    for it in syn:
        L.append(f"| `{it['id']}` | {it['hotel']} | {it['sentiment']} ({it['confidence']:.2f}) | "
                 f"{it['decision']} | {'; '.join(it['reasons']) or '—'} |")  # fmt: skip
    pub = [it for it in out if it["decision"] == "publicable"]
    L += ["", f"## Respuestas que se publicarían sin revisión ({len(pub)})", "",
          "Son las que más importa leer: nadie las revisaría antes de publicarlas.", ""]  # fmt: skip
    for it in pub:
        L += [
            f"**`{it['id']}`** · {it['sentiment']} ({it['confidence']:.2f})",
            "",
            f"> {it['review'][:400]}",
            "",
            it["response"],
            "",
        ]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
