"""
workers/shared/message_splitter.py
────────────────────────────────────
Particionador de mensajes del bot en 2-3 chunks para humanizar el saludo
inicial. Usa gpt-4o-mini como splitter barato.

Patrón:
    Bot genera saludo largo:
        "¡Hola Arnaldo! Bienvenido a System IA. Somos una desarrolladora
         inmobiliaria en Misiones con proyectos en San Ignacio. Atendemos
         de lunes a viernes 9-18hs. ¿Con quién tengo el gusto?"

    Splitter devuelve:
        ["¡Hola Arnaldo! 👋 Bienvenido a System IA",
         "Somos una desarrolladora inmobiliaria en Misiones (San Ignacio,
          Gdor Roca, Apóstoles). Atendemos lunes a viernes 9-18hs",
         "¿Con quién tengo el gusto de conversar? 😉"]

    Worker envía cada chunk con delay + typing indicator entre medio.

Cuándo usar:
    SOLO para el saludo inicial / presentación / horarios de atención.
    NUNCA para el flow BANT posterior (presupuesto, zona, tipo de
    propiedad, etc) — esos mensajes deben ir consolidados.

    El worker es responsable de decidir si llamar split_greeting() o no
    según el turno de la conversación. Typical check:
        es_primer_turno = sesion["cantidad_mensajes_bot"] == 0

API pública:
    split_greeting(texto, *, max_chunks=3, lang="es") -> list[str]

    Devuelve una lista de 1 a max_chunks strings. Si falla la llamada al
    LLM o el texto es corto, devuelve [texto] (1 chunk, comportamiento
    pre-feature).

Feature flag:
    MESSAGE_SPLITTER_ENABLED (env, default "true")
    MESSAGE_SPLITTER_MODEL (env, default "gpt-4o-mini")

Costo:
    gpt-4o-mini ≈ $0.0001 por partición. Solo se llama una vez por
    conversación (primer turno). Despreciable.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    flag = os.environ.get("MESSAGE_SPLITTER_ENABLED", "").lower()
    if flag == "false":
        return False
    return True


_SYSTEM_PROMPT = """Sos un editor de mensajes WhatsApp. Recibís un mensaje largo del bot y lo partís en HASTA 3 mensajes más cortos para simular conversación humana.

Reglas IRROMPIBLES:
1. NO perdés contenido. Todo lo del mensaje original tiene que aparecer en algún chunk.
2. NO cambias el sentido, tono ni emojis. Solo cortás.
3. Cortás en puntos naturales (oración terminada, idea completa). NUNCA en medio de una oración.
4. Cada chunk debe tener sentido por sí mismo cuando se lee solo.
5. Si el mensaje es corto (< 120 caracteres o 1 sola oración), devolvés 1 solo chunk.
6. Preferís que los chunks queden parejos en largo, no uno gigante y otros chiquitos.
7. NO agregás contenido nuevo, NO reformulás, NO corregís ortografía.
8. NO agregás prefijos ("Parte 1:", "•", etc). Solo el contenido tal cual.

Respondés SIEMPRE en formato JSON estricto:
{"chunks": ["chunk1", "chunk2", "chunk3"]}

Si es 1 solo chunk: {"chunks": ["texto completo"]}
Si son 2 chunks: {"chunks": ["parte1", "parte2"]}
Si son 3 chunks: {"chunks": ["parte1", "parte2", "parte3"]}"""


def split_greeting(
    texto: str,
    *,
    max_chunks: int = 3,
    lang: str = "es",
    api_key: Optional[str] = None,
) -> List[str]:
    """
    Parte un texto en 1-max_chunks strings. Fallback a [texto] si falla.

    No levanta excepciones salvo bugs de programación.

    `api_key`: si no se pasa, intenta leer OPENAI_API_KEY del env. Si
    tampoco está, intenta LOVBOT_OPENAI_API_KEY (worker Robert) y
    MICA_OPENAI_API_KEY (por si algún día se separa). Esto permite que
    cada worker pase su propia clave sin depender de nombres de env var.
    """
    if not texto:
        return [texto]

    if not _enabled():
        return [texto]

    # Guard: si es muy corto, no tiene sentido partir
    if len(texto) < 120:
        return [texto]

    resolved_key = (
        api_key
        or os.environ.get("OPENAI_API_KEY", "")
        or os.environ.get("LOVBOT_OPENAI_API_KEY", "")
        or os.environ.get("MICA_OPENAI_API_KEY", "")
    )
    if not resolved_key:
        logger.warning("message_splitter: ninguna OPENAI_API_KEY disponible (ni OPENAI_API_KEY, LOVBOT_OPENAI_API_KEY, MICA_OPENAI_API_KEY)")
        return [texto]
    api_key = resolved_key

    model = os.environ.get("MESSAGE_SPLITTER_MODEL", "gpt-4o-mini")

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Mensaje a partir:\n{texto}"},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": 1000,
            },
            timeout=10,
        )
    except requests.exceptions.Timeout:
        logger.warning("message_splitter: timeout llamando a OpenAI")
        return [texto]
    except Exception as exc:
        logger.warning("message_splitter: fallo request (%s)", exc)
        return [texto]

    if r.status_code != 200:
        logger.warning("message_splitter: OpenAI HTTP %s — %s", r.status_code, r.text[:200])
        return [texto]

    try:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        chunks = parsed.get("chunks", [])
        if not isinstance(chunks, list):
            return [texto]
        # Validar: que sean strings, que no estén vacíos, que no excedan max_chunks
        clean = [c.strip() for c in chunks if isinstance(c, str) and c.strip()]
        if not clean:
            return [texto]
        if len(clean) > max_chunks:
            clean = clean[:max_chunks]
        # Validar que no se perdió contenido (heurística: la longitud total
        # debe ser >= 80% del original — si cae mucho algo se perdió)
        total_len = sum(len(c) for c in clean)
        if total_len < len(texto) * 0.7:
            logger.warning(
                "message_splitter: chunks perdieron contenido (%d → %d) — fallback",
                len(texto), total_len,
            )
            return [texto]
        logger.info(
            "message_splitter: ok chunks=%d len_orig=%d",
            len(clean), len(texto),
        )
        return clean
    except Exception as exc:
        logger.warning("message_splitter: fallo parsing (%s)", exc)
        return [texto]


def split_by_paragraphs(texto: str, max_chunks: int = 3) -> List[str]:
    """
    Fallback local sin LLM: parte por doble salto de línea. Útil si el
    bot ya formatea con párrafos claros y querés ahorrar la llamada LLM.

    Devuelve hasta max_chunks chunks. Si hay menos párrafos, devuelve los
    que haya. Si hay más, concatena los últimos en el último chunk.
    """
    if not texto:
        return [texto]

    parts = [p.strip() for p in re.split(r'\n\s*\n', texto) if p.strip()]
    if not parts:
        return [texto]
    if len(parts) <= max_chunks:
        return parts
    # Más párrafos que max_chunks → juntar los últimos
    head = parts[: max_chunks - 1]
    tail = "\n\n".join(parts[max_chunks - 1:])
    return head + [tail]
