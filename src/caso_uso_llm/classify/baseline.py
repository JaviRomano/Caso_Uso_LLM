"""Baseline TF-IDF + regresión logística para las opciones A, A_sin_trad y B.

La opción C (secuencial: COAR y luego COAH) no se evalúa aquí: la regresión logística es
convexa y converge al mismo óptimo empiece donde empiece, así que C sería idéntica a B.
C se mide con el fine-tuning de mRoBERTa, donde el punto de partida sí importa.

Uso: uv run just baseline
"""

import json
from datetime import date

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import FeatureUnion, make_pipeline

from caso_uso_llm.classify import metrics as M
from caso_uso_llm.classify.datasets import LABELS, OPTIONS, eval_sets, load, train_set
from caso_uso_llm.log import log
from caso_uso_llm.paths import RESULTS, ROOT, ensure_dirs
from caso_uso_llm.seed import DEFAULT_SEED, set_seed

C_GRID = (0.1, 0.3, 1.0, 3.0, 10.0)
CV_SPLITS, CV_REPEATS = 5, 3
REPORT = ROOT / "reports" / "phase3_baseline.md"
RESULTS_JSON = RESULTS / "phase3_baseline.json"


def make_model(c: float, seed: int):
    features = FeatureUnion(
        [
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True
                ),
            ),
        ]
    )  # el vectorizador pasa a minúsculas: es SU preprocesado, no el del dataset
    return make_pipeline(features, LogisticRegression(C=c, max_iter=3000, random_state=seed))


def fit(train: pd.DataFrame, weights: np.ndarray, c: float, seed: int):
    model = make_model(c, seed)
    model.fit(train["input"], train["label3"], logisticregression__sample_weight=weights)
    return model


def run_option(df, option, sets, seed) -> dict:
    train, w = train_set(df, option)
    log(f"== Opción {option.name}: {option.description} · {len(train)} filas de train")
    # 1) Selección de C con coah_val (el test no se toca)
    val = sets["coah_val"]
    val_scores = {}
    for c in C_GRID:
        val_scores[c] = M.f1_macro(val["label3"], fit(train, w, c, seed).predict(val["input"]))
        log(f"   C={c:<5} F1 macro coah_val = {val_scores[c]:.3f}")
    best_c = max(val_scores, key=val_scores.get)
    log(f"   Mejor C = {best_c}; reentrenando")
    model = fit(train, w, best_c, seed)

    out = {
        "option": option.name,
        "description": option.description,
        "train_rows": len(train),
        "train_rows_by_source": train["source"].value_counts().to_dict(),
        "val_f1_by_C": {str(c): round(s, 4) for c, s in val_scores.items()},
        "best_C": best_c,
        "predictions": {},
    }
    for name, s in sets.items():
        pred = model.predict(s["input"])
        out["predictions"][name] = pred.tolist()
        out[name] = {
            "f1_macro": round(M.f1_macro(s["label3"], pred), 4),
            "ci95": M.bootstrap_ci(s["label3"], pred, seed),
            "f1_per_class": M.per_class_f1(s["label3"], pred),
            "confusion": M.confusion(s["label3"], pred),
        }
        ci = out[name]["ci95"]
        log(
            f"   {name:<9} F1 macro = {out[name]['f1_macro']:.3f} (IC 95 % {ci[0]:.3f}–{ci[1]:.3f})"
        )
    out["cv"] = cross_validate(df, option, best_c, seed)
    return out


def cross_validate(df, option, c, seed) -> dict:
    """F1 macro en validación cruzada repetida sobre COAH train+val (el test queda fuera).

    En cada pliegue se entrena con el resto de COAH (+ COAR train si la opción lo usa).
    """
    pool = df[(df.source == "coah") & df.split.isin(["train", "val"])]
    rskf = RepeatedStratifiedKFold(n_splits=CV_SPLITS, n_repeats=CV_REPEATS, random_state=seed)

    def one_fold(tr, te) -> float:
        train, w = train_set(df, option, coah_part=pool.iloc[tr])
        held = pool.iloc[te]
        return M.f1_macro(held["label3"], fit(train, w, c, seed).predict(held["input"]))

    # Pliegues en paralelo (uno por núcleo); se registran según terminan.
    total = CV_SPLITS * CV_REPEATS
    jobs = (delayed(one_fold)(tr, te) for tr, te in rskf.split(pool, pool["rating"]))
    scores = []
    for score in Parallel(n_jobs=-1, return_as="generator_unordered")(jobs):
        scores.append(score)
        log(f"   CV pliegue {len(scores):>2}/{total}: F1 macro = {score:.3f}")
    log(f"   CV media {np.mean(scores):.3f} ± {np.std(scores):.3f}")
    return {"mean": round(float(np.mean(scores)), 4), "std": round(float(np.std(scores)), 4),
            "folds": len(scores)}  # fmt: skip


