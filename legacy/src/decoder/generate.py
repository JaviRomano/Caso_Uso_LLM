import torch
from transformers import GPT2Tokenizer, GPT2LMHeadModel

class DecoderInference:
    """Generador mejorado de respuestas con prompts más claros"""
    
    def __init__(self, model_path: str = "models/decoder"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = GPT2Tokenizer.from_pretrained(model_path)
        self.model = GPT2LMHeadModel.from_pretrained(model_path).to(self.device)
        self.model.eval()
    
    def get_prompt(self, sentiment: str, review: str) -> str:
        """Prompts mejorados y más estructurados"""
        
        if sentiment == "positivo":
            return f"""Responde como gerente hotelero profesional. La opinión es POSITIVA.

OPINIÓN DEL CLIENTE:
{review}

INSTRUCCIONES:
- Expresa gratitud sincera y auténtica
- Menciona un aspecto específico que mencionó el cliente
- Máximo 2-3 frases
- Tono cálido y profesional

TU RESPUESTA:
Gracias """
        
        elif sentiment == "negativo":
            return f"""Responde como gerente hotelero profesional. La opinión es NEGATIVA/QUEJA.

OPINIÓN DEL CLIENTE:
{review}

INSTRUCCIONES:
- Disculpate sincera y claramente
- Reconoce el problema específico mencionado
- Ofrece una solución o contacto para resolver
- Máximo 2-3 frases
- Tono empático y profesional

TU RESPUESTA:
Nos disculpamos """
        
        else:  # neutral
            return f"""Responde como gerente hotelero profesional. La opinión es NEUTRAL/CONSTRUCTIVA.

OPINIÓN DEL CLIENTE:
{review}

INSTRUCCIONES:
- Valida su opinión constructivamente
- Agradece el feedback específico
- Invita a una próxima visita
- Máximo 2-3 frases
- Tono profesional y constructivo

TU RESPUESTA:
Apreciamos """
    
    def generate(self, review: str, sentiment: str, max_length: int = 100) -> str:
        """Genera respuesta con prompt mejorado"""
        
        prompt = self.get_prompt(sentiment, review)
        input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            output = self.model.generate(
                input_ids,
                max_length=max_length,
                temperature=0.6,  # Menos aleatorio
                top_p=0.9,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                num_return_sequences=1
            )
        
        response = self.tokenizer.decode(output[0], skip_special_tokens=True)
        response = response.replace(prompt, "").strip()
        
        # Limpiar
        response = response.replace("\n", " ").strip()
        
        # Si está vacío, retornar default
        if len(response) < 10:
            defaults = {
                "positivo": "Agradecemos sinceramente tu comentario positivo. ¡Esperamos verte pronto!",
                "negativo": "Nos disculpamos por tu experiencia. ¿Podemos contactarte para mejorar?",
                "neutral": "Apreciamos tu feedback. Continuaremos mejorando."
            }
            response = defaults.get(sentiment, "Gracias por tu opinión.")
        
        return response