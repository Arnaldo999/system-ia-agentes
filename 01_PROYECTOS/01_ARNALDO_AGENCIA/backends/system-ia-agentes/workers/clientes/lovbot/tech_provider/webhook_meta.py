"""
Meta Tech Provider — Webhook Router
=====================================
Reemplaza los 5 subworkflows n8n del Tech Provider de Robert (Lovbot.ai) con endpoints
FastAPI puros. Montado en `/webhook/meta` en el backend principal `agentes.lovbot.ai`.

Arquitectura del flow
---------------------
1. Meta Developer App apunta su webhook a:
       https://agentes.lovbot.ai/webhook/meta/events  (POST)
       https://agentes.lovbot.ai/webhook/meta/verify  (GET — verificacion inicial)

2. Cuando llega un mensaje de WhatsApp a CUALQUIER cliente registrado como tenant:
   - El GET /verify es llamado una sola vez al registrar la URL (handshake).
   - El POST /events es llamado por cada evento (mensaje, estado de entrega, etc).
   - El router busca el phone_number_id en la tabla `waba_clients` de PostgreSQL.
   - Si lo encuentra, forwadea el payload completo al `worker_url` del tenant con el
     header `X-Tenant-Slug` para que el worker sepa de quién es el mensaje.
   - Responde 200 inmediatamente a Meta (antes de 5s) para evitar reintentos.

3. Endpoints administrativos (requieren X-Admin-Token):
   - POST /webhook/meta/subscribe-webhooks — suscribe una WABA a la app Meta
   - POST /webhook/meta/override — cambia callback_uri + verify_token de una WABA

Endpoints expuestos
-------------------
  GET  /webhook/meta/verify               — Handshake inicial Meta (publico)
  POST /webhook/meta/events               — Recepcion de eventos Meta (publico)
  POST /webhook/meta/subscribe-webhooks   — Suscribir WABA a app (admin)
  POST /webhook/meta/override             — Override callback URI (admin)

Como registrar un tenant nuevo
-------------------------------
Usar los endpoints ya existentes en `/admin/waba/*`:
  1. POST /admin/waba/setup-table          — crear tabla si no existe (una sola vez)
  2. POST /admin/waba/register-existing    — registrar phone_number_id + waba_id + worker_url
  3. POST /webhook/meta/subscribe-webhooks — suscribir esa WABA a la app Meta de Robert
  El tenant queda listo. El proximo mensaje que llegue a ese phone_number_id
  sera forwardeado automaticamente a su worker_url.

Como cambiar la URL del webhook en Meta Developers
---------------------------------------------------
  1. Ir a https://developers.facebook.com/apps/<APP_ID>/whatsapp-business/wa-dev-console/
  2. Seccion "Webhook" → "Edit"
  3. URL de devolucion de llamada: https://agentes.lovbot.ai/webhook/meta/events
  4. Token de verificacion: el valor de META_VERIFY_TOKEN en Coolify Hetzner
  5. Hacer clic en "Verificar y guardar" — Meta llama GET /webhook/meta/verify
  6. Suscribir campos: messages, message_deliveries, message_reads (minimo "messages")
  URL anterior (n8n): https://n8n.lovbot.ai/webhook/meta-events  (queda como backup)

Variables de entorno requeridas
--------------------------------
  LOVBOT_META_VERIFY_TOKEN  (fallback: META_VERIFY_TOKEN)
  LOVBOT_META_APP_ID        (fallback: META_APP_ID)
  LOVBOT_META_APP_SECRET    (fallback: META_APP_SECRET)
  LOVBOT_META_ACCESS_TOKEN  (fallback: META_ACCESS_TOKEN)
  LOVBOT_ADMIN_TOKEN        — para endpoints /subscribe-webhooks y /override
  LOVBOT_PG_HOST, LOVBOT_PG_PORT, LOVBOT_PG_DB, LOVBOT_PG_USER, LOVBOT_PG_PASS
"""

import os
import logging
import threading
import time

import requests as _requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel

# ── DB helper (reutiliza db_postgres del worker Robert) ──────────────────────
from workers.clientes.lovbot.robert_inmobiliaria import db_postgres as db

logger = logging.getLogger("lovbot.webhook_meta")

# ── Env vars con fallback LOVBOT_META_* → META_* ─────────────────────────────

def _env(key: str, fallback: str = "") -> str:
    """Lee LOVBOT_META_<key> con fallback a META_<key> y luego al default."""
    lovbot_key = f"LOVBOT_{key}"
    return os.environ.get(lovbot_key) or os.environ.get(key) or fallback


