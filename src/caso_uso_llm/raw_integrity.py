"""Verificación de que data/raw/ no ha cambiado (regla: los datos crudos son inmutables)."""

import hashlib
import sys
from pathlib import Path

from caso_uso_llm.paths import DATA_RAW

CHECKSUMS = DATA_RAW / "SHA256SUMS"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_files() -> list[Path]:
    # .cache/ la crea huggingface_hub al descargar; no forma parte de los datos.
    return sorted(
        p
        for p in DATA_RAW.rglob("*")
        if p.is_file() and p != CHECKSUMS and ".cache" not in p.relative_to(DATA_RAW).parts
    )


def write_checksums() -> None:
    """Registra los ficheros crudos actuales.

    Solo se ejecuta al AÑADIR datos nuevos, nunca para "arreglar" un fallo de verificación.
    """
    lines = [f"{sha256(p)}  {p.relative_to(DATA_RAW).as_posix()}" for p in raw_files()]
    CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify() -> list[str]:
    """Devuelve la lista de problemas (vacía si todo está bien)."""
    expected = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        expected[name] = digest
    actual = {p.relative_to(DATA_RAW).as_posix(): p for p in raw_files()}
    problems = [f"falta: {n}" for n in expected.keys() - actual.keys()]
    problems += [f"no registrado: {n}" for n in actual.keys() - expected.keys()]
    problems += [
        f"modificado: {n}"
        for n in expected.keys() & actual.keys()
        if sha256(actual[n]) != expected[n]
    ]
    return sorted(problems)


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write_checksums()
    problems = verify()
    print("\n".join(problems) or "data/raw OK")
    sys.exit(1 if problems else 0)
