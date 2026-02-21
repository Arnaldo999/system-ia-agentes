import os
import requests
from fastapi import FastAPI, Request
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI(title="System IA - Cerebro Central")

# Configuración de Gemini desde Variables de Entorno
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Usamos el modelo rápido y económico para texto
    modelo_texto = genai.GenerativeModel('gemini-2.5-flash')

# Modelo de datos que esperamos recibir de n8n
class DatosEntradaPost(BaseModel):
    cliente_id: str
    datos_marca: list

# La ruta principal que usará el Agente de Redes Sociales
@app.post("/crear-post")
async def generar_post(entrada: DatosEntradaPost):
    if not GEMINI_API_KEY:
         return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en Easypanel."}

    # 1. Buscar los datos del cliente en el JSON que manda Airtable a través de n8n
    cliente_data = None
    for item in entrada.datos_marca:
        # n8n suele mandar arreglos bajo la llave "json"
        if item.get("json", {}).get("ID Cliente") == entrada.cliente_id:
            cliente_data = item.get("json")
            break
            
    if not cliente_data:
        return {"status": "error", "mensaje": f"No se encontró el cliente '{entrada.cliente_id}' en los datos proporcionados."}

    # 2. Extraer el Brandbook dinámico
    industria = cliente_data.get("Industria", "General")
    publico = cliente_data.get("Público Objetivo", "Público general")
    tono = cliente_data.get("Tono de Voz", "Profesional")
    reglas = cliente_data.get("Reglas Estrictas (Lo que NO debe hacer)", "Ninguna")

    # 3. Construir el Mega-Prompt
    prompt = f"""
    Eres el Estratega y Copywriter Experto en Redes Sociales.
    
    CONTEXTO DE LA MARCA PARA LA QUE ESCRIBES HOY:
    - Industria: {industria}
    - Público Objetivo: {publico}
    - Tono de Voz: {tono}
    - LÍMITES ESTRICTOS (NO HACER): {reglas}
    
    TAREA:
    Escribe contenido de alto valor sobre cómo la IA y la automatización ahorran tiempo.
    Crea 3 versiones diferentes para 3 redes sociales.
    
    INSTRUCCIONES DE FORMATO OBLIGATORIAS:
    Separa cada post EXACTAMENTE con este símbolo: |||
    NO uses markdown de código, devuelve solo texto puro.
    
    1. Para Instagram: Usa balas (viñetas), un gancho fuerte, 3-4 emojis.
    |||
    2. Para LinkedIn: Más analítico, estructura de 'apertura, nudo, desenlace', profesional, max 1 emoji.
    |||
    3. Para Facebook: Formato storytelling cercano, como hablando con un amigo emprendedor, invita a comentar.
    """
    
    # 4. Llamar a la IA y parsear los resultados
    try:
        respuesta = modelo_texto.generate_content(prompt)
        textos = respuesta.text.split("|||")
        
        post_ig = textos[0].strip() if len(textos) > 0 else "Error generando IG"
        post_li = textos[1].strip() if len(textos) > 1 else "Error generando LI"
        post_fb = textos[2].strip() if len(textos) > 2 else "Error generando FB"
        
        # 5. Devolver a n8n el objeto limpio
        return {
            "status": "success",
            "resultados": {
                "instagram": post_ig,
                "linkedin": post_li,
                "facebook": post_fb
            }
        }
    except Exception as e:
        return {"status": "error", "mensaje": f"Error comunicándose con Gemini: {str(e)}"}

# Una ruta de prueba para saber que el servidor está prendido
@app.get("/")
def verificar_estado():
    return {"status": "online", "mensaje": "Cerebro Central de System IA funcionando 🚀"}
