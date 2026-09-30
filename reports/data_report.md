# Informe de datos (Fase 2)

Generado por `uv run just data` el 2026-10-01 · semilla 42. No editar a mano.

## 1. Fuentes

| Fuente | Commit HF | Filas crudas | Dominio |
|---|---|---|---|
| COAH | `058f847` | 1816 | hotel |
| COAR | `9d7d707` | 4932 | restaurante |

COAR trae 4.932 registros; la documentación de SINAI habla de 2.202.

## 2. Reglas aplicadas (textos afectados)

| Regla | Campo | COAH | COAR |
|---|---|---|---|
| R5 comillas CSV | title | 15 | 37 |
| R2 mojibake detectado | title | 0 | 2 |
| R1–R6 texto modificado | title | 1 | 4932 |
| R5 comillas CSV | text | 0 | 397 |
| R2 mojibake detectado | text | 0 | 5 |
| R1–R6 texto modificado | text | 1816 | 10 |
| R7 comillas del título | title | 1 | 4930 |
| R14 PII: habitacion | title+text | 15 | 0 |
| R14 PII: nombre_cargo | title+text | 4 | 0 |
| R14 PII: nombre_tratamiento | title+text | 19 | 0 |
| R14 PII: url | title+text | 1 | 0 |
| R14 PII: nombre_cargo | title+text | 0 | 54 |
| R14 PII: nombre_tratamiento | title+text | 0 | 17 |
| R14 PII: telefono | title+text | 0 | 1 |
| R14 PII: url | title+text | 0 | 1 |

Reglas de metadatos (R8–R13) sin excepciones: un valor no reconocido detiene el pipeline.

## 3. Embudo

| Paso | COAH | COAR |
|---|---|---|
| Crudo | 1816 | 4932 |
| Sin texto vacío ni ilegible | 1816 | 4931 |
| Solo español | 1816 | 4909 |
| Sin duplicados | 1791 | 4906 |

Motivos de descarte:

| drop_reason    |   coah |   coar |
|:---------------|-------:|-------:|
| conservada     |   1791 |   4906 |
| duplicado      |     25 |      3 |
| texto_ilegible |      0 |      1 |
| idioma_no_es   |      0 |     22 |

Filas en clústeres de duplicados (umbral Jaccard 0.8):

|                   |   filas |
|:------------------|--------:|
| ('coah', 'exact') |      48 |
| ('coah', 'near')  |       2 |
| ('coar', 'exact') |       2 |
| ('coar', 'near')  |       4 |

Clústeres con las dos fuentes: 0.

## 4. Resultado por partición

Etiqueta:

|                   |   negativo |   neutral |   positivo |   total |
|:------------------|-----------:|----------:|-----------:|--------:|
| ('coah', 'test')  |         75 |        43 |        151 |     269 |
| ('coah', 'train') |        350 |       198 |        705 |    1253 |
| ('coah', 'val')   |         75 |        43 |        151 |     269 |
| ('coar', 'test')  |        153 |        49 |        469 |     671 |
| ('coar', 'train') |        513 |       267 |       2789 |    3569 |
| ('coar', 'val')   |        149 |        49 |        468 |     666 |

Rating:

|                   |   1 |   2 |   3 |   4 |    5 |   total |
|:------------------|----:|----:|----:|----:|-----:|--------:|
| ('coah', 'test')  |  46 |  29 |  43 |  72 |   79 |     269 |
| ('coah', 'train') | 215 | 135 | 198 | 337 |  368 |    1253 |
| ('coah', 'val')   |  46 |  29 |  43 |  72 |   79 |     269 |
| ('coar', 'test')  | 116 |  37 |  49 | 120 |  349 |     671 |
| ('coar', 'train') | 345 | 168 | 267 | 796 | 1993 |    3569 |
| ('coar', 'val')   | 106 |  43 |  49 |  88 |  380 |     666 |

COAR, agrupado por establecimiento:

| split   |   establecimientos |   reseñas |   mayor_establecimiento |
|:--------|-------------------:|----------:|------------------------:|
| test    |                 19 |       671 |                   0.191 |
| train   |                 59 |      3569 |                   0.178 |
| val     |                 19 |       666 |                   0.167 |

Establecimientos compartidos entre train y test: 0.

COAR, origen del autor (R13, proxy de traducción automática):

| split   |   hispanic |   non_hispanic |   spain |   unknown |   total |
|:--------|-----------:|---------------:|--------:|----------:|--------:|
| test    |          6 |             77 |     328 |       260 |     671 |
| train   |         14 |            417 |    1812 |      1326 |    3569 |
| val     |          1 |             88 |     326 |       251 |     666 |

Marcas (no se descartan): 

| source   |   flag_short |   flag_long |
|:---------|-------------:|------------:|
| coah     |            0 |          18 |
| coar     |            0 |          50 |

## 5. Reproducción de la fuga del proyecto original

`Balanced_AHR.csv`: 7615 filas, 5101 textos únicos; ratings {1: 1677, 2: 994, 3: 2274, 5: 2670}.
Con el split original (`train_test_split(test_size=0.2, random_state=42)`), el **50.8%** de las 1523 filas de test aparece literal en train.
Por etiqueta: {0: 0.368, 1: 0.835, 3: 0.319}.

Textos de COAH presentes en `Balanced_AHR.csv`: 785 de 1792. Si alguna vez se combina con AHR, hay que deduplicar contra COAH.

## 6. Pendiente

- Nombres sin tratamiento ni cargo ("gracias a Emilio"): NER con Presidio.
- Etiquetas ruidosas con `cleanlab`: necesita las probabilidades del baseline (Fase 3).
- Traducción automática: `reviewer_origin` es un proxy; validar a mano una muestra.
