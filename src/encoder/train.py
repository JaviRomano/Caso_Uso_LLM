import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, confusion_matrix, classification_report
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from torch.utils.data import Dataset
import torch
import numpy as np

# Cargar el dataset
df = pd.read_csv("data/Balanced_AHR.csv")

# Ver estructura del CSV
print("Columnas disponibles:", df.columns.tolist())
print(f"Primeras filas:\n{df.head()}")

# Seleccionar columnas
if 'rating' in df.columns:
    df = df[["review_text", "rating"]].dropna()
    rating_col = "rating"
else:
    df = df[["review_text", "label"]].dropna()
    rating_col = "label"

print(f"\nValores únicos en {rating_col}: {sorted(df[rating_col].unique())}")

# Reclasificar a 3 clases (basado en rating 1-5)
def remap_3class(val):
    val = int(val)
    if val <= 2:
        return 0  # NEGATIVO
    elif val == 3:
        return 1  # NEUTRAL
    else:  # 4-5
        return 2  # POSITIVO

df["label"] = df[rating_col].apply(remap_3class)

print(f"\nDistribución después de remapeo:")
print(df["label"].value_counts().sort_index())
print(f"Total reseñas: {len(df)}")

# Quitar columna rating si existe
if "rating" in df.columns:
    df = df.drop(columns=["rating"])

# EDA
df["longitud"] = df["review_text"].apply(lambda x: len(x.split()))
print(f"\nLongitud media: {df['longitud'].mean():.0f} palabras")
print(f"Longitud máxima: {df['longitud'].max()} palabras")

# ============================================================================
# GRÁFICA 1: Distribución de clases (3 clases con porcentajes)
# ============================================================================
plt.figure(figsize=(10, 6))
class_counts = df["label"].value_counts().sort_index()
class_names = ["Negativo", "Neutral", "Positivo"]
colors = ["#d62728", "#ff7f0e", "#2ca02c"]  # Rojo, Naranja, Verde

# Asegurarse de que hay 3 valores
counts_list = [class_counts.get(i, 0) for i in range(3)]

bars = plt.bar(class_names, counts_list, color=colors, edgecolor='black', linewidth=2, alpha=0.8)

# Añadir valores en las barras
for bar, count in zip(bars, counts_list):
    height = bar.get_height()
    if height > 0:
        percentage = (count / len(df)) * 100
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(count)}\n({percentage:.1f}%)',
                ha='center', va='bottom', fontweight='bold', fontsize=11)

plt.title("Distribución de Clases - Dataset de Opiniones", fontsize=14, fontweight='bold')
plt.ylabel("Cantidad de Opiniones", fontsize=12)
plt.xlabel("Sentimiento", fontsize=12)
plt.grid(axis='y', alpha=0.3, linestyle='--')
plt.ylim(0, max(counts_list) * 1.15)
plt.tight_layout()
plt.savefig("data/distribucion_clases.png", dpi=300, bbox_inches='tight')
print("\n✅ Gráfica distribucion_clases.png guardada")
plt.close()

# ============================================================================
# GRÁFICA 2: Longitud de textos
# ============================================================================
plt.figure(figsize=(10, 6))
plt.hist(df["longitud"], bins=50, color="steelblue", edgecolor='black', alpha=0.7)
plt.axvline(df["longitud"].mean(), color='red', linestyle='--', linewidth=2, label=f'Media: {df["longitud"].mean():.0f}')
plt.axvline(df["longitud"].median(), color='green', linestyle='--', linewidth=2, label=f'Mediana: {df["longitud"].median():.0f}')
plt.title("Distribución de Longitud de Reseñas", fontsize=14, fontweight='bold')
plt.xlabel("Número de Palabras", fontsize=12)
plt.ylabel("Frecuencia", fontsize=12)
plt.legend(fontsize=11)
plt.grid(axis='y', alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig("data/longitud_textos.png", dpi=300, bbox_inches='tight')
print("✅ Gráfica longitud_textos.png guardada")
plt.close()

# Split
train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
print(f"\n📊 Train: {len(train_df)}, Test: {len(test_df)}")

# Tokenizer
tokenizer = BertTokenizer.from_pretrained("dccuchile/bert-base-spanish-wwm-uncased")

# Dataset personalizado
class ReviewDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=128):
        self.encodings = tokenizer(texts.tolist(), padding=True, truncation=True, max_length=max_length, return_tensors='pt')
        self.labels = torch.tensor(labels.tolist())
    
    def __getitem__(self, idx):
        return {
            'input_ids': self.encodings['input_ids'][idx],
            'attention_mask': self.encodings['attention_mask'][idx],
            'labels': self.labels[idx]
        }
    
    def __len__(self):
        return len(self.labels)

train_dataset = ReviewDataset(train_df["review_text"].values, train_df["label"].values, tokenizer)
test_dataset = ReviewDataset(test_df["review_text"].values, test_df["label"].values, tokenizer)

print("✅ Datos tokenizados")

# Modelo
model = BertForSequenceClassification.from_pretrained(
    "dccuchile/bert-base-spanish-wwm-uncased",
    num_labels=3
)

# Training
training_args = TrainingArguments(
    output_dir='./models/encoder',
    num_train_epochs=3,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    logging_steps=100,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    fp16=False,  # Desabilitar fp16 si tienes problemas
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    compute_metrics=lambda p: {'f1': f1_score(p.predictions.argmax(-1), p.label_ids, average='macro')}
)

print("\n🚀 Iniciando entrenamiento...")
trainer.train()

# Evaluación
print("\n📊 Evaluando en test set...")
predictions = trainer.predict(test_dataset)
y_true = test_df["label"].values
y_pred = predictions.predictions.argmax(-1)

f1 = f1_score(y_true, y_pred, average='macro')
cm = confusion_matrix(y_true, y_pred)
report = classification_report(y_true, y_pred, target_names=['Negativo', 'Neutral', 'Positivo'])

print(f"\n{'='*60}")
print(f"F1-score (macro): {f1:.4f}")
print(f"{'='*60}")
print(f"\nMatriz de confusión:\n{cm}")
print(f"\nReporte de clasificación:\n{report}")

# ============================================================================
# GRÁFICA 3: Matriz de confusión
# ============================================================================
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Negativo', 'Neutral', 'Positivo'],
            yticklabels=['Negativo', 'Neutral', 'Positivo'],
            cbar_kws={'label': 'Cantidad'}, 
            annot_kws={'fontsize': 12, 'fontweight': 'bold'})
plt.title('Matriz de Confusión - Encoder BERT', fontsize=14, fontweight='bold')
plt.ylabel('Etiqueta Real', fontsize=12)
plt.xlabel('Predicción', fontsize=12)
plt.tight_layout()
plt.savefig('data/confusion_matrix.png', dpi=300, bbox_inches='tight')
plt.close()

print("\n✅ Matriz de confusión guardada en data/confusion_matrix.png")

# Guardar modelo
model.save_pretrained('./models/encoder')
tokenizer.save_pretrained('./models/encoder')
print("✅ Modelo y tokenizer guardados en models/encoder/")

print(f"\n{'='*60}")
print("✅ ENTRENAMIENTO COMPLETADO")
print(f"{'='*60}")