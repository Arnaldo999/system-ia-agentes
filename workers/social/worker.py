import os
import re
import json
import time
import base64
import requests as req
from io import BytesIO
from datetime import datetime
from PIL import Image
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
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

def _generar_imagen_interna(prompt: str, max_intentos: int = 4, espera: int = 25, raw_prompt: bool = False):
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
    texto = re.sub(r'\*+', '', texto)
    texto = re.sub(r'#+\s*', '', texto)
    texto = re.sub(r'_+', '', texto)
    texto = re.sub(r'`+', '', texto)
    return texto.strip()


def _extraer_colores_marca(colores_str: str):
    """
    Extrae colores hex del string de marca.
    Retorna (color_fondo, color_acento): el más oscuro como fondo,
    el más claro/vibrante como acento.
    """
    hexes = re.findall(r'#[0-9A-Fa-f]{6}', colores_str or "")

    def lum(h):
        h = h.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return 0.299 * r + 0.587 * g + 0.114 * b

    if not hexes:
        return "#0A0E1A", "#0099FF"
    ordered = sorted(hexes, key=lum)
    fondo  = ordered[0]
    acento = ordered[-1] if len(ordered) > 1 else "#FFFFFF"
    return fondo, acento


def _crear_slide_carrusel(base64_img: str, titulo: str, subtitulo: str,
                           color_acento: str,
                           logo_url: str = "", numero_slide: int = 0) -> str:
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

        titulo    = _limpiar_markdown(titulo)
        subtitulo = _limpiar_markdown(subtitulo)

        SIZE = 1080
        PAD  = 60

        def hex_rgb(h):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

        acc_rgb = hex_rgb(color_acento)
        TITLE_C = (10, 10, 20)       # negro puro para máximo impacto
        SUB_C   = (80, 85, 100)      # gris oscuro legible
        NUM_C   = acc_rgb

        # ── Canvas blanco limpio ──────────────────────────────────────────────
        canvas = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
        draw   = ImageDraw.Draw(canvas)

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

        # ── TÍTULO GIGANTE (130px Bold, alineado izquierda) ───────────────────
        TEXT_MAX = SIZE - PAD * 2
        font_tit = _get_font(130)
        font_sub = _get_font_regular(58)

        def draw_wrapped(text, font, color, y, max_lines=3, line_spacing=8, align="left"):
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

        # Título empieza bien abajo del número/logo
        text_y = 140
        text_y = draw_wrapped(titulo[:50], font_tit, TITLE_C, text_y,
                              max_lines=2, line_spacing=6, align="left")

        # Subtítulo
        if subtitulo:
            text_y = draw_wrapped(subtitulo[:80], font_sub, SUB_C, text_y + 8,
                                  max_lines=2, line_spacing=6, align="left")

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
        top  = (nh - IMG_H) // 2
        gemini = gemini.crop((left, top, left + IMG_W, top + IMG_H))
        canvas.paste(gemini, (0, IMG_Y))

        # ── Barra inferior acento (14px) ──────────────────────────────────────
        draw.rectangle([(0, SIZE - 14), (SIZE, SIZE)], fill=acc_rgb)

        out = BytesIO()
        canvas.save(out, format="PNG", quality=95)
        return base64.b64encode(out.getvalue()).decode()

    except Exception:
        return base64_img  # fallback sin diseño


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


