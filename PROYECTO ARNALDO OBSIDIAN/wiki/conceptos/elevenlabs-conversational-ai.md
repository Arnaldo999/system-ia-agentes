---
title: "ElevenLabs Conversational AI"
tags: [voz, elevenlabs, llm, tool-calling, gemini, stack-tecnico]
source_count: 1
proyectos_aplicables: [arnaldo, robert, mica]
---

# ElevenLabs Conversational AI

## Definición

Plataforma de agentes de voz que combina:
- ASR (speech-to-text) propio de ElevenLabs
- LLM seleccionable (recomendado: Gemini 2.5 Flash)
- TTS (text-to-speech) — el producto histórico de ElevenLabs
- Custom tools (HTTP webhooks)
- Knowledge base (texto / PDFs)
- Dynamic variables (caller_id, system_time, etc.)
- Conexión con telefonía (Twilio nativo)

Es la base del [[playbooks/worker-voz-elevenlabs|playbook de bot voz]]
del ecosistema.

## Quién la usa

- Robert: demo voz inmobiliaria (cuenta dev en ElevenCreative de Arnaldo
  hasta que Robert pague la suya)
- Arnaldo: a futuro para Maicol y otros clientes
- Mica: a futuro para clientes inmobiliaria

## Modelos de LLM disponibles

| LLM | Latencia | Tool calling | Deletreo email | Recomendado |
|-----|----------|--------------|----------------|-------------|
| **Gemini 2.5 Flash** | Baja | Excelente | Excelente | ✅ Default |
| Gemini 2.0 Flash | Muy baja | Bueno | Bueno | Para alto volumen |
| GPT-4 | Alta | Bueno | Regular | ❌ Muy lento |
| GPT-5 Nano | Media | Regular | Malo | ❌ Falla en email |
| Claude Sonnet | Media | Bueno | Bueno | Backup si Gemini falla |

Recomendación firme: **Gemini 2.5 Flash** salvo razón fuerte para otra
cosa. Validado por la comunidad y por nuestros tests internos.

## Pricing (al 2026-04)

| Plan | USD/mes | Minutos incluidos | Notas |
|------|---------|-------------------|-------|
| Free | 0 | ~10 min total trial | Solo dev |
| Starter | 5 | ~50 min | Apenas alcanza |
| **Creator** | 22 | ~250 min | Mínimo viable producción |
| Pro | 99 | ~1100 min | Para alto volumen |

Para clientes nuestros: empezar con Creator. Subir si supera 200 min/mes.

## Custom tools — formato

Cada tool define:
- `name` — usado por el LLM para identificarla
- `description` — el LLM la lee para decidir cuándo invocarla
- `method` (POST recomendado)
- `url` — debe ir bajo el dominio del cliente (`agentes.lovbot.ai/...`,
  `agentes.arnaldoayalaestratega.cloud/...`, etc.)
- `headers`
- `body_parameters` cada uno con:
  - `value_type`: `dynamic` (variable de sistema), `llm_prompt` (lo
    decide el LLM en runtime), `constant` (valor fijo)
- `response_timeout_seconds` — siempre **40s** (default 20s es poco)
- `pre_tool_speech` — frase que el bot dice al invocar (ej: "Un momento")

Ver template en `02_OPERACION_COMPARTIDA/handoff/elevenlabs-robert/tools.json`.

## Dynamic variables disponibles

- `system_time_utc` — auto, hora UTC actual
- `system_timezone` — configurable (default `America/Argentina/Buenos_Aires`)
- `caller_id` — número del que llama (cuando hay Twilio conectado)
- `conversation_id` — ID único de la conversación
- + variables custom que el agente puede inyectar al iniciar la conversación

## Knowledge base — cuándo usar RAG y cuándo no

ElevenLabs decide automáticamente:
- KB <10 páginas → embebida en el prompt (más rápido y preciso)
- KB ≥10 páginas → RAG real (puede tener miss de chunks relevantes)

Para FAQ inmobiliaria 2-3 páginas alcanza. NO subir el catálogo de
propiedades — eso va por tool en vivo, no por KB.

## Limitaciones conocidas

- **WhatsApp Voice** vía ElevenLabs: en beta, no probado en AR aún
- **Outbound calls** (que el bot llame): requiere config extra en
  Twilio + permisos
- **Multi-idioma simultáneo**: el agente puede detectar idioma pero la
  voz es una sola — si hay clientes EN+ES seguidos, considerar 2
  agentes
- **Cobranza por minuto**: si la conversación se cuelga abierta,
  consume crédito. Por eso `silence_call_timeout: 60s`

## Workflow de export/import

ElevenLabs permite exportar la config del agente como JSON (en el panel
del agente → "..." → Export). Para handoff:

1. Construir agente en cuenta dev (Arnaldo "ElevenCreative")
2. Validar con "Test AI agent"
3. Export JSON
4. Cliente paga y crea su cuenta
5. Import JSON en cuenta cliente (manual o vía API si está habilitada)
6. Actualizar API keys en Coolify del cliente

## Relaciones

- Stack que lo usa → [[playbooks/worker-voz-elevenlabs]]
- Provider de teléfono asociado → [[twilio-numeros-telefonicos]]
- LLM recomendado → Gemini 2.5 Flash (compartido entre canales)
- Cuenta dev histórica → ElevenCreative (workspace personal Arnaldo)

## Fuentes que lo mencionan

- _Pendiente ingestar_: video de Kevin (tutorial original)
- `02_OPERACION_COMPARTIDA/handoff/elevenlabs-robert/*` (handoff doc completo)
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/demos/inmobiliaria_voz/` (primer worker voz)
