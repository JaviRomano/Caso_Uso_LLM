import pytest

from caso_uso_llm.data import normalize as N


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("40Â° aniversario", "40° aniversario"),  # R2 mojibake
        ("habitaciÃ³n", "habitación"),
        ("a &amp; b", "a & b"),  # R2 HTML
        ("“hola”", '"hola"'),  # R3
        ("uno\r\ndos", "uno\ndos"),  # R4
        ("  mucho   espacio \t aquí  ", "mucho espacio aquí"),  # R6
        ("a\n\n\n\nb", "a\n\nb"),
        ("PÉSIMO!!! \U0001f621", "PÉSIMO!!! \U0001f621"),  # NO se tocan mayúsculas, signos, emojis
        ("etc...", "etc..."),  # los puntos suspensivos son estilo, no texto cortado
    ],
)
def test_normalize_text(raw, expected):
    assert N.normalize_text(raw) == expected


def test_unquote_csv():
    assert N.unquote_csv('"un ""antro"" caro"') == 'un "antro" caro'
    assert N.unquote_csv('sin comillas "dentro"') == 'sin comillas "dentro"'


def test_strip_wrapping_quotes():
    assert N.strip_wrapping_quotes('"Caro"') == "Caro"
    assert N.strip_wrapping_quotes('el "rabo"') == 'el "rabo"'


@pytest.mark.parametrize(
    ("rating", "label"),
    [(1, "negativo"), (2, "negativo"), (3, "neutral"), (4, "positivo"), (5, "positivo")],
)
def test_label3(rating, label):
    assert N.label3(rating) == label


def test_parse_coar_rating_y_fecha():
    assert N.parse_coar_rating("4 de 5 estrellas") == 4
    assert N.parse_coar_date("Opinión escrita el 30 diciembre 2012") == "2012-12-30"
    assert N.parse_coar_date("Opinión escrita el 11 enero 2015 NUEVO") == "2015-01-11"
    with pytest.raises(ValueError):
        N.parse_coar_rating("cuatro")


# Todos los valores de provincia que aparecen en COAR (revisados a mano).
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sevilla", "Sevilla"), ("Province_of_Seville_Andalucia", "Sevilla"),
        ("Málaga", "Málaga"), ("Province_of_Malaga_Andalucia", "Málaga"),
        ("Province_of_Malaga_Andaluc", "Málaga"), ("Province_of_Ma", "Málaga"),
        ("Almería", "Almería"), ("Province_of_Almeria_Andalucia", "Almería"),
        ("Province_of_Cadiz_Andalucia", "Cádiz"), ("Córdoba", "Córdoba"),
        ("Province_of_Cordoba_Andalucia", "Córdoba"), ("Granada", "Granada"),
        ("Province_of_Granada_Andalucia", "Granada"), ("Huelva", "Huelva"),
        ("Province_of_Huelva_Andalucia", "Huelva"), ("Jaén", "Jaén"),
        ("Province_of_Jaen_Andalucia", "Jaén"),
        ("Sierra_de_Aracena_and_Picos_de_Aroche_Nat", "Huelva"),
        # AHR
        ("znajar_Province_of_Cordoba_Andalucia", "Córdoba"),
        ("Malaga_Costa_del_Sol_Province_of_Malag", "Málaga"),
        ("Alajar_Sierra_de_Aracena_and_Picos_de_Aroche_Natural_Park_Pro", "Huelva"),
        ("Tavira_Faro_District_Algarve", "Faro (Portugal)"),
    ],
)  # fmt: skip
def test_canonical_province(raw, expected):
    assert N.canonical_province(raw) == expected


def test_parse_establishment():
    url = "http://www.tripadvisor.es/Restaurant_Review-g187430-d2211214-Reviews-Los_Deanes-X.html"
    assert N.parse_establishment(url) == "ta-d2211214"


@pytest.mark.parametrize(
    ("user", "origin"),
    [
        ("lfgf37 Madrid (España)", "spain"),
        ("Spain1978-2 Málaga, España", "spain"),
        ("Guildford52 Londres, Reino Unido", "non_hispanic"),
        ("pepe Córdoba, Argentina", "hispanic"),  # el país manda sobre la ciudad homónima
        ("maria sevilla", "spain"),
        ("x7", "unknown"),
    ],
)
def test_reviewer_origin(user, origin):
    assert N.reviewer_origin(user) == origin


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("el camarero Juan nos atendió", "el camarero [NOMBRE] nos atendió"),
        ("su directora Elena Rizo", "su directora [NOMBRE]"),
        ("la Srta. Ana y al Sr Emilio", "la Srta. [NOMBRE] y al Sr [NOMBRE]"),
        ("en la habitación 311", "en la habitación [NUM]"),
        ("llamad al 954215878.", "llamad al [TELEFONO]."),
        ("escribid a info@hotel.es", "escribid a [EMAIL]"),
        ("web http://www. hotelx. com/es y ya", "web [URL] y ya"),
        # falsos positivos encontrados en la revisión manual: no se tocan
        ("el camarero muy amable", "el camarero muy amable"),
        ("la Sra. Que atendía", "la Sra. Que atendía"),
        ("D Superrecomendable", "D Superrecomendable"),
        ("el dueño No estaba", "el dueño No estaba"),
        ("Dado que era tarde", "Dado que era tarde"),
    ],
)
def test_mask_pii(text, expected):
    assert N.mask_pii(text)[0] == expected


def test_dedup_key_ignora_formato_pero_no_la_enye():
    assert N.dedup_key("¡Muy BIEN,  el   hotel!") == N.dedup_key("muy bien el hotel")
    assert N.dedup_key("año") != N.dedup_key("ano")
