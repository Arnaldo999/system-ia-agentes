"""
workers/shared/image_describer.py
──────────────────────────────────
Normalizador de imágenes entrantes en WhatsApp → descripción textual.

Cuando el usuario manda una foto (plano, ficha, propiedad, plano de lote),
el LLM principal del worker trabaja solo con texto. Este módulo convierte
la imagen a una descripción textual usando gpt-4o-mini vision, para que
el contexto llegue completo al LLM conversacional.

Ejemplo:
    Usuario: [foto de un plano de loteo] + caption "¿cuánto este?"
    Sin normalizador: LLM ve "¿cuánto este?" → responde genérico
    Con normalizador: LLM ve "[Imagen: plano con 12 lotes numerados, zona
                              norte, frente urbano] ¿cuánto este?"

API pública:
    describe_image(image_bytes, *, mime="image/jpeg",
                   context_hint=None, max_words=80) -> str

    Recibe bytes de la imagen (descargada por el worker desde Meta Graph
    API, Evolution API, YCloud, etc.) y devuelve una descripción breve en
    español. Si falla algo (API key faltante, imagen corrupta, timeout),
    devuelve string vacío — el worker debe seguir sin romper.

Configuración:
    OPENAI_API_KEY (env) — clave para gpt-4o-mini vision
    IMAGE_DESCRIBER_ENABLED (env, default "true") — feature flag
    IMAGE_DESCRIBER_MODEL (env, default "gpt-4o-mini") — modelo a usar

Costo:
    gpt-4o-mini vision ≈ $0.00015 por imagen pequeña. Despreciable.

Diseño:
    - No introduce asyncio: llamada síncrona con timeout corto (15s)
    - Base64 inline (no upload a storage): usa data URL directo a OpenAI
    - Fallback silencioso: si algo falla, devuelve "" (no None, no excepción)
      para que el worker pueda concatenar sin manejar casos especiales
    - Prompt orientado a contexto inmobiliario por defecto, pero configurable
      con `context_hint` para otros nichos (gastronomía, etc)
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_DEFAULT_CONTEXT = (
    "Contexto: imagen enviada por un lead en WhatsApp a un bot inmobiliario "
    "(lotes, casas, departamentos, locales). La imagen puede ser: plano de "
    "loteo/manzana, ficha de propiedad, foto de inmueble, mapa, captura de "
    "precio, documento (DNI/escritura), selfie, o irrelevante (meme, sticker)."
)


def _describer_enabled() -> bool:
    flag = os.environ.get("IMAGE_DESCRIBER_ENABLED", "").lower()
    if flag == "false":
        return False
    return True


_ALLOWED_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _detect_mime_from_bytes(data: bytes) -> str:
    """
    Detecta el mime inspeccionando los primeros bytes (magic numbers).
    Devuelve uno de los 4 mimes que OpenAI acepta, o "image/jpeg" como fallback.
    """
    if not data or len(data) < 4:
        return "image/jpeg"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _sanitize_mime(mime: str, image_bytes: bytes) -> str:
    """
    OpenAI Vision solo acepta image/jpeg, png, gif, webp. Si el mime declarado
    no cumple (p.ej. 'application/octet-stream' que Evolution a veces manda),
    detectamos por magic numbers.
    """
    m = (mime or "").lower().split(";")[0].strip()
    if m in _ALLOWED_MIMES:
        return m
    detected = _detect_mime_from_bytes(image_bytes)
    logger.info("image_describer: mime reemplazado de '%s' a '%s'", mime, detected)
    return detected


def _looks_like_image(image_bytes: bytes) -> bool:
    """True si los primeros bytes matchean algún formato de imagen conocido."""
    if not image_bytes or len(image_bytes) < 12:
        return False
    if image_bytes[:3] == b"\xff\xd8\xff":
        return True
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return True
    return False


def describe_image(
    image_bytes: bytes,
    *,
    mime: str = "image/jpeg",
    context_hint: Optional[str] = None,
    max_words: int = 80,
) -> str:
    """
    Devuelve una descripción textual de la imagen en español.

    Si falla (sin API key, bytes vacíos, timeout, error HTTP), devuelve
    string vacío. El worker debe tratar "" como "no hay descripción" y
    continuar.

    No levanta excepciones salvo bugs de programación.
    """
    if not _describer_enabled():
        return ""
    if not image_bytes:
        return ""

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("image_describer: OPENAI_API_KEY no seteado")
        return ""

    model = os.environ.get("IMAGE_DESCRIBER_MODEL", "gpt-4o-mini")
    context = context_hint or _DEFAULT_CONTEXT

    # Guard: los bytes deben ser una imagen real. Evolution/WhatsApp a veces
    # devuelven payloads encriptados/HTML si falta auth — mandarlos a OpenAI
    # solo gasta tokens y devuelve 400.
    if not _looks_like_image(image_bytes):
        hex_prefix = image_bytes[:16].hex() if image_bytes else ""
        logger.warning(
            "image_describer: bytes no son imagen válida — size=%d first_bytes_hex=%s",
            len(image_bytes), hex_prefix,
        )
        return ""

    safe_mime = _sanitize_mime(mime, image_bytes)
    logger.info(
        "image_describer: bytes OK size=%d mime_final=%s", len(image_bytes), safe_mime,
    )

    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{safe_mime};base64,{b64}"
    except Exception as exc:
        logger.warning("image_describer: fallo encoding base64 (%s)", exc)
        return ""

    prompt = (
        f"{context}\n\n"
        f"Describí la imagen en español rioplatense, máximo {max_words} palabras. "
        "Mencioná: tipo de contenido (plano/ficha/foto/etc), datos visibles "
        "relevantes (zona, precio, superficie, dirección si aparecen), y si es "
        "irrelevante para una conversación inmobiliaria decilo breve. "
        "No inventes datos que no veas. No uses formato markdown, solo texto plano."
    )

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                "max_tokens": 200,
                "temperature": 0.2,
            },
            timeout=15,
        )
    except requests.exceptions.Timeout:
        logger.warning("image_describer: timeout llamando a OpenAI vision")
        return ""
    except Exception as exc:
        logger.warning("image_describer: fallo request OpenAI (%s)", exc)
        return ""

    if resp.status_code != 200:
        logger.warning(
            "image_describer: OpenAI HTTP %s — %s",
            resp.status_code, resp.text[:200],
        )
        return ""

    try:
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        descripcion = choices[0].get("message", {}).get("content", "").strip()
        logger.info("image_describer: ok len=%d model=%s", len(descripcion), model)
        return descripcion
    except Exception as exc:
        logger.warning("image_describer: fallo parsing response (%s)", exc)
        return ""


def download_media_meta(media_id: str, meta_access_token: str) -> tuple[bytes, str]:
    """
    Descarga un media de Meta Graph API por media_id.

    Devuelve (bytes, mime_type). Si falla devuelve (b"", "").
    Helper compartido para que los workers Meta (Robert) no repitan lógica.
    """
    if not media_id or not meta_access_token:
        return b"", ""
    try:
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{media_id}",
            headers={"Authorization": f"Bearer {meta_access_token}"},
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning(
                "image_describer: error obteniendo URL media %s — %s",
                r.status_code, r.text[:200],
            )
            return b"", ""
        meta = r.json()
        media_url = meta.get("url", "")
        mime = meta.get("mime_type", "image/jpeg")
        if not media_url:
            return b"", ""
        r2 = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {meta_access_token}"},
            timeout=20,
        )
        if r2.status_code != 200:
            logger.warning("image_describer: error descargando media %s", r2.status_code)
            return b"", ""
        return r2.content, mime
    except Exception as exc:
        logger.warning("image_describer: fallo descargando media (%s)", exc)
        return b"", ""


def download_media_url(url: str, bearer_token: Optional[str] = None) -> tuple[bytes, str]:
    """
    Descarga una imagen desde URL pública (YCloud u otro provider con URLs directas).

    NOTA: las URLs `imageMessage.url` que devuelve Evolution apuntan a media
    encriptado de WhatsApp y no se pueden descargar directamente. Para
    Evolution usar `download_media_evolution()` con el message_id.

    Devuelve (bytes, mime_type). Si falla devuelve (b"", "").
    """
    if not url:
        return b"", ""
    headers = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            logger.warning("image_describer: error descargando url %s", r.status_code)
            return b"", ""
        mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        return r.content, mime
    except Exception as exc:
        logger.warning("image_describer: fallo descargando url (%s)", exc)
        return b"", ""


def download_media_evolution(
    message_id: str,
    evolution_url: str,
    evolution_instance: str,
    evolution_api_key: str,
) -> tuple[bytes, str]:
    """
    Descarga un media de Evolution API usando el endpoint getBase64FromMediaMessage.

    Evolution no expone URLs descargables directas — usa un endpoint específico
    que descifra el media de WhatsApp y devuelve base64. Este helper prueba las
    variantes conocidas de distintas versiones de Evolution (v1 y v2).

    Devuelve (bytes, mime_type). Si falla devuelve (b"", "").
    """
    if not message_id or not evolution_url or not evolution_instance:
        return b"", ""

    base = evolution_url.rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "apikey": evolution_api_key,
    }

    endpoints = [
        {
            "method": "POST",
            "url": f"{base}/chat/getBase64FromMediaMessage/{evolution_instance}",
            "json": {"message": {"key": {"id": message_id}}},
        },
        {
            "method": "POST",
            "url": f"{base}/chat/getBase64FromMediaMessage/{evolution_instance}",
            "json": {"key": {"id": message_id}},
        },
        {
            "method": "GET",
            "url": f"{base}/chat/getMediaMessage/{evolution_instance}/{message_id}",
            "json": None,
        },
    ]

    for ep in endpoints:
        try:
            if ep["method"] == "POST":
                r = requests.post(ep["url"], headers=headers, json=ep["json"], timeout=20)
            else:
                r = requests.get(ep["url"], headers=headers, timeout=20)

            if r.status_code not in (200, 201):
                logger.info(
                    "image_describer: Evolution endpoint %s devolvió %s",
                    ep["url"].rsplit("/", 2)[-2], r.status_code,
                )
                continue

            data = r.json() if r.content else {}
            if not isinstance(data, dict):
                continue

            b64 = (
                data.get("base64")
                or data.get("mediaBase64")
                or data.get("media")
                or ""
            )
            if not b64:
                continue

            try:
                img_bytes = base64.b64decode(b64)
            except Exception as exc:
                logger.warning("image_describer: fallo decodificando base64 Evolution (%s)", exc)
                continue

            mime = (
                data.get("mimetype")
                or data.get("mimeType")
                or "image/jpeg"
            )
            return img_bytes, mime

        except Exception as exc:
            logger.warning("image_describer: fallo Evolution endpoint %s (%s)", ep["url"], exc)
            continue

    logger.warning(
        "image_describer: ningún endpoint Evolution devolvió media para message_id=%s",
        message_id,
    )
    return b"", ""
