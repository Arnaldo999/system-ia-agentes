"""
Worker — Creaciones Lau (Evolution API + Airtable + Cloudinary + Gemini)
=========================================================================
Bot WhatsApp para emprendimiento de manualidades y decoraciones de Lau.

Modos:
  - CLIENTE: menú por categoría → muestra fotos → deriva a Lau
  - ADMIN: activado con "CARGAR <PIN>" → Lau sube fotos con descripción

Endpoints:
  POST /clientes/system-ia/lau/whatsapp   ← Evolution API webhook
  GET  /clientes/system-ia/lau/config     ← Diagnóstico
"""

import os
import re
import logging
import requests
import cloudinary
import cloudinary.uploader
from datetime import datetime
from google import genai
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLIENTE_SLUG = "lau"
CLIENTE_TAG  = "Creaciones Lau"

ADMIN_PIN          = os.environ.get("LAU_ADMIN_PIN", "1234")
NUMERO_LAU         = os.environ.get("LAU_NUMERO_ASESOR", "543765389823")  # para derivar clientes

GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
EVOLUTION_API_URL  = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY  = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("LAU_EVOLUTION_INSTANCE", "Lau Emprende")

AIRTABLE_TOKEN     = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID   = os.environ.get("LAU_AIRTABLE_BASE_ID", "app4WvGPank8QixTU")
TABLE_PRODUCTOS    = os.environ.get("LAU_TABLE_PRODUCTOS", "tblhCGfMLhaOZaXqe")
TABLE_LEADS        = os.environ.get("LAU_TABLE_LEADS", "tblJLwmnhfihzybFz")

CLOUDINARY_CLOUD   = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_KEY     = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_SECRET  = os.environ.get("CLOUDINARY_API_SECRET", "")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD,
    api_key=CLOUDINARY_KEY,
    api_secret=CLOUDINARY_SECRET,
)

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(
    prefix=f"/clientes/system-ia/{CLIENTE_SLUG}",
    tags=[CLIENTE_TAG],
)

# sesiones activas — clave: telefono, valor: dict con estado y modo
SESIONES: dict[str, dict] = {}

