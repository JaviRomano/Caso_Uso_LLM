"""Fine-tuning de mRoBERTa (BSC) para las opciones A, A_sin_trad, B y C (solo en WSL2 + ROCm).

- Selección: parada temprana con el F1 macro de la validación (`coah_val`; en la primera
  etapa de C, `coar_val`). El test no interviene en ninguna decisión.
- Varias semillas por opción: con 1.253 reseñas de train, la semilla mueve el F1 varias
  centésimas y una sola ejecución no permite comparar opciones.
- Cada ejecución (opción, semilla) se guarda en results/phase3_roberta/ en cuanto termina;
  si el proceso se corta, al relanzarlo se salta lo ya hecho.

Uso:  uv run just train                       # todas las opciones, 3 semillas
      uv run just train --options B,C --seeds 42 --max-epochs 2   # prueba rápida
"""

import argparse
import copy
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from caso_uso_llm.classify import metrics as M
from caso_uso_llm.classify.datasets import (
    FINETUNE_OPTIONS,
    LABELS,
    OPTIONS,
    coar_stage,
    eval_sets,
    load,
    train_set,
)
from caso_uso_llm.log import log
from caso_uso_llm.paths import MODELS, RESULTS, ROOT, ensure_dirs
from caso_uso_llm.seed import set_seed

# RoBERTa-BNE (PlanTL) se retiró en julio de 2025 y su repo ya no tiene pesos. mRoBERTa es su
# sucesor en BSC: misma arquitectura, multilingüe con mucho español, catalán, gallego y euskera.
MODEL_ID = "BSC-LT/mRoBERTa"
MODEL_REVISION = "0bede83320adb31f196fc6a99b23a2ce2b3367fe"
RUNS_DIR = RESULTS / "phase3_roberta"
SEEDS = (42, 43, 44)
LABEL2ID = {lab: i for i, lab in enumerate(LABELS)}


@dataclass(frozen=True)
class Config:
    max_len: int = 384  # la mediana de COAH son ~100 palabras; el p99, ~540 (se trunca el 1–2 %)
    batch_size: int = 16
    lr: float = 2e-5
    weight_decay: float = 0.01
    warmup_frac: float = 0.1
    max_epochs: int = 8
    patience: int = 2  # épocas sin mejorar el F1 de validación antes de parar
    grad_clip: float = 1.0

    @property
    def id(self) -> str:
        """Huella de la configuración: ejecuciones con configs distintas no se mezclan."""
        blob = json.dumps(asdict(self), sort_keys=True) + MODEL_REVISION
        return hashlib.sha1(blob.encode()).hexdigest()[:8]


# --- Datos --------------------------------------------------------------------------------------


HEAD_TOKENS = 128  # en "head_tail": tokens del principio; el resto del cupo, del final


def _head_tail(ids: list[int], max_len: int) -> list[int]:
    """Principio y final de un texto largo: en las reseñas, el veredicto suele ir al final."""
    if len(ids) <= max_len:
        return ids
    return ids[:HEAD_TOKENS] + ids[-(max_len - HEAD_TOKENS) :]


def encode(tokenizer, df: pd.DataFrame, cfg: Config, weights=None, strategy="head") -> list[dict]:
    """Tokeniza. `strategy`: 'head' corta por el final; 'head_tail' conserva principio y final."""
    if strategy == "head":
        enc = tokenizer(df["input"].tolist(), truncation=True, max_length=cfg.max_len)
    elif strategy == "head_tail":
        enc = tokenizer(df["input"].tolist(), truncation=False, verbose=False)
        enc = {
            "input_ids": [_head_tail(x, cfg.max_len) for x in enc["input_ids"]],
            "attention_mask": [_head_tail(x, cfg.max_len) for x in enc["attention_mask"]],
        }
    else:
        raise ValueError(strategy)
    labels = df["label3"].map(LABEL2ID).tolist()
    w = np.ones(len(df)) if weights is None else weights
    return [
        {"input_ids": ids, "attention_mask": am, "labels": y, "weight": float(wi)}
        for ids, am, y, wi in zip(enc["input_ids"], enc["attention_mask"], labels, w, strict=True)
    ]


def collate(tokenizer):
    def fn(batch):
        pad = tokenizer.pad(
            [{"input_ids": b["input_ids"], "attention_mask": b["attention_mask"]} for b in batch],
            return_tensors="pt",
        )
        pad["labels"] = torch.tensor([b["labels"] for b in batch])
        pad["weight"] = torch.tensor([b["weight"] for b in batch], dtype=torch.float32)
        return pad

    return fn


