# Uso: `uv run just <receta>`. Sin argumentos lista las recetas.
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

# Instala el entorno (en WSL2 incluye torch ROCm)
setup:
    uv sync

# Tests
test:
    uv run pytest

# Linter y formato
lint:
    uv run ruff check src tests scripts
    uv run ruff format --check src tests scripts

fmt:
    uv run ruff format src tests scripts
    uv run ruff check --fix src tests scripts

# Comprueba que data/raw no ha cambiado
check-raw:
    uv run python -m caso_uso_llm.raw_integrity

# Comprueba la GPU AMD con ROCm (solo en WSL2)
gpu:
    uv run python scripts/check_gpu.py
