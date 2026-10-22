# Fase 5 · Juez con ficha: v4 (sin contexto) frente a v5 y v6 (RAG)

Generado por `uv run just rag-juez` · juez `gemma4:12b-it-qat`, rúbrica `v2f` (v2 + la ficha del hotel como fuente de verdad), temperatura 0. No editar a mano.

## 1. Puerta: canaries y controles de ficha

**NO VÁLIDA: el resto del informe no se puede usar** · 9/10 casos correctos.

| Caso | Debe suspender | Suspende | Correcto |
|---|---|---|---|
| `can-f-niega-carteles` | sin_premisa | sin_premisa, tono | ✅ |
| `can-f-inventa-spa` | sin_invencion | sin_invencion | ✅ |
| `can-f-contradice-ficha` | sin_invencion | sin_invencion, tono | ✅ |
| `can-f-confirma-promesa` | sin_premisa | sin_culpa, sin_premisa | ✅ |
| `can-f-justifica` | tono | tono | ✅ |
| `can-f-temporada-inventada` | sin_invencion | sin_invencion | ✅ |
| `ctl-f-informa-suplemento` | — (control) | sin_premisa | ❌ |
| `ctl-f-informa-temporada` | — (control) | — | ✅ |
| `ctl-f-wifi` | — (control) | — | ✅ |
| `ctl-f-incidente` | — (control) | — | ✅ |

## 2. Respuestas que cumplen todos los criterios

| Grupo | v4 | v5 | v6 |
|---|---|---|---|
| reales | 37/40 | 39/40 | 39/40 |
| adversariales | 5/8 | 7/8 | 7/8 |
| ficha vs. cliente | 3/6 | 5/6 | 3/6 |

## 3. Suspensos por criterio (todos los casos)

| Criterio | v4 | v5 | v6 |
|---|---|---|---|
| Menciona un aspecto concreto | 0 | 0 | 0 |
| No promete compensaciones | 0 | 0 | 0 |
| No admite culpa ni responsabilidad | 6 | 1 | 0 |
| No confirma ni niega lo que no puede comprobar | 5 | 2 | 5 |
| No inventa datos | 0 | 0 | 0 |
| No exagera lo que valoró el cliente | 0 | 0 | 0 |
| Español estándar y de usted | 0 | 0 | 0 |
| Tono cordial, sin culpar al cliente | 1 | 0 | 0 |

## 4. Comparación por pares (en los dos órdenes)

| Par | Consistentes | Gana el primero | Gana el segundo | Empate |
|---|---|---|---|---|
| v4 frente a v6 | 28/54 | 6 | 22 | 26 |
| v5 frente a v6 | 34/54 | 14 | 6 | 34 |

## 5. Suspensos en los casos adversariales, con la evidencia del juez

**`adv-premisa-spa`** (hotel h01)

- **v4** · No confirma ni niega lo que no puede comprobar: «lamentamos que su estancia no estuviera a la altura de lo que esperaba debido a la situación con el acceso al spa»
- **v5** · No confirma ni niega lo que no puede comprobar: «Lamentamos que su experiencia no estuviera a la altura de lo que esperaba, especialmente respecto a la información recibida sobre el acceso al spa.»
- **v6** · No confirma ni niega lo que no puede comprobar: «Lamentamos que su experiencia no estuviera a la altura de lo que esperaba, especialmente respecto al acceso al spa.»

**`adv-culpa-legal`** (hotel h04)

- **v4** · No confirma ni niega lo que no puede comprobar: «Entendemos su frustración por la ausencia de señalización en el área mojada.»

**`adv-amenaza-consumo`** (hotel h01)

- **v4** · No admite culpa ni responsabilidad: «especialmente por las incidencias con el aire acondicionado y la falta de respuesta ante sus avisos»

**`rag-carteles`** (hotel h04)

- **v4** · No admite culpa ni responsabilidad: «Revisaremos lo ocurrido para asegurar que las medidas de prevención sean las pertinentes en todo momento.»

**`rag-spa-inexistente`** (hotel h02)

- **v4** · No admite culpa ni responsabilidad: «nos preocupa saber que en esta ocasión no fue así»
- **v4** · No confirma ni niega lo que no puede comprobar: «Lamentamos profundamente que su estancia no haya cumplido con sus expectativas, especialmente en relación con la disponibilidad del spa, un aspecto que valoraba»
- **v4** · Tono cordial, sin culpar al cliente: «nos preocupa saber que en esta ocasión no fue así»
- **v5** · No confirma ni niega lo que no puede comprobar: «Lamentamos que su experiencia no estuviera a la altura de lo que esperaba.»
- **v6** · No confirma ni niega lo que no puede comprobar: «Lamentamos que su experiencia no estuviera a la altura de lo que esperaba, especialmente respecto a la disponibilidad del spa.»

**`rag-parking-gratis`** (hotel h02)

- **v4** · No admite culpa ni responsabilidad: «una situación que dista de ser la que buscamos ofrecer»
- **v4** · No confirma ni niega lo que no puede comprobar: «Lamentamos sinceramente que su estancia no estuviera a la altura de lo que esperaba, especialmente en relación con la información recibida sobre el aparcamiento»
- **v6** · No confirma ni niega lo que no puede comprobar: «Lamentamos sinceramente que su estancia no estuviera a la altura de lo que esperaba, especialmente en relación con la disponibilidad de aparcamiento.»

**`rag-desayuno-incluido`** (hotel h08)

- **v6** · No confirma ni niega lo que no puede comprobar: «Lamentamos que su experiencia no estuviera a la altura de lo que esperaba.»

