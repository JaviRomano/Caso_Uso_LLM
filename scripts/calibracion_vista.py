"""Hoja de etiquetado HTML para evals/gold/calibracion_humana.csv (el CSV no se modifica).

Muestra cada reseña con su respuesta y, debajo, los 8 criterios como preguntas con botones
Sí (1) / No (0). Guarda el progreso en el navegador y exporta `id;criterios;notas` para integrarlo
en el CSV. No lee calibracion_mapa.json: la hoja es a ciegas.
"""
# ruff: noqa: E501  (textos de la guía y CSS: partirlos los haría menos legibles)

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evals" / "gold" / "calibracion_humana.csv"
OUT = ROOT / "evals" / "gold" / "calibracion_vista.html"

# (columna, nombre corto, pregunta, ayuda con los casos frontera de guia_calibracion.md)
CRITERIA = [
    ("aspecto", "Aspecto", "¿Menciona algo concreto que comenta el cliente?",
     "Basta un aspecto, aunque esté parafraseado. No cumple si solo hay fórmulas genéricas."),
    ("sin_promesa", "Sin promesa", "¿Evita ofrecer algo a cambio?",
     "No cumple si promete o insinúa reembolso, descuento, regalo, noche gratis, mejora o «un detalle». Invitar a contactar por canal privado SÍ cumple."),
    ("sin_culpa", "Sin culpa", "¿Lamenta sin asumir causas ni responsabilidad?",
     "No cumple si da por cierta la causa de un daño o incumplimiento, califica sus fallos («inaceptable») o asume culpa. «Lamentamos que la limpieza no estuviera a la altura» y «revisaremos lo ocurrido» SÍ cumplen."),
    ("sin_premisa", "Sin premisa", "¿Ni confirma ni niega lo que el hotel no puede comprobar?",
     "No cumple si da por buena una promesa o servicio que alega el cliente («el spa estaba incluido») o lo niega («nunca prometimos eso»). «Respecto a lo que nos describe… lo revisaremos» SÍ cumple."),
    ("sin_invencion", "Sin invención", "¿Todo lo que dice del hotel y del cliente aparece en la reseña?",
     "No cumple si menciona servicios, reformas, nombres o detalles que el cliente no dijo, o le atribuye comentarios que no hizo. Frases genéricas sobre «el equipo» SÍ cumplen."),
    ("sin_exageracion", "Sin exageración", "¿Refleja los elogios con la misma intensidad?",
     "No cumple si infla una valoración tibia («correcto» → «excelente»). Compara intensidad, no palabras."),
    ("registro", "Registro", "¿Español estándar de España y de usted?",
     "No cumple si tutea o imita el dialecto o coloquialismo del cliente."),
    ("tono", "Tono", "¿Cordial y profesional?",
     "No cumple si se pone a la defensiva, se justifica, ironiza o culpa al cliente. Fórmulas frías pero correctas SÍ cumplen."),
]  # fmt: skip

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--bd:#bbb;--card:#f6f6f6;--ok:#1f7a3d;--muted:#666}
@media (prefers-color-scheme:dark){:root{--bg:#1e1e1e;--fg:#ddd;--bd:#555;--card:#262626;--ok:#5fd18a;--muted:#999}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0 auto;max-width:1300px;padding:0 1rem 4rem}
header{position:sticky;top:0;background:var(--bg);padding:.6rem 0;border-bottom:1px solid var(--bd);z-index:2;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
button.main{font:inherit;padding:.4rem .9rem;cursor:pointer}
details.guia{margin:.6rem 0}
.card{background:var(--card);border:1px solid var(--bd);border-radius:6px;padding:.8rem;margin:1.2rem 0}
.card h2{margin:0 0 .5rem;font-size:1.1rem}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
@media (max-width:800px){.cols{grid-template-columns:1fr}}
.txt{white-space:pre-wrap;border:1px solid var(--bd);border-radius:4px;padding:.5rem;background:var(--bg)}
.lab{font-size:.8rem;color:var(--muted);text-transform:uppercase;margin-bottom:.2rem}
table.crit{border-collapse:collapse;width:100%;margin-top:.8rem}
.crit th,.crit td{border:1px solid var(--bd);padding:.35rem .5rem;text-align:left;vertical-align:top}
.crit td.b{white-space:nowrap;width:1%}
.crit label{margin-right:.7rem;cursor:pointer}
small{color:var(--muted);display:block}
textarea{width:100%;box-sizing:border-box;margin-top:.5rem;font:inherit}
.done{border-left:5px solid var(--ok)}
"""

JS = r"""
const KEY = "calibracion_humana_v1";
const state = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } })();
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
const cols = CRITERIA.map(c => c[0]);
const complete = id => cols.every(c => ["0", "1"].includes((state[id] || {})[c]));
function refresh() {
  let n = 0;
  for (const r of ROWS) {
    const ok = complete(r.id); n += ok;
    document.getElementById("card-" + r.id).classList.toggle("done", ok);
  }
  document.getElementById("prog").textContent = n + " de " + ROWS.length + " completas";
}
document.addEventListener("change", e => {
  const t = e.target, id = t.dataset.id;
  if (!id || t.tagName !== "INPUT") return;
  (state[id] = state[id] || {})[t.dataset.k] = t.value; save(); refresh();
});
document.addEventListener("input", e => {
  const t = e.target;
  if (t.tagName !== "TEXTAREA") return;
  (state[t.dataset.id] = state[t.dataset.id] || {}).notas = t.value; save();
});
document.querySelectorAll("input[type=radio]").forEach(i => {
  if ((state[i.dataset.id] || {})[i.dataset.k] === i.value) i.checked = true;
});
document.querySelectorAll("textarea").forEach(t => { t.value = (state[t.dataset.id] || {}).notas || ""; });
const q = s => '"' + s.replace(/"/g, '""') + '"';
function csv() {
  const L = ["id;" + cols.map(c => "humano_" + c).join(";") + ";notas"];
  for (const r of ROWS) {
    const s = state[r.id] || {};
    L.push([r.id, ...cols.map(c => s[c] === undefined ? "" : s[c]), q(s.notas || "")].join(";"));
  }
  return L.join("\n") + "\n";
}
document.getElementById("exp").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + csv()], { type: "text/csv;charset=utf-8" }));
  a.download = "calibracion_etiquetas.csv"; a.click();
};
document.getElementById("cp").onclick = async () => {
  try { await navigator.clipboard.writeText(csv()); alert("Copiado al portapapeles"); }
  catch (e) { prompt("Copia el texto:", csv()); }
};
refresh();
"""


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        rows = [
            {"id": r["id"], "reseña": r["reseña"], "respuesta": r["respuesta"]}
            for r in csv.DictReader(f, delimiter=";")
        ]

    guia = "".join(
        f"<li><b>{n}</b>: {esc(p)}<small>{esc(h)}</small></li>" for _, n, p, h in CRITERIA
    )
    body = [
        "<header><b>Calibración humana</b><span id=prog></span>",
        "<button class=main id=exp>Descargar etiquetas (CSV)</button>",
        "<button class=main id=cp>Copiar etiquetas</button></header>",
        "<details class=guia open><summary>Reglas (Sí = 1 = cumple · No = 0 = no cumple)</summary>",
        "<p>Pregúntate solo: «¿hay alguna frase que incumpla esta regla?». Aplica la regla escrita, "
        "no tu gusto; si algo te parece mal y ninguna regla lo cubre, marca Sí y anótalo.</p>"
        f"<ol>{guia}</ol></details>",
    ]
    for r in rows:
        rid = r["id"]
        trs = "".join(
            f"<tr><td><b>{esc(n)}</b></td><td>{esc(p)}<small>{esc(h)}</small></td><td class=b>"
            f"<label><input type=radio name='{rid}-{k}' data-id={rid} data-k={k} value=1> Sí (1)</label>"
            f"<label><input type=radio name='{rid}-{k}' data-id={rid} data-k={k} value=0> No (0)</label>"
            "</td></tr>"
            for k, n, p, h in CRITERIA
        )
        body.append(
            f"<section class=card id=card-{rid}><h2>{rid}</h2><div class=cols>"
            f"<div><div class=lab>Reseña del cliente</div><div class=txt>{esc(r['reseña'])}</div></div>"
            f"<div><div class=lab>Respuesta del hotel</div><div class=txt>{esc(r['respuesta'])}</div></div>"
            f"</div><table class=crit><tr><th>Criterio<th>¿Cumple?<th>Marca</tr>{trs}</table>"
            f"<textarea rows=2 data-id={rid} placeholder='Notas (dudas, casos frontera)'></textarea></section>"
        )
    data = (
        f"const ROWS={json.dumps([{'id': r['id']} for r in rows])};"
        f"const CRITERIA={json.dumps([[c[0]] for c in CRITERIA])};"
    )
    doc = (
        "<!doctype html><html lang=es><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Calibración humana</title><style>{CSS}</style><body>{''.join(body)}"
        f"<script>{data}{JS}</script></body></html>"
    )
    OUT.write_text(doc, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
