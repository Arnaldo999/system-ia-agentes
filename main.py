import os
import requests
import time
import base64
from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI(title="System IA - Cerebro Central Autopiloto")

# =========================================================================
# 1. CARGA DE CREDENCIALES DESDE EASYPANEL (EL COFRE SECRETO)
# =========================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET")

META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
IG_BUSINESS_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_PERSON_ID = os.environ.get("LINKEDIN_PERSON_ID")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo_texto = genai.GenerativeModel('gemini-2.5-flash')
    # Modelo predeterminado para generar imagen según documentación de API
    modelo_imagen = "gemini-2.0-flash-preview-image-generation"

class DatosEntradaPost(BaseModel):
    cliente_id: str
    datos_marca: list

# =========================================================================
# FUNCIONES AUXILIARES DE PUBLICACIÓN Y SUBIDA DE IMÁGENES
# =========================================================================

def generar_imagen_gemini(prompt_visual: str):
    """Llama a Gemini 2.0 Flash Image Generation y devuelve el Base64 de la imagen."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_imagen}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "instances": [{"prompt": prompt_visual}],
        "parameters": {"sampleCount": 1} # Pide 1 imagen
    }
    # Gemini 2.0 usa una estructura particular. Intentaremos un request REST directo a Google:
    try:
        req_body = {
            "contents": [{ "parts": [{"text": prompt_visual}] }]
        }
        res = requests.post(url, json=req_body)
        data = res.json()
        # Buscar el base64 en la respuesta compleja de Gemini
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for p in parts:
            if "inlineData" in p:
                return p["inlineData"]["data"]
    except Exception as e:
        print("Error generando imagen Gemini:", str(e))
    return None

def subir_cloudinary(base64_img: str):
    """Sube la imagen en Base64 a Cloudinary y obtiene URL pública."""
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    data = {"file": f"data:image/png;base64,{base64_img}", "upload_preset": CLOUDINARY_UPLOAD_PRESET}
    res = requests.post(url, data=data)
    if res.status_code == 200:
        return res.json().get("secure_url")
    return None

def publicar_facebook(mensaje: str, url_imagen: str):
    url = f"https://graph.facebook.com/v22.0/{FACEBOOK_PAGE_ID}/photos"
    payload = {
        "url": url_imagen,
        "message": mensaje,
        "access_token": META_ACCESS_TOKEN
    }
    return requests.post(url, data=payload).json()

def publicar_instagram(mensaje: str, url_imagen: str):
    # Paso 1: Crear el contenedor
    url_container = f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ACCOUNT_ID}/media"
    payload_c = {
        "image_url": url_imagen,
        "caption": mensaje,
        "access_token": META_ACCESS_TOKEN
    }
    res_c = requests.post(url_container, data=payload_c).json()
    creation_id = res_c.get("id")
    
    if not creation_id:
        return {"error": "Fallo creando contenedor IG", "detalle": res_c}
    
    # Pausa de espera obligatoria por Meta para que procesen la foto internamente
    time.sleep(15) 
    
    # Paso 2: Publicar el contenedor
    url_publish = f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ACCOUNT_ID}/media_publish"
    payload_p = {"creation_id": creation_id, "access_token": META_ACCESS_TOKEN}
    return requests.post(url_publish, data=payload_p).json()

def publicar_linkedin(mensaje: str, base64_img: str):
    # LinkedIn requiere 3 pasos: InitUpload, Upload file (PUT), Create Post
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "LinkedIn-Version": "202501",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    # Paso 1
    init_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
    init_payload = {"initializeUploadRequest": {"owner": f"urn:li:person:{LINKEDIN_PERSON_ID}"}}
    res_init = requests.post(init_url, headers=headers, json=init_payload).json()
    upload_url = res_init.get("value", {}).get("uploadUrl")
    image_urn = res_init.get("value", {}).get("image")
    
    if not upload_url: return {"error": "Fallo Step 1 LI", "detalle": res_init}
    
    # Paso 2
    img_bytes = base64.b64decode(base64_img)
    headers_put = {"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}", "Content-Type": "image/png"}
    requests.put(upload_url, headers=headers_put, data=img_bytes)
    
    # Paso 3
    post_url = "https://api.linkedin.com/rest/posts"
    post_payload = {
        "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",
        "commentary": mensaje,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "content": {"media": {"id": image_urn}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }
    res_post = requests.post(post_url, headers=headers, json=post_payload)
    if res_post.status_code == 201:
        return {"id": res_post.headers.get("x-linkedin-id")}
    else:
        return {"error": "Fallo Step 3 LI", "detalle": res_post.text}


# =========================================================================
# LA RUTA MAESTRA: TODO EN UN SOLO CLICK
# =========================================================================
@app.post("/crear-post")
async def generar_post(entrada: DatosEntradaPost):
    if not GEMINI_API_KEY:
         return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en Easypanel."}

    # 1. BUSCAR CLIENTE
    cliente_data = None
    for item in entrada.datos_marca:
        if item.get("json", {}).get("ID Cliente") == entrada.cliente_id:
            cliente_data = item.get("json")
            break
            
    if not cliente_data:
        return {"status": "error", "mensaje": f"No encuentro el cliente {entrada.cliente_id}"}

    industria = cliente_data.get("Industria", "General")
    publico = cliente_data.get("Público Objetivo", "Público")
    tono = cliente_data.get("Tono de Voz", "Profesional")
    reglas = cliente_data.get("Reglas Estrictas (Lo que NO debe hacer)", "Ninguna")
    estilo_visual = cliente_data.get("Estilo Visual (Prompt DALL-E/Gemini)", "clean flat design no text")

    # 2. PENSAR REPORTE ESCRITO (Copys)
    prompt_texto = f"""
    Eres Copywriter. INDUSTRIA: {industria}. PÚBLICO: {publico}.
    TONO: {tono}. PROHIBIDO: {reglas}
    TEMA: Automatización e IA. Escribe 3 versiones separadas por |||
    1. Instagram (balas, gancho, emojis)
    |||
    2. LinkedIn (analítico, profesional)
    |||
    3. Facebook (storytelling, pregunta final)
    """
    try:
        res_gemini = modelo_texto.generate_content(prompt_texto)
        textos = res_gemini.text.split("|||")
        post_ig = textos[0].strip()
        post_li = textos[1].strip()
        post_fb = textos[2].strip()
    except Exception as e:
        return {"status": "error", "mensaje": f"Error redactando: {str(e)}"}

    # 3. PENSAR Y PINTAR (IMAGEN)
    prompt_img_final = f"{estilo_visual}. Elemento principal representativo de: Inteligencia Artificial. NO LETTERS. NO TEXT."
    base64_img = generar_imagen_gemini(prompt_img_final)
    
    if not base64_img:
        return {"status": "error", "mensaje": "Gemini no generó la imagen base64."}
        
    # 4. SUBIR A LA NUBE ETERNA (CLOUDINARY)
    url_publica = subir_cloudinary(base64_img)
    if not url_publica:
        return {"status": "error", "mensaje": "Fallo al subir a Cloudinary."}

    # 5. DESPLEGAR EL ARMAMENTO (PUBLICAR EN REDES)
    resultados_publicacion = {}
    
    # Facebook
    if META_ACCESS_TOKEN and FACEBOOK_PAGE_ID:
        res_fb = publicar_facebook(post_fb, url_publica)
        resultados_publicacion["Facebook"] = "Exito" if "id" in res_fb else res_fb
        
    # Instagram
    if META_ACCESS_TOKEN and IG_BUSINESS_ACCOUNT_ID:
        res_ig = publicar_instagram(post_ig, url_publica)
        resultados_publicacion["Instagram"] = "Exito" if "id" in res_ig else res_ig
        
    # LinkedIn
    if LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID:
        res_li = publicar_linkedin(post_li, base64_img) # LI API prefiere el binario a la URL
        resultados_publicacion["LinkedIn"] = "Exito" if "id" in res_li else res_li

    # 6. REPORTE FINAL A N8N
    return {
        "status": "success",
        "workflow": "AUTOPILOTO TOTAL INICIADO",
        "imagen_generada": url_publica,
        "resultados_redes": resultados_publicacion,
        "textos": {
            "ig": post_ig[:50] + "...",
            "fb": post_fb[:50] + "...",
            "li": post_li[:50] + "..."
        }
    }

@app.get("/")
def verificar_estado():
    return {"status": "online", "mensaje": "Cerebro Central Autopiloto funcionando 🚀"}