# --- Entrenamiento --------------------------------------------------------------------------------


def device() -> torch.device:
    if not torch.cuda.is_available():
        raise SystemExit("Sin GPU: ejecuta esto en WSL2 con ROCm (`uv run just gpu`).")
    if torch.version.hip is None:
        raise SystemExit("torch no es la build de ROCm (torch.version.hip es None).")
    return torch.device("cuda")  # en ROCm, "cuda" es la GPU AMD


@torch.no_grad()
def predict_proba(model, data, tokenizer, cfg, dev) -> np.ndarray:
    model.eval()
    probs = []
    for batch in DataLoader(data, batch_size=cfg.batch_size * 2, collate_fn=collate(tokenizer)):
        batch = {k: v.to(dev) for k, v in batch.items() if k in ("input_ids", "attention_mask")}
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = model(**batch).logits
        probs.append(torch.softmax(logits.float(), dim=-1).cpu().numpy())
    return np.concatenate(probs)


def f1_of(probs: np.ndarray, df: pd.DataFrame) -> float:
    return M.f1_macro(df["label3"], [LABELS[i] for i in probs.argmax(1)])


def train_stage(model, tokenizer, train_df, weights, val_df, cfg, dev, seed, tag) -> dict:
    """Una etapa de fine-tuning con pérdida ponderada y parada temprana por F1 de validación.

    Deja en `model` los pesos de la mejor época y devuelve el historial.
    """
    g = torch.Generator().manual_seed(seed)
    train = encode(tokenizer, train_df, cfg, weights)
    val = encode(tokenizer, val_df, cfg)
    loader = DataLoader(
        train, batch_size=cfg.batch_size, shuffle=True, generator=g, collate_fn=collate(tokenizer)
    )
    steps = cfg.max_epochs * len(loader)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    sched = get_linear_schedule_with_warmup(opt, math.ceil(cfg.warmup_frac * steps), steps)

    best = {"f1": -1.0, "epoch": 0, "state": None}
    history = []
    for epoch in range(1, cfg.max_epochs + 1):
        model.train()
        t0, total, n = time.perf_counter(), 0.0, 0
        for step, batch in enumerate(loader, start=1):
            batch = {k: v.to(dev) for k, v in batch.items()}
            with torch.autocast("cuda", dtype=torch.bfloat16):
                logits = model(
                    input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]
                ).logits
            loss_each = torch.nn.functional.cross_entropy(
                logits.float(), batch["labels"], reduction="none"
            )
            loss = (loss_each * batch["weight"]).sum() / batch["weight"].sum()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            opt.step()
            sched.step()
            total, n = total + loss.item(), n + 1
            if step % 50 == 0 or step == len(loader):
                log(
                    f"      {tag} época {epoch} paso {step:>4}/{len(loader)} "
                    f"· pérdida {total / n:.4f}"
                )
        val_f1 = f1_of(predict_proba(model, val, tokenizer, cfg, dev), val_df)
        improved = val_f1 > best["f1"]
        history.append(
            {"epoch": epoch, "train_loss": round(total / n, 4), "val_f1": round(val_f1, 4)}
        )
        log(
            f"   {tag} época {epoch}: pérdida {total / n:.4f} · F1 val {val_f1:.3f}"
            f"{'  ← mejor' if improved else ''} · {time.perf_counter() - t0:.0f}s"
        )
        if improved:
            best = {
                "f1": val_f1,
                "epoch": epoch,
                "state": copy.deepcopy({k: v.cpu() for k, v in model.state_dict().items()}),
            }
        elif epoch - best["epoch"] >= cfg.patience:
            log(f"   {tag} parada temprana: {cfg.patience} épocas sin mejorar")
            break
    model.load_state_dict(best["state"])
    return {"best_epoch": best["epoch"], "best_val_f1": round(best["f1"], 4), "history": history}


def new_model(dev):
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)),
        label2id=LABEL2ID,
    )
    return model.to(dev)


def model_dir(cfg: "Config", option_name: str, seed: int):
    """Dónde se guardan los pesos de una ejecución (models/ no va a git)."""
    return MODELS / "mroberta" / cfg.id / f"{option_name}_s{seed}"