META_VERIFY_TOKEN = _env("META_VERIFY_TOKEN")
META_APP_ID       = _env("META_APP_ID")
META_APP_SECRET   = _env("META_APP_SECRET")
META_ACCESS_TOKEN = _env("META_ACCESS_TOKEN")
ADMIN_TOKEN       = os.environ.get("LOVBOT_ADMIN_TOKEN", "")

GRAPH_BASE = "https://graph.facebook.com/v21.0"

# Deduplicacion de reintentos Meta (en memoria, reset cada 1000 msgs)
_MSG_IDS_PROCESADOS: set[str] = set()
_DEDUP_LOCK = threading.Lock()

# ── Router ───────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/webhook/meta", tags=["Meta Tech Provider"])


# ── Dependencia de auth admin ─────────────────────────────────────────────────

def _require_admin(request: Request):
    token = request.headers.get("X-Admin-Token", "")
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=500, detail="LOVBOT_ADMIN_TOKEN no configurado en servidor")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Token admin invalido")


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class SubscribeWebhooksBody(BaseModel):
    waba_id: str


class OverrideBody(BaseModel):
    waba_id: str
    override_callback_uri: str
    verify_token: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dedup_msg(msg_id: str) -> bool:
    """Retorna True si el mensaje ya fue procesado (duplicado). Thread-safe."""
    with _DEDUP_LOCK:
        if msg_id in _MSG_IDS_PROCESADOS:
            return True
        _MSG_IDS_PROCESADOS.add(msg_id)
        if len(_MSG_IDS_PROCESADOS) > 1000:
            _MSG_IDS_PROCESADOS.clear()
        return False


def _forward_to_worker(tenant: dict, payload: dict) -> None:
    """
    Forwardea el payload de Meta al worker_url del tenant.
    Ejecutado en background — errores solo se loggean.
    """
    worker_url = tenant.get("worker_url", "")
    client_slug = tenant.get("client_slug", "?")
    if not worker_url:
        logger.warning(f"[META-FWD] tenant={client_slug} no tiene worker_url — skip forward")
        return
    try:
        resp = _requests.post(
            worker_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Tenant-Slug": client_slug,
            },
            timeout=10,
        )
        logger.info(f"[META-FWD] tenant={client_slug} → {worker_url} status={resp.status_code}")
    except Exception as e:
        logger.error(f"[META-FWD] tenant={client_slug} → {worker_url} ERROR: {e}")
        # NO reintentar. Meta reintentara si no respondimos 200 (ya respondimos).


