"""Fase 4 · Generación sin fine-tuning: aspectos en JSON + respuesta, con comprobaciones.

Conjunto de desarrollo: 40 reseñas del train de COAH (8 por rating; los tests no se tocan)
y los casos adversariales sintéticos de evals/adversarial/generacion_v1.json.

Uso: uv run just generar
"""

import hashlib
import json

import ollama
import pandas as pd
from pydantic import ValidationError

from caso_uso_llm.classify.datasets import load
from caso_uso_llm.generate import checks as C
from caso_uso_llm.generate.prompts import ANALYSIS_SYSTEM, RESPONSE_SYSTEM, response_user
from caso_uso_llm.generate.schema import Analisis
from caso_uso_llm.log import log
from caso_uso_llm.paths import RESULTS, ROOT
from caso_uso_llm.seed import DEFAULT_SEED

MODEL = "qwen3.6:27b-q4_K_M"
OPTIONS = {"temperature": 0, "seed": DEFAULT_SEED, "num_ctx": 8192}
CACHE = RESULTS / "phase4_cache.jsonl"
ADVERSARIAL = ROOT / "evals" / "adversarial" / "generacion_v1.json"
PER_RATING = 8


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


def process(row: pd.Series, cache: Cache) -> dict:
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
        {"model": MODEL, "opts": OPTIONS, "sys": RESPONSE_SYSTEM, "user": user},
        lambda: chat(RESPONSE_SYSTEM, user),
    ).strip()
    out["checks"] = C.run_checks(out["response"], analysis["aspectos"], list(row["must_not"]))
    return out


def main(seed: int = DEFAULT_SEED) -> None:
    dev = dev_set(seed)
    log(f"Modelo {MODEL} · {len(dev)} reseñas ({(dev.kind == 'real').sum()} reales, "
        f"{(dev.kind == 'adversarial').sum()} adversariales sintéticas)")  # fmt: skip
    cache = Cache(CACHE)
    results = []
    for i, row in dev.iterrows():
        results.append(process(row, cache))
        r = results[-1]
        flags = [
            k for k in ("promise", "liability", "tuteo", "dialect") if r.get("checks", {}).get(k)
        ]
        status = (
            "análisis inválido"
            if not r["analysis_valid"]
            else f"{r['checks']['words']} palabras" + (f" · ALERTA {flags}" if flags else "")
        )
        log(f"   [{i + 1}/{len(dev)}] {r['id']}: {status}")
    (RESULTS / "phase4_dev.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    write_report(results)
    log("OK: results/phase4_dev.json y reports/phase4_generacion.md")


def _rate(rows: list[dict], fn) -> str:
    vals = [fn(r) for r in rows]
    return f"{sum(vals)}/{len(vals)}"


def write_report(results: list[dict]) -> None:
    valid = [r for r in results if r["analysis_valid"]]
    aspects = [a for r in valid for a in r["analysis"]["aspectos"]]
    L = [
        "# Fase 4 · Generación de respuestas sin fine-tuning",
        "",
        f"Generado por `uv run just generar` · `{MODEL}` vía Ollama, temperatura 0. "
        "No editar a mano.",
        "",
        "Conjunto de desarrollo: 40 reseñas reales del *train* de COAH (8 por rating) y 8 casos "
        "adversariales **sintéticos** ([`evals/adversarial/generacion_v1.json`]"
        "(../evals/adversarial/generacion_v1.json)). Las comprobaciones son detectores "
        "deterministas: marcan señales, no juzgan la calidad (eso será el juez LLM de la Fase 6).",
        "",
        "## Análisis (aspectos en JSON)",
        "",
        f"- JSON válido según el esquema: {_rate(results, lambda r: r['analysis_valid'])}.",
        f"- Citas que aparecen literalmente en la reseña: {sum(a['cita_literal'] for a in aspects)}"
        f"/{len(aspects)} (las demás son paráfrasis o invenciones del modelo).",
        "",
        "## Respuestas: comprobaciones",
        "",
        "| Comprobación | Reales | Adversariales |",
        "|---|---|---|",
    ]
    real = [r for r in valid if r["kind"] == "real"]
    adv = [r for r in valid if r["kind"] == "adversarial"]
    for label, fn in (
        ("Longitud 50–130 palabras", lambda r: r["checks"]["length_ok"]),
        ("Menciona un aspecto de la reseña", lambda r: r["checks"]["mentions_aspect"]),
        ("Firma «El equipo del hotel»", lambda r: r["checks"]["signature_ok"]),
        ("⚠ Posible promesa de compensación", lambda r: r["checks"]["promise"]),
        ("⚠ Posible admisión de culpa", lambda r: r["checks"]["liability"]),
        ("⚠ Tuteo", lambda r: r["checks"]["tuteo"]),
        ("⚠ Rasgos dialectales", lambda r: r["checks"]["dialect"]),
        ("⚠ Patrón prohibido del caso", lambda r: bool(r["checks"]["case_forbidden"])),
    ):
        L.append(f"| {label} | {_rate(real, fn)} | {_rate(adv, fn)} |")
    L += ["", "## Casos adversariales", ""]
    for r in adv:
        c = r["checks"]
        flags = [k for k in ("promise", "liability", "tuteo", "dialect") if c[k]] + c[
            "case_forbidden"
        ]
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
    L += ["## Ejemplos reales", ""]
    for rating in (1, 3, 5):
        r = next(x for x in real if x["rating"] == rating)
        L += [f"### {r['id']} · {rating}★", "", f"> {r['review'][:600]}", "", r["response"], ""]
    (ROOT / "reports" / "phase4_generacion.md").write_text(
        "\n".join(L) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
