"""Comprobaciones deterministas de la Fase 4 (una por regla de la guía de estilo).

Son detectores baratos y explicables, no un juicio de calidad: marcan señales (una palabra de
compensación, un tuteo) que el juez LLM de la Fase 6 tendrá que confirmar. Falsos positivos
conocidos: "gratuito" citando al cliente, "pa" en "Pa-" de un nombre propio.
"""

import re

from caso_uso_llm.data.normalize import dedup_key

# Sin tildes: se comparan con dedup_key(), que las quita.
_STOP = frozenset(
    (
        "para", "pero", "como", "cuando", "donde", "desde", "hasta", "sobre", "entre", "aunque",
        "porque", "mucho", "mucha", "muchos", "muchas", "todo", "toda", "todos", "todas", "este",
        "esta", "estos", "estas", "habia", "hemos", "estaba", "estaban", "hotel", "habitacion",
        "habitaciones", "bien", "nada", "algo", "siempre", "tambien", "gracias", "estancia",
    )
)  # fmt: skip

# Promesa = verbo de compromiso + algo que se da o se devuelve. Mencionar "reembolso" para
# derivar al canal privado ("respecto a su solicitud de reembolso, le invitamos a contactar")
# NO es una promesa: así responde la guía de estilo (regla 4).
_COMMIT = (
    r"(?:le|les)\s+(?:devolveremos|reembolsaremos|compensaremos|regalaremos|abonaremos|"
    r"ofrecemos|ofreceremos|haremos|aplicaremos|invitamos\s+a\s+(?:una|un|disfrutar))|"
    r"procederemos\s+(?:a|al)|recibirá|tendrá\s+derecho"
)
_GOODS = (
    r"reembols\w*|devoluci\w*|dinero|importe|descuent\w*|compensaci\w*|noche\w*\s+gratis|"
    r"gratis|gratuit\w*|regalo\w*|cortes[ií]a|vale\b|bono\b|upgrade|mejora\s+de\s+habitaci"
)
PROMISE = re.compile(rf"\b(?:{_COMMIT})\b(?:\W+\w+){{0,6}}?\W+(?:{_GOODS})", re.IGNORECASE)
LIABILITY = re.compile(
    r"(culpa nuestra|nuestra culpa|asumimos (?:toda )?(?:la )?responsabilidad|"
    r"reconocemos (?:nuestro|el|un) error|fue un error nuestro|negligencia)",
    re.IGNORECASE,
)
TUTEO = re.compile(r"\b(tu|tus|contigo|te esperamos|gracias por compartir tu)\b", re.IGNORECASE)
DIALECT = re.compile(r"\b(mu|pa|to|toa|na|verdá|usté|quillo|illo|pisha)\b", re.IGNORECASE)
SIGNATURE = re.compile(r"El equipo del hotel\.?\s*$")


def quote_in_review(quote: str, review: str) -> bool:
    """La cita aparece en la reseña (ignorando mayúsculas, tildes y signos)."""
    q = dedup_key(quote)
    return bool(q) and q in dedup_key(review)


def _content_words(text: str) -> set[str]:
    return {w[:5] for w in dedup_key(text).split() if len(w) >= 5 and w not in _STOP}


def mentions_aspect(response: str, aspects: list[dict]) -> bool:
    """Aproximación: la respuesta comparte alguna palabra con contenido (por su raíz de 5 letras)
    con la cita de algún aspecto. No detecta paráfrasis sin palabras en común."""
    resp = _content_words(response)
    return any(_content_words(a["cita"]) & resp for a in aspects)


def word_count(text: str) -> int:
    return len(text.split())


def run_checks(response: str, aspects: list[dict], extra_forbidden: list[str] = ()) -> dict:
    """Todas las comprobaciones de una respuesta. `extra_forbidden`: patrones propios de un caso
    adversarial (p. ej. confirmar un spa gratuito que nadie ha comprobado)."""
    n = word_count(response)
    forbidden_hits = [p for p in extra_forbidden if re.search(p, response, re.IGNORECASE)]
    return {
        "words": n,
        "length_ok": 50 <= n <= 130,
        "mentions_aspect": mentions_aspect(response, aspects),
        "promise": bool(PROMISE.search(response)),
        "liability": bool(LIABILITY.search(response)),
        "tuteo": bool(TUTEO.search(response)),
        "dialect": bool(DIALECT.search(response)),
        "signature_ok": bool(SIGNATURE.search(response.strip())),
        "case_forbidden": forbidden_hits,
    }
