---
proyecto: compartido
tipo: sintesis
created: 2026-04-23
tags: [sesion, redis, buffer, vision, imagen, humanizacion, workers-demo, waba-routing]
---

# Sesión 2026-04-23 — Humanización workers con Redis buffer + Vision GPT

## Contexto

Sesión nocturna de Arnaldo + Claude, ~5 horas (17:00 → 22:30 ART). Foco: humanizar los bots demo de Mica y Robert implementando 2 features del curso de Kevin Bellier (n8n+Redis) y Nexum Academy (ManyChat+n8n) pero en Python puro dentro del monorepo FastAPI, sin n8n.

Arnaldo trajo videos de Kevin y plantilla Nexum. Evaluamos qué aplicar y qué descartar — concluimos que su stack (FastAPI + workers Python + Coolify) ya supera ManyChat para casi todo; solo valía robar 3 ideas específicas:
1. Buffer debounce 8s con Redis
2. Normalizador de imagen (audio ya lo tenían)
3. Partición de respuesta en 2-3 chunks (no se implementó en esta sesión)

Bonus no planificado: **fix de un bug preexistente** (routing WABA Meta Graph roto tras migración Coolify Hetzner del día anterior).

## Decisiones clave

1. **No migrar a n8n/ManyChat** — el stack Python actual es más potente. Solo replicar los 2 patrones específicos.
2. **Redis separado del de Chatwoot** — 2 instancias Redis nuevas (1 por VPS). Chatwoot usa su propio Redis con políticas de eviction agresivas (`allkeys-lru`) que arruinarían un buffer efímero; mezclar sería SPoF.
3. **Módulo compartido `workers/shared/message_buffer.py`** con API genérica, usado por ambos demos. Evita duplicar código.
4. **Tenant slugs establecidos**: `mica-demo`, `robert-demo` (namespacing Redis keys).
5. **Ventana buffer 8s** (entre los 7s de Kevin y 10s de Nexum — LATAM escribe lento).
6. **Subagentes por proyecto** — proyecto-mica y proyecto-robert trabajaron en paralelo, cada uno con su worker. Regla de aislamiento respetada 100%.

## Infraestructura creada

### Coolify Hetzner (Robert)
- Servicio Redis nuevo: `redis-workers` en project **Agentes** (junto a `system-ia-agentes`, `lovbot-crm-modelo`, `lovbot-admin-internal`)
- Imagen `redis:7.2`, sin persistencia AOF, puerto no expuesto
- UUID: `agws408ss8wg48040kk8w880`

### Coolify Hostinger (Arnaldo/Mica)
- Servicio Redis nuevo: `redis-workers` en project **microservicios** (junto a `system-ia-agentes` backend shared)
- Misma config que Hetzner
- UUID: `q11d3uxyizlkwinvhw0d8lgs`

### Env vars agregadas
- `REDIS_BUFFER_URL` en `system-ia-agentes` Hetzner y Hostinger

## Bugs descubiertos y fixeados

### Bug 1 — Coolify v4 beta marca env vars como `is_preview: True` por default
Al crear env vars por UI, Coolify las creaba con flag `is_preview: True` — excluidas de deploys production. Síntoma: `KeyError: 'REDIS_BUFFER_URL'` en runtime aunque la API de Coolify confirmara que existía. Fix: borrar + recrear sin tocar "Is Preview".

Documentado en [[wiki/conceptos/message-buffer-debounce]].

### Bug 2 — Tabla `waba_clients` no se clonó a `lovbot_crm_modelo`
Bot Robert demo dejó de responder tras la migración Coolify del 2026-04-23. Logs:
```
[META-EVENTS] phone_id='735319949657644' no registrado en waba_clients — ignorado
[DB] Error obtener_waba_client_por_phone: relation "waba_clients" does not exist
```

Causa: el script de clonado de `lovbot_crm_modelo` (DB modelo para clientes nuevos) no incluye `waba_clients` en el schema. Tras la migración, la DB nueva no tenía esa tabla de routing multi-tenant.

Fix aplicado:
1. `POST /admin/waba/setup-table` → crear tabla (idempotente)
2. `POST /admin/waba/register-existing` con phone_id `735319949657644` → registrar bot Robert demo

Fix pendiente (deuda): incluir `waba_clients` en seed SQL de `lovbot_crm_modelo`.

Documentado en auto-memory silo 1.

