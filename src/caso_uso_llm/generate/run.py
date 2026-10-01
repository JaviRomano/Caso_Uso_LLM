"""Fase 4 · Generación sin fine-tuning: aspectos en JSON + respuesta, con comprobaciones.

Conjunto de desarrollo: 40 reseñas del train de COAH (8 por rating; los tests no se tocan)
y los casos adversariales sintéticos de evals/adversarial/generacion_v1.json.

Los prompts de respuesta están versionados (prompts.RESPONSE_PROMPTS). Cada versión guarda
sus resultados en results/phase4_dev_<versión>.json y el informe compara todas.

Uso: uv run just generar             # última versión del prompt
     uv run just generar --prompt v1
"""

import argparse
import hashlib
import json

import ollama
import pandas as pd
from pydantic import ValidationError

from caso_uso_llm.classify.datasets import load
from caso_uso_llm.generate import checks as C
from caso_uso_llm.generate.prompts import ANALYSIS_SYSTEM, RESPONSE_PROMPTS, response_user
from caso_uso_llm.generate.schema import Analisis
from caso_uso_llm.log import log
from caso_uso_llm.paths import RESULTS, ROOT
from caso_uso_llm.seed import DEFAULT_SEED

MODEL = "qwen3.6:27b-q4_K_M"
OPTIONS = {"temperature": 0, "seed": DEFAULT_SEED, "num_ctx": 8192}
CACHE = RESULTS / "phase4_cache.jsonl"
ADVERSARIAL = ROOT / "evals" / "adversarial" / "generacion_v1.json"
REPORT = ROOT / "reports" / "phase4_generacion.md"
PER_RATING = 8
ALERTS = ("promise", "liability", "tuteo", "dialect")
CRITICAL = ("adv-culpa-legal", "adv-premisa-spa", "adv-reembolso")  # se comparan entre versiones


def results_path(version: str):
    return RESULTS / f"phase4_dev_{version}.json"


def dev_set(seed: int = DEFAULT_SEED) -> pd.DataFrame:
    df = load()
    train = df[(df.source == "coah") & (df.split == "train")]
    real = train.groupby("rating", group_keys=False).sample(PER_RATING, random_state=seed)
    real = real.assign(kind="real", review=real["input"], must_not=[[]] * len(real))
    adv = json.loads(ADVERSARIAL.read_text(encoding="utf-8"))["cases"]
    adv = pd.DataFrame(adv).rename(columns={"tipo": "adv_type"})
    adv = adv.assign(kind="adversarial", rating=None, label3=None)
    cols = ["id", "kind", "rating", "label3", "review", "must_not"]
    return pd.concat([real[cols], adv[[*cols[:-1], "must_not", "adv_type"]]], ignore_index=True)


class Cache:
    def __init__(self, path):
        self.path = path
        self.data = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                self.data[r["key"]] = r["value"]

    def get_or_call(self, payload: dict, fn):
        key = hashlib.sha1(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        if key not in self.data:
            self.data[key] = fn()
            with self.path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(
                    json.dumps({"key": key, "value": self.data[key]}, ensure_ascii=False) + "\n"
                )
        return self.data[key]


def chat(system: str, user: str, schema: dict | None = None) -> str:
    r = ollama.chat(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format=schema,
        think=False,
        options=OPTIONS,
    )
    return r.message.content


def process(row: pd.Series, cache: Cache, response_system: str) -> dict:
    out = {"id": row["id"], "kind": row["kind"], "rating": row["rating"], "review": row["review"]}
    if row["kind"] == "adversarial":
        out["adv_type"] = row["adv_type"]
    schema = Analisis.model_json_schema()
    raw = cache.get_or_call(
        {"model": MODEL, "opts": OPTIONS, "sys": ANALYSIS_SYSTEM, "review": row["review"],
         "schema": schema},
        lambda: chat(ANALYSIS_SYSTEM, row["review"], schema),
    )  # fmt: skip
    try:
        analysis = Analisis.model_validate_json(raw).model_dump(mode="json")
        out["analysis_valid"] = True
    except ValidationError as e:
        out.update(analysis_valid=False, analysis_error=str(e)[:300])
        return out
    for a in analysis["aspectos"]:
        a["cita_literal"] = C.quote_in_review(a["cita"], row["review"])
    out["analysis"] = analysis
    user = response_user(row["review"], analysis)
    out["response"] = cache.get_or_call(
        {"model": MODEL, "opts": OPTIONS, "sys": response_system, "user": user},
        lambda: chat(response_system, user),
    ).strip()
    out["checks"] = C.run_checks(out["response"], analysis["aspectos"], list(row["must_not"]))
    return out


def main(seed: int = DEFAULT_SEED) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default=list(RESPONSE_PROMPTS)[-1], choices=list(RESPONSE_PROMPTS))
    version = ap.parse_args().prompt
    dev = dev_set(seed)
    n_real, n_adv = (dev.kind == "real").sum(), (dev.kind == "adversarial").sum()
    log(f"Modelo {MODEL} · prompt {version} · {n_real} reales + {n_adv} adversariales")
    cache = Cache(CACHE)
    results = []
    for i, row in dev.iterrows():
        r = process(row, cache, RESPONSE_PROMPTS[version])
        results.append(r)
        flags = [k for k in ALERTS if r.get("checks", {}).get(k)]
        status = (
            "análisis inválido"
            if not r["analysis_valid"]
            else f"{r['checks']['words']} palabras" + (f" · ALERTA {flags}" if flags else "")
        )
        log(f"   [{i + 1}/{len(dev)}] {r['id']}: {status}")
    results_path(version).write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report()
    log(f"OK: {results_path(version).relative_to(ROOT)} y {REPORT.relative_to(ROOT)}")


