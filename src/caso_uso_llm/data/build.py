"""Pipeline de datos de la Fase 2: crudo -> limpio -> particiones + reports/data_report.md.

Uso: uv run just data
Todas las cifras del informe salen de aquí; no se editan a mano.
"""

import re
from collections import Counter
from datetime import date

import pandas as pd
from lingua import Language, LanguageDetectorBuilder
from sklearn.model_selection import train_test_split

from caso_uso_llm.data import normalize as N
from caso_uso_llm.data.dedup import NEAR_DUP_THRESHOLD, find_duplicates, resolve_duplicates
from caso_uso_llm.data.download import AHR_FILE, SOURCES
from caso_uso_llm.data.sources import load_ahr, load_coah, load_coar
from caso_uso_llm.data.split import split_grouped, split_stratified
from caso_uso_llm.log import log
from caso_uso_llm.paths import DATA_INTERIM, DATA_PROCESSED, DATA_RAW, ROOT, ensure_dirs
from caso_uso_llm.seed import DEFAULT_SEED, set_seed

REPORT = ROOT / "reports" / "data_report.md"
AHR_PAGE = "https://www.kaggle.com/datasets/chizhikchi/andalusian-hotels-reviews-unbalanced"
SHORT_WORDS = 5
MIN_ES_CONF = 0.10  # R17: el texto no español tenía <= 0,01; el español mal detectado, >= 0,14
MAX_QMARK_FRAC = 0.30  # R16: texto en otro alfabeto que se perdió al extraerlo ("??????")
LANGS = [Language.SPANISH, Language.ENGLISH, Language.FRENCH, Language.GERMAN,
         Language.ITALIAN, Language.PORTUGUESE, Language.CATALAN]  # fmt: skip
_MOJIBAKE = re.compile(r"Ã[\x80-\xbf]|Â|â€")


def clean_text(df: pd.DataFrame, rules: list) -> pd.DataFrame:
    """Aplica R1–R7 y R14 y apunta cuántos textos toca cada regla."""
    df = df.copy()
    for col in ("title", "text"):
        raw = df[f"{col}_raw"]
        unq = raw.map(N.unquote_csv)
        rules.append(("R5 comillas CSV", col, (unq != raw).groupby(df["source"]).sum()))
        rules.append(
            ("R2 mojibake detectado", col, raw.str.contains(_MOJIBAKE).groupby(df["source"]).sum())
        )
        norm = unq.map(N.normalize_text)
        rules.append(("R1–R6 texto modificado", col, (norm != unq).groupby(df["source"]).sum()))
        df[col] = norm
    stripped = df["title"].map(N.strip_wrapping_quotes)
    rules.append(
        ("R7 comillas del título", "title", (stripped != df["title"]).groupby(df["source"]).sum())
    )
    df["title"] = stripped

    pii_counts = Counter()
    for col in ("title", "text"):
        masked = df[col].map(N.mask_pii)
        df[col] = masked.map(lambda t: t[0])
        for src, counts in zip(df["source"], masked.map(lambda t: t[1]), strict=True):
            for k, v in counts.items():
                pii_counts[(src, k)] += v
    df["pii_masked"] = pii_counts.total()
    for (src, kind), n in sorted(pii_counts.items()):
        rules.append((f"R14 PII: {kind}", "title+text", pd.Series({src: n})))
    return df.drop(columns=["title_raw", "text_raw", "pii_masked"])


def detect_language(df: pd.DataFrame) -> pd.DataFrame:
    detector = (
        LanguageDetectorBuilder.from_languages(*LANGS).with_preloaded_language_models().build()
    )
    texts = (df["title"] + ". " + df["text"]).tolist()
    langs = detector.detect_languages_in_parallel_of(texts)
    conf = detector.compute_language_confidence_values_in_parallel(texts)
    df = df.copy()
    df["lang"] = [lang.iso_code_639_1.name.lower() if lang else "und" for lang in langs]
    df["lang_conf"] = [
        round(next(c.value for c in cs if c.language == Language.SPANISH), 3) for cs in conf
    ]
    return df


def leak_reproduction() -> dict:
    """Reproduce la fuga del proyecto original con su mismo split (legacy/src/encoder/train.py)."""
    df = pd.read_csv(DATA_RAW / "Balanced_AHR.csv")
    train, test = train_test_split(df, test_size=0.2, random_state=42)
    exact = test["review_text"].isin(set(train["review_text"])).mean()
    by_label = (
        test.assign(leak=test["review_text"].isin(set(train["review_text"])))
        .groupby("label")["leak"]
        .mean()
    )
    keys = df["review_text"].fillna("").map(N.dedup_key)
    return {
        "rows": len(df),
        "unique_texts": df["review_text"].nunique(),
        "test_rows": len(test),
        "test_in_train": exact,
        "test_in_train_by_label": by_label.round(3).to_dict(),
        "keys": set(keys),
        "ratings": df["rating"].value_counts().sort_index().to_dict(),
    }


