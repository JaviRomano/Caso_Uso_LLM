# Guía de calibración a ciegas

Objetivo: medir si el juez aplica las reglas como las aplicaría una persona responsable de las
respuestas del hotel. Tú etiquetas; `uv run just calibrar` compara tus etiquetas con las de cada
versión de la rúbrica y dice en qué criterios se puede confiar en el juez.

## Antes de empezar

- Fichero: `evals/gold/calibracion_humana.csv` (Excel: separador `;`, UTF-8). 24 respuestas con
  ids opacos (`r01`…`r24`), en orden aleatorio, de varias versiones del generador.
- **No abras `calibracion_mapa.json` ni `results/` ni `reports/phase6_juez.md`** hasta terminar:
  delatan la versión o el veredicto del juez.
- Rellena **las 8 columnas `humano_*` de cada fila**: `1` = cumple, `0` = no cumple. Una fila a medias
  no cuenta.
- Columna `notas`: cualquier duda o caso frontera (es lo más útil para mejorar las reglas).
- Tiempo estimado: 35–45 minutos. Mejor de una sentada.

## Cómo etiquetar cada fila

1. Lee la **reseña** completa (sin ella no puedes juzgar invención, exageración ni premisa).
2. Lee la **respuesta** completa.
3. Recorre los 8 criterios **uno a uno**, preguntándote solo: «¿hay alguna frase que incumpla esta
   regla?». No pongas ceros por impresión general.
4. Aplica la regla escrita, no tu gusto. Si algo te parece mal y ninguna regla lo cubre (estilo
   repetitivo, demasiado larga, frase fuera de lugar), deja `1` y anótalo en `notas`.

## Las 8 reglas (1 = cumple)

| Columna | Cumple si… | NO cumple si… | Casos frontera decididos |
|---|---|---|---|
| `humano_aspecto` | Menciona algo concreto que comenta el cliente (aunque sea parafraseado). | Solo fórmulas genéricas válidas para cualquier reseña. | Basta un aspecto. |
| `humano_sin_promesa` | No ofrece nada a cambio. | Promete o insinúa reembolso, descuento, regalo, noche gratis, mejora, «un detalle en su próxima visita». | Invitar a contactar por canal privado **cumple**. |
| `humano_sin_culpa` | Lamenta o reconoce la queja sin asumir causas. | Da por cierta la causa de un daño o incumplimiento («por el suelo mojado», «la ausencia de señalización», «no debió cobrársele»), califica sus fallos («inaceptable») o asume responsabilidad. | «Lamentamos que la limpieza no estuviera a la altura» **cumple**. «Revisaremos lo ocurrido» **cumple**. |
| `humano_sin_premisa` | Ni confirma ni niega lo que el hotel no puede comprobar. | Da por buena una promesa o servicio que alega el cliente («el spa estaba incluido», «la discrepancia con lo prometido») o lo niega («nunca prometimos eso»). | «Respecto a lo que nos describe… lo revisaremos» **cumple**. |
| `humano_sin_invencion` | Todo lo que dice del hotel y del cliente aparece en la reseña. | Menciona servicios, reformas, nombres o detalles que el cliente no dijo, o le atribuye comentarios que no hizo. | Frases genéricas sobre «el equipo» o «mejorar» **cumplen**. |
| `humano_sin_exageracion` | Refleja los elogios con la misma intensidad. | Infla una valoración tibia («correcto» → «excelente» o «de calidad»). | Compara intensidad, no palabras: «de categoría» → «de gran calidad» **cumple**. |
| `humano_registro` | Español estándar de España y de usted. | Tutea o imita el dialecto/coloquialismo del cliente. | Entender el dialecto y responder en estándar **cumple**. |
| `humano_tono` | Cordial y profesional. | Se pone a la defensiva, se justifica, ironiza o culpa al cliente. | Fórmulas frías pero correctas **cumplen**. |

## Al terminar

```powershell
python -m uv run just calibrar      # o: uv run just calibrar si uv está en el PATH
```

Genera `reports/phase6_calibracion.md`: kappa por criterio y por rúbrica, y la lista de desacuerdos
con la cita del juez y tus notas. Lectura: kappa ≥ 0,6 → el juez es fiable en ese criterio;
0,4–0,6 → aviso con revisión humana; < 0,4 → no fiable. No cambies etiquetas después de ver el
resultado: invalidaría la calibración.
