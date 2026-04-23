"""
workers/shared/message_buffer.py
─────────────────────────────────
Buffer anti-spam de mensajes WhatsApp fragmentados con debounce de N segundos.

Problema que resuelve:
    Los usuarios de WhatsApp mandan mensajes fragmentados tipo:
        "hola"
        "me interesa"
        "un lote de 500m² en zona norte"
    Si el worker responde a cada mensaje por separado, pierde contexto y
    se siente robótico. Este módulo acumula los mensajes en Redis durante
    N segundos desde el último mensaje, y solo cuando el usuario deja de
    escribir lanza el procesamiento con el texto consolidado.

Patrón:
    1. Llega mensaje → push a lista Redis + set timestamp
    2. Se programa un callback diferido (Timer threading) que se despierta
       a los N segundos
    3. Al despertar, compara timestamp guardado vs ahora:
       - Si pasaron >=N seg sin nuevo mensaje → procesa el lote y limpia
       - Si no → otro callback más reciente ya se encargará, este exit

Ventaja vs in-memory dict:
    - Sobrevive a reinicios del worker (TTL Redis)
    - Serializa conversaciones del mismo usuario aunque haya varios
      workers del monorepo procesando el mismo tenant
    - Namespaced por tenant (jamás se mezclan agencias)

API pública:
    buffer_and_schedule(tenant_slug, wa_id, texto, callback, *, extra=None,
                        debounce_seconds=8, separator=" ")

    Se llama en el webhook handler ANTES de lanzar el Thread de _procesar.
    Si `REDIS_BUFFER_URL` no está en env, hace fallback graceful: ejecuta
    el callback inmediato (comportamiento pre-buffer). Esto permite que
    workers en producción sin Redis sigan funcionando sin cambios.

    Parámetros:
        tenant_slug: ID único del cliente (ej: "mica-demo", "robert-demo")
        wa_id: teléfono limpio (solo dígitos, ej "5493765005465")
        texto: mensaje del usuario ya parseado
        callback: función que recibe (wa_id, texto_consolidado, extra)
                  y ejecuta el procesamiento real (típicamente _procesar)
        extra: dict arbitrario del primer mensaje (ej {"referral": {...}})
               Se preserva del PRIMER mensaje del lote (ads de Meta traen
               referral solo en el msg inicial).
        debounce_seconds: ventana de espera desde último mensaje (default 8)
        separator: string entre mensajes del lote al concatenar (default " ")

Feature flag:
    MESSAGE_BUFFER_ENABLED (env var)
        "true" (default si hay REDIS_BUFFER_URL) → buffer activo
        "false" → bypass total, callback directo (útil para debug)

Diseño:
    - Sin dependencias asyncio: usa threading.Timer para respetar el patrón
      sync-in-thread de los workers existentes
    - Un solo callback diferido por usuario a la vez: si llega nuevo msg
      antes del debounce, el callback viejo al despertar ve que el timestamp
      cambió y hace exit sin procesar
    - Keys con TTL automático (debounce_seconds + 10) por si el callback
      nunca se dispara (Redis limpia solo)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_REDIS_CLIENT = None
_REDIS_INIT_LOCK = threading.Lock()


def _get_redis():
    """
    Lazy init del cliente Redis. Devuelve None si no hay REDIS_BUFFER_URL
    o si la conexión falla (fallback graceful).
    """
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    with _REDIS_INIT_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        url = os.environ.get("REDIS_BUFFER_URL")
        if not url:
            logger.info("message_buffer: REDIS_BUFFER_URL no seteado, fallback sin buffer")
            return None
        try:
            import redis
            client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            client.ping()
            _REDIS_CLIENT = client
            logger.info("message_buffer: conectado a Redis OK")
            return client
        except Exception as exc:
            logger.warning("message_buffer: fallo al conectar Redis (%s), fallback sin buffer", exc)
            return None


def _buffer_enabled() -> bool:
    flag = os.environ.get("MESSAGE_BUFFER_ENABLED", "").lower()
    if flag == "false":
        return False
    return True


def _key_msgs(tenant: str, wa_id: str) -> str:
    return f"buffer:msgs:{tenant}:{wa_id}"


def _key_ts(tenant: str, wa_id: str) -> str:
    return f"buffer:last_ts:{tenant}:{wa_id}"


def _key_extra(tenant: str, wa_id: str) -> str:
    return f"buffer:extra:{tenant}:{wa_id}"


def buffer_and_schedule(
    tenant_slug: str,
    wa_id: str,
    texto: str,
    callback: Callable[[str, str, Optional[dict]], Any],
    *,
    extra: Optional[dict] = None,
    debounce_seconds: int = 8,
    separator: str = " ",
) -> None:
    """
    Acumula `texto` en el buffer del usuario y programa un callback diferido
    que procesa el lote cuando pasen `debounce_seconds` sin nuevo mensaje.

    No bloquea: retorna inmediatamente tras registrar el mensaje.

    Si Redis no está disponible o el flag desactivado, ejecuta callback
    inmediato con el texto crudo (bypass).
    """
    if not _buffer_enabled():
        _run_callback_safe(callback, wa_id, texto, extra)
        return

    r = _get_redis()
    if r is None:
        _run_callback_safe(callback, wa_id, texto, extra)
        return

    ttl = debounce_seconds + 10
    now_ms = int(time.time() * 1000)
    key_m = _key_msgs(tenant_slug, wa_id)
    key_t = _key_ts(tenant_slug, wa_id)
    key_e = _key_extra(tenant_slug, wa_id)

    try:
        pipe = r.pipeline()
        pipe.rpush(key_m, texto)
        pipe.expire(key_m, ttl)
        pipe.set(key_t, now_ms, ex=ttl)
        if extra is not None:
            pipe.set(key_e, json.dumps(extra), ex=ttl, nx=True)
        pipe.execute()
    except Exception as exc:
        logger.warning("message_buffer: fallo guardando en Redis (%s), fallback directo", exc)
        _run_callback_safe(callback, wa_id, texto, extra)
        return

    timer = threading.Timer(
        debounce_seconds,
        _flush_if_ready,
        args=(tenant_slug, wa_id, now_ms, callback, separator),
    )
    timer.daemon = True
    timer.start()


def _flush_if_ready(
    tenant_slug: str,
    wa_id: str,
    scheduled_ts: int,
    callback: Callable[[str, str, Optional[dict]], Any],
    separator: str,
) -> None:
    """
    Callback diferido. Se despierta tras `debounce_seconds` y decide si
    procesa el lote o deja que otro callback más reciente se encargue.
    """
    r = _get_redis()
    if r is None:
        return

    key_m = _key_msgs(tenant_slug, wa_id)
    key_t = _key_ts(tenant_slug, wa_id)
    key_e = _key_extra(tenant_slug, wa_id)

    try:
        last_ts_raw = r.get(key_t)
        if last_ts_raw is None:
            return
        last_ts = int(last_ts_raw)
        if last_ts != scheduled_ts:
            return

        msgs = r.lrange(key_m, 0, -1) or []
        extra_raw = r.get(key_e)
        extra = json.loads(extra_raw) if extra_raw else None

        pipe = r.pipeline()
        pipe.delete(key_m)
        pipe.delete(key_t)
        pipe.delete(key_e)
        pipe.execute()
    except Exception as exc:
        logger.error("message_buffer: fallo leyendo lote (%s)", exc)
        return

    if not msgs:
        return

    texto_consolidado = separator.join(m for m in msgs if m)
    logger.info(
        "message_buffer: flush tenant=%s wa_id=%s parts=%d len=%d",
        tenant_slug, wa_id, len(msgs), len(texto_consolidado),
    )
    _run_callback_safe(callback, wa_id, texto_consolidado, extra)


def _run_callback_safe(
    callback: Callable[[str, str, Optional[dict]], Any],
    wa_id: str,
    texto: str,
    extra: Optional[dict],
) -> None:
    """
    Ejecuta el callback en un thread daemon (mismo patrón que los workers
    actuales). Captura excepciones para que un callback roto no deje el
    buffer en estado inconsistente.
    """
    def _runner():
        try:
            callback(wa_id, texto, extra)
        except Exception:
            logger.exception("message_buffer: callback falló wa_id=%s", wa_id)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
