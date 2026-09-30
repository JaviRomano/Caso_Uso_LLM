"""Particiones train/val/test (70/15/15). El test no se usa para elegir modelo."""

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

TEST_FRAC = 0.15
VAL_FRAC = 0.15
BIG_GROUP_FRAC = 0.05  # un establecimiento con más del 5 % de las reseñas va siempre a train


def split_stratified(df: pd.DataFrame, seed: int) -> pd.Series:
    """COAH: sin grupo disponible, se estratifica por rating (1–5) para conservar el 4★."""
    idx = df.index.to_numpy()
    rest, test = train_test_split(
        idx, test_size=TEST_FRAC, stratify=df["rating"], random_state=seed
    )
    train, val = train_test_split(
        rest,
        test_size=VAL_FRAC / (1 - TEST_FRAC),
        stratify=df.loc[rest, "rating"],
        random_state=seed,
    )
    return _labels(df.index, train, val, test)


def split_grouped(df: pd.DataFrame, group_col: str, seed: int) -> pd.Series:
    """COAR: todas las reseñas de un establecimiento caen en la misma partición.

    Los establecimientos con más del 5 % de las reseñas van directos a train: si uno de ellos cae
    en test (el mayor de COAR tiene el 13 %), el test mide ese restaurante y no el dominio.
    Con el resto, StratifiedGroupKFold: un pliegue es test y, de lo que queda, otro es val.
    """
    share = df[group_col].map(df[group_col].value_counts(normalize=True))
    big = df.index[share > BIG_GROUP_FRAC]
    pool = df.drop(index=big)
    # Pliegues calculados sobre el total para que test y val se acerquen al 15 % del total.
    n_folds = max(2, round(len(pool) / (TEST_FRAC * len(df))))
    sgkf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    rest_pos, test_pos = next(sgkf.split(pool, pool["label3"], pool[group_col]))
    rest = pool.iloc[rest_pos]
    n_folds = max(2, round(len(rest) / (VAL_FRAC * len(df))))
    sgkf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    train_pos, val_pos = next(sgkf.split(rest, rest["label3"], rest[group_col]))
    train = rest.index[train_pos].append(big)
    return _labels(df.index, train, rest.index[val_pos], pool.index[test_pos])


def _labels(index: pd.Index, train, val, test) -> pd.Series:
    s = pd.Series(None, index=index, dtype="object")
    s.loc[train], s.loc[val], s.loc[test] = "train", "val", "test"
    assert s.notna().all()
    return s
