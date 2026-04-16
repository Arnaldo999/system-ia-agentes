---
name: whatsapp-conversational-bot
description: Diseña, implementa y prueba bots de WhatsApp conversacionales profesionales con metodología BANT, presentación de productos una-a-la-vez sin menús numéricos (anti-curiosos), parsing tolerante de LLM, y deploy en Coolify. Soporta múltiples proveedores WhatsApp (Meta Graph API, Evolution API, YCloud) con parsers específicos y capa de abstracción común. Usar cuando el usuario menciona "bot WhatsApp", "Meta Graph API", "Evolution API", "YCloud", "BANT", "calificar leads", "Lovbot", "agente IA inmobiliario/gastronómico", "anti-friction bot", "filtrar curiosos", "Click-to-WhatsApp Ads", "Lead Ads", "cambiar proveedor WhatsApp", "migrar de Evolution a Meta", o quiere mejorar/debuggear conversaciones de bot. También aplica cuando se diseñan flujos conversacionales que deben filtrar leads no-comprometidos, o cuando el bot está usando menús numéricos (`*1*`, `*2*`, `*0*`) y se quiere migrar a presentación natural una-prop-a-la-vez. SIEMPRE usar esta skill ANTES de modificar workers de bots WhatsApp en `workers/clientes/*/` o crear bots nuevos.
---

# WhatsApp Conversational Bot — Multi-Provider

Skill maestra para diseñar, implementar y probar bots WhatsApp profesionales en el ecosistema **Arnaldo / Lovbot / System IA**. Soporta los 3 proveedores usados en producción: **Meta Graph API**, **Evolution API**, y **YCloud**, con una capa de abstracción común.

## Cuándo usar esta skill

- Crear bot WhatsApp nuevo para un cliente (Robert/Mica/Arnaldo/Maicol/etc.)
- Elegir proveedor WhatsApp adecuado para un cliente nuevo
- Migrar un cliente de Evolution a Meta (o viceversa)
- Refactorizar bot existente para metodología BANT
- Migrar de menús numéricos `*1* *2* *0*` a presentación conversacional
- Implementar filtrado anti-curiosos
- Parsing de webhooks de cualquier proveedor
- Deploy + test cycle en Coolify Hetzner / Hostinger
- Integrar con Chatwoot (bridge común para los 3 proveedores)

## 🔒 MATRIZ INFRAESTRUCTURA POR CLIENTE (LEER PRIMERO — IRROMPIBLE)

| Recurso | **Robert (Lovbot)** | **Mica (System IA)** | **Arnaldo / Maicol** |
|---------|---------------------|----------------------|----------------------|
| VPS / Orquestador | Hetzner / Coolify `coolify.lovbot.ai` | Easypanel propio | Hostinger / Coolify Arnaldo |
| Backend FastAPI | `agentes.lovbot.ai` | `agentes.arnaldoayalaestratega.cloud` | `agentes.arnaldoayalaestratega.cloud` |
| **DB del bot** | 🔒 **PostgreSQL `robert_crm`** (de Robert) | 🔒 **Airtable `appA8QxIhBYYAHw0F`** (de Mica) | 🔒 **Airtable** (de Arnaldo) |
| Cal.com | de Arnaldo (compartido) | de Arnaldo (compartido) | de Arnaldo |
| Supabase | de Arnaldo (compartido) | de Arnaldo (compartido) | — |
| **OpenAI** | 🔒 **Cuenta Robert** (`LOVBOT_OPENAI_API_KEY`) | de Arnaldo | de Arnaldo |
| Gemini | de Arnaldo (compartido) | de Arnaldo | de Arnaldo |
| **WhatsApp provider** | Meta Graph API | Evolution API | YCloud |
| Chatwoot | `chatwoot.lovbot.ai` | `chatwoot.arnaldoayalaestratega.cloud` | idem |
| n8n | `n8n.lovbot.ai` | `n8n.arnaldoayalaestratega.cloud` | idem |

**Detalle completo en `memory/feedback_REGLA_infraestructura_clientes.md`.**

## Reglas irrompibles (de memoria de producción)

