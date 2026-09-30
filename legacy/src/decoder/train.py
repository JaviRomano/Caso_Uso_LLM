import torch
import os
import json
from transformers import GPT2Tokenizer, GPT2LMHeadModel, AdamW
from torch.optim.lr_scheduler import LinearLR

# Importar desde el mismo directorio
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dataset import get_dataloader

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

MODEL_NAME = "gpt2"
BATCH_SIZE = 8
EPOCHS = 10
LEARNING_RATE = 2e-5
MAX_LENGTH = 256
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ✅ DEFINIR DATASET_PATH
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "generation", "training_pairs_final.json")
# Alternativa más simple:
# DATASET_PATH = "data/generation/training_pairs_final.json"

MODEL_OUTPUT_DIR = "./models/decoder"

print(f"🖥️ Usando device: {DEVICE}")
print(f"📊 Configuración:")
print(f"   - Modelo: {MODEL_NAME}")
print(f"   - Batch size: {BATCH_SIZE}")
print(f"   - Epochs: {EPOCHS}")
print(f"   - Learning rate: {LEARNING_RATE}")

# ============================================================================
# CARGAR TOKENIZER Y MODELO
# ============================================================================

print("\n📥 Cargando GPT-2...")
tokenizer = GPT2Tokenizer.from_pretrained(MODEL_NAME)
tokenizer.pad_token = tokenizer.eos_token  # Usar EOS como PAD token
model = GPT2LMHeadModel.from_pretrained(MODEL_NAME).to(DEVICE)

print(f"✅ Modelo cargado: {model.config.model_type}")
print(f"   - Parámetros: {sum(p.numel() for p in model.parameters()):,}")

# ============================================================================
# PREPARAR DATASET
# ============================================================================

print(f"\n📊 Preparando dataset desde: {DATASET_PATH}")

# Verificar que el dataset existe
if not os.path.exists(DATASET_PATH):
    print(f"❌ ERROR: No existe {DATASET_PATH}")
    print("💡 Ejecuta primero: python src/decoder/generate_dataset.py")
    exit(1)

train_loader = get_dataloader(DATASET_PATH, tokenizer, batch_size=BATCH_SIZE, max_length=MAX_LENGTH)
print(f"✅ Dataset cargado: {len(train_loader.dataset)} ejemplos")

# ============================================================================
# CONFIGURAR OPTIMIZER
# ============================================================================

optimizer = AdamW(model.parameters(), lr=LEARNING_RATE)
scheduler = LinearLR(
    optimizer, 
    start_factor=1.0, 
    end_factor=0.1, 
    total_iters=len(train_loader) * EPOCHS
)

print(f"\n⚙️ Optimizer: AdamW")
print(f"   - Learning rate: {LEARNING_RATE}")
print(f"   - Scheduler: Linear decay")

# ============================================================================
# TRAINING LOOP
# ============================================================================

print(f"\n🚀 Iniciando entrenamiento...")
print(f"{'='*70}")

model.train()

for epoch in range(EPOCHS):
    total_loss = 0
    num_batches = 0
    
    for batch_idx, batch in enumerate(train_loader):
        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)
        labels = batch["labels"].to(DEVICE)
        
        # Forward pass
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )
        
        loss = outputs.loss
        total_loss += loss.item()
        num_batches += 1
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        
        # Log cada 10 batches
        if (batch_idx + 1) % 10 == 0:
            avg_loss = total_loss / num_batches
            print(f"Epoch {epoch+1}/{EPOCHS} | Batch {batch_idx+1}/{len(train_loader)} | Loss: {avg_loss:.4f}")
    
    # Log de época
    avg_epoch_loss = total_loss / len(train_loader)
    print(f"{'─'*70}")
    print(f"✅ Epoch {epoch+1}/{EPOCHS} completada | Avg Loss: {avg_epoch_loss:.4f}")
    print(f"{'─'*70}\n")

# ============================================================================
# GUARDAR MODELO
# ============================================================================

print(f"💾 Guardando modelo en {MODEL_OUTPUT_DIR}...")
os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)

model.save_pretrained(MODEL_OUTPUT_DIR)
tokenizer.save_pretrained(MODEL_OUTPUT_DIR)

print("✅ Modelo guardado correctamente")

# ============================================================================
# RESUMEN
# ============================================================================

print(f"\n{'='*70}")
print("✅ ENTRENAMIENTO COMPLETADO")
print(f"{'='*70}")
print(f"\n📊 Resumen:")
print(f"   - Épocas: {EPOCHS}")
print(f"   - Total batches: {len(train_loader)}")
print(f"   - Modelo guardado: {MODEL_OUTPUT_DIR}")
print(f"\n💡 Próximo paso: python src/decoder/evaluate.py")
print(f"{'='*70}")