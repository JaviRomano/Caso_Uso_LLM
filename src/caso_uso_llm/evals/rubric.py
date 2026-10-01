"""Rúbrica del juez: criterios binarios, uno por regla de la guía de estilo (generate/prompts.py).

Binarios y no notas del 1 al 10: una nota mezcla criterios y es difícil de calibrar con
humanos; un "cumple / no cumple" con evidencia se puede auditar caso a caso.
Fuente única: evals/rubric.md se genera a partir de aquí (`uv run just juez`).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Criterio:
    id: str
    nombre: str
    pregunta: str  # se formula de modo que "sí" = cumple
    no_cumple_si: str
    ejemplo_falla: str


CRITERIOS = (
    Criterio(
        "aspecto",
        "Menciona un aspecto concreto",
        "¿La respuesta menciona al menos un aspecto concreto de los que comenta el cliente?",
        "Solo contiene agradecimientos o fórmulas genéricas aplicables a cualquier reseña.",
        "«Gracias por su reseña. Esperamos verle pronto.»",
    ),
    Criterio(
        "sin_promesa",
        "No promete compensaciones",
        "¿La respuesta evita prometer reembolsos, descuentos, regalos, noches gratis, mejoras de "
        "habitación o cualquier compensación, aunque sea de forma velada?",
        "Ofrece o insinúa algo a cambio («le devolveremos», «en su próxima visita tendrá un "
        "detalle especial»). Derivar la petición a un canal privado SÍ cumple.",
        "«En su próxima estancia le esperará una sorpresa por nuestra parte.»",
    ),
    Criterio(
        "sin_culpa",
        "No admite culpa ni responsabilidad",
        "¿La respuesta evita admitir culpa o responsabilidad, tanto de forma expresa como dando "
        "por ciertas las causas o carencias que alega el cliente?",
        "Dice «fue culpa nuestra», o repite como hecho la causa alegada («sufrió un accidente "
        "debido al suelo mojado», «la ausencia de señalización»). Referirse a ello como «lo que "
        "nos describe» SÍ cumple.",
        "«Lamentamos que su hijo se cayera debido a que el suelo estaba mojado.»",
    ),
    Criterio(
        "sin_premisa",
        "No confirma ni niega lo que no puede comprobar",
        "¿La respuesta evita confirmar o negar afirmaciones del cliente que el hotel no puede "
        "comprobar (promesas, servicios incluidos, conversaciones)?",
        "Da por buena la afirmación («efectivamente el spa debía ser gratuito», «lamentamos la "
        "discrepancia con lo prometido») o la niega («nunca prometimos eso»).",
        "«Sentimos que no se respetara el acceso gratuito al spa que le prometimos.»",
    ),
    Criterio(
        "sin_invencion",
        "No inventa datos",
        "¿Todo lo que la respuesta dice del hotel o de la estancia aparece en la reseña?",
        "Menciona servicios, instalaciones, reformas, nombres, cargos o detalles de la estancia "
        "que el cliente no ha mencionado.",
        "«Nuestra piscina climatizada, recién reformada, le espera en su próxima visita.»",
    ),
    Criterio(
        "sin_exageracion",
        "No exagera lo que valoró el cliente",
        "¿La respuesta refleja los elogios del cliente con la misma intensidad, sin inflarlos?",
        "Convierte una valoración tibia en entusiasta («correcto» → «excelente», «aceptable» → "
        "«de gran calidad»).",
        "Cliente: «el desayuno era correcto». Respuesta: «nos alegra que disfrutara de nuestro "
        "excelente desayuno».",
    ),
    Criterio(
        "registro",
        "Español estándar y de usted",
        "¿La respuesta está en español estándar de España, trata al cliente de usted y no imita "
        "el dialecto ni el registro coloquial del cliente?",
        "Tutea («gracias por tu reseña») o imita rasgos dialectales o coloquiales del cliente "
        "(«mu», «pa», «to»).",
        "«¡Qué alegría que te lo pasaras mu bien!»",
    ),
    Criterio(
        "tono",
        "Tono cordial, sin culpar al cliente",
        "¿El tono es cordial y profesional, sin ponerse a la defensiva ni culpar o corregir al "
        "cliente?",
        "Discute, se justifica, ironiza o atribuye el problema al cliente («si hubiera leído las "
        "condiciones…»).",
        "«Si hubiera leído las condiciones de su reserva, sabría que el spa se paga aparte.»",
    ),
)

IDS = tuple(c.id for c in CRITERIOS)


def rubric_markdown() -> str:
    L = [
        "# Rúbrica del juez",
        "",
        "Generado desde `src/caso_uso_llm/evals/rubric.py` (fuente única). No editar a mano.",
        "",
        "Cada criterio es binario. Para cada «no cumple», el juez debe citar **literalmente** "
        "el fragmento de la respuesta que lo justifica; el código comprueba que la cita existe.",
        "",
        "| Criterio | Pregunta (sí = cumple) | No cumple si… | Ejemplo que falla |",
        "|---|---|---|---|",
    ]
    for c in CRITERIOS:
        L.append(
            f"| **{c.nombre}** (`{c.id}`) | {c.pregunta} | {c.no_cumple_si} | {c.ejemplo_falla} |"
        )
    return "\n".join(L) + "\n"
