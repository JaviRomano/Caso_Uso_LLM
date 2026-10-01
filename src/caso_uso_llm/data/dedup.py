"""Duplicados exactos y casi duplicados (MinHash/LSH), dentro de cada fuente y entre fuentes."""

import pandas as pd
from datasketch import MinHash, MinHashLSH

from caso_uso_llm.data.normalize import dedup_key

NEAR_DUP_THRESHOLD = 0.8  # Jaccard estimada sobre 5-gramas de caracteres de la clave
NUM_PERM = 128
SHINGLE = 5
SOURCE_PRIORITY = {
    "coah": 0,
    "coar": 1,
    "ahr": 2,
}  # ante un duplicado entre fuentes se queda el hotel


def _minhash(key: str, seed: int) -> MinHash:
    m = MinHash(num_perm=NUM_PERM, seed=seed)
    grams = {key[i : i + SHINGLE] for i in range(max(1, len(key) - SHINGLE + 1))}
    for g in grams:
        m.update(g.encode("utf-8"))
    return m


def _clusters(pairs: list[tuple[int, int]], n: int) -> list[int]:
    """Union-find: devuelve para cada fila el id de su clúster (el menor índice del grupo)."""
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return [find(i) for i in range(n)]


def find_duplicates(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Añade `dup_cluster` y `dup_kind` ('exact' | 'near' | None) sin borrar nada.

    El texto que se compara es título + texto: dos reseñas con el mismo cuerpo y distinto título
    siguen siendo la misma opinión.
    """
    df = df.reset_index(drop=True).copy()
    keys = (df["title"] + " " + df["text"]).map(dedup_key).tolist()
    n = len(df)

    exact_pairs, first_by_key = [], {}
    for i, k in enumerate(keys):
        if k in first_by_key:
            exact_pairs.append((first_by_key[k], i))
        else:
            first_by_key[k] = i

    lsh = MinHashLSH(threshold=NEAR_DUP_THRESHOLD, num_perm=NUM_PERM)
    near_pairs = []
    for i in sorted(first_by_key.values()):  # solo representantes de cada clave exacta
        mh = _minhash(keys[i], seed)
        near_pairs += [(j, i) for j in lsh.query(mh)]
        lsh.insert(str(i), mh)
    near_pairs = [(int(a), b) for a, b in near_pairs]

    cluster = _clusters(exact_pairs + near_pairs, n)
    exact_members = {i for p in exact_pairs for i in p}
    near_members = {i for p in near_pairs for i in p}
    df["dup_cluster"] = cluster
    sizes = df.groupby("dup_cluster")["id"].transform("size")
    df["dup_kind"] = None
    df.loc[[i in near_members for i in range(n)], "dup_kind"] = "near"
    df.loc[[i in exact_members for i in range(n)], "dup_kind"] = "exact"
    df.loc[sizes == 1, ["dup_kind"]] = None
    return df


def resolve_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Marca en `drop_reason` qué filas sobran.

    - Clúster con una sola etiqueta: se queda una fila (prioridad de fuente, luego orden).
    - Clúster con etiquetas distintas: no se sabe cuál es la buena, se descartan todas.
    """
    df = df.copy()
    if "drop_reason" not in df:
        df["drop_reason"] = None
    order = df["source"].map(SOURCE_PRIORITY).astype(int)
    df = df.assign(_order=order).sort_values(["dup_cluster", "_order"], kind="stable")
    multi = df.groupby("dup_cluster")["id"].transform("size") > 1
    conflict = df.groupby("dup_cluster")["label3"].transform("nunique") > 1
    first = ~df.duplicated("dup_cluster")
    alive = df["drop_reason"].isna()
    df.loc[alive & multi & conflict, "drop_reason"] = "duplicado_conflicto_etiqueta"
    df.loc[alive & multi & ~conflict & ~first, "drop_reason"] = "duplicado"
    return df.drop(columns="_order").sort_index()
