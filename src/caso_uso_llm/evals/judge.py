"""Juez LLM: evalúa una respuesta del hotel contra la rúbrica (checks binarios con evidencia).

- Modelo de OTRA familia que el generador (Gemma frente a Qwen): reduce la autopreferencia.
- En el JSON, la evidencia va ANTES que el veredicto: el modelo localiza el fragmento y luego
  decide, en vez de decidir y justificar después.
- Toda evidencia de un "no cumple" se comprueba contra el texto: si no es una cita literal de
  la respuesta, el veredicto se marca como `evidencia_inventada`.
- Comparación por pares en los dos órdenes (A/B y B/A) para medir el sesgo de posición.
"""

import json

import ollama

from caso_uso_llm.evals.rubric import CRITERIOS, IDS
from caso_uso_llm.generate.checks import quote_in_review

JUDGE_MODEL = "gemma4:12b-it-qat"
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192}

SYSTEM = (
    "Eres un auditor de calidad de las respuestas públicas que un hotel da a las reseñas de sus "
    "clientes. Evalúas la RESPUESTA del hotel, no la reseña.\n\n"
    "Para cada criterio decide si la respuesta CUMPLE. Reglas:\n"
    "- Evalúa cada criterio por separado y con rigor. Una respuesta educada, larga o empática "
    "puede incumplir igualmente: no premies la cortesía.\n"
    "- Antes de decidir, si algún fragmento de la respuesta incumple, cópialo LITERALMENTE en "
    "'evidencia' (sin cambiar ni resumir nada). Si cumple, deja 'evidencia' vacía.\n"
    "- Para saber si algo es invención o exageración, compáralo con lo que dice la reseña.\n\n"
    "Criterios:\n"
    + "\n".join(f"- {c.id}: {c.pregunta} NO CUMPLE si: {c.no_cumple_si}" for c in CRITERIOS)
)

SCHEMA = {
    "type": "object",
    "properties": {
        cid: {
            "type": "object",
            "properties": {"evidencia": {"type": "string"}, "cumple": {"type": "boolean"}},
            "required": ["evidencia", "cumple"],
        }
        for cid in IDS
    },
    "required": list(IDS),
}

PAIR_SYSTEM = (
    "Eres un auditor de calidad de respuestas de hotel a reseñas. Te doy una reseña y dos "
    "respuestas, A y B. Elige la que mejor cumple estas reglas (en este orden de importancia): "
    "no prometer compensaciones, no admitir culpa ni dar por ciertas las causas que alega el "
    "cliente, no confirmar ni negar lo que no se puede comprobar, no inventar datos, no exagerar "
    "los elogios, mencionar algún aspecto concreto, español estándar y de usted, tono cordial. "
    "La longitud y la cortesía no son méritos por sí mismas. Si son equivalentes, responde "
    "'empate'."
)
PAIR_SCHEMA = {
    "type": "object",
    "properties": {"motivo": {"type": "string"}, "preferida": {"enum": ["A", "B", "empate"]}},
    "required": ["motivo", "preferida"],
}


def _chat(system: str, user: str, schema: dict) -> str:
    r = ollama.chat(
        model=JUDGE_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format=schema,
        think=False,
        options=OPTIONS,
    )
    return r.message.content


def judge(review: str, response: str, cache) -> dict:
    """Veredicto por criterio: {id: {cumple, evidencia, evidencia_inventada}}."""
    user = f"RESEÑA:\n«{review}»\n\nRESPUESTA DEL HOTEL:\n«{response}»"
    raw = cache.get_or_call(
        {"judge": JUDGE_MODEL, "opts": OPTIONS, "sys": SYSTEM, "user": user},
        lambda: _chat(SYSTEM, user, SCHEMA),
    )
    out = json.loads(raw)
    for cid in IDS:
        v = out[cid]
        v["evidencia_inventada"] = (not v["cumple"]) and not quote_in_review(
            v.get("evidencia", ""), response
        )
    return out


def compare(review: str, a: str, b: str, cache) -> str:
    """'A', 'B' o 'empate'."""
    user = f"RESEÑA:\n«{review}»\n\nRESPUESTA A:\n«{a}»\n\nRESPUESTA B:\n«{b}»"
    raw = cache.get_or_call(
        {"judge": JUDGE_MODEL, "opts": OPTIONS, "sys": PAIR_SYSTEM, "user": user},
        lambda: _chat(PAIR_SYSTEM, user, PAIR_SCHEMA),
    )
    return json.loads(raw)["preferida"]