CATEGORIAS = {
    "1": "Escolar",
    "2": "Fiestas y Eventos",
    "3": "Papeleria Creativa",
    "4": "Diseños e Impresiones",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MENSAJES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MSG_BIENVENIDA = """✨ ¡Hola! Bienvenido a *Creaciones Lau* 🎨

Hacemos manualidades y decoraciones para que tus momentos sean únicos 💫

¿Qué te interesa ver?

1️⃣ Manualidades escolares (carpetas, maquetas, láminas)
2️⃣ Fiestas y eventos (decoración con telas y globos, souvenirs, centros de mesa, cajas sorpresa)
3️⃣ Papelería creativa (invitaciones, tarjetería, cuadernos, stickers)
4️⃣ Diseños e Impresiones

Respondé con el número de tu opción 😊"""

MSG_ADMIN_ELEGIR_CATEGORIA = """✅ *Modo carga activado*

¿A qué categoría pertenece el trabajo?

1️⃣ Escolar
2️⃣ Fiestas y Eventos
3️⃣ Papelería Creativa
4️⃣ Diseños e Impresiones

Respondé con el número 👆"""

MSG_SIN_PRODUCTOS = """Todavía no hay trabajos cargados en esa categoría.
¡Pero podemos hacerlo a medida para vos! 🎨

¿Querés hablar con Lau directamente?
Respondé *SI* y te paso su contacto."""

MSG_DERIVAR = """¡Genial! 🌟 Lau te va a atender personalmente.

📲 Escribile por acá: https://wa.me/543765389823

Contale qué necesitás y ella te ayuda a crear algo único 💫"""

MSG_ADMIN_BIENVENIDA = """✅ *Modo carga activado*

Mandame la foto con una descripción del trabajo.
Ejemplo: _"Torta Peppa para cumple de 3 años"_

La IA detecta la categoría automáticamente.
Cuando termines escribí *LISTO*."""

MSG_ADMIN_GUARDADO = """✅ *Guardado correctamente*

📁 *Categoría:* {categoria}
📝 *Nombre:* {nombre}
🔗 *Cloudinary:* ✓

¿Mandás otro trabajo o escribís *LISTO* para salir?"""

MSG_ADMIN_ERROR = "❌ No pude guardar el trabajo. Intentá de nuevo o escribí LISTO para salir."

MSG_ADMIN_SALIDA = "👋 Modo carga finalizado. ¡Gracias Lau!"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EVOLUTION API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _evo_headers() -> dict:
    return {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not EVOLUTION_INSTANCE:
        logger.warning("[Lau] Evolution config incompleta")
        return False
    try:
        numero = re.sub(r'\D', '', telefono)
        r = requests.post(
            f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            headers=_evo_headers(),
            json={"number": numero, "text": mensaje},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[Lau] Error enviar_texto: %s", e)
        return False


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not EVOLUTION_INSTANCE:
        return False
    try:
        numero = re.sub(r'\D', '', telefono)
        r = requests.post(
            f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}",
            headers=_evo_headers(),
            json={
                "number": numero,
                "mediatype": "image",
                "media": url_imagen,
                "caption": caption,
            },
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[Lau] Error enviar_imagen: %s", e)
        return False


def _descargar_media_evolution(message_id: str) -> bytes | None:
    """Descarga el binario de una imagen recibida en Evolution API."""
    try:
        r = requests.post(
            f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{EVOLUTION_INSTANCE}",
            headers=_evo_headers(),
            json={"message": {"key": {"id": message_id}}},
            timeout=15,
        )
        if r.status_code == 200:
            import base64
            b64 = r.json().get("base64", "")
            if b64:
                return base64.b64decode(b64)
    except Exception as e:
        logger.warning("[Lau] Error descargar_media: %s", e)
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLOUDINARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _subir_cloudinary(imagen_bytes: bytes, nombre_archivo: str) -> str | None:
    """Sube imagen a Cloudinary carpeta creaciones-lau/ y retorna URL pública."""
    try:
        import io
        result = cloudinary.uploader.upload(
            io.BytesIO(imagen_bytes),
            folder="creaciones-lau",
            public_id=nombre_archivo,
            overwrite=False,
            resource_type="image",
        )
        return result.get("secure_url")
    except Exception as e:
        logger.warning("[Lau] Error Cloudinary: %s", e)
        return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AIRTABLE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _at_headers() -> dict:
    return {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def _at_base_url(table_id: str) -> str:
    return f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"


def _obtener_productos_por_categoria(categoria: str) -> list[dict]:
    """Retorna lista de productos de una categoría con URL_Cloudinary."""
    try:
        r = requests.get(
            _at_base_url(TABLE_PRODUCTOS),
            headers=_at_headers(),
            params={
                "filterByFormula": f"{{Categoria}}='{categoria}'",
                "fields[]": ["Nombre", "Descripcion", "Precio", "URL_Cloudinary"],
                "maxRecords": 5,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("records", [])
    except Exception as e:
        logger.warning("[Lau] Error Airtable get_productos: %s", e)
    return []


def _guardar_producto(nombre: str, descripcion: str, categoria: str, url_cloudinary: str) -> bool:
    """Crea un registro nuevo en Productos/Trabajos."""
    try:
        r = requests.post(
            _at_base_url(TABLE_PRODUCTOS),
            headers=_at_headers(),
            json={"fields": {
                "Nombre": nombre,
                "Descripcion": descripcion,
                "Categoria": categoria,
                "URL_Cloudinary": url_cloudinary,
            }},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[Lau] Error Airtable guardar_producto: %s", e)
        return False


def _guardar_lead(nombre: str, telefono: str, categoria: str) -> None:
    """Registra un interesado en la tabla Leads."""
    try:
        requests.post(
            _at_base_url(TABLE_LEADS),
            headers=_at_headers(),
            json={"fields": {
                "Nombre": nombre,
                "Telefono": telefono,
                "Categoria_Interes": categoria,
                "Fecha_Consulta": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }},
            timeout=10,
        )
    except Exception as e:
        logger.warning("[Lau] Error Airtable guardar_lead: %s", e)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GEMINI — detectar categoría
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _detectar_categoria(descripcion: str) -> str:
    """Usa Gemini para detectar la categoría del trabajo según la descripción."""
    if not _gemini_client:
        return "Cumpleaños"
    try:
        prompt = f"""Clasificá el siguiente trabajo de manualidades en UNA de estas categorías:
- Escolar
- Cumpleaños
- Eventos
- Cameo/Diseños

Descripción: "{descripcion}"

Respondé SOLO con el nombre exacto de la categoría, sin explicación."""
        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite", contents=prompt
        )
        cat = resp.text.strip()
        if cat in ["Escolar", "Cumpleaños", "Eventos", "Cameo/Diseños"]:
            return cat
        return "Cumpleaños"
    except Exception as e:
        logger.warning("[Lau] Error Gemini categoría: %s", e)
        return "Cumpleaños"


def _sugerir_nombre(descripcion: str) -> str:
    """Genera un nombre corto para el trabajo basado en la descripción."""
    if not _gemini_client:
        return descripcion[:50]
    try:
        prompt = f"""Dado este texto de un trabajo de manualidades: "{descripcion}"
Generá un nombre corto (máx 5 palabras) para identificarlo en un catálogo.
Respondé SOLO con el nombre, sin comillas ni explicación."""
        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite", contents=prompt
        )
        return resp.text.strip()
    except Exception:
        return descripcion[:50]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LÓGICA PRINCIPAL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _procesar_y_guardar_con_categoria(telefono: str, descripcion: str, imagen_bytes: bytes, categoria: str) -> str:
    """Sube a Cloudinary y guarda en Airtable usando la categoría elegida por Lau."""
    nombre = _sugerir_nombre(descripcion)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"{categoria.lower().replace('/', '_').replace(' ', '_')}_{ts}"

    url_cloudinary = _subir_cloudinary(imagen_bytes, nombre_archivo)
    if not url_cloudinary:
        _enviar_texto(telefono, MSG_ADMIN_ERROR)
        return MSG_ADMIN_ERROR

    ok = _guardar_producto(nombre, descripcion, categoria, url_cloudinary)
    if not ok:
        _enviar_texto(telefono, MSG_ADMIN_ERROR)
        return MSG_ADMIN_ERROR

    msg = MSG_ADMIN_GUARDADO.format(categoria=categoria, nombre=nombre)
    _enviar_texto(telefono, msg)
    return msg


CATEGORIAS_ADMIN = {
    "1": "Escolar",
    "2": "Fiestas y Eventos",
    "3": "Papeleria Creativa",
    "4": "Diseños e Impresiones",
}


def _procesar_admin(telefono: str, texto: str, imagen_bytes: bytes | None, nombre_push: str) -> str:
    """Modo admin: Lau carga productos.
    Pasos:
      1) Elegir categoría (1-4)
      2) Mandar foto (con o sin descripción)
      3) Si foto sin descripción → bot pide descripción
      4) Guarda en Cloudinary + Airtable
    """
    sesion = SESIONES.get(telefono, {})
    txt = texto.strip()

    # Salida del modo admin
    if txt.upper() == "LISTO":
        SESIONES.pop(telefono, None)
        _enviar_texto(telefono, MSG_ADMIN_SALIDA)
        return MSG_ADMIN_SALIDA

    # Paso 1: Lau aún no eligió categoría
    if not sesion.get("categoria_admin"):
        if txt in CATEGORIAS_ADMIN:
            categoria = CATEGORIAS_ADMIN[txt]
            SESIONES[telefono] = {**sesion, "modo": "admin", "categoria_admin": categoria}
            msg = f"✅ Categoría: *{categoria}*\n\n📸 Ahora mandame la foto del trabajo (podés escribir la descripción en el mismo mensaje o después)."
            _enviar_texto(telefono, msg)
            return msg
        else:
            _enviar_texto(telefono, MSG_ADMIN_ELEGIR_CATEGORIA)
            return MSG_ADMIN_ELEGIR_CATEGORIA

    # Categoría ya elegida — procesar foto
    categoria = sesion["categoria_admin"]

    # Foto + descripción juntos
    if imagen_bytes and txt:
        SESIONES[telefono] = {**sesion, "modo": "admin", "categoria_admin": categoria}
        return _procesar_y_guardar_con_categoria(telefono, txt, imagen_bytes, categoria)

    # Solo foto sin descripción → pedir descripción
    if imagen_bytes and not txt:
        SESIONES[telefono] = {**sesion, "modo": "admin", "categoria_admin": categoria, "foto_pendiente": imagen_bytes}
        msg = "📝 ¿Cómo se llama o qué es este trabajo? Describilo brevemente."
        _enviar_texto(telefono, msg)
        return msg

    # Texto después de la foto
    if not imagen_bytes and txt and sesion.get("foto_pendiente"):
        foto = sesion["foto_pendiente"]
        SESIONES[telefono] = {**sesion, "modo": "admin", "categoria_admin": categoria}
        del SESIONES[telefono]["foto_pendiente"]
        return _procesar_y_guardar_con_categoria(telefono, txt, foto, categoria)

    # Solo texto sin foto
    if not imagen_bytes and txt:
        msg = "📸 Mandame la foto del trabajo."
        _enviar_texto(telefono, msg)
        return msg

    _enviar_texto(telefono, MSG_ADMIN_ELEGIR_CATEGORIA)
    return MSG_ADMIN_ELEGIR_CATEGORIA


def _procesar_cliente(telefono: str, texto: str, nombre_push: str) -> str:
    """Modo cliente: menú por categoría → fotos → deriva a Lau."""
    txt = texto.strip().lower()
    sesion = SESIONES.get(telefono, {})

    # Reset / bienvenida
    if txt in ("hola", "menu", "menú", "inicio", "0", "00", ""):
        SESIONES.pop(telefono, None)
        _enviar_texto(telefono, MSG_BIENVENIDA)
        return MSG_BIENVENIDA

    # Derivar a Lau
    if txt in ("si", "sí", "si quiero", "sí quiero") and sesion.get("esperando_derivar"):
        SESIONES.pop(telefono, None)
        categoria = sesion.get("categoria", "")
        _guardar_lead(nombre_push, telefono, categoria)
        _enviar_texto(telefono, MSG_DERIVAR)
        return MSG_DERIVAR

    # Selección de categoría
    if txt in CATEGORIAS:
        categoria = CATEGORIAS[txt]
        SESIONES[telefono] = {"categoria": categoria, "esperando_derivar": False}
        productos = _obtener_productos_por_categoria(categoria)

        if not productos:
            SESIONES[telefono]["esperando_derivar"] = True
            _enviar_texto(telefono, MSG_SIN_PRODUCTOS)
            return MSG_SIN_PRODUCTOS

        # Mandar hasta 3 fotos de esa categoría
        _enviar_texto(telefono, f"✨ Acá algunos trabajos de *{categoria}*:")
        for p in productos[:3]:
            fields = p.get("fields", {})
            url = fields.get("URL_Cloudinary", "")
            caption = fields.get("Nombre", "") + (" — " + fields.get("Descripcion", "") if fields.get("Descripcion") else "")
            if url:
                _enviar_imagen(telefono, url, caption)

        msg_final = f"¿Te interesa algo de *{categoria}*? ¿Querés hablar con Lau?\nRespondé *SI* y te paso el contacto, o *MENU* para volver. 😊"
        SESIONES[telefono]["esperando_derivar"] = True
        _enviar_texto(telefono, msg_final)
        return msg_final

    # Fallback
    msg = "Escribí *MENU* para ver las opciones 😊"
    _enviar_texto(telefono, msg)
    return msg


def _es_numero_lau(telefono: str) -> bool:
    """Verifica si el mensaje viene del número personal de Lau."""
    numero_limpio = re.sub(r'\D', '', telefono)
    numero_lau = re.sub(r'\D', '', NUMERO_LAU)
    return numero_limpio.endswith(numero_lau[-10:])


def _procesar_mensaje(
    telefono: str,
    texto: str,
    nombre_push: str,
    imagen_bytes: bytes | None = None,
) -> str:
    txt = texto.strip()
    sesion = SESIONES.get(telefono, {})

    # Activar modo admin: solo desde el nro de Lau + palabra clave + PIN
    if txt.upper().startswith("CARGAR ") and _es_numero_lau(telefono):
        pin_ingresado = txt[7:].strip()
        if pin_ingresado == ADMIN_PIN:
            SESIONES[telefono] = {"modo": "admin"}
            _enviar_texto(telefono, MSG_ADMIN_BIENVENIDA)
            return MSG_ADMIN_BIENVENIDA
        else:
            msg = "❌ PIN incorrecto."
            _enviar_texto(telefono, msg)
            return msg

    # Si está en modo admin (solo Lau puede estar en este modo)
    if sesion.get("modo") == "admin" and _es_numero_lau(telefono):
        return _procesar_admin(telefono, txt, imagen_bytes, nombre_push)

    # Modo cliente (cualquier otro número, o Lau sin modo admin activo)
    return _procesar_cliente(telefono, txt, nombre_push)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/whatsapp")
async def webhook_whatsapp(request: Request):
    """Webhook Evolution API — mensajes entrantes de Creaciones Lau."""
    body = await request.json()

    data = body.get("data", body)
    key = data.get("key", {})

    # Ignorar mensajes propios del bot
    if key.get("fromMe"):
        return {"status": "ignored", "reason": "fromMe"}

    telefono = key.get("remoteJid", "").replace("@s.whatsapp.net", "")
    message = data.get("message", {})
    nombre_push = data.get("pushName", "")
    message_id = key.get("id", "")

    # Extraer texto
    texto = (
        message.get("conversation", "")
        or message.get("extendedTextMessage", {}).get("text", "")
        or message.get("imageMessage", {}).get("caption", "")
        or ""
    )

    # Detectar si hay imagen
    imagen_bytes = None
    if "imageMessage" in message and message_id:
        imagen_bytes = _descargar_media_evolution(message_id)

    if not telefono:
        return {"status": "ignored", "reason": "sin telefono"}

    _procesar_mensaje(telefono, texto, nombre_push, imagen_bytes)
    return {"status": "ok"}


@router.get("/config")
def config():
    return {
        "proyecto": "system-ia",
        "cliente": "lau",
        "negocio": "Creaciones Lau",
        "evolution_url": EVOLUTION_API_URL or "FALTA",
        "evolution_instance": EVOLUTION_INSTANCE or "FALTA",
        "evolution_key": "ok" if EVOLUTION_API_KEY else "FALTA",
        "airtable_base": AIRTABLE_BASE_ID,
        "cloudinary": "ok" if CLOUDINARY_CLOUD else "FALTA",
        "gemini": "ok" if GEMINI_API_KEY else "FALTA",
        "admin_pin": "configurado" if ADMIN_PIN else "FALTA",
    }
