"""
Worker — Bot Prueba Arnaldo + Chatwoot
=======================================
Número de prueba personal de Arnaldo.
- Recibe mensajes de YCloud → procesa con Gemini → responde por YCloud
- Sincroniza conversaciones con Chatwoot (CRM)
- Recibe respuestas manuales desde Chatwoot → las envía por YCloud

Endpoints:
  POST /clientes/arnaldo/prueba/whatsapp          ← YCloud webhook entrante
  POST /clientes/arnaldo/prueba/chatwoot-webhook  ← Chatwoot respuesta manual
"""

import os
import logging
import requests
from fastapi import APIRouter, Request
from google import genai

logger = logging.getLogger(__name__)

# ─── CONFIG (todo desde env vars) ─────────────────────────────────────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
YCLOUD_API_KEY   = os.environ.get("YCLOUD_API_KEY_PRUEBA", "") or os.environ.get("YCLOUD_API_KEY_MAICOL", "") or os.environ.get("YCLOUD_API_KEY", "")
NUMERO_BOT       = os.environ.get("NUMERO_BOT_PRUEBA", "5493764815689")

# Chatwoot
CHATWOOT_URL        = os.environ.get("CHATWOOT_URL", "https://chatwoot.arnaldoayalaestratega.cloud")
CHATWOOT_API_TOKEN  = os.environ.get("CHATWOOT_API_TOKEN_PRUEBA", "")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID   = os.environ.get("CHATWOOT_INBOX_ID_PRUEBA", "")   # número entero del inbox

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(prefix="/clientes/arnaldo/prueba", tags=["Arnaldo — Bot Prueba"])

# ─── SESIONES in-memory ───────────────────────────────────────────────────────
SESIONES: dict[str, dict] = {}

# ─── CHATWOOT HELPERS ─────────────────────────────────────────────────────────
_CW_HEADERS = lambda: {
    "api_access_token": CHATWOOT_API_TOKEN,
    "Content-Type": "application/json",
}

def _cw_base():
    return f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}"


def _cw_get_or_create_contact(telefono: str, nombre: str = "") -> str | None:
    """Busca o crea un contacto en Chatwoot. Retorna el contact_id."""
    if not CHATWOOT_API_TOKEN:
        return None
    try:
        # Buscar por teléfono
        r = requests.get(
            f"{_cw_base()}/contacts/search",
            headers=_CW_HEADERS(),
            params={"q": telefono, "page": 1},
            timeout=8,
        )
        if r.status_code == 200:
            payload = r.json()
            results = payload.get("payload", {}).get("contacts", []) or payload.get("payload", [])
            if results:
                return str(results[0]["id"])

        # Crear si no existe
        body = {"phone_number": f"+{telefono.lstrip('+')}"}
        if nombre:
            body["name"] = nombre.strip()
        r2 = requests.post(f"{_cw_base()}/contacts", headers=_CW_HEADERS(), json=body, timeout=8)
        if r2.status_code in (200, 201):
            return str(r2.json().get("id") or r2.json().get("payload", {}).get("id"))
    except Exception as e:
        logger.warning("[Chatwoot] Error get_or_create_contact: %s", e)
    return None


def _cw_get_or_create_conversation(contact_id: str) -> str | None:
    """Obtiene conversación abierta o crea una nueva. Retorna conversation_id."""
    if not CHATWOOT_API_TOKEN or not CHATWOOT_INBOX_ID:
        return None
    try:
        # Buscar conversaciones abiertas del contacto
        r = requests.get(
            f"{_cw_base()}/contacts/{contact_id}/conversations",
            headers=_CW_HEADERS(),
            timeout=8,
        )
        if r.status_code == 200:
            convs = r.json().get("payload", [])
            for c in convs:
                if (
                    str(c.get("inbox_id")) == str(CHATWOOT_INBOX_ID)
                    and c.get("status") == "open"
                ):
                    return str(c["id"])

        # Crear nueva conversación
        body = {
            "contact_id": int(contact_id),
            "inbox_id": int(CHATWOOT_INBOX_ID),
        }
        r2 = requests.post(f"{_cw_base()}/conversations", headers=_CW_HEADERS(), json=body, timeout=8)
        if r2.status_code in (200, 201):
            data = r2.json()
            return str(data.get("id") or data.get("payload", {}).get("id"))
    except Exception as e:
        logger.warning("[Chatwoot] Error get_or_create_conversation: %s", e)
    return None


