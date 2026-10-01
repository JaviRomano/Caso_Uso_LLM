# Reseñas de hotel: sentimiento y respuesta con LLMs locales

Pipeline para una cadena hotelera que **clasifica el sentimiento** de una reseña (negativo, neutral, positivo) y **redacta una respuesta** profesional y personalizada. Todo se ejecuta en local, sobre una GPU AMD, sin enviar reseñas a servicios externos.

Es la reconstrucción de un primer intento (en [`legacy/`](legacy/), etiqueta `v1-original`) cuyas métricas no eran válidas. Ver [por qué se rehízo](#por-qué-se-rehízo).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1. Entorno | `uv` + lockfile, rutas absolutas, semillas, tests, GPU AMD con ROCm en WSL2 | Hecho |
| 2. Datos | Corpus de SINAI en español de España, normalización, deduplicación, split sin fuga | Hecho |
| 3. Clasificador | Baseline TF-IDF y *fine-tuning* de mRoBERTa; evaluación realista | En curso, rama [`fase-3-clasificador`](https://github.com/JaviRomano/Caso_Uso_LLM/tree/fase-3-clasificador) |
| 4. Generación | Respuesta con un LLM local, extracción de aspectos en JSON | Pendiente |
| 5. RAG y guardarraíles | Ficha del hotel y políticas; sin compensaciones ni datos inventados; cola de revisión humana | Pendiente |
| 6. Evaluación | Gold set, juez LLM calibrado y pruebas *anti-sycophancy* | Pendiente |

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

Licencia CC BY-NC-SA 4.0; uso no comercial. Los datos no se incluyen en el repositorio: se descargan con un commit fijado y en git solo se guarda su hash ([`data/raw/SHA256SUMS`](data/raw/SHA256SUMS)). COAH y COAR son *gated*: hay que aceptar sus términos en Hugging Face con tu cuenta.

El pipeline de datos ([`reports/data_report.md`](reports/data_report.md) recoge cada paso con sus cifras):

- Normaliza el texto sin borrar señal de sentimiento: conserva mayúsculas, signos y emojis.
- Enmascara datos personales: nombres con tratamiento o cargo ("la Srta. Ana", "el camarero Juan"), teléfonos, emails, URLs y números de habitación. Del autor no se guarda nada salvo una categoría de origen (España, hispanohablante, otro), que sirve para detectar reseñas traducidas automáticamente.
- Elimina duplicados exactos y casi duplicados (MinHash), y textos que no están en español.
- Separa train, val y test: COAH estratificado por puntuación; COAR agrupado por restaurante, para que ninguno aparezca en dos particiones.

## Requisitos

- Python 3.12 y [uv](https://docs.astral.sh/uv/).
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
uv run just                    # lista todas las recetas
```

Los scripts muestran su progreso en consola y lo escriben también en `logs/<script>.log`.

## Estructura

```
src/caso_uso_llm/
  data/        descarga, lectura, normalización (reglas R1–R17), deduplicación y split
  paths.py     rutas absolutas · seed.py semillas · log.py progreso
tests/         normalización, deduplicación, split e invariantes de los datos generados
reports/       informes generados por los scripts (no se editan a mano)
data/raw/      datos crudos inmutables, verificados por hash
legacy/        proyecto original, congelado
```

## Reproducibilidad

- Versiones fijadas en `uv.lock`, semillas fijas y datasets descargados por commit.
- El pipeline de datos es determinista: dos ejecuciones producen los mismos ficheros, byte a byte.
- Ninguna cifra de este README está escrita a mano: todas salen de un informe generado por un script.

## Proyecto original

El código del primer intento está en [`legacy/`](legacy/) tal como se auditó (etiqueta `v1-original`). No se ejecuta ni se modifica; se conserva para comparar. Su dataset de partida (`Balanced_AHR.csv`, del corpus [Andalusian Hotels' Reviews](https://www.kaggle.com/datasets/chizhikchi/andalusian-hotels-reviews-unbalanced), CC BY-NC 4.0) está en `data/raw/`.