def build_ahr(core: pd.DataFrame, seed: int) -> dict:
    """AHR como test fuera de distribución: mismas reglas que COAH/COAR y, además, fuera
    cualquier reseña que coincida (exacta o casi) con una de COAH o COAR, de cualquier partición.
    """
    raw = load_ahr()
    raw["label3"] = raw["rating"].map(N.label3)
    rules: list = []
    df = clean_text(raw, rules)
    df["is_synthetic"] = False
    df["n_words"] = df["text"].str.split().str.len()
    df["drop_reason"] = None
    funnel = [("Crudo (sin las filas de COAH)", len(df))]
    df.loc[df["text"].str.len() == 0, "drop_reason"] = "texto_vacio"
    qmarks = df["text"].str.count(r"\?") / df["text"].str.len().clip(lower=1)
    df.loc[df["drop_reason"].isna() & (qmarks > MAX_QMARK_FRAC), "drop_reason"] = "texto_ilegible"
    log("   AHR: idioma")
    df = detect_language(df)
    not_es = (df["lang"] != "es") & (df["lang_conf"] < MIN_ES_CONF)
    df.loc[df["drop_reason"].isna() & not_es, "drop_reason"] = "idioma_no_es"
    funnel.append(("Solo español", int(df["drop_reason"].isna().sum())))

    log("   AHR: solape con COAH/COAR (MinHash)")
    cols = ["id", "source", "title", "text", "label3"]
    combo = pd.concat([core[cols], df.loc[df["drop_reason"].isna(), cols]], ignore_index=True)
    cl = find_duplicates(combo, seed=seed)
    core_clusters = set(cl.loc[cl["source"] != "ahr", "dup_cluster"])
    overlap = cl.loc[(cl["source"] == "ahr") & cl["dup_cluster"].isin(core_clusters), "id"]
    df.loc[df["id"].isin(overlap), "drop_reason"] = "solapa_coah_coar"
    funnel.append(("Sin solape con COAH/COAR", int(df["drop_reason"].isna().sum())))

    log("   AHR: duplicados internos")
    dups = resolve_duplicates(find_duplicates(df[df["drop_reason"].isna()], seed=seed))
    dups = dups.set_index("id")
    df = df.set_index("id")
    df.loc[dups.index, "drop_reason"] = dups["drop_reason"]
    df = df.reset_index()
    funnel.append(("Sin duplicados", int(df["drop_reason"].isna().sum())))
    final = df[df["drop_reason"].isna()].copy()
    final["split"] = "ood_test"
    return {"all": df, "final": final, "rules": rules, "funnel": funnel}


