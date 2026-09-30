"""Reglas de normalización (funciones puras, sin E/S).

Cada regla sale de una inspección de los datos crudos; las cifras de cuántos textos toca cada
una están en reports/data_report.md. Lo que NO se hace es tan deliberado como lo que sí:
no se pasa a minúsculas, ni se quitan tildes, signos, mayúsculas sostenidas ("PÉSIMO"),
exclamaciones repetidas ni emojis, porque llevan señal de sentimiento y los modelos
(RoBERTa-BNE es *cased*) la aprovechan. Cada modelo aplica después su propio preprocesado.
"""

import re
import unicodedata

import ftfy

# --- Texto ------------------------------------------------------------------------------------

_FTFY = ftfy.TextFixerConfig(
    unescape_html=True,  # R2: &amp; -> &
    fix_line_breaks=True,  # R4: \r\n y \r -> \n
    uncurl_quotes=True,  # R3: “ ” ‘ ’ -> " '
    normalization="NFC",  # R1
)
_SPACES = re.compile(r"[ \t  -​  　]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")


def unquote_csv(s: str) -> str:
    """R5: deshace el entrecomillado CSV que COAR arrastra en algunos campos.

    Ejemplo: `"un ""antro"" caro"` pasa a `un "antro" caro`. Solo si el campo empieza y acaba
    en comilla.
    """
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('""', '"')
    return s


def normalize_text(s: str) -> str:
    """R1–R4 y R6: NFC, mojibake y HTML (ftfy), comillas rectas, saltos de línea y espacios."""
    s = ftfy.fix_text(s, _FTFY)  # R1-R4; "Â°" -> "°", "habitaciÃ³n" -> "habitación"
    lines = (_SPACES.sub(" ", line).strip() for line in s.split("\n"))  # R6
    s = "\n".join(lines)
    return _MANY_NEWLINES.sub("\n\n", s).strip()


def strip_wrapping_quotes(s: str) -> str:
    """R7: TripAdvisor envuelve los títulos de COAR entre comillas tipográficas; se quitan."""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].strip()
    return s


# --- Metadatos --------------------------------------------------------------------------------

LABEL3 = {1: "negativo", 2: "negativo", 3: "neutral", 4: "positivo", 5: "positivo"}


def label3(rating: int) -> str:
    """R8: 1–2★ negativo, 3★ neutral, 4–5★ positivo."""
    return LABEL3[rating]


_COAR_RATING = re.compile(r"^([1-5]) de 5 estrellas$")


def parse_coar_rating(s: str) -> int:
    """R9: "4 de 5 estrellas" -> 4. Cualquier otro formato es un error, no un valor por defecto."""
    m = _COAR_RATING.match(s.strip())
    if not m:
        raise ValueError(f"rating COAR no reconocido: {s!r}")
    return int(m.group(1))


_MONTH_NAMES = (
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"
)
_MONTHS = {m: i + 1 for i, m in enumerate(_MONTH_NAMES.split())}
_COAR_DATE = re.compile(r"^Opinión escrita el (\d{1,2}) (\w+) (\d{4})(?: NUEVO)?$")


