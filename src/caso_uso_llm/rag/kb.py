"""Base de conocimiento de la Fase 5 (sintética): fichas de hotel, políticas y respuestas aprobadas.

- La ficha del hotel NO se busca: la reseña llega con su hotel y la ficha entra entera en el
  prompt (selección por id).
- Se recuperan por búsqueda las políticas aplicables (salvo las de `siempre=true`, que van en
  todos los prompts) y las respuestas aprobadas a reseñas parecidas (few-shot dinámico). En las
  respuestas se indexa la reseña, porque la consulta también es una reseña.
"""

import json
from dataclasses import dataclass, field

from caso_uso_llm.paths import ROOT

KB = ROOT / "kb"


@dataclass(frozen=True)
class Doc:
    id: str
    kind: str  # "politica" | "respuesta"
    text: str  # lo que se indexa
    payload: dict = field(default_factory=dict, compare=False)


def _read(name: str) -> dict:
    return json.loads((KB / name).read_text(encoding="utf-8"))


def politicas(include_always: bool = False) -> list[Doc]:
    return [
        Doc(p["id"], "politica", f"{p['titulo']}. {p['texto']}", p)
        for p in _read("politicas.json")["politicas"]
        if include_always or not p.get("siempre")
    ]


def politicas_siempre() -> list[dict]:
    return [p for p in _read("politicas.json")["politicas"] if p.get("siempre")]


def respuestas() -> list[Doc]:
    return [
        Doc(r["id"], "respuesta", r["resena"], r)
        for r in _read("respuestas_aprobadas.json")["respuestas"]
    ]


def fichas() -> dict[str, dict]:
    return {h["id"]: h for h in _read("fichas_hoteles.json")["hoteles"]}


def ficha_texto(hotel_id: str) -> str:
    h = fichas()[hotel_id]
    lines = [f"{h['nombre']} ({h['ciudad']}, {h['categoria']} estrellas)."]
    lines += [f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in h["servicios"].items()]
    return "\n".join(lines)
