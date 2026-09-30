"""Conjuntos de entrenamiento y evaluación de la Fase 3 (opciones A/B/C sobre el uso de COAR).

- Selección de modelo e hiperparámetros: SIEMPRE con `coah_val`.
- Métrica principal: `coah_test` (hoteles), que no se mira hasta el final.
- `coar_test`: robustez fuera de dominio (restaurantes que el modelo no ha visto).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from caso_uso_llm.paths import DATA_PROCESSED

LABELS = ("negativo", "neutral", "positivo")


def load() -> pd.DataFrame:
    df = pd.concat(
        [pd.read_parquet(DATA_PROCESSED / f"{s}.parquet") for s in ("coah", "coar")],
        ignore_index=True,
    )
    df["input"] = df["title"].str.strip() + ". " + df["text"]
    return df


@dataclass(frozen=True)
class Option:
    name: str
    description: str
    use_coar: bool
    drop_translated: bool = False


OPTIONS = (
    Option("B", "Solo COAH", use_coar=False),
    Option("A", "COAH + COAR mezclados (fuentes y clases ponderadas)", use_coar=True),
    Option(
        "A_sin_trad",
        "Como A, sin reseñas de COAR de autores no hispanohablantes",
        use_coar=True,
        drop_translated=True,
    ),
)


def train_set(df: pd.DataFrame, option: Option, coah_part: pd.DataFrame | None = None):
    """Filas de entrenamiento y sus pesos.

    `coah_part` permite sustituir el train de COAH (validación cruzada). Los pesos equilibran
    las clases dentro de cada fuente y dan a cada fuente el 50 % del peso total: sin eso,
    COAR (3,5k filas, 78 % positivas) dominaría un modelo que se evalúa en hoteles.
    """
    coah = df[(df.source == "coah") & (df.split == "train")] if coah_part is None else coah_part
    parts = [coah]
    if option.use_coar:
        coar = df[(df.source == "coar") & (df.split == "train")]
        if option.drop_translated:
            coar = coar[coar.reviewer_origin != "non_hispanic"]
        parts.append(coar)
    train = pd.concat(parts)
    return train, _weights(train)


def _weights(train: pd.DataFrame) -> np.ndarray:
    w = pd.Series(1.0, index=train.index)
    n_sources = train["source"].nunique()
    for _, g in train.groupby("source"):
        counts = g["label3"].value_counts()
        # clase equilibrada dentro de la fuente: cada clase suma len(g)/n_clases
        cw = len(g) / (len(counts) * counts)
        w[g.index] = g["label3"].map(cw).to_numpy()
        w[g.index] *= len(train) / (n_sources * len(g))  # cada fuente, misma masa total
    return (w / w.mean()).to_numpy()


def eval_sets(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "coah_val": df[(df.source == "coah") & (df.split == "val")],
        "coah_test": df[(df.source == "coah") & (df.split == "test")],
        "coar_test": df[(df.source == "coar") & (df.split == "test")],
    }