def _cw_send_message(conversation_id: str, content: str, message_type: str = "incoming") -> None:
    """Envía un mensaje a Chatwoot. message_type: 'incoming' (cliente) o 'outgoing' (bot)."""
    if not CHATWOOT_API_TOKEN or not conversation_id:
        return
    try:
        body = {
            "content": content,
            "message_type": message_type,
            "private": False,
        }
        requests.post(
            f"{_cw_base()}/conversations/{conversation_id}/messages",
            headers=_CW_HEADERS(),
            json=body,
            timeout=8,
        )
    except Exception as e:
        logger.warning("[Chatwoot] Error send_message: %s", e)


def _sincronizar_chatwoot(telefono: str, nombre: str, msg_cliente: str, respuesta_bot: str) -> None:
    """Sincroniza la conversación completa (mensaje entrante + respuesta bot) en Chatwoot."""
    contact_id = _cw_get_or_create_contact(telefono, nombre)
    if not contact_id:
        return
    conv_id = _cw_get_or_create_conversation(contact_id)
    if not conv_id:
        return
    _cw_send_message(conv_id, msg_cliente, "incoming")
    _cw_send_message(conv_id, respuesta_bot, "outgoing")


# ─── YCLOUD HELPERS ───────────────────────────────────────────────────────────
def _ycloud_send(to: str, text: str) -> None:
    if not YCLOUD_API_KEY:
        logger.warning("[YCloud] YCLOUD_API_KEY_PRUEBA no configurada")
        return
    numero = to if to.startswith("+") else f"+{to}"
    try:
        requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"X-API-Key": YCLOUD_API_KEY, "Content-Type": "application/json"},
            json={
                "from": NUMERO_BOT,
                "to": numero,
                "type": "text",
                "text": {"body": text},
            },
            timeout=10,
        )
    except Exception as e:
        logger.error("[YCloud] Error send: %s", e)


# ─── GEMINI ───────────────────────────────────────────────────────────────────
def _responder_con_gemini(telefono: str, mensaje: str) -> str:
    historial = SESIONES.get(telefono, {}).get("historial", [])
    contexto = "\n".join(f"{h['rol']}: {h['msg']}" for h in historial[-6:])

    prompt = f"""Sos un asistente de prueba amigable de System IA.
Respondé de forma breve y natural en español.

Historial reciente:
{contexto}

Usuario: {mensaje}
Asistente:"""

    if _gemini_client:
        try:
            resp = _gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return resp.text.strip()
        except Exception as e:
            logger.error("[Gemini] Error: %s", e)
    return "Hola! Soy el bot de prueba de System IA. ¿En qué puedo ayudarte?"


