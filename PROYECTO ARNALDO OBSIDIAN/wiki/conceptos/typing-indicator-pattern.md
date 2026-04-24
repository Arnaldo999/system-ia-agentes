---
proyecto: compartido
tipo: concepto
created: 2026-04-24
tags: [workers, whatsapp, humanizacion, typing, evolution, meta-graph]
---

# Typing Indicator — "escribiendo..." en todas las respuestas del bot

## Qué es

Módulo compartido `workers/shared/typing_indicator.py` que muestra el indicador "escribiendo..." al usuario antes de cada mensaje que envía el bot. Simula que hay una persona tipeando del otro lado.

## Por qué existe

Sin typing indicator, los mensajes del bot llegan "de la nada" — el usuario ve solo las burbujas aparecer sin contexto visual. Con typing indicator, la percepción humana mejora notoriamente: el usuario ve "Lovbot está escribiendo..." durante 2 segundos antes del mensaje, igual que un humano tipeando.

Complementa [[wiki/conceptos/message-splitter-pattern]] — cuando el saludo se parte en 3 chunks, cada chunk tiene su propio typing indicator antes, dando la sensación de una persona tipeando 3 mensajes seguidos.

## API pública

```python
from workers.shared.typing_indicator import send_typing

send_typing(
    provider="evolution",  # o "meta"
    phone=telefono,
    duration=2.0,
    # Si provider=evolution:
    evolution_url=os.environ.get("EVOLUTION_API_URL"),
    evolution_instance=os.environ.get("MICA_DEMO_EVOLUTION_INSTANCE"),
    evolution_api_key=os.environ.get("EVOLUTION_API_KEY"),
    # Si provider=meta:
    meta_access_token=META_ACCESS_TOKEN,
    meta_phone_id=META_PHONE_ID,
    message_id=ultimo_msg_id_entrante,  # opcional pero recomendado
)
```

## Soporte por provider

### Evolution API
- Endpoint: `POST /chat/sendPresence/{instance}`
- Body: `{"number": phone, "presence": "composing", "delay": ms}`
- ✅ Soporta typing indicator nativo sin context
- Se muestra durante `delay` ms

### Meta Graph API v21.0
- Endpoint: `POST /{phone_id}/messages`
- Body: `{"messaging_product": "whatsapp", "status": "read", "message_id": "<ID>", "typing_indicator": {"type": "text"}}`
- ⚠️ Requiere `message_id` de un mensaje entrante reciente (context-aware)
- Si no hay `message_id` → `send_typing()` bloquea `duration` seg pero no muestra indicator visual

### YCloud
- Sin soporte nativo de typing indicator
- `send_typing()` solo bloquea `duration` seg (efecto de latencia humanizada)

## Comportamiento clave

- **Siempre bloquea** `duration` seg, aunque el indicator falle. El bot necesita la pausa para que la sensación de "escribiendo..." sea coherente.
- **Fallback silencioso**: si el provider no responde, log warning pero no levanta excepción.
- **Feature flag** `TYPING_INDICATOR_ENABLED=false` permite bypass global sin redeploy.

## Uso correcto — wrapper de `_enviar_texto()`

El patrón es wrappear la función `_enviar_texto()` del worker para que SIEMPRE llame `send_typing()` antes del request HTTP real:

```python
def _enviar_texto(telefono: str, mensaje: str, _incoming_message_id: str = "") -> bool:
    _agregar_historial(telefono, "Bot", mensaje)

    # Typing 2s antes de enviar (humanización)
    send_typing(
        provider=_provider_activo(telefono),
        phone=telefono,
        duration=2.0,
        evolution_url=os.environ.get("EVOLUTION_API_URL"),
        evolution_instance=os.environ.get("EVOLUTION_INSTANCE"),
        evolution_api_key=os.environ.get("EVOLUTION_API_KEY"),
        meta_access_token=META_ACCESS_TOKEN,
        meta_phone_id=META_PHONE_ID,
        message_id=_incoming_message_id or None,
    )

    # Resto del código original (envío real)
    ...
```

Así TODOS los mensajes del bot muestran "escribiendo..." antes de llegar.

## Duración recomendada

- **2.0s fijo** — suficiente para humanizar sin ralentizar
- Opcionalmente usar `random_typing_duration(1.8, 2.5)` para variar (más humano, patrón Nexum)
- NO usar menos de 1.5s (no alcanza a renderizarse en WhatsApp móvil)
- NO usar más de 3s (usuario empieza a notar que el bot demora)

## Guardar `ultimo_msg_id` para Meta typing visual

Para que Meta muestre el indicador visual real (no solo pausa), el worker debe guardar el `message_id` entrante en la sesión:

```python
# En el webhook handler:
msg_id_entrante = msg.get("id", "")
if msg_id_entrante:
    sesion = SESIONES.get(tel_clean, {})
    sesion["ultimo_msg_id"] = msg_id_entrante
    SESIONES[tel_clean] = sesion

# En _enviar_texto:
ultimo_msg_id = SESIONES.get(tel_clean, {}).get("ultimo_msg_id")
send_typing(..., message_id=ultimo_msg_id)
```

Robert demo tiene esto implementado (commit `5b21e15`). Mica demo también (commit `888a258`).

## Workers que lo usan

- `workers/clientes/system_ia/demos/inmobiliaria/worker.py` — Mica demo (Evolution + Meta via TP)
- `workers/clientes/lovbot/robert_inmobiliaria/worker.py` — Robert demo (Meta Graph)

## Origen

- Idea del patrón: video de Kevin Bellier (curso agentes conversacionales) + plantilla Nexum Academy
- Diseñado e implementado 2026-04-24 por [[wiki/entidades/arnaldo-ayala]] + Claude
- Commits: `6a2617e` (módulo), `888a258` (Mica integrado), `5b21e15` (Robert integrado)

## Relacionado

- [[wiki/conceptos/message-splitter-pattern]] — cada chunk del saludo tiene su propio typing
- [[wiki/conceptos/message-buffer-debounce]] — typing se activa DESPUÉS del flush del buffer
- [[wiki/conceptos/image-describer]] — cuando hay imagen, se describe ANTES del primer typing
