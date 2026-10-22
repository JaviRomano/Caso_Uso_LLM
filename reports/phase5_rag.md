# Fase 5 · RAG: evaluación de la recuperación

Generado por `uv run just rag` · embeddings `bge-m3` vía Ollama · 30 consultas ([`consultas_v1.json`](../evals/retrieval/consultas_v1.json)). No editar a mano.

Base de conocimiento **sintética** ([`kb/`](../kb/)): la ficha del hotel se selecciona por id (no se busca); se recuperan las políticas aplicables y las respuestas aprobadas a reseñas parecidas. Las etiquetas de relevancia son de Claude, pendientes de revisión humana.

## Índice de politicas (17 documentos, 30 consultas)

| Método | recall@1 | recall@3 (IC 95 %) | recall@5 | MRR |
|---|---|---|---|---|
| bm25 | 0.41 | 0.66 (0.49–0.80) | 0.77 | 0.67 |
| densa | 0.43 | 0.74 (0.60–0.87) | 0.82 | 0.72 |
| hibrida | 0.51 | 0.80 (0.68–0.92) | 0.89 | 0.78 |

Consultas donde la híbrida deja fuera de los 3 primeros algún relevante: 9.

| Consulta | Relevantes | Top 3 híbrida |
|---|---|---|
| `adv-reembolso` | pol-compensaciones, pol-reembolsos, pol-averias | pol-ruido, pol-reubicacion, pol-compensaciones |
| `adv-amenaza-consumo` | pol-reclamaciones-oficiales, pol-compensaciones, pol-averias | pol-reclamaciones-oficiales, pol-averias, pol-limpieza |
| `adv-4estrellas-queja` | pol-averias, pol-elogios | pol-averias, pol-ruido, pol-reubicacion |
| `adv-ambigua` | pol-ruido, pol-elogios | pol-ruido, pol-reubicacion, pol-precio |
| `q01` | pol-reembolsos, pol-compensaciones | pol-reembolsos, pol-precio, pol-ruido |
| `q06` | pol-personal, pol-elogios | pol-compensaciones, pol-personal, pol-ruido |
| `q07` | pol-personal | pol-compensaciones, pol-ruido, pol-instrucciones |
| `q10` | pol-reclamaciones-oficiales | pol-reubicacion, pol-reembolsos, pol-objetos-perdidos |
| `q19` | pol-elogios | pol-salud-alergias, pol-precio, pol-servicios |

## Índice de respuestas (16 documentos, 28 consultas)

| Método | recall@1 | recall@3 (IC 95 %) | recall@5 | MRR |
|---|---|---|---|---|
| bm25 | 0.25 | 0.64 (0.46–0.80) | 0.70 | 0.48 |
| densa | 0.55 | 0.91 (0.82–0.98) | 0.93 | 0.77 |
| hibrida | 0.39 | 0.82 (0.68–0.93) | 0.88 | 0.63 |

Consultas donde la híbrida deja fuera de los 3 primeros algún relevante: 7.

| Consulta | Relevantes | Top 3 híbrida |
|---|---|---|
| `q06` | resp-elogio, resp-dialecto | resp-aire-consumo, resp-wifi, resp-elogio |
| `q08` | resp-aire-consumo, resp-wifi | resp-aire-consumo, resp-limpieza, resp-caida |
| `q09` | resp-aire-consumo, resp-wifi | resp-caida, resp-aire-consumo, resp-reembolso |
| `q13` | resp-alergia | resp-correcto, resp-reubicacion, resp-wifi |
| `q16` | resp-precio | resp-correcto, resp-ruido, resp-spa-incluido |
| `q17` | resp-instrucciones | resp-correcto, resp-precio, resp-reembolso |
| `q21` | resp-reembolso, resp-ruido | resp-precio, resp-trato, resp-reembolso |

