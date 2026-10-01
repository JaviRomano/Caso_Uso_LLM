"""Fase 3b · Evaluación realista del clasificador elegido (opción A, ensamble de 3 semillas).

Tres preguntas que el F1 de un test limpio no responde:
1. ¿Cuánto cambia la predicción si la reseña está mal escrita, sin título o en andaluz?
   (*flip rate* frente a la predicción sobre el texto original).
2. ¿Aguanta reseñas reales de otra web llenas de negaciones? (SFU, ciao.es).
3. Si solo se responden automáticamente las reseñas con confianza alta, ¿qué parte se cubre
   y con cuánto error? El umbral se elige con `coah_val` y se informa en `coah_test`.

Requiere los pesos de `uv run just train --options A --save`. Solo WSL2.
Uso: uv run just realista
"""

import json

import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from caso_uso_llm.classify import metrics as M
from caso_uso_llm.classify.datasets import LABELS, eval_sets, load
from caso_uso_llm.classify.finetune import SEEDS, Config, device, encode, model_dir, predict_proba
from caso_uso_llm.classify.stress import load_sfu_hoteles, perturbations
from caso_uso_llm.log import log
from caso_uso_llm.paths import RESULTS, ROOT
from caso_uso_llm.seed import DEFAULT_SEED

OPTION = "A"
MAX_ERROR = 0.05  # error máximo aceptable en las reseñas que se responden sin revisión
THRESHOLDS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99)
INVARIANT = ("sin_titulo", "informal", "erratas", "andaluz")  # no deberían cambiar la etiqueta


def ensemble_proba(frames: dict[str, pd.DataFrame], cfg: Config, dev) -> dict[str, np.ndarray]:
    """Media de probabilidades de las 3 semillas para cada conjunto (`input` es el texto).

    Los conjuntos cuyo nombre acaba en `@head_tail` se truncan conservando principio y final.
    """
    sums: dict[str, np.ndarray] = {}
    for seed in SEEDS:
        path = model_dir(cfg, OPTION, seed)
        if not path.exists():
            raise SystemExit(
                f"Faltan los pesos en {path}: ejecuta `uv run just train --options A --save`."
            )
        log(f"Modelo {OPTION} semilla {seed}: prediciendo {len(frames)} conjuntos")
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModelForSequenceClassification.from_pretrained(path).to(dev)
        for name, df in frames.items():
            strategy = "head_tail" if name.endswith("@head_tail") else "head"
            p = predict_proba(model, encode(tok, df, cfg, strategy=strategy), tok, cfg, dev)
            sums[name] = sums.get(name, 0) + p
        del model
        torch.cuda.empty_cache()
    return {k: v / len(SEEDS) for k, v in sums.items()}


def labels_of(p: np.ndarray) -> np.ndarray:
    return np.array(LABELS)[p.argmax(1)]


def coverage_table(y: pd.Series, p: np.ndarray, negatives_to_human: bool) -> list[dict]:
    """Por umbral: % respondido sin revisión, error en ese %, y tamaño de la cola humana.

    `negatives_to_human`: la arquitectura manda siempre a revisión las reseñas negativas
    (riesgo reputacional), sea cual sea la confianza.
    """
    y = y.to_numpy()
    pred, conf = labels_of(p), p.max(1)
    rows = []
    for t in THRESHOLDS:
        auto = conf >= t
        if negatives_to_human:
            auto &= pred != "negativo"
        n_auto = int(auto.sum())
        err = float((pred[auto] != y[auto]).mean()) if n_auto else 0.0
        rows.append(
            {
                "threshold": t,
                "auto_frac": round(n_auto / len(y), 3),
                "auto_error": round(err, 3),
                "auto_n": n_auto,
                "errors_n": int((pred[auto] != y[auto]).sum()),
            }
        )
    return rows


def pick_threshold(rows: list[dict]) -> float:
    """El umbral más bajo cuyo error, en validación, no supera MAX_ERROR."""
    ok = [r["threshold"] for r in rows if r["auto_error"] <= MAX_ERROR and r["auto_n"] > 0]
    return min(ok) if ok else max(THRESHOLDS)


