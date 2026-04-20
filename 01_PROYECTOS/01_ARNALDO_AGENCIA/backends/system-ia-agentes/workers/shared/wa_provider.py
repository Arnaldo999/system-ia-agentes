"""
WhatsApp Provider Abstraction
==============================
Capa unificada de envio/parseo que soporta 3 providers:

  - meta       → Meta Graph API (Tech Provider Lovbot / WABA oficial)
  - evolution  → Evolution API self-hosted (Mica, Lau)
  - ycloud     → YCloud BSP comercial (Maicol, Arnaldo legacy)

Objetivo: que cualquier worker pueda cambiar de provider solo cambiando
la env var WHATSAPP_PROVIDER, sin tocar logica de negocio. Esto habilita
el patron "numero de test unico" donde Arnaldo conecta un numero al
Tech Provider de Robert y lo routea a cualquier worker (propio / Mica /
Robert / demos).

Uso tipico en un worker
-----------------------

    from workers.shared.wa_provider import send_text, parse_incoming, get_provider

    # Envio
    send_text(telefono="549...", mensaje="Hola")

    # Parseo de webhook entrante
    @router.post("/whatsapp")
    async def wh(request: Request):
        body = await request.json()
        parsed = parse_incoming(body)  # dict con {telefono, texto, nombre, tipo, referral}
        if not parsed:
            return {"status": "ignored"}
        # ... logica de negocio

Config por env var
------------------
    WHATSAPP_PROVIDER          = meta | evolution | ycloud
    # Meta:
    META_ACCESS_TOKEN / LOVBOT_META_ACCESS_TOKEN
    META_PHONE_ID / LOVBOT_META_PHONE_ID
    # Evolution:
    EVOLUTION_API_URL
    EVOLUTION_API_KEY
    EVOLUTION_INSTANCE
    # YCloud:
    YCLOUD_API_KEY
    YCLOUD_PHONE_NUMBER  (telefono emisor +549...)

Migrar un cliente de provider
------------------------------
Cambiar solo las env vars en Coolify/Easypanel. No tocar codigo del worker.
El codigo Meta Graph queda como MENCION en el historial pero no se ejecuta
si WHATSAPP_PROVIDER != "meta".
"""

from __future__ import annotations

import os
import re
import logging
from typing import Optional

import requests

logger = logging.getLogger("wa_provider")

PROVIDER = os.environ.get("WHATSAPP_PROVIDER", "meta").lower().strip()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS DE ENV
# ═══════════════════════════════════════════════════════════════════════════════

def _env(key: str, *fallbacks: str, default: str = "") -> str:
    """Lee env var con fallbacks ordenados."""
    for k in (key, *fallbacks):
        v = os.environ.get(k, "")
        if v:
            return v
    return default


def _clean_phone(telefono: str) -> str:
    return re.sub(r"\D", "", telefono or "")


# ═══════════════════════════════════════════════════════════════════════════════
# ENVIO — SEND
# ═══════════════════════════════════════════════════════════════════════════════

def send_text(telefono: str, mensaje: str, provider: Optional[str] = None) -> bool:
    """Envia un mensaje de texto usando el provider activo."""
    p = (provider or PROVIDER).lower()
    tel = _clean_phone(telefono)
    if not tel or not mensaje:
        return False

    if p == "meta":
        return _meta_send_text(tel, mensaje)
    if p == "evolution":
        return _evolution_send_text(tel, mensaje)
    if p == "ycloud":
        return _ycloud_send_text(tel, mensaje)

    logger.error(f"[WA-PROVIDER] provider desconocido: {p!r}")
    return False


def send_image(telefono: str, url_imagen: str, caption: str = "",
               provider: Optional[str] = None) -> bool:
    """Envia una imagen usando el provider activo."""
    p = (provider or PROVIDER).lower()
    tel = _clean_phone(telefono)
    if not tel or not url_imagen:
        return False

    if p == "meta":
        return _meta_send_image(tel, url_imagen, caption)
    if p == "evolution":
        return _evolution_send_image(tel, url_imagen, caption)
    if p == "ycloud":
        return _ycloud_send_image(tel, url_imagen, caption)

    logger.error(f"[WA-PROVIDER] provider desconocido: {p!r}")
    return False


