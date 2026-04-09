import os
import re
import json
import time
import base64
import logging
import requests as req

logger = logging.getLogger(__name__)
from io import BytesIO
from datetime import datetime
from PIL import Image
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List
from workers.shared.guardrails import (
    detect_injection,
    sanitize_for_llm,
    validate_output,
    FALLBACK_SOCIAL,
)

router = APIRouter(prefix="/social", tags=["Social Media"])

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_IMG_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"

# ── Publicación en redes (Fallbacks de seguridad) ─────────────────────────────
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
IG_BUSINESS_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "")
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_ID = os.environ.get("LINKEDIN_PERSON_ID", "")

# ── Credenciales Centrales para Arquitectura Multi-Tenant ──
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")

# ── Otras integraciones ───────────────────────────────────────────────────────
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "")
EVOLUTION_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
WHATSAPP_NOTIFY_NUMBER = os.environ.get("WHATSAPP_APPROVAL_NUMBER", "")

# ── Rotación de temas (4 rubros × 6 días lunes-sábado) ───────────────────────
_ROTACION_TEMAS = {
    0: {  # Lunes - GASTRONOMÍA (WhatsApp)
        "tema": "Autocontrol y Pedidos Gastronómicos Automatizados",
        "angulo": "Cómo atender más pedidos sin colapsar la cocina ni el WhatsApp del restaurante",
        "idea_central": "Un bot de WhatsApp para tu local atiende 100 pedidos en segundos y sin errores humanos, dejando que tu personal se enfoque solo en cocinar y atender en el salón.",
        "prompt_imagen": "busy restaurant kitchen with smart displays, AI taking automated orders on smartphone, efficient modern workflow gastronomy concept, flat design colorful, no text in image",
    },
    1: {  # Martes - GENÉRICO (WhatsApp PyMEs)
        "tema": "Automatización de Ventas por WhatsApp",
        "angulo": "Atender clientes 24 horas al día sin contratar más personal",
        "idea_central": "Convertir horas de chat manual en un embudo de ventas automático vía WhatsApp permite que el dueño de negocio suelte el celular y escale su atención.",
        "prompt_imagen": "smartphone showing WhatsApp chat with automated AI responses, business automation concept, modern flat design colorful background, no text in image",
    },
    2: {  # Miércoles - GASTRONOMÍA (CRM / Retención)
        "tema": "Cómo rescatar ganancias de apps de delivery",
        "angulo": "Las apps de delivery se quedan con tu cliente y el 30% de tu dinero",
        "idea_central": "Implementar un bot propio rescata ese 30% de comisión y captura la base de datos de los clientes. El restaurante pasa del anonimato a fidelizar directamente usando su CRM.",
        "prompt_imagen": "restaurant owner looking at modern tablet showing automated orders and customer data, no delivery apps, smart kitchen system, colorful flat design illustration, no text in image",
    },
    3: {  # Jueves - GENÉRICO (CRM PyMEs)
        "tema": "Seguimiento Infalible con CRM en Automático",
        "angulo": "Nunca más perder una cotización o lead por falta de seguimiento",
        "idea_central": "Un CRM conectado con IA hace el seguimiento de cada cliente en el momento exacto, recordando fechas sin depender de la memoria de los vendedores.",
        "prompt_imagen": "CRM pipeline dashboard with automated lead cards flowing through stages, colorful funnel, modern business software, flat design, no text in image",
    },
    4: {  # Viernes - GASTRONOMÍA (Reservas y Menú)
        "tema": "IA tomando Reservas en tu Restaurante",
        "angulo": "Perder reservas o sufrir demoras por atender mal de noche",
        "idea_central": "Tu local de comida puede tomar reservas 24/7 y agendarlas automáticamente con un asistente inteligente, evitando cancelaciones sorpresa o dobles reservas de papel.",
        "prompt_imagen": "digital restaurant reservation system on smartphone, AI chatbot confirming table booking, flat design colorful modern UI, no text in image",
    },
    5: {  # Sábado - GENÉRICO (Agendamiento de Citas)
        "tema": "Calendario Automático Inteligente",
        "angulo": "Eliminar el molesto ida y vuelta manual para coordinar una simple reunión",
        "idea_central": "Tus clientes y proveedores pueden agendar una cita o reunión sin que el dueño intervenga en absoluto, conectando automáticamente el calendario de Google.",
        "prompt_imagen": "digital calendar with automated appointment booking flow, AI scheduling assistant icon, clean modern interface, flat design colorful, no text in image",
    },
    6: {  # Domingo - GENÉRICO (Redes Sociales AI)
        "tema": "La IA gestionando las redes de tu PyME",
        "angulo": "Publicar contenido de valor todos los días sin pasar horas editando",
        "idea_central": "Sistemas de IA hoy pueden pensar, diseñar y publicar estratégicamente tu contenido para que el dueño se enfoque en cerrar los negocios físicos.",
        "prompt_imagen": "social media management dashboard with automated posts on Instagram LinkedIn Facebook, content calendar with AI robot, flat design colorful, no text in image",
    },
}


_ROTACION_TEMAS_INMOBILIARIA = {
    0: {  # Lunes
        "tema": "Cómo elegir el lote ideal en Misiones",
        "angulo": "Los 3 factores que nadie te cuenta antes de comprar",
        "idea_central": "Ubicación, servicios y documentación legal son los pilares para elegir bien. Un lote con mensura, agua y luz ya instalados vale más y te ahorra problemas futuros.",
        "prompt_imagen": "aerial view of green land lots in Misiones Argentina, urban planning, marked terrain parcels, lush vegetation, professional real estate photo, no text in image",
    },
    1: {  # Martes
        "tema": "Invertir en terrenos: por qué el suelo siempre sube",
        "angulo": "La tierra no se deprecia — y en Misiones menos",
        "idea_central": "Mientras los ahorros pierden valor frente a la inflación, la tierra en zonas de crecimiento como Misiones históricamente se revaloriza. Un lote hoy puede valer el doble en 5 años.",
        "prompt_imagen": "land value growth concept, green terrain in Misiones Argentina, investment arrow going up, professional flat design illustration, no text in image",
    },
    2: {  # Miércoles
        "tema": "Financiar tu lote en cuotas: todo lo que necesitás saber",
        "angulo": "Ya no hace falta tener todo el dinero junto",
        "idea_central": "Con planes de hasta 120 cuotas mensuales accesibles, hoy es posible comprar tu terreno pagando menos que un alquiler. Sin banco, sin garante, directo con la desarrolladora.",
        "prompt_imagen": "family signing land purchase agreement, happy couple with keys, modern real estate office, Misiones Argentina landscape background, flat design colorful, no text in image",
    },
    3: {  # Jueves
        "tema": "Qué documentación revisar antes de comprar un lote",
        "angulo": "Evitá sorpresas legales que pueden costarte caro",
        "idea_central": "Mensura aprobada, escritura libre de deudas y habilitación municipal son los documentos clave. Un lote sin estos papeles puede convertirse en un dolor de cabeza legal.",
        "prompt_imagen": "legal documents for land purchase, notary signing papers, terrain map and title deed, professional clean illustration, no text in image",
    },
    4: {  # Viernes
        "tema": "Zonas de mayor crecimiento en Misiones para invertir",
        "angulo": "San Ignacio, Apóstoles, Gdor. Roca: ¿cuál es mejor?",
        "idea_central": "Cada zona tiene su perfil de inversión. San Ignacio crece por turismo, Apóstoles por comercio, Gdor. Roca por expansión urbana. Elegir bien la zona puede duplicar tu inversión.",
        "prompt_imagen": "map of Misiones Argentina highlighting growth zones, urban expansion aerial view, green landscape with new housing developments, professional illustration, no text in image",
    },
    5: {  # Sábado
        "tema": "Construir o guardar: qué hacer con tu lote",
        "angulo": "Dos estrategias válidas según tu objetivo",
        "idea_central": "Si comprás para vivir, planificá la construcción por etapas. Si comprás para invertir, simplemente mantenerlo algunos años puede multiplicar tu capital sin hacer nada.",
        "prompt_imagen": "split view of empty land lot vs modern house built on similar lot, investment concept, Misiones Argentina green landscape, flat design illustration, no text in image",
    },
    6: {  # Domingo
        "tema": "El sueño de la casa propia empieza por el terreno",
        "angulo": "Antes de construir, primero necesitás el suelo",
        "idea_central": "La mayoría posterga comprar el terreno esperando tener todo el dinero. Pero con financiamiento en cuotas, el primer paso es más accesible de lo que pensás.",
        "prompt_imagen": "happy family standing on their empty land lot, Misiones Argentina nature background, sunset warm light, dream home concept, flat design colorful, no text in image",
    },
}


