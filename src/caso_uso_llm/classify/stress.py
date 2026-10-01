"""Conjuntos de estrés para la evaluación realista (Fase 3b). Funciones puras, sin modelo.

Dos tipos:
- Perturbaciones de `coah_test` que NO deberían cambiar la etiqueta (invarianza): se mide
  cuántas predicciones cambian (*flip rate*) y el F1.
- Conjuntos reales de otra procedencia (SFU: ciao.es, reseñas llenas de negaciones).

Las perturbaciones son sintéticas y aproximadas: se etiquetan como tales y nunca se mezclan
con el test real.
"""

import random
import re

import pandas as pd

from caso_uso_llm.data.normalize import label3, strip_accents
from caso_uso_llm.paths import DATA_RAW

SFU_HOTELES = (
    DATA_RAW
    / "sinai/sfu_review_sp_neg/SFU_Review_SP_NEG_cue_scope_event_with_dependency_info_CoNLL"
    / "hoteles.txt"
)


def informal(text: str) -> str:
    """Escritura descuidada: minúsculas, sin tildes (la ñ se conserva) y sin ¡ ¿."""
    t = text.lower().replace("ñ", "\0")
    return strip_accents(t).replace("\0", "ñ").replace("¡", "").replace("¿", "")


def typos(text: str, seed: int, rate: float = 0.08) -> str:
    """Erratas en ~8 % de las palabras de 4+ letras: letras cambiadas, borradas o repetidas."""
    rng = random.Random(seed)

    def damage(m: re.Match) -> str:
        w = m.group(0)
        if len(w) < 4 or rng.random() > rate:
            return w
        i = rng.randrange(1, len(w) - 1)
        op = rng.choice(("swap", "drop", "dup"))
        if op == "swap":
            return w[:i] + w[i + 1] + w[i] + w[i + 2 :]
        if op == "drop":
            return w[:i] + w[i + 1 :]
        return w[:i] + w[i] + w[i:]

    return re.sub(r"\w+", damage, text)


# Rasgos del andaluz escrito informal (léxico y ortografía, no fonética completa).
_ANDALUZ = (
    (r"\bmuy\b", "mu"), (r"\bpara\b", "pa"), (r"\btodo\b", "to"), (r"\btoda\b", "toa"),
    (r"\bnada\b", "na"), (r"\bverdad\b", "verdá"), (r"\busted\b", "usté"),
    (r"(\w{2,})ado\b", r"\1ao"), (r"(\w{2,})ados\b", r"\1aos"), (r"\bse ha\b", "s'a"),
)  # fmt: skip


def andaluz(text: str) -> str:
    for pattern, repl in _ANDALUZ:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def perturbations(test: pd.DataFrame, seed: int) -> dict[str, pd.DataFrame]:
    """Variantes de `coah_test`. `input` es lo que ve el modelo (título + texto)."""
    base = test[["id", "title", "text", "label3", "rating"]].copy()

    def variant(name: str, inputs: pd.Series) -> pd.DataFrame:
        out = base.assign(input=inputs.to_numpy(), variant=name)
        return out[["id", "input", "label3", "rating", "variant"]]

    full = base["title"].str.strip() + ". " + base["text"]
    return {
        "original": variant("original", full),
        "sin_titulo": variant("sin_titulo", base["text"]),
        "solo_titulo": variant("solo_titulo", base["title"]),
        "informal": variant("informal", full.map(informal)),
        "erratas": variant(
            "erratas", pd.Series([typos(t, seed + i) for i, t in enumerate(full)], index=base.index)
        ),
        "andaluz": variant("andaluz", full.map(andaluz)),
    }


_NO_SPACE_BEFORE = re.compile(r"\s+([.,;:!?)\]»%])")
_NO_SPACE_AFTER = re.compile(r"([¿¡(\[«])\s+")


def load_sfu_hoteles(path=SFU_HOTELES) -> pd.DataFrame:
    """50 reseñas de hoteles de ciao.es. El id lleva polaridad y estrellas: hoteles_no_2_6 = 2★."""
    docs: dict[str, list[list[str]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) < 3:
            continue
        doc, sent = cols[0], cols[1]
        sents = docs.setdefault(doc, [])
        if not sents or sents[-1][0] != sent:
            sents.append([sent])
        sents[-1].append(cols[3])
    rows = []
    for doc, sents in docs.items():
        text = " ".join(" ".join(s[1:]) for s in sents)
        text = _NO_SPACE_AFTER.sub(r"\1", _NO_SPACE_BEFORE.sub(r"\1", text))
        rating = int(doc.split("_")[2])
        rows.append({"id": doc, "input": text, "rating": rating, "label3": label3(rating),
                     "variant": "sfu_hoteles"})  # fmt: skip
    return pd.DataFrame(rows)
