"""Descarga de los datasets de terceros a data/raw/ (no se versionan en git).

Cada fuente fija el commit (`revision`) del repo de Hugging Face, así que la descarga es
reproducible. Los datasets de SINAI son *gated*: hay que aceptar sus términos en la web de
HF con la misma cuenta del token (`hf auth login` una vez, o `HF_TOKEN` en el entorno).

Uso: uv run just data-download
"""

from dataclasses import dataclass

from huggingface_hub import snapshot_download

from caso_uso_llm.paths import DATA_RAW


@dataclass(frozen=True)
class Source:
    repo_id: str
    revision: str
    dest: str  # subcarpeta de data/raw
    allow_patterns: tuple[str, ...]
    license: str


SOURCES = (
    Source(
        repo_id="SINAI/COAH",
        revision="058f8477b9c7af7ac13f79e9d0a570b38a062204",
        dest="sinai/coah",
        allow_patterns=("corpus_coah.xml", "LICENSE", "README.md"),
        license="CC BY-NC-SA 4.0",
    ),
    Source(
        repo_id="SINAI/COAR",
        revision="9d7d707408e8904d757609037058810e84506d3e",
        dest="sinai/coar",
        allow_patterns=("CorpusCOAR_0.tsv", "LICENSE", "README.md"),
        license="CC BY-NC-SA 4.0",
    ),
    Source(
        repo_id="SINAI/SFU-Review-SP-Neg",
        revision="971f6d8de59ae8d078151da6e928c145027ece94",
        dest="sinai/sfu_review_sp_neg",
        allow_patterns=("*/hoteles.txt", "README.md"),
        license="CC BY-NC-SA 4.0",
    ),
)


def download(source: Source) -> None:
    snapshot_download(
        repo_id=source.repo_id,
        repo_type="dataset",
        revision=source.revision,
        allow_patterns=list(source.allow_patterns),
        local_dir=DATA_RAW / source.dest,
    )


# AHR completo (Kaggle, versión 3, CC BY-NC 4.0): solo se usa como test fuera de distribución.
# Es público: se descarga sin cuenta. Contiene COAH entero (las filas sin hotel).
AHR_URL = (
    "https://www.kaggle.com/api/v1/datasets/download/"
    "chizhikchi/andalusian-hotels-reviews-unbalanced?datasetVersionNumber=3"
)
AHR_FILE = DATA_RAW / "ahr" / "Big_AHR.csv"


def download_ahr() -> None:
    import io
    import urllib.request
    import zipfile

    with urllib.request.urlopen(AHR_URL, timeout=120) as r:
        data = r.read()
    AHR_FILE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        AHR_FILE.write_bytes(z.read("Big_AHR.csv"))


if __name__ == "__main__":
    for s in SOURCES:
        print(f"{s.repo_id}@{s.revision[:7]} -> data/raw/{s.dest} ({s.license})")
        download(s)
    print(f"Kaggle AHR v3 -> {AHR_FILE.relative_to(DATA_RAW.parent.parent)} (CC BY-NC 4.0)")
    download_ahr()
