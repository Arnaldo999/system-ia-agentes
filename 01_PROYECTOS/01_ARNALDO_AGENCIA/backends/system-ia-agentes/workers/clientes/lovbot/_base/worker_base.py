"""
Worker Base — Proyecto Lovbot / Robert (Meta Graph API + Chatwoot Lovbot)
=========================================================================
Template para clientes de la alianza Arnaldo + Robert (Lovbot).
WhatsApp vía Meta Graph API directo (Tech Provider). CRM vía Chatwoot Lovbot.

USO: Copiar este archivo a workers/clientes/lovbot/[cliente]/worker.py
     y personalizar CONFIG_NEGOCIO, MENSAJES y el prompt de Gemini.

DIFERENCIAS con worker Arnaldo:
  - Envío de mensajes: Meta Graph API (no YCloud)
  - Chatwoot: chatwoot.lovbot.ai (no chatwoot.arnaldoayalaestratega.cloud)
  - Auth: Bearer token por cliente (generado en WF2 Login Code)
  - Webhook entrante: viene del n8n de Robert (WF4), no de YCloud directo

Endpoints base:
  POST /clientes/lovbot/[cliente]/whatsapp          ← n8n WF4 reenvía acá
  POST /clientes/lovbot/[cliente]/chatwoot-webhook   ← Chatwoot respuesta manual
  GET  /clientes/lovbot/[cliente]/config             ← Diagnóstico
"""

import os
import re
import logging
import requests
from google import genai
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PERSONALIZAR PARA CADA CLIENTE — Inicio
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLIENTE_SLUG = "CAMBIAR"  # ej: "inmobiliaria-demo", "ford-sureste"
CLIENTE_TAG  = "CAMBIAR — Nombre del Cliente"

CONFIG_NEGOCIO = {
    "nombre":   "Nombre del Negocio",
    "ciudad":   "Ciudad, Estado",
    "rubro":    "inmobiliaria",
    "asesor":   "Nombre del asesor",
}

# Variables de entorno (renombrar sufijo por cliente)
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
PHONE_NUMBER_ID   = os.environ.get(f"META_PHONE_ID_{CLIENTE_SLUG.upper()}", "")
META_ACCESS_TOKEN = os.environ.get(f"META_TOKEN_{CLIENTE_SLUG.upper()}", "")
NUMERO_ASESOR     = os.environ.get(f"NUMERO_ASESOR_{CLIENTE_SLUG.upper()}", "")

