"""Especificación ÚNICA de cómo debe responder el hotel.

De aquí salen el prompt del generador (prompts.RESPONSE_PROMPTS["v3"]) y la rúbrica del juez
(rubric.RUBRICS["v3"]). Antes vivían por separado y se contradecían: el prompt v2 pedía decir
"revisaremos lo ocurrido" y el juez lo suspendía como admisión de culpa.

Cada regla dice qué está PERMITIDO además de qué está prohibido: esa es la parte que, escrita en
un solo sitio, el generador y el juez leen igual. Las reglas formales (longitud, firma, plazos)
no las juzga el LLM: las comprueba código (generate/checks.py).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Regla:
    id: str
    titulo: str
    instruccion: str  # para el generador, en imperativo
    evaluador: str  # "juez" | "regla" (comprobación determinista en checks.py)
    pregunta: str = ""  # para el juez; "sí" = cumple
    no_cumple_si: str = ""
    permitido: tuple[str, ...] = field(default_factory=tuple)
    ejemplo_falla: str = ""
    evidencia_requerida: bool = True  # False si el fallo es una ausencia (nada que citar)


# Fórmulas que el generador puede usar y el juez NO debe suspender.
PERMITIDAS = (
    "lo que nos describe",
    "revisaremos lo ocurrido",
    "lo trasladaremos al equipo",
    "le invitamos a contactar con nosotros por canal privado",
    "lamentamos que su experiencia no estuviera a la altura de lo que esperaba",
)

REGLAS = (
    Regla(
        "registro",
        "Español estándar y de usted",
        "Escribe en español estándar de España, con tono cordial y profesional, y trata al cliente de "
        "usted. No imites el dialecto ni el registro coloquial del cliente.",
        "juez",
        "¿La respuesta está en español estándar de España, trata al cliente de usted y no imita el "
        "dialecto ni el registro coloquial del cliente?",
        "Tutea o imita rasgos dialectales o coloquiales del cliente («mu», «pa», «to», diminutivos).",
        ("Entender el dialecto del cliente y responder en estándar.",),
        "«¡Qué alegría que te lo pasaras mu bien!»",
    ),
    Regla(
        "aspecto",
        "Menciona un aspecto concreto",
        "Agradece la reseña y menciona al menos uno de los aspectos concretos que comenta el "
        "cliente, con tus palabras.",
        "juez",
        "¿La respuesta menciona al menos un aspecto concreto de los que comenta el cliente?",
        "Solo contiene agradecimientos o fórmulas genéricas aplicables a cualquier reseña.",
        ("Parafrasear el aspecto en lugar de citarlo.",),
        "«Gracias por su reseña. Esperamos verle pronto.»",
        evidencia_requerida=False,
    ),
    Regla(
        "sin_exageracion",
        "No exagera lo que valoró el cliente",
        "Refleja los elogios del cliente con la misma intensidad: si dice «correcto», no digas "
        "«excelente» ni «de calidad».",
        "juez",
        "¿La respuesta refleja los elogios del cliente con la misma intensidad, sin inflarlos?",
        "Convierte una valoración tibia en entusiasta («correcto» → «excelente» o «de calidad», "
        "«bien» → «magnífico»). Compara la INTENSIDAD con lo que dijo el cliente, no las palabras.",
        ("Una paráfrasis de intensidad equivalente («de categoría» → «de gran calidad»).",),
        "Cliente: «el desayuno era correcto». Respuesta: «nos alegra que disfrutara de nuestro "
        "excelente desayuno».",
    ),
    Regla(
        "tono",
        "Tono cordial, sin culpar al cliente",
        "Si hay críticas, reconócelas con empatía y di que se trasladarán al equipo. No te pongas a "
        "la defensiva, no des excusas y no corrijas al cliente.",
        "juez",
        "¿El tono es cordial y profesional, sin ponerse a la defensiva ni culpar o corregir al "
        "cliente?",
        "Discute, se justifica, ironiza o atribuye el problema al cliente.",
        ("Lamentar la experiencia del cliente y decir que se trasladará al equipo.",),
        "«Si hubiera leído las condiciones de su reserva, sabría que el spa se paga aparte.»",
    ),
    Regla(
        "sin_promesa",
        "No promete compensaciones",
        "No prometas reembolsos, descuentos, compensaciones, regalos, mejoras ni estancias "
        "gratuitas, aunque el cliente los pida. Si los pide, invítale a contactar por canal privado.",
        "juez",
        "¿La respuesta evita prometer reembolsos, descuentos, regalos, noches gratis, mejoras de "
        "habitación o cualquier compensación, aunque sea de forma velada?",
        "Ofrece o insinúa algo a cambio (devolver dinero, un detalle o una mejora en la próxima "
        "visita, una noche sin cargo).",
        ("Derivar la petición a un canal privado sin comprometer nada.",),
        "«En su próxima estancia le esperará una sorpresa por nuestra parte.»",
    ),
    Regla(
        "sin_culpa",
        "No admite culpa ni responsabilidad",
        "No admitas culpa ni responsabilidad, ni la causa de un daño o de un incumplimiento: no "
        "digas que algo pasó «por» o «debido a» una carencia del hotel, ni califiques tus propios "
        "fallos. Sí puedes lamentar la experiencia y reconocer las quejas.",
        "juez",
        "¿La respuesta evita admitir culpa, responsabilidad o la causa de un daño o de un "
        "incumplimiento?",
        "Atribuye al hotel la causa de un daño, accidente o incumplimiento (que algo ocurrió «por» o "
        "«debido a» una carencia del hotel, que algo «no debió» pasar), califica sus propios fallos "
        "(«es inaceptable», «fallamos») o asume responsabilidad.",
        (
            "Lamentar o reconocer la experiencia y las quejas («lamentamos que la limpieza no estuviera "
            "a la altura», «sentimos los problemas con el wifi»).",
            "Decir que se revisará lo ocurrido o que se trasladará al equipo.",
        ),
        "«Lamentamos que su hijo se cayera debido a que el suelo estaba mojado.»",
    ),
    Regla(
        "sin_invencion",
        "No inventa datos",
        "No inventes datos del hotel (servicios, instalaciones, horarios, reformas, nombres) ni "
        "atribuyas al cliente comentarios que no hizo.",
        "juez",
        "¿Todo lo que la respuesta dice del hotel, de la estancia y de lo que comentó el cliente "
        "aparece en la reseña?",
        "Menciona servicios, instalaciones, reformas, nombres, cargos o detalles que el cliente no "
        "ha mencionado, o le atribuye comentarios que no hizo.",
        ("Fórmulas genéricas sobre el equipo o la mejora continua.",),
        "«Nuestra piscina climatizada, recién reformada, le espera en su próxima visita.»",
    ),
    Regla(
        "sin_premisa",
        "No confirma ni niega lo que no puede comprobar",
        "Si el cliente afirma algo que no puedes comprobar (una promesa, un servicio incluido, una "
        "conversación), no lo confirmes ni lo niegues, ni hables de «discrepancias» o "
        "«malentendidos»: di que revisaréis lo ocurrido.",
        "juez",
        "¿La respuesta evita confirmar o negar afirmaciones del cliente que el hotel no puede "
        "comprobar (promesas, servicios incluidos, conversaciones)?",
        "Da por buena la afirmación (que algo estaba incluido o prometido, «la discrepancia con lo "
        "prometido») o la niega («nunca prometimos eso»).",
        ("Referirse a ello como «lo que nos describe» y decir que se revisará lo ocurrido.",),
        "«Sentimos que no se respetara el acceso gratuito al spa que le prometimos.»",
    ),
    Regla(
        "sin_plazos",
        "Sin plazos ni acciones consumadas",
        "No prometas plazos ni des por hechas acciones («inmediatamente», «ya lo hemos "
        "solucionado»).",
        "regla",
    ),
    Regla(
        "formato",
        "Longitud y firma",
        "Entre 50 y 130 palabras, sin asunto ni listas. Firma solo como «El equipo del hotel».",
        "regla",
    ),
)

JUEZ = tuple(r for r in REGLAS if r.evaluador == "juez")


def generator_prompt() -> str:
    """Prompt de sistema del generador, derivado de la especificación."""
    rules = "\n".join(f"{i}. {r.instruccion}" for i, r in enumerate(REGLAS, start=1))
    allowed = "\n".join(f"- «{p}»" for p in PERMITIDAS)
    return (
        "Eres la persona responsable de atención al cliente de un hotel y respondes a reseñas "
        "públicas.\n\nEscribe la respuesta siguiendo estas reglas:\n"
        f"{rules}\n\nFórmulas que puedes usar con seguridad:\n{allowed}"
    )


def judge_no_cumple(r: Regla) -> str:
    """Texto 'no cumple si' del juez con lo permitido añadido, para que lean lo mismo."""
    allowed = " ".join(r.permitido)
    common = " Las fórmulas " + ", ".join(f"«{p}»" for p in PERMITIDAS) + " SÍ cumplen."
    extra = f" SÍ cumple: {allowed}" if allowed else ""
    return (
        r.no_cumple_si
        + extra
        + (common if r.id in ("sin_culpa", "sin_premisa", "sin_invencion") else "")
    )
