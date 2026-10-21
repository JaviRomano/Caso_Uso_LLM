# Reseñas de hotel: sentimiento y respuesta con LLMs locales

Pipeline para una cadena hotelera que **clasifica el sentimiento** de una reseña (negativo, neutral, positivo) y **redacta una respuesta** profesional y personalizada. Todo se ejecuta en local, sobre una GPU AMD, sin enviar reseñas a servicios externos.

Es la reconstrucción de un primer intento (en [`legacy/`](legacy/), etiqueta `v1-original`) cuyas métricas no eran válidas. Ver [por qué se rehízo](#por-qué-se-rehízo).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1. Entorno | `uv` + lockfile, rutas absolutas, semillas, tests, GPU AMD con ROCm en WSL2 | Hecho |
| 2. Datos | Corpus de SINAI en español de España, normalización, deduplicación, split sin fuga | Hecho |
| 3. Clasificador | Baseline TF-IDF, *fine-tuning* de mRoBERTa, LLM *zero-shot* y evaluación realista | Hecho ([resultados](#resultados-del-clasificador)) |
| 4. Generación | Respuesta con un LLM local, extracción de aspectos en JSON, cuatro versiones del prompt | Hecho, primera iteración ([resultados](#generación-de-respuestas)) |
| 5. RAG y guardarraíles | Ficha del hotel y políticas; sin compensaciones ni datos inventados; cola de revisión humana | Pendiente |
| 6. Evaluación | Juez LLM con rúbrica binaria, *canaries*, sesgo de posición y calibración humana | En curso ([resultados](#juez-llm-evaluar-al-evaluador)) |

## Por qué se rehízo

El proyecto original reportaba un F1 que no se sostenía:

- **Fuga de datos.** El dataset se sobremuestreó *antes* de separar train y test, así que el **50,8 %** del test aparecía literal en train. Se reproduce con el mismo split en [`reports/data_report.md`](reports/data_report.md) (§5).
- **El test se usaba para elegir el modelo**, y no había conjunto de validación.
- **Faltaba el rating 4★**: "positivo" significaba solo 5★.
- **Las respuestas de entrenamiento se elegían al azar** entre 30 plantillas, sin relación con la reseña, así que el generador no podía aprender a personalizar.

## Datos

Corpus académicos del grupo [SINAI](https://sinai.ujaen.es/) (Universidad de Jaén), en español de España y con las cinco puntuaciones:

| Corpus | Contenido | Uso |
|---|---|---|
| [COAH](https://huggingface.co/datasets/SINAI/COAH) | 1.816 reseñas de hoteles andaluces (TripAdvisor) | Clasificador, test principal |
| [COAR](https://huggingface.co/datasets/SINAI/COAR) | 4.932 reseñas de 97 restaurantes andaluces (TripAdvisor) | Entrenamiento adicional y test fuera de dominio |
| [SFU-Review-SP-Neg](https://huggingface.co/datasets/SINAI/SFU-Review-SP-Neg) | Reseñas de hoteles de ciao.es con la negación anotada | Prueba de robustez |
| [AHR completo](https://www.kaggle.com/datasets/chizhikchi/andalusian-hotels-reviews-unbalanced) (Kaggle, CC BY-NC 4.0) | 11.414 reseñas de 703 hoteles (TripAdvisor 2021), tras quitar duplicados y todo lo que coincide con COAH/COAR | **Test grande fuera de distribución**; nunca se entrena con él |

Licencias CC BY-NC-SA 4.0 (SINAI) y CC BY-NC 4.0 (AHR); uso no comercial. Los datos no se incluyen en el repositorio: se descargan con un commit fijado y en git solo se guarda su hash ([`data/raw/SHA256SUMS`](data/raw/SHA256SUMS)). COAH y COAR son *gated*: hay que aceptar sus términos en Hugging Face con tu cuenta.

El pipeline de datos ([`reports/data_report.md`](reports/data_report.md) recoge cada paso con sus cifras):

- Normaliza el texto sin borrar señal de sentimiento: conserva mayúsculas, signos y emojis.
- Enmascara datos personales: nombres con tratamiento o cargo ("la Srta. Ana", "el camarero Juan"), teléfonos, emails, URLs y números de habitación. Del autor no se guarda nada salvo una categoría de origen (España, hispanohablante, otro), que sirve para detectar reseñas traducidas automáticamente.
- Elimina duplicados exactos y casi duplicados (MinHash), y textos que no están en español.
- Separa train, val y test: COAH estratificado por puntuación; COAR agrupado por restaurante, para que ninguno aparezca en dos particiones.

## Resultados del clasificador

F1 macro (negativo / neutral / positivo). Las cifras salen de los informes de [`reports/`](reports/), generados por los scripts.

| Modelo | Test limpio: COAH (269) | Test grande: AHR (11.414) | AHR, muestra pareada (2.000) | Otra web: SFU (50, acierto) |
|---|---|---|---|---|
| TF-IDF + regresión logística | 0,750 | — | — | — |
| mRoBERTa, *fine-tuning* (ensamble de 3 semillas) | **0,797** | **0,781** (IC 95 % 0,770–0,791) | 0,750 | 78 % |
| Qwen3.6 27B, *zero-shot* (sin entrenar) | 0,748 | — | **0,771** | **90 %** |

Lo que enseñó la evaluación ([baseline](reports/phase3_baseline.md), [mRoBERTa](reports/phase3_roberta.md), [realista](reports/phase3b_realista.md), [zero-shot](reports/phase3_zeroshot.md)):

- **El test limpio no bastaba.** En COAH gana el modelo entrenado. Con reseñas nuevas (AHR) o de otra web (SFU), el LLM sin entrenar le alcanza y le supera.
- **El error real es el triple del estimado.** Respondiendo solo cuando la confianza es ≥ 0,85 (umbral elegido en validación), el error de lo respondido es del 1,0 % en COAH y del 3,1 % en AHR, con un 74 % de reseñas respondidas.
- **La clase neutral (3★) es el límite.** Su F1 en AHR es 0,549: son reseñas con aspectos buenos y malos.
- **El LLM cede a la presión justo donde duda.** Con una nota falsa ("esta reseña es claramente positiva"), cambia su respuesta en 54 de 113 neutrales y casi nunca en reseñas claras.
- **Robustez de escritura:** erratas, minúsculas sin tildes o andaluz escrito cambian como mucho el 4,5 % de las predicciones; dejar solo el título, el 17 %.
- **Elegir entre opciones de entrenamiento es imposible con 269 reseñas de test.** Las diferencias entre usar o no los restaurantes (COAR) quedan dentro del ruido, y en la GPU la misma semilla no da el mismo resultado.

## Generación de respuestas

`qwen3.6:27b` en local (temperatura 0) extrae primero los aspectos de la reseña en JSON, cada uno con una cita literal, y después redacta la respuesta. El conjunto de desarrollo son 40 reseñas reales de COAH (8 por puntuación) y 8 casos adversariales **sintéticos**: premisa falsa, cebo de responsabilidad, petición de reembolso, inyección de instrucciones y dialecto andaluz. Informe: [`reports/phase4_generacion.md`](reports/phase4_generacion.md).

- **El análisis es fiable:** JSON válido en 48/48 casos y 238/238 citas presentes literalmente en la reseña.
- **Los detectores deterministas no ven los fallos que importan.** Con las cuatro versiones del prompt, ninguna regla marca promesas, culpa expresa, tuteo ni dialecto. Pero leyendo las respuestas aparece la **admisión implícita de culpa**: ante «se resbaló porque el suelo estaba mojado y no había ningún cartel», las versiones v1 y v4 responden dando por cierta la causa («debido a las condiciones del suelo», «la ausencia de señalización en el área mojada»). Ninguna expresión regular lo detecta: hace falta un juez.
- Los prompts están versionados (v1–v4). v3 y v4 salen de una **especificación única** ([`spec.py`](src/caso_uso_llm/spec.py)) de la que se generan también las reglas del juez, y un test impide que diverjan.

## Juez LLM: evaluar al evaluador

Juez `gemma4:12b` (otra familia que el generador, para evitar la autopreferencia) con una rúbrica de **8 criterios binarios** y una cita literal como evidencia de cada suspenso: aspecto concreto, sin promesas, sin admitir culpa, sin confirmar premisas, sin inventar, sin exagerar, registro (de usted, español estándar) y tono. Informes: [`reports/phase6_juez.md`](reports/phase6_juez.md) y [`reports/phase6_calibracion.md`](reports/phase6_calibracion.md).

| Prueba | Rúbrica v1 | v2 | v3 |
|---|---|---|---|
| *Canaries* (respuestas malas a propósito) suspendidos | 19/19 | 19/19 | 19/19 |
| Controles (respuestas correctas) sin ningún suspenso | 9/11 | 10/11 | 11/11 |
| Fallos reales del generador detectados (semillas del gold) | 2/5 | 2/5 | 1/5 |
| Calibración humana · kappa en «sin admitir culpa» | 0,22 | **0,70** | 0,62 |
| Calibración humana · kappa en «sin promesas» | 0,00 | 0,00 | 0,00 |

Lo que enseñó:

- **Aprobar todos los *canaries* no basta.** El juez suspende 19 de 19 respuestas malas escritas a mano, incluidas las «sutiles», pero solo detecta 1–2 de 5 fallos reales del generador: los *canaries* escritos a mano son más explícitos que los errores de verdad.
- **Relajar la rúbrica la empeora sin que se note.** La v3 añade fórmulas permitidas: deja limpios todos los controles, pero detecta menos fallos reales.
- **Sesgo de posición.** Al comparar dos respuestas en los dos órdenes, el juez solo es consistente en el 58–67 % de los pares y elige la primera opción unas dos veces más que la segunda. Por eso cada par se juzga en ambos órdenes y lo inconsistente cuenta como empate.
- **Calibración frente a una persona:** 24 respuestas de tres versiones del prompt, con identificadores opacos y etiquetadas a ciegas ([guía](evals/gold/guia_calibracion.md)). Con la rúbrica v2, el juez es fiable en «sin admitir culpa» (kappa 0,70), pero **no detecta la promesa encubierta** («esperamos poder resolver esta situación» ante una petición de reembolso). En los otros seis criterios la persona no suspende ninguna respuesta y la kappa no está definida.

> **Límites de la calibración.** 24 respuestas con 4 suspensos humanos no tienen potencia estadística: las kappas son un indicio, no una prueba. Además, las etiquetas humanas se corrigieron después de ver los resultados, a partir de los desacuerdos con un segundo anotador a ciegas (un LLM en un contexto limpio, sin acceso al juez ni a las etiquetas humanas). Las correcciones están anotadas fila a fila, y la primera pasada se conserva en [`calibracion_primera_pasada.csv`](evals/gold/calibracion_primera_pasada.csv).

Conclusión de diseño: el juez sirve como **prueba de regresión** ante cambios de prompt o modelo y para señalar frases sospechosas a quien revisa, no como permiso para publicar sin revisión humana. El siguiente paso es el RAG con fichas de hotel: con la ficha delante, «nos prometieron spa gratis» se puede contrastar con un dato y la *sycophancy* pasa a medirse de forma objetiva.

## Requisitos

- Python 3.12 y [uv](https://docs.astral.sh/uv/).
- Para el LLM: [Ollama](https://ollama.com) con `qwen3.6:27b-q4_K_M` (generador y referencia *zero-shot*) y `gemma4:12b-it-qat` (juez de las evaluaciones).
- Para entrenar: GPU con PyTorch. El proyecto usa una **AMD RX 7900 XTX con ROCm 7.2 en WSL2**; el grupo `train` instala torch para ROCm solo en Linux. Datos, baseline y tests funcionan en Windows sin GPU.

<details>
<summary>ROCm en WSL2 (lo que hizo falta para que torch viera la GPU)</summary>

- ROCm 7.2.4 con `amdgpu-install -y --usecase=rocm --no-dkms`. La opción `--usecase=wsl` ya no existe desde ROCm 7.2.1.
- [librocdxg](https://github.com/ROCm/librocdxg) compilado e instalado en `/opt/rocm`. Necesita las cabeceras del Windows SDK 10.0.26100, que pueden sacarse del paquete NuGet `Microsoft.Windows.SDK.CPP` sin instalar el SDK.
- En `~/.profile`: `HSA_ENABLE_DXG_DETECTION=1` y `ROCPROFILER_REGISTER_ENABLED=0`. Sin la segunda, el profiler que trae torch aborta porque busca `/sys/class/kfd`.
- Trabaja con un clon dentro del sistema de ficheros de Linux, no en `/mnt/c` o `/mnt/d`: un entorno de Linux sobre la carpeta de Windows rompe el `.venv` de Windows.
- Comprobación: `uv run just gpu`.

</details>

## Uso

```bash
uv sync                        # entorno (en Linux incluye torch ROCm)
uv run hf auth login           # una vez; acepta antes los términos de COAH y COAR en Hugging Face
uv run just data-download      # descarga los corpus a data/raw/
uv run just data               # pipeline de datos -> data/processed/ y reports/data_report.md
uv run just test               # tests (incluye que data/raw no se ha modificado)
uv run just baseline           # Fase 3: TF-IDF + regresión logística
uv run just train              # Fase 3: fine-tuning de mRoBERTa (WSL2 + ROCm; --save guarda pesos)
uv run just realista           # Fase 3: estrés, SFU, AHR y cobertura frente a error (WSL2)
uv run just zeroshot           # Fase 3: LLM zero-shot y prueba de presión (Ollama)
uv run just generar            # Fase 4: aspectos y respuestas (--prompt v1|v2|v3|v4)
uv run just juez               # Fase 6: canaries, controles, gold y comparación por pares
uv run just calibrar           # Fase 6: kappa del juez frente a las etiquetas humanas
uv run python scripts/acuerdo_anotadores.py  # acuerdo con el segundo anotador
uv run python scripts/calibracion_vista.py   # hoja HTML para etiquetar a ciegas
uv run just                    # lista todas las recetas
```

Los scripts muestran su progreso en consola y lo escriben también en `logs/<script>.log`.

## Estructura

```
src/caso_uso_llm/
  data/        descarga, lectura, normalización (reglas R1–R17), deduplicación y split
  classify/    baseline, fine-tuning, evaluación realista, zero-shot y métricas con IC
  generate/    prompts versionados, esquema JSON de aspectos y comprobaciones deterministas
  evals/       juez, rúbricas versionadas y calibración
  spec.py      especificación única de la que salen el prompt y la rúbrica
  paths.py     rutas absolutas · seed.py semillas · log.py progreso
evals/         casos adversariales, canaries, gold y etiquetas de calibración
scripts/       utilidades (hoja de etiquetado, acuerdo entre anotadores, GPU)
tests/         normalización, deduplicación, split, invariantes de los datos y coherencia prompt-rúbrica
reports/       informes generados por los scripts (no se editan a mano)
results/       resultados en JSON (incluidas las predicciones, para regenerar informes)
data/raw/      datos crudos inmutables, verificados por hash
legacy/        proyecto original, congelado
```

## Reproducibilidad

- Versiones fijadas en `uv.lock`, semillas fijas y datasets descargados por commit.
- El pipeline de datos es determinista: dos ejecuciones, en Windows o en WSL, producen los mismos ficheros byte a byte. El *fine-tuning* en GPU no lo es (los kernels de ROCm no son deterministas): por eso se informan varias semillas y su ensamble.
- Todas las cifras de este README salen de un informe de `reports/` generado por un script; cada informe indica el comando que lo regenera.

## Proyecto original

El código del primer intento está en [`legacy/`](legacy/) tal como se auditó (etiqueta `v1-original`). No se ejecuta ni se modifica; se conserva para comparar. Su dataset de partida (`Balanced_AHR.csv`, del corpus [Andalusian Hotels' Reviews](https://www.kaggle.com/datasets/chizhikchi/andalusian-hotels-reviews-unbalanced), CC BY-NC 4.0) está en `data/raw/`.
