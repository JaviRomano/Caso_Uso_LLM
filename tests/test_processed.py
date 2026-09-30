"""Invariantes de los datos generados por `just data` (se saltan si aún no existen)."""

import pandas as pd
import pytest

from caso_uso_llm.data.normalize import dedup_key
from caso_uso_llm.paths import DATA_PROCESSED

FILES = {s: DATA_PROCESSED / f"{s}.parquet" for s in ("coah", "coar")}
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in FILES.values()), reason="ejecuta `uv run just data` antes"
)


@pytest.fixture(scope="module")
def data():
    return pd.concat([pd.read_parquet(p) for p in FILES.values()], ignore_index=True)


def test_ningun_texto_se_repite_entre_particiones(data):
    keys = (data["title"] + " " + data["text"]).map(dedup_key)
    assert data.groupby(keys)["split"].nunique().max() == 1


def test_coar_ningun_establecimiento_en_dos_particiones(data):
    coar = data[data["source"] == "coar"]
    assert coar.groupby("establishment_id")["split"].nunique().max() == 1


def test_todos_los_ratings_en_cada_particion(data):
    for (src, part), g in data.groupby(["source", "split"]):
        assert set(g["rating"]) == {1, 2, 3, 4, 5}, (src, part)


def test_sin_datos_personales_del_autor(data):
    assert "usuario" not in data.columns
    assert not data["text"].str.contains(r"\S+@\S+\.\w+").any()
