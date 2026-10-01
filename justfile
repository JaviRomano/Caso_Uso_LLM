# Uso: `uv run just <receta>` (uv activa el entorno, así que aquí no se llama a uv).
# Instalar/actualizar el entorno: `uv sync` (en WSL2 incluye torch ROCm).
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

# Tests
test:
    python -m pytest

# Linter y formato
lint:
    ruff check src tests scripts
    ruff format --check src tests scripts

fmt:
    ruff format src tests scripts
    ruff check --fix src tests scripts

# Comprueba que data/raw no ha cambiado
check-raw:
    python -m caso_uso_llm.raw_integrity

# Comprueba la GPU AMD con ROCm (solo en WSL2)
gpu:
    python scripts/check_gpu.py

# Descarga los datasets de terceros (requiere `hf auth login` y aceptar sus términos en HF)
data-download:
    python -m caso_uso_llm.data.download

# Pipeline de datos: crudo -> data/processed + reports/data_report.md
data:
    python -m caso_uso_llm.data.build

# Fase 3: baseline TF-IDF + LR (opciones A, A_sin_trad, B) -> results/ + reports/
baseline:
    python -m caso_uso_llm.classify.baseline

# Fase 3: fine-tuning de RoBERTa-BNE (solo WSL2). Ej.: just train --options B,C --seeds 42
train *ARGS:
    python -m caso_uso_llm.classify.finetune {{ARGS}}

# Fase 3b: evaluación realista (estrés, SFU, cobertura vs error) del ensamble A (solo WSL2)
realista:
    python -m caso_uso_llm.classify.realistic