def run(option, seed, df, sets, tokenizer, cfg, dev, save: bool = False) -> dict:
    set_seed(seed)
    model = new_model(dev)
    stages = {}
    if option.sequential:
        coar_train, coar_w, coar_val = coar_stage(df)
        log(f"   Etapa 1/2: COAR ({len(coar_train)} filas) · parada con coar_val")
        stages["coar"] = train_stage(
            model, tokenizer, coar_train, coar_w, coar_val, cfg, dev, seed, "[COAR]"
        )
        train_df, w = train_set(df, OPTIONS[0])  # la opción B: solo COAH
        log(f"   Etapa 2/2: COAH ({len(train_df)} filas) · parada con coah_val")
        stages["coah"] = train_stage(
            model, tokenizer, train_df, w, sets["coah_val"], cfg, dev, seed, "[COAH]"
        )
    else:
        train_df, w = train_set(df, option)
        log(f"   Train: {len(train_df)} filas {train_df['source'].value_counts().to_dict()}")
        stages["main"] = train_stage(
            model, tokenizer, train_df, w, sets["coah_val"], cfg, dev, seed, "[   ]"
        )

    out = {"option": option.name, "seed": seed, "stages": stages, "probs": {}, "metrics": {}}
    for name, s in sets.items():
        p = predict_proba(model, encode(tokenizer, s, cfg), tokenizer, cfg, dev)
        pred = [LABELS[i] for i in p.argmax(1)]
        out["probs"][name] = np.round(p, 5).tolist()
        out["metrics"][name] = {"f1_macro": round(M.f1_macro(s["label3"], pred), 4),
                                "f1_per_class": M.per_class_f1(s["label3"], pred)}  # fmt: skip
        log(f"   {name:<9} F1 macro = {out['metrics'][name]['f1_macro']:.3f}")
    if save:
        path = model_dir(cfg, option.name, seed)
        model.save_pretrained(path)
        tokenizer.save_pretrained(path)
        log(f"   Pesos guardados en {path.relative_to(ROOT)}")
    del model
    torch.cuda.empty_cache()
    return out


# --- Informe ------------------------------------------------------------------------------------


def summarize(runs: list[dict], sets, seed: int) -> dict:
    """Media ± sd entre semillas y un 'ensamble' (media de probabilidades) por opción."""
    by_opt: dict[str, list[dict]] = {}
    for r in runs:
        by_opt.setdefault(r["option"], []).append(r)
    summary, ens_pred = {}, {}
    for opt, rs in by_opt.items():
        summary[opt] = {"seeds": [r["seed"] for r in rs]}
        for name, s in sets.items():
            f1s = [r["metrics"][name]["f1_macro"] for r in rs]
            probs = np.mean([r["probs"][name] for r in rs], axis=0)
            pred = [LABELS[i] for i in probs.argmax(1)]
            summary[opt][name] = {
                "f1_mean": round(float(np.mean(f1s)), 4),
                "f1_sd": round(float(np.std(f1s)), 4),
                "ensemble_f1": round(M.f1_macro(s["label3"], pred), 4),
                "ensemble_ci95": M.bootstrap_ci(s["label3"], pred, seed),
                "ensemble_f1_per_class": M.per_class_f1(s["label3"], pred),
                "ensemble_confusion": M.confusion(s["label3"], pred),
            }
            ens_pred[(opt, name)] = pred
    comparisons = {}
    if "B" in by_opt:
        y = sets["coah_test"]["label3"]
        for opt in by_opt:
            if opt != "B":
                comparisons[f"{opt}_vs_B"] = M.paired_bootstrap(
                    y, ens_pred[(opt, "coah_test")], ens_pred[("B", "coah_test")], seed
                )
    return {"summary": summary, "comparisons_coah_test": comparisons}


