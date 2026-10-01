"""Esquemas de la Fase 4: análisis de la reseña (aspectos) y respuesta.

El esquema JSON se le pasa al LLM (salida restringida) y además se valida al recibirla.
Validar no basta para fiarse: que una cita tenga formato de cita no garantiza que exista en
la reseña. Eso lo comprueba `checks.quote_in_review`.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Polaridad(StrEnum):
    positiva = "positiva"
    negativa = "negativa"
    neutra = "neutra"


class Categoria(StrEnum):
    """Lista cerrada: así se pueden agregar aspectos entre reseñas y medir cobertura."""

    habitacion = "habitación"
    limpieza = "limpieza"
    personal = "personal y trato"
    ubicacion = "ubicación"
    desayuno = "desayuno y comida"
    ruido = "ruido"
    precio = "precio y relación calidad-precio"
    instalaciones = "instalaciones (piscina, spa, gimnasio, zonas comunes)"
    recepcion = "recepción, check-in y reservas"
    aparcamiento = "aparcamiento y accesos"
    wifi = "wifi y tecnología"
    otro = "otro"


class Aspecto(BaseModel):
    categoria: Categoria
    polaridad: Polaridad
    cita: str = Field(description="Fragmento copiado LITERALMENTE de la reseña (3 a 20 palabras)")


class Analisis(BaseModel):
    sentimiento: str = Field(pattern="^(negativo|neutral|positivo)$")
    aspectos: list[Aspecto] = Field(min_length=1, max_length=6)
    peticiones: list[str] = Field(
        default_factory=list,
        description="Lo que el cliente pide o exige explícitamente (reembolso, cambio...)",
    )


class Respuesta(BaseModel):
    texto: str
