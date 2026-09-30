"""Lectura de los corpus crudos a DataFrames con el esquema común.

El texto se deja tal cual (`title_raw`, `text_raw`); la limpieza la hace `build.py`, que así
puede contar qué cambia cada regla. Los metadatos sí se parsean aquí (R9–R13).
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from caso_uso_llm.data import normalize as N
from caso_uso_llm.paths import DATA_RAW

COAH_XML = DATA_RAW / "sinai/coah/corpus_coah.xml"
COAR_TSV = DATA_RAW / "sinai/coar/CorpusCOAR_0.tsv"

_COAH_NS = {"c": "http://sinai.ujaen.es/coah"}
_COAR_FIELDS = (
    "provincia", "restaurantes", "restaurante url", "usuario", "titulo", "rate", "fecha",
    "comentario",
)  # fmt: skip


def load_coah(path: Path = COAH_XML) -> pd.DataFrame:
    """COAH: XML con <id>, <rank> (1–5), <abstract> (título) y <review>. Sin hotel ni fecha."""
    root = ET.parse(path).getroot()
    rows = []
    for r in root.findall("c:hotel_review", _COAH_NS):
        rows.append(
            {
                "id": f"coah-{r.findtext('c:id', namespaces=_COAH_NS)}",
                "source": "coah",
                "domain": "hotel",
                "establishment_id": None,
                "province": None,
                "date": None,
                "rating": int(r.findtext("c:rank", namespaces=_COAH_NS)),
                "title_raw": r.findtext("c:abstract", default="", namespaces=_COAH_NS),
                "text_raw": r.findtext("c:review", default="", namespaces=_COAH_NS),
                "reviewer_origin": "unknown",
            }
        )
    return pd.DataFrame(rows)


def _coar_records(path: Path) -> list[dict[str, str]]:
    """COAR es un TSV de pares `valor<TAB>clave`, 8 líneas por reseña, tras una cabecera."""
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value, _, key = line.rpartition("\t")
        if key != "name":  # cabecera "field<TAB>name"
            pairs.append((key, value))
    if len(pairs) % len(_COAR_FIELDS):
        raise ValueError(f"COAR: {len(pairs)} pares no es múltiplo de {len(_COAR_FIELDS)}")
    records = []
    for i in range(0, len(pairs), len(_COAR_FIELDS)):
        chunk = pairs[i : i + len(_COAR_FIELDS)]
        if tuple(k for k, _ in chunk) != _COAR_FIELDS:
            raise ValueError(f"COAR: registro {i // len(_COAR_FIELDS)} con campos inesperados")
        records.append(dict(chunk))
    return records


def load_coar(path: Path = COAR_TSV) -> pd.DataFrame:
    """COAR: reseñas de restaurantes. El usuario se reduce a su origen (R13) y se descarta."""
    rows = []
    for i, r in enumerate(_coar_records(path)):
        rows.append(
            {
                "id": f"coar-{i}",
                "source": "coar",
                "domain": "restaurante",
                "establishment_id": N.parse_establishment(r["restaurante url"]),
                "province": N.canonical_province(r["provincia"]),
                "date": N.parse_coar_date(r["fecha"]),
                "rating": N.parse_coar_rating(r["rate"]),
                "title_raw": r["titulo"],
                "text_raw": r["comentario"],
                "reviewer_origin": N.reviewer_origin(r["usuario"]),
            }
        )
    return pd.DataFrame(rows)
