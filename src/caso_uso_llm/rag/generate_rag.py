"""Fase 5 · Generación con contexto recuperado (prompts v5, v6) frente a la misma generación sin él (v4).

Los prompts RAG = reglas de v4 (spec.py) + un bloque de cómo usar el contexto, así que la
diferencia con v4 mide el efecto del RAG y no el de un prompt distinto. Contexto de cada reseña:
- ficha del hotel, seleccionada por id (las reseñas reales de COAH no tienen hotel: van sin ficha);
- 5 políticas (búsqueda híbrida) más las de `siempre=true`;
- 2 respuestas aprobadas parecidas (búsqueda densa), solo reseña y respuesta: las notas internas
  de la revisión nunca entran en el prompt.

Conjunto: las 40 reseñas reales y los 8 adversariales de la Fase 4, más 6 casos donde la ficha
contradice o matiza al cliente (evals/adversarial/rag_v1.json). Comprobaciones deterministas
de la Fase 4 más las que solo son posibles con la ficha. Marcan señales: los casos críticos
se leen en el informe.

Primero se recupera el contexto de todas las reseñas y después se genera: bge-m3 se descarga de
la GPU (keep_alive=0) y no compite por la VRAM con el generador de 27B.

Cada versión guarda results/phase5_generacion_<versión>.json; el informe compara todas las que
existan. Ojo: cada fichero refleja la base de conocimiento (kb/) del commit en que se generó.

Uso: uv run just rag-generar              # última versión
     uv run just rag-generar --prompt v5
"""

import argparse
import json
import re

import pandas as pd

from caso_uso_llm.generate import checks as C
from caso_uso_llm.generate.prompts import RAG_PROMPTS, RESPONSE_PROMPTS, response_user
from caso_uso_llm.generate.run import CACHE, MODEL, Cache, analyze, dev_set, respond
from caso_uso_llm.log import log
from caso_uso_llm.ollama_gpu import require_gpu
from caso_uso_llm.paths import EVALS, RESULTS, ROOT
from caso_uso_llm.rag import kb
from caso_uso_llm.rag.retrieve import Embedder, Retriever
from caso_uso_llm.seed import DEFAULT_SEED

RAG_CASES = EVALS / "adversarial" / "rag_v1.json"
REPORT = ROOT / "reports" / "phase5_generacion.md"
BASE = "v4"
K_POLICIES, K_EXAMPLES = 5, 2

# Términos con los que una respuesta menciona cada servicio de la ficha.
SERVICES = {
    "spa": r"\bspa\b|circuito",
    "piscina": r"piscina",
    "parking": r"parking|aparcamiento",
    "desayuno": r"desayuno",
    "mascotas": r"mascota|perro",
    "aire_acondicionado": r"aire acondicionado",
}
ABSENT = re.compile(r"^No (hay|se sirve|se admiten)", re.IGNORECASE)
PRICE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:€|euros?)", re.IGNORECASE)
FIGURE = re.compile(PRICE.pattern + r"|\b\d{1,2}:\d{2}\b", re.IGNORECASE)
CONTRADICTS = re.compile(
    r"\b(s[ií] (hab[ií]a|hay|exist[ií]a|contamos)|no es cierto|se equivoca|est[aá] usted equivocad"
    r"|como (se )?indica(mos)? en|deber[ií]a haber|le recordamos que)\b",
    re.IGNORECASE,
)
# Nombra la fuente interna del contexto en vez de hablar como el hotel.
SOURCE = re.compile(
    r"\b(nuestra ficha|la ficha|según nuestra información|nuestras políticas|respuestas? aprobadas?)\b",
    re.IGNORECASE,
)


def results_path(version: str):
    return RESULTS / f"phase5_generacion_{version}.json"


def cases(seed: int) -> pd.DataFrame:
    dev = dev_set(seed).assign(hotel=None)
    rag = json.loads(RAG_CASES.read_text(encoding="utf-8"))
    dev.loc[dev.kind == "adversarial", "hotel"] = dev.loc[dev.kind == "adversarial", "id"].map(
        rag["hoteles_generacion_v1"]
    )
    new = pd.DataFrame(rag["cases"]).rename(columns={"tipo": "adv_type"})
    new = new.assign(kind="rag", rating=None, label3=None)
    return pd.concat([dev, new[dev.columns]], ignore_index=True)


