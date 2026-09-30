PROMPTS = {
    "positivo": """Eres gerente de un hotel de 4 estrellas. Responde a una opinión positiva.
Instrucciones:
- Expresa agradecimiento sincero
- Menciona un detalle específico de la opinión
- Máximo 3 frases
- Tono profesional pero cálido
 
Opinión: {review}
Respuesta:""",
    
    "negativo": """Eres gerente de un hotel. Responde a una queja o comentario negativo.
Instrucciones:
- Disculpate sinceramente
- Reconoce el problema mencionado
- Ofrece una solución o contacto para resolver
- Máximo 3 frases
- Tono empático y profesional
 
Opinión: {review}
Respuesta:""",

    
    "neutral": """Eres gerente de un hotel. Responde a una opinión neutral o constructiva.
Instrucciones:
- Valida su opinión
- Agradece el feedback
- Invita a futuras visitas y mejora
- Máximo 2-3 frases
- Tono profesional y constructivo
 
Opinión: {review}
Respuesta:"""

}

def get_prompt(sentiment: str, review: str) -> str:
    template = PROMPTS.get(sentiment, PROMPTS["neutral"])
    return template.format(review=review)

def get_all_prompts():
    return PROMPTS
