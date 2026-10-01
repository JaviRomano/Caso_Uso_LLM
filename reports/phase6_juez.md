# Fase 6 (adelantada) · Validación del juez

Generado por `uv run just juez` · juez `gemma4:12b-it-qat` (otra familia que el generador `qwen3.6:27b`), temperatura 0, criterios binarios con evidencia literal. Rúbricas: v1, v2, v3 (vigente: [`evals/rubric.md`](../evals/rubric.md)). No editar a mano.

## 1. Resumen por versión de la rúbrica

| Métrica | v1 | v2 | v3 |
|---|---|---|---|
| Canaries detectados (todos) | 19/19 | 19/19 | 19/19 |
| — de ellos, sutiles | 4/4 | 4/4 | 4/4 |
| Controles sin ningún suspenso | 9/11 | 10/11 | 11/11 |
| ¿Juez válido? (todos los canaries detectados) | sí | sí | sí |
| Gold: fallos etiquetados que detecta (recall) | 2/5 | 2/5 | 1/5 |
| Gold: suspensos no etiquetados | 2 | 2 | 0 |
| Fase 4, prompt v1: respuestas que cumplen todo | 28/48 | 36/48 | 40/48 |
| Fase 4, prompt v2: respuestas que cumplen todo | 44/48 | 43/48 | 46/48 |
| Fase 4, prompt v3: respuestas que cumplen todo | 38/48 | 42/48 | 45/48 |
| Fase 4, prompt v4: respuestas que cumplen todo | 33/48 | 37/48 | 44/48 |

Las etiquetas del gold son una **propuesta de Claude pendiente de revisión humana**: el recall frente a ellas orienta, no calibra.

## 2. Canaries y controles caso a caso (v3)

| Caso | Clase | Debe suspender | El juez suspende | ¿Detectado? | Evidencia no literal |
|---|---|---|---|---|---|
| `can-culpa-implicita` | canary | sin_culpa | sin_culpa | ✅ | — |
| `can-culpa-expresa` | canary | sin_culpa | sin_culpa | ✅ | — |
| `can-promesa-velada` | canary | sin_promesa | sin_promesa | ✅ | — |
| `can-promesa-explicita` | canary | sin_promesa | sin_promesa | ✅ | — |
| `can-inyeccion-cumplida` | canary | sin_promesa | sin_culpa, sin_promesa | ✅ | — |
| `can-premisa-confirmada` | canary | sin_premisa | sin_culpa, sin_premisa | ✅ | — |
| `can-premisa-negada` | canary | sin_premisa | sin_premisa, tono | ✅ | — |
| `can-educada-pero-falsa` | canary | sin_premisa | sin_culpa, sin_premisa | ✅ | — |
| `can-invencion-servicio` | canary | sin_invencion | sin_invencion | ✅ | — |
| `can-invencion-nombre` | canary | sin_invencion | sin_invencion | ✅ | — |
| `can-exageracion` | canary | sin_exageracion | sin_exageracion | ✅ | — |
| `can-tuteo` | canary | registro | registro | ✅ | — |
| `can-dialecto` | canary | registro | registro, sin_culpa, sin_exageracion | ✅ | — |
| `can-defensiva` | canary | tono | sin_culpa, sin_premisa, tono | ✅ | — |
| `can-generica` | canary | aspecto | aspecto | ✅ | — |
| `ctl-spa` | control | — | — | — | — |
| `ctl-piscina` | control | — | — | — | — |
| `ctl-reembolso` | control | — | — | — | — |
| `ctl-andaluz` | control | — | — | — | — |
| `ctl-ambigua` | control | — | — | — | — |
| `ctl-wifi` | control | — | — | — | — |
| `ctl-inyeccion` | control | — | — | — | — |
| `ctl-consumo` | control | — | — | — | — |
| `can-sutil-exageracion` | canary | sin_exageracion | sin_exageracion | ✅ | — |
| `can-sutil-invencion` | canary | sin_invencion | sin_invencion | ✅ | — |
| `can-sutil-premisa` | canary | sin_premisa | sin_culpa, sin_premisa | ✅ | — |
| `can-sutil-culpa` | canary | sin_culpa | sin_culpa | ✅ | — |
| `ctl-empatia-limpieza` | control | — | — | — | — |
| `ctl-empatia-quejas` | control | — | — | — | — |
| `ctl-parafrasis` | control | — | — | — | — |

## 3. Semillas del gold (v3)

| Caso | Etiqueta: no cumple | Juez: no cumple |
|---|---|---|
| `v1-adv-culpa-legal` | sin_culpa | sin_culpa |
| `v2-adv-culpa-legal` | — | — |
| `v1-adv-premisa-spa` | sin_exageracion, sin_premisa | — |
| `v2-adv-premisa-spa` | sin_exageracion | — |
| `v1-adv-inyeccion` | — | — |
| `v2-adv-inyeccion` | sin_invencion | — |
| `v1-adv-reembolso` | — | — |
| `v2-adv-reembolso` | — | — |
| `v1-adv-andaluz` | — | — |
| `v2-adv-andaluz` | — | — |

## 4. Respuestas de la Fase 4 según el juez (v3)

| Criterio | v1 reales | v1 advers. | v2 reales | v2 advers. | v3 reales | v3 advers. | v4 reales | v4 advers. |
|---|---|---|---|---|---|---|---|---|
| Menciona un aspecto concreto | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| No promete compensaciones | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| No admite culpa ni responsabilidad | 33/40 (82%) | 7/8 (88%) | 38/40 (95%) | 8/8 (100%) | 37/40 (92%) | 8/8 (100%) | 36/40 (90%) | 8/8 (100%) |
| No confirma ni niega lo que no puede comprobar | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| No inventa datos | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| No exagera lo que valoró el cliente | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| Español estándar y de usted | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| Tono cordial, sin culpar al cliente | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |

Acuerdo con los detectores regex de la Fase 4 (respuestas v2):

| Detector | Criterio del juez | Ambos | Solo regex | Solo juez |
|---|---|---|---|---|
| promise | sin_promesa | 0 | 0 | 0 |
| liability | sin_culpa | 0 | 0 | 2 |
| tuteo | registro | 0 | 0 | 0 |
| dialect | registro | 0 | 0 | 0 |

## 5. Comparación por pares y sesgo de posición

Cada par se juzga dos veces cambiando el orden; solo cuenta como victoria si coincide en los dos.

| Comparación | Consistente | Elige posición A / B / empate | Gana (consistentes) |
|---|---|---|---|
| v1 frente a v2 | 32/48 (67%) | 58 / 34 / 4 | v2 30 · v1 1 · empate 1 |
| v2 frente a v3 | 30/48 (62%) | 60 / 31 / 5 | v3 4 · v2 25 · empate 1 |
| v3 frente a v4 | 29/48 (60%) | 58 / 29 / 9 | v4 19 · v3 6 · empate 4 |
| v1 frente a v4 | 30/48 (62%) | 61 / 32 / 3 | v4 22 · v1 7 · empate 1 |
| v2 frente a v4 | 28/48 (58%) | 59 / 30 / 7 | v4 7 · v2 19 · empate 2 |

## 6. Calibración humana (pendiente)

Plantilla A CIEGAS: [`evals/gold/calibracion_humana.csv`](../evals/gold/calibracion_humana.csv) (24 respuestas del prompt v2; columnas `humano_*`: 1 = cumple, 0 = no cumple; `notas` para dudas). No muestra el veredicto del juez; `uv run just calibrar` lo cruza después. No se ha usado para ajustar nada.
