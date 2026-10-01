import pytest

from caso_uso_llm.raw_integrity import verify


def test_data_raw_no_ha_cambiado():
    problems = verify()
    changed = [p for p in problems if not p.startswith("falta:")]
    assert changed == []  # un fichero crudo modificado o sin registrar es un error
    if problems:  # faltar no es modificar: datos de terceros aún sin descargar
        pytest.skip(f"{len(problems)} ficheros sin descargar: ejecuta `uv run just data-download`")