def _procesar_events_background(payload: dict) -> None:
    """
    Logica principal de procesamiento del evento Meta.
    Corre en thread background para liberar la respuesta HTTP inmediatamente.
    """
    object_type = payload.get("object", "")
    if object_type != "whatsapp_business_account":
        logger.warning(f"[META-EVENTS] object desconocido: {object_type!r} — ignorado")
        return

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                # Campo desconocido — solo loggear
                logger.info(f"[META-EVENTS] campo ignorado: {change.get('field')}")
                continue

            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            if not phone_number_id:
                logger.warning("[META-EVENTS] phone_number_id vacio en metadata — skip")
                continue

            # Statuses (delivery/read receipts): solo loggear, no forwardear
            statuses = value.get("statuses", [])
            if statuses:
                for s in statuses:
                    logger.info(
                        f"[META-STATUS] phone_id={phone_number_id} "
                        f"msg_id={s.get('id')} status={s.get('status')} "
                        f"recipient={s.get('recipient_id')}"
                    )

            # Messages: buscar tenant y forwardear
            messages = value.get("messages", [])
            if not messages:
                continue

            # Buscar tenant una sola vez por phone_number_id
            tenant = db.obtener_waba_client_por_phone(phone_number_id)
            if not tenant:
                logger.warning(
                    f"[META-EVENTS] phone_id={phone_number_id!r} no registrado en waba_clients — ignorado"
                )
                continue

            for msg in messages:
                msg_id = msg.get("id", "")
                msg_type = msg.get("type", "")

                # Deduplicacion: Meta puede reintentar el mismo mensaje
                if msg_id and _dedup_msg(msg_id):
                    logger.info(f"[META-EVENTS] duplicado ignorado msg_id={msg_id}")
                    continue

                # Ignorar mensajes muy viejos (reintentos tras restart del backend)
                msg_ts = int(msg.get("timestamp", 0))
                if msg_ts and (time.time() - msg_ts) > 30:
                    age = int(time.time() - msg_ts)
                    logger.info(f"[META-EVENTS] mensaje viejo ({age}s) ignorado msg_id={msg_id}")
                    continue

                # Loggear tipo para trazabilidad
                logger.info(
                    f"[META-EVENTS] tenant={tenant['client_slug']} "
                    f"phone_id={phone_number_id} "
                    f"from={msg.get('from')} type={msg_type} msg_id={msg_id}"
                )

                # Forwardear payload completo al worker del tenant
                # El worker es responsable de manejar todos los tipos (text, audio, button, interactive, image, etc.)
                _forward_to_worker(tenant, payload)

                # Solo forwardeamos una vez por entry/change aunque haya multiples msgs
                # (el worker recibe el payload completo con todos los messages)
                break


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/verify",
    response_class=PlainTextResponse,
    summary="Handshake inicial de Meta (publico)",
    description=(
        "Meta llama este endpoint una sola vez al registrar la URL del webhook. "
        "Valida hub.verify_token y responde con hub.challenge como texto plano. "
        "Meta EXIGE texto plano — no JSON."
    ),
)
async def meta_verify(request: Request):
    """
    GET /webhook/meta/verify

    Params enviados por Meta:
      hub.mode          = "subscribe"
      hub.verify_token  = <token configurado en Meta Developers>
      hub.challenge     = <string aleatorio que hay que devolver>
    """
    params = dict(request.query_params)
    hub_token = params.get("hub.verify_token", "")
    hub_challenge = params.get("hub.challenge", "")

    if not META_VERIFY_TOKEN:
        logger.error("[META-VERIFY] META_VERIFY_TOKEN no configurado")
        return PlainTextResponse("Configuracion incompleta", status_code=500)

    if hub_token == META_VERIFY_TOKEN:
        logger.info(f"[META-VERIFY] Verificacion exitosa — challenge={hub_challenge!r}")
        return PlainTextResponse(hub_challenge)

    logger.warning(f"[META-VERIFY] Token invalido: {hub_token!r}")
    return PlainTextResponse("Token invalido", status_code=403)


@router.post(
    "/events",
    summary="Recepcion de eventos Meta (publico)",
    description=(
        "Meta envia todos los eventos de WhatsApp (mensajes, estados de entrega) a este endpoint. "
        "Responde 200 inmediatamente y procesa en background para no superar el timeout de 5s de Meta."
    ),
)
async def meta_events(request: Request, background_tasks: BackgroundTasks):
    """
    POST /webhook/meta/events

    Payload tipico de Meta:
    {
      "object": "whatsapp_business_account",
      "entry": [{
        "id": "<waba_id>",
        "changes": [{
          "field": "messages",
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "X", "display_phone_number": "+..."},
            "messages": [{"from": "...", "id": "...", "text": {"body": "..."}, "type": "text"}],
            "statuses": [...]
          }
        }]
      }]
    }
    """
    # Parsear body
    try:
        payload = await request.json()
    except Exception:
        logger.warning("[META-EVENTS] Body no es JSON valido — ignorado")
        return JSONResponse({"status": "ignored"}, status_code=200)

    # Validacion minima: debe ser evento de WABA
    if payload.get("object") != "whatsapp_business_account":
        logger.warning(f"[META-EVENTS] object={payload.get('object')!r} — no es WABA, retorno 400")
        return JSONResponse({"error": "Payload no corresponde a whatsapp_business_account"}, status_code=400)

    # Responder 200 INMEDIATAMENTE a Meta (antes de 5s)
    # Procesamiento real en background thread
    background_tasks.add_task(_procesar_events_background, payload)

    return JSONResponse({"status": "received"}, status_code=200)


