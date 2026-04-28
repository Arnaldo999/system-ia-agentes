---
name: Playbook — Worker Voz con ElevenLabs (vertical inmobiliaria/gastronomía/turismo)
description: Patrón estándar para construir un agente de voz que conteste llamadas telefónicas (Twilio + ElevenLabs Conversational AI) y consuma endpoints-tool del backend FastAPI. Reusa la capa de datos del bot WhatsApp existente (BANT + catálogo + Cal.com).
type: playbook
proyecto: compartido
tags: [voz, elevenlabs, twilio, bot, bant, worker, fastapi, playbook]
version: 1
ultima_actualizacion: 2026-04-27
casos_aplicados: [robert-demo-inmobiliaria-voz]
---

# Playbook — Worker Voz con ElevenLabs

> **Cuándo usar este playbook**: vas a construir un agente de voz para
> que conteste llamadas telefónicas y resuelva consultas + agendamiento.
> El cerebro conversacional vive en ElevenLabs; nosotros exponemos
> endpoints-tool en FastAPI que el agente consume.

## Arquitectura estándar (no inventes otra)

```
Cliente → Twilio (PSTN) → ElevenLabs Agent (Gemini 2.5 Flash + voz ES)
                                      ↓
                          POST agentes.lovbot.ai/.../voz/*
                                      ↓
                    FastAPI worker (workers/demos/inmobiliaria_voz/worker.py)
                                      ↓
                    workers.shared.{calcom_client, catalog, lead_matcher, bant}
                                      ↓
              Postgres lovbot_crm_modelo + Cal.com Arnaldo
```

## Stack por agencia (NO mezclar)

| Agencia | Voz LLM | BD | Cal.com | Provider voz | Deploy backend |
|---------|---------|-----|---------|--------------|----------------|
| **Robert** | ElevenLabs (Gemini 2.5 Flash) | Postgres `*_crm` cliente | Arnaldo compartido | Twilio | Coolify Hetzner |
| **Arnaldo** | ElevenLabs (Gemini 2.5 Flash) | Airtable cliente | Arnaldo compartido | Twilio | Coolify Hostinger |
| **Mica** | ElevenLabs (Gemini 2.5 Flash) | Airtable `appA8QxIhBYYAHw0F` | Arnaldo compartido | Twilio | Easypanel |

> Provider voz por defecto = **Twilio**. Comprar SIM físico SOLO si el
> cliente exige número con prefijo que Twilio no ofrece.

## Pasos exactos — crear agente voz nuevo (~6 horas total)

### Precondiciones