def _get_tema_del_dia(industria: str = "") -> dict:
    """Retorna el dict de tema/ángulo/idea_central según el día y la industria del cliente."""
    dia = datetime.now().weekday()  # 0=Lunes … 6=Domingo
    if "inmobiliaria" in industria.lower() or "lote" in industria.lower() or "terreno" in industria.lower():
        return _ROTACION_TEMAS_INMOBILIARIA.get(dia, _ROTACION_TEMAS_INMOBILIARIA[0])
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


def _call_gemini_text(prompt: str, timeout: int = 60, json_mode: bool = False, max_reintentos: int = 3) -> str:
    """Llamada centralizada a Gemini para texto. Reintenta hasta 3 veces en errores 503/429."""
    import time
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    ultimo_error = None
    for intento in range(max_reintentos):
        try:
            resp = req.post(
                GEMINI_TEXT_URL,
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            if resp.status_code in (503, 429) and intento < max_reintentos - 1:
                espera = 5 * (intento + 1)  # 5s, 10s, 15s
                logger.warning(f"Gemini {resp.status_code} — reintento {intento + 1}/{max_reintentos} en {espera}s")
                time.sleep(espera)
                continue
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            ultimo_error = e
            if intento < max_reintentos - 1:
                espera = 5 * (intento + 1)
                logger.warning(f"Gemini error ({type(e).__name__}) — reintento {intento + 1}/{max_reintentos} en {espera}s")
                time.sleep(espera)
            else:
                raise
    raise ultimo_error


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
        return {
            "status": "error",
            "mensaje": "Falta GEMINI_API_KEY en variables de entorno.",
        }

    # Buscar datos del cliente en el array de n8n
    cliente_data = None
    for item in entrada.datos_marca:
        if item.get("json", {}).get("ID Cliente") == entrada.cliente_id:
            cliente_data = item.get("json")
            break

    if not cliente_data:
        return {
            "status": "error",
            "mensaje": f"No se encontró el cliente '{entrada.cliente_id}' en los datos.",
        }

    industria = cliente_data.get("Industria", "General")
    servicio = cliente_data.get("Servicio Principal", "Automatizaciones IA")
    publico = cliente_data.get("Público Objetivo", "Dueños de restaurantes, bares y PyMEs que quieren modernizar sus operaciones con IA — WhatsApp, CRM, agendamiento, redes sociales")
    tono = cliente_data.get("Tono de Voz", "Humano, cercano, experto")
    reglas = cliente_data.get("Reglas Estrictas", "No prometer resultados garantizados")
    tema = cliente_data.get("Tema del Día", "Automatización con IA")
    angulo = cliente_data.get("Ángulo", "Beneficios prácticos para el negocio")

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
                "linkedin": partes[1].strip() if len(partes) > 1 else "",
                "facebook": partes[2].strip() if len(partes) > 2 else "",
            },
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
        return {
            "status": "error",
            "mensaje": "Falta GEMINI_API_KEY en variables de entorno.",
        }

    prompt_completo = f"{entrada.prompt}. Estilo visual: {entrada.estilo}. Alta calidad, sin texto escrito en la imagen."

    for intento in range(1, entrada.max_intentos + 1):
        try:
            resp = req.post(
                GEMINI_IMG_URL,
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                # NOTA: gemini-2.5-flash-image no necesita generationConfig
                # El modelo nativamente devuelve imágenes según la doc oficial
                json={"contents": [{"parts": [{"text": prompt_completo}]}]},
                timeout=90,
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
                        "intentos": intento,
                    }

            # Si llegamos aquí, Gemini respondió sin imagen (solo texto)
            respuesta_debug = json.dumps(data)[:300]
            ultimo_error_endpoint = (
                f"Intento {intento}: Sin imagen en respuesta. Data: {respuesta_debug}"
            )

        except Exception as e:
            if intento == entrada.max_intentos:
                return {
                    "status": "error",
                    "mensaje": f"Error en intento {intento}: {str(e)}",
                }

        # Imagen no lista aún — esperar antes del siguiente intento
        if intento < entrada.max_intentos:
            time.sleep(entrada.espera_segundos)

    return {
        "status": "error",
        "mensaje": f"Gemini no generó imagen tras {entrada.max_intentos} intentos de {entrada.espera_segundos}s cada uno.",
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
        return {
            "status": "error",
            "mensaje": "Falta GEMINI_API_KEY en variables de entorno.",
        }

    historial_str = (
        ", ".join(entrada.historial_temas[-10:])
        if entrada.historial_temas
        else "ninguno aún"
    )
    objetivo_str = (
        entrada.objetivo_mes
        or "posicionamiento general de marca como expertos en automatización"
    )

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
        texto = _call_gemini_text(prompt, timeout=30, json_mode=True)
        match = re.search(r"\{[\s\S]*\}", texto)
        if not match:
            return {"status": "error", "mensaje": "Gemini no devolvió JSON válido."}
        parsed = json.loads(match.group(0))
        return {"status": "success", **parsed}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error seleccionando tema: {str(e)}"}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS para publicar-completo
# ─────────────────────────────────────────────────────────────────────────────


def _generar_imagen_interna(
    prompt: str, max_intentos: int = 4, espera: int = 25, raw_prompt: bool = False
):
    """Retorna (base64_str, mime_type). Lanza Exception si todos los intentos fallan.
    raw_prompt=True: usa el prompt tal cual (para slides diseñados con texto).
    raw_prompt=False: agrega sufijo anti-texto (para posts normales).
    """
    if raw_prompt:
        prompt_completo = prompt
    else:
        prompt_completo = f"{prompt}. Estilo: fotografico profesional moderno, SIN texto escrito en la imagen."
    ultimo_error = ""
    for intento in range(1, max_intentos + 1):
        try:
            resp = req.post(
                GEMINI_IMG_URL,
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                # NOTA: gemini-2.5-flash-image devuelve imágenes nativamente
                # NO agregar generationConfig.responseModalities (interfiere con la respuesta)
                json={"contents": [{"parts": [{"text": prompt_completo}]}]},
                timeout=90,
            )
            if resp.status_code == 429:
                ultimo_error = f"Intento {intento}: 429 Too Many Requests"
                if intento < max_intentos:
                    time.sleep(60)  # Rate limit: esperar 60s antes de reintentar
                continue
            resp.raise_for_status()
            data = resp.json()
            debug_resp = json.dumps(data)[:500]
            for part in (
                data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            ):
                if "inlineData" in part:
                    return part["inlineData"]["data"], part["inlineData"].get(
                        "mimeType", "image/png"
                    )
            # Si llegamos aquí, Gemini respondió sin imagen (bloqueado por safety o sin créditos)
            ultimo_error = (
                f"Intento {intento}: Sin imagen en la respuesta. Detalle: {debug_resp}"
            )
        except Exception as e:
            ultimo_error = f"Intento {intento}: {str(e)}"
        if intento < max_intentos:
            time.sleep(espera)
    raise Exception(
        f"Gemini no generó imagen tras {max_intentos} intentos. Último: {ultimo_error}"
    )


def _subir_cloudinary(base64_img: str, mime_type: str) -> str:
    """Sube imagen a Cloudinary via multipart y retorna secure_url."""
    img_bytes = base64.b64decode(base64_img)
    ext = mime_type.split("/")[-1]
    resp = req.post(
        f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
        data={"upload_preset": CLOUDINARY_UPLOAD_PRESET},
        files={"file": (f"post.{ext}", BytesIO(img_bytes), mime_type)},
        timeout=60,
    )
    if not resp.ok:
        raise Exception(f"Cloudinary {resp.status_code}: {resp.text[:300]}")
    return resp.json()["secure_url"]


def _get_font(size: int):
    """Carga fuente Bold del sistema. Prioriza Inter > Roboto > DejaVu."""
    from PIL import ImageFont

    font_paths = [
        "/usr/share/fonts/truetype/inter-zorin-os/Inter-Bold.ttf",
        "/usr/share/fonts/truetype/inter/Inter-Bold.ttf",
        "/app/fonts/Inter-Bold.ttf",
        "/app/fonts/Inter-Bold.otf",
        "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf",
        "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _get_font_regular(size: int):
    """Carga fuente Regular del sistema para subtítulos."""
    from PIL import ImageFont

    font_paths = [
        "/usr/share/fonts/truetype/inter-zorin-os/Inter-Regular.ttf",
        "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
        "/app/fonts/Inter-Regular.ttf",
        "/app/fonts/Inter-Regular.otf",
        "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _limpiar_markdown(texto: str) -> str:
    """Elimina asteriscos, numerales y otros símbolos markdown del texto."""
    texto = re.sub(r"\*+", "", texto)
    texto = re.sub(r"#+\s*", "", texto)
    texto = re.sub(r"_+", "", texto)
    texto = re.sub(r"`+", "", texto)
    return texto.strip()


def _extraer_colores_marca(colores_str: str):
    """
    Extrae colores hex del string de marca.
    Retorna (color_fondo, color_acento): el más oscuro como fondo,
    el más claro/vibrante como acento.
    """
    hexes = re.findall(r"#[0-9A-Fa-f]{6}", colores_str or "")

    def lum(h):
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return 0.299 * r + 0.587 * g + 0.114 * b

    if not hexes:
        return "#0A0E1A", "#0099FF"
    ordered = sorted(hexes, key=lum)
    fondo = ordered[0]
    acento = ordered[-1] if len(ordered) > 1 else "#FFFFFF"
    return fondo, acento


def _crear_slide_carrusel(
    base64_img: str,
    titulo: str,
    subtitulo: str,
    color_acento: str,
    logo_url: str = "",
    numero_slide: int = 0,
) -> str:
    """
    Diseña slide de carrusel estilo david_ai_pro — texto ENORME dominante.
    - Título gigante 130px Bold, alineado izquierda
    - Subtítulo 58px en gris
    - Número 90px en color acento
    - Logo 140px nítido
    - Imagen ocupa 50% inferior edge-to-edge (crop to fill)
    """
    try:
        from PIL import ImageDraw

        titulo = _limpiar_markdown(titulo)
        subtitulo = _limpiar_markdown(subtitulo)

        SIZE = 1080
        PAD = 60

        def hex_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

        acc_rgb = hex_rgb(color_acento)
        TITLE_C = (10, 10, 20)  # negro puro para máximo impacto
        SUB_C = (80, 85, 100)  # gris oscuro legible
        NUM_C = acc_rgb

        # ── Canvas blanco limpio ──────────────────────────────────────────────
        canvas = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # Gradiente MUY sutil solo en zona texto (top 50%)
        TEXT_ZONE_H = int(SIZE * 0.50)
        for y_line in range(TEXT_ZONE_H):
            ratio = y_line / TEXT_ZONE_H * 0.04
            r = int(255 * (1 - ratio) + acc_rgb[0] * ratio)
            g = int(255 * (1 - ratio) + acc_rgb[1] * ratio)
            b = int(255 * (1 - ratio) + acc_rgb[2] * ratio)
            draw.line([(0, y_line), (SIZE, y_line)], fill=(r, g, b))

        # ── Barra acento tope (12px) ──────────────────────────────────────────
        draw.rectangle([(0, 0), (SIZE, 12)], fill=acc_rgb)

        # ── Número GIGANTE (90px) ─────────────────────────────────────────────
        font_num = _get_font(90)
        if numero_slide > 0:
            draw.text((PAD, 28), f"{numero_slide}.", font=font_num, fill=NUM_C)

        # ── Logo GRANDE (140px) ───────────────────────────────────────────────
        if logo_url:
            try:
                logo_resp = req.get(logo_url, timeout=15)
                logo_resp.raise_for_status()
                logo_img = Image.open(BytesIO(logo_resp.content)).convert("RGBA")
                logo_img.thumbnail((140, 140), Image.LANCZOS)
                lx = SIZE - logo_img.width - PAD
                canvas.paste(logo_img, (lx, 24), logo_img)
            except Exception:
                pass

        # ── TÍTULO (95px Bold, alineado izquierda) ─────────────────────────────
        TEXT_MAX = SIZE - PAD * 2
        font_tit = _get_font(95)
        font_sub = _get_font_regular(45)

        def draw_wrapped(
            text, font, color, y, max_lines=4, line_spacing=8, align="left"
        ):
            """Word-wrap con alineación configurable. Retorna Y final."""
            words = text.split()
            lines, cur = [], ""
            for w in words:
                test = f"{cur} {w}".strip()
                bx = draw.textbbox((0, 0), test, font=font)
                if bx[2] - bx[0] <= TEXT_MAX:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            for line in lines[:max_lines]:
                bx = draw.textbbox((0, 0), line, font=font)
                lw = bx[2] - bx[0]
                lh = bx[3] - bx[1]
                if align == "center":
                    x = (SIZE - lw) // 2
                else:
                    x = PAD
                draw.text((x, y), line, font=font, fill=color)
                y += lh + line_spacing
            return y

        # Título empieza un poco más arriba y permitimos 3 líneas
        text_y = 120
        text_y = draw_wrapped(
            titulo[:70],
            font_tit,
            TITLE_C,
            text_y,
            max_lines=3,
            line_spacing=6,
            align="left",
        )

        # Subtítulo (hasta 3 líneas)
        if subtitulo:
            text_y = draw_wrapped(
                subtitulo[:120],
                font_sub,
                SUB_C,
                text_y + 12,
                max_lines=3,
                line_spacing=6,
                align="left",
            )

        # ── Línea separadora acento (6px, gruesa) ─────────────────────────────
        sep_y = TEXT_ZONE_H - 8
        draw.rectangle([(0, sep_y), (SIZE, sep_y + 6)], fill=acc_rgb)

        # ── Imagen — bottom 50%, EDGE TO EDGE, crop to fill ──────────────────
        IMG_Y = TEXT_ZONE_H
        IMG_H = SIZE - IMG_Y
        IMG_W = SIZE  # pared a pared

        gemini = Image.open(BytesIO(base64.b64decode(base64_img))).convert("RGB")
        # CROP TO FILL: escalar al mayor para llenar completamente
        scale = max(IMG_W / gemini.width, IMG_H / gemini.height)
        nw = int(gemini.width * scale)
        nh = int(gemini.height * scale)
        gemini = gemini.resize((nw, nh), Image.LANCZOS)
        left = (nw - IMG_W) // 2
        top = (nh - IMG_H) // 2
        gemini = gemini.crop((left, top, left + IMG_W, top + IMG_H))
        canvas.paste(gemini, (0, IMG_Y))

        # ── Barra inferior acento (14px) ──────────────────────────────────────
        draw.rectangle([(0, SIZE - 14), (SIZE, SIZE)], fill=acc_rgb)

        out = BytesIO()
        canvas.save(out, format="PNG", quality=95)
        return base64.b64encode(out.getvalue()).decode()

    except Exception:
        return base64_img  # fallback sin diseño


def _overlay_texto_marca(
    base64_img: str,
    titulo: str,
    subtitulo: str,
    colores_str: str = "",
    logo_url: str = "",
) -> str:
    """
    Superpone título + subtítulo en overlay oscuro en la zona inferior de la imagen.
    Logo en esquina superior derecha sobre el overlay.
    Retorna base64 PNG.
    """
    try:
        from PIL import ImageDraw, ImageFont

        # Parsear color de fondo del overlay desde marca
        hexes = re.findall(r"#[0-9A-Fa-f]{6}", colores_str or "")

        def lum(h):
            h = h.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return 0.299 * r + 0.587 * g + 0.114 * b

        # Color más oscuro como fondo overlay, más claro como acento
        if hexes:
            ordered = sorted(hexes, key=lum)
            overlay_color = ordered[0]   # más oscuro
            acento_color  = ordered[-1] if len(ordered) > 1 else "#FFFFFF"
        else:
            overlay_color = "#1a4a2e"
            acento_color  = "#c9a84c"

        def hex_rgb(h, alpha=255):
            h = h.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)

        img = Image.open(BytesIO(base64.b64decode(base64_img))).convert("RGBA")
        W, H = img.size

        # ── Overlay oscuro en franja inferior (35% de la imagen) ─────────────
        overlay_h = int(H * 0.35)
        overlay_y = H - overlay_h
        overlay = Image.new("RGBA", (W, overlay_h), hex_rgb(overlay_color, 210))

        # Gradiente vertical: más transparente arriba, más sólido abajo
        for y in range(overlay_h):
            alpha = int(80 + (210 - 80) * (y / overlay_h))
            draw_o = ImageDraw.Draw(overlay)
            draw_o.line([(0, y), (W, y)], fill=hex_rgb(overlay_color, alpha))

        img.paste(overlay, (0, overlay_y), overlay)
        draw = ImageDraw.Draw(img)

        # ── Línea de acento (4px) arriba del overlay ─────────────────────────
        acc = hex_rgb(acento_color, 255)[:3]
        draw.rectangle([(0, overlay_y), (W, overlay_y + 4)], fill=acc)

        PAD = int(W * 0.05)

        # ── Título (bold, ~5% de W) ───────────────────────────────────────────
        titulo = _limpiar_markdown(titulo)[:80]
        subtitulo = _limpiar_markdown(subtitulo)[:120]

        font_titulo = _get_font(int(W * 0.052))
        font_sub    = _get_font_regular(int(W * 0.034))

        # Wrap título
        words = titulo.split()
        lines, line = [], ""
        for w in words:
            test = (line + " " + w).strip()
            if draw.textlength(test, font=font_titulo) <= W - PAD * 2:
                line = test
            else:
                if line:
                    lines.append(line)
                line = w
        if line:
            lines.append(line)
        lines = lines[:2]  # máx 2 líneas

        # altura ocupada por título (usado para posicionar subtítulo)
        y_titulo = overlay_y + int(overlay_h * 0.18)
        for l in lines:
            draw.text((PAD, y_titulo), l, font=font_titulo, fill=(255, 255, 255, 255))
            y_titulo += int(W * 0.052) + 6

        # ── Subtítulo ─────────────────────────────────────────────────────────
        y_sub = y_titulo + 8
        # Wrap subtítulo
        words_s = subtitulo.split()
        lines_s, line_s = [], ""
        for w in words_s:
            test = (line_s + " " + w).strip()
            if draw.textlength(test, font=font_sub) <= W - PAD * 2:
                line_s = test
            else:
                if line_s:
                    lines_s.append(line_s)
                line_s = w
        if line_s:
            lines_s.append(line_s)
        for l in lines_s[:2]:
            draw.text((PAD, y_sub), l, font=font_sub, fill=(*hex_rgb(acento_color)[:3], 230))
            y_sub += int(W * 0.034) + 4

        # ── Logo esquina superior derecha del overlay ─────────────────────────
        if logo_url:
            try:
                logo_resp = req.get(logo_url, timeout=15)
                logo_resp.raise_for_status()
                logo = Image.open(BytesIO(logo_resp.content)).convert("RGBA")
                logo_w = min(int(W * 0.14), 150)
                logo_h_r = int(logo.height * (logo_w / logo.width))
                logo = logo.resize((logo_w, logo_h_r), Image.LANCZOS)
                lx = W - logo_w - PAD
                ly = overlay_y + int((overlay_h - logo_h_r) * 0.35)
                img.paste(logo, (lx, ly), logo)
            except Exception:
                pass

        output = BytesIO()
        img.convert("RGB").save(output, format="PNG")
        return base64.b64encode(output.getvalue()).decode()
    except Exception:
        return base64_img


def _overlay_logo(base64_img: str, logo_url: str) -> str:
    """Descarga logo y lo superpone en esquina inferior derecha. Retorna base64 PNG."""
    try:
        img = Image.open(BytesIO(base64.b64decode(base64_img))).convert("RGBA")
        logo_resp = req.get(logo_url, timeout=15)
        logo_resp.raise_for_status()
        logo = Image.open(BytesIO(logo_resp.content)).convert("RGBA")
        logo_w = min(int(img.width * 0.15), 200)
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        padding = 20
        pos = (img.width - logo_w - padding, img.height - logo_h - padding)
        img.paste(logo, pos, logo)
        output = BytesIO()
        img.convert("RGB").save(output, format="PNG")
        return base64.b64encode(output.getvalue()).decode()
    except Exception:
        return base64_img


def _publicar_instagram(imagen_url: str, caption: str, ig_id: str, token: str) -> dict:
    """Crea container + publica en Instagram Business."""
    if not ig_id or not token:
        return {"success": False, "error": "Falta ig_id o token_de_acceso"}
    try:
        r1 = req.post(
            f"https://graph.facebook.com/v22.0/{ig_id}/media",
            params={"access_token": token},
            json={"image_url": imagen_url, "caption": caption},
            timeout=30,
        )
        if not r1.ok:
            return {"success": False, "error": f"{r1.status_code}: {r1.text[:500]}"}

        container_id = r1.json()["id"]
        time.sleep(8)

        r2 = req.post(
            f"https://graph.facebook.com/v22.0/{ig_id}/media_publish",
            params={"access_token": token},
            json={"creation_id": container_id},
            timeout=30,
        )
        if not r2.ok:
            return {"success": False, "error": f"{r2.status_code}: {r2.text[:500]}"}

        return {"success": True, "post_id": r2.json().get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_linkedin_imagen(
    texto: str, imagen_url: str, li_token: str = None, li_person: str = None
) -> dict:
    """Publica post en LinkedIn con imagen. Flujo: register → upload → post."""
    try:
        t = li_token or LINKEDIN_ACCESS_TOKEN
        p = li_person or LINKEDIN_PERSON_ID
        if not t or not p:
            return {"success": False, "error": "Faltan credenciales de LinkedIn"}
        headers = {
            "Authorization": f"Bearer {t}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        person_urn = f"urn:li:person:{p}"
        # Paso 1: Registrar upload
        r1 = req.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=headers,
            json={
                "registerUploadRequest": {
                    "owner": person_urn,
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "serviceRelationships": [
                        {
                            "identifier": "urn:li:userGeneratedContent",
                            "relationshipType": "OWNER",
                        }
                    ],
                }
            },
            timeout=30,
        )
        if not r1.ok:
            return _publicar_linkedin_texto(texto)
        upload_url = r1.json()["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = r1.json()["value"]["asset"]
        # Paso 2: Subir imagen binaria
        img_bytes = req.get(imagen_url, timeout=30).content
        req.put(
            upload_url,
            headers={"Authorization": f"Bearer {t}"},
            data=img_bytes,
            timeout=60,
        )
        # Paso 3: Crear post con imagen
        r3 = req.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json={
                "author": person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": texto},
                        "shareMediaCategory": "IMAGE",
                        "media": [{"status": "READY", "media": asset_urn}],
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            },
            timeout=30,
        )
        if not r3.ok:
            return {"success": False, "error": f"{r3.status_code}: {r3.text[:300]}"}
        return {"success": True, "post_id": r3.json().get("id", "ugc-img")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_linkedin(
    texto: str, imagen_url: str, li_token: str = None, li_person: str = None
) -> dict:
    """Publica en LinkedIn con imagen si está disponible, si no texto solo."""
    if (
        imagen_url
        and (li_token or LINKEDIN_ACCESS_TOKEN)
        and (li_person or LINKEDIN_PERSON_ID)
    ):
        return _publicar_linkedin_imagen(texto, imagen_url, li_token, li_person)
    return _publicar_linkedin_texto(texto, li_token, li_person)


def _get_facebook_page_token(page_id: str, token: str) -> str:
    """Obtiene el Page Access Token desde el User/System User Token."""
    if not page_id or not token:
        return token
    try:
        r = req.get(
            f"https://graph.facebook.com/v22.0/{page_id}",
            params={"fields": "access_token", "access_token": token},
            timeout=15,
        )
        if not r.ok:
            return token
        return r.json().get("access_token", token)
    except Exception:
        return token


def _publicar_facebook(texto: str, imagen_url: str, page_id: str, token: str) -> dict:
    """Publica foto con caption en Facebook Page."""
    if not page_id or not token:
        return {"success": False, "error": "Falta page_id o token_de_acceso"}
    try:
        page_token = _get_facebook_page_token(page_id, token)
        resp = req.post(
            f"https://graph.facebook.com/v22.0/{page_id}/photos",
            params={"access_token": page_token},
            json={"url": imagen_url, "message": texto},
            timeout=30,
        )
        if not resp.ok:
            return {"success": False, "error": f"{resp.status_code}: {resp.text[:500]}"}
        data = resp.json()
        return {"success": True, "post_id": data.get("post_id") or data.get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_linkedin_texto(
    texto: str, li_token: str = None, li_person: str = None
) -> dict:
    """Publica post en LinkedIn via UGC API (v2, sin version header)."""
    try:
        t = li_token or LINKEDIN_ACCESS_TOKEN
        p = li_person or LINKEDIN_PERSON_ID
        if not t or not p:
            return {"success": False, "error": "Faltan credenciales de LinkedIn"}
        headers = {
            "Authorization": f"Bearer {t}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        r = req.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json={
                "author": f"urn:li:person:{p}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": texto},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            },
            timeout=30,
        )
        if not r.ok:
            return {"success": False, "error": f"{r.status_code}: {r.text[:300]}"}
        return {"success": True, "post_id": r.json().get("id", "ugc-post")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_facebook_texto(texto: str, page_id: str, token: str) -> dict:
    """Publica post de solo texto en Facebook Page."""
    if not page_id or not token:
        return {"success": False, "error": "Falta page_id o token_de_acceso"}
    try:
        page_token = _get_facebook_page_token(page_id, token)
        resp = req.post(
            f"https://graph.facebook.com/v22.0/{page_id}/feed",
            params={"access_token": page_token},
            json={"message": texto},
            timeout=30,
        )
        if not resp.ok:
            return {"success": False, "error": f"{resp.status_code}: {resp.text[:500]}"}
        return {"success": True, "post_id": resp.json().get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _notificar_whatsapp(
    mensaje: str,
    numero: str = None,
    evo_url: str = None,
    evo_instance: str = None,
    evo_token: str = None,
) -> dict:
    """Envía notificación vía Evolution API, usando credenciales por cliente si existen o fallbacks."""
    try:
        u = evo_url or EVOLUTION_URL
        i = evo_instance or EVOLUTION_INSTANCE
        t = evo_token or EVOLUTION_API_KEY
        n = numero or WHATSAPP_NOTIFY_NUMBER

        if not u or not i or not t or not n:
            return {
                "success": False,
                "error": "Faltan credenciales de Evolution o número destino.",
            }

        resp = req.post(
            f"{u.rstrip('/')}/message/sendText/{i}",
            headers={"apikey": t},
            json={"number": n, "text": mensaje},
            timeout=15,
        )
        return {"success": resp.status_code < 300}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _limpiar_texto_post(texto: str) -> str:
    """Elimina encabezados, markdown y elementos que no se ven bien en redes sociales."""
    # Quitar intro tipo "Aquí tienes los 3 posts..."
    texto = re.sub(
        r"^.*(Aquí tienes|Here are|posts únicos|separados).*\n+",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    # Quitar separadores markdown ---
    texto = re.sub(r"^-{3,}\s*\n", "", texto, flags=re.MULTILINE)
    # Quitar encabezados tipo "### **1. INSTAGRAM**", "**1. INSTAGRAM**", "1. INSTAGRAM:", etc.
    texto = re.sub(
        r"^#{0,6}\s*\*{0,2}\s*\d+\.\s*\*{0,2}\s*[A-ZÁÉÍÓÚÑ]+\s*\*{0,2}:?\*{0,2}\s*\n+",
        "",
        texto,
        flags=re.MULTILINE,
    )
    # Quitar negritas **texto** → texto
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto, flags=re.DOTALL)
    # Quitar viñetas markdown (* al inicio de línea)
    texto = re.sub(r"^\*\s+", "", texto, flags=re.MULTILINE)
    # Quitar itálicas sueltas *texto* → texto
    texto = re.sub(r"\*([^\n*]+?)\*", r"\1", texto)
    # Quitar negritas con guión bajo __texto__ → texto
    texto = re.sub(r"__(.+?)__", r"\1", texto, flags=re.DOTALL)
    return texto.strip()


# ─────────────────────────────────────────────────────────────────────────────
# POST /social/publicar-completo  — endpoint agéntico maestro
# ─────────────────────────────────────────────────────────────────────────────


class CredencialesCliente(BaseModel):
    meta_access_token: str = ""
    fb_page_id: str = ""
    ig_account_id: str = ""
    linkedin_access_token: str = ""
    linkedin_person_id: str = ""
    whatsapp_numero_notificacion: str = ""
    evolution_api_url: str = ""
    evolution_instance_name: str = ""
    evolution_instance_token: str = ""


class DatosPublicarCompleto(BaseModel):
    cliente_id: str = ""
    datos_marca: dict  # JSON plano del registro de Airtable
    credenciales: CredencialesCliente = None


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
    rotacion = _get_tema_del_dia(industria=marca.get("Industria", ""))
    tema = rotacion["tema"]
    angulo = rotacion["angulo"]
    idea_central = rotacion["idea_central"]

    # ── 1. Generar textos IA ─────────────────────────────────────────────────
    try:
        prompt_txt = f"""Eres el Copywriter jefe de una agencia de automatizaciones IA para LATAM.

BRANDBOOK:
- Industria: {marca.get("Industria", "Automatización IA")}
- Servicio: {marca.get("Servicio Principal", "Automatizaciones con IA para negocios")}
- Público: {marca.get("Público Objetivo", "Dueños de restaurantes, bares y PyMEs que quieren modernizar sus operaciones con IA — WhatsApp, CRM, agendamiento, redes sociales")}
- Tono de voz: {marca.get("Tono de Voz", "Humano, cercano, directo y experto")}
- RESTRICCIONES: {marca.get("Reglas Estrictas") or marca.get("Reglas Estrictas (Lo que NO debe hacer)") or "Nunca prometer resultados garantizados. Nada de spam."}

TEMA DEL DÍA: {tema}
ÁNGULO: {angulo}
IDEA CENTRAL: {idea_central}

FORMATO (OBLIGATORIO):
- PROHIBIDO usar markdown: sin **, sin *, sin #, sin __, sin guiones como viñetas. Solo texto plano.
- Las viñetas o listas se escriben con emojis al inicio de línea, no con asteriscos.

FILOSOFÍA DE CONTENIDO (OBLIGATORIA):
- SIEMPRE aportar valor real y accionable: el lector debe llevarse algo útil.
- Nunca spam, nunca clickbait vacío, nunca hipérboles sin sustento.
- El CTA es una invitación natural — nunca agresivo ni desesperado.
- NUNCA uses nombres propios de personas — habla siempre como la marca {marca.get("Nombre Comercial", "la agencia")}, de forma genérica.

Crea 3 posts únicos y diferenciados. Separa EXACTAMENTE con: |||

1. INSTAGRAM: Hook irresistible en primera línea, viñetas con emojis con tips prácticos y accionables, 150-200 palabras. CTA final: invitar a SEGUIR la cuenta y/o dar LIKE. 6-8 hashtags al final.
|||
2. LINKEDIN: Apertura con dato real o reflexión del sector, desarrollo con insights accionables (problema → solución → resultado), cierre con pregunta que genere debate, 300-400 palabras, máx 2 emojis. CTA final: invitar a CONECTAR y/o COMENTAR con su experiencia. 3-4 hashtags profesionales.
|||
3. FACEBOOK: Storytelling cercano como si hablaras con un amigo emprendedor, incluye un tip útil o historia de transformación real, 200-250 palabras, máx 3 emojis. CTA final: invitar a DAR LIKE, COMPARTIR con alguien que lo necesite y/o SEGUIR la página."""

        texto_raw = _call_gemini_text(prompt_txt, timeout=60)
        partes = texto_raw.split("|||")
        texto_ig = _limpiar_texto_post(partes[0]) if len(partes) > 0 else ""
        texto_li = _limpiar_texto_post(partes[1]) if len(partes) > 1 else ""
        texto_fb = _limpiar_texto_post(partes[2]) if len(partes) > 2 else ""
    except Exception as e:
        return {"status": "error", "paso": "generacion_textos", "mensaje": str(e)}

    # ── 2. Generar imagen con Gemini → subir a Cloudinary ────────────────────
    imagen_url = None
    imagen_error = None
    try:
        # Usar el prompt de imagen del tema rotado (más específico que Airtable)
        prompt_img = rotacion.get(
            "prompt_imagen",
            marca.get(
                "Estilo Visual (Prompt DALL-E/Gemini)",
                "professional automation business flat design colorful no text",
            ),
        )
        b64, mime = _generar_imagen_interna(prompt_img, max_intentos=5, espera=20)
        logo_field = marca.get("Logo", [])
        logo_url = (
            logo_field[0].get("url", "")
            if isinstance(logo_field, list) and logo_field
            else ""
        )
        # Extraer título y subtítulo desde el tema del día
        titulo_img = tema  # ej: "Consejos para comprar lotes en Misiones"
        subtitulo_img = angulo  # ej: "Lo que nadie te cuenta antes de firmar"
        colores_marca = marca.get("Colores de Marca", "") or marca.get("Colores de marca", "")
        b64 = _overlay_texto_marca(
            b64,
            titulo=titulo_img,
            subtitulo=subtitulo_img,
            colores_str=colores_marca,
            logo_url=logo_url,
        )
        imagen_url = _subir_cloudinary(b64, "image/png")
    except Exception as e:
        imagen_error = str(e)
        imagen_url = None

    # ── 3. Preparar credenciales dinámicas (evita cruce de clientes) ──────────
    cliente_id = entrada.cliente_id or marca.get("ID Cliente", "")
    supa_creds = _get_supa_credenciales_by_cliente_id(cliente_id)

    if entrada.credenciales and entrada.credenciales.meta_access_token:
        ig_id = entrada.credenciales.ig_account_id
        page_id = entrada.credenciales.fb_page_id
        token = entrada.credenciales.meta_access_token
        token_li = entrada.credenciales.linkedin_access_token
        person_li = entrada.credenciales.linkedin_person_id
        wa_num = entrada.credenciales.whatsapp_numero_notificacion
        evo_url = entrada.credenciales.evolution_api_url
        evo_instance = entrada.credenciales.evolution_instance_name
        evo_token = entrada.credenciales.evolution_instance_token
    elif supa_creds:
        ig_id = supa_creds.get("ig_account_id", "")
        page_id = supa_creds.get("fb_page_id", "")
        token = supa_creds.get("meta_access_token", "")
        token_li = supa_creds.get("linkedin_access_token", "")
        person_li = supa_creds.get("linkedin_person_id", "")
        wa_num = supa_creds.get("whatsapp_numero_notificacion", "") or supa_creds.get(
            "whatsapp_numero", ""
        )
        evo_url = supa_creds.get("evolution_api_url", "")
        evo_instance = supa_creds.get("evolution_instance_name", "")
        evo_token = supa_creds.get("evolution_instance_token", "")
    else:
        # Fallback de seguridad al global (borrar en prod)
        ig_id = marca.get("IG Business Account ID", IG_BUSINESS_ACCOUNT_ID)
        page_id = marca.get("Facebook Page ID", FACEBOOK_PAGE_ID)
        token = _build_page_token_map().get(page_id) or META_ACCESS_TOKEN
        token_li = None
        person_li = None
        wa_num = None
        evo_url = None
        evo_instance = None
        evo_token = None

    # ── 4. Publicar en las 3 redes ───────────────────────────────────────────
    if imagen_url:
        res_ig = _publicar_instagram(imagen_url, texto_ig, ig_id, token)
        res_li = _publicar_linkedin(texto_li, imagen_url, token_li, person_li)
        res_fb = _publicar_facebook(texto_fb, imagen_url, page_id, token)
    else:
        # Sin imagen: omitir Instagram, publicar texto en LI y FB
        res_ig = {"success": False, "error": f"Sin imagen: {imagen_error}"}
        res_li = _publicar_linkedin_texto(texto_li, token_li, person_li)
        res_fb = _publicar_facebook_texto(texto_fb, page_id, token)

    for red, res in [("Instagram", res_ig), ("LinkedIn", res_li), ("Facebook", res_fb)]:
        if not res.get("success"):
            errores.append(f"{red}: {res.get('error', 'error desconocido')}")

    # ── 5. Notificación WhatsApp ─────────────────────────────────────────────
    redes_ok = [
        r
        for r, v in [("IG ✅", res_ig), ("LI ✅", res_li), ("FB ✅", res_fb)]
        if v.get("success")
    ]
    redes_fail = [
        r
        for r, v in [("IG ❌", res_ig), ("LI ❌", res_li), ("FB ❌", res_fb)]
        if not v.get("success")
    ]

    msg_wa = (
        f"{'✅' if not redes_fail else '⚠️'} *Post completado*\n\n"
        f"📌 *Tema:* {tema}\n"
        f"🎯 *Ángulo:* {angulo}\n\n"
        f"📸 {' · '.join(redes_ok) or 'Sin publicaciones exitosas'}\n"
        + (
            f"🖼️ {imagen_url}\n\n"
            if imagen_url
            else "🖼️ Sin imagen (Gemini no disponible)\n\n"
        )
        + f"📝 {texto_li[:100]}..."
    )
    if redes_fail:
        msg_wa += f"\n\n⚠️ Fallaron: {', '.join(redes_fail)}"

    notif = _notificar_whatsapp(
        mensaje=msg_wa,
        numero=wa_num,
        evo_url=evo_url,
        evo_instance=evo_instance,
        evo_token=evo_token,
    )

    return {
        "status": "success" if not errores else "partial",
        "tema_del_dia": {"tema": tema, "angulo": angulo},
        "imagen_url": imagen_url,
        "publicaciones": {"instagram": res_ig, "linkedin": res_li, "facebook": res_fb},
        "textos": {
            "instagram": texto_ig[:200],
            "linkedin": texto_li[:200],
            "facebook": texto_fb[:200],
        },
        "notificacion_wa": notif,
        "errores": errores,
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /social/publicar-carrusel — 5 slides IG (Lunes a Sábado)
# ─────────────────────────────────────────────────────────────────────────────

_PILARES_CARRUSEL = {
    0: {
        "pilar": "Consejos prácticos",
        "instruccion": "Comparte 4 consejos prácticos y accionables. Slide 1: título impactante del tema. Slides 2-4: un consejo específico por slide. Slide 5: CTA.",
    },
    1: {
        "pilar": "Casos de éxito",
        "instruccion": "Cuenta una historia de transformación (sin nombres reales). Slide 1: el problema inicial. Slide 2: la solución aplicada. Slide 3: los resultados obtenidos. Slide 4: la lección clave. Slide 5: CTA.",
    },
    2: {
        "pilar": "Tendencias del sector",
        "instruccion": "Comparte 4 tendencias actuales relevantes. Slide 1: título con la tendencia principal. Slides 2-4: una tendencia por slide con su impacto. Slide 5: CTA.",
    },
    3: {
        "pilar": "Motivación / mentalidad",
        "instruccion": "Inspira al emprendedor. Slide 1: frase o pregunta impactante. Slides 2-4: reflexiones que profundizan el tema. Slide 5: CTA.",
    },
    4: {
        "pilar": "Servicios (sutil)",
        "instruccion": "Muestra el valor sin vender directamente. Slide 1: el problema común que sufre el público. Slides 2-4: cómo se resuelve y qué cambia (sin precios ni llamados a comprar). Slide 5: CTA sutil.",
    },
    5: {
        "pilar": "Pregunta a la comunidad",
        "instruccion": "Genera conversación. Slide 1: pregunta que invite a reflexionar. Slides 2-4: perspectivas o datos relacionados. Slide 5: invita a comentar.",
    },
}


def _get_pilar_del_dia() -> dict:
    """Retorna el pilar del carrusel según día de la semana (0=Lunes)."""
    return _PILARES_CARRUSEL.get(datetime.now().weekday(), _PILARES_CARRUSEL[0])


def _publicar_carrusel_instagram(
    imagenes_urls: list, caption: str, ig_id: str, token: str
) -> dict:
    """
    Publica carrusel en Instagram.
    Paso 1: container por cada imagen (is_carousel_item=True)
    Paso 2: container CAROUSEL con los IDs
    Paso 3: media_publish
    """
    try:
        media_ids = []
        for url in imagenes_urls:
            r = req.post(
                f"https://graph.facebook.com/v22.0/{ig_id}/media",
                params={"access_token": token},
                json={"image_url": url, "is_carousel_item": True},
                timeout=30,
            )
            r.raise_for_status()
            media_ids.append(r.json()["id"])
            time.sleep(2)

        r2 = req.post(
            f"https://graph.facebook.com/v22.0/{ig_id}/media",
            params={"access_token": token},
            json={"media_type": "CAROUSEL", "children": media_ids, "caption": caption},
            timeout=30,
        )
        r2.raise_for_status()
        carousel_id = r2.json()["id"]

        time.sleep(8)

        r3 = req.post(
            f"https://graph.facebook.com/v22.0/{ig_id}/media_publish",
            params={"access_token": token},
            json={"creation_id": carousel_id},
            timeout=30,
        )
        r3.raise_for_status()
        return {"success": True, "post_id": r3.json().get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


class DatosPublicarCarrusel(BaseModel):
    cliente_id: str = ""
    datos_marca: dict  # JSON plano del registro de Airtable
    credenciales: CredencialesCliente = None


@router.post("/publicar-carrusel")
async def publicar_carrusel(entrada: DatosPublicarCarrusel):
    """
    Genera y publica carrusel de 5 slides en Instagram.
    Pilares rotan Lunes-Sábado automáticamente por día de semana.
    Cada slide: imagen Gemini + logo overlay + texto corto.
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "paso": "init", "mensaje": "Falta GEMINI_API_KEY"}

    marca = entrada.datos_marca
    pilar_info = _get_pilar_del_dia()
    pilar = pilar_info["pilar"]
    instruccion = pilar_info["instruccion"]

    nombre = marca.get("Nombre Comercial", "la marca")
    industria = marca.get("Industria", "negocios")
    publico = marca.get("Público Objetivo", "emprendedores")
    tono = marca.get("Tono de Voz", "cercano y profesional")
    reglas = marca.get("Reglas Estrictas", "")
    estilo = marca.get(
        "Estilo Visual (Prompt DALL-E/Gemini)",
        "modern flat design colorful professional",
    )
    colores = marca.get("Colores de Marca", "")
    cta = marca.get("CTA", "Seguinos para más contenido como este")
    ig_id = marca.get("IG Business Account ID", "")
    numero_wa = marca.get("WhatsApp Notificación", WHATSAPP_NOTIFY_NUMBER)

    if entrada.credenciales and entrada.credenciales.meta_access_token:
        ig_id = entrada.credenciales.ig_account_id
        token = entrada.credenciales.meta_access_token
    else:
        token = _build_page_token_map().get(ig_id, META_ACCESS_TOKEN)

    # ── 1. Generar estructura de 5 slides + captions ─────────────────────────
    try:
        prompt_slides = f"""Eres el Estratega de Contenidos de {nombre}.

BRANDBOOK:
- Industria: {industria}
- Público objetivo: {publico}
- Tono de voz: {tono}
- RESTRICCIONES ABSOLUTAS: {reglas}
- Colores de marca: {colores}

PILAR DEL DÍA: {pilar}
INSTRUCCIÓN: {instruccion}

Vas a crear el contenido para un carrusel de 5 slides de Instagram.
Cada slide tiene un TÍTULO (máximo 5 palabras, impactante) y un SUBTÍTULO (máximo 8 palabras).
El slide 5 es siempre el CTA: "{cta}"

Responde SOLO con este JSON sin explicaciones adicionales:
{{
  "titulo_carrusel": "Título general del carrusel",
  "slides": [
    {{"numero": 1, "titulo": "MÁXIMO 5 PALABRAS", "subtitulo": "Frase corta de apoyo"}},
    {{"numero": 2, "titulo": "...", "subtitulo": "..."}},
    {{"numero": 3, "titulo": "...", "subtitulo": "..."}},
    {{"numero": 4, "titulo": "...", "subtitulo": "..."}},
    {{"numero": 5, "titulo": "{cta}", "subtitulo": "Seguinos para más"}}
  ],
  "caption_instagram": "Caption IG: hook en línea 1, resumen del carrusel, invitación a guardar/seguir, 6-8 hashtags al final. 150-200 palabras.",
  "caption_linkedin": "Caption LinkedIn: reflexión profesional, 200-300 palabras, 3-4 hashtags."
}}"""

        raw = _call_gemini_text(prompt_slides, timeout=60, json_mode=True)
        raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return {
                "status": "error",
                "paso": "generar_slides",
                "mensaje": "Gemini no devolvió JSON válido",
            }
        slides_data = json.loads(match.group(0))
    except Exception as e:
        return {"status": "error", "paso": "generar_slides", "mensaje": str(e)}

    # ── 2. Gemini genera el SLIDE COMPLETO (diseño + texto + gráfico) ────────
    logo_field = marca.get("Logo", [])
    logo_url = (
        logo_field[0].get("url", "")
        if isinstance(logo_field, list) and logo_field
        else ""
    )

    imagenes_urls = []
    errores_img = []

    _, acento_hex = _extraer_colores_marca(colores)

    for slide in slides_data.get("slides", []):
        titulo_slide = slide.get("titulo", "")
        subtitulo_slide = slide.get("subtitulo", "")
        num = slide.get("numero", 1)

        # Gemini solo genera una imagen limpia (sin texto)
        slide_prompt = f"""Generate a high-quality, professional image representing: {titulo_slide} for {industria} ({pilar}).
Style: {estilo}.
Warm, realistic photography or clean illustration. Professional business environment.
Show real people working, a cozy office, hands typing on a laptop, or a friendly business meeting.
CRITICAL: NO text, NO numbers, NO letters, NO words, NO spelling of any kind anywhere in the image. Just the visual scene."""

        try:
            # raw_prompt=False para que agregue la instrucción anti-texto estándar
            b64, mime = _generar_imagen_interna(
                slide_prompt, max_intentos=5, espera=20, raw_prompt=False
            )

            # Usamos el dibujado en Python (Pillow) para tener texto 100% perfecto, sin faltas ortográficas
            b64_final = _crear_slide_carrusel(
                base64_img=b64,
                titulo=titulo_slide,
                subtitulo=subtitulo_slide,
                color_acento=acento_hex,
                logo_url=logo_url,
                numero_slide=num,
            )

            imagenes_urls.append(_subir_cloudinary(b64_final, "image/png"))
        except Exception as e:
            errores_img.append(f"Slide {num}: {str(e)}")
            imagenes_urls.append(None)

    imagenes_validas = [u for u in imagenes_urls if u]

    if len(imagenes_validas) < 2:
        return {
            "status": "error",
            "paso": "generar_imagenes",
            "mensaje": f"Solo {len(imagenes_validas)} imágenes generadas. Mínimo 2 para carrusel.",
            "errores": errores_img,
        }

    # ── 3. Publicar carrusel en Instagram ─────────────────────────────────────
    caption_ig = slides_data.get("caption_instagram", "")
    res_ig = {"success": False, "error": "ig_id no configurado"}
    if ig_id and token:
        res_ig = _publicar_carrusel_instagram(
            imagenes_validas, caption_ig, ig_id, token
        )

    # ── 4. Notificar WhatsApp ─────────────────────────────────────────────────
    _notificar_whatsapp(
        f"{'✅' if res_ig.get('success') else '⚠️'} *Carrusel publicado*\n\n"
        f"📌 *Pilar:* {pilar}\n"
        f"🖼️ *Slides:* {len(imagenes_validas)}/5\n"
        f"📸 Instagram: {'✅' if res_ig.get('success') else '❌ ' + res_ig.get('error', '')[:60]}\n\n"
        f"📝 {slides_data.get('titulo_carrusel', '')}",
        numero=numero_wa,
    )

    return {
        "status": "success" if res_ig.get("success") else "partial",
        "pilar_del_dia": pilar,
        "titulo_carrusel": slides_data.get("titulo_carrusel", ""),
        "slides_generados": len(imagenes_validas),
        "imagenes_urls": imagenes_urls,
        "publicaciones": {"instagram": res_ig},
        "captions": {
            "instagram": caption_ig[:200],
            "linkedin": slides_data.get("caption_linkedin", "")[:200],
        },
        "errores_imagen": errores_img,
    }


# ─────────────────────────────────────────────────────────────────────────────
# META WEBHOOK — Verificación + Respuesta a comentarios
# ─────────────────────────────────────────────────────────────────────────────

META_WEBHOOK_VERIFY_TOKEN = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_ID = os.environ.get("AIRTABLE_TABLE_ID", "")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")


def _build_page_token_map() -> dict:
    """Construye mapa {page_id: token} desde env vars. Cliente principal + CLIENT_N_*"""
    mapa = {}
    # Cliente principal (env vars base)
    for pid in [
        os.environ.get("FACEBOOK_PAGE_ID", ""),
        os.environ.get("IG_BUSINESS_ACCOUNT_ID", ""),
    ]:
        if pid:
            mapa[pid] = os.environ.get("META_ACCESS_TOKEN", "")
    # Clientes adicionales: CLIENT_2_PAGE_ID, CLIENT_2_IG_ID, CLIENT_2_META_TOKEN, etc.
    for i in range(2, 50):
        page_id = os.environ.get(f"CLIENT_{i}_PAGE_ID", "")
        ig_id = os.environ.get(f"CLIENT_{i}_IG_ID", "")
        token = os.environ.get(f"CLIENT_{i}_META_TOKEN", "")
        if not page_id and not ig_id:
            continue
        if page_id:
            mapa[page_id] = token
        if ig_id:
            mapa[ig_id] = token
    return mapa


def _get_page_token(page_id: str, user_token: str) -> str:
    """Intercambia user token por page access token de Facebook."""
    try:
        resp = req.get(
            f"https://graph.facebook.com/v22.0/{page_id}",
            params={"fields": "access_token", "access_token": user_token},
            timeout=10,
        )
        return resp.json().get("access_token", user_token)
    except Exception:
        return user_token


# ── Consultas a Supabase y Airtable en directo ──


def _get_supa_credenciales_by_page(page_id: str) -> dict:
    """Busca dinámicamente el cliente en Supabase por su FB Page ID o IG ID"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {}
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/clientes"
    params = {
        "select": "*",
        "or": f"(fb_page_id.eq.{page_id},ig_account_id.eq.{page_id})",
    }
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        resp = req.get(url, params=params, headers=headers, timeout=5)
        return resp.json()[0] if resp.json() else {}
    except:
        return {}


def _get_supa_credenciales_by_cliente_id(cliente_id: str) -> dict:
    """Busca dinámicamente el cliente en Supabase por cliente_id."""
    if not SUPABASE_URL or not SUPABASE_KEY or not cliente_id:
        return {}
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/clientes"
    params = {"select": "*", "cliente_id": f"eq.{cliente_id}"}
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        resp = req.get(url, params=params, headers=headers, timeout=5)
        return resp.json()[0] if resp.json() else {}
    except:
        return {}


def _get_cliente_por_page_id(page_id: str, airtable_base_id: str = "", airtable_table_id: str = "") -> dict:
    """Busca el cliente en su propia base de Airtable."""
    base = airtable_base_id or AIRTABLE_BASE_ID
    table = airtable_table_id or AIRTABLE_TABLE_ID
    if not base or not table or not AIRTABLE_TOKEN:
        return {}
    try:
        url = f"https://api.airtable.com/v0/{base}/{table}"
        formula = f"OR({{IG Business Account ID}}='{page_id}',{{Facebook Page ID}}='{page_id}')"
        resp = req.get(
            url,
            headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"},
            params={"filterByFormula": formula},
            timeout=10,
        )
        records = resp.json().get("records", [])
        return records[0].get("fields", {}) if records else {}
    except Exception as e:
        print(f"[AIRTABLE] ERROR: {e}", flush=True)
        return {}


def _responder_comentario(
    comentario_id: str, texto: str, cliente: dict, page_id: str = "", token: str = ""
) -> dict:
    """Genera respuesta con Gemini y la publica como reply al comentario."""
    nombre = cliente.get("Nombre Comercial", "la agencia")
    tono = cliente.get("Tono de Voz", "cercano y profesional")
    servicio = cliente.get("Industria", cliente.get("Servicio Principal", "automatización con IA"))
    reglas = cliente.get("Reglas Estrictas (Lo que NO debe hacer)", "")
    cta = cliente.get("CTA", "escribinos un DM")
    if not token:
        token_map = _build_page_token_map()
        token = token_map.get(page_id, META_ACCESS_TOKEN)

    # ── Guardrail 1: detección de prompt injection en el comentario ──────────
    if detect_injection(texto, worker="social"):
        return {"success": True, "respuesta": FALLBACK_SOCIAL, "_guardrail": "injection_detected"}

    # ── Guardrail 2: sanitizar el comentario antes de insertarlo en el prompt ─
    texto_safe = sanitize_for_llm(texto, context="comentario_usuario")

    prompt = (
        f"Sos el community manager de {nombre}.\n"
        f"TONO: {tono}\n"
        f"NEGOCIO: {servicio}\n"
        f"RESTRICCIONES: {reglas}\n\n"
        f"Alguien dejó este comentario en tu post:\n{texto_safe}\n\n"
        f"Escribí UNA respuesta (máximo 3 líneas) que:\n"
        f"1. Agradezca de forma genuina y específica al comentario\n"
        f"2. Dé UN consejo o insight concreto relacionado al negocio\n"
        f"3. Cierre con: {cta}\n\n"
        f"USA emojis naturales (máximo 2). NO uses asteriscos ni markdown. Solo texto plano."
    )

    try:
        gemini_resp = req.post(
            GEMINI_TEXT_URL,
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        respuesta = gemini_resp.json()["candidates"][0]["content"]["parts"][0][
            "text"
        ].strip()
    except Exception:
        respuesta = FALLBACK_SOCIAL

    # ── Guardrail 3: validar output antes de publicar ─────────────────────────
    if not validate_output(respuesta, worker="social"):
        respuesta = FALLBACK_SOCIAL

    try:
        # Facebook usa /{comment_id}/comments, Instagram usa /{comment_id}/replies
        endpoint = "comments" if "_" in comentario_id else "replies"
        reply = req.post(
            f"https://graph.facebook.com/v22.0/{comentario_id}/{endpoint}",
            params={"message": respuesta, "access_token": token},
            timeout=15,
        )
        print(
            f"[REPLY] endpoint={endpoint} status={reply.status_code} body={reply.text[:200]}",
            flush=True,
        )
        return {"success": reply.ok, "respuesta": respuesta}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/meta-webhook")
async def meta_webhook_verificar(request: Request):
    """Verificación del webhook de Meta."""
    params = dict(request.query_params)
    if params.get("hub.verify_token") == META_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Token inválido", status_code=403)


@router.post("/meta-webhook")
async def meta_webhook_eventos(request: Request):
    """Recibe eventos de comentarios de Instagram y Facebook."""
    try:
        body = await request.json()
        print(f"[WEBHOOK] BODY_RAW={json.dumps(body)[:500]}", flush=True)
        entry = (body.get("entry") or [{}])[0]
        page_id = entry.get("id", "")

        # ── 1. Cargar credenciales desde Supabase ──
        supa_creds = _get_supa_credenciales_by_page(page_id)
        token_cliente = supa_creds.get("meta_access_token", "")
        base_airtable = supa_creds.get("airtable_base_id", "")
        table_airtable = supa_creds.get("airtable_table_id", "") or AIRTABLE_TABLE_ID

        # ── 2. Cargar Brandbook desde su Airtable aislado ──
        cliente = _get_cliente_por_page_id(page_id, base_airtable, table_airtable) if page_id else {}

        # IDs propios para evitar responder a nuestros propios comentarios (anti-loop)
        own_ids = set()
        token_map = _build_page_token_map()
        own_ids.update(token_map.keys())  # todos los fallback ids
        if page_id:
            own_ids.add(page_id)

        print(
            f"[WEBHOOK] page_id={page_id!r} en_supabase={bool(supa_creds)} cliente_found={bool(cliente)}",
            flush=True,
        )

        for change in entry.get("changes", []):
            field = change.get("field", "")
            value = change.get("value", {})
            print(
                f"[WEBHOOK] field={field!r} item={value.get('item')!r} verb={value.get('verb')!r}",
                flush=True,
            )

            # Instagram comment
            if field == "comments":
                texto = value.get("text", "")
                comentario_id = value.get("id", "")
                from_id = value.get("from", {}).get("id", "")

                # ⚠️ ANTI-LOOP: ignorar comentarios hechos por nosotros mismos
                if from_id and from_id in own_ids:
                    print(f"[WEBHOOK] IG SKIP own comment from={from_id!r}", flush=True)
                    continue

                print(
                    f"[WEBHOOK] IG comment id={comentario_id!r} from={from_id!r} texto={texto[:40]!r}",
                    flush=True,
                )
                if texto and len(texto) >= 3 and comentario_id:
                    result = _responder_comentario(
                        comentario_id, texto, cliente or {}, page_id, token=token_cliente
                    )
                    print(f"[WEBHOOK] reply_result={result}", flush=True)

            # Facebook page comment
            elif field == "feed":
                if value.get("item") == "comment" and value.get("verb") == "add":
                    comentario_id = value.get("comment_id", "")
                    texto = value.get("message", "")
                    from_id = value.get("from", {}).get("id", "")

                    # ⚠️ ANTI-LOOP: ignorar comentarios hechos por la página misma
                    if from_id and from_id in own_ids:
                        print(
                            f"[WEBHOOK] FB SKIP own comment from={from_id!r}",
                            flush=True,
                        )
                        continue

                    # También ignorar si Meta dice que fue creado por la página
                    if value.get("created_by") == "page":
                        print(f"[WEBHOOK] FB SKIP created_by=page", flush=True)
                        continue

                    user_tkn = token_cliente or token_map.get(
                        page_id, META_ACCESS_TOKEN
                    )
                    page_tkn = _get_page_token(page_id, user_tkn)
                    # Facebook no envía el texto en el webhook — hay que buscarlo via API
                    if not texto and comentario_id:
                        try:
                            r = req.get(
                                f"https://graph.facebook.com/v22.0/{comentario_id}",
                                params={
                                    "fields": "message,from",
                                    "access_token": page_tkn,
                                },
                                timeout=10,
                            )
                            rj = r.json()
                            texto = rj.get("message", "")
                            # Segundo check anti-loop con el from del fetch
                            fetched_from = rj.get("from", {}).get("id", "")
                            if fetched_from and fetched_from in own_ids:
                                print(
                                    f"[WEBHOOK] FB SKIP own comment (fetched) from={fetched_from!r}",
                                    flush=True,
                                )
                                continue
                            print(f"[WEBHOOK] FB fetch raw={str(rj)[:200]}", flush=True)
                        except Exception as fe:
                            print(f"[WEBHOOK] FB fetch error: {fe}", flush=True)
                    print(
                        f"[WEBHOOK] FB comment id={comentario_id!r} from={from_id!r} texto={texto[:40]!r}",
                        flush=True,
                    )
                    if texto and len(texto) >= 3 and comentario_id:
                        result = _responder_comentario(
                            comentario_id, texto, cliente or {}, page_id, token=page_tkn
                        )
                        print(f"[WEBHOOK] reply_result={result}", flush=True)

    except Exception as e:
        print(f"[WEBHOOK] ERROR: {e}", flush=True)

    return PlainTextResponse("EVENT_RECEIVED", status_code=200)