# ─── ENDPOINT: YCloud → WhatsApp entrante ─────────────────────────────────────
@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        raw = await request.body()
        print("[Prueba] RAW BYTES:", raw[:500], flush=True)
        import json
        body = json.loads(raw)
    except Exception as e:
        print("[Prueba] ERROR parsing body:", e, flush=True)
        return {"status": "ok"}

    print("[Prueba] RAW BODY:", str(body)[:500], flush=True)
    print("[Prueba] KEYS:", list(body.keys()), flush=True)
    print("[Prueba] from_raw:", repr(body.get("from")), flush=True)

    # Formato YCloud: type=whatsapp.inbound_message.received
    # Estructura: {type, from, to, customerProfile, whatsappInboundMessage: {text: {body}}}
    if body.get("type") != "whatsapp.inbound_message.received":
        return {"status": "ignored", "type": body.get("type")}

    telefono = body.get("from", "").replace("+", "").strip()
    wa_msg   = body.get("whatsappInboundMessage", {})
    texto    = (wa_msg.get("text", {}) or {}).get("body", "").strip()
    nombre   = body.get("customerProfile", {}).get("name", "")

    print(f"[Prueba] PARSED telefono={repr(telefono)} texto={repr(texto)} nombre={repr(nombre)}", flush=True)

    messages = [{"telefono": telefono, "texto": texto, "nombre": nombre}] if telefono and texto else []

    if not messages:
        print("[Prueba] SKIP — telefono o texto vacíos", flush=True)

    for msg in messages:
        telefono = msg["telefono"]
        texto    = msg["texto"]
        nombre   = msg["nombre"]

        if not telefono or not texto:
            continue

        print(f"[Prueba] Procesando mensaje de {telefono}: {texto[:50]}", flush=True)

        # Actualizar sesión
        if telefono not in SESIONES:
            SESIONES[telefono] = {"nombre": nombre, "historial": []}
        if nombre:
            SESIONES[telefono]["nombre"] = nombre
        SESIONES[telefono]["historial"].append({"rol": "Usuario", "msg": texto})

        # Generar respuesta
        print(f"[Prueba] Llamando Gemini... gemini_client={bool(_gemini_client)}", flush=True)
        respuesta = _responder_con_gemini(telefono, texto)
        print(f"[Prueba] Gemini respondió: {respuesta[:80]}", flush=True)
        SESIONES[telefono]["historial"].append({"rol": "Asistente", "msg": respuesta})

        # Enviar por WhatsApp
        print(f"[Prueba] Enviando YCloud a {telefono} key={'OK' if YCLOUD_API_KEY else 'VACIA'}", flush=True)
        _ycloud_send(telefono, respuesta)
        print(f"[Prueba] YCloud send completado", flush=True)

        # Sincronizar en Chatwoot
        _sincronizar_chatwoot(telefono, SESIONES[telefono]["nombre"], texto, respuesta)

    return {"status": "ok"}


# ─── ENDPOINT: Chatwoot → respuesta manual del agente ─────────────────────────
@router.post("/chatwoot-webhook")
async def chatwoot_webhook(request: Request):
    """
    Chatwoot llama este endpoint cuando un agente humano envía un mensaje.
    FastAPI lo reenvía por YCloud al cliente.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    event = body.get("event")

    # Solo procesar mensajes salientes escritos por un agente (no por el bot)
    if event != "message_created":
        return {"status": "ignored", "event": event}

    message_type = body.get("message_type")
    content = body.get("content", "").strip()

    # message_type 1 = outgoing (agente → cliente)
    # Solo procesar si es del agente y no está marcado como privado
    if message_type != 1 or not content or body.get("private"):
        return {"status": "ignored", "message_type": message_type}

    # Obtener teléfono del contacto
    meta = body.get("meta", {})
    sender = meta.get("sender", {})
    telefono = (sender.get("phone_number") or "").replace("+", "").strip()

    if not telefono:
        # Intentar obtenerlo de la conversación via API
        conv_id = body.get("conversation", {}).get("id")
        if conv_id and CHATWOOT_API_TOKEN:
            try:
                r = requests.get(
                    f"{_cw_base()}/conversations/{conv_id}",
                    headers=_CW_HEADERS(),
                    timeout=8,
                )
                if r.status_code == 200:
                    telefono = (
                        r.json()
                        .get("meta", {})
                        .get("sender", {})
                        .get("phone_number", "")
                        .replace("+", "")
                        .strip()
                    )
            except Exception as e:
                logger.warning("[Chatwoot webhook] Error obteniendo telefono: %s", e)

    if not telefono:
        logger.warning("[Chatwoot webhook] No se pudo determinar el teléfono del contacto")
        return {"status": "error", "detail": "telefono no encontrado"}

    logger.info("[Chatwoot webhook] Agente responde a %s: %s", telefono, content[:50])
    _ycloud_send(telefono, content)

    return {"status": "ok", "enviado_a": telefono}
