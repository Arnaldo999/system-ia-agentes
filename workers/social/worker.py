import os
import re
import json
import time
import requests as req
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/social", tags=["Social Media"])

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_IMG_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent"

# ── Publicación en redes ──────────────────────────────────────────────────────
META_ACCESS_TOKEN      = os.environ.get("META_ACCESS_TOKEN", "")
IG_BUSINESS_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID       = os.environ.get("FACEBOOK_PAGE_ID", "")
LINKEDIN_ACCESS_TOKEN  = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_ID     = os.environ.get("LINKEDIN_PERSON_ID", "")
CLOUDINARY_CLOUD_NAME  = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "")
EVOLUTION_URL          = os.environ.get("EVOLUTION_URL", "")
EVOLUTION_INSTANCE     = os.environ.get("EVOLUTION_INSTANCE", "")
EVOLUTION_API_KEY      = os.environ.get("EVOLUTION_API_KEY", "")
WHATSAPP_NOTIFY_NUMBER = os.environ.get("WHATSAPP_NOTIFY_NUMBER", "")


class DatosCrearPost(BaseModel):
    cliente_id: str
    datos_marca: list  # Array de items de Airtable enviados por n8n


class DatosGenerarImagen(BaseModel):
    prompt: str
    estilo: Optional[str] = "fotografico, profesional, moderno, sin texto"
    max_intentos: Optional[int] = 4
    espera_segundos: Optional[int] = 25


class DatosSeleccionarTema(BaseModel):
    historial_temas: Optional[List[str]] = []
    industria: Optional[str] = "Automatización IA"
    objetivo_mes: Optional[str] = None


def _call_gemini_text(prompt: str, timeout: int = 60) -> str:
    """Llamada centralizada a Gemini para texto. Lanza excepción si falla."""
    resp = req.post(
        f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# POST /social/crear-post
# ---------------------------------------------------------------------------
@router.post("/crear-post")
async def crear_post(entrada: DatosCrearPost):
    """
    Genera posts para IG, LinkedIn y Facebook con brandbook del cliente.
    Entrada: cliente_id + datos_marca (array de Airtable via n8n).
    Salida: {status, resultados: {instagram, linkedin, facebook}}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en variables de entorno."}

    # Buscar datos del cliente en el array de n8n
    cliente_data = None
    for item in entrada.datos_marca:
        if item.get("json", {}).get("ID Cliente") == entrada.cliente_id:
            cliente_data = item.get("json")
            break

    if not cliente_data:
        return {"status": "error", "mensaje": f"No se encontró el cliente '{entrada.cliente_id}' en los datos."}

    industria   = cliente_data.get("Industria", "General")
    servicio    = cliente_data.get("Servicio Principal", "Automatizaciones IA")
    publico     = cliente_data.get("Público Objetivo", "Emprendedores y pymes LATAM")
    tono        = cliente_data.get("Tono de Voz", "Humano, cercano, experto")
    reglas      = cliente_data.get("Reglas Estrictas", "No prometer resultados garantizados")
    tema        = cliente_data.get("Tema del Día", "Automatización con IA")
    angulo      = cliente_data.get("Ángulo", "Beneficios prácticos para el negocio")

    prompt = f"""Eres el Estratega y Copywriter de una agencia de automatizaciones IA para LATAM.

BRANDBOOK DEL CLIENTE:
- Industria: {industria}
- Servicio principal: {servicio}
- Público objetivo: {publico}
- Tono de voz: {tono}
- RESTRICCIONES ABSOLUTAS: {reglas}

TEMA DEL DÍA: {tema}
ÁNGULO: {angulo}

TAREA: Crea 3 posts únicos y diferenciados, uno por red social.
Separa cada post EXACTAMENTE con: |||
NO uses markdown de código. Solo texto puro.

1. INSTAGRAM: Hook fuerte en línea 1, viñetas con emojis, 150-200 palabras, 6-8 hashtags al final.
|||
2. LINKEDIN: Apertura con dato o reflexión, desarrollo analítico (apertura-nudo-desenlace), cierre con pregunta, 300-400 palabras, max 2 emojis, 3-4 hashtags profesionales.
|||
3. FACEBOOK: Storytelling cercano como hablando con un amigo emprendedor, invita a comentar al final, 200-250 palabras, max 3 emojis."""

    try:
        texto = _call_gemini_text(prompt, timeout=60)
        partes = texto.split("|||")
        return {
            "status": "success",
            "resultados": {
                "instagram": partes[0].strip() if len(partes) > 0 else "",
                "linkedin":  partes[1].strip() if len(partes) > 1 else "",
                "facebook":  partes[2].strip() if len(partes) > 2 else ""
            }
        }
    except Exception as e:
        return {"status": "error", "mensaje": f"Error generando contenido: {str(e)}"}


# ---------------------------------------------------------------------------
# POST /social/generar-imagen
# ---------------------------------------------------------------------------
@router.post("/generar-imagen")
async def generar_imagen(entrada: DatosGenerarImagen):
    """
    Genera imagen con Gemini 2.0 Flash con loop de reintentos interno.
    Resuelve el problema de ciclos en n8n — el Worker espera internamente.
    Entrada: prompt + estilo + max_intentos + espera_segundos.
    Salida: {status, base64Image, mimeType, intentos}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en variables de entorno."}

    prompt_completo = f"{entrada.prompt}. Estilo visual: {entrada.estilo}. Alta calidad, sin texto escrito en la imagen."

    for intento in range(1, entrada.max_intentos + 1):
        try:
            resp = req.post(
                f"{GEMINI_IMG_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt_completo}]}],
                    "generationConfig": {"responseModalities": ["image", "text"]}
                },
                timeout=90
            )
            resp.raise_for_status()
            parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])

            for part in parts:
                if "inlineData" in part:
                    return {
                        "status": "success",
                        "base64Image": part["inlineData"]["data"],
                        "mimeType": part["inlineData"].get("mimeType", "image/png"),
                        "intentos": intento
                    }

        except Exception as e:
            if intento == entrada.max_intentos:
                return {"status": "error", "mensaje": f"Error en intento {intento}: {str(e)}"}

        # Imagen no lista aún — esperar antes del siguiente intento
        if intento < entrada.max_intentos:
            time.sleep(entrada.espera_segundos)

    return {
        "status": "error",
        "mensaje": f"Gemini no generó imagen tras {entrada.max_intentos} intentos de {entrada.espera_segundos}s cada uno."
    }


