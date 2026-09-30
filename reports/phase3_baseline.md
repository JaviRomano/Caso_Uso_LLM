# Fase 3 · Baseline TF-IDF + regresión logística

Generado por `uv run just baseline` el 2026-10-01 · semilla 42. No editar a mano.

Selección de `C` con `coah_val`; `coah_test` es la métrica principal (hoteles). La opción C (secuencial) no aplica a un modelo convexo: se evalúa con RoBERTa.

| Opción | Filas de train | C | CV COAH (media ± sd) | F1 macro `coah_test` (n=269) | IC 95 % | F1 macro `coar_test` (n=671) |
|---|---|---|---|---|---|---|
| **B** · Solo COAH | 1253 | 0.3 | 0.739 ± 0.023 | **0.710** | 0.650–0.767 | 0.628 |
| **A** · COAH + COAR mezclados (fuentes y clases ponderadas) | 4822 | 0.3 | 0.761 ± 0.018 | **0.737** | 0.678–0.791 | 0.749 |
| **A_sin_trad** · Como A, sin reseñas de COAR de autores no hispanohablantes | 4405 | 0.3 | 0.762 ± 0.015 | **0.750** | 0.691–0.803 | 0.765 |

## F1 por clase en `coah_test`

| Opción | negativo | neutral | positivo |
|---|---|---|---|
| B | 0.848 | 0.405 | 0.878 |
| A | 0.859 | 0.473 | 0.878 |
| A_sin_trad | 0.865 | 0.495 | 0.889 |

## ¿Las diferencias superan el ruido del test? (bootstrap pareado)

| Comparación | ΔF1 macro | IC 95 % | P(mejor que B) |
|---|---|---|---|
| A_vs_B | +0.027 | -0.013 a +0.067 | 0.89 |
| A_sin_trad_vs_B | +0.039 | -0.002 a +0.082 | 0.97 |

## Matrices de confusión en `coah_test` (filas: real; columnas: predicho)

**B**

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 64 | 9 | 2 |
| neutral | 9 | 17 | 17 |
| positivo | 3 | 15 | 133 |

**A**

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 64 | 10 | 1 |
| neutral | 7 | 22 | 14 |
| positivo | 3 | 18 | 130 |

**A_sin_trad**

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 64 | 10 | 1 |
| neutral | 7 | 23 | 13 |
| positivo | 2 | 17 | 132 |

