"""Rutas absolutas del proyecto, independientes del directorio de trabajo."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
DATA_RAW = DATA / "raw"  # inmutable
DATA_INTERIM = DATA / "interim"  # generado por scripts
DATA_PROCESSED = DATA / "processed"  # generado por scripts
MODELS = ROOT / "models"  # pesos locales, fuera de git
RESULTS = ROOT / "results"
EVALS = ROOT / "evals"


def ensure_dirs() -> None:
    """Crea los directorios generados (los que no se versionan)."""
    for d in (DATA_INTERIM, DATA_PROCESSED, MODELS, RESULTS):
        d.mkdir(parents=True, exist_ok=True)