def _publicar_linkedin_imagen(texto: str, imagen_url: str) -> dict:
    """Publica post en LinkedIn con imagen. Flujo: register → upload → post."""
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        person_urn = f"urn:li:person:{LINKEDIN_PERSON_ID}"
        # Paso 1: Registrar upload
        r1 = req.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=headers,
            json={"registerUploadRequest": {
                "owner": person_urn,
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "serviceRelationships": [{"identifier": "urn:li:userGeneratedContent", "relationshipType": "OWNER"}]
            }},
            timeout=30
        )
        if not r1.ok:
            return _publicar_linkedin_texto(texto)
        upload_url = r1.json()["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = r1.json()["value"]["asset"]
        # Paso 2: Subir imagen binaria
        img_bytes = req.get(imagen_url, timeout=30).content
        req.put(upload_url, headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"}, data=img_bytes, timeout=60)
        # Paso 3: Crear post con imagen
        r3 = req.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json={
                "author": person_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {"com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": texto},
                    "shareMediaCategory": "IMAGE",
                    "media": [{"status": "READY", "media": asset_urn}]
                }},
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
            },
            timeout=30
        )
        if not r3.ok:
            return {"success": False, "error": f"{r3.status_code}: {r3.text[:300]}"}
        return {"success": True, "post_id": r3.json().get("id", "ugc-img")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _publicar_linkedin(texto: str, imagen_url: str) -> dict:
    """Publica en LinkedIn con imagen si está disponible, si no texto solo."""
    if imagen_url and LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID:
        return _publicar_linkedin_imagen(texto, imagen_url)
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


def _notificar_whatsapp(mensaje: str, numero: str = None) -> dict:
    """Envía notificación vía Evolution API. Si no se pasa numero, usa WHATSAPP_NOTIFY_NUMBER."""
    try:
        n = numero or WHATSAPP_NOTIFY_NUMBER
        resp = req.post(
            f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            headers={"apikey": EVOLUTION_API_KEY},
            json={"number": n, "text": mensaje},
            timeout=15
        )
        return {"success": resp.status_code < 300}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _limpiar_texto_post(texto: str) -> str:
    """Elimina encabezados, markdown y elementos que no se ven bien en redes sociales."""
    # Quitar intro tipo "Aquí tienes los 3 posts..."
    texto = re.sub(r'^.*(Aquí tienes|Here are|posts únicos|separados).*\n+', '', texto, flags=re.IGNORECASE)
    # Quitar separadores markdown ---
    texto = re.sub(r'^-{3,}\s*\n', '', texto, flags=re.MULTILINE)
    # Quitar encabezados tipo "### **1. INSTAGRAM**", "**1. INSTAGRAM**", "1. INSTAGRAM:", etc.
    texto = re.sub(r'^#{0,6}\s*\*{0,2}\s*\d+\.\s*\*{0,2}\s*[A-ZÁÉÍÓÚÑ]+\s*\*{0,2}:?\*{0,2}\s*\n+', '', texto, flags=re.MULTILINE)
    # Quitar negritas **texto** → texto
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto, flags=re.DOTALL)
    # Quitar viñetas markdown (* al inicio de línea)
    texto = re.sub(r'^\*\s+', '', texto, flags=re.MULTILINE)
    # Quitar itálicas sueltas *texto* → texto
    texto = re.sub(r'\*([^\n*]+?)\*', r'\1', texto)
    # Quitar negritas con guión bajo __texto__ → texto
    texto = re.sub(r'__(.+?)__', r'\1', texto, flags=re.DOTALL)
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

FORMATO (OBLIGATORIO):
- PROHIBIDO usar markdown: sin **, sin *, sin #, sin __, sin guiones como viñetas. Solo texto plano.
- Las viñetas o listas se escriben con emojis al inicio de línea, no con asteriscos.

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
        logo_field = marca.get("Logo", [])
        logo_url = logo_field[0].get("url", "") if isinstance(logo_field, list) and logo_field else ""
        if logo_url:
            b64 = _overlay_logo(b64, logo_url)
        imagen_url = _subir_cloudinary(b64, "image/png")
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


# ─────────────────────────────────────────────────────────────────────────────
# POST /social/publicar-carrusel — 5 slides IG (Lunes a Sábado)
# ─────────────────────────────────────────────────────────────────────────────

