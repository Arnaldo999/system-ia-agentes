import os
import re
import json
import time
import base64
import requests as req
from io import BytesIO
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/social", tags=["Social Media"])

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_IMG_URL  = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"

# ── Publicación en redes ──────────────────────────────────────────────────────
META_ACCESS_TOKEN      = os.environ.get("META_ACCESS_TOKEN", "")
IG_BUSINESS_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID       = os.environ.get("FACEBOOK_PAGE_ID", "")
LINKEDIN_ACCESS_TOKEN  = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_ID     = os.environ.get("LINKEDIN_PERSON_ID", "")
CLOUDINARY_CLOUD_NAME  = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "")
EVOLUTION_URL          = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_INSTANCE     = os.environ.get("EVOLUTION_INSTANCE", "")
EVOLUTION_API_KEY      = os.environ.get("EVOLUTION_API_KEY", "")
WHATSAPP_NOTIFY_NUMBER = os.environ.get("WHATSAPP_APPROVAL_NUMBER", "")

# ── Rotación de temas (4 rubros × 6 días lunes-sábado) ───────────────────────
_ROTACION_TEMAS = {
    0: {  # Lunes
        "tema": "Automatización de WhatsApp",
        "angulo": "Cómo atender más clientes sin contratar más personal",
        "idea_central": "Un bot de WhatsApp bien configurado puede multiplicar tu capacidad de atención ×10 sin sumar costos fijos.",
        "prompt_imagen": "smartphone showing WhatsApp chat with automated AI responses, business automation concept, modern flat design colorful background, no text in image",
    },
    1: {  # Martes
        "tema": "Automatización de CRM",
        "angulo": "Nunca más perder un lead por falta de seguimiento",
        "idea_central": "Un CRM automatizado hace el seguimiento perfecto aunque no estés disponible — cada lead recibe atención en el momento exacto.",
        "prompt_imagen": "CRM pipeline dashboard with automated lead cards flowing through stages, colorful funnel, modern business software, flat design, no text in image",
    },
    2: {  # Miércoles
        "tema": "Automatización de agendamiento de citas",
        "angulo": "Eliminar el ida y vuelta de mensajes para coordinar una reunión",
        "idea_central": "Tus clientes pueden reservar su cita sin que intervengas — 24/7, sin errores, sin olvidos.",
        "prompt_imagen": "digital calendar with automated appointment booking flow, AI scheduling assistant icon, clean modern interface, flat design colorful, no text in image",
    },
    3: {  # Jueves
        "tema": "Automatización de redes sociales",
        "angulo": "Publicar contenido de valor todos los días sin dedicarle horas",
        "idea_central": "La IA crea, programa y publica tu contenido mientras vos trabajás en lo que realmente importa.",
        "prompt_imagen": "social media management dashboard with automated posts on Instagram LinkedIn Facebook, content calendar with AI robot, flat design colorful, no text in image",
    },
    4: {  # Viernes
        "tema": "Automatización de WhatsApp",
        "angulo": "Respuestas automáticas que suenan humanas y convierten clientes",
        "idea_central": "El secreto no es el bot — es cómo está configurado: flujos inteligentes que guían al cliente hasta la venta.",
        "prompt_imagen": "WhatsApp conversation flow diagram with AI brain icon, messaging automation arrows, professional colorful business illustration, flat design, no text in image",
    },
    5: {  # Sábado
        "tema": "Automatización de CRM",
        "angulo": "Datos que no mienten: cómo saber en qué leads enfocarte hoy",
        "idea_central": "Un CRM automatizado califica y prioriza tus leads solo — vos solo hablás con los que realmente van a comprar.",
        "prompt_imagen": "data analytics dashboard with lead scoring charts, automated CRM insights, business intelligence graphs, flat design colorful, no text in image",
    },
}


