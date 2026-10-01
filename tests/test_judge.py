import json

from caso_uso_llm.evals import judge as J
from caso_uso_llm.evals.rubric import IDS, RUBRICS


class FakeCache:
    """Devuelve una respuesta fija del juez sin llamar a ningún LLM."""

    def __init__(self, verdicts: dict):
        self.raw = json.dumps(verdicts)

    def get_or_call(self, payload, fn):
        return self.raw


RESPONSE = "Lamentamos que su hijo se cayera por el suelo mojado. El equipo del hotel"


def _verdicts(**fails):
    return {c: {"cumple": c not in fails, "evidencia": fails.get(c, "")} for c in IDS}


def test_evidencia_literal_valida():
    v = J.judge("reseña", RESPONSE, FakeCache(_verdicts(sin_culpa="se cayera por el suelo mojado")))
    assert not v["sin_culpa"]["cumple"] and not v["sin_culpa"]["evidencia_inventada"]


def test_evidencia_inventada_se_marca():
    v = J.judge("reseña", RESPONSE, FakeCache(_verdicts(sin_culpa="reconocemos nuestro error")))
    assert v["sin_culpa"]["evidencia_inventada"]


def test_aspecto_no_exige_cita_en_v2_pero_si_en_v1():
    cache = FakeCache(_verdicts(aspecto=""))
    assert not J.judge("r", RESPONSE, cache, "v2")["aspecto"]["evidencia_inventada"]
    assert J.judge("r", RESPONSE, cache, "v1")["aspecto"]["evidencia_inventada"]


def test_rubricas_mismos_criterios_y_v2_cambia_la_culpa():
    assert [c.id for c in RUBRICS["v1"]] == [c.id for c in RUBRICS["v2"]] == list(IDS)
    v1 = {c.id: c for c in RUBRICS["v1"]}
    v2 = {c.id: c for c in RUBRICS["v2"]}
    assert "SÍ cumple" in v2["sin_culpa"].no_cumple_si and v1["sin_culpa"] != v2["sin_culpa"]
    assert J.system_prompt("v1") != J.system_prompt("v2")
