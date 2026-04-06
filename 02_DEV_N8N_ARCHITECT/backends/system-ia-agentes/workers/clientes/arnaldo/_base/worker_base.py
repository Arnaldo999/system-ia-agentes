"""
Worker Base — Proyecto Arnaldo (YCloud + Chatwoot Arnaldo)
==========================================================
Template para clientes de Arnaldo Ayala.
WhatsApp vía YCloud API. CRM vía Chatwoot de Arnaldo.

USO: Copiar este archivo a workers/clientes/arnaldo/[cliente]/worker.py
     y personalizar CONFIG_NEGOCIO, MENSAJES y el prompt de Gemini.

Endpoints base:
  POST /clientes/arnaldo/[cliente]/whatsapp          ← YCloud webhook entrante
  POST /clientes/arnaldo/[cliente]/chatwoot-webhook   ← Chatwoot respuesta manual
  GET  /clientes/arnaldo/[cliente]/config             ← Diagnóstico
"""

import os
import re
import time
import logging
import requests
from google import genai
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PERSONALIZAR PARA CADA CLIENTE — Inicio
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLIENTE_SLUG = "CAMBIAR"  # ej: "maicol", "otro-cliente"
CLIENTE_TAG  = "CAMBIAR — Nombre del Cliente"

CONFIG_NEGOCIO = {
    "nombre":   "Nombre del Negocio",
    "ciudad":   "Ciudad, Provincia",
    "rubro":    "inmobiliaria",  # inmobiliaria, gastronomia, etc
    "asesor":   "Nombre del asesor",
}

# Variables de entorno (renombrar sufijo por cliente)
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
YCLOUD_API_KEY   = os.environ.get(f"YCLOUD_API_KEY_{CLIENTE_SLUG.upper()}", "")
NUMERO_BOT       = os.environ.get(f"NUMERO_BOT_{CLIENTE_SLUG.upper()}", "")
NUMERO_ASESOR    = os.environ.get(f"NUMERO_ASESOR_{CLIENTE_SLUG.upper()}", "")

