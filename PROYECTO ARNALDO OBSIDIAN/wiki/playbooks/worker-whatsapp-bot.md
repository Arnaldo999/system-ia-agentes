---
name: Playbook — Worker WhatsApp Bot (vertical inmobiliaria/gastronomía/turismo)
description: Patrón estándar para crear bot WhatsApp conversacional con metodología BANT, presentación 1-a-1 sin menús, parsing LLM tolerante, y deploy en Coolify. Aplica a los 3 proyectos (Arnaldo/Robert/Mica) con el provider correcto de cada uno.
type: playbook
proyecto: compartido
tags: [whatsapp, bot, bant, worker, fastapi, playbook]
version: 1
ultima_actualizacion: 2026-04-24
casos_aplicados: [maicol-back-urbanizaciones, lau, robert-demo-inmobiliaria, mica-demo-inmobiliaria]
---

# Playbook — Worker WhatsApp Bot

> **Cuándo usar este playbook**: vas a construir un bot WhatsApp conversacional para un cliente nuevo (o migrar uno existente). El bot responde preguntas, califica leads (BANT) y agenda/deriva.

## Arquitectura estándar (no inventes otra)

```
WhatsApp provider (YCloud / Evolution / Meta Graph)
        ↓ webhook
FastAPI worker (`workers/clientes/[agencia]/[cliente]/worker.py`)
        ↓
  ├─ Message buffer (Redis, debounce 8s) — workers/shared/message_buffer.py
  ├─ Sesión en Postgres / Airtable
  ├─ LLM (OpenAI/Gemini) con prompt BANT
  ├─ Fuente de datos (Airtable / Postgres CRM)
  └─ Respuesta (Message splitter + typing indicator)
```

## Stack por agencia (NO mezclar)

| Agencia | Provider WhatsApp | BD sesión | LLM | Deploy |
|---------|-------------------|-----------|-----|--------|
| **Arnaldo** | YCloud | Airtable cliente | Gemini (Arnaldo) | Coolify Hostinger |
| **Mica** | Evolution API | Airtable `appA8QxIhBYYAHw0F` | OpenAI Arnaldo | Easypanel |
| **Robert** | Meta Graph API | PostgreSQL cliente | OpenAI propio Robert | Coolify Hetzner |

Ver `wiki/conceptos/matriz-infraestructura.md` para detalles completos.

---

## Pasos exactos — crear worker nuevo (total ~45 min si clonás demo)

### Precondiciones