1. **NUNCA modificar `workers/clientes/*/` directo** — primero sandbox en `workers/demos/[vertical]/worker.py`, probar, después copiar al cliente
2. **Confirmar destino**: "¿esto va a Robert / Mica / Arnaldo?" antes de cualquier curl/MCP/código
3. **Modelo LLM actual**: `gpt-4o-mini` (OpenAI) principal, `gemini-2.0-flash` → `gemini-2.5-flash` fallback. (gpt-5-mini era muy lento → timeout)
4. **Robert NO usa Airtable** — usa PostgreSQL `robert_crm` (NO `lovbot_crm` — bug histórico). Solo Mica y Arnaldo usan Airtable
5. **Mica Airtable**: base correcta `appA8QxIhBYYAHw0F` (NO la del .env desactualizado)
6. **Meta webhook**: necesita GET y POST en la misma URL (sino falla el handshake)
7. **Lead recurrente Robert**: query a PostgreSQL `leads` por sufijo (últimos 10 dígitos, tolerante a `+`). Mica: query a Airtable `filterByFormula`

## Estructura de la skill

```
whatsapp-conversational-bot/
├── SKILL.md                                       (este archivo)
├── references/
│   ├── providers/
│   │   ├── _provider-selection.md                 ← cómo elegir proveedor
│   │   ├── meta-graph-api.md                      ← Meta (Robert, prod)
│   │   ├── evolution-api.md                       ← Evolution (Mica, demos)
│   │   ├── ycloud-api.md                          ← YCloud (Maicol, Arnaldo)
│   │   └── chatwoot-bridge.md                     ← integración Chatwoot
│   ├── bant-system-prompt.md                      ← prompts BANT
│   ├── conversational-prop-display.md             ← presentación 1-a-la-vez
│   ├── deterministic-keywords.md                  ← keywords pre-LLM
│   ├── llm-response-parser.md                     ← parser tolerante
│   └── deploy-test-loop.md                        ← deploy + test cycle
└── scripts/
    └── test-bot.sh                                ← script de testing
```

## Arquitectura del bot — Vista general

```
┌──────────────────────────────────────────────────────────────────┐
│  WEBHOOK (proveedor-específico)                                   │
│  - Meta: POST /clientes/{x}/{y}/whatsapp                          │
│  - Evolution: POST /<ruta>/whatsapp (event MESSAGES_UPSERT)       │
│  - YCloud: POST /<ruta>/whatsapp (event whatsapp.message.received)│
└─────────────────────────┬────────────────────────────────────────┘
                          ▼
       ┌────────────────────────────────────┐
       │  PROVIDER PARSER                    │  → references/providers/{name}.md
       │  Normaliza a formato interno:       │
       │  {telefono, texto, referral,        │
       │   nombre_perfil, msg_id, tipo}      │
       └──────────────┬─────────────────────┘
                      ▼
       ┌────────────────────────────────────┐
       │  Deduplicación (set + lock)         │
       │  Verificar bot_pausado()            │
       │  Cargar sesión (RAM + DB fallback)  │
       └──────────────┬─────────────────────┘
                      ▼
       ┌────────────────────────────────────┐
       │  Step handlers PRE-LLM              │  ← deterministas, antes del LLM:
       │  - agendar_slots (selección horarios)│     references/deterministic-keywords.md
       │  - confirmar_cita                   │     references/conversational-prop-display.md
       │  - explorando ◄ keywords siguiente/ │
       │                 interés             │
       │  - anti_friction "que opciones"    │
       └──────────────┬─────────────────────┘
                      ▼
       ┌────────────────────────────────────┐
       │  LLM call (gpt-5-mini)              │  → references/bant-system-prompt.md
       │  System prompt BANT                 │
       └──────────────┬─────────────────────┘
                      ▼
       ┌────────────────────────────────────┐
       │  Parser tolerante de respuesta LLM  │  → references/llm-response-parser.md
       │  - separa mensaje vs ACCION         │
       │  - strip bullets/headers/emojis     │
       │  - extrae EMAIL/SCORE/etc           │
       └──────────────┬─────────────────────┘
                      ▼
       ┌────────────────────────────────────┐
       │  Ejecutar ACCION                    │
       │  - mostrar_props                    │
       │  - ir_asesor ──→ Chatwoot bridge   │  → references/providers/chatwoot-bridge.md
       │  - cerrar_curioso                   │
       │  - calificar                        │
       └────────────────────────────────────┘
                      ▼
       ┌────────────────────────────────────┐
       │  Send via PROVIDER específico       │  → references/providers/{name}.md
       └────────────────────────────────────┘
```