# Chatwoot — instancia de Arnaldo
CHATWOOT_URL        = os.environ.get("CHATWOOT_URL", "https://chatwoot.arnaldoayalaestratega.cloud")
CHATWOOT_API_TOKEN  = os.environ.get(f"CHATWOOT_API_TOKEN_{CLIENTE_SLUG.upper()}", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID   = os.environ.get(f"CHATWOOT_INBOX_ID_{CLIENTE_SLUG.upper()}", "")

MSG_BIENVENIDA = """👋 ¡Hola! Bienvenido a *{nombre}*
{ciudad}

¿En qué podemos ayudarte?

1️⃣ Ver opciones
2️⃣ Hablar con un asesor

Respondé con el número de tu opción. 😊"""

PROMPT_GEMINI = """Sos el asistente virtual de {nombre}, en {ciudad}, Argentina.
El asesor humano se llama {asesor}.
Respondé consultas del rubro. Sé breve, amigable y profesional.
Respondé en español argentino.

Consulta del cliente: {mensaje}"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PERSONALIZAR PARA CADA CLIENTE — Fin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(
    prefix=f"/clientes/arnaldo/{CLIENTE_SLUG}",
    tags=[CLIENTE_TAG],
)

SESIONES: dict[str, dict] = {}


# ─── YCLOUD — Envío de mensajes ─────────────────────────────────────────────

def _normalizar_telefono(tel: str) -> str:
    solo_digitos = re.sub(r'\D', '', tel)
    return f"+{solo_digitos}"


def _typing(msg_id: str) -> None:
    if not YCLOUD_API_KEY or not msg_id:
        return
    try:
        requests.post(
            f"https://api.ycloud.com/v2/whatsapp/inboundMessages/{msg_id}/typingIndicator",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            timeout=5,
        )
        time.sleep(1.2)
    except Exception:
        pass


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not YCLOUD_API_KEY:
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            json={"from": NUMERO_BOT, "to": telefono, "type": "text", "text": {"body": mensaje}},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[YCloud] Excepción: %s", e)
        return False


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    if not YCLOUD_API_KEY or not url_imagen:
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            json={"from": NUMERO_BOT, "to": telefono, "type": "image",
                  "image": {"link": url_imagen, "caption": caption}},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[YCloud] Excepción imagen: %s", e)
        return False


# ─── CHATWOOT — Bridge bidireccional ────────────────────────────────────────

_CW_HEADERS = lambda: {
    "api_access_token": CHATWOOT_API_TOKEN,
    "Content-Type": "application/json",
}


def _cw_base():
    return f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}"


def _cw_get_or_create_contact(telefono: str, nombre: str = "") -> str | None:
    if not CHATWOOT_API_TOKEN:
        return None
    try:
        r = requests.get(
            f"{_cw_base()}/contacts/search",
            headers=_CW_HEADERS(),
            params={"q": telefono, "page": 1},
            timeout=8,
        )
        if r.status_code == 200:
            payload = r.json()
            raw = payload.get("payload", []) if isinstance(payload, dict) else payload
            results = raw.get("contacts", raw) if isinstance(raw, dict) else raw
            if results:
                return str(results[0]["id"])

        body = {"phone_number": f"+{telefono.lstrip('+')}"}
        if nombre:
            body["name"] = nombre.strip()
        r2 = requests.post(f"{_cw_base()}/contacts", headers=_CW_HEADERS(), json=body, timeout=8)
        if r2.status_code in (200, 201):
            return str(r2.json().get("id") or r2.json().get("payload", {}).get("id"))
    except Exception as e:
        logger.warning("[CW] Error get_or_create_contact: %s", e)
    return None


def _cw_get_or_create_conversation(contact_id: str) -> str | None:
    if not CHATWOOT_API_TOKEN or not CHATWOOT_INBOX_ID:
        return None
    try:
        r = requests.get(
            f"{_cw_base()}/contacts/{contact_id}/conversations",
            headers=_CW_HEADERS(),
            timeout=8,
        )
        if r.status_code == 200:
            convs = r.json().get("payload", [])
            for c in convs:
                if str(c.get("inbox_id")) == str(CHATWOOT_INBOX_ID) and c.get("status") == "open":
                    return str(c["id"])

        body = {"contact_id": int(contact_id), "inbox_id": int(CHATWOOT_INBOX_ID or 0)}
        r2 = requests.post(f"{_cw_base()}/conversations", headers=_CW_HEADERS(), json=body, timeout=8)
        if r2.status_code in (200, 201):
            data = r2.json()
            return str(data.get("id") or data.get("payload", {}).get("id"))
    except Exception as e:
        logger.warning("[CW] Error get_or_create_conversation: %s", e)
    return None


def _cw_send_message(conversation_id: str, content: str, message_type: str = "incoming") -> None:
    if not CHATWOOT_API_TOKEN or not conversation_id:
        return
    try:
        requests.post(
            f"{_cw_base()}/conversations/{conversation_id}/messages",
            headers=_CW_HEADERS(),
            json={"content": content, "message_type": message_type, "private": False},
            timeout=8,
        )
    except Exception as e:
        logger.warning("[CW] Error send_message: %s", e)


def _sincronizar_chatwoot(telefono: str, nombre: str, msg_cliente: str, respuesta_bot: str) -> None:
    contact_id = _cw_get_or_create_contact(telefono, nombre)
    if not contact_id:
        return
    conv_id = _cw_get_or_create_conversation(contact_id)
    if not conv_id:
        return
    _cw_send_message(conv_id, msg_cliente, "incoming")
    _cw_send_message(conv_id, respuesta_bot, "outgoing")


# ─── GEMINI — IA ────────────────────────────────────────────────────────────

def _gemini_respuesta(mensaje: str) -> str:
    if not GEMINI_API_KEY:
        return f"Gracias por tu consulta. Para más info hablá con {CONFIG_NEGOCIO['asesor']}."
    try:
        prompt = PROMPT_GEMINI.format(**CONFIG_NEGOCIO, mensaje=mensaje)
        resp = _gemini_client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        return resp.text.strip()
    except Exception as e:
        logger.warning("[Gemini] Error: %s", e)
        return f"Gracias por tu consulta. Hablá con {CONFIG_NEGOCIO['asesor']}."


# ─── PROCESADOR PRINCIPAL ───────────────────────────────────────────────────

def _procesar_mensaje(telefono: str, texto: str) -> str:
    """
    Lógica principal del bot. Retorna la respuesta (para sync Chatwoot).
    PERSONALIZAR según el negocio del cliente.
    """
    txt = texto.strip().lower()

    if txt in ("hola", "menu", "menú", "inicio", "0", "00"):
        SESIONES.pop(telefono, None)
        msg = MSG_BIENVENIDA.format(**CONFIG_NEGOCIO)
        _enviar_texto(telefono, msg)
        return msg

    if txt == "2":
        msg = f"Te comunico con {CONFIG_NEGOCIO['asesor']}. ¡Ya te contacta! 😊"
        _enviar_texto(telefono, msg)
        return msg

    # Fallback: Gemini
    msg = _gemini_respuesta(texto)
    _enviar_texto(telefono, msg)
    return msg


# ─── ENDPOINTS ──────────────────────────────────────────────────────────────

@router.post("/whatsapp")
async def webhook_whatsapp(request: Request):
    """Webhook de YCloud — mensajes entrantes de WhatsApp."""
    body = await request.json()

    # YCloud estructura: body.whatsappInboundMessage o body directo
    inbound = body.get("whatsappInboundMessage", body)
    telefono = inbound.get("from", "")
    texto    = inbound.get("text", {}).get("body", "") if isinstance(inbound.get("text"), dict) else inbound.get("text", "")
    nombre   = inbound.get("customerProfile", {}).get("name", "")
    msg_id   = inbound.get("id", "")

    if not telefono or not texto:
        return {"status": "ignored", "reason": "sin telefono o texto"}

    telefono = _normalizar_telefono(telefono)

    _typing(msg_id)
    respuesta = _procesar_mensaje(telefono, texto)
    _sincronizar_chatwoot(re.sub(r'\D', '', telefono), nombre, texto, respuesta)

    return {"status": "ok"}


@router.post("/chatwoot-webhook")
async def chatwoot_webhook(request: Request):
    """Chatwoot envia respuesta manual del agente → reenviar por WhatsApp."""
    body = await request.json()

    event = body.get("event")
    if event != "message_created":
        return {"status": "ignored"}

    message_type = body.get("message_type")
    if message_type != "outgoing":
        return {"status": "ignored", "reason": "no es outgoing"}

    sender = body.get("sender", {})
    if sender.get("type") == "contact":
        return {"status": "ignored", "reason": "es mensaje del contacto"}

    content = body.get("content", "")
    conversation = body.get("conversation", {})
    contact = conversation.get("contact", {}) or conversation.get("meta", {}).get("sender", {})
    telefono = contact.get("phone_number", "")

    if not telefono or not content:
        return {"status": "ignored", "reason": "sin telefono o contenido"}

    telefono = _normalizar_telefono(telefono)
    _enviar_texto(telefono, content)

    return {"status": "sent"}


@router.get("/config")
def config():
    """Diagnóstico de configuración."""
    return {
        "proyecto": "arnaldo",
        "cliente": CLIENTE_SLUG,
        "negocio": CONFIG_NEGOCIO["nombre"],
        "ycloud_key": "ok" if YCLOUD_API_KEY else "FALTA",
        "gemini_key": "ok" if GEMINI_API_KEY else "FALTA",
        "chatwoot_token": "ok" if CHATWOOT_API_TOKEN else "FALTA",
        "chatwoot_inbox": CHATWOOT_INBOX_ID or "FALTA",
        "numero_bot": NUMERO_BOT or "FALTA",
    }
