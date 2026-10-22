"""Figuras del README a partir de los resultados versionados (no lleva cifras escritas a mano).

1. Efecto del RAG: suspensos del juez con ficha (rúbrica v2g) por versión del prompt, en los
   dos criterios que cambian (results/phase5_juez.json).
2. Enrutado del pipeline: publicables frente a revisión humana por grupo
   (results/pipeline_cola.json).

Cada figura sale en inglés y en español, y en tema claro y oscuro (el README las sirve con
<picture> según el tema de GitHub). Paleta: los tres primeros colores categóricos de la paleta de
referencia, validados en los dos modos; cada barra lleva su valor escrito (el aqua claro no llega
a 3:1 contra el fondo).

Uso: uv run python scripts/figuras.py   ->  docs/img/*.png
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"

THEMES = {
    "light": {"surface": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3df",
              "series": ["#2a78d6", "#eb6834", "#1baf7a"]},
    "dark": {"surface": "#1a1a19", "text": "#f0efec", "muted": "#c3c2b7", "grid": "#3a3a37",
             "series": ["#3987e5", "#d95926", "#199e70"]},
}  # fmt: skip

T = {
    "en": {
        "rag_title": "RAG removes implicit blame",
        "rag_sub": "LLM-judge fails with the hotel fact sheet (rubric v2g), 54 replies per version",
        "crit": ["Admits blame or a cause", "Confirms or denies what\nit cannot verify"],
        "versions": ["v4 · no context", "v5 · RAG", "v6 · RAG, corrected"],
        "route_title": "What the pipeline publishes and what goes to a person",
        "route_sub": "54 reviews: 14 synthetic adversarial cases + 40 real AHR reviews (8 per rating)",
        "groups": ["Synthetic", "AHR 1★", "AHR 2★", "AHR 3★", "AHR 4★", "AHR 5★"],
        "routes": ["Published", "Human review"],
        "x": "replies",
    },
    "es": {
        "rag_title": "El RAG elimina la culpa implícita",
        "rag_sub": "Suspensos del juez con la ficha del hotel (rúbrica v2g), 54 respuestas por versión",
        "crit": ["Admite culpa o una causa", "Confirma o niega lo que\nno puede comprobar"],
        "versions": ["v4 · sin contexto", "v5 · RAG", "v6 · RAG corregido"],
        "route_title": "Qué publica el pipeline y qué pasa a una persona",
        "route_sub": "54 reseñas: 14 casos adversariales sintéticos + 40 reales del AHR (8 por puntuación)",
        "groups": ["Sintéticos", "AHR 1★", "AHR 2★", "AHR 3★", "AHR 4★", "AHR 5★"],
        "routes": ["Publicable", "Revisión humana"],
        "x": "respuestas",
    },
}


def rounded_barh(ax, y, left, width, height, color, surface):
    """Barra horizontal con el extremo de datos redondeado (4 px) y 2 px de separación."""
    if width <= 0:
        return
    ax.add_patch(FancyBboxPatch((left, y - height / 2), width, height, linewidth=2,
                                edgecolor=surface, facecolor=color,
                                boxstyle="round,pad=0,rounding_size=0.08", mutation_aspect=0.6))  # fmt: skip


def _lum(hex_color: str) -> float:
    rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ink_on(fill: str, th: dict) -> str:
    """Texto sobre una barra: blanco o la tinta del tema, el que más contraste dé."""

    def contrast(a, b):
        hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    dark_ink = THEMES["light"]["text"]
    return "#ffffff" if contrast(fill, "#ffffff") >= contrast(fill, dark_ink) else dark_ink


def style(fig, ax, th):
    fig.patch.set_facecolor(th["surface"])
    ax.set_facecolor(th["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(th["grid"])
    ax.tick_params(colors=th["muted"], length=0, labelsize=10)
    ax.grid(axis="x", color=th["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def header(fig, th, title, sub):
    fig.text(0.02, 0.95, title, color=th["text"], fontsize=15, fontweight="bold", va="top")
    fig.text(0.02, 0.87, sub, color=th["muted"], fontsize=10.5, va="top")


def legend(fig, th, labels, colors, y=0.80):
    x = 0.02
    for label, color in zip(labels, colors, strict=True):
        fig.patches.append(FancyBboxPatch((x, y - 0.012), 0.014, 0.03, transform=fig.transFigure,
                                          facecolor=color, edgecolor="none",
                                          boxstyle="round,pad=0,rounding_size=0.003"))  # fmt: skip
        fig.text(x + 0.02, y, label, color=th["text"], fontsize=10, va="center")
        x += 0.02 + 0.0105 * len(label) + 0.04


def rag_data() -> list[list[int]]:
    cases = json.loads((ROOT / "results" / "phase5_juez.json").read_text(encoding="utf-8"))["cases"]
    return [
        [sum(not c["verdicts"][v][crit]["cumple"] for c in cases) for v in ("v4", "v5", "v6")]
        for crit in ("sin_culpa", "sin_premisa")
    ]


def route_data() -> list[tuple[int, int]]:
    out = json.loads((ROOT / "results" / "pipeline_cola.json").read_text(encoding="utf-8"))
    groups = [[it for it in out if it["meta"]["grupo"] == "sintético"]]
    groups += [[it for it in out if it["meta"].get("rating") == k] for k in range(1, 6)]
    return [(sum(it["decision"] == "publicable" for it in g),
             sum(it["decision"] != "publicable" for it in g)) for g in groups]  # fmt: skip


def fig_rag(lang: str, theme: str) -> None:
    t, th, data = T[lang], THEMES[theme], rag_data()
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=150)
    style(fig, ax, th)
    h, gap = 0.22, 0.04
    for gi, values in enumerate(data):
        for vi, val in enumerate(values):
            y = gi + (vi - 1) * (h + gap)  # v4 arriba, en el orden de la leyenda
            rounded_barh(ax, y, 0, val, h, th["series"][vi], th["surface"])
            ax.text(val + 0.12, y, str(val), color=th["text"], fontsize=10, va="center")
    ax.set_yticks(range(len(data)), t["crit"], color=th["text"], fontsize=11)
    ax.set_ylim(len(data) - 0.5, -0.5)
    ax.set_xlim(0, max(map(max, data)) + 1)
    ax.set_xlabel(t["x"], color=th["muted"], fontsize=10)
    header(fig, th, t["rag_title"], t["rag_sub"])
    legend(fig, th, t["versions"], th["series"])
    fig.subplots_adjust(left=0.25, right=0.97, top=0.72, bottom=0.14)
    fig.savefig(OUT / f"rag_{lang}_{theme}.png", facecolor=th["surface"])
    plt.close(fig)


def fig_route(lang: str, theme: str) -> None:
    t, th, data = T[lang], THEMES[theme], route_data()
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=150)
    style(fig, ax, th)
    colors = th["series"][:2]
    for gi, (pub, rev) in enumerate(data):
        rounded_barh(ax, gi, 0, pub, 0.6, colors[0], th["surface"])
        rounded_barh(ax, gi, pub, rev, 0.6, colors[1], th["surface"])
        for left, val, fill in ((0, pub, colors[0]), (pub, rev, colors[1])):
            if val:
                ax.text(left + val / 2, gi, str(val), color=ink_on(fill, th), fontsize=10,
                        fontweight="bold", ha="center", va="center")  # fmt: skip
    ax.set_yticks(range(len(data)), t["groups"], color=th["text"], fontsize=11)
    ax.set_ylim(len(data) - 0.5, -0.5)
    ax.set_xlim(0, max(p + r for p, r in data))
    ax.set_xlabel(t["x"], color=th["muted"], fontsize=10)
    header(fig, th, t["route_title"], t["route_sub"])
    legend(fig, th, t["routes"], colors)
    fig.subplots_adjust(left=0.14, right=0.97, top=0.72, bottom=0.13)
    fig.savefig(OUT / f"pipeline_{lang}_{theme}.png", facecolor=th["surface"])
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for lang in T:
        for theme in THEMES:
            fig_rag(lang, theme)
            fig_route(lang, theme)
    print(sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