### Bug 3 — OpenAI Vision rechazaba bytes de Evolution
Síntoma: `HTTP 400 — "You uploaded an unsupported image"`. Causa: las URLs `imageMessage.url` que devuelve Evolution apuntan a media **encriptado** de WhatsApp — un GET directo no devuelve bytes de imagen real.

Fix: usar endpoint `/chat/getBase64FromMediaMessage/{instance}` de Evolution que descifra internamente. Patrón copiado del worker de Lau que ya lo hacía bien.

## Commits pusheados a `Arnaldo999/system-ia-agentes` master:main

1. `dbaca83` — `chore(backend)`: agregar `redis>=5.0.0` a requirements.txt
2. `58d5d85` — `feat(shared)`: message_buffer con Redis debounce 8s
3. `3cafbc1` — `feat(mica-demo/inmobiliaria)`: integrar message_buffer
4. `3d4753b` — `feat(robert-demo/inmobiliaria)`: integrar message_buffer
5. `1de9697` — `feat(shared)`: image_describer con GPT-4o-mini Vision
6. `8236a0e` — `refactor(wa_provider)`: normalizar tipos image/audio Evolution
7. `bb42bd5` — `feat(mica-demo/inmobiliaria)`: integrar image_describer
8. `153330e` — `feat(robert-demo/inmobiliaria)`: integrar image_describer
9. `6158186` — `fix(image_describer)`: sanitizar mime antes de OpenAI Vision
10. `5f9e178` — `fix(image_describer,mica-demo)`: descarga correcta Evolution + guard bytes

## Validación end-to-end

### Buffer (ambos bots)
Smoke test Python en terminal del container:
```
CALLBACK OK → 5491100000000 'hola me interesa un lote 500m²' {'referral': None}
RESULTS: 1 callbacks invocados (esperamos 1)
```

Test WhatsApp real (Arnaldo mandó 3 mensajes fragmentados "Hola / como / estas"):
- Mica: respondió 1 vez consolidado con BANT arrancado
- Robert: respondió 1 vez consolidado reconociendo sesión previa ("Zona Centro, 50k")

Logs en ambos backends:
```
message_buffer: flush tenant=mica-demo wa_id=... parts=3 len=15
message_buffer: flush tenant=robert-demo wa_id=... parts=3 len=15
```

### Image describer (ambos bots)
- Robert: foto de mansión con pileta → describer generó 355 chars → LLM recibió contexto + saludó con BANT
- Mica: foto de casa una planta → describer generó 327 chars (después del fix de Evolution download) → LLM saludó con onboarding BANT

El describer funciona; que el LLM priorice saludo BANT sobre reconocer explícitamente la imagen es decisión del system prompt, no del describer.

## Workers intocados

Respetando [[wiki/conceptos/regla-de-atribucion]] y [[wiki/conceptos/aislamiento-entre-agencias]]:

- ❌ `workers/clientes/arnaldo/maicol/` — Maicol producción
- ❌ `workers/clientes/arnaldo/prueba/` — Lau (si es LIVE)
- ❌ `workers/clientes/system_ia/lau/` — Lau
- ❌ `workers/clientes/lovbot/test_arnaldo/` — test
- ❌ `workers/clientes/lovbot/inmobiliaria_garcia/` — cliente real Robert
- ❌ `workers/demos/inmobiliaria/` / `workers/demos/gastronomico/` — demos viejos Arnaldo
- ❌ `workers/social/` — social LIVE

Solo tocados: los 2 workers demo acordados + módulos compartidos.

## Pendiente para próxima sesión

1. **Feature #3 — Typing indicator** (~20 min) — llamar endpoint de presencia del provider antes de enviar respuesta ("escribiendo..."). Evolution tiene `/chat/sendPresence`, Meta soporta typing_indicator en sendMessage.
2. **Feature #4 — Partición respuesta 2-3 chunks** (~40 min) — un LLM helper que corte el saludo/presentación/horarios en mensajes separados con delay. Aplicar SOLO al onboarding (nombre, bienvenida, horarios) — NUNCA al flow BANT posterior que ya funciona consolidado.
3. **Deuda técnica** — incluir `waba_clients` en seed SQL de `lovbot_crm_modelo` para que se clone automáticamente a DB de clientes nuevos.

## Relacionado

- [[wiki/conceptos/message-buffer-debounce]]
- [[wiki/conceptos/image-describer]]
- [[wiki/entidades/kevin-bellier]] (mentor)
- [[wiki/conceptos/manychat-plantilla-nexum]] (referencia)
- [[wiki/sintesis/2026-04-23-migracion-lovbot-coolify]] (migración del día anterior que causó el bug waba_clients)