# --- Informe ------------------------------------------------------------------------------------

CHECKS = (
    ("Longitud 50–130 palabras", lambda r: r["checks"]["length_ok"]),
    ("Menciona un aspecto de la reseña", lambda r: r["checks"]["mentions_aspect"]),
    ("Firma «El equipo del hotel»", lambda r: r["checks"]["signature_ok"]),
    ("⚠ Promesa de compensación", lambda r: r["checks"]["promise"]),
    ("⚠ Admisión de culpa (expresa)", lambda r: r["checks"]["liability"]),
    ("⚠ Tuteo", lambda r: r["checks"]["tuteo"]),
    ("⚠ Rasgos dialectales", lambda r: r["checks"]["dialect"]),
    ("⚠ Patrón prohibido del caso", lambda r: bool(r["checks"]["case_forbidden"])),
)


def _rate(rows: list[dict], fn) -> str:
    return f"{sum(fn(r) for r in rows)}/{len(rows)}"


def write_report() -> None:
    runs = {v: json.loads(results_path(v).read_text(encoding="utf-8"))
            for v in RESPONSE_PROMPTS if results_path(v).exists()}  # fmt: skip
    latest = list(runs)[-1]
    res = runs[latest]
    valid = [r for r in res if r["analysis_valid"]]
    aspects = [a for r in valid for a in r["analysis"]["aspectos"]]
    L = [
        "# Fase 4 · Generación de respuestas sin fine-tuning",
        "",
        f"Generado por `uv run just generar` · `{MODEL}` vía Ollama, temperatura 0 · versiones "
        f"del prompt: {', '.join(runs)}. No editar a mano.",
        "",
        "Conjunto de desarrollo: 40 reseñas reales del *train* de COAH (8 por rating) y 8 casos "
        "adversariales **sintéticos** ([`evals/adversarial/generacion_v1.json`]"
        "(../evals/adversarial/generacion_v1.json)). Las comprobaciones son detectores "
        "deterministas: marcan señales, no juzgan la calidad (eso será el juez LLM de la Fase 6). "
        "**No detectan la admisión de culpa implícita** (repetir como hecho la causa que alega "
        "el cliente): esa se revisa leyendo los casos críticos de abajo.",
        "",
        "## Análisis (aspectos en JSON)",
        "",
        f"- JSON válido según el esquema: {_rate(res, lambda r: r['analysis_valid'])}.",
        f"- Citas que aparecen literalmente en la reseña: "
        f"{sum(a['cita_literal'] for a in aspects)}/{len(aspects)}.",
        "",
        "## Respuestas: comprobaciones por versión del prompt",
        "",
        "| Comprobación | " + " | ".join(f"{v} reales | {v} advers." for v in runs) + " |",
        "|---|" + "---|---|" * len(runs),
    ]
    for label, fn in CHECKS:
        cells = []
        for rows in runs.values():
            ok = [r for r in rows if r["analysis_valid"]]
            cells += [_rate([r for r in ok if r["kind"] == "real"], fn),
                      _rate([r for r in ok if r["kind"] == "adversarial"], fn)]  # fmt: skip
        L.append(f"| {label} | " + " | ".join(cells) + " |")

    L += ["", "## Casos críticos: respuesta de cada versión", ""]
    by_id = {v: {r["id"]: r for r in rows} for v, rows in runs.items()}
    for cid in CRITICAL:
        first = by_id[latest][cid]
        L += [f"### {cid} · {first['adv_type']}", "", f"> {first['review']}", ""]
        for v in runs:
            L += [f"**{v}:**", "", by_id[v][cid]["response"], ""]

    adv = [r for r in valid if r["kind"] == "adversarial" and r["id"] not in CRITICAL]
    L += [f"## Resto de casos adversariales ({latest})", ""]
    for r in adv:
        flags = [k for k in ALERTS if r["checks"][k]] + r["checks"]["case_forbidden"]
        L += [
            f"### {r['id']} · {r['adv_type']}",
            "",
            f"> {r['review']}",
            "",
            f"**Peticiones detectadas:** {', '.join(r['analysis']['peticiones']) or 'ninguna'} · "
            f"**Alertas:** {', '.join(flags) or 'ninguna'}",
            "",
            r["response"],
            "",
        ]
    real = [r for r in valid if r["kind"] == "real"]
    L += [f"## Ejemplos reales ({latest})", ""]
    for rating in (1, 3, 5):
        r = next(x for x in real if x["rating"] == rating)
        L += [f"### {r['id']} · {rating}★", "", f"> {r['review'][:600]}", "", r["response"], ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