def main(seed: int = DEFAULT_SEED) -> None:
    set_seed(seed)
    ensure_dirs()
    df = load()
    sets = eval_sets(df)
    log(f"Datos: {', '.join(f'{k}={len(v)}' for k, v in sets.items())}")
    results = {opt.name: run_option(df, opt, sets, seed) for opt in OPTIONS}
    log("Bootstrap pareado de A y A_sin_trad frente a B")

    y = sets["coah_test"]["label3"]
    comparisons = {
        f"{a}_vs_B": M.paired_bootstrap(
            y,
            results[a]["predictions"]["coah_test"],
            results["B"]["predictions"]["coah_test"],
            seed,
        )
        for a in ("A", "A_sin_trad")
    }
    payload = {"date": date.today().isoformat(), "seed": seed, "labels": LABELS,
               "results": results, "comparisons_coah_test": comparisons}  # fmt: skip
    RESULTS_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report(payload, sets)
    log(f"OK: {RESULTS_JSON.relative_to(ROOT)} y {REPORT.relative_to(ROOT)}")


def write_report(p: dict, sets) -> None:
    R = p["results"]
    n = {k: len(v) for k, v in sets.items()}
    L = [
        "# Fase 3 · Baseline TF-IDF + regresión logística",
        "",
        f"Generado por `uv run just baseline` el {p['date']} · semilla {p['seed']}. "
        "No editar a mano.",
        "",
        "Selección de `C` con `coah_val`; `coah_test` es la métrica principal (hoteles). "
        "La opción C (secuencial) no aplica a un modelo convexo: se evalúa con mRoBERTa.",
        "",
        "| Opción | Filas de train | C | CV COAH (media ± sd) "
        f"| F1 macro `coah_test` (n={n['coah_test']}) "
        f"| IC 95 % | F1 macro `coar_test` (n={n['coar_test']}) |",
        "|---|---|---|---|---|---|---|",
    ]
    for k, r in R.items():
        t, o = r["coah_test"], r["coar_test"]
        L.append(
            f"| **{k}** · {r['description']} | {r['train_rows']} | {r['best_C']} "
            f"| {r['cv']['mean']:.3f} ± {r['cv']['std']:.3f} | **{t['f1_macro']:.3f}** "
            f"| {t['ci95'][0]:.3f}–{t['ci95'][1]:.3f} | {o['f1_macro']:.3f} |"
        )
    L += ["", "## F1 por clase en `coah_test`", "", "| Opción | " + " | ".join(p["labels"]) + " |",
          "|---|---|---|---|"]  # fmt: skip
    for k, r in R.items():
        L.append(
            f"| {k} | "
            + " | ".join(f"{r['coah_test']['f1_per_class'][lab]:.3f}" for lab in p["labels"])
            + " |"
        )
    L += ["", "## ¿Las diferencias superan el ruido del test? (bootstrap pareado)", "",
          "| Comparación | ΔF1 macro | IC 95 % | P(mejor que B) |",
          "|---|---|---|---|"]  # fmt: skip
    for k, c in p["comparisons_coah_test"].items():
        L.append(
            f"| {k} | {c['diff']:+.3f} | {c['ci95'][0]:+.3f} a {c['ci95'][1]:+.3f} "
            f"| {c['p_a_better']:.2f} |"
        )
    L += ["", "## Matrices de confusión en `coah_test` (filas: real; columnas: predicho)", ""]
    for k, r in R.items():
        cm = r["coah_test"]["confusion"]
        L += [
            f"**{k}**",
            "",
            "| real \\ pred | " + " | ".join(p["labels"]) + " |",
            "|---|---|---|---|",
        ]
        L += [
            f"| {lab} | " + " | ".join(str(v) for v in row) + " |"
            for lab, row in zip(p["labels"], cm, strict=True)
        ]
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