_PILARES_CARRUSEL = {
    0: {"pilar": "Consejos prácticos",      "instruccion": "Comparte 4 consejos prácticos y accionables. Slide 1: título impactante del tema. Slides 2-4: un consejo específico por slide. Slide 5: CTA."},
    1: {"pilar": "Casos de éxito",          "instruccion": "Cuenta una historia de transformación (sin nombres reales). Slide 1: el problema inicial. Slide 2: la solución aplicada. Slide 3: los resultados obtenidos. Slide 4: la lección clave. Slide 5: CTA."},
    2: {"pilar": "Tendencias del sector",   "instruccion": "Comparte 4 tendencias actuales relevantes. Slide 1: título con la tendencia principal. Slides 2-4: una tendencia por slide con su impacto. Slide 5: CTA."},
    3: {"pilar": "Motivación / mentalidad", "instruccion": "Inspira al emprendedor. Slide 1: frase o pregunta impactante. Slides 2-4: reflexiones que profundizan el tema. Slide 5: CTA."},
    4: {"pilar": "Servicios (sutil)",       "instruccion": "Muestra el valor sin vender directamente. Slide 1: el problema común que sufre el público. Slides 2-4: cómo se resuelve y qué cambia (sin precios ni llamados a comprar). Slide 5: CTA sutil."},
    5: {"pilar": "Pregunta a la comunidad", "instruccion": "Genera conversación. Slide 1: pregunta que invite a reflexionar. Slides 2-4: perspectivas o datos relacionados. Slide 5: invita a comentar."},
}


def _get_pilar_del_dia() -> dict:
    """Retorna el pilar del carrusel según día de la semana (0=Lunes)."""
    return _PILARES_CARRUSEL.get(datetime.now().weekday(), _PILARES_CARRUSEL[0])


def _publicar_carrusel_instagram(imagenes_urls: list, caption: str, ig_id: str, token: str) -> dict:
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
                timeout=30
            )
            r.raise_for_status()
            media_ids.append(r.json()["id"])
            time.sleep(2)

        r2 = req.post(
            f"https://graph.facebook.com/v22.0/{ig_id}/media",
            params={"access_token": token},
            json={"media_type": "CAROUSEL", "children": media_ids, "caption": caption},
            timeout=30
        )
        r2.raise_for_status()
        carousel_id = r2.json()["id"]

        time.sleep(8)

        r3 = req.post(
            f"https://graph.facebook.com/v22.0/{ig_id}/media_publish",
            params={"access_token": token},
            json={"creation_id": carousel_id},
            timeout=30
        )
        r3.raise_for_status()
        return {"success": True, "post_id": r3.json().get("id", "")}
    except Exception as e:
        return {"success": False, "error": str(e)}


