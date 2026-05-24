import pandas as pd
import json
import random
import os

print("🔨 Generando dataset MEJORADO (300 pares) para decoder...\n")

# ============================================================================
# CARGAR DATOS ORIGINALES
# ============================================================================

df = pd.read_csv("data/Balanced_AHR.csv")
df = df[["review_text", "label"]].dropna()

# Reclasificar a 3 clases
def remap_3class(label_val):
    if label_val == 0:
        return 0  # NEGATIVO
    elif label_val == 3:
        return 1  # NEUTRAL
    else:
        return 2  # POSITIVO

df["sentiment"] = df["label"].apply(remap_3class)

print(f"✅ Dataset cargado: {len(df)} opiniones\n")

# ============================================================================
# SELECCIONAR MÁS MUESTRAS (100 por clase en lugar de 50)
# ============================================================================

samples_per_class = 100

neg_reviews = df[df["sentiment"] == 0]["review_text"].sample(
    min(samples_per_class, len(df[df["sentiment"] == 0])), 
    random_state=42
).tolist()

neu_reviews = df[df["sentiment"] == 1]["review_text"].sample(
    min(samples_per_class, len(df[df["sentiment"] == 1])), 
    random_state=42
).tolist()

pos_reviews = df[df["sentiment"] == 2]["review_text"].sample(
    min(samples_per_class, len(df[df["sentiment"] == 2])), 
    random_state=42
).tolist()

print(f"📊 Muestras seleccionadas:")
print(f"   - Negativas: {len(neg_reviews)}")
print(f"   - Neutrales: {len(neu_reviews)}")
print(f"   - Positivas: {len(pos_reviews)}\n")

# ============================================================================
# TEMPLATES MEJORADOS (MÁS ESPECÍFICOS)
# ============================================================================

# POSITIVAS - Más variadas y específicas
positive_responses = [
    "¡Gracias por tu excelente valoración! Nos alegra enormemente que hayas disfrutado de nuestro hotel.",
    "Apreciamos sinceramente tu feedback positivo. ¡Esperamos poder servirte nuevamente!",
    "¡Muchas gracias! Tu comentario nos motiva a seguir mejorando.",
    "Nos alegra que hayas tenido una experiencia maravillosa. Tu satisfacción es nuestra prioridad.",
    "¡Gracias por elegirnos! Esperamos verte pronto de nuevo.",
    "Agradecemos tu amabilidad al compartir tu experiencia positiva con nosotros.",
    "¡Excelente! Comentarios como el tuyo nos inspiran a mantener nuestros altos estándares.",
    "Gracias por tu confianza y por recomendarnos. Fue un placer recibirte.",
    "¡Qué alegría saber que todo fue de tu agrado! Vuelve pronto.",
    "Tu opinión positiva es muy valiosa para nosotros. ¡Hasta pronto!",
]

# NEGATIVAS - Más empáticas y con soluciones
negative_responses = [
    "Lamentamos profundamente tu experiencia negativa. Nos encantaría compensarte. ¿Podemos contactarte?",
    "Nos disculpamos sinceramente por los problemas. Tu feedback es valioso. ¿Nos permites contactarte?",
    "Sentimos que no hayas tenido una buena experiencia. Haremos lo posible por remediar esto.",
    "Disculpa por los inconvenientes. Nos gustaría resolver esto directamente contigo. ¿Podemos hablar?",
    "Agradecemos tu honestidad. Tomaremos medidas para mejorar. ¿Te contactamos?",
    "Lamento mucho que tu estancia no fue satisfactoria. Nos gustaría hacer las cosas bien.",
    "Tu comentario negativo nos preocupa. Queremos entender qué salió mal y corregirlo.",
    "Disculpas por los problemas mencionados. Nos comprometeremos a mejorar.",
    "Sentimos no haber cumplido tus expectativas. Por favor, permítenos contactarte.",
    "Tu feedback negativo es importante para nosotros. Trabajaremos en ello.",
]

# NEUTRALES - Constructivas e invitadoras
neutral_responses = [
    "Apreciamos tu feedback constructivo. Continuaremos mejorando en los puntos que mencionas.",
    "Gracias por tu opinión. Esperamos poder superar tus expectativas próximamente.",
    "Valuamos tu feedback. ¡Vuelve pronto y disfruta de nuestras mejoras!",
    "Agradecemos tus comentarios. Trabajamos constantemente para mejorar la experiencia.",
    "Tu opinión nos ayuda a crecer. Esperamos poder sorprenderte en una próxima visita.",
    "Gracias por compartir tus observaciones. Tomaremos nota para mejorar.",
    "Apreciamos tu honestidad. Continuamos trabajando en ofrecer lo mejor.",
    "Tu feedback es valioso. Esperamos una próxima oportunidad para mejorar.",
    "Gracias por tu opinión equilibrada. Nos motiva a seguir mejorando.",
    "Valoramos tu experiencia neutral. Siempre hay espacio para mejorar.",
]

print("✅ Templates mejorados cargados\n")

# ============================================================================
# CREAR DATASET MEJORADO
# ============================================================================

dataset = []

# Positivas
for i, review in enumerate(pos_reviews):
    dataset.append({
        "review_id": f"pos_{i}",
        "review_text": review,
        "sentiment": "positivo",
        "response": random.choice(positive_responses)
    })

# Negativas
for i, review in enumerate(neg_reviews):
    dataset.append({
        "review_id": f"neg_{i}",
        "review_text": review,
        "sentiment": "negativo",
        "response": random.choice(negative_responses)
    })

# Neutrales
for i, review in enumerate(neu_reviews):
    dataset.append({
        "review_id": f"neu_{i}",
        "review_text": review,
        "sentiment": "neutral",
        "response": random.choice(neutral_responses)
    })

print(f"📦 Dataset mejorado: {len(dataset)} pares opinion-respuesta\n")

# ============================================================================
# GUARDAR
# ============================================================================

output_dir = "data/generation"
os.makedirs(output_dir, exist_ok=True)

output_path = os.path.join(output_dir, "training_pairs_final.json")

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(dataset, f, ensure_ascii=False, indent=2)

print(f"✅ Dataset mejorado guardado: {output_path}\n")

# ============================================================================
# EJEMPLO
# ============================================================================

print("📋 Ejemplo de datos:\n")
for item in random.sample(dataset, 3):
    print(f"- {item['sentiment'].upper()}: {item['response'][:60]}...")

print(f"\n{'='*70}")
print("✅ DATASET MEJORADO LISTO")
print(f"{'='*70}")
print(f"\n💡 Próximos pasos:")
print(f"   1. python src/decoder/generate_dataset.py  (generar)")
print(f"   2. python src/decoder/train.py             (entrenar - 2-3h)")
print(f"   3. python pipeline_simple.py               (probar)")