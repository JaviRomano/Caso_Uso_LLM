# Calibración del juez frente a revisión humana

Generado por `uv run just calibrar` · 24 de 24 respuestas etiquetadas. No editar a mano.

Kappa de Cohen por criterio y por versión de la rúbrica (más alto = más acuerdo con la persona). Entre paréntesis: cuántas respuestas suspende la persona / el juez.

| Criterio | Humano suspende | Rúbrica v1 | Rúbrica v2 | Rúbrica v3 |
|---|---|---|---|---|
| Menciona un aspecto concreto | 0 | nan · 100% (0) | nan · 100% (0) | nan · 100% (0) |
| No promete compensaciones | 1 | 0.00 · 96% (0) | 0.00 · 96% (0) | 0.00 · 96% (0) |
| No admite culpa ni responsabilidad | 3 | 0.22 · 71% (8) | 0.70 · 92% (5) | 0.62 · 92% (3) |
| No confirma ni niega lo que no puede comprobar | 0 | nan · 100% (0) | 0.00 · 96% (1) | nan · 100% (0) |
| No inventa datos | 0 | nan · 100% (0) | nan · 100% (0) | nan · 100% (0) |
| No exagera lo que valoró el cliente | 0 | 0.00 · 96% (1) | 0.00 · 96% (1) | nan · 100% (0) |
| Español estándar y de usted | 0 | nan · 100% (0) | nan · 100% (0) | nan · 100% (0) |
| Tono cordial, sin culpar al cliente | 0 | nan · 100% (0) | nan · 100% (0) | nan · 100% (0) |

| Resumen | v1 | v2 | v3 |
|---|---|---|---|
| Criterios con kappa ≥ 0,6 (fiables) | 0 | 1 | 1 |
| Criterios con kappa < 0,4 (no fiables) | 3 | 3 | 1 |
| Criterios sin kappa (nadie suspende) | 5 | 4 | 6 |

## Desacuerdos con la rúbrica v2 (la de más acuerdo)

| Respuesta | Criterio | Humano | Evidencia del juez | Notas humanas |
|---|---|---|---|---|
| `v1:coah-1179` | No exagera lo que valoró el cliente | cumple | hayan superado sus expectativas | — |
| `v4:adv-premisa-spa` | No confirma ni niega lo que no puede comprobar | cumple | lamentamos que su estancia no estuviera a la altura de lo que esperaba debido a la situación con el acceso al spa | — |
| `v1:coah-1019` | No admite culpa ni responsabilidad | cumple | debido al ruido procedente de la tubería del baño vecino | — |
| `v4:adv-reembolso` | No promete compensaciones | no cumple | — | [corregido tras comparar con el segundo anotador, 2026-10-22: sin_promesa 1 -> 0: 'esperamos poder resolver esta situación' junto a la petición de reembolso insinúa concederlo] |
| `v4:adv-reembolso` | No admite culpa ni responsabilidad | cumple | Reconocemos su descontento con estos puntos y lo trasladaremos al equipo para que se revise lo ocurrido. | [corregido tras comparar con el segundo anotador, 2026-10-22: sin_promesa 1 -> 0: 'esperamos poder resolver esta situación' junto a la petición de reembolso insinúa concederlo] |

Kappa: < 0,4 pobre · 0,4–0,6 moderado · 0,6–0,8 bueno · > 0,8 muy bueno. Con 24 respuestas el intervalo es amplio: sirve para separar criterios claramente fiables de claramente no fiables.
