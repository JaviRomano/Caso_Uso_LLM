import pytest

from caso_uso_llm.classify import stress as S


def test_informal_quita_tildes_y_mayusculas_pero_no_la_enye():
    assert S.informal("¡Qué Bañera tan PEQUEÑA!") == "que bañera tan pequeña!"


def test_andaluz():
    original = "Todo muy bien, nos han tratado genial para nada caro. Es verdad."
    assert S.andaluz(original) == "to mu bien, nos han tratao genial pa na caro. Es verdá."


def test_erratas_reproducibles_y_moderadas():
    text = "La habitación estaba limpísima y el personal fue amabilísimo durante toda la estancia"
    assert S.typos(text, seed=1) == S.typos(text, seed=1)
    changed = sum(a != b for a, b in zip(text.split(), S.typos(text, seed=1).split(), strict=True))
    assert changed <= 3


@pytest.mark.skipif(not S.SFU_HOTELES.exists(), reason="ejecuta `uv run just data-download` antes")
def test_sfu_hoteles():
    df = S.load_sfu_hoteles()
    assert len(df) == 50
    assert set(df["rating"]) == {1, 2, 4, 5}
    assert df["label3"].value_counts().to_dict() == {"negativo": 25, "positivo": 25}
    assert " ." not in df["input"].iloc[0]  # puntuación pegada a la palabra
