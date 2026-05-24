import sys
import os
import torch
from transformers import BertTokenizer, BertForSequenceClassification, GPT2Tokenizer, GPT2LMHeadModel

class SimpleDecoder:
    """Generador simple de respuestas"""
    
    def __init__(self, model_path: str = "models/decoder"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = GPT2Tokenizer.from_pretrained(model_path)
        self.model = GPT2LMHeadModel.from_pretrained(model_path).to(self.device)
        self.model.eval()
    
    def get_prompt(self, sentiment: str, review: str) -> str:
        prompts = {
            "positivo": f"Eres gerente hotelero. Responde positivamente a: {review}\nRespuesta:",
            "negativo": f"Eres gerente hotelero. Responde a esta queja: {review}\nRespuesta:",
            "neutral": f"Eres gerente hotelero. Responde a: {review}\nRespuesta:"
        }
        return prompts.get(sentiment, prompts["neutral"])
    
    def generate(self, review: str, sentiment: str) -> str:
        prompt = self.get_prompt(sentiment, review)
        input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            output = self.model.generate(
                input_ids,
                max_length=80,
                temperature=0.7,
                top_p=0.95,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        response = self.tokenizer.decode(output[0], skip_special_tokens=True)
        response = response.replace(prompt, "").strip()
        return response

class SimplePipeline:
    """Pipeline simple encoder + decoder"""
    
    def __init__(self):
        print("📥 Cargando Encoder (BERT)...")
        self.encoder_tokenizer = BertTokenizer.from_pretrained("models/encoder")
        self.encoder_model = BertForSequenceClassification.from_pretrained("models/encoder")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.encoder_model = self.encoder_model.to(self.device)
        self.encoder_model.eval()
        print("✅ Encoder cargado\n")
        
        print("📥 Cargando Decoder (GPT-2)...")
        self.decoder = SimpleDecoder()
        print("✅ Decoder cargado\n")
        
        self.sentiment_labels = {0: "negativo", 1: "neutral", 2: "positivo"}
    
    def predict(self, review: str) -> dict:
        # Clasificar
        print("🔍 Clasificando sentimiento...")
        inputs = self.encoder_tokenizer(review, return_tensors="pt", truncation=True, max_length=128)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.encoder_model(**inputs)
            logits = outputs.logits
        
        sentiment_idx = torch.argmax(logits, dim=-1).item()
        sentiment = self.sentiment_labels.get(sentiment_idx, "neutral")
        confidence = torch.nn.functional.softmax(logits, dim=-1)[0][sentiment_idx].item()
        print(f"✓ Sentimiento: {sentiment} ({confidence:.2%})\n")
        
        # Generar
        print("✍️  Generando respuesta...")
        response = self.decoder.generate(review, sentiment)
        print(f"✓ Respuesta generada\n")
        
        return {
            "review": review,
            "sentiment": sentiment,
            "confidence": round(confidence, 4),
            "response": response
        }

if __name__ == "__main__":
    print("\n" + "="*100)
    print("PIPELINE END-TO-END")
    print("="*100 + "\n")
    
    test_reviews = [
        "Habitación hermosa, vistas increíbles, personal muy atento.",
        "Ruido toda la noche, servicio lentísimo, fue horrible.",
        "Hotel normal, nada especial, precios altos."
    ]
    
    try:
        pipeline = SimplePipeline()
        
        for i, review in enumerate(test_reviews, 1):
            print("="*100)
            print(f"CASO {i}")
            print("="*100 + "\n")
            
            result = pipeline.predict(review)
            
            print(f"📝 Opinión: \"{result['review']}\"")
            print(f"🎯 Sentimiento: {result['sentiment']} (confianza: {result['confidence']*100:.1f}%)")
            print(f"📤 Respuesta: \"{result['response']}\"\n")
        
        print("="*100)
        print("✅ PIPELINE COMPLETADO")
        print("="*100 + "\n")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)