class DatosPublicarCarrusel(BaseModel):
    datos_marca: dict  # JSON plano del registro de Airtable


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

    nombre   = marca.get("Nombre Comercial", "la marca")
    industria = marca.get("Industria", "negocios")
    publico  = marca.get("Público Objetivo", "emprendedores")
    tono     = marca.get("Tono de Voz", "cercano y profesional")
    reglas   = marca.get("Reglas Estrictas", "")
    estilo   = marca.get("Estilo Visual (Prompt DALL-E/Gemini)", "modern flat design colorful professional")
    colores  = marca.get("Colores de Marca", "")
    cta      = marca.get("CTA", "Seguinos para más contenido como este")
    ig_id    = marca.get("IG Business Account ID", "")
    numero_wa = marca.get("WhatsApp Notificación", WHATSAPP_NOTIFY_NUMBER)
    token    = _build_page_token_map().get(ig_id, META_ACCESS_TOKEN)

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

        raw = _call_gemini_text(prompt_slides, timeout=60)
        raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
        match = re.search(r'\{[\s\S]*\}', raw)
        if not match:
            return {"status": "error", "paso": "generar_slides", "mensaje": "Gemini no devolvió JSON válido"}
        slides_data = json.loads(match.group(0))
    except Exception as e:
        return {"status": "error", "paso": "generar_slides", "mensaje": str(e)}

    # ── 2. Gemini genera el SLIDE COMPLETO (diseño + texto + gráfico) ────────
    logo_field = marca.get("Logo", [])
    logo_url = logo_field[0].get("url", "") if isinstance(logo_field, list) and logo_field else ""

    imagenes_urls = []
    errores_img = []

    for slide in slides_data.get("slides", []):
        titulo_slide = slide.get("titulo", "")
        subtitulo_slide = slide.get("subtitulo", "")
        num = slide.get("numero", 1)

        # Prompt para que Gemini genere el SLIDE DISEÑADO COMPLETO
        slide_prompt = f"""Generate a premium Instagram carousel slide image (square 1080x1080 pixels).

DESIGN LAYOUT (follow this EXACTLY):
- TOP HALF (white/light background, clean and spacious):
  • Top-left corner: the number "{num}." in VERY LARGE bold font, color {colores or 'bright blue'}
  • Center of top half: the title "{titulo_slide}" in EXTREMELY LARGE, BOLD, BLACK text (this must be the dominant element, huge lettering that fills the width)
  • Below the title: "{subtitulo_slide}" in medium gray text, smaller than the title but still clearly readable
  • A thin horizontal accent line in {colores or 'blue'} separating the text area from the image area

- BOTTOM HALF (photo/illustration):
  • A warm, realistic photograph or clean illustration related to: {industria}, {pilar}
  • Style: realistic photography with natural lighting, warm tones, professional business environment
  • Show real people working, a cozy office, hands typing on a laptop, or a friendly business meeting
  • NOT futuristic, NOT sci-fi, NOT neon, NOT cyberpunk — keep it warm, human, and relatable
  • The image should feel approachable and professional, like a real business photo

CRITICAL RULES:
- TEXT SPELLING: Copy the title and subtitle EXACTLY character by character. The text is in SPANISH — write it correctly: "{titulo_slide}" and "{subtitulo_slide}"
- The title text MUST be ENORMOUS — bold black letters that dominate the upper half
- The number "{num}." must be clearly visible in {colores or 'brand color'}
- The design must look like a professional Instagram carousel slide
- Clean, modern, minimalist top half with huge typography
- Warm, realistic image in the bottom half (NO futuristic/sci-fi imagery)
- DO NOT add any extra text, watermarks, or UI elements beyond what is specified"""

        try:
            b64, mime = _generar_imagen_interna(slide_prompt, max_intentos=3, espera=20, raw_prompt=True)
            # Asegurar que sea exactamente 1080x1080
            img = Image.open(BytesIO(base64.b64decode(b64))).convert("RGB")
            if img.size != (1080, 1080):
                img = img.resize((1080, 1080), Image.LANCZOS)
            # Overlay logo en esquina superior derecha si hay
            if logo_url:
                try:
                    logo_resp = req.get(logo_url, timeout=15)
                    logo_resp.raise_for_status()
                    logo_img = Image.open(BytesIO(logo_resp.content)).convert("RGBA")
                    logo_img.thumbnail((120, 120), Image.LANCZOS)
                    lx = 1080 - logo_img.width - 40
                    img_rgba = img.convert("RGBA")
                    img_rgba.paste(logo_img, (lx, 30), logo_img)
                    img = img_rgba.convert("RGB")
                except Exception:
                    pass
            out = BytesIO()
            img.save(out, format="PNG", quality=95)
            b64_final = base64.b64encode(out.getvalue()).decode()
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
            "errores": errores_img
        }

    # ── 3. Publicar carrusel en Instagram ─────────────────────────────────────
    caption_ig = slides_data.get("caption_instagram", "")
    res_ig = {"success": False, "error": "ig_id no configurado"}
    if ig_id and token:
        res_ig = _publicar_carrusel_instagram(imagenes_validas, caption_ig, ig_id, token)

    # ── 4. Notificar WhatsApp ─────────────────────────────────────────────────
    _notificar_whatsapp(
        f"{'✅' if res_ig.get('success') else '⚠️'} *Carrusel publicado*\n\n"
        f"📌 *Pilar:* {pilar}\n"
        f"🖼️ *Slides:* {len(imagenes_validas)}/5\n"
        f"📸 Instagram: {'✅' if res_ig.get('success') else '❌ ' + res_ig.get('error', '')[:60]}\n\n"
        f"📝 {slides_data.get('titulo_carrusel', '')}",
        numero=numero_wa
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
            "linkedin":  slides_data.get("caption_linkedin", "")[:200]
        },
        "errores_imagen": errores_img
    }