def context_user(review: str, analysis: dict, hotel: str | None, policies, examples) -> str:
    ficha = kb.ficha_texto(hotel) if hotel else "No disponible."
    pols = [*kb.politicas_siempre(), *(d.payload for d in policies)]
    pol_text = "\n".join(f"- {p['titulo']}: {p['texto']}" for p in pols)
    ex_text = "\n\n".join(
        f"Reseña: «{d.payload['resena']}»\nRespuesta aprobada:\n{d.payload['respuesta']}"
        for d in examples
    )
    return (
        f"Ficha del hotel:\n{ficha}\n\nPolíticas aplicables:\n{pol_text}\n\n"
        f"Respuestas aprobadas a reseñas parecidas (solo como ejemplo):\n{ex_text}\n\n---\n\n"
        + response_user(review, analysis)
    )


def ficha_checks(response: str, review: str, hotel: str | None) -> dict:
    out = {
        "importe": PRICE.findall(response),
        "nombra_fuente": bool(SOURCE.search(response)),
        "servicio_inexistente": [],
        "cifra_inventada": [],
        "contradice": False,
    }
    if not hotel:
        return out
    ficha, servicios = kb.ficha_texto(hotel), kb.fichas()[hotel]["servicios"]
    out["servicio_inexistente"] = [
        s
        for s, pat in SERVICES.items()
        if ABSENT.match(servicios.get(s, ""))
        and re.search(pat, response, re.IGNORECASE)
        and not re.search(pat, review, re.IGNORECASE)
    ]
    norm = lambda t: re.sub(r"\s+", "", t.lower())  # noqa: E731
    out["cifra_inventada"] = [
        f for f in FIGURE.findall(response) if norm(f) not in norm(ficha + review)
    ]
    out["contradice"] = bool(CONTRADICTS.search(response))
    return out


def retrieve_all(df: pd.DataFrame) -> dict[str, tuple[list, list]]:
    """Contexto de todas las reseñas antes de generar, para no alternar modelos en la GPU."""
    embedder = Embedder(keep_alive=0)
    policies, examples = Retriever(kb.politicas(), embedder), Retriever(kb.respuestas(), embedder)
    return {
        row["id"]: (
            policies.search(row["review"], K_POLICIES, "hibrida"),
            examples.search(row["review"], K_EXAMPLES, "densa"),
        )
        for _, row in df.iterrows()
    }


def main(seed: int = DEFAULT_SEED) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default=RAG_PROMPTS[-1], choices=RAG_PROMPTS)
    version = ap.parse_args().prompt
    df = cases(seed)
    log(f"Modelo {MODEL} · {BASE} sin contexto frente a {version} con contexto · {len(df)} reseñas")
    context = retrieve_all(df)
    log(f"Contexto recuperado para {len(context)} reseñas; empieza la generación")
    require_gpu(MODEL)  # después de recuperar: bge-m3 ya se ha descargado de la GPU
    cache = Cache(CACHE)
    out = []
    for i, row in df.iterrows():
        hotel = row["hotel"] if isinstance(row["hotel"], str) else None  # reales: sin hotel
        analysis, error = analyze(row["review"], cache)
        r = {"id": row["id"], "kind": row["kind"], "hotel": hotel, "review": row["review"]}
        r["adv_type"] = row.get("adv_type") if row["kind"] != "real" else None
        if analysis is None:
            out.append({**r, "analysis_valid": False, "analysis_error": error})
            log(f"   [{i + 1}/{len(df)}] {row['id']}: análisis inválido")
            continue
        pols, exs = context[row["id"]]
        r.update(analysis_valid=True, politicas=[d.id for d in pols], ejemplos=[d.id for d in exs])
        for v, user in (
            (BASE, response_user(row["review"], analysis)),
            (version, context_user(row["review"], analysis, hotel, pols, exs)),
        ):
            text = respond(RESPONSE_PROMPTS[v], user, cache)
            checks = C.run_checks(text, analysis["aspectos"], list(row["must_not"]))
            checks.update(ficha_checks(text, row["review"], hotel))
            r[v] = {"response": text, "checks": checks}
        out.append(r)
        words = r[version]["checks"]["words"]
        log(f"   [{i + 1}/{len(df)}] {row['id']} ({row['kind']}): {words} palabras")
    results_path(version).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report()
    log(f"OK: {results_path(version).relative_to(ROOT)} y {REPORT.relative_to(ROOT)}")