- [ ] Cliente identificado y agencia asignada (`/router-de-proyectos`)
- [ ] Credenciales WhatsApp del cliente obtenidas (ver `wiki/conceptos/ycloud.md` / `evolution-api.md` / `meta-graph-api.md`)
- [ ] Fuente de datos del cliente preparada (Airtable creado o DB Postgres creada — ver playbooks #4 y #5)
- [ ] Decidido vertical: inmobiliaria / gastronomía / turismo / otro

### Paso 1 — Copiar worker demo correcto (2 min)

**NUNCA escribir worker desde cero.** Siempre clonar el demo más cercano.

| Vertical | Worker demo a clonar |
|----------|----------------------|
| Inmobiliaria | `workers/demos/inmobiliaria/worker.py` |
| Gastronomía | `workers/demos/gastronomia/worker.py` |
| Turismo / otro | Clonar `inmobiliaria` (más maduro) y adaptar |

```bash
# Ejemplo: bot turismo para Cesar Posada (agencia Arnaldo)
cp workers/demos/inmobiliaria/worker.py \
   workers/clientes/arnaldo/cesar-posada/worker.py
```

### Paso 2 — Adaptar constantes del worker (5 min)

En el archivo nuevo, editar la sección de constantes arriba:

```python
# Identificación
CLIENTE_ID = "cesar-posada"          # slug
TENANT_SLUG = "cesar-posada"         # para message_buffer y routing
VERTICAL = "turismo"                 # inmobiliaria/gastronomia/turismo

# Provider (según agencia — NO mezclar)
PROVIDER = "ycloud"                  # ycloud/evolution/meta
NUMERO_BOT = "5493764999999"         # número del cliente

# Datos del cliente
AIRTABLE_BASE = "appXXXXXXXXXXXXXX"  # o None si usa Postgres
AIRTABLE_TABLE_LEADS = "tblXXX..."
POSTGRES_DB = None                   # o "cliente_crm" si usa Postgres

# LLM
LLM_PROVIDER = "gemini"              # gemini/openai
LLM_MODEL = "gemini-2.0-flash"       # o "gpt-4o-mini"
```

### Paso 3 — Registrar ruta en `main.py` (2 min)

En `backends/system-ia-agentes/main.py`, agregar:

```python
from workers.clientes.arnaldo.cesar_posada import worker as cesar_posada_worker

app.include_router(cesar_posada_worker.router, prefix="/clientes/arnaldo/cesar-posada")
```

Rutas que quedan expuestas:
- `POST /clientes/arnaldo/cesar-posada/whatsapp` — webhook principal
- `GET /clientes/arnaldo/cesar-posada/health` — healthcheck

### Paso 4 — Redis para buffer (1 min)

El buffer debounce usa Redis (ver `wiki/conceptos/message-buffer-debounce.md`). Verificar que env vars estén en Coolify:

```
REDIS_URL=redis://redis-workers:6379/0
```

Si el cliente es el primero de su VPS: crear service Redis en Coolify/Easypanel. **NO marcar "Is Preview" al crear env vars** (bug documentado en `feedback_buffer_debounce_workers.md`).

### Paso 5 — Configurar webhook del provider (5 min)

**YCloud**: en `app.ycloud.com` → WhatsApp → Webhooks → URL: `https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/cesar-posada/whatsapp`

**Evolution API**: en n8n / panel Evolution → webhook URL idem al endpoint del worker

**Meta Graph**: en `developers.facebook.com/apps/<app_id>/webhooks/` → Callback URL + Verify Token

### Paso 6 — Prompt BANT adaptado al vertical (10 min)

El prompt vive dentro del worker en constante `SYSTEM_PROMPT`. Adaptar:

- **Presentación**: 1 mensaje inicial corto, dice quién es y pide qué busca
- **BANT natural**: preguntar presupuesto, timing, autoridad, necesidad **sin que suene a formulario**
- **Presentación 1-a-1**: UN producto por turno, NUNCA listas numeradas (trae curiosos, no compradores)
- **Brevedad por turno**: primer turno puede ser más largo (incluye horarios/presentación), resto de turnos ≤2 líneas
- **CTA**: cada cierto N turnos de calentamiento, derivar a humano o agendar

Referencias de prompts que funcionan:
- Mica demo inmobiliaria (ver `workers/clientes/system_ia/mica-demo-inmo/worker.py`)
- Robert demo inmobiliaria (ver `workers/demos/inmobiliaria/worker.py`)

### Paso 7 — Deploy Coolify (10 min)

Usar skill `/deploy` o el script `02_OPERACION_COMPARTIDA/execution/deploy_service.py`.

- Arnaldo → Coolify Hostinger, URL `agentes.arnaldoayalaestratega.cloud`
- Robert → Coolify Hetzner, URL `agentes.lovbot.ai`
- Mica → Easypanel, URL compartida backend Arnaldo con prefijo `/mica/*`

**Force rebuild si Coolify no detecta cambios** (ver `feedback_REGLA_coolify_cache_force.md`): `force=true` en API o UI.

### Paso 8 — Test E2E con WhatsApp real (5 min)

Desde tu celular, mandar al número del bot:
- "hola" → debe saludar con horarios (primer turno es excepción a la brevedad)
- preguntas normales del vertical → respuestas ≤2 líneas
- mensajes fragmentados en rápida sucesión → debe procesar TODO junto (gracias al buffer 8s)
- silencio de 1 min → no spam, esperar próximo mensaje

Ver logs en Coolify:
```
[WORKER-{cliente}] msg_in from=+549... buffer_size=N
[WORKER-{cliente}] llm_out tokens_in=X tokens_out=Y lat_ms=Z
```

### Paso 9 — Resetear sesión antes de tests (importante para Robert)

Si estás probando Robert/Postgres, **antes de cada test serio**:

```sql
DELETE FROM sesiones WHERE numero_whatsapp = 'TU_NUMERO';
```

Ver `feedback_reset_sesion_robert.md`.

---

## Gotchas conocidos

### Gotcha #1 — Python 3.11 y f-strings triples anidados

**Síntoma**: container Coolify crashea al deploy con SyntaxError.

**Causa**: el patrón `f"""...{f"""..."""}..."""` rompe Python 3.11 (aunque funcione en 3.12+). Hetzner/Hostinger corren 3.11.

**Solución**: siempre extraer la parte dinámica a variable intermedia.

MAL:
```python
prompt = f"""Hola {f"""buen día""" if horario else ""}."""
```

BIEN:
```python
saludo_hora = "buen día" if horario else ""
prompt = f"""Hola {saludo_hora}."""
```

Ver `feedback_REGLA_python311_fstring_triples.md`.

### Gotcha #2 — `re.sub(r'\D', ...)` dentro de f-string

Mismo problema: backslash en f-string rompe Python 3.11 al deploy.

MAL:
```python
texto = f"numero: {re.sub(r'\D', '', numero)}"
```

BIEN:
```python
numero_limpio = re.sub(r'\D', '', numero)
texto = f"numero: {numero_limpio}"
```

### Gotcha #3 — Prompt BANT con reglas contradictorias

**Síntoma**: agregás "incluir horarios en el saludo" pero ya había "mensajes cortos siempre" — el LLM descarta tu nueva regla.

**Solución**: excepciones explícitas por turno ("solo primer turno incluye horarios, resto ≤2 líneas").

Ver `feedback_REGLA_prompt_bant_conflictos.md`.

### Gotcha #4 — Buffer debounce 8s

**Síntoma**: usuario manda 3 mensajes seguidos "hola", "quiero", "info casa" — bot responde 3 veces a cada uno, inconsistente.

**Solución**: usar siempre `workers/shared/message_buffer.py` con Redis. Acumula 8 segundos antes de procesar.

Ver `wiki/conceptos/message-buffer-debounce.md`.

### Gotcha #5 — Tenant slugs de demos

- `mica-demo` = worker demo de Mica
- `robert-demo` = worker demo de Robert
- `demo` = tenant en Postgres `lovbot_crm` de Robert

**NO confundir** con slugs de clientes reales.

### Gotcha #6 — Nombres largos / multibyte en LLM

**Síntoma**: el bot saluda "Hola 🎉👋" y genera respuestas raras.

**Solución**: sanitizar nombre del usuario antes de inyectarlo al prompt. Usar `_sanitizar_nombre()` del demo inmobiliaria.

### Gotcha #7 — Marcar como leído en Meta Graph

**Síntoma**: tilde azul no aparece en WhatsApp del usuario (Robert).

**Solución**: llamar `mark_as_read` en el webhook INMEDIATAMENTE, antes de procesar. Ver commit `42a2dbf`.

---

## Checklist final antes de entregar

- [ ] Worker clonado de demo correcto (no escrito desde cero)
- [ ] Constantes actualizadas (CLIENTE_ID, provider, BD, LLM)
- [ ] Ruta registrada en `main.py`
- [ ] Redis configurado en el VPS correcto
- [ ] Webhook del provider apunta al endpoint correcto
- [ ] Prompt BANT adaptado al vertical, excepciones por turno explícitas
- [ ] Deploy Coolify con force=true si no detectó cambio
- [ ] Test E2E con celular real: saludo, pregunta simple, mensajes fragmentados
- [ ] Logs en Coolify muestran flow correcto
- [ ] Sesión limpia antes de demo con cliente
- [ ] Worker **NO modifica** `workers/clientes/*` directo — siempre primero demo

---

## Archivos que tocás al seguir este playbook

```
workers/clientes/{agencia}/{cliente}/worker.py         ← archivo nuevo
workers/shared/message_buffer.py                       ← reutilizar, NO modificar
backends/system-ia-agentes/main.py                     ← agregar router
.env o Coolify env vars                                ← provider creds
```

---

## Cuándo escalar a versión v2 de este playbook

Cuando detectemos:
- Un provider nuevo no documentado acá (ej: alguien pide WhatsApp Business API directo)
- Una BD de sesión nueva (ej: alguien pide Redis para sesión además de buffer)
- Un patrón LLM nuevo (ej: tool calling en vez de prompt libre)

---

## Histórico de descubrimientos

- **2026-04-23** — Buffer debounce 8s agregado al patrón. Antes los workers procesaban mensaje por mensaje.
- **2026-04-23** — Marcar como leído inmediato en Meta Graph para Robert demo (commit `42a2dbf`).
- **2026-04-24** — Excepción primer turno incluye horarios, resto mantiene brevedad (sesión Mica + Robert).
- **2026-04-24** — Saludo Robert inmobiliaria menciona horarios (replica patrón Mica, commit `91b9924`).
- **2026-04-24** — Regla brevedad NO aplica al primer turno (commit `5a99bb1`).

---

## Referencias cruzadas

- `wiki/conceptos/message-buffer-debounce.md` — detalles del buffer Redis
- `wiki/conceptos/message-splitter-pattern.md` — partir respuesta larga en múltiples mensajes
- `wiki/conceptos/typing-indicator-pattern.md` — indicador "escribiendo..." durante LLM
- `wiki/conceptos/image-describer.md` — manejo de imágenes entrantes
- `wiki/conceptos/ycloud.md` / `evolution-api.md` / `meta-graph-api.md` — specs por provider
- `.claude/skills/whatsapp-conversational-bot/` — skill con templates de código
