from caso_uso_llm import paths


def test_root_es_la_raiz_del_repo():
    assert (paths.ROOT / "pyproject.toml").is_file()
    assert (paths.ROOT / "CLAUDE.md").is_file()


def test_rutas_absolutas():
    assert paths.DATA_RAW.is_absolute()