## Flujos de trabajo

### A) Crear bot WhatsApp nuevo

1. **Elegir proveedor** según cliente → [`providers/_provider-selection.md`](references/providers/_provider-selection.md)
2. **Decidir cliente** (Robert/Mica/Arnaldo/nuevo) → confirmar con usuario
3. **Copiar template**: `cp workers/demos/[vertical]/worker.py workers/clientes/{tenant}/{cliente}/worker.py`
4. **Adaptar parser** según proveedor → [`providers/{meta|evolution|ycloud}.md`](references/providers/)
5. **Adaptar prompt BANT** según subnicho → [`bant-system-prompt.md`](references/bant-system-prompt.md)
6. **Agregar admin endpoints** (reset-sesion, ver-sesion, simular-lead) → [`deploy-test-loop.md`](references/deploy-test-loop.md)
7. **Configurar webhook** del proveedor → [`providers/{name}.md`](references/providers/)
8. **Test loop** → [`deploy-test-loop.md`](references/deploy-test-loop.md) o `scripts/test-bot.sh`

### B) Migrar bot con menús numéricos a conversacional

1. Leer worker actual → identificar funciones tipo `_lista_titulos()` / `_enviar_ficha()`
2. Reemplazar con `_presentar_prop_breve()` → [`conversational-prop-display.md`](references/conversational-prop-display.md)
3. Cambiar step `"lista"` → `"explorando"` con keywords pre-LLM
4. Quitar shortcuts `*0*` y `*#*` de mensajes (mantener `#` como comando válido)
5. Test cycle completo

### C) Cambiar proveedor de un cliente (ej: Evolution → Meta)

1. Revisar tabla comparativa → [`providers/_provider-selection.md`](references/providers/_provider-selection.md)
2. Reemplazar parser del webhook por el del nuevo proveedor
3. Reemplazar funciones de envío `_enviar_texto()`, `_enviar_imagen()`
4. Mantener `_procesar()` intacto (es agnóstico al proveedor)
5. Configurar credenciales del nuevo proveedor en Coolify env vars
6. Test loop

### D) Debug bot que repite preguntas o ignora cliente

1. Verificar deploy correcto: ver commit hash en Coolify deployment logs
2. Usar endpoint `/admin/ver-sesion/{tel}` para inspeccionar estado RAM
3. Curl reset + simular + check sesión → [`deploy-test-loop.md`](references/deploy-test-loop.md)
4. Si LLM ignora reglas: agregar **detección determinista en Python** ANTES del LLM (no confiar en prompts) → [`deterministic-keywords.md`](references/deterministic-keywords.md)

### E) Integrar con Chatwoot para asesor humano

1. Configurar inbox y API token del Chatwoot del cliente
2. Implementar bridge → [`providers/chatwoot-bridge.md`](references/providers/chatwoot-bridge.md)
3. Configurar webhook de Chatwoot → FastAPI para pausar bot cuando asesor toma
4. Testear handoff humano ↔ bot

## Sub-skills (references)

### Proveedores WhatsApp

| Archivo | Cuándo usar |
|---------|-------------|
| [`providers/_provider-selection.md`](references/providers/_provider-selection.md) | **Siempre leer primero** — tabla comparativa y cómo elegir entre Meta/Evolution/YCloud |
| [`providers/meta-graph-api.md`](references/providers/meta-graph-api.md) | Bot oficial WhatsApp Business API — Click-to-WhatsApp Ads, Lead Ads forms, botones interactivos (Robert) |
| [`providers/evolution-api.md`](references/providers/evolution-api.md) | Wrapper community sobre WhatsApp Web — self-hosted gratis, sin Ads (Mica, demos) |
| [`providers/ycloud-api.md`](references/providers/ycloud-api.md) | BSP comercial — oficial sin verificación Meta directa, soporta Ads (Maicol, Arnaldo) |
| [`providers/chatwoot-bridge.md`](references/providers/chatwoot-bridge.md) | Integrar con Chatwoot para asesor humano — funciona con los 3 proveedores |

### Lógica común (agnóstica al proveedor)