def _get_tema_del_dia() -> dict:
    """Retorna el dict de tema/ángulo/idea_central según el día de la semana (0=Lunes)."""
    dia = datetime.now().weekday()  # 0=Lunes … 6=Domingo
    return _ROTACION_TEMAS.get(dia, _ROTACION_TEMAS[0])


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
        GEMINI_TEXT_URL,
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json"
        },
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
                GEMINI_IMG_URL,
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json"
                },
                # NOTA: gemini-2.5-flash-image no necesita generationConfig
                # El modelo nativamente devuelve imágenes según la doc oficial
                json={"contents": [{"parts": [{"text": prompt_completo}]}]},
                timeout=90
            )
            resp.raise_for_status()
            data = resp.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])

            for part in parts:
                if "inlineData" in part:
                    return {
                        "status": "success",
                        "base64Image": part["inlineData"]["data"],
                        "mimeType": part["inlineData"].get("mimeType", "image/png"),
                        "intentos": intento
                    }

            # Si llegamos aquí, Gemini respondió sin imagen (solo texto)
            respuesta_debug = json.dumps(data)[:300]
            ultimo_error_endpoint = f"Intento {intento}: Sin imagen en respuesta. Data: {respuesta_debug}"

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
    for intento in range(1, max_intentos + 1):
        try:
            resp = req.post(
                GEMINI_IMG_URL,
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json"
                },
                # NOTA: gemini-2.5-flash-image devuelve imágenes nativamente
                # NO agregar generationConfig.responseModalities (interfiere con la respuesta)
                json={"contents": [{"parts": [{"text": prompt_completo}]}]},
                timeout=90
            )
            if resp.status_code == 429:
                ultimo_error = f"Intento {intento}: 429 Too Many Requests"
                if intento < max_intentos:
                    time.sleep(60)  # Rate limit: esperar 60s antes de reintentar
                continue
            resp.raise_for_status()
            data = resp.json()
            debug_resp = json.dumps(data)[:500]
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    return part["inlineData"]["data"], part["inlineData"].get("mimeType", "image/png")
            # Si llegamos aquí, Gemini respondió sin imagen (bloqueado por safety o sin créditos)
            ultimo_error = f"Intento {intento}: Sin imagen en la respuesta. Detalle: {debug_resp}"
        except Exception as e:
            ultimo_error = f"Intento {intento}: {str(e)}"
        if intento < max_intentos:
            time.sleep(espera)
    raise Exception(f"Gemini no generó imagen tras {max_intentos} intentos. Último: {ultimo_error}")


def _subir_cloudinary(base64_img: str, mime_type: str) -> str:
    """Sube imagen a Cloudinary via multipart y retorna secure_url."""
    img_bytes = base64.b64decode(base64_img)
    ext = mime_type.split("/")[-1]
    resp = req.post(
        f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
        data={"upload_preset": CLOUDINARY_UPLOAD_PRESET},
        files={"file": (f"post.{ext}", BytesIO(img_bytes), mime_type)},
        timeout=60
    )
    if not resp.ok:
        raise Exception(f"Cloudinary {resp.status_code}: {resp.text[:300]}")
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


def _publicar_linkedin(texto: str, imagen_url: str) -> dict:  # noqa: ARG001
    """Publica post en LinkedIn. Imagen ignorada — usa UGC text post."""
    return _publicar_linkedin_texto(texto)


def _get_facebook_page_token() -> str:
    """Obtiene el Page Access Token desde el User/System User Token."""
    try:
        r = req.get(
            f"https://graph.facebook.com/v22.0/{FACEBOOK_PAGE_ID}",
            params={"fields": "access_token", "access_token": META_ACCESS_TOKEN},
            timeout=15
        )
        r.raise_for_status()
        return r.json().get("access_token", META_ACCESS_TOKEN)
    except Exception:
        return META_ACCESS_TOKEN


