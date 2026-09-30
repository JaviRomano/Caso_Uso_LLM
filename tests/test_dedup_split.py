import pandas as pd

from caso_uso_llm.data.dedup import find_duplicates, resolve_duplicates
from caso_uso_llm.data.split import split_grouped, split_stratified


def _df(rows):
    return pd.DataFrame(rows, columns=["id", "source", "title", "text", "label3"])


def test_duplicados_exactos_y_casi_duplicados():
    base = "La habitación era amplia y limpia, el desayuno muy completo y el personal amable. " * 3
    df = _df(
        [
            ("a", "coah", "Bien", base, "positivo"),
            ("b", "coah", "bien!", base.upper(), "positivo"),  # exacto tras la clave
            ("c", "coar", "Bien", base + " Volveremos.", "positivo"),  # casi duplicado
            ("d", "coah", "Otro", "Nada que ver con lo anterior, fue un desastre.", "negativo"),
        ]
    )
    out = resolve_duplicates(find_duplicates(df))
    assert out.set_index("id")["drop_reason"].to_dict() == {
        "a": None,
        "b": "duplicado",
        "c": "duplicado",
        "d": None,
    }


def test_duplicado_con_etiquetas_distintas_se_descarta_entero():
    t = "Texto idéntico repetido con dos puntuaciones diferentes en el corpus original."
    df = _df([("a", "coah", "", t, "positivo"), ("b", "coah", "", t, "neutral")])
    out = resolve_duplicates(find_duplicates(df))
    assert set(out["drop_reason"]) == {"duplicado_conflicto_etiqueta"}


def test_split_estratificado_conserva_proporciones():
    df = pd.DataFrame({"rating": [1, 2, 3, 4, 5] * 40})
    s = split_stratified(df, seed=0)
    sizes = s.value_counts()
    assert abs(sizes["test"] - 30) <= 1 and abs(sizes["val"] - 30) <= 1  # redondeo de sklearn
    for part in ("train", "val", "test"):
        counts = df[s == part]["rating"].value_counts()
        assert counts.max() - counts.min() <= 1  # cada rating, en la misma proporción


def test_split_agrupado_no_mezcla_establecimientos_y_manda_grandes_a_train():
    groups = ["grande"] * 60 + [f"g{i}" for i in range(40) for _ in range(5)]
    labels = (["positivo", "negativo", "neutral"] * 100)[: len(groups)]
    df = pd.DataFrame({"est": groups, "label3": labels})
    s = split_grouped(df, "est", seed=0)
    assert (s[df["est"] == "grande"] == "train").all()
    assert s.groupby(df["est"]).nunique().max() == 1