# ─── META GRAPH API ──────────────────────────────────────────────────────────

def _meta_send_text(tel: str, mensaje: str) -> bool:
    token = _env("LOVBOT_META_ACCESS_TOKEN", "META_ACCESS_TOKEN")
    phone_id = _env("LOVBOT_META_PHONE_ID", "META_PHONE_ID")
    if not token or not phone_id:
        logger.warning(f"[WA-META] Sin token/phone_id. Msg: {mensaje[:60]}")
        return False
    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "to": tel,
                "type": "text",
                "text": {"body": mensaje, "preview_url": False},
            },
            timeout=10,
        )
        ok = r.status_code in (200, 201)
        if not ok:
            logger.error(f"[WA-META] {r.status_code}: {r.text[:200]}")
        return ok
    except Exception as e:
        logger.error(f"[WA-META] exc: {e}")
        return False


def _meta_send_image(tel: str, url_imagen: str, caption: str) -> bool:
    token = _env("LOVBOT_META_ACCESS_TOKEN", "META_ACCESS_TOKEN")
    phone_id = _env("LOVBOT_META_PHONE_ID", "META_PHONE_ID")
    if not token or not phone_id:
        return False
    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "to": tel,
                "type": "image",
                "image": {"link": url_imagen, "caption": caption},
            },
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.error(f"[WA-META] exc img: {e}")
        return False


# ─── EVOLUTION API ───────────────────────────────────────────────────────────

def _evolution_send_text(tel: str, mensaje: str) -> bool:
    url = _env("EVOLUTION_API_URL")
    key = _env("EVOLUTION_API_KEY")
    # Instance name: probar EVOLUTION_INSTANCE generico (Arnaldo) →
    # MICA_DEMO_EVOLUTION_INSTANCE (Mica demo) → LAU_EVOLUTION_INSTANCE (Lau)
    instance = (
        _env("EVOLUTION_INSTANCE")
        or _env("MICA_DEMO_EVOLUTION_INSTANCE")
        or _env("LAU_EVOLUTION_INSTANCE")
    )
    if not (url and key and instance):
        logger.warning(
            f"[WA-EVO] Sin config (url={bool(url)} key={bool(key)} inst={bool(instance)}). "
            f"Msg: {mensaje[:60]}"
        )
        return False
    try:
        r = requests.post(
            f"{url}/message/sendText/{instance}",
            headers={"Content-Type": "application/json", "apikey": key},
            json={"number": tel, "text": mensaje},
            timeout=10,
        )
        ok = r.status_code in (200, 201)
        if not ok:
            logger.error(f"[WA-EVO] {r.status_code}: {r.text[:200]}")
        return ok
    except Exception as e:
        logger.error(f"[WA-EVO] exc: {e}")
        return False


def _evolution_send_image(tel: str, url_imagen: str, caption: str) -> bool:
    url = _env("EVOLUTION_API_URL")
    key = _env("EVOLUTION_API_KEY")
    instance = (
        _env("EVOLUTION_INSTANCE")
        or _env("MICA_DEMO_EVOLUTION_INSTANCE")
        or _env("LAU_EVOLUTION_INSTANCE")
    )
    if not (url and key and instance):
        return False
    try:
        r = requests.post(
            f"{url}/message/sendMedia/{instance}",
            headers={"Content-Type": "application/json", "apikey": key},
            json={
                "number": tel,
                "mediatype": "image",
                "media": url_imagen,
                "caption": caption,
            },
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        logger.error(f"[WA-EVO] exc img: {e}")
        return False


# ─── YCLOUD ──────────────────────────────────────────────────────────────────

def _ycloud_send_text(tel: str, mensaje: str) -> bool:
    key = _env("YCLOUD_API_KEY")
    from_num = _env("YCLOUD_PHONE_NUMBER", "YCLOUD_FROM")
    if not key or not from_num:
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={
                "from": from_num,
                "to": f"+{tel}",
                "type": "text",
                "text": {"body": mensaje},
            },
            timeout=10,
        )
        ok = r.status_code in (200, 201, 202)
        if not ok:
            logger.error(f"[WA-YC] {r.status_code}: {r.text[:200]}")
        return ok
    except Exception as e:
        logger.error(f"[WA-YC] exc: {e}")
        return False