# ---------------------------------------------------------------------------
# POST /social/seleccionar-tema
# ---------------------------------------------------------------------------
@router.post("/seleccionar-tema")
async def seleccionar_tema(entrada: DatosSeleccionarTema):
    """
    IA selecciona el tema y ángulo óptimo para el post del día.
    Evita repetir temas recientes del historial.
    Salida: {status, tema, angulo, idea_central, prompt_imagen, razonamiento}
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "mensaje": "Falta GEMINI_API_KEY en variables de entorno."}

    historial_str = ", ".join(entrada.historial_temas[-10:]) if entrada.historial_temas else "ninguno aún"
    objetivo_str  = entrada.objetivo_mes or "posicionamiento general de marca como expertos en automatización"

    prompt = f"""Eres el Estratega de Contenidos de una agencia de automatizaciones IA para LATAM.

INDUSTRIA: {entrada.industria}
OBJETIVO DEL MES: {objetivo_str}
TEMAS PUBLICADOS RECIENTEMENTE (no repetir): {historial_str}

Selecciona el mejor tema y ángulo para el post de HOY considerando:
- Variedad respecto al historial
- Relevancia para emprendedores y pymes LATAM
- Alto potencial de engagement

Responde SOLO con este JSON, sin explicaciones previas:
{{
  "tema": "Nombre del macro-tema",
  "angulo": "El ángulo específico y diferenciador de hoy",
  "idea_central": "La idea principal en una oración poderosa",
  "prompt_imagen": "Descripción visual detallada y específica para generar la imagen del post",
  "razonamiento": "Por qué este tema hoy (máximo 1 oración)"
}}"""

    try:
        texto = _call_gemini_text(prompt, timeout=30)
        match = re.search(r'\{[\s\S]*\}', texto)
        if not match:
            return {"status": "error", "mensaje": "Gemini no devolvió JSON válido."}
        parsed = json.loads(match.group(0))
        return {"status": "success", **parsed}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error seleccionando tema: {str(e)}"}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS para publicar-completo
# ─────────────────────────────────────────────────────────────────────────────

def _generar_imagen_interna(prompt: str, max_intentos: int = 4, espera: int = 25):
    """Retorna (base64_str, mime_type). Lanza Exception si todos los intentos fallan."""
    prompt_completo = f"{prompt}. Estilo: fotografico profesional moderno, SIN texto escrito en la imagen."
    ultimo_error = ""
    ultima_respuesta = ""
    for intento in range(1, max_intentos + 1):
        try:
            resp = req.post(
                f"{GEMINI_IMG_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt_completo}]}],
                    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
                },
                timeout=90
            )
            resp.raise_for_status()
            data = resp.json()
            ultima_respuesta = json.dumps(data)[:500]  # para debug
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    return part["inlineData"]["data"], part["inlineData"].get("mimeType", "image/png")
            # Si llegamos aquí, Gemini respondió sin imagen
            ultimo_error = f"Intento {intento}: Gemini respondió sin imagen. Respuesta: {ultima_respuesta}"
        except Exception as e:
            ultimo_error = f"Intento {intento}: {str(e)}"
        if intento < max_intentos:
            time.sleep(espera)
    raise Exception(f"Gemini no generó imagen tras {max_intentos} intentos. Último error: {ultimo_error}")


def _subir_cloudinary(base64_img: str, mime_type: str) -> str:
    """Sube imagen base64 a Cloudinary y retorna secure_url."""
    resp = req.post(
        f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
        data={
            "file": f"data:{mime_type};base64,{base64_img}",
            "upload_preset": CLOUDINARY_UPLOAD_PRESET,
            "folder": "system-ia-posts"
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["secure_url"]


def _publicar_instagram(imagen_url: str, caption: str) -> dict:
    """Crea container + publica en Instagram Business."""
    try:
        r1 = req.post(
            f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ACCOUNT_ID}/media",
            params={"access_token": META_ACCESS_TOKEN},
            json={"image_url": imagen_url, "caption": caption},
            timeout=30
        )
        r1.raise_for_status()
        container_id = r1.json()["id"]
        time.sleep(8)
        r2 = req.post(
            f"https://graph.facebook.com/v22.0/{IG_BUSINESS_ACCOUNT_ID}/media_publish",
            params={"access_token": META_ACCESS_TOKEN},
            json={"creation_id": container_id},
            timeout=30
        )
        r2.raise_for_status()
        return {"success": True, "post_id": r2.json().get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_linkedin(texto: str, imagen_url: str) -> dict:
    """Inicializa upload, sube imagen y crea post en LinkedIn."""
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "LinkedIn-Version": "202501",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        r1 = req.post(
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            headers=headers,
            json={"initializeUploadRequest": {"owner": f"urn:li:person:{LINKEDIN_PERSON_ID}"}},
            timeout=30
        )
        r1.raise_for_status()
        li_data    = r1.json()["value"]
        upload_url = li_data["uploadUrl"]
        image_urn  = li_data["image"]

        img_bytes = req.get(imagen_url, timeout=30).content
        req.put(
            upload_url,
            headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}", "Content-Type": "image/jpeg"},
            data=img_bytes,
            timeout=60
        )

        r4 = req.post(
            "https://api.linkedin.com/rest/posts",
            headers=headers,
            json={
                "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",
                "commentary": texto,
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": []
                },
                "content": {"media": {"altText": "Post System IA", "id": image_urn}},
                "lifecycleState": "PUBLISHED",
                "isReshareDisableForOperator": False
            },
            timeout=30
        )
        r4.raise_for_status()
        return {"success": True, "post_id": image_urn}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_facebook(texto: str, imagen_url: str) -> dict:
    """Publica foto con caption en Facebook Page."""
    try:
        resp = req.post(
            f"https://graph.facebook.com/v22.0/{FACEBOOK_PAGE_ID}/photos",
            params={"access_token": META_ACCESS_TOKEN},
            json={"url": imagen_url, "message": texto},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return {"success": True, "post_id": data.get("post_id") or data.get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _notificar_whatsapp(mensaje: str) -> dict:
    """Envía notificación vía Evolution API."""
    try:
        resp = req.post(
            f"http://{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={"number": WHATSAPP_NOTIFY_NUMBER, "text": mensaje},
            timeout=15
        )
        return {"success": resp.status_code < 300}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# POST /social/publicar-completo  — endpoint agéntico maestro
# ─────────────────────────────────────────────────────────────────────────────

class DatosPublicarCompleto(BaseModel):
    datos_marca: dict  # JSON plano del registro de Airtable


@router.post("/publicar-completo")
async def publicar_completo(entrada: DatosPublicarCompleto):
    """
    Endpoint agéntico maestro. Recibe el brandbook de Airtable y ejecuta
    TODO el flujo: generar textos → imagen → Cloudinary → publicar IG/LI/FB → notificar WA.
    n8n solo necesita 3 nodos: Trigger → Airtable → este endpoint.
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "paso": "init", "mensaje": "Falta GEMINI_API_KEY"}

    marca = entrada.datos_marca
    errores = []

    # ── 1. Generar textos IA ─────────────────────────────────────────────────
    try:
        prompt_txt = f"""Eres el Copywriter de una agencia de automatizaciones IA para LATAM.

BRANDBOOK:
- Industria: {marca.get('Industria', 'General')}
- Servicio: {marca.get('Servicio Principal', 'Automatizaciones IA')}
- Público: {marca.get('Público Objetivo', 'Emprendedores y pymes LATAM')}
- Tono: {marca.get('Tono de Voz', 'Humano, cercano, experto')}
- RESTRICCIONES: {marca.get('Reglas Estrictas', 'No prometer resultados garantizados')}
- Tema del día: {marca.get('Tema del Día', 'Automatización con IA')}
- Ángulo: {marca.get('Ángulo', 'Beneficios prácticos para el negocio')}

Crea 3 posts únicos. Separa EXACTAMENTE con: |||

1. INSTAGRAM: Hook fuerte, viñetas con emojis, 150-200 palabras, 6-8 hashtags al final.
|||
2. LINKEDIN: Apertura con dato/reflexión, desarrollo analítico, cierre con pregunta, 300-400 palabras, max 2 emojis, 3-4 hashtags.
|||
3. FACEBOOK: Storytelling cercano, invita a comentar, 200-250 palabras, max 3 emojis."""

        texto_raw = _call_gemini_text(prompt_txt, timeout=60)
        partes    = texto_raw.split("|||")
        texto_ig  = partes[0].strip() if len(partes) > 0 else ""
        texto_li  = partes[1].strip() if len(partes) > 1 else ""
        texto_fb  = partes[2].strip() if len(partes) > 2 else ""
    except Exception as e:
        return {"status": "error", "paso": "generacion_textos", "mensaje": str(e)}

    # ── 2. Generar imagen con Gemini ─────────────────────────────────────────
    try:
        prompt_img = marca.get("Estilo Visual (Prompt DALL-E/Gemini)",
                               "professional automation business flat design colorful no text")
        base64_img, mime_type = _generar_imagen_interna(prompt_img)
    except Exception as e:
        return {"status": "error", "paso": "generacion_imagen", "mensaje": str(e)}

    # ── 3. Subir a Cloudinary ────────────────────────────────────────────────
    try:
        imagen_url = _subir_cloudinary(base64_img, mime_type)
    except Exception as e:
        return {"status": "error", "paso": "cloudinary", "mensaje": str(e)}

    # ── 4. Publicar en las 3 redes (errores no detienen el flujo) ───────────
    res_ig = _publicar_instagram(imagen_url, texto_ig)
    res_li = _publicar_linkedin(texto_li, imagen_url)
    res_fb = _publicar_facebook(texto_fb, imagen_url)

    for red, res in [("Instagram", res_ig), ("LinkedIn", res_li), ("Facebook", res_fb)]:
        if not res.get("success"):
            errores.append(f"{red}: {res.get('error', 'error desconocido')}")

    # ── 5. Notificación WhatsApp ─────────────────────────────────────────────
    redes_ok   = [r for r, v in [("IG ✅", res_ig), ("LI ✅", res_li), ("FB ✅", res_fb)] if v.get("success")]
    redes_fail = [r for r, v in [("IG ❌", res_ig), ("LI ❌", res_li), ("FB ❌", res_fb)] if not v.get("success")]

    msg_wa = (
        f"{'✅' if not redes_fail else '⚠️'} *Post completado*\n\n"
        f"📸 {' · '.join(redes_ok) or 'Sin publicaciones exitosas'}\n"
        f"🖼️ {imagen_url}\n\n"
        f"📝 IG: {texto_ig[:100]}..."
    )
    if redes_fail:
        msg_wa += f"\n\n⚠️ Fallaron: {', '.join(redes_fail)}"

    notif = _notificar_whatsapp(msg_wa)

    return {
        "status": "success" if not errores else "partial",
        "imagen_url": imagen_url,
        "publicaciones": {
            "instagram": res_ig,
            "linkedin":  res_li,
            "facebook":  res_fb
        },
        "textos": {
            "instagram": texto_ig[:200],
            "linkedin":  texto_li[:200],
            "facebook":  texto_fb[:200]
        },
        "notificacion_wa": notif,
        "errores": errores
    }
