"""Progreso en consola y en fichero: hora, tiempo transcurrido desde el inicio y mensaje.

Cada ejecución escribe también en `logs/<script>.log` (se sobrescribe), para poder seguirla
desde otra terminal aunque la haya lanzado otra persona:
    PowerShell:  Get-Content logs\\baseline.log -Wait
    WSL / bash:  tail -f logs/baseline.log

Uso: `from caso_uso_llm.log import log` y `log("Entrenando opción A")`.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from caso_uso_llm.paths import ROOT

_T0 = time.perf_counter()
_FILE = None


def _file():
    global _FILE
    if _FILE is None:
        name = Path(sys.argv[0]).stem or "interactive"
        (ROOT / "logs").mkdir(exist_ok=True)
        _FILE = open(ROOT / "logs" / f"{name}.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    return _FILE


def log(msg: str) -> None:
    elapsed = time.perf_counter() - _T0
    line = f"[{datetime.now():%H:%M:%S} +{elapsed:6.1f}s] {msg}"
    print(line, file=sys.stderr, flush=True)
    print(line, file=_file(), flush=True)