# ─────────────────────────────────────────────────────────────────────────────
# META WEBHOOK — Verificación + Respuesta a comentarios
# ─────────────────────────────────────────────────────────────────────────────

META_WEBHOOK_VERIFY_TOKEN = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "SystemIA2026")
AIRTABLE_BASE_ID  = os.environ.get("AIRTABLE_BASE_ID", "appejn9ep8JMLJmPG")
AIRTABLE_TABLE_ID = os.environ.get("AIRTABLE_TABLE_ID", "tblgFvYebZcJaYM07")
AIRTABLE_TOKEN    = os.environ.get("AIRTABLE_TOKEN", "")


def _build_page_token_map() -> dict:
    """Construye mapa {page_id: token} desde env vars. Cliente principal + CLIENT_N_*"""
    mapa = {}
    # Cliente principal (env vars base)
    for pid in [os.environ.get("FACEBOOK_PAGE_ID", ""), os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")]:
        if pid:
            mapa[pid] = os.environ.get("META_ACCESS_TOKEN", "")
    # Clientes adicionales: CLIENT_2_PAGE_ID, CLIENT_2_IG_ID, CLIENT_2_META_TOKEN, etc.
    for i in range(2, 50):
        page_id = os.environ.get(f"CLIENT_{i}_PAGE_ID", "")
        ig_id   = os.environ.get(f"CLIENT_{i}_IG_ID", "")
        token   = os.environ.get(f"CLIENT_{i}_META_TOKEN", "")
        if not page_id and not ig_id:
            break
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
            timeout=10
        )
        return resp.json().get("access_token", user_token)
    except Exception:
        return user_token