def build(seed: int = DEFAULT_SEED) -> None:
    set_seed(seed)
    ensure_dirs()
    rules: list = []

    log("Leyendo COAH (XML) y COAR (TSV clave/valor)")
    raw = pd.concat([load_coah(), load_coar()], ignore_index=True)
    log(f"   {raw['source'].value_counts().to_dict()}")
    log("Normalizando texto (R1–R7) y enmascarando datos personales (R14)")
    raw["label3"] = raw["rating"].map(N.label3)
    funnel = [("Crudo", raw["source"].value_counts())]

    df = clean_text(raw, rules)
    df["is_synthetic"] = False
    df["n_words"] = df["text"].str.split().str.len()
    df["drop_reason"] = None
    df.loc[df["text"].str.len() == 0, "drop_reason"] = "texto_vacio"
    qmarks = df["text"].str.count(r"\?") / df["text"].str.len().clip(lower=1)
    df.loc[df["drop_reason"].isna() & (qmarks > MAX_QMARK_FRAC), "drop_reason"] = "texto_ilegible"
    funnel.append(
        ("Sin texto vacío ni ilegible", df[df["drop_reason"].isna()]["source"].value_counts())
    )

    log("Detectando idioma (lingua, 7 idiomas)")
    df = detect_language(df)
    not_es = (df["lang"] != "es") & (df["lang_conf"] < MIN_ES_CONF)
    df.loc[df["drop_reason"].isna() & not_es, "drop_reason"] = "idioma_no_es"
    funnel.append(("Solo español", df[df["drop_reason"].isna()]["source"].value_counts()))

    log("Buscando duplicados exactos y casi duplicados (MinHash)")
    # Los duplicados se buscan solo entre las filas que siguen vivas; las ya descartadas
    # conservan su motivo.
    dups = resolve_duplicates(find_duplicates(df[df["drop_reason"].isna()], seed=seed))
    dups = dups.set_index("id")
    df = df.set_index("id")
    df["dup_cluster"] = dups["dup_cluster"]
    df["dup_kind"] = dups["dup_kind"]
    df.loc[dups.index, "drop_reason"] = dups["drop_reason"]
    df = df.reset_index()
    funnel.append(("Sin duplicados", df[df["drop_reason"].isna()]["source"].value_counts()))

    log(f"   descartes: {df['drop_reason'].value_counts().to_dict()}")
    log("Particiones: COAH estratificado, COAR agrupado por restaurante")
    final = df[df["drop_reason"].isna()].copy()
    long_cut = final.groupby("source")["n_words"].transform(lambda s: s.quantile(0.99))
    final["flag_short"] = final["n_words"] < SHORT_WORDS
    final["flag_long"] = final["n_words"] > long_cut
    final["split"] = None
    coah = final["source"] == "coah"
    final.loc[coah, "split"] = split_stratified(final[coah], seed)
    final.loc[~coah, "split"] = split_grouped(final[~coah], "establishment_id", seed)

    df.to_parquet(DATA_INTERIM / "reviews_all.parquet", index=False)
    for src in ("coah", "coar"):
        final[final["source"] == src].to_parquet(DATA_PROCESSED / f"{src}.parquet", index=False)

    ahr = None
    if AHR_FILE.exists():
        log("AHR completo: test fuera de distribución")
        ahr = build_ahr(df, seed)
        ahr["final"].to_parquet(DATA_PROCESSED / "ahr_ood.parquet", index=False)
        log(f"   AHR: {len(ahr['final'])} reseñas -> data/processed/ahr_ood.parquet")
    else:
        log("AHR no descargado: se omite (`uv run just data-download`)")

    log("Reproduciendo la fuga del proyecto original")
    leak = leak_reproduction()
    write_report(raw, df, final, funnel, rules, leak, seed, ahr)
    log(f"OK: {len(final)} reseñas -> data/processed/, informe en {REPORT.relative_to(ROOT)}")


# --- Informe ----------------------------------------------------------------------------------


def _md(df: pd.DataFrame) -> str:
    return df.to_markdown()


def _dist(df: pd.DataFrame, by: list[str], col: str) -> pd.DataFrame:
    t = df.groupby(by)[col].value_counts().unstack(fill_value=0)
    t["total"] = t.sum(axis=1)
    return t