def main(seed: int = DEFAULT_SEED) -> None:
    cfg = Config()
    dev = device()
    df = load()
    sets = eval_sets(df)
    variants = perturbations(sets["coah_test"], seed)
    sfu = load_sfu_hoteles()
    frames = {
        "coah_val": sets["coah_val"],
        **{f"test_{k}": v for k, v in variants.items()},
        "sfu_hoteles": sfu,
        "test_original@head_tail": variants["original"],
        "sfu_hoteles@head_tail": sfu,
    }
    log(f"Conjuntos: { {k: len(v) for k, v in frames.items()} }")
    probs = ensemble_proba(frames, cfg, dev)

    out: dict = {
        "option": OPTION,
        "seeds": list(SEEDS),
        "config_id": cfg.id,
        "max_error": MAX_ERROR,
    }
    # 1) Estrés por perturbación
    y = sets["coah_test"]["label3"]
    base_pred = labels_of(probs["test_original"])
    stress = {}
    for name in variants:
        pred = labels_of(probs[f"test_{name}"])
        stress[name] = {
            "f1_macro": round(M.f1_macro(y, pred), 4),
            "ci95": M.bootstrap_ci(y, pred, seed),
            "flip_rate": round(float((pred != base_pred).mean()), 4),
            "f1_per_class": M.per_class_f1(y, pred),
        }
        log(
            f"   {name:<12} F1 {stress[name]['f1_macro']:.3f} "
            f"· cambia {stress[name]['flip_rate']:.1%}"
        )
    out["stress"] = stress

    # 2) SFU: reseñas reales de otra web (solo 1–2★ y 4–5★)
    sp = labels_of(probs["sfu_hoteles"])
    out["sfu_hoteles"] = {
        "n": len(sfu),
        "accuracy": round(float((sp == sfu["label3"].to_numpy()).mean()), 4),
        "predicted_neutral": int((sp == "neutral").sum()),
        "confusion": M.confusion(sfu["label3"], sp),
        "errors": [{"id": i, "real": r, "pred": p, "input": t[:300]}
                   for i, r, p, t in zip(sfu["id"], sfu["label3"], sp, sfu["input"], strict=True)
                   if r != p],
    }  # fmt: skip
    log(
        f"   SFU: acierto {out['sfu_hoteles']['accuracy']:.1%} · "
        f"{out['sfu_hoteles']['predicted_neutral']} predichas neutral"
    )

    # 3) Cobertura frente a error: umbral elegido en val, informado en test
    cov = {}
    for policy, neg in (("solo_confianza", False), ("negativas_a_revision", True)):
        val_rows = coverage_table(sets["coah_val"]["label3"], probs["coah_val"], neg)
        test_rows = coverage_table(y, probs["test_original"], neg)
        t = pick_threshold(val_rows)
        chosen = next(r for r in test_rows if r["threshold"] == t)
        cov[policy] = {
            "val": val_rows,
            "test": test_rows,
            "threshold": t,
            "test_at_threshold": chosen,
        }
        log(
            f"   {policy}: umbral {t} -> test responde {chosen['auto_frac']:.0%} "
            f"con error {chosen['auto_error']:.1%}"
        )
    out["coverage"] = cov

    # 4) Truncado: solo el principio (como en el entrenamiento) frente a principio + final
    trunc = {}
    for name, ref in (("test_original", y), ("sfu_hoteles", sfu["label3"])):
        for strategy in ("head", "head_tail"):
            key = name if strategy == "head" else f"{name}@head_tail"
            pred = labels_of(probs[key])
            r = {"f1_macro": round(M.f1_macro(ref, pred), 4),
                 "accuracy": round(float((pred == ref.to_numpy()).mean()), 4)}  # fmt: skip
            trunc[f"{name}|{strategy}"] = r
            log(f"   {name} · {strategy}: acierto {r['accuracy']:.1%}")
    out["truncation"] = trunc

    (RESULTS / "phase3b_realista.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report(out, {k: len(v) for k, v in frames.items()})
    log("OK: results/phase3b_realista.json y reports/phase3b_realista.md")


def write_report(o: dict, n: dict) -> None:
    L = [
        "# Fase 3b · Evaluación realista del clasificador",
        "",
        f"Generado por `uv run just realista` · opción {o['option']}, "
        f"ensamble de semillas {o['seeds']} "
        f"(config `{o['config_id']}`). No editar a mano.",
        "",
        f"## 1. Robustez: variantes de `coah_test` (n={n['test_original']})",
        "",
        "Las variantes son sintéticas y no deberían cambiar la etiqueta (salvo `solo_titulo`, que "
        "quita información). *Cambia* = % de reseñas cuya predicción difiere de la del texto "
        "original.",
        "",
        "| Variante | F1 macro | IC 95 % | Cambia | F1 neutral |",
        "|---|---|---|---|---|",
    ]
    for name, r in o["stress"].items():
        L.append(f"| {name} | {r['f1_macro']:.3f} | {r['ci95'][0]:.3f}–{r['ci95'][1]:.3f} "
                 f"| {r['flip_rate']:.1%} | {r['f1_per_class']['neutral']:.3f} |")  # fmt: skip
    s = o["sfu_hoteles"]
    L += [
        "",
        f"## 2. Reseñas reales de otra web: SFU hoteles (ciao.es, n={s['n']})",
        "",
        f"Solo hay 1–2★ y 4–5★. Acierto: **{s['accuracy']:.1%}**; {s['predicted_neutral']} reseñas "
        "predichas como neutral (cuentan como error).",
        "",
        "| real \\ pred | " + " | ".join(LABELS) + " |",
        "|---|---|---|---|",
    ]
    L += [
        f"| {lab} | " + " | ".join(map(str, row)) + " |"
        for lab, row in zip(LABELS, s["confusion"], strict=True)
    ]
    L += ["", "Errores:", ""] + [
        f"- `{e['id']}` real {e['real']} → {e['pred']}: «{e['input'][:200]}…»" for e in s["errors"]
    ]
    L += [
        "",
        "## 3. Cobertura frente a error",
        "",
        "Se responde sin revisión humana solo si la confianza supera un umbral. El umbral se "
        f"elige en `coah_val` como el más bajo con error ≤ {o['max_error']:.0%}, y se informa "
        "en `coah_test`.",
        "",
    ]
    for policy, c in o["coverage"].items():
        ch = c["test_at_threshold"]
        title = (
            "Solo confianza"
            if policy == "solo_confianza"
            else "Además, todas las negativas a revisión"
        )
        L += [
            f"**{title}** — umbral {c['threshold']}: en test se responde el "
            f"**{ch['auto_frac']:.0%}** de las reseñas con un error del "
            f"**{ch['auto_error']:.1%}** ({ch['errors_n']} de {ch['auto_n']}); "
            f"el {1 - ch['auto_frac']:.0%} va a revisión.",
            "",
            "| Umbral | Val: respondido | Val: error | Test: respondido | Test: error |",
            "|---|---|---|---|---|",
        ]
        for v, t in zip(c["val"], c["test"], strict=True):
            L.append(f"| {v['threshold']} | {v['auto_frac']:.0%} | {v['auto_error']:.1%} "
                     f"| {t['auto_frac']:.0%} | {t['auto_error']:.1%} |")  # fmt: skip
        L.append("")
    L += [
        "## 4. Truncado de reseñas largas",
        "",
        "El modelo lee como máximo 384 tokens. `head` corta por el final (como en el "
        "entrenamiento); `head_tail` conserva los 128 primeros y los últimos, donde suele ir el "
        "veredicto. Solo cambia la inferencia: el modelo no se ha reentrenado.",
        "",
        "| Conjunto | Truncado | Acierto | F1 macro |",
        "|---|---|---|---|",
    ]
    for key, r in o["truncation"].items():
        name, strategy = key.split("|")
        L.append(f"| {name} | {strategy} | {r['accuracy']:.1%} | {r['f1_macro']:.3f} |")
    (ROOT / "reports" / "phase3b_realista.md").write_text(
        "\n".join(L) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
