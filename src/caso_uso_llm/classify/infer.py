"""Clasificador de producción en CPU: ensamble de las 3 semillas de mRoBERTa (opción A).

Es el modelo elegido al cerrar la Fase 3. Se ejecuta en CPU para que el pipeline viva en un solo
proceso en Windows (torch CPU, grupo `serve`); mRoBERTa tiene 283M parámetros y en CPU basta.
La entrada se prepara como en el entrenamiento: título + ". " + texto, con la normalización
R1–R6 y el enmascarado de datos personales (R14).

Los pesos (3 × 1,1 GB) no van en git: models/mroberta/<config>/A_s<semilla>, copiados del clon
de WSL2 donde se entrenaron (`uv run just train --options A --save`).
"""

from dataclasses import dataclass

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from caso_uso_llm.classify.datasets import LABELS
from caso_uso_llm.classify.finetune import SEEDS, Config, model_dir
from caso_uso_llm.data.normalize import mask_pii, normalize_text

OPTION = "A"


def prepare(text: str, title: str = "") -> str:
    """Misma entrada que en el entrenamiento (datasets.load): «título. texto»."""
    text, _ = mask_pii(normalize_text(text))
    title = mask_pii(normalize_text(title))[0].strip()
    return f"{title}. {text}" if title else text


@dataclass
class Prediction:
    label: str
    confidence: float  # probabilidad media de la clase elegida
    probs: dict[str, float]


class SentimentEnsemble:
    def __init__(self, cfg: Config | None = None):
        cfg = cfg or Config()
        self.max_len = cfg.max_len
        self.models = []
        for seed in SEEDS:
            path = model_dir(cfg, OPTION, seed)
            if not (path / "model.safetensors").exists():
                raise SystemExit(f"Faltan los pesos de mRoBERTa en {path} (ver docstring).")
            tok = AutoTokenizer.from_pretrained(path)
            model = AutoModelForSequenceClassification.from_pretrained(path).eval()
            self.models.append((tok, model))

    @torch.no_grad()
    def predict(self, texts: list[str], batch_size: int = 16) -> list[Prediction]:
        total = np.zeros((len(texts), len(LABELS)))
        for tok, model in self.models:
            for i in range(0, len(texts), batch_size):
                enc = tok(texts[i : i + batch_size], truncation=True, max_length=self.max_len,
                          padding=True, return_tensors="pt")  # fmt: skip
                logits = model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"])
                total[i : i + batch_size] += torch.softmax(logits.logits, dim=-1).numpy()
        probs = total / len(self.models)
        return [
            Prediction(
                LABELS[p.argmax()], float(p.max()), dict(zip(LABELS, map(float, p), strict=True))
            )
            for p in probs
        ]
