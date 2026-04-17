"""
Worker dummy para onboarding de prueba (test-arnaldo).

Solo existe para que el endpoint /public/waba/onboarding valide que el slug
apunta a un worker real cuando Arnaldo prueba el flow de Embedded Signup con
su propio numero personal.

Al recibir un mensaje de WhatsApp, simplemente responde con un eco de prueba
usando el access_token del tenant registrado en waba_clients.

NO usar en produccion. Este worker es solo para testing.
"""

import logging
import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("lovbot.test_arnaldo")

router = APIRouter(prefix="/clientes/lovbot/test-arnaldo", tags=["Test Arnaldo — Onboarding Test"])


def _get_access_token_for_phone(phone_number_id: str) -> str | None:
    """Obtiene el access_token del tenant desde la tabla waba_clients."""
    try:
        from workers.clientes.lovbot.robert_inmobiliaria import db_postgres as db
        row = db.obtener_waba_client_por_phone(phone_number_id)
        if row:
            return row.get("access_token")
    except Exception as e:
        logger.warning(f"[TEST-ARNALDO] Error leyendo access_token: {e}")
    return None


def _send_whatsapp(phone_number_id: str, to: str, text: str, access_token: str) -> dict:
    """Envia mensaje via Meta Graph API."""
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
            timeout=15,
        )
        return {"status": resp.status_code, "body": resp.text[:200]}
    except Exception as e:
        return {"status": 0, "error": str(e)}


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Endpoint que recibe los mensajes routeados desde /webhook/meta/events.
    Espera el payload completo de Meta (no simplificado).
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "ignored", "reason": "no json"}, status_code=200)

    logger.info(f"[TEST-ARNALDO] Mensaje recibido: {str(body)[:400]}")
    print(f"[TEST-ARNALDO] Mensaje recibido: {str(body)[:400]}")

    try:
        entry = (body.get("entry") or [])[0]
        changes = (entry.get("changes") or [])[0]
        value = changes.get("value") or {}
        phone_number_id = (value.get("metadata") or {}).get("phone_number_id", "")
        messages = value.get("messages") or []
        if not messages:
            return JSONResponse({"status": "ok", "note": "no messages (posible statuses)"})

        msg = messages[0]
        from_user = msg.get("from", "")
        msg_type = msg.get("type", "")
        text_in = (msg.get("text") or {}).get("body", "") if msg_type == "text" else f"[{msg_type}]"

        access_token = _get_access_token_for_phone(phone_number_id)
        if not access_token:
            logger.warning(f"[TEST-ARNALDO] Sin access_token para phone_id={phone_number_id}")
            return JSONResponse({"status": "error", "reason": "no access_token"}, status_code=200)

        reply = (
            f"🧪 Test bot (test-arnaldo)\n\n"
            f"Recibí tu mensaje: {text_in!r}\n\n"
            f"Si ves esto, el flow Embedded Signup funcionó end-to-end:\n"
            f"✓ Meta webhook → Python router → worker dedicado\n"
            f"✓ phone_number_id: {phone_number_id}\n"
            f"✓ Remitente: {from_user}\n\n"
            f"Este es solo el worker de prueba — el cliente real tendría su propio worker."
        )

        result = _send_whatsapp(phone_number_id, from_user, reply, access_token)
        logger.info(f"[TEST-ARNALDO] Respuesta enviada: {result}")
        return JSONResponse({"status": "ok", "sent": result})

    except Exception as e:
        logger.exception(f"[TEST-ARNALDO] Error procesando mensaje: {e}")
        return JSONResponse({"status": "error", "detail": str(e)[:200]}, status_code=200)


@router.get("/whatsapp/health")
def health():
    return {"ok": True, "worker": "test-arnaldo", "purpose": "onboarding test only"}