def _publicar_facebook(texto: str, imagen_url: str) -> dict:
    """Publica foto con caption en Facebook Page."""
    try:
        page_token = _get_facebook_page_token()
        resp = req.post(
            f"https://graph.facebook.com/v22.0/{FACEBOOK_PAGE_ID}/photos",
            params={"access_token": page_token},
            json={"url": imagen_url, "message": texto},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return {"success": True, "post_id": data.get("post_id") or data.get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_linkedin_texto(texto: str) -> dict:
    """Publica post en LinkedIn via UGC API (v2, sin version header)."""
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        r = req.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json={
                "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": texto},
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            },
            timeout=30
        )
        if not r.ok:
            return {"success": False, "error": f"{r.status_code}: {r.text[:300]}"}
        return {"success": True, "post_id": r.json().get("id", "ugc-post")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_facebook_texto(texto: str) -> dict:
    """Publica post de solo texto en Facebook Page."""
    try:
        page_token = _get_facebook_page_token()
        resp = req.post(
            f"https://graph.facebook.com/v22.0/{FACEBOOK_PAGE_ID}/feed",
            params={"access_token": page_token},
            json={"message": texto},
            timeout=30
        )
        if not resp.ok:
            return {"success": False, "error": f"{resp.status_code}: {resp.text[:300]}"}
        return {"success": True, "post_id": resp.json().get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _notificar_whatsapp(mensaje: str) -> dict:
    """Envía notificación vía Evolution API."""
    try:
        resp = req.post(
            f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={"number": WHATSAPP_NOTIFY_NUMBER, "text": mensaje},
            timeout=15
        )
        return {"success": resp.status_code < 300}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _limpiar_texto_post(texto: str) -> str:
    """Elimina encabezados numerados y líneas introductorias que Gemini añade."""
    # Quitar intro tipo "Aquí tienes los 3 posts..."
    texto = re.sub(r'^.*(Aquí tienes|Here are|posts únicos|separados).*\n+', '', texto, flags=re.IGNORECASE)
    # Quitar separadores markdown ---
    texto = re.sub(r'^-{3,}\s*\n', '', texto, flags=re.MULTILINE)
    # Quitar encabezados tipo "### **1. INSTAGRAM**", "**1. INSTAGRAM**", "1. INSTAGRAM:", etc.
    texto = re.sub(r'^#{0,6}\s*\*{0,2}\s*\d+\.\s*\*{0,2}\s*[A-ZÁÉÍÓÚÑ]+\s*\*{0,2}:?\*{0,2}\s*\n+', '', texto, flags=re.MULTILINE)
    return texto.strip()


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

    # ── Tema del día: rotación automática por día de semana ──────────────────
    rotacion     = _get_tema_del_dia()
    tema         = rotacion["tema"]
    angulo       = rotacion["angulo"]
    idea_central = rotacion["idea_central"]

    # ── 1. Generar textos IA ─────────────────────────────────────────────────
    try:
        prompt_txt = f"""Eres el Copywriter jefe de una agencia de automatizaciones IA para LATAM.

BRANDBOOK:
- Industria: {marca.get('Industria', 'Automatización IA')}
- Servicio: {marca.get('Servicio Principal', 'Automatizaciones con IA para negocios')}
- Público: {marca.get('Público Objetivo', 'Emprendedores y pymes de LATAM')}
- Tono de voz: {marca.get('Tono de Voz', 'Humano, cercano, directo y experto')}
- RESTRICCIONES: {marca.get('Reglas Estrictas', 'Nunca prometer resultados garantizados. Nada de spam.')}

TEMA DEL DÍA: {tema}
ÁNGULO: {angulo}
IDEA CENTRAL: {idea_central}

FILOSOFÍA DE CONTENIDO (OBLIGATORIA):
- SIEMPRE aportar valor real y accionable: el lector debe llevarse algo útil.
- Nunca spam, nunca clickbait vacío, nunca hipérboles sin sustento.
- El CTA es una invitación natural — nunca agresivo ni desesperado.
- NUNCA uses nombres propios de personas — habla siempre como la marca {marca.get('Nombre Comercial', 'la agencia')}, de forma genérica.

Crea 3 posts únicos y diferenciados. Separa EXACTAMENTE con: |||

1. INSTAGRAM: Hook irresistible en primera línea, viñetas con emojis con tips prácticos y accionables, 150-200 palabras. CTA final: invitar a SEGUIR la cuenta y/o dar LIKE. 6-8 hashtags al final.
|||
2. LINKEDIN: Apertura con dato real o reflexión del sector, desarrollo con insights accionables (problema → solución → resultado), cierre con pregunta que genere debate, 300-400 palabras, máx 2 emojis. CTA final: invitar a CONECTAR y/o COMENTAR con su experiencia. 3-4 hashtags profesionales.
|||
3. FACEBOOK: Storytelling cercano como si hablaras con un amigo emprendedor, incluye un tip útil o historia de transformación real, 200-250 palabras, máx 3 emojis. CTA final: invitar a DAR LIKE, COMPARTIR con alguien que lo necesite y/o SEGUIR la página."""

        texto_raw = _call_gemini_text(prompt_txt, timeout=60)
        partes    = texto_raw.split("|||")
        texto_ig  = _limpiar_texto_post(partes[0]) if len(partes) > 0 else ""
        texto_li  = _limpiar_texto_post(partes[1]) if len(partes) > 1 else ""
        texto_fb  = _limpiar_texto_post(partes[2]) if len(partes) > 2 else ""
    except Exception as e:
        return {"status": "error", "paso": "generacion_textos", "mensaje": str(e)}

    # ── 2. Generar imagen con Gemini → subir a Cloudinary ────────────────────
    imagen_url = None
    imagen_error = None
    try:
        # Usar el prompt de imagen del tema rotado (más específico que Airtable)
        prompt_img = rotacion.get("prompt_imagen", marca.get(
            "Estilo Visual (Prompt DALL-E/Gemini)",
            "professional automation business flat design colorful no text"
        ))
        b64, mime = _generar_imagen_interna(prompt_img, max_intentos=3, espera=20)
        imagen_url = _subir_cloudinary(b64, mime)
    except Exception as e:
        imagen_error = str(e)
        imagen_url = None

    # ── 4. Publicar en las 3 redes ───────────────────────────────────────────
    if imagen_url:
        res_ig = _publicar_instagram(imagen_url, texto_ig)
        res_li = _publicar_linkedin(texto_li, imagen_url)
        res_fb = _publicar_facebook(texto_fb, imagen_url)
    else:
        # Sin imagen: omitir Instagram, publicar texto en LI y FB
        res_ig = {"success": False, "error": f"Sin imagen: {imagen_error}"}
        res_li = _publicar_linkedin_texto(texto_li)
        res_fb = _publicar_facebook_texto(texto_fb)

    for red, res in [("Instagram", res_ig), ("LinkedIn", res_li), ("Facebook", res_fb)]:
        if not res.get("success"):
            errores.append(f"{red}: {res.get('error', 'error desconocido')}")

    # ── 5. Notificación WhatsApp ─────────────────────────────────────────────
    redes_ok   = [r for r, v in [("IG ✅", res_ig), ("LI ✅", res_li), ("FB ✅", res_fb)] if v.get("success")]
    redes_fail = [r for r, v in [("IG ❌", res_ig), ("LI ❌", res_li), ("FB ❌", res_fb)] if not v.get("success")]

    msg_wa = (
        f"{'✅' if not redes_fail else '⚠️'} *Post completado*\n\n"
        f"📌 *Tema:* {tema}\n"
        f"🎯 *Ángulo:* {angulo}\n\n"
        f"📸 {' · '.join(redes_ok) or 'Sin publicaciones exitosas'}\n"
        + (f"🖼️ {imagen_url}\n\n" if imagen_url else "🖼️ Sin imagen (Gemini no disponible)\n\n")
        + f"📝 {texto_li[:100]}..."
    )
    if redes_fail:
        msg_wa += f"\n\n⚠️ Fallaron: {', '.join(redes_fail)}"

    notif = _notificar_whatsapp(msg_wa)

    return {
        "status": "success" if not errores else "partial",
        "tema_del_dia": {"tema": tema, "angulo": angulo},
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
