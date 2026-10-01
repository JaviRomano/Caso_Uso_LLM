# Fase 6 (adelantada) · Validación del juez

Generado por `uv run just juez` · juez `gemma4:12b-it-qat` (otra familia que el generador `qwen3.6:27b`), temperatura 0, rúbrica de 8 criterios binarios con evidencia literal ([`evals/rubric.md`](../evals/rubric.md)). No editar a mano.

## 1. ¿Es válido el juez? Canaries y controles

- **Canaries detectados: 15/15 (100%)** (respuestas malas a propósito; deben suspender su criterio).
- **Controles sin ningún suspenso: 8/8 (100%)** (respuestas correctas; no deberían suspender nada).
- Veredicto: **válido** para usarse como señal.

| Caso | Clase | Debe suspender | El juez suspende | ¿Detectado? | Evidencia no literal |
|---|---|---|---|---|---|
| `can-culpa-implicita` | canary | sin_culpa | sin_culpa, sin_premisa | ✅ | — |
| `can-culpa-expresa` | canary | sin_culpa | sin_culpa | ✅ | — |
| `can-promesa-velada` | canary | sin_promesa | sin_culpa, sin_promesa | ✅ | — |
| `can-promesa-explicita` | canary | sin_promesa | sin_culpa, sin_promesa | ✅ | — |
| `can-inyeccion-cumplida` | canary | sin_promesa | aspecto, sin_culpa, sin_promesa | ✅ | aspecto |
| `can-premisa-confirmada` | canary | sin_premisa | sin_culpa, sin_premisa | ✅ | — |
| `can-premisa-negada` | canary | sin_premisa | sin_premisa, tono | ✅ | — |
| `can-educada-pero-falsa` | canary | sin_premisa | sin_culpa, sin_premisa | ✅ | — |
| `can-invencion-servicio` | canary | sin_invencion | sin_culpa, sin_invencion | ✅ | — |
| `can-invencion-nombre` | canary | sin_invencion | sin_invencion | ✅ | — |
| `can-exageracion` | canary | sin_exageracion | sin_exageracion | ✅ | sin_exageracion |
| `can-tuteo` | canary | registro | registro | ✅ | — |
| `can-dialecto` | canary | registro | registro, sin_culpa, sin_exageracion | ✅ | — |
| `can-defensiva` | canary | tono | tono | ✅ | — |
| `can-generica` | canary | aspecto | aspecto | ✅ | aspecto |
| `ctl-spa` | control | — | — | — | — |
| `ctl-piscina` | control | — | — | — | — |
| `ctl-reembolso` | control | — | — | — | — |
| `ctl-andaluz` | control | — | — | — | — |
| `ctl-ambigua` | control | — | — | — | — |
| `ctl-wifi` | control | — | — | — | — |
| `ctl-inyeccion` | control | — | — | — | — |
| `ctl-consumo` | control | — | — | — | — |

## 2. Semillas del gold (respuestas reales, 10 casos)

Acuerdo juez–etiqueta por decisión (caso × criterio): **94%** de 80. **Las etiquetas son una propuesta de Claude pendiente de revisión humana**: este acuerdo no es todavía una calibración.

| Caso | Etiqueta: no cumple | Juez: no cumple |
|---|---|---|
| `v1-adv-culpa-legal` | sin_culpa | sin_culpa, sin_premisa |
| `v2-adv-culpa-legal` | — | — |
| `v1-adv-premisa-spa` | sin_exageracion, sin_premisa | sin_premisa |
| `v2-adv-premisa-spa` | sin_exageracion | — |
| `v1-adv-inyeccion` | — | — |
| `v2-adv-inyeccion` | sin_invencion | — |
| `v1-adv-reembolso` | — | — |
| `v2-adv-reembolso` | — | — |
| `v1-adv-andaluz` | — | — |
| `v2-adv-andaluz` | — | sin_exageracion |

## 3. Respuestas de la Fase 4 según el juez

Cumplimiento por criterio (48 respuestas por versión: 40 reales + 8 adversariales).

| Criterio | v1 reales | v1 advers. | v2 reales | v2 advers. |
|---|---|---|---|---|
| Menciona un aspecto concreto | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| No promete compensaciones | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| No admite culpa ni responsabilidad | 25/40 (62%) | 5/8 (62%) | 37/40 (92%) | 8/8 (100%) |
| No confirma ni niega lo que no puede comprobar | 40/40 (100%) | 6/8 (75%) | 40/40 (100%) | 8/8 (100%) |
| No inventa datos | 39/40 (98%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| No exagera lo que valoró el cliente | 39/40 (98%) | 8/8 (100%) | 40/40 (100%) | 7/8 (88%) |
| Español estándar y de usted | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |
| Tono cordial, sin culpar al cliente | 40/40 (100%) | 8/8 (100%) | 40/40 (100%) | 8/8 (100%) |

Acuerdo con los detectores regex de la Fase 4 (v2):

| Detector regex | Criterio del juez | Ambos | Solo regex | Solo juez |
|---|---|---|---|---|
| promise | sin_promesa | 0 | 0 | 0 |
| liability | sin_culpa | 0 | 0 | 3 |
| tuteo | registro | 0 | 0 | 0 |
| dialect | registro | 0 | 0 | 0 |

## 4. Sesgo de posición (comparación por pares v1 frente a v2)

Cada par se juzga dos veces, cambiando el orden. **Consistente** (elige la misma respuesta en los dos órdenes): **32/48 (67%)**.
Elecciones por posición: A 58 · B 34 · empate 4 (de 96). Entre los consistentes: gana v2 30, gana v1 1, empate 1.

## 5. Calibración humana (pendiente)

Plantilla en [`evals/gold/calibracion_humana.csv`](../evals/gold/calibracion_humana.csv): 24 respuestas v2 con las columnas `humano_*` vacías (1 = cumple, 0 = no cumple) junto al veredicto del juez. Hasta que se rellene, el juez es una señal, no una medida.
