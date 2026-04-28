# Worker — Demo Inmobiliaria Voz (ElevenLabs)

Endpoints-tool que ElevenLabs Conversational AI consume durante una
llamada de voz para inmobiliaria.

## Stack

- **Canal voz**: ElevenLabs Conversational AI (Gemini 2.5 Flash + voz ES)
- **BD**: Postgres `lovbot_crm_modelo` (Coolify Hetzner Robert)
- **Cal.com**: cuenta compartida Arnaldo (env `INMO_DEMO_CAL_*`)
- **Match cross-channel**: por `caller_id` (voz) ↔ `wa_id` (whatsapp)

## Endpoints

Base: `https://agentes.lovbot.ai/demos/voz/inmobiliaria`

| Método | Path | Tool ElevenLabs | Propósito |
|--------|------|-----------------|-----------|
| GET | `/healthz` | — | Smoke test (config Cal.com, etc.) |
| POST | `/identificar-lead` | `identificar_lead` | Match cross-channel por caller_id |
| POST | `/buscar-propiedad` | `buscar_propiedad` | Search catálogo Postgres |
| POST | `/disponibilidad` | `disponibilidad` | Slots Cal.com próximos N días |
| POST | `/agendar-visita` | `agendar_visita` | Book Cal.com + upsert lead |
| POST | `/cancelar-visita` | `cancelar_visita` | Cancel booking Cal.com |

## Test desde curl

```bash
# Health check
curl https://agentes.lovbot.ai/demos/voz/inmobiliaria/healthz

# Disponibilidad
curl -X POST https://agentes.lovbot.ai/demos/voz/inmobiliaria/disponibilidad \
  -H "Content-Type: application/json" \
  -d '{"dias": 7}'

# Buscar propiedad
curl -X POST https://agentes.lovbot.ai/demos/voz/inmobiliaria/buscar-propiedad \
  -H "Content-Type: application/json" \
  -d '{"tipo":"casa","operacion":"venta","zona":"Posadas Centro"}'

# Identificar lead
curl -X POST https://agentes.lovbot.ai/demos/voz/inmobiliaria/identificar-lead \
  -H "Content-Type: application/json" \
  -d '{"caller_id":"+5493764999999"}'
```

## Test desde ElevenLabs

1. Configurar agente siguiendo `02_OPERACION_COMPARTIDA/handoff/elevenlabs-robert/README-handoff.md`
2. Botón "Test AI agent" en dashboard ElevenLabs
3. Validar flujo: saludo → identificar lead → búsqueda → disponibilidad → agendar

## Promoción a cliente Robert

Cuando esté validado:

```bash
cp -r workers/demos/inmobiliaria_voz workers/clientes/lovbot/robert_voz
# Cambiar prefix a /clientes/lovbot/robert/voz en el router
# Actualizar URLs en tools de ElevenLabs
```

## Módulos shared usados

- `workers.shared.calcom_client` — wrapper Cal.com
- `workers.shared.catalog` — wrapper búsqueda Postgres
- `workers.shared.lead_matcher` — match cross-channel
- `workers.shared.bant` — extracción señales BANT (futuro)

## Dependencias del worker WhatsApp

Reusa `workers.demos.inmobiliaria.db_postgres` (la misma capa de BD que
el bot WhatsApp demo). NO duplica conexiones. Si cambia el schema de
Postgres, ambos canales se ven afectados — eso es intencional.
