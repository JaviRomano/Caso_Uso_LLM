import pytest

from caso_uso_llm.generate import checks as C

REVIEW = "La habitación estaba limpísima, pero el desayuno era muy escaso y el personal, amable."


def test_cita_literal_ignora_mayusculas_tildes_y_signos():
    assert C.quote_in_review("el DESAYUNO era muy escaso", REVIEW)
    assert C.quote_in_review("habitacion estaba limpisima", REVIEW)
    assert not C.quote_in_review("el desayuno era abundante", REVIEW)  # invención
    assert not C.quote_in_review("", REVIEW)


def test_menciona_aspecto():
    aspects = [{"cita": "el desayuno era muy escaso"}]
    assert C.mentions_aspect("Lamentamos que el desayuno no estuviera a la altura.", aspects)
    assert not C.mentions_aspect("Gracias por su estancia en el hotel.", aspects)


@pytest.mark.parametrize(
    ("text", "flag"),
    [
        ("Le devolveremos el dinero de inmediato.", "promise"),
        ("Le ofrecemos un descuento en su próxima visita.", "promise"),
        ("Queremos invitarle a una noche gratis.", "promise"),
        ("Ha sido culpa nuestra, sin duda.", "liability"),
        ("Asumimos toda la responsabilidad de lo ocurrido.", "liability"),
        ("Gracias por compartir tu experiencia.", "tuteo"),
        ("Nos alegra que todo fuera mu bien.", "dialect"),
    ],
)
def test_alertas(text, flag):
    assert C.run_checks(text, [{"cita": "x"}])[flag]


def test_respuesta_correcta_sin_alertas():
    text = (
        "Muchas gracias por su reseña. Nos alegra que la habitación le pareciera impecable y que "
        "el personal le atendiera con amabilidad. Lamentamos que el desayuno le resultara escaso: "
        "trasladaremos su comentario al equipo de cocina para revisarlo. Esperamos tener la "
        "oportunidad de recibirle de nuevo y que su próxima estancia sea redonda en todos los "
        "sentidos.\n\nEl equipo del hotel"
    )
    c = C.run_checks(text, [{"cita": "el desayuno era muy escaso"}])
    assert c["length_ok"] and c["mentions_aspect"] and c["signature_ok"]
    assert not any(c[k] for k in ("promise", "liability", "tuteo", "dialect"))


def test_patron_prohibido_del_caso():
    c = C.run_checks(
        "El spa es gratuito para todos.", [], extra_forbidden=[r"spa (es|era) gratuito"]
    )
    assert c["case_forbidden"] == [r"spa (es|era) gratuito"]
