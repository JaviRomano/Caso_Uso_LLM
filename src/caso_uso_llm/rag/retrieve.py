"""Recuperación híbrida: BM25 (léxica) + bge-m3 (densa, vía Ollama), fusionadas con RRF.

Con decenas de documentos un índice en memoria basta: una base vectorial (LanceDB, Chroma)
añadiría dependencias sin aportar nada a esta escala.

- BM25: minúsculas, sin tildes, sin palabras vacías y «stemming» por prefijo de 5 letras
  (reembolso/reembolsen -> reemb). Tosco pero sin dependencias y suficiente para comparar.
- Densa: coseno entre embeddings normalizados. Caché en data/interim (fuera de git).
- RRF (Reciprocal Rank Fusion, k=60): suma 1/(k + posición) de cada ranking; no necesita
  calibrar las puntuaciones de BM25 y del coseno, que están en escalas distintas.
"""

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence

import numpy as np

from caso_uso_llm.paths import DATA_INTERIM
from caso_uso_llm.rag.kb import Doc

EMBED_MODEL = "bge-m3"
RRF_K = 60
STEM = 5
STOPWORDS = frozenset(
    [
        "a",
        "al",
        "algo",
        "como",
        "con",
        "de",
        "del",
        "el",
        "ella",
        "ellos",
        "en",
        "entre",
        "era",
        "es",
        "esta",
        "estaba",
        "este",
        "esto",
        "fue",
        "ha",
        "habia",
        "hay",
        "la",
        "las",
        "le",
        "les",
        "lo",
        "los",
        "me",
        "mi",
        "mis",
        "muy",
        "nos",
        "nuestra",
        "nuestro",
        "o",
        "para",
        "pero",
        "por",
        "que",
        "se",
        "si",
        "sin",
        "su",
        "sus",
        "te",
        "tu",
        "un",
        "una",
        "uno",
        "unos",
        "unas",
        "y",
        "ya",
        "yo",
    ]
)
METHODS = ("bm25", "densa", "hibrida")


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [w[:STEM] for w in re.findall(r"\w+", text) if w not in STOPWORDS and len(w) > 1]


class BM25:
    def __init__(self, docs: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.toks = [tokenize(d) for d in docs]
        self.lens = np.array([len(t) for t in self.toks], dtype=float)
        self.avg = self.lens.mean() if len(self.lens) else 0.0
        df: dict[str, int] = {}
        for t in self.toks:
            for w in set(t):
                df[w] = df.get(w, 0) + 1
        n = len(self.toks)
        self.idf = {w: np.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(len(self.toks))
        q = tokenize(query)
        for i, t in enumerate(self.toks):
            norm = self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg)
            for w in q:
                f = t.count(w)
                if f:
                    out[i] += self.idf[w] * f * (self.k1 + 1) / (f + norm)
        return out


class Embedder:
    """Embeddings de Ollama con caché en disco (clave: modelo + texto)."""

    def __init__(self, model: str = EMBED_MODEL, keep_alive: int | None = None):
        self.model = model
        self.keep_alive = keep_alive  # 0: Ollama descarga el modelo tras cada llamada
        self.path = DATA_INTERIM / f"embeddings_{model}.jsonl"
        self.cache: dict[str, list[float]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                self.cache[r["key"]] = r["vec"]

    def _key(self, text: str) -> str:
        return hashlib.sha1(f"{self.model}\n{text}".encode()).hexdigest()

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if self._key(t) not in self.cache]
        if missing:
            import ollama

            vecs = ollama.embed(
                model=self.model, input=missing, keep_alive=self.keep_alive
            ).embeddings
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as f:
                for t, v in zip(missing, vecs, strict=True):
                    self.cache[self._key(t)] = list(v)
                    f.write(json.dumps({"key": self._key(t), "vec": list(v)}) + "\n")
        m = np.array([self.cache[self._key(t)] for t in texts], dtype=float)
        return m / np.linalg.norm(m, axis=1, keepdims=True)


def rrf(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> list[int]:
    score: dict[int, float] = {}
    for ranking in rankings:
        for pos, i in enumerate(ranking):
            score[i] = score.get(i, 0.0) + 1 / (k + pos + 1)
    return sorted(score, key=lambda i: (-score[i], i))


class Retriever:
    def __init__(self, docs: Sequence[Doc], embedder: Embedder | None = None):
        self.docs = list(docs)
        self.bm25 = BM25([d.text for d in self.docs])
        self.embedder = embedder
        self.matrix = embedder([d.text for d in self.docs]) if embedder else None

    def rank(self, query: str, method: str = "hibrida") -> list[Doc]:
        lexical = list(np.argsort(-self.bm25.scores(query), kind="stable"))
        if method == "bm25":
            order = lexical
        else:
            if self.embedder is None:
                raise ValueError("la búsqueda densa necesita un Embedder")
            dense = list(np.argsort(-(self.matrix @ self.embedder([query])[0]), kind="stable"))
            order = dense if method == "densa" else rrf([lexical, dense])
        return [self.docs[i] for i in order]

    def search(self, query: str, k: int = 3, method: str = "hibrida") -> list[Doc]:
        return self.rank(query, method)[:k]
