"""Comprueba que Ollama ejecuta el modelo entero en la GPU antes de una ejecución larga.

Motivo (2026-10-22): la actualización automática de Ollama 0.40.5 -> 0.40.6 reinstaló
`lib\\ollama` sin el paquete de ROCm (`ollama-windows-amd64-rocm.zip`, que se instala aparte) y
Ollama pasó a la CPU sin avisar: cada respuesta del 27B tardaba ~130 s en vez de ~3,5 s. El
único rastro estaba en el log del servidor (`library=cpu`). Esta comprobación lo convierte en
un error visible.

Uso: `require_gpu(MODEL)` al empezar un script, o `uv run just gpu-ollama`.
"""

import sys

import ollama

FIX = (
    "Ollama no está usando la GPU. En Windows con AMD: descarga ollama-windows-amd64-rocm.zip de "
    "la MISMA versión de Ollama (https://github.com/ollama/ollama/releases), extráelo en "
    "%LOCALAPPDATA%\\Programs\\Ollama y reinicia Ollama. Comprueba en "
    "%LOCALAPPDATA%\\Ollama\\server.log que aparece «library=ROCm»."
)


def gpu_fraction(model: str) -> float:
    """Carga el modelo (si no lo está) y devuelve qué fracción ocupa en la VRAM."""
    ollama.generate(model=model, prompt="", keep_alive="5m")  # prompt vacío: solo carga
    for m in ollama.ps().models:
        if m.model == model or m.name == model:
            return m.size_vram / m.size if m.size else 0.0
    raise RuntimeError(f"{model} no aparece entre los modelos cargados en Ollama")


def require_gpu(model: str, minimum: float = 0.99) -> None:
    frac = gpu_fraction(model)
    if frac < minimum:
        raise RuntimeError(f"{model}: solo el {frac:.0%} está en la GPU. {FIX}")


def main() -> None:
    from caso_uso_llm.generate.run import MODEL

    model = sys.argv[1] if len(sys.argv) > 1 else MODEL
    frac = gpu_fraction(model)
    print(f"{model}: {frac:.0%} en la GPU")
    if frac < 0.99:
        sys.exit(FIX)


if __name__ == "__main__":
    main()