# Chatwoot — instancia de Lovbot (Robert)
CHATWOOT_URL        = os.environ.get("CHATWOOT_URL_LOVBOT", "https://chatwoot.lovbot.ai")
CHATWOOT_API_TOKEN  = os.environ.get(f"CHATWOOT_API_TOKEN_{CLIENTE_SLUG.upper()}", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID_LOVBOT", "1")
CHATWOOT_INBOX_ID   = os.environ.get(f"CHATWOOT_INBOX_ID_{CLIENTE_SLUG.upper()}", "")

MSG_BIENVENIDA = """👋 ¡Hola! Bienvenido a *{nombre}*
{ciudad}

¿En qué podemos ayudarte?

1️⃣ Ver opciones
2️⃣ Hablar con un asesor

Responde con el número de tu opción. 😊"""

PROMPT_GEMINI = """Eres el asistente virtual de {nombre}, en {ciudad}, México.
El asesor humano se llama {asesor}.
Responde consultas del rubro. Sé breve, amigable y profesional.
Responde en español mexicano.

Consulta del cliente: {mensaje}"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PERSONALIZAR PARA CADA CLIENTE — Fin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

META_API_URL = "https://graph.facebook.com/v21.0"

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(
    prefix=f"/clientes/lovbot/{CLIENTE_SLUG}",
    tags=[CLIENTE_TAG],
)

SESIONES: dict[str, dict] = {}


# ─── META GRAPH API — Envío de mensajes ─────────────────────────────────────

def _meta_headers() -> dict:
    return {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    """Enviar mensaje de texto vía Meta Graph API."""
    if not META_ACCESS_TOKEN or not PHONE_NUMBER_ID:
        logger.warning("[Meta] Falta META_ACCESS_TOKEN o PHONE_NUMBER_ID")
        return False
    try:
        r = requests.post(
            f"{META_API_URL}/{PHONE_NUMBER_ID}/messages",
            headers=_meta_headers(),
            json={
                "messaging_product": "whatsapp",
                "to": re.sub(r'\D', '', telefono),
                "type": "text",
                "text": {"body": mensaje},
            },
            timeout=10,
        )
        if r.status_code not in (200, 201):
            logger.warning("[Meta] Error %s: %s", r.status_code, r.text[:200])
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[Meta] Excepción: %s", e)
        return False


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    """Enviar imagen vía Meta Graph API."""
    if not META_ACCESS_TOKEN or not PHONE_NUMBER_ID or not url_imagen:
        return False
    try:
        r = requests.post(
            f"{META_API_URL}/{PHONE_NUMBER_ID}/messages",
            headers=_meta_headers(),
            json={
                "messaging_product": "whatsapp",
                "to": re.sub(r'\D', '', telefono),
                "type": "image",
                "image": {"link": url_imagen, "caption": caption},
            },
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[Meta] Excepción imagen: %s", e)
        return False


def _enviar_template(telefono: str, template_name: str, language: str = "es_MX", components: list = None) -> bool:
    """Enviar mensaje de plantilla (marketing, recordatorios, etc) vía Meta Graph API."""
    if not META_ACCESS_TOKEN or not PHONE_NUMBER_ID:
        return False
    try:
        body = {
            "messaging_product": "whatsapp",
            "to": re.sub(r'\D', '', telefono),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }
        if components:
            body["template"]["components"] = components
        r = requests.post(
            f"{META_API_URL}/{PHONE_NUMBER_ID}/messages",
            headers=_meta_headers(),
            json=body,
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning("[Meta] Excepción template: %s", e)
        return False


def _marcar_leido(message_id: str) -> None:
    """Marcar mensaje como leído (doble check azul)."""
    if not META_ACCESS_TOKEN or not PHONE_NUMBER_ID or not message_id:
        return
    try:
        requests.post(
            f"{META_API_URL}/{PHONE_NUMBER_ID}/messages",
            headers=_meta_headers(),
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
            timeout=5,
        )
    except Exception:
        pass


# ─── CHATWOOT — Bridge bidireccional (chatwoot.lovbot.ai) ──────────────────

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
        return f"Gracias por tu consulta. Para más info habla con {CONFIG_NEGOCIO['asesor']}."
    try:
        prompt = PROMPT_GEMINI.format(**CONFIG_NEGOCIO, mensaje=mensaje)
        resp = _gemini_client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        return resp.text.strip()
    except Exception as e:
        logger.warning("[Gemini] Error: %s", e)
        return f"Gracias por tu consulta. Habla con {CONFIG_NEGOCIO['asesor']}."


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
    """
    Webhook de mensajes entrantes.
    Recibe el mensaje ya parseado desde n8n WF4 (Router por Cliente).
    Formato esperado: {from, text, phone_number_id, message_type, message_id, client_name}
    """
    body = await request.json()

    telefono   = body.get("from", "")
    texto      = body.get("text", "")
    message_id = body.get("message_id", "")
    nombre     = body.get("client_name", "")

    if not telefono or not texto:
        return {"status": "ignored", "reason": "sin telefono o texto"}

    _marcar_leido(message_id)
    respuesta = _procesar_mensaje(telefono, texto)
    _sincronizar_chatwoot(re.sub(r'\D', '', telefono), nombre, texto, respuesta)

    return {"status": "ok"}


@router.post("/chatwoot-webhook")
async def chatwoot_webhook(request: Request):
    """Chatwoot envia respuesta manual del agente → reenviar por WhatsApp vía Meta."""
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

    _enviar_texto(telefono, content)
    return {"status": "sent"}


@router.get("/config")
def config():
    """Diagnóstico de configuración."""
    return {
        "proyecto": "lovbot",
        "cliente": CLIENTE_SLUG,
        "negocio": CONFIG_NEGOCIO["nombre"],
        "whatsapp_provider": "meta_graph_api",
        "phone_number_id": PHONE_NUMBER_ID[:6] + "..." if PHONE_NUMBER_ID else "FALTA",
        "meta_token": "ok" if META_ACCESS_TOKEN else "FALTA",
        "gemini_key": "ok" if GEMINI_API_KEY else "FALTA",
        "chatwoot_url": CHATWOOT_URL,
        "chatwoot_token": "ok" if CHATWOOT_API_TOKEN else "FALTA",
        "chatwoot_inbox": CHATWOOT_INBOX_ID or "FALTA",
    }
