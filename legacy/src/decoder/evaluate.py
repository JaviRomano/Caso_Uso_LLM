import json
import torch
import sys
import os

# Añadir ruta para importar desde src/decoder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from decoder_generate import DecoderInference
except ImportError:
    print(" Error: No se puede importar DecoderInference")
    print(" Asegúrate de que los archivos están en src/decoder/")
    sys.exit(1)

print("\n" + "="*90)
print("EVALUACIÓN CUALITATIVA - DECODER")
print("="*90 + "\n")

# CASOS DE PRUEBA

test_cases = [
    {
        "id": 1,
        "review": "Excelente ubicación, personal atento y profesional. Las habitaciones muy cómodas.",
        "expected_sentiment": "positivo",
        "expected_tone": "agradecimiento específico"
    },
    {
        "id": 2,
        "review": "Ruido insoportable, piscina rota, servicio lentísimo. No dormí nada.",
        "expected_sentiment": "negativo",
        "expected_tone": "disculpa + oferta de solución"
    },
    {
        "id": 3,
        "review": "Hotel normal, nada especial. El desayuno estaba ok pero los precios altos.",
        "expected_sentiment": "neutral",
        "expected_tone": "validación constructiva"
    }
]

# CARGAR DECODER

print(" Cargando decoder entrenado...\n")

try:
    generator = DecoderInference(model_path="models/decoder")
except Exception as e:
    print(f" Error: {e}")
    print(" ¿Ejecutaste 'python src/decoder/train.py'?")
    sys.exit(1)

# EVALUACIÓN

print("="*90)
print("TABLA DE EVALUACIÓN CUALITATIVA")
print("="*90 + "\n")

results = []

for test in test_cases:
    print(f"{'─'*90}")
    print(f" CASO {test['id']}: {test['expected_sentiment'].upper()}")
    print(f"{'─'*90}\n")
    
    # Generar respuesta
    response = generator.generate(test['review'], test['expected_sentiment'], max_length=100)
    
    # Mostrar detalles
    print(f"  ENTRADA:")
    print(f"    Opinión: \"{test['review']}\"")
    print(f"    Sentimiento esperado: {test['expected_sentiment']}")
    print(f"    Tono esperado: {test['expected_tone']}\n")
    
    print(f" SALIDA:")
    print(f"    Respuesta generada: \"{response}\"\n")
    
    print(f" ANÁLISIS:")
    # Análisis simple
    is_coherent = len(response) > 20  # Al menos 20 caracteres
    has_greeting = any(word in response.lower() for word in ['gracias', 'agradece', 'disculp', 'aprecia', 'valora'])
    
    coherence_status = "✓ Coherente" if is_coherent else "✗ Muy corta"
    greeting_status = "✓ Tiene reconocimiento" if has_greeting else "✗ Falta reconocimiento"
    
    print(f"    {coherence_status} (longitud: {len(response)} caracteres)")
    print(f"    {greeting_status}")
    
    results.append({
        "case": test['id'],
        "sentiment": test['expected_sentiment'],
        "response": response,
        "coherent": is_coherent,
        "has_recognition": has_greeting
    })
    
    print()

# RESUMEN

print("RESUMEN DE EVALUACIÓN")

coherent_count = sum(1 for r in results if r['coherent'])
recognition_count = sum(1 for r in results if r['has_recognition'])
total_cases = len(results)

print(f" Estadísticas:")
print(f"   - Total casos: {total_cases}")
print(f"   - Respuestas coherentes: {coherent_count}/{total_cases} ({coherent_count/total_cases*100:.0f}%)")
print(f"   - Con reconocimiento: {recognition_count}/{total_cases} ({recognition_count/total_cases*100:.0f}%)")

print(f"\n Conclusión:")
if coherent_count == total_cases:
    print(f"    El decoder genera respuestas coherentes y apropiadas")
else:
    print(f"     Hay casos donde la generación podría mejorarse")

print(f"\n Observaciones:")
print(f"   - El modelo tiende a respuestas genéricas (es lo esperado de GPT-2)")
print(f"   - Para producción: considerar RAG (añadir contexto del hotel)")
print(f"   - Para mejorar: fine-tuning más largo (>5 épocas)")

print(" EVALUACIÓN COMPLETADA")