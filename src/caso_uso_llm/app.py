"""Demo en Gradio: responder una reseña y revisar la cola humana.

Pestaña «Responder una reseña»: elige el hotel (ficha de kb/ o sin ficha), pega la reseña y
muestra cada paso del pipeline: sentimiento y confianza, aspectos, políticas y ejemplos
recuperados, borrador, comprobaciones, veredicto del juez y la decisión con sus motivos.

Pestaña «Cola de revisión»: las reseñas que el pipeline no publica (las de la demostración de
`just pipeline` y las procesadas en la app). Quien revisa puede aprobar el borrador, editarlo
y aprobarlo, o descartarlo. Cada decisión se guarda en results/revision_humana.jsonl (fuera de
git: es trabajo de la persona, no un resultado reproducible).

Todo es local: el clasificador corre en CPU y el LLM en Ollama. Cada reseña tarda unos segundos
más la carga de los modelos: generador (27B) y juez (12B) no caben juntos en la VRAM y Ollama
los alterna.

Uso: uv run just app        # http://127.0.0.1:7860
"""

import json
from datetime import datetime

import gradio as gr

from caso_uso_llm.classify.infer import SentimentEnsemble
from caso_uso_llm.evals.rubric import IDS
from caso_uso_llm.log import log
from caso_uso_llm.paths import RESULTS
from caso_uso_llm.pipeline import NAMES, QUEUE, run
from caso_uso_llm.rag import kb

SESSION_QUEUE = RESULTS / "cola_app.jsonl"  # reseñas a revisión procesadas en la app
DECISIONS = RESULTS / "revision_humana.jsonl"
NO_HOTEL = "Sin ficha (hotel no registrado)"

log("Cargando el clasificador (3 semillas de mRoBERTa en CPU)")
CLASSIFIER = SentimentEnsemble()
HOTELS = {f"{h['id']} · {h['nombre']} ({h['ciudad']})": h["id"] for h in kb.fichas().values()}


def _jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _append(path, row: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# --- Responder una reseña ------------------------------------------------------------------------


def respond(hotel_label: str, title: str, text: str):
    if not text.strip():
        raise gr.Error("Escribe o pega una reseña.")
    hotel = HOTELS.get(hotel_label)
    item_id = f"app-{datetime.now():%Y%m%d-%H%M%S}"
    it = run([{"id": item_id, "hotel": hotel, "title": title, "text": text,
               "meta": {"grupo": "app"}}], CLASSIFIER)[0]  # fmt: skip
    if it["decision"] == "revisión humana":
        _append(SESSION_QUEUE, it)
    probs = " · ".join(f"{k} {v:.2f}" for k, v in it["probs"].items())
    sentiment = f"**{it['sentiment']}** (confianza {it['confidence']:.2f}) — {probs}"
    if it.get("response") is None:
        return sentiment, None, "", "", "", f"### ⚠ Revisión humana\n- {'; '.join(it['reasons'])}"
    context = (
        f"**Ficha:** {'sí, ' + hotel if hotel else 'no disponible'}\n\n"
        f"**Políticas:** {', '.join(it['politicas'])}\n\n**Ejemplos:** {', '.join(it['ejemplos'])}"
    )
    judge = "\n".join(
        f"- {'✅' if it['judge'][k]['cumple'] else '❌'} {NAMES[k]}"
        + ("" if it["judge"][k]["cumple"] else f": «{it['judge'][k]['evidencia']}»")
        for k in IDS
    )
    if it["decision"] == "publicable":
        decision = "### ✅ Publicable sin revisión"
    else:
        decision = "### ⚠ A revisión humana\n" + "\n".join(f"- {r}" for r in it["reasons"])
    return sentiment, it["analysis"], context, it["response"], judge, decision


# --- Cola de revisión ----------------------------------------------------------------------------


def pending() -> list[dict]:
    demo = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []
    items = [it for it in demo + _jsonl(SESSION_QUEUE) if it["decision"] == "revisión humana"]
    done = {d["id"] for d in _jsonl(DECISIONS)}
    return [it for it in items if it["id"] not in done]


def queue_table():
    rows = [[it["id"], it.get("hotel") or "—", it["sentiment"], round(it["confidence"], 2),
             "; ".join(it["reasons"])[:120]] for it in pending()]  # fmt: skip
    ids = [r[0] for r in rows]
    return rows, gr.update(choices=ids, value=ids[0] if ids else None)


def show(item_id: str | None):
    it = next((x for x in pending() if x["id"] == item_id), None)
    if it is None:
        return "", "", ""
    reasons = "\n".join(f"- {r}" for r in it["reasons"])
    return it["review"], it.get("response") or "", reasons


def decide(item_id: str | None, draft: str, notes: str, action: str):
    if not item_id:
        raise gr.Error("No hay ninguna reseña seleccionada.")
    it = next(x for x in pending() if x["id"] == item_id)
    _append(DECISIONS, {
        "id": item_id, "fecha": datetime.now().isoformat(timespec="seconds"), "accion": action,
        "borrador_original": it.get("response"), "respuesta_final": draft if action != "descartada" else None,
        "editada": action != "descartada" and draft != it.get("response"), "notas": notes,
        "motivos": it["reasons"],
    })  # fmt: skip
    table, selector = queue_table()
    return table, selector, f"Guardado: {item_id} → {action}."


def build() -> gr.Blocks:
    with gr.Blocks(title="Respuestas a reseñas de hotel") as demo:
        gr.Markdown(
            "# Respuestas a reseñas de hotel\nPipeline local: clasificador mRoBERTa, RAG con la "
            "ficha del hotel, generador Qwen 27B, guardarraíles y juez Gemma 12B. Los hoteles y "
            "sus fichas son **ficticios**."
        )
        with gr.Tab("Responder una reseña"):
            with gr.Row():
                with gr.Column():
                    hotel = gr.Dropdown(
                        [*HOTELS, NO_HOTEL], value=next(iter(HOTELS)), label="Hotel"
                    )
                    title = gr.Textbox(label="Título (opcional)")
                    text = gr.Textbox(label="Reseña", lines=6)
                    go = gr.Button("Generar respuesta", variant="primary")
                with gr.Column():
                    decision = gr.Markdown()
                    sentiment = gr.Markdown(label="Sentimiento")
                    draft = gr.Textbox(label="Borrador de respuesta", lines=10)
            with gr.Accordion("Detalle del pipeline", open=False):
                context = gr.Markdown()
                judge = gr.Markdown()
                analysis = gr.JSON(label="Aspectos (JSON)")
            go.click(
                respond,
                [hotel, title, text],
                [sentiment, analysis, context, draft, judge, decision],
            )
        with gr.Tab("Cola de revisión") as tab:
            table = gr.Dataframe(headers=["id", "hotel", "sentimiento", "confianza", "motivos"],
                                 interactive=False, wrap=True)  # fmt: skip
            selector = gr.Dropdown(label="Reseña a revisar")
            with gr.Row():
                review = gr.Textbox(label="Reseña", lines=8, interactive=False)
                with gr.Column():
                    reasons = gr.Markdown()
                    edited = gr.Textbox(label="Respuesta (puedes editarla)", lines=10)
            notes = gr.Textbox(label="Notas de la revisión")
            with gr.Row():
                approve = gr.Button("Aprobar", variant="primary")
                discard = gr.Button("Descartar", variant="stop")
            status = gr.Markdown()
            tab.select(queue_table, None, [table, selector])
            selector.change(show, selector, [review, edited, reasons])
            approve.click(lambda i, d, n: decide(i, d, n, "aprobada"), [selector, edited, notes],
                          [table, selector, status])  # fmt: skip
            discard.click(lambda i, d, n: decide(i, d, n, "descartada"), [selector, edited, notes],
                          [table, selector, status])  # fmt: skip
    return demo


def main() -> None:
    build().launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()
