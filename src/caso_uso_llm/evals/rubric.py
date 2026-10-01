"""Rúbrica del juez: criterios binarios, uno por regla de la guía de estilo (generate/prompts.py).

Binarios y no notas del 1 al 10: una nota mezcla criterios y es difícil de calibrar con
humanos; un "cumple / no cumple" con evidencia se puede auditar caso a caso.
Fuente única: evals/rubric.md se genera a partir de aquí (`uv run just juez`).
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Criterio:
    id: str
    nombre: str
    pregunta: str  # se formula de modo que "sí" = cumple
    no_cumple_si: str
    ejemplo_falla: str
    evidencia_requerida: bool = True  # False si el fallo es una ausencia (no hay nada que citar)


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

# v2: correcciones de definición tras validar v1 (reports/phase6_juez.md). No se ajusta caso a
# caso a las semillas del gold: se corrigen definiciones que estaban mal planteadas.
# - sin_culpa: v1 suspendía cualquier frase empática ("lamentamos los problemas de limpieza").
#   El riesgo legal es admitir la CAUSA de un daño o incumplimiento, no reconocer la queja.
# - sin_exageracion: v1 suspendía paráfrasis de igual intensidad ("de categoría" -> "de gran
#   calidad"); se compara la intensidad, no las palabras.
# - sin_invencion: incluye atribuir al cliente comentarios que no hizo.
# - aspecto: su fallo es una ausencia; no se exige cita.
_V2 = {
    "aspecto": dict(evidencia_requerida=False),
    "sin_culpa": dict(
        pregunta="¿La respuesta evita admitir culpa, responsabilidad o la causa de un daño o de "
        "un incumplimiento?",
        no_cumple_si="Atribuye al hotel la causa de un daño, accidente o incumplimiento (que algo "
        "ocurrió «por» o «debido a» una carencia del hotel, que algo «no debió» pasar), califica "
        "sus propios fallos («es inaceptable», «fallamos») o asume responsabilidad. Lamentar o "
        "reconocer la experiencia y las quejas del cliente («lamentamos que la limpieza no "
        "estuviera a la altura», «sentimos los problemas con el wifi») SÍ cumple.",
    ),
    "sin_exageracion": dict(
        no_cumple_si="Convierte una valoración tibia en entusiasta («correcto» → «excelente», "
        "«bien» → «de gran calidad»). Compara la INTENSIDAD con lo que dijo el cliente, no las "
        "palabras: una paráfrasis de intensidad equivalente («de categoría» → «de gran calidad») "
        "SÍ cumple.",
    ),
    "sin_invencion": dict(
        no_cumple_si="Menciona servicios, instalaciones, reformas, nombres, cargos o detalles de "
        "la estancia que el cliente no ha mencionado, o le atribuye comentarios que no hizo "
        "(«su comentario sobre el aparcamiento» si no habló del aparcamiento).",
    ),
}
CRITERIOS_V2 = tuple(replace(c, **_V2.get(c.id, {})) for c in CRITERIOS)


# v3: generada desde la especificación única (spec.py), la misma que genera el prompt v3 del
# generador. Añade lo PERMITIDO a cada criterio, para que juez y generador lean lo mismo.
def _from_spec() -> tuple[Criterio, ...]:
    from caso_uso_llm.spec import JUEZ, judge_no_cumple

    by_id = {r.id: r for r in JUEZ}
    assert set(by_id) == set(IDS), (
        "la especificación y la rúbrica deben cubrir los mismos criterios"
    )
    return tuple(
        Criterio(
            r.id, r.titulo, r.pregunta, judge_no_cumple(r), r.ejemplo_falla, r.evidencia_requerida
        )
        for r in (by_id[i] for i in IDS)
    )


RUBRICS = {"v1": CRITERIOS, "v2": CRITERIOS_V2, "v3": _from_spec()}


def rubric_markdown(version: str = "v2") -> str:
    criterios = RUBRICS[version]
    L = [
        f"# Rúbrica del juez ({version})",
        "",
        "Generado desde `src/caso_uso_llm/evals/rubric.py` (fuente única). No editar a mano.",
        "",
        "Cada criterio es binario. Para cada «no cumple», el juez debe citar **literalmente** "
        "el fragmento de la respuesta que lo justifica; el código comprueba que la cita existe.",
        "",
        "| Criterio | Pregunta (sí = cumple) | No cumple si… | Ejemplo que falla |",
        "|---|---|---|---|",
    ]
    for c in criterios:
        L.append(
            f"| **{c.nombre}** (`{c.id}`) | {c.pregunta} | {c.no_cumple_si} | {c.ejemplo_falla} |"
        )
    return "\n".join(L) + "\n"
