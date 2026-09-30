"""Semillas globales para que cada experimento sea reproducible."""

import os
import random

import numpy as np

DEFAULT_SEED = 42


def set_seed(seed: int = DEFAULT_SEED, deterministic: bool = False) -> None:
    """Fija las semillas de random, numpy y torch (si está instalado).

    `deterministic=True` fuerza algoritmos deterministas en torch; es más lento y
    en ROCm algunas operaciones no tienen versión determinista.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)  # en ROCm "cuda" es la GPU AMD
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