def write_report(s: dict, sets, cfg: Config) -> None:
    n = {k: len(v) for k, v in sets.items()}
    L = [
        "# Fase 3 · Fine-tuning de mRoBERTa (BSC)",
        "",
        f"Generado por `uv run just train` · modelo `{MODEL_ID}@{MODEL_REVISION[:7]}` · "
        f"config {asdict(cfg)}. No editar a mano.",
        "",
        "F1 macro. **media ± sd** entre semillas; **ensamble** = media de las probabilidades de "
        "las semillas, con IC 95 % por bootstrap. Parada temprana con `coah_val`.",
        "",
        f"| Opción | Semillas | `coah_val` | **`coah_test`** (n={n['coah_test']}) "
        "| Ensamble `coah_test` "
        f"| IC 95 % | `coar_test` (n={n['coar_test']}) |",
        "|---|---|---|---|---|---|---|",
    ]
    for opt, r in s["summary"].items():
        v, t, o = r["coah_val"], r["coah_test"], r["coar_test"]
        L.append(
            f"| **{opt}** | {len(r['seeds'])} | {v['f1_mean']:.3f} ± {v['f1_sd']:.3f} "
            f"| **{t['f1_mean']:.3f} ± {t['f1_sd']:.3f}** | {t['ensemble_f1']:.3f} "
            f"| {t['ensemble_ci95'][0]:.3f}–{t['ensemble_ci95'][1]:.3f} "
            f"| {o['f1_mean']:.3f} ± {o['f1_sd']:.3f} |"
        )
    L += [
        "",
        "## F1 por clase (ensamble, `coah_test`)",
        "",
        "| Opción | " + " | ".join(LABELS) + " |",
        "|---|---|---|---|",
    ]
    for opt, r in s["summary"].items():
        pc = r["coah_test"]["ensemble_f1_per_class"]
        L.append(f"| {opt} | " + " | ".join(f"{pc[lab]:.3f}" for lab in LABELS) + " |")
    if s["comparisons_coah_test"]:
        L += ["", "## Frente a B (bootstrap pareado, ensambles, `coah_test`)", "",
              "| Comparación | ΔF1 macro | IC 95 % | P(mejor que B) |",
              "|---|---|---|---|"]  # fmt: skip
        for k, c in s["comparisons_coah_test"].items():
            L.append(
                f"| {k} | {c['diff']:+.3f} | {c['ci95'][0]:+.3f} a {c['ci95'][1]:+.3f} "
                f"| {c['p_a_better']:.2f} |"
            )
    L += ["", "## Matrices de confusión (ensamble, `coah_test`; filas: real)", ""]
    for opt, r in s["summary"].items():
        cm = r["coah_test"]["ensemble_confusion"]
        L += [
            f"**{opt}**",
            "",
            "| real \\ pred | " + " | ".join(LABELS) + " |",
            "|---|---|---|---|",
        ]
        L += [
            f"| {lab} | " + " | ".join(map(str, row)) + " |"
            for lab, row in zip(LABELS, cm, strict=True)
        ]
        L.append("")
    (ROOT / "reports" / "phase3_roberta.md").write_text(
        "\n".join(L) + "\n", encoding="utf-8", newline="\n"
    )


# --- CLI --------------------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--options", default=",".join(o.name for o in FINETUNE_OPTIONS))
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    ap.add_argument("--max-epochs", type=int, default=Config.max_epochs)
    ap.add_argument("--rerun", action="store_true", help="repite ejecuciones ya guardadas")
    ap.add_argument(
        "--save", action="store_true", help="guarda los pesos en models/ (~1,1 GB cada uno)"
    )
    args = ap.parse_args()

    cfg = Config(max_epochs=args.max_epochs)
    wanted = args.options.split(",")
    options = [o for o in FINETUNE_OPTIONS if o.name in wanted]
    seeds = [int(s) for s in args.seeds.split(",")]
    ensure_dirs()
    runs_dir = RUNS_DIR / cfg.id
    runs_dir.mkdir(parents=True, exist_ok=True)
    dev = device()
    log(
        f"GPU: {torch.cuda.get_device_name(0)} · torch {torch.__version__} "
        f"· HIP {torch.version.hip}"
    )
    log(f"Opciones {[o.name for o in options]} × semillas {seeds} · config {cfg.id} {asdict(cfg)}")

    df = load()
    sets = eval_sets(df)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    total, i = len(options) * len(seeds), 0
    for option in options:
        for seed in seeds:
            i += 1
            path = runs_dir / f"{option.name}_s{seed}.json"
            if path.exists() and not args.rerun:
                log(f"== [{i}/{total}] {option.name} semilla {seed}: ya hecho, se salta")
                continue
            log(f"== [{i}/{total}] Opción {option.name} ({option.description}) · semilla {seed}")
            out = run(option, seed, df, sets, tokenizer, cfg, dev, save=args.save)
            out["config"] = asdict(cfg)
            path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8", newline="\n")

    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(runs_dir.glob("*.json"))]
    s = summarize(runs, sets, seed=SEEDS[0])
    s["config"], s["config_id"] = asdict(cfg), cfg.id
    (RESULTS / "phase3_roberta_summary.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report(s, sets, cfg)
    log("OK: results/phase3_roberta_summary.json y reports/phase3_roberta.md")


if __name__ == "__main__":
    main()
