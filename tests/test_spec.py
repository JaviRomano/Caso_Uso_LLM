"""La especificación única no puede volver a divergir entre generador y juez."""

import pytest

from caso_uso_llm.evals.judge import system_prompt
from caso_uso_llm.evals.rubric import IDS, RUBRICS
from caso_uso_llm.generate.prompts import RESPONSE_PROMPTS
from caso_uso_llm.spec import JUEZ, PERMITIDAS, REGLAS


def test_el_juez_evalua_exactamente_los_criterios_de_la_rubrica():
    assert {r.id for r in JUEZ} == set(IDS)
    assert [c.id for c in RUBRICS["v3"]] == list(IDS)


@pytest.mark.parametrize("version", ["v3", "v4"])
def test_cada_regla_aparece_en_el_prompt_del_generador(version):
    for r in REGLAS:
        assert r.instruccion in RESPONSE_PROMPTS[version], r.id


@pytest.mark.parametrize("version", ["v3", "v4"])
def test_las_formulas_permitidas_las_leen_generador_y_juez(version):
    generator, judge = RESPONSE_PROMPTS[version], system_prompt("v3")
    for phrase in PERMITIDAS:
        assert phrase in generator, phrase
        assert phrase in judge, phrase


def test_revisar_lo_ocurrido_permitido_en_culpa_y_premisa():
    """El conflicto que motivó la especificación: el generador debe decirlo y el juez aceptarlo."""
    v3 = {c.id: c for c in RUBRICS["v3"]}
    for cid in ("sin_culpa", "sin_premisa"):
        assert "revisaremos lo ocurrido" in v3[cid].no_cumple_si
    assert "revisaréis lo ocurrido" in RESPONSE_PROMPTS["v3"]


def test_v4_dice_cuando_usar_cada_formula():
    from caso_uso_llm.spec import CUANDO

    assert set(CUANDO) == set(PERMITIDAS)
    for phrase, when in CUANDO.items():
        assert f"«{phrase}»: {when}." in RESPONSE_PROMPTS["v4"]