def write_report(raw, df, final, funnel, rules, leak, seed, ahr=None) -> None:
    REPORT.parent.mkdir(exist_ok=True)
    rev = {s.dest.split("/")[-1]: s.revision[:7] for s in SOURCES}
    L = [
        "# Informe de datos (Fase 2)",
        "",
        f"Generado por `uv run just data` el {date.today().isoformat()} · semilla {seed}. "
        "No editar a mano.",
        "",
        "## 1. Fuentes",
        "",
        "| Fuente | Commit HF | Filas crudas | Dominio |",
        "|---|---|---|---|",
        f"| COAH | `{rev['coah']}` | {(raw.source == 'coah').sum()} | hotel |",
        f"| COAR | `{rev['coar']}` | {(raw.source == 'coar').sum()} | restaurante |",
        "",
        "COAR trae 4.932 registros; la documentación de SINAI habla de 2.202.",
        "",
        "## 2. Reglas aplicadas (textos afectados)",
        "",
        "| Regla | Campo | COAH | COAR |",
        "|---|---|---|---|",
    ]
    for rule, col, counts in rules:
        L.append(
            f"| {rule} | {col} | {int(counts.get('coah', 0))} | {int(counts.get('coar', 0))} |"
        )
    L += [
        "",
        "Reglas de metadatos (R8–R13) sin excepciones: un valor no reconocido detiene el pipeline.",
        "",
        "## 3. Embudo",
        "",
        "| Paso | COAH | COAR |",
        "|---|---|---|",
    ]
    for step, counts in funnel:
        L.append(f"| {step} | {counts.get('coah', 0)} | {counts.get('coar', 0)} |")
    reasons = (
        df["drop_reason"]
        .fillna("conservada")
        .to_frame()
        .join(df["source"])
        .value_counts()
        .unstack(fill_value=0)
    )
    L += ["", "Motivos de descarte:", "", _md(reasons), ""]
    kinds = (
        df[df["dup_kind"].notna()].groupby(["source", "dup_kind"]).size().rename("filas").to_frame()
    )
    L += [
        f"Filas en clústeres de duplicados (umbral Jaccard {NEAR_DUP_THRESHOLD}):",
        "",
        _md(kinds),
        "",
    ]
    cross = df[df["dup_kind"].notna()].groupby("dup_cluster")["source"].nunique().gt(1).sum()
    L += [f"Clústeres con las dos fuentes: {cross}.", ""]

    L += [
        "## 4. Resultado por partición",
        "",
        "Etiqueta:",
        "",
        _md(_dist(final, ["source", "split"], "label3")),
        "",
    ]
    L += ["Rating:", "", _md(_dist(final, ["source", "split"], "rating")), ""]
    coar = final[final["source"] == "coar"]
    g = coar.groupby("split").agg(
        establecimientos=("establishment_id", "nunique"),
        reseñas=("id", "size"),
        mayor_establecimiento=(
            "establishment_id",
            lambda s: round(s.value_counts().iloc[0] / len(s), 3),
        ),
    )
    overlap = set(coar[coar.split == "train"].establishment_id) & set(
        coar[coar.split == "test"].establishment_id
    )
    L += [
        "COAR, agrupado por establecimiento:",
        "",
        _md(g),
        "",
        f"Establecimientos compartidos entre train y test: {len(overlap)}.",
        "",
    ]
    L += [
        "COAR, origen del autor (R13, proxy de traducción automática):",
        "",
        _md(_dist(coar, ["split"], "reviewer_origin")),
        "",
    ]
    L += [
        "Marcas (no se descartan): ",
        "",
        _md(final.groupby("source")[["flag_short", "flag_long"]].sum()),
        "",
    ]

    L += [
        "## 5. Reproducción de la fuga del proyecto original",
        "",
        f"`Balanced_AHR.csv`: {leak['rows']} filas, {leak['unique_texts']} textos únicos; "
        f"ratings {leak['ratings']}.",
        f"Con el split original (`train_test_split(test_size=0.2, random_state=42)`), el "
        f"**{leak['test_in_train']:.1%}** de las {leak['test_rows']} filas de test "
        "aparece literal en train.",
        f"Por etiqueta: {leak['test_in_train_by_label']}.",
        "",
    ]
    coah_keys = set(raw.loc[raw.source == "coah", "text_raw"].map(N.dedup_key))
    both = len(coah_keys & leak["keys"])
    L += [
        f"Textos de COAH presentes en `Balanced_AHR.csv`: {both} de {len(coah_keys)}. "
        "Si alguna vez se combina con AHR, hay que deduplicar contra COAH.",
        "",
    ]
    if ahr is not None:
        a = ahr["final"]
        L += [
            "## 6. AHR como test fuera de distribución",
            "",
            f"AHR completo ([Kaggle]({AHR_PAGE}), v3, CC BY-NC 4.0): reseñas de TripAdvisor de "
            "2021, con nombre de hotel. Solo se evalúa con él; nunca se entrena. Se quitan sus "
            "filas sin hotel (son COAH) y cualquier reseña que coincida, exacta o casi, con COAH "
            "o COAR.",
            "",
            "| Paso | Reseñas |",
            "|---|---|",
        ]
        L += [f"| {step} | {n} |" for step, n in ahr["funnel"]]
        reasons = ahr["all"]["drop_reason"].fillna("conservada").value_counts()
        by_rating = (
            a.groupby("rating")["label3"]
            .agg(["first", "size"])
            .rename(columns={"first": "etiqueta", "size": "reseñas"})
        )
        provinces = ", ".join(f"{k} {v}" for k, v in a["province"].value_counts().items())
        L += ["", "Motivos de descarte:", "", _md(reasons.to_frame("reseñas")), ""]
        L += [f"Resultado: {len(a)} reseñas de {a['establishment_id'].nunique()} hoteles.", ""]
        L += [_md(by_rating), "", f"Provincias: {provinces}.", ""]
    L += [
        "## 7. Pendiente",
        "",
        '- Nombres sin tratamiento ni cargo ("gracias a Emilio"): NER con Presidio.',
        "- Etiquetas ruidosas con `cleanlab`: necesita las probabilidades del baseline (Fase 3).",
        "- Traducción automática: `reviewer_origin` es un proxy; validar a mano una muestra.",
    ]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")  # LF también en Windows


if __name__ == "__main__":
    build()