def parse_coar_date(s: str) -> str:
    """R10: "Opinión escrita el 30 diciembre 2012[ NUEVO]" -> "2012-12-30" (ISO 8601)."""
    m = _COAR_DATE.match(normalize_text(s))
    if not m or m.group(2) not in _MONTHS:
        raise ValueError(f"fecha COAR no reconocida: {s!r}")
    day, month, year = int(m.group(1)), _MONTHS[m.group(2)], int(m.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


_PROVINCES = {
    "almeria": "Almería",
    "cadiz": "Cádiz",
    "cordoba": "Córdoba",
    "granada": "Granada",
    "huelva": "Huelva",
    "jaen": "Jaén",
    "malaga": "Málaga",
    "sevilla": "Sevilla",
    "seville": "Sevilla",
}
# Valores que no contienen el nombre de la provincia (truncados o comarcas).
_PROVINCE_SPECIAL = {
    "province_of_ma": "Málaga",  # truncado; la única provincia andaluza que empieza por "Ma"
    "sierra_de_aracena_and_picos_de_aroche_nat": "Huelva",  # parque natural, en Huelva
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def canonical_province(raw: str) -> str:
    """R11: nombre oficial de la provincia a partir de las variantes de COAR.

    "Province_of_Seville_Andalucia", "Sevilla", "sevilla" -> "Sevilla". Si no se reconoce, error.
    """
    key = strip_accents(raw.strip()).lower()
    if key in _PROVINCE_SPECIAL:
        return _PROVINCE_SPECIAL[key]
    for token in re.split(r"[_\s]+", key):
        if token in _PROVINCES:
            return _PROVINCES[token]
    raise ValueError(f"provincia no reconocida: {raw!r}")


def parse_establishment(url: str) -> str:
    """R12: identificador estable del establecimiento = el id `d<nnn>` de su URL de TripAdvisor."""
    m = re.search(r"-d(\d+)-", url)
    if not m:
        raise ValueError(f"URL sin id de establecimiento: {url!r}")
    return f"ta-d{m.group(1)}"


# --- Origen del autor (proxy de traducción automática) ----------------------------------------

# Palabras que identifican la ubicación de autores de países no hispanohablantes. Es un proxy:
# TripAdvisor traducía automáticamente sus reseñas al español, y esas reseñas no son español
# de España auténtico. Lista corta y revisable a mano; lo que no encaja queda "desconocido".
_SPAIN = {"espana", "spain"}
# Ciudades españolas: se comprueban al final, porque hay homónimas en otros países
# (Córdoba en Argentina, Valencia en Venezuela) y el país explícito manda.
_SPAIN_CITIES = {
    "almeria", "cadiz", "cordoba", "granada", "huelva", "jaen", "malaga",
    "sevilla", "seville", "madrid", "barcelona", "valencia", "bilbao", "zaragoza", "murcia",
    "alicante", "valladolid", "salamanca", "toledo", "badajoz", "caceres", "oviedo", "gijon",
    "santander", "pamplona", "vitoria", "san sebastian", "donostia", "a coruna", "vigo",
    "palma", "las palmas", "tenerife", "marbella", "jerez", "algeciras", "ronda", "motril",
}  # fmt: skip
_HISPANIC = {"mexico", "argentina", "colombia", "chile", "peru", "venezuela", "uruguay", "cuba"}
_NON_HISPANIC = {
    "reino unido", "united kingdom", "uk", "england", "inglaterra", "escocia", "scotland",
    "gales", "wales", "irlanda", "ireland", "london", "londres", "australia", "canada",
    "estados unidos", "usa", "united states", "francia", "france", "alemania", "germany",
    "belgica", "belgium", "italia", "italy", "paises bajos", "holanda", "netherlands",
    "suecia", "sweden", "noruega", "norway", "dinamarca", "denmark", "finlandia", "suiza",
    "austria", "portugal", "rusia", "polonia", "nueva zelanda", "new zealand", "singapore",
    "singapur", "japon", "china", "israel", "sudafrica", "california", "florida", "texas",
    "illinois", "estado de nueva york", "new york", "nueva york", "chicago", "massachusetts",
}  # fmt: skip


def reviewer_origin(user_field: str) -> str:
    """R13: 'spain' | 'hispanic' | 'non_hispanic' | 'unknown' a partir de la ubicación del autor.

    Solo se guarda esta categoría; el alias y la ciudad (datos personales) se descartan.
    """
    # El campo es "<alias> <ciudad>, <país>" o "<alias> <ciudad> (<país>)"; el alias va primero y
    # no tiene espacios, así que se descarta la primera palabra.
    loc = strip_accents(user_field).lower().split(maxsplit=1)
    place = loc[1] if len(loc) == 2 else ""

    def has(keys: set[str]) -> bool:
        return any(re.search(rf"\b{re.escape(k)}\b", place) for k in keys)

    if has(_SPAIN):
        return "spain"
    if has(_HISPANIC):
        return "hispanic"
    if has(_NON_HISPANIC):
        return "non_hispanic"
    if has(_SPAIN_CITIES):
        return "spain"
    return "unknown"


# --- Datos personales -------------------------------------------------------------------------

# Palabras con mayúscula que no son nombres y aparecían tras "Sra."/"D"/"dueño" (revisión manual).
_NOT_NAMES = r"(?!(?:Que|De|Del|La|El|Los|Las|No|Si|Sí|Muy|Y|En|Un|Una|Super\w*)\b)"
_NAME = _NOT_NAMES + r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?"  # 1–2 palabras
_PII_PATTERNS = (
    ("email", "[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # "http://www. hotelx. com/es" aparece con espacios; se absorben los trozos de dominio
    (
        "url",
        "[URL]",
        re.compile(r"(?:https?://|www\.)\S*(?:\s+\S+\.\s*(?:com|es|net|org)\S*)?", re.I),
    ),
    (
        "telefono",
        "[TELEFONO]",
        re.compile(r"(?<!\d)(?:\+34[\s.]?)?[6789]\d{2}[\s.]?\d{3}[\s.]?\d{3}(?!\d)"),
    ),
    # "habitación 312", "habitacion nº 12": se conserva la palabra y se oculta el número
    ("habitacion", r"\1[NUM]", re.compile(r"((?i:habitaci[oó]n)\s+(?:n[º°o.]*\s*)?)\d{1,4}")),
    # Tratamiento + nombre propio: "la Srta. Ana", "Sr Emilio", "D. José Luis"
    (
        "nombre_tratamiento",
        r"\1[NOMBRE]",
        re.compile(r"\b((?:(?:Sr|Sra|Srta|Don|Doña|Dña)\.?|D\.)\s+)" + _NAME),
    ),
    # Cargo + nombre propio: "su directora Elena Rizo", "el camarero Juan". Solo el cargo
    # ignora mayúsculas: el nombre tiene que empezar por mayúscula ("camarero muy amable" no).
    (
        "nombre_cargo",
        r"\1[NOMBRE]",
        re.compile(
            r"\b((?i:recepcionista|camarer[oa]|director[a]?|gerente|dueñ[oa]|chef|cociner[oa]|"
            r"propietari[oa]|encargad[oa]|jef[ea])s?\s+)" + _NAME
        ),
    ),
)


def mask_pii(s: str) -> tuple[str, dict[str, int]]:
    """R14: sustituye emails, URLs, teléfonos, nº de habitación y nombres con tratamiento o cargo.

    Devuelve (texto, sustituciones por tipo). Es una primera capa por reglas: los nombres sueltos
    sin tratamiento ni cargo ("gracias a Emilio") necesitan NER (Presidio), pendiente.
    """
    counts = {}
    for name, repl, pattern in _PII_PATTERNS:
        s, n = pattern.subn(repl, s)
        if n:
            counts[name] = n
    return s, counts


# --- Clave de deduplicación -------------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9ñ]+")


def dedup_key(s: str) -> str:
    """R15: clave SOLO para comparar duplicados (el texto guardado no cambia).

    Minúsculas, sin tildes (salvo la ñ), sin signos ni espacios repetidos.
    """
    s = s.casefold().replace("ñ", "\0")
    s = strip_accents(s).replace("\0", "ñ")
    return _NON_ALNUM.sub(" ", s).strip()
