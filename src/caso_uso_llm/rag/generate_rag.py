"""Fase 5 · Generación con contexto recuperado (prompt v5) frente a la misma generación sin él (v4).

v5 = reglas de v4 (spec.py) + cómo usar el contexto, así que la diferencia entre ambos mide el
efecto del RAG y no el de un prompt distinto. Contexto de cada reseña:
- ficha del hotel, seleccionada por id (las reseñas reales de COAH no tienen hotel: van sin ficha);
- 5 políticas (búsqueda híbrida) más las de `siempre=true`;
- 2 respuestas aprobadas parecidas (búsqueda densa), solo reseña y respuesta: las notas internas
  de la revisión nunca entran en el prompt.

Conjunto: las 40 reseñas reales y los 8 adversariales de la Fase 4, más 6 casos donde la ficha
contradice o matiza al cliente (evals/adversarial/rag_v1.json). Comprobaciones deterministas
de la Fase 4 más tres que solo son posibles con la ficha. Marcan señales: los casos críticos
se leen en el informe.

Uso: uv run just rag-generar
"""

import json
import re

import pandas as pd

from caso_uso_llm.generate import checks as C
from caso_uso_llm.generate.prompts import RESPONSE_PROMPTS, response_user
from caso_uso_llm.generate.run import CACHE, MODEL, Cache, analyze, dev_set, respond
from caso_uso_llm.log import log
from caso_uso_llm.paths import EVALS, RESULTS, ROOT
from caso_uso_llm.rag import kb
from caso_uso_llm.rag.retrieve import Embedder, Retriever
from caso_uso_llm.seed import DEFAULT_SEED

RAG_CASES = EVALS / "adversarial" / "rag_v1.json"
OUT = RESULTS / "phase5_generacion.json"
REPORT = ROOT / "reports" / "phase5_generacion.md"
BASE, RAG = "v4", "v5"
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
FIGURE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:€|euros?)|\b\d{1,2}:\d{2}\b", re.IGNORECASE)
CONTRADICTS = re.compile(
    r"\b(s[ií] (hab[ií]a|hay|exist[ií]a|contamos)|no es cierto|se equivoca|est[aá] usted equivocad"
    r"|como (se )?indica(mos)? en|deber[ií]a haber|le recordamos que)\b",
    re.IGNORECASE,
)


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
    if not hotel:
        return {"servicio_inexistente": [], "cifra_inventada": [], "contradice": False}
    ficha, servicios = kb.ficha_texto(hotel), kb.fichas()[hotel]["servicios"]
    absent = [
        s
        for s, pat in SERVICES.items()
        if ABSENT.match(servicios.get(s, ""))
        and re.search(pat, response, re.IGNORECASE)
        and not re.search(pat, review, re.IGNORECASE)
    ]
    norm = lambda t: re.sub(r"\s+", "", t.lower())  # noqa: E731
    figures = [f for f in FIGURE.findall(response) if norm(f) not in norm(ficha + review)]
    return {
        "servicio_inexistente": absent,
        "cifra_inventada": figures,
        "contradice": bool(CONTRADICTS.search(response)),
    }


def main(seed: int = DEFAULT_SEED) -> None:
    df = cases(seed)
    log(f"Modelo {MODEL} · {BASE} sin contexto frente a {RAG} con contexto · {len(df)} reseñas")
    cache, embedder = Cache(CACHE), Embedder()
    policies, examples = Retriever(kb.politicas(), embedder), Retriever(kb.respuestas(), embedder)
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
        pols = policies.search(row["review"], K_POLICIES, "hibrida")
        exs = examples.search(row["review"], K_EXAMPLES, "densa")
        r.update(analysis_valid=True, politicas=[d.id for d in pols], ejemplos=[d.id for d in exs])
        for version, user in (
            (BASE, response_user(row["review"], analysis)),
            (RAG, context_user(row["review"], analysis, hotel, pols, exs)),
        ):
            text = respond(RESPONSE_PROMPTS[version], user, cache)
            checks = C.run_checks(text, analysis["aspectos"], list(row["must_not"]))
            checks.update(ficha_checks(text, row["review"], hotel))
            r[version] = {"response": text, "checks": checks}
        out.append(r)
        log(
            f"   [{i + 1}/{len(df)}] {row['id']} ({row['kind']}): {r[RAG]['checks']['words']} palabras"
        )
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    write_report(out)
    log(f"OK: {OUT.relative_to(ROOT)} y {REPORT.relative_to(ROOT)}")


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
)
GROUPS = (
    ("real", "reales (sin ficha)"),
    ("adversarial", "adversariales"),
    ("rag", "ficha vs. cliente"),
)


def write_report(out: list[dict]) -> None:
    ok = [r for r in out if r["analysis_valid"]]
    L = [
        "# Fase 5 · Generación con RAG",
        "",
        f"Generado por `uv run just rag-generar` · `{MODEL}` vía Ollama, temperatura 0 · "
        f"prompt {BASE} (sin contexto) frente a {RAG} (mismas reglas + ficha, {K_POLICIES} políticas "
        f"y {K_EXAMPLES} respuestas aprobadas recuperadas). No editar a mano.",
        "",
        "Casos **sintéticos** salvo las reseñas reales de COAH, que no tienen hotel y van sin ficha. "
        "Las comprobaciones son deterministas: marcan señales, no juzgan. Los casos adversariales "
        "se leen abajo.",
        "",
        f"Análisis JSON válido: {len(ok)}/{len(out)}.",
        "",
        "| Comprobación | " + " | ".join(f"{g} {v}" for _, g in GROUPS for v in (BASE, RAG)) + " |",
        "|---|" + "---|" * (2 * len(GROUPS)),
    ]
    for label, fn, _ in CHECKS:
        cells = []
        for kind, _ in GROUPS:
            rows = [r for r in ok if r["kind"] == kind]
            cells += [
                f"{sum(bool(fn(r[v]['checks'])) for r in rows)}/{len(rows)}" for v in (BASE, RAG)
            ]
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    L += ["", "## Casos adversariales: respuesta sin y con contexto", ""]
    for r in [r for r in ok if r["kind"] != "real"]:
        L += [
            f"### {r['id']} · {r['adv_type']} · hotel {r['hotel']}",
            "",
            f"> {r['review']}",
            "",
            f"Recuperado: {', '.join(r['politicas'])} · ejemplos: {', '.join(r['ejemplos'])}",
            "",
        ]
        for v in (BASE, RAG):
            flags = [label for label, fn, alert in CHECKS if alert and fn(r[v]["checks"])]
            L += [
                f"**{v}**" + (f" — ⚠ {'; '.join(flags)}" if flags else "") + ":",
                "",
                r[v]["response"],
                "",
            ]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
