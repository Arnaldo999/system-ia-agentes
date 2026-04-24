---
proyecto: compartido
tipo: concepto
created: 2026-04-23
tags: [workers, whatsapp, redis, debounce, patron-kevin, buffer]
---

# Message Buffer — debounce anti-spam de mensajes WhatsApp fragmentados

## Qué es

Módulo compartido `workers/shared/message_buffer.py` en el monorepo `system-ia-agentes` que acumula mensajes WhatsApp fragmentados de un mismo usuario en Redis durante N segundos (default 8), y solo cuando el usuario deja de escribir dispara el procesamiento consolidado.

Reemplaza al `threading.Thread(target=_procesar, ...).start()` directo que tenían los workers antes.

## Por qué existe

En WhatsApp los usuarios escriben fragmentado:
- "hola"
- "me interesa"
- "un lote 500m² zona norte"

Sin buffer el worker procesa 3 webhooks separados, llama al LLM 3 veces, responde 3 mensajes descoordinados. Con buffer: consolida a "hola me interesa un lote 500m² zona norte" y responde 1 sola vez con contexto completo.

Patrón extraído del curso de [[wiki/entidades/kevin-bellier]] (n8n + Redis) y validado contra la plantilla [[wiki/conceptos/manychat-plantilla-nexum]].

## Comportamiento

1. Llega mensaje → push a lista Redis (`buffer:msgs:{tenant}:{wa_id}`) + set timestamp
2. Timer threading de 8s
3. Al despertar, compara timestamp guardado vs el programado:
   - **Igual** → no llegó mensaje nuevo → flush, concatena, llama callback
   - **Distinto** → otro mensaje reseteó el buffer → exit sin procesar (otro timer más reciente se encargará)

## Keys Redis (namespaced por tenant)

- `buffer:msgs:{tenant_slug}:{wa_id}` — lista de mensajes
- `buffer:last_ts:{tenant_slug}:{wa_id}` — timestamp último
- `buffer:extra:{tenant_slug}:{wa_id}` — dict arbitrario del primer msg (ej referral de Meta Ads)

TTL automático = `debounce_seconds + 10` por seguridad.

## Aislamiento entre agencias

El tenant_slug namespacea las keys. Slugs establecidos:
- `mica-demo` → worker `workers/clientes/system_ia/demos/inmobiliaria/worker.py`
- `robert-demo` → worker `workers/clientes/lovbot/robert_inmobiliaria/worker.py`

Compatible con [[wiki/conceptos/aislamiento-entre-agencias]]. Aunque haya una sola instancia de Redis en cada Coolify (Hostinger / Hetzner), las conversaciones nunca se cruzan porque las keys tienen el slug.

## Infra

| VPS | Redis | Backends que lo usan |
|---|---|---|
| Coolify Hostinger | service `redis-workers` (project microservicios) | `system-ia-agentes` → workers Arnaldo + Mica |
| Coolify Hetzner | service `redis-workers` (project Agentes) | `system-ia-agentes` → workers Robert |

- Imagen: `redis:7.2`
- Sin persistencia AOF (buffer efímero 8s)
- Puerto NO expuesto al host — solo red interna Docker
- Env var `REDIS_BUFFER_URL` en cada backend apunta al Redis interno

## Uso

```python
from workers.shared.message_buffer import buffer_and_schedule

def _procesar_from_buffer(wa_id: str, texto: str, extra: dict | None):
    referral = (extra or {}).get("referral")
    _procesar(wa_id, texto, referral)

buffer_and_schedule(
    tenant_slug="mica-demo",
    wa_id=tel_clean,
    texto=texto,
    callback=_procesar_from_buffer,
    extra={"referral": referral},
    debounce_seconds=8,
)
```

## Fallbacks y failure modes

- Sin `REDIS_BUFFER_URL` en env → callback directo (comportamiento pre-buffer)
- Redis no responde al ping → callback directo (log warning)
- Feature flag `MESSAGE_BUFFER_ENABLED=false` → bypass total
- Callback lanza excepción → capturada + log, no rompe el módulo

## Logs esperados

Exitoso:
```
message_buffer: conectado a Redis OK
POST /clientes/.../whatsapp HTTP/1.1 200 OK  (x3)
message_buffer: flush tenant=mica-demo wa_id=5493765384843 parts=3 len=15
```

`parts` = cantidad de mensajes consolidados. `len` = caracteres del texto final.

## Bug conocido — "Is Preview" flag en Coolify v4 beta

Al crear env vars nuevas por UI, Coolify a veces marca `is_preview: True` por default. Eso hace que la var NO se inyecte al container en production. Síntoma: `KeyError: 'REDIS_BUFFER_URL'` aunque la API diga que existe. Fix: recrear la env var sin marcar "Is Preview".

Validado y documentado en feedback auto-memory.

## Origen y validación

- Diseñado e implementado 2026-04-23 por [[wiki/entidades/arnaldo-ayala]] + Claude
- Commits de integración: `58d5d85` (módulo), `3cafbc1` (Mica), `3d4753b` (Robert)
- Smoke tests Python + tests E2E WhatsApp reales confirmados en logs
- Patrón Kevin Bellier — ver su video curso [agentes conversacionales]

## Relacionado

- [[wiki/conceptos/image-describer]] — normaliza imágenes a texto ANTES del buffer
- [[wiki/conceptos/regla-de-atribucion]] — cada worker en su proyecto correcto
- [[wiki/entidades/coolify-arnaldo]] / [[wiki/entidades/coolify-robert]]