def _get_cliente_por_page_id(page_id: str) -> dict:
    """Busca el cliente en Airtable por IG Business Account ID o Facebook Page ID."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
        formula = f"OR({{IG Business Account ID}}='{page_id}',{{Facebook Page ID}}='{page_id}')"
        resp = req.get(url, headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"},
                       params={"filterByFormula": formula}, timeout=10)
        records = resp.json().get("records", [])
        print(f"[AIRTABLE] page_id={page_id!r} status={resp.status_code} records={len(records)}", flush=True)
        return records[0].get("fields", {}) if records else {}
    except Exception as e:
        print(f"[AIRTABLE] ERROR: {e}", flush=True)
        return {}


def _responder_comentario(comentario_id: str, texto: str, cliente: dict, page_id: str = "", token: str = "") -> dict:
    """Genera respuesta con Gemini y la publica como reply al comentario."""
    nombre   = cliente.get("Nombre Comercial", "la agencia")
    tono     = cliente.get("Tono de Voz", "cercano y profesional")
    servicio = cliente.get("Servicio Principal", "automatización con IA")
    if not token:
        token_map = _build_page_token_map()
        token = token_map.get(page_id, META_ACCESS_TOKEN)

    prompt = (
        f"Sos el community manager de {nombre}. "
        f"Alguien comentó en tu post: \"{texto}\"\n\n"
        f"Escribí UNA respuesta (máximo 3 líneas) en tono {tono} que:\n"
        f"1. Agradezca brevemente\n"
        f"2. Dé UN tip accionable relacionado al negocio ({servicio})\n"
        f"3. Invite a escribir un DM para más info\n\n"
        f"USA emojis naturales. NO uses asteriscos ni markdown. Solo texto plano."
    )

    try:
        gemini_resp = req.post(
            GEMINI_TEXT_URL,
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30
        )
        respuesta = gemini_resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        respuesta = f"¡Gracias por tu comentario! 💡 La automatización puede transformar tu negocio. Escribinos un DM y te contamos cómo."

    try:
        # Facebook usa /{comment_id}/comments, Instagram usa /{comment_id}/replies
        endpoint = "comments" if "_" in comentario_id else "replies"
        reply = req.post(
            f"https://graph.facebook.com/v22.0/{comentario_id}/{endpoint}",
            params={"message": respuesta, "access_token": token},
            timeout=15
        )
        print(f"[REPLY] endpoint={endpoint} status={reply.status_code} body={reply.text[:200]}", flush=True)
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
        entry = (body.get("entry") or [{}])[0]
        page_id = entry.get("id", "")
        cliente = _get_cliente_por_page_id(page_id) if page_id else {}

        # IDs propios para evitar responder a nuestros propios comentarios (anti-loop)
        own_ids = set()
        token_map = _build_page_token_map()
        own_ids.update(token_map.keys())  # todos los page_id e ig_id conocidos
        if page_id:
            own_ids.add(page_id)

        print(f"[WEBHOOK] page_id={page_id!r} cliente_found={bool(cliente)} own_ids_count={len(own_ids)}", flush=True)

        for change in entry.get("changes", []):
            field = change.get("field", "")
            value = change.get("value", {})
            print(f"[WEBHOOK] field={field!r} item={value.get('item')!r} verb={value.get('verb')!r}", flush=True)

            # Instagram comment
            if field == "comments":
                texto = value.get("text", "")
                comentario_id = value.get("id", "")
                from_id = value.get("from", {}).get("id", "")

                # ⚠️ ANTI-LOOP: ignorar comentarios hechos por nosotros mismos
                if from_id and from_id in own_ids:
                    print(f"[WEBHOOK] IG SKIP own comment from={from_id!r}", flush=True)
                    continue

                print(f"[WEBHOOK] IG comment id={comentario_id!r} from={from_id!r} texto={texto[:40]!r}", flush=True)
                if texto and len(texto) >= 3 and comentario_id and cliente:
                    result = _responder_comentario(comentario_id, texto, cliente, page_id)
                    print(f"[WEBHOOK] reply_result={result}", flush=True)

            # Facebook page comment
            elif field == "feed":
                if value.get("item") == "comment" and value.get("verb") == "add":
                    comentario_id = value.get("comment_id", "")
                    texto = value.get("message", "")
                    from_id = value.get("from", {}).get("id", "")

                    # ⚠️ ANTI-LOOP: ignorar comentarios hechos por la página misma
                    if from_id and from_id in own_ids:
                        print(f"[WEBHOOK] FB SKIP own comment from={from_id!r}", flush=True)
                        continue

                    # También ignorar si Meta dice que fue creado por la página
                    if value.get("created_by") == "page":
                        print(f"[WEBHOOK] FB SKIP created_by=page", flush=True)
                        continue

                    user_tkn = token_map.get(page_id, META_ACCESS_TOKEN)
                    page_tkn = _get_page_token(page_id, user_tkn)
                    # Facebook no envía el texto en el webhook — hay que buscarlo via API
                    if not texto and comentario_id:
                        try:
                            r = req.get(
                                f"https://graph.facebook.com/v22.0/{comentario_id}",
                                params={"fields": "message,from", "access_token": page_tkn},
                                timeout=10
                            )
                            rj = r.json()
                            texto = rj.get("message", "")
                            # Segundo check anti-loop con el from del fetch
                            fetched_from = rj.get("from", {}).get("id", "")
                            if fetched_from and fetched_from in own_ids:
                                print(f"[WEBHOOK] FB SKIP own comment (fetched) from={fetched_from!r}", flush=True)
                                continue
                            print(f"[WEBHOOK] FB fetch raw={str(rj)[:200]}", flush=True)
                        except Exception as fe:
                            print(f"[WEBHOOK] FB fetch error: {fe}", flush=True)
                    print(f"[WEBHOOK] FB comment id={comentario_id!r} from={from_id!r} texto={texto[:40]!r}", flush=True)
                    if texto and len(texto) >= 3 and comentario_id and cliente:
                        result = _responder_comentario(comentario_id, texto, cliente, page_id, token=page_tkn)
                        print(f"[WEBHOOK] reply_result={result}", flush=True)

    except Exception as e:
        print(f"[WEBHOOK] ERROR: {e}", flush=True)

    return PlainTextResponse("EVENT_RECEIVED", status_code=200)
