"""Hoja HTML para revisar a mano las respuestas aprobadas de kb/ (el JSON no se modifica).

Cada tarjeta muestra la reseña, la ficha del hotel, la respuesta propuesta y las políticas
de referencia. Se marca Aprobada / Corregir / Descartar, con respuesta corregida y notas.
Guarda el progreso en el navegador y exporta un CSV para integrarlo en kb/respuestas_aprobadas.json.

Uso: python scripts/revision_kb.py
"""
# ruff: noqa: E501  (CSS y JS en línea)

import html
import json

from caso_uso_llm.paths import ROOT
from caso_uso_llm.rag import kb

OUT = ROOT / "kb" / "revision.html"

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--bd:#bbb;--card:#f6f6f6;--ok:#1f7a3d;--ko:#b3261e;--warn:#9a6700;--muted:#666}
@media (prefers-color-scheme:dark){:root{--bg:#1e1e1e;--fg:#ddd;--bd:#555;--card:#262626;--ok:#5fd18a;--ko:#ff8a80;--warn:#e3b341;--muted:#999}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0 auto;max-width:1300px;padding:0 1rem 4rem}
header{position:sticky;top:0;background:var(--bg);padding:.6rem 0;border-bottom:1px solid var(--bd);z-index:2;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
button{font:inherit;padding:.4rem .9rem;cursor:pointer}
.card{background:var(--card);border:1px solid var(--bd);border-left:6px solid var(--bd);border-radius:6px;padding:.8rem;margin:1.2rem 0}
.card.aprobada{border-left-color:var(--ok)}.card.corregir{border-left-color:var(--warn)}.card.descartar{border-left-color:var(--ko)}
.card h2{margin:0 0 .5rem;font-size:1.1rem}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
@media (max-width:800px){.cols{grid-template-columns:1fr}}
.txt{white-space:pre-wrap;border:1px solid var(--bd);border-radius:4px;padding:.5rem;background:var(--bg)}
.lab{font-size:.8rem;color:var(--muted);text-transform:uppercase;margin:.4rem 0 .2rem}
details{margin:.5rem 0}
.est label{margin-right:1rem;cursor:pointer}
textarea{width:100%;box-sizing:border-box;font:inherit;margin-top:.3rem}
ul.chk{margin:.3rem 0;padding-left:1.2rem;color:var(--muted);font-size:.9rem}
"""

CHECKLIST = [
    "De usted y en español estándar, sin imitar el dialecto.",
    "No admite causas ni culpa (lamentar sin dar por cierto el motivo).",
    "No promete ni insinúa compensaciones.",
    "No confirma ni niega lo que el hotel no puede comprobar; los datos del hotel salen de la ficha.",
    "No inventa ni exagera; menciona lo que dice el cliente.",
    "Canal privado solo si el cliente pide algo; firma «El equipo del hotel»; 50–130 palabras.",
]

JS = r"""
const KEY = "revision_kb_v1";
const st = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } })();
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} };
const get = id => (st[id] = st[id] || {});
function paint() {
  let n = 0;
  for (const id of IDS) {
    const e = get(id).estado || ""; if (e) n++;
    const c = document.getElementById("card-" + id);
    c.classList.remove("aprobada", "corregir", "descartar"); if (e) c.classList.add(e);
    document.getElementById("fix-" + id).style.display = e === "corregir" ? "block" : "none";
  }
  document.getElementById("prog").textContent = n + " de " + IDS.length + " revisadas";
}
document.addEventListener("change", e => { const t = e.target; if (t.name && t.name.startsWith("e-")) { get(t.dataset.id).estado = t.value; save(); paint(); } });
document.addEventListener("input", e => { const t = e.target; if (t.dataset.f) { get(t.dataset.id)[t.dataset.f] = t.value; save(); } });
for (const id of IDS) {
  const s = get(id);
  document.querySelectorAll(`input[name="e-${id}"]`).forEach(i => { i.checked = i.value === s.estado; });
  document.querySelectorAll(`textarea[data-id="${id}"]`).forEach(t => {
    if (s[t.dataset.f] !== undefined) t.value = s[t.dataset.f];
    else if (t.dataset.f === "respuesta") s.respuesta = t.value;
  });
}
const q = s => '"' + String(s || "").replace(/"/g, '""') + '"';
function csv() {
  const L = ["id;estado;respuesta_corregida;notas"];
  for (const id of IDS) { const s = get(id); L.push([id, s.estado || "", s.estado === "corregir" ? q(s.respuesta) : '""', q(s.notas)].join(";")); }
  return L.join("\n") + "\n";
}
document.getElementById("exp").onclick = () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + csv()], { type: "text/csv;charset=utf-8" }));
  a.download = "revision_kb.csv"; a.click();
};
paint();
"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def main() -> None:
    pols = {p.id: p.payload for p in kb.politicas(include_always=True)}
    resps = kb.respuestas()
    checklist = "".join(f"<li>{esc(c)}</li>" for c in CHECKLIST)
    body = [
        "<header><b>Revisión de respuestas aprobadas (kb/)</b><span id=prog></span>",
        "<button id=exp>Descargar revisión (CSV)</button></header>",
        "<p>Son el modelo que imitará el generador: cualquier defecto aquí se copiará. Marca cada una como "
        "<b>Aprobada</b>, <b>Corregir</b> (edita el texto) o <b>Descartar</b>.</p>",
        f"<details open><summary>Qué comprobar</summary><ul class=chk>{checklist}</ul></details>",
        "<details><summary>Políticas de la cadena</summary>"
        + "".join(
            f"<p><b>{esc(p['titulo'])}</b> <small>({esc(i)})</small><br>{esc(p['texto'])}</p>"
            for i, p in pols.items()
        )
        + "</details>",
    ]
    for d in resps:
        r, rid = d.payload, d.id
        words = len(r["respuesta"].split())
        estados = "".join(
            f"<label><input type=radio name='e-{rid}' data-id={rid} value={v}> {t}</label>"
            for v, t in (
                ("aprobada", "Aprobada"),
                ("corregir", "Corregir"),
                ("descartar", "Descartar"),
            )
        )
        body.append(
            f"<section class=card id=card-{rid}><h2>{rid} <small>· hotel {r['hotel']} · {words} palabras</small></h2>"
            f"<div class=cols><div><div class=lab>Reseña</div><div class=txt>{esc(r['resena'])}</div>"
            f"<div class=lab>Ficha del hotel</div><div class=txt>{esc(kb.ficha_texto(r['hotel']))}</div></div>"
            f"<div><div class=lab>Respuesta propuesta</div><div class=txt>{esc(r['respuesta'])}</div>"
            f"<div class=est style='margin-top:.6rem'>{estados}</div>"
            f"<div id=fix-{rid}><div class=lab>Respuesta corregida</div>"
            f"<textarea rows=9 data-id={rid} data-f=respuesta>{esc(r['respuesta'])}</textarea></div>"
            f"<div class=lab>Notas</div><textarea rows=2 data-id={rid} data-f=notas></textarea></div></div></section>"
        )
    doc = (
        "<!doctype html><html lang=es><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Revisión KB</title><style>{CSS}</style><body>{''.join(body)}"
        f"<script>const IDS={json.dumps([d.id for d in resps])};{JS}</script></body></html>"
    )
    OUT.write_text(doc, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
