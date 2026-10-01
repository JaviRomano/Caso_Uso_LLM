# Fase 3 · Fine-tuning de mRoBERTa (BSC)

Generado por `uv run just train` · modelo `BSC-LT/mRoBERTa@0bede83` · config {'max_len': 384, 'batch_size': 16, 'lr': 2e-05, 'weight_decay': 0.01, 'warmup_frac': 0.1, 'max_epochs': 8, 'patience': 2, 'grad_clip': 1.0}. No editar a mano.

F1 macro. **media ± sd** entre semillas; **ensamble** = media de las probabilidades de las semillas, con IC 95 % por bootstrap. Parada temprana con `coah_val`.

| Opción | Semillas | `coah_val` | **`coah_test`** (n=269) | Ensamble `coah_test` | IC 95 % | `coar_test` (n=671) |
|---|---|---|---|---|---|---|
| **A** | 3 | 0.796 ± 0.007 | **0.822 ± 0.016** | 0.822 | 0.764–0.876 | 0.820 ± 0.012 |
| **A_sin_trad** | 3 | 0.795 ± 0.002 | **0.813 ± 0.023** | 0.802 | 0.740–0.857 | 0.806 ± 0.012 |
| **B** | 3 | 0.806 ± 0.014 | **0.800 ± 0.023** | 0.797 | 0.737–0.857 | 0.777 ± 0.017 |
| **C** | 3 | 0.786 ± 0.011 | **0.814 ± 0.008** | 0.839 | 0.781–0.891 | 0.811 ± 0.012 |

## F1 por clase (ensamble, `coah_test`)

| Opción | negativo | neutral | positivo |
|---|---|---|---|
| A | 0.935 | 0.608 | 0.925 |
| A_sin_trad | 0.931 | 0.543 | 0.932 |
| B | 0.900 | 0.548 | 0.944 |
| C | 0.935 | 0.641 | 0.941 |

## Frente a B (bootstrap pareado, ensambles, `coah_test`)

| Comparación | ΔF1 macro | IC 95 % | P(mejor que B) |
|---|---|---|---|
| A_vs_B | +0.025 | -0.033 a +0.082 | 0.79 |
| A_sin_trad_vs_B | +0.004 | -0.045 a +0.050 | 0.56 |
| C_vs_B | +0.042 | -0.019 a +0.102 | 0.91 |

## Matrices de confusión (ensamble, `coah_test`; filas: real)

**A**

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 72 | 3 | 0 |
| neutral | 6 | 24 | 13 |
| positivo | 1 | 9 | 141 |

**A_sin_trad**

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 74 | 1 | 0 |
| neutral | 10 | 19 | 14 |
| positivo | 0 | 7 | 144 |

**B**

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 72 | 3 | 0 |
| neutral | 13 | 20 | 10 |
| positivo | 0 | 7 | 144 |

**C**

| real \ pred | negativo | neutral | positivo |
|---|---|---|---|
| negativo | 72 | 3 | 0 |
| neutral | 7 | 25 | 11 |
| positivo | 0 | 7 | 144 |