CHECKS = (
    ("Longitud 50–130 palabras", lambda c: c["length_ok"], False),
    ("Menciona un aspecto de la reseña", lambda c: c["mentions_aspect"], False),
    ("⚠ Promesa de compensación", lambda c: c["promise"], True),
    ("⚠ Admisión de culpa (expresa)", lambda c: c["liability"], True),
    ("⚠ Tuteo o dialecto", lambda c: c["tuteo"] or c["dialect"], True),
    ("⚠ Plazo o acción dada por hecha", lambda c: c["plazo"], True),
    ("⚠ Patrón prohibido del caso", lambda c: bool(c["case_forbidden"]), True),
    ("⚠ Servicio que la ficha dice que no existe", lambda c: bool(c["servicio_inexistente"]), True),
    ("⚠ Precio u horario que no está en la ficha", lambda c: bool(c["cifra_inventada"]), True),
    ("⚠ Contradice o corrige al cliente", lambda c: c["contradice"], True),
    ("⚠ Da un importe (pol-precio)", lambda c: bool(c.get("importe")), True),
    ("⚠ Nombra la ficha o las políticas", lambda c: c.get("nombra_fuente", False), True),
)
GROUPS = (("real", "reales"), ("adversarial", "advers."), ("rag", "ficha vs. cliente"))


def write_report() -> None:
    runs = {v: json.loads(results_path(v).read_text(encoding="utf-8"))
            for v in RAG_PROMPTS if results_path(v).exists()}  # fmt: skip
    for res in runs.values():  # las comprobaciones nuevas se recalculan sobre resultados antiguos
        for r in res:
            for v in (BASE, *runs):
                if r.get("analysis_valid") and v in r:
                    r[v]["checks"].update(ficha_checks(r[v]["response"], r["review"], r["hotel"]))
    first = next(iter(runs.values()))
    versions = (BASE, *runs)
    pick = lambda v: runs.get(v, first)  # noqa: E731  (v4 se toma de cualquier ejecución)
    L = [
        "# Fase 5 · Generación con RAG",
        "",
        f"Generado por `uv run just rag-generar` · `{MODEL}` vía Ollama, temperatura 0 · prompt "
        f"{BASE} (sin contexto) frente a {', '.join(runs)} (mismas reglas + ficha, {K_POLICIES} "
        f"políticas y {K_EXAMPLES} respuestas aprobadas recuperadas). No editar a mano.",
        "",
        "Casos **sintéticos** salvo las reseñas reales de COAH, que no tienen hotel y van sin ficha. "
        "Las comprobaciones son deterministas: marcan señales, no juzgan. Los casos adversariales "
        "se leen abajo. Cada versión se generó con la base de conocimiento de su commit (v6 resolvió "
        "en `pol-servicios` que no se dan importes).",
        "",
        "| Comprobación | " + " | ".join(f"{g} {v}" for _, g in GROUPS for v in versions) + " |",
        "|---|" + "---|" * (len(GROUPS) * len(versions)),
    ]
    for label, fn, _ in CHECKS:
        cells = []
        for kind, _ in GROUPS:
            for v in versions:
                rows = [r for r in pick(v) if r["analysis_valid"] and r["kind"] == kind]
                cells.append(f"{sum(bool(fn(r[v]['checks'])) for r in rows)}/{len(rows)}")
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    L += ["", "## Casos adversariales: respuesta de cada versión", ""]
    by_id = {v: {r["id"]: r for r in pick(v)} for v in versions}
    for r in [r for r in first if r["analysis_valid"] and r["kind"] != "real"]:
        L += [f"### {r['id']} · {r['adv_type']} · hotel {r['hotel']}", "", f"> {r['review']}", ""]
        for v in versions:
            rv = by_id[v][r["id"]]
            flags = [label for label, fn, alert in CHECKS if alert and fn(rv[v]["checks"])]
            ctx = (
                ""
                if v == BASE
                else f" (políticas: {', '.join(rv['politicas'])} · ejemplos: {', '.join(rv['ejemplos'])})"
            )
            L += [
                f"**{v}**{ctx}" + (f" — ⚠ {'; '.join(flags)}" if flags else "") + ":",
                "",
                rv[v]["response"],
                "",
            ]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