def _ycloud_send_image(tel: str, url_imagen: str, caption: str) -> bool:
    key = _env("YCLOUD_API_KEY")
    from_num = _env("YCLOUD_PHONE_NUMBER", "YCLOUD_FROM")
    if not key or not from_num:
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={
                "from": from_num,
                "to": f"+{tel}",
                "type": "image",
                "image": {"link": url_imagen, "caption": caption},
            },
            timeout=10,
        )
        return r.status_code in (200, 201, 202)
    except Exception as e:
        logger.error(f"[WA-YC] exc img: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PARSEO — INCOMING
# ═══════════════════════════════════════════════════════════════════════════════

def parse_incoming(body: dict) -> Optional[dict]:
    """
    Detecta el formato del payload y retorna dict unificado:

      {
        "telefono": str,       # digitos limpios, ej "5491134567890"
        "texto": str,
        "nombre": str,         # nombre del contacto (si esta)
        "tipo": str,           # text | audio | image | button | interactive | ...
        "provider": str,       # meta | evolution | ycloud | bridge
        "referral": dict,      # metadata del anuncio (solo Meta) — vacio si no
        "raw": dict,           # payload original para casos avanzados
      }

    Retorna None si el payload no tiene mensaje procesable (status update,
    mensaje propio, evento irrelevante).
    """
    if not body:
        return None

    # Bridge interno: payload simplificado {from, text, nombre?, referral?}
    # (ej: el forwarder webhook_meta.py puede enviar asi al worker)
    if "from" in body and "text" in body and "object" not in body:
        return {
            "telefono": _clean_phone(body.get("from", "")),
            "texto": body.get("text", ""),
            "nombre": body.get("nombre", ""),
            "tipo": "text",
            "provider": "bridge",
            "referral": body.get("referral", {}) or {},
            "raw": body,
        }

    # Meta Graph API
    if body.get("object") == "whatsapp_business_account":
        return _parse_meta(body)

    # Evolution API
    event = (body.get("event") or "").lower().replace("_", ".")
    if event == "messages.upsert" or ("data" in body and "key" in (body.get("data") or {})):
        return _parse_evolution(body)

    # YCloud: payload tipo {"type": "whatsapp.inbound_message.received", "whatsappInboundMessage": {...}}
    if body.get("type", "").startswith("whatsapp.inbound_message"):
        return _parse_ycloud(body)

    return None


def _parse_meta(body: dict) -> Optional[dict]:
    try:
        entry = body["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])
        if not messages:
            return None

        msg = messages[0]
        telefono = _clean_phone(msg.get("from", ""))
        msg_type = msg.get("type", "")
        texto = ""

        if msg_type == "text":
            texto = msg.get("text", {}).get("body", "")
        elif msg_type == "button":
            texto = msg.get("button", {}).get("text", "")
        elif msg_type == "interactive":
            inter = msg.get("interactive", {})
            itype = inter.get("type")
            if itype == "button_reply":
                texto = inter.get("button_reply", {}).get("title", "")
            elif itype == "list_reply":
                texto = inter.get("list_reply", {}).get("title", "")
        elif msg_type == "image":
            texto = msg.get("image", {}).get("caption", "") or "[imagen recibida]"
        elif msg_type == "audio":
            texto = ""  # worker debe transcribir (usa media_id del raw)

        nombre = ""
        if contacts:
            nombre = contacts[0].get("profile", {}).get("name", "")

        referral = {}
        if "referral" in msg:
            ref = msg["referral"]
            referral = {
                "source_url": ref.get("source_url", ""),
                "source_id": ref.get("source_id", ""),
                "source_type": ref.get("source_type", ""),
                "headline": ref.get("headline", ""),
                "body": ref.get("body", ""),
                "media_type": ref.get("media_type", ""),
                "image_url": ref.get("image_url", ""),
                "thumbnail_url": ref.get("thumbnail_url", ""),
            }

        if not telefono:
            return None

        return {
            "telefono": telefono,
            "texto": texto,
            "nombre": nombre,
            "tipo": msg_type,
            "provider": "meta",
            "referral": referral,
            "raw": msg,
        }
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"[WA-PARSE-META] error: {e}")
        return None


def _parse_evolution(body: dict) -> Optional[dict]:
    try:
        data = body.get("data", body)
        key = data.get("key", {})
        if key.get("fromMe"):
            return None

        remote_jid = key.get("remoteJid", "")
        # WhatsApp privacy update 2025-2026: si el JID viene como '<id>@lid'
        # (Linked ID), el telefono REAL viene en `remoteJidAlt`. Ej:
        #   key.remoteJid = "199406758436896@lid"
        #   key.remoteJidAlt = "5493765384843@s.whatsapp.net"  ← este es el de verdad
        # Ver tambien: addressingMode == "lid".
        if "@lid" in remote_jid:
            jid_alt = key.get("remoteJidAlt", "") or ""
            if jid_alt and "@s.whatsapp.net" in jid_alt:
                remote_jid = jid_alt
        telefono = _clean_phone(re.sub(r"@.*", "", remote_jid))

        message = data.get("message", {}) or {}
        msg_type = list(message.keys())[0] if message else ""
        texto = ""

        if msg_type == "conversation":
            texto = message.get("conversation", "")
        elif msg_type == "extendedTextMessage":
            texto = message.get("extendedTextMessage", {}).get("text", "")
        elif msg_type == "buttonsResponseMessage":
            texto = message.get("buttonsResponseMessage", {}).get("selectedDisplayText", "")
        elif msg_type == "listResponseMessage":
            texto = message.get("listResponseMessage", {}).get("title", "")

        nombre = data.get("pushName", "")

        if not telefono:
            return None

        return {
            "telefono": telefono,
            "texto": texto,
            "nombre": nombre,
            "tipo": msg_type,
            "provider": "evolution",
            "referral": {},
            "raw": data,
        }
    except Exception as e:
        logger.warning(f"[WA-PARSE-EVO] error: {e}")
        return None


def _parse_ycloud(body: dict) -> Optional[dict]:
    try:
        msg = body.get("whatsappInboundMessage", {}) or {}
        telefono = _clean_phone(msg.get("from", ""))
        msg_type = msg.get("type", "")
        texto = ""
        if msg_type == "text":
            texto = msg.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            inter = msg.get("interactive", {})
            if inter.get("type") == "button_reply":
                texto = inter.get("buttonReply", {}).get("title", "")

        nombre = msg.get("customerProfile", {}).get("name", "")

        if not telefono:
            return None

        return {
            "telefono": telefono,
            "texto": texto,
            "nombre": nombre,
            "tipo": msg_type,
            "provider": "ycloud",
            "referral": {},
            "raw": msg,
        }
    except Exception as e:
        logger.warning(f"[WA-PARSE-YC] error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════════════════

def get_provider() -> str:
    """Provider actualmente activo (lee env en caliente)."""
    return os.environ.get("WHATSAPP_PROVIDER", "meta").lower().strip()


def health() -> dict:
    """Reporta que provider esta configurado y si tiene credenciales."""
    p = get_provider()
    status = {
        "provider": p,
        "meta_ready": bool(_env("LOVBOT_META_ACCESS_TOKEN", "META_ACCESS_TOKEN")
                           and _env("LOVBOT_META_PHONE_ID", "META_PHONE_ID")),
        "evolution_ready": bool(_env("EVOLUTION_API_URL")
                                and _env("EVOLUTION_API_KEY")
                                and _env("EVOLUTION_INSTANCE")),
        "ycloud_ready": bool(_env("YCLOUD_API_KEY") and _env("YCLOUD_PHONE_NUMBER", "YCLOUD_FROM")),
    }
    status["active_ready"] = status.get(f"{p}_ready", False)
    return status
