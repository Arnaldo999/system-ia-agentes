"""
workers/shared/typing_indicator.py
────────────────────────────────────
Indicador "escribiendo..." genérico para workers WhatsApp.

Muestra el indicador de typing al usuario mientras el bot prepara/envía
una respuesta, simulando que hay una persona del otro lado tipeando.
Mejora la percepción humana del bot (patrón Kevin Bellier / Nexum).

Comportamiento:
- Por cada mensaje que el bot va a enviar, se llama a send_typing()
  ANTES del envío y se espera N segundos (default 2s).
- Si el provider no soporta typing indicator o falla la llamada, el flujo
  continúa sin romper (solo omite el indicador visual).

API pública:
    send_typing(provider, phone, duration=2.0, **provider_kwargs)

    provider: "meta" | "evolution" | "ycloud" (solo meta/evolution tienen
              soporte real, ycloud no tiene endpoint)
    phone: teléfono destino (solo dígitos)
    duration: segundos a mostrar "escribiendo..." (default 2.0)

    provider_kwargs según el caso:
        Meta:       meta_access_token, meta_phone_id, message_id (opcional —
                    si viene, usa el endpoint de typing indicator sobre ese
                    mensaje específico para respuesta conversacional)
        Evolution:  evolution_url, evolution_instance, evolution_api_key

Endpoints usados:
- Meta Graph API v21.0: POST /{phone_id}/messages con body
      {"status": "read", "typing_indicator": {"type": "text"}, ...}
  Solo funciona si se incluye un message_id de un mensaje entrante
  reciente (los typing indicators de Meta son "en contexto" de un msg).
  Para nuestro uso, Meta soporta marcar como leído + typing indicator en
  la misma llamada tras recibir webhook. Si no hay message_id, Meta no
  tiene endpoint puro de "typing on".

- Evolution API: POST /chat/sendPresence/{instance}
  Body: {"number": phone, "presence": "composing", "delay": ms}
  Soporta "composing" (typing), "recording" (audio), "paused".

Diseño:
- Wrapper síncrono que bloquea `duration` segundos. El worker ya corre
  en thread daemon (patrón sync-in-thread), así que el bloqueo es local
  al thread, no afecta el event loop de FastAPI.
- Fallback silencioso: si el provider no responde o da error, retorna
  False pero no levanta excepción. El worker sigue enviando el mensaje.
- Flag global TYPING_INDICATOR_ENABLED (env, default true) para bypass.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    flag = os.environ.get("TYPING_INDICATOR_ENABLED", "").lower()
    if flag == "false":
        return False
    return True


def send_typing(
    provider: str,
    phone: str,
    duration: float = 2.0,
    *,
    # Meta kwargs
    meta_access_token: Optional[str] = None,
    meta_phone_id: Optional[str] = None,
    message_id: Optional[str] = None,
    # Evolution kwargs
    evolution_url: Optional[str] = None,
    evolution_instance: Optional[str] = None,
    evolution_api_key: Optional[str] = None,
) -> bool:
    """
    Muestra "escribiendo..." por `duration` segundos y bloquea hasta que
    termine (el worker puede enviar el mensaje justo después).

    Devuelve True si el indicator se mostró correctamente, False si falló
    o el provider no lo soporta. En cualquier caso bloquea `duration` seg
    para que el efecto de latencia humanizada se mantenga aunque falle el
    indicator visual.
    """
    if not _enabled():
        time.sleep(duration)
        return False

    if not phone:
        time.sleep(duration)
        return False

    ok = False
    try:
        if provider == "meta":
            ok = _send_typing_meta(
                phone=phone,
                access_token=meta_access_token or "",
                phone_id=meta_phone_id or "",
                message_id=message_id,
            )
        elif provider == "evolution":
            ok = _send_typing_evolution(
                phone=phone,
                url=evolution_url or "",
                instance=evolution_instance or "",
                api_key=evolution_api_key or "",
                duration_ms=int(duration * 1000),
            )
        else:
            # ycloud u otro — sin soporte, solo dormir
            pass
    except Exception as exc:
        logger.warning("typing_indicator: fallo enviando presencia (%s)", exc)
        ok = False

    time.sleep(duration)
    return ok


def _send_typing_meta(
    phone: str,
    access_token: str,
    phone_id: str,
    message_id: Optional[str],
) -> bool:
    """
    Meta Graph v21.0 — typing indicator es solo válido en contexto de un
    mensaje entrante reciente. Si hay message_id, lo usamos para marcar
    como leído + disparar typing. Si no, no hay endpoint puro.

    Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/mark-message-as-read
    """
    if not access_token or not phone_id:
        return False

    if not message_id:
        # Meta no tiene "typing on" sin contexto de mensaje. Devolvemos
        # False pero el caller igual duerme `duration` para mantener pausa.
        return False

    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
                "typing_indicator": {"type": "text"},
            },
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as exc:
        logger.warning("typing_indicator meta: %s", exc)
        return False


def _send_typing_evolution(
    phone: str,
    url: str,
    instance: str,
    api_key: str,
    duration_ms: int,
) -> bool:
    """
    Evolution API — POST /chat/sendPresence/{instance}
    Body: {"number": phone, "presence": "composing", "delay": ms}
    """
    if not url or not instance:
        return False

    try:
        r = requests.post(
            f"{url.rstrip('/')}/chat/sendPresence/{instance}",
            headers={
                "Content-Type": "application/json",
                "apikey": api_key,
            },
            json={
                "number": phone,
                "presence": "composing",
                "delay": duration_ms,
            },
            timeout=5,
        )
        return r.status_code in (200, 201)
    except Exception as exc:
        logger.warning("typing_indicator evolution: %s", exc)
        return False


def random_typing_duration(min_s: float = 1.8, max_s: float = 2.5) -> float:
    """
    Helper opcional para variar la duración del typing entre mensajes.
    Uniforme en rango [min_s, max_s]. Un humano no siempre tarda lo mismo.
    """
    return random.uniform(min_s, max_s)


def mark_read_meta(
    message_id: str,
    access_token: str,
    phone_id: str,
) -> bool:
    """
    Marca un mensaje de Meta Graph WhatsApp como leído (tilde azul).

    Uso típico: apenas llega el webhook de un mensaje entrante, llamar esta
    función para que el cliente vea inmediatamente la tilde azul. Así no
    queda con 1 tilde sola durante los 8s que espera el buffer + typing.

    No bloquea (sync rápido ~200ms). Fallback silencioso si falla.

    API Meta: POST /{phone_id}/messages con body:
        {"messaging_product": "whatsapp", "status": "read", "message_id": "<ID>"}

    Este endpoint es distinto del que usa send_typing_meta (que hace read
    + typing_indicator en la misma llamada). Acá solo marcamos leído,
    sin disparar typing — porque typing se dispara más tarde (en _enviar_texto).

    Ref: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/mark-message-as-read
    """
    if not message_id or not access_token or not phone_id:
        return False
    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            },
            timeout=5,
        )
        if r.status_code not in (200, 201):
            logger.info("mark_read_meta: HTTP %s — %s", r.status_code, r.text[:150])
        return r.status_code in (200, 201)
    except Exception as exc:
        logger.warning("mark_read_meta: fallo (%s)", exc)
        return False
