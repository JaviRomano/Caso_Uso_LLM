"""Enrutado del pipeline: qué se publica sin revisión y qué va a la cola humana."""

from caso_uso_llm.evals.rubric import IDS
from caso_uso_llm.pipeline import THRESHOLD, reason_kind, route

CLEAN_CHECKS = {
    "promise": False, "liability": False, "tuteo": False, "dialect": False, "plazo": False,
    "servicio_inexistente": [], "cifra_inventada": [], "contradice": False, "importe": [],
    "nombra_fuente": False, "length_ok": True, "signature_ok": True,
}  # fmt: skip


def item(**over) -> dict:
    base = {
        "response": "Gracias por su reseña…",
        "sentiment": "positivo",
        "confidence": 0.93,
        "analysis": {"peticiones": []},
        "checks": dict(CLEAN_CHECKS),
        "judge": {k: {"cumple": True, "evidencia": ""} for k in IDS},
    }
    return base | over


def test_positiva_segura_y_limpia_se_publica():
    assert route(item()) == []


def test_negativa_va_siempre_a_revision_aunque_todo_lo_demas_este_bien():
    assert route(item(sentiment="negativo")) == ["reseña negativa"]


def test_neutral_va_siempre_a_revision():
    assert route(item(sentiment="neutral")) == ["reseña neutral"]


def test_confianza_bajo_el_umbral_va_a_revision():
    reasons = route(item(confidence=THRESHOLD - 0.01))
    assert len(reasons) == 1 and reason_kind(reasons[0]) == f"confianza < {THRESHOLD}"


def test_peticion_del_cliente_va_a_revision():
    assert route(item(analysis={"peticiones": ["reembolso"]})) == ["el cliente pide: reembolso"]


def test_cualquier_alerta_determinista_va_a_revision():
    for key, value in (("promise", True), ("importe", ["12 €"]), ("signature_ok", False)):
        checks = dict(CLEAN_CHECKS) | {key: value}
        assert route(item(checks=checks)), key


def test_un_suspenso_del_juez_va_a_revision():
    verdict = {k: {"cumple": k != "sin_premisa", "evidencia": ""} for k in IDS}
    assert route(item(judge=verdict)) == ["juez: No confirma ni niega lo que no puede comprobar"]