@router.post(
    "/subscribe-webhooks",
    summary="Suscribir WABA a la app Meta (admin)",
    description=(
        "Llama a Graph API para suscribir el waba_id a la app Meta de Robert. "
        "Requiere header X-Admin-Token."
    ),
    dependencies=[Depends(_require_admin)],
)
async def subscribe_webhooks(body: SubscribeWebhooksBody):
    """
    POST /webhook/meta/subscribe-webhooks
    Header: X-Admin-Token: <LOVBOT_ADMIN_TOKEN>
    Body:   {"waba_id": "..."}

    Hace POST a:
      https://graph.facebook.com/v21.0/{waba_id}/subscribed_apps
    con Authorization: Bearer <access_token del tenant>

    Luego marca webhook_subscrito=TRUE en waba_clients para ese WABA.
    """
    waba_id = body.waba_id.strip()
    if not waba_id:
        raise HTTPException(status_code=422, detail="waba_id es requerido")

    # Buscar tenant por waba_id para obtener su access_token y phone_number_id
    clients = db.listar_waba_clients()
    tenant = next((c for c in clients if c.get("waba_id") == waba_id), None)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"waba_id={waba_id!r} no encontrado en waba_clients. Registralo primero via /admin/waba/register-existing"
        )

    access_token = tenant.get("access_token") or META_ACCESS_TOKEN
    phone_number_id = tenant.get("phone_number_id", "")

    if not access_token:
        raise HTTPException(status_code=500, detail="access_token no disponible para esta WABA")

    # Llamar a Graph API
    url = f"{GRAPH_BASE}/{waba_id}/subscribed_apps"
    try:
        resp = _requests.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    except Exception as e:
        logger.error(f"[META-SUBSCRIBE] Error llamando Graph API: {e}")
        raise HTTPException(status_code=502, detail=f"Error llamando Graph API: {e}")

    if resp.status_code not in (200, 201):
        logger.error(f"[META-SUBSCRIBE] Graph API error {resp.status_code}: {resp.text[:300]}")
        raise HTTPException(
            status_code=502,
            detail=f"Graph API respondio {resp.status_code}: {resp.text[:300]}"
        )

    # Marcar en DB
    db_ok = False
    if phone_number_id:
        db_ok = db.marcar_webhook_subscrito(phone_number_id)

    logger.info(f"[META-SUBSCRIBE] waba_id={waba_id} suscrito OK. DB marcado: {db_ok}")
    return {
        "ok": True,
        "waba_id": waba_id,
        "graph_status": resp.status_code,
        "graph_response": resp.json() if resp.text else {},
        "db_webhook_marcado": db_ok,
    }


@router.post(
    "/override",
    summary="Override callback URI de una WABA (admin)",
    description=(
        "Cambia la URL del webhook y el verify_token de una WABA especifica. "
        "Util para migrar de n8n a este endpoint. Requiere X-Admin-Token."
    ),
    dependencies=[Depends(_require_admin)],
)
async def override_webhook(body: OverrideBody):
    """
    POST /webhook/meta/override
    Header: X-Admin-Token: <LOVBOT_ADMIN_TOKEN>
    Body:
    {
      "waba_id": "...",
      "override_callback_uri": "https://agentes.lovbot.ai/webhook/meta/events",
      "verify_token": "<nuevo_token>"
    }

    Hace POST a Graph API con los parametros de override para cambiar
    la URL del webhook sin tocar la configuracion global de la app.
    """
    waba_id = body.waba_id.strip()
    if not waba_id:
        raise HTTPException(status_code=422, detail="waba_id es requerido")
    if not body.override_callback_uri.startswith("https://"):
        raise HTTPException(status_code=422, detail="override_callback_uri debe ser HTTPS")

    # Obtener access_token del tenant
    clients = db.listar_waba_clients()
    tenant = next((c for c in clients if c.get("waba_id") == waba_id), None)
    access_token = (tenant.get("access_token") if tenant else None) or META_ACCESS_TOKEN

    if not access_token:
        raise HTTPException(status_code=500, detail="access_token no disponible para esta WABA")

    url = f"{GRAPH_BASE}/{waba_id}/subscribed_apps"
    payload_graph = {
        "override_callback_uri": body.override_callback_uri,
        "verify_token": body.verify_token,
    }
    try:
        resp = _requests.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload_graph,
            timeout=15,
        )
    except Exception as e:
        logger.error(f"[META-OVERRIDE] Error llamando Graph API: {e}")
        raise HTTPException(status_code=502, detail=f"Error llamando Graph API: {e}")

    if resp.status_code not in (200, 201):
        logger.error(f"[META-OVERRIDE] Graph API error {resp.status_code}: {resp.text[:300]}")
        raise HTTPException(
            status_code=502,
            detail=f"Graph API respondio {resp.status_code}: {resp.text[:300]}"
        )

    logger.info(
        f"[META-OVERRIDE] waba_id={waba_id} override aplicado → {body.override_callback_uri}"
    )
    return {
        "ok": True,
        "waba_id": waba_id,
        "nuevo_callback_uri": body.override_callback_uri,
        "graph_status": resp.status_code,
        "graph_response": resp.json() if resp.text else {},
    }