| Archivo | Propósito |
|---------|-----------|
| [`bant-system-prompt.md`](references/bant-system-prompt.md) | System prompts BANT (Budget/Authority/Need/Timeline) — Caso A (lead Ads) vs Caso B (genérico) |
| [`conversational-prop-display.md`](references/conversational-prop-display.md) | Presentación una-prop-a-la-vez sin menú numérico (anti-curiosos) |
| [`deterministic-keywords.md`](references/deterministic-keywords.md) | Detección por keywords ANTES del LLM (más confiable que prompts) |
| [`llm-response-parser.md`](references/llm-response-parser.md) | Parser tolerante de respuestas LLM (bullets, markdown, extracción de datos) |
| [`deploy-test-loop.md`](references/deploy-test-loop.md) | Ciclo deploy Coolify + curl test + admin endpoints |

## Script de testing

```bash
# Test bot completo en 30 segundos
cd .claude/skills/whatsapp-conversational-bot/scripts/
./test-bot.sh robert 5493765384843 caso_a   # Robert + lead desde anuncio
./test-bot.sh mica 5493765005465 caso_b     # Mica + lead genérico
./test-bot.sh maicol 5493764815689 caso_a   # Maicol + lead Meta Ads
```

El script:
1. Resetea la sesión
2. Simula lead entrante (Caso A = con referral, Caso B = mensaje directo)
3. Espera respuesta del bot (polling del endpoint `/admin/ver-sesion`)
4. Muestra estado de sesión + último mensaje del bot

## Anti-patrones conocidos (del log de producción)

❌ **Confiar en que el LLM siga reglas complejas**
   → Si una regla es crítica, hacer detección determinista en Python ANTES del LLM

❌ **Acciones LLM declaradas pero no implementadas**
   → Si el prompt dice `ACCION: mostrar_props`, debe haber `if accion == "mostrar_props"` en código

❌ **Step handlers DESPUÉS del LLM call**
   → Si LLM falla, los handlers de step nunca se ejecutan
   → Mover handlers deterministas (explorando, agendar_slots, etc.) ANTES del LLM

❌ **Menús numéricos `*1* *2* *0*`**
   → Facilitan el scroll pasivo del curioso
   → Una propiedad a la vez + texto libre filtra el commitment real

❌ **Mostrar todas las propiedades de una vez**
   → Tipo catálogo/website, no conversación
   → Una a la vez con anchor question al final

❌ **Modificar `clientes/` sin pasar por `demos/`**
   → Producción rompe → conversaciones reales afectadas
   → Sandbox primero, validar, después copiar

❌ **Olvidarse del GET handshake en Meta**
   → Meta necesita GET con `hub.verify_token` para configurar webhook
   → Si solo hay POST, nunca se podrá configurar

❌ **Evento `MESSAGES_UPSERT` vs `messages.upsert`**
   → Evolution manda en uppercase. Comparar case-insensitive: `event.lower().replace("_", ".")`

❌ **Usar YCloud API v1**
   → Deprecada. Siempre v2: `https://api.ycloud.com/v2/whatsapp/messages`

## Memoria operativa relacionada

- `memory/project_crm_ia_chat.md` — CRM IA chat + workflows n8n
- `memory/project_robert_alianza.md` — Lovbot Robert estado actual
- `memory/feedback_workers_separados.md` — workers separados por proyecto
- `memory/feedback_REGLA_demo_primero.md` — demo primero, nunca prod directo
- `memory/bugs_integraciones.md` — bugs de proveedores (Meta, Evolution, YCloud)
- `memory/bugs_calcom_evolution.md` — bugs específicos Evolution + Cal.com

## Clientes actuales mapeados a proveedores

| Cliente | Proveedor | Worker | Estado |
|---------|-----------|--------|--------|
| **Maicol** (Back Urbanizaciones) | YCloud | `workers/clientes/arnaldo/maicol/worker.py` | LIVE con datos reales |
| **Robert** (Lovbot inmobiliaria) | Meta Graph | `workers/clientes/lovbot/robert_inmobiliaria/worker.py` | LIVE |
| **Mica** (System IA demo) | Evolution | `workers/demos/inmobiliaria/worker.py` (compartido) | LIVE demo |
| **Lau** (System IA) | Evolution | `workers/clientes/system-ia/lau/worker.py` | Deploy pendiente |
| **Arnaldo prueba** | YCloud | `workers/clientes/arnaldo/prueba/worker.py` | LIVE |