- [ ] Bot WhatsApp del cliente ya existe (mismo vertical)
- [ ] Catálogo de propiedades en BD del cliente
- [ ] Cal.com del cliente configurado (env vars `INMO_DEMO_CAL_*`)
- [ ] Cuenta ElevenLabs (en dev: la de Arnaldo "ElevenCreative")
- [ ] Voice ID elegida (escuchar samples en https://elevenlabs.io/app/voice-library)

### Paso 1 — Crear módulos shared (1 vez por ecosistema)

Si no existen aún, crear:

- `workers/shared/calcom_client.py` — wrapper Cal.com v2
- `workers/shared/catalog.py` — wrapper búsqueda BD
- `workers/shared/lead_matcher.py` — match cross-channel
- `workers/shared/bant.py` — extracción señales BANT

**Estos viven una sola vez en el monorepo**. Workers de voz de
clientes nuevos solo importan, no duplican.

### Paso 2 — Crear worker demo voz (clonar el modelo)

```bash
cp -r workers/demos/inmobiliaria_voz workers/demos/{vertical}_voz
# o si es para cliente directamente:
cp -r workers/demos/inmobiliaria_voz workers/clientes/{agencia}/{cliente}_voz
```

Adaptar:
- `prefix=/...` del router
- Nombre empresa, asesor, ciudad (env vars `INMO_DEMO_*` o las del cliente)
- Si el vertical es distinto: ajustar prompts + tools

### Paso 3 — Registrar router en main.py

```python
from workers.demos.{vertical}_voz.worker import router as {vertical}_voz_router
app.include_router({vertical}_voz_router)
```

### Paso 4 — Deploy backend

```bash
git push origin master:main
# Trigger redeploy Coolify (Hetzner para Robert / Hostinger para Arnaldo / Easypanel para Mica)
curl https://{backend}/{prefix}/healthz
```

### Paso 5 — Configurar agente en ElevenLabs

1. New Agent → Business Agent → Real Estate (o vertical correspondiente) → Scheduling
2. Idioma: Español + auto-detect English
3. **System prompt en INGLÉS** (mejora tool-calling) → ver template
   en `02_OPERACION_COMPARTIDA/handoff/elevenlabs-{cliente}/system-prompt.md`
4. LLM: **Gemini 2.5 Flash** (NO usar GPT/Claude — peor para deletreo email)
5. Temperature: 0.5
6. Voice: la voice_id del cliente
7. Subir 2 docs de Knowledge Base (FAQ + servicios)
8. Crear las 5 custom tools (JSON template en `tools.json`)
9. Configuraciones avanzadas:
   - Turn timeout: 7s
   - Silence call timeout: 60s
   - Max conversation: 600s

### Paso 6 — Test desde "Test AI agent" (sin Twilio aún)

Validar 5 flujos mínimo. Ver gotchas más abajo.

### Paso 7 — Comprar Twilio + conectar (cliente paga)

Solo cuando el demo esté validado. Ver
`wiki/conceptos/twilio-numeros-telefonicos.md` para detalles AR/MX.

### Paso 8 — Promover demo → cliente (REGLA Demo→Producción)

```bash
cp -r workers/demos/{vertical}_voz workers/clientes/{agencia}/{cliente}_voz
# Cambiar prefix del router
# Actualizar URLs de tools en ElevenLabs (cambiar /demos/ por /clientes/...)
```

## Tabla de gotchas (descubiertos en producción)

| # | Gotcha | Causa | Fix |
|---|--------|-------|-----|
| 1 | LLM cita precios falsos | System prompt no marca regla "NEVER quote without tool" | Reforzar regla y agregarla al docstring de la tool `buscar_propiedad` |
| 2 | Email mal capturado | Modelo distinto a Gemini 2.5 Flash | Cambiar LLM. GPT-5 / Claude son peores en deletreo letra-por-letra |
| 3 | Tool da timeout | Default 20s + queries lentas | Subir a **40s** mínimo. Considerar caching si query >2s |
| 4 | Voz se corta cuando llama tool | Falta `pre_tool_speech` | Agregar "Un momento, lo verifico" en cada tool |
| 5 | Slots vacíos | `INMO_DEMO_CAL_*` no en Coolify | Validar con `/healthz` que `calcom_configured: true` |
| 6 | Cliente conocido no es reconocido | `caller_id` formato distinto al de BD | Usar `lead_matcher.normalize_phone` (últimos 10 dígitos) |
| 7 | Lead duplicado WhatsApp + voz | Sin matching cross-channel | SIEMPRE llamar `identificar_lead` PRIMERO |
| 8 | Twilio AR rechaza KYC | Argentina pide más docs que USA | Justificar uso + DNI + comprobante domicilio. 3-10 días hábiles |
| 9 | Conversación se traba en bucles | LLM no sabe "ceder" a humano | Regla explícita en system prompt: si frustración, tomar callback |
| 10 | El agente lee el JSON de la tool en voz | Falta campo `message` en respuesta del backend | Endpoints SIEMPRE retornan `{success, data, message}` donde `message` es lo que el bot dirá |
| 11 | Worker no encuentra db_postgres | Import path equivocado | `from workers.demos.inmobiliaria import db_postgres as db` (la misma capa que WhatsApp demo) |

## Decisiones de diseño históricas

### ¿Por qué worker independiente del WhatsApp y no extenderlo?

- Latencia: voz tolera <500ms; WhatsApp tolera 2-8s con debounce
- Failure isolation: si voz se rompe, WhatsApp sigue funcionando
- Deploy independiente

### ¿Por qué endpoints-tool y no que el agente hable directo con la BD?

ElevenLabs no tiene driver de Postgres. Y aunque lo tuviera, queremos
que el SQL viva en nuestro código (versionado, testeado).

### ¿Por qué match por últimos 10 dígitos del teléfono?

Twilio entrega `+5493764xxxxxx`. Meta WhatsApp entrega `5493764xxxxxx`.
Algunos clientes tienen guardado solo `3764xxxxxx` (sin código país).
Los últimos 10 dígitos son siempre el celular real.

### ¿Por qué system prompt en inglés?

Best practice ElevenLabs validada en su documentación. Mejora la
precisión del tool-calling. La salida al usuario sigue en español por
la voz seleccionada y la KB.

## Cómo se cobra al cliente

Setup one-time: USD 500-800 (depende del cliente)
Mensual mantenimiento: USD 80-150 sobre la infra
Costos del cliente:
- ElevenLabs Creator: USD 22/mes
- Twilio AR: USD 1-3/mes + USD 0.04/min entrante
- Coolify / Postgres: incluido (sin costo extra al ya pagado por WhatsApp)

Precio mínimo viable: USD 25/mes para el cliente final.

## Histórico de descubrimientos

- **2026-04-27** (caso 1: Robert demo): patrón inicial validado.
  Gotchas 1-11 capturados durante construcción. Voice ID
  `16UXUey4OpoKrC9IiRNt`.
