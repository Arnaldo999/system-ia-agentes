---
title: "Matriz de Infraestructura por Proyecto"
tags: [matriz-infraestructura, stack-tecnico, regla-irrompible, global]
source_count: 0
proyectos_aplicables: [arnaldo, robert, mica]
---

# Matriz de Infraestructura por Proyecto

## Definición

Tabla **definitiva y única** de qué tecnología usa cada agencia del ecosistema. Es la fuente de verdad cuando hay duda sobre si un proyecto usa X o Y. **Leer ANTES de tocar código de cualquier bot, CRM o integración**.

## Paso 0 obligatorio — atribución

Antes de leer la tabla, aplicar [[regla-de-atribucion]]: confirmar a cuál de las 3 agencias corresponde el trabajo.

- [[agencia-arnaldo-ayala]] (mía propia, dueño Arnaldo)
- [[system-ia]] (Mica, Arnaldo socio)
- [[lovbot-ai]] (Robert, Arnaldo socio)

Si no es obvio, **preguntar antes de avanzar**.

## Tabla matriz

| Recurso | [[wiki/entidades/agencia-arnaldo-ayala\|Agencia Arnaldo Ayala]] | [[wiki/entidades/lovbot-ai\|Agencia Lovbot.ai]] | [[wiki/entidades/system-ia\|Agencia System IA]] |
|---------|--------------------------------------------------------------|--------------------------------------------------|--------------------------------------------------|
| **Dueño de la agencia** | [[arnaldo-ayala]] | [[robert-bazan]] | [[micaela-colmenares]] |
| **Rol de Arnaldo** | Dueño | Socio técnico | Socio técnico |
| **VPS** | [[wiki/entidades/vps-hostinger-arnaldo\|Hostinger Arnaldo]] | [[wiki/entidades/vps-hetzner-robert\|Hetzner Robert]] | [[wiki/entidades/vps-hostinger-mica\|Hostinger Mica]] |
| **Orquestador** | [[wiki/entidades/coolify-arnaldo\|Coolify]] `coolify.arnaldoayalaestratega.cloud` | [[wiki/entidades/coolify-robert\|Coolify]] `coolify.lovbot.ai` | [[wiki/entidades/easypanel-mica\|Easypanel]] |
| **Backend FastAPI** | `agentes.arnaldoayalaestratega.cloud` | `agentes.lovbot.ai` | `agentes.arnaldoayalaestratega.cloud` (via paths `/mica/*` y `/clientes/system-ia/*`) |
| **Base de datos del bot** | 🔒 [[wiki/conceptos/airtable\|Airtable]] (base de Arnaldo) | 🔒 **[[wiki/conceptos/postgresql\|PostgreSQL `robert_crm`]]** | 🔒 [[wiki/conceptos/airtable\|Airtable]] `appA8QxIhBYYAHw0F` (base propia de Mica) |
| **Cal.com (agenda)** | Cal.com de Arnaldo | Cal.com de Arnaldo (COMPARTIDO) | Cal.com de Arnaldo (COMPARTIDO) |
| **Supabase (CRM SaaS)** | — (no usa) | Supabase de Arnaldo (COMPARTIDO, solo tenants) | Supabase de Arnaldo (COMPARTIDO, solo tenants) |
| **OpenAI** | Cuenta Arnaldo (`OPENAI_API_KEY`) | 🔒 **Cuenta propia Robert** (`LOVBOT_OPENAI_API_KEY`) | Cuenta Arnaldo (COMPARTIDA) |
| **Gemini** | Cuenta Arnaldo | Cuenta Arnaldo (COMPARTIDA) | Cuenta Arnaldo (COMPARTIDA) |
| **WhatsApp provider** | [[wiki/conceptos/ycloud\|YCloud]] | [[wiki/conceptos/meta-graph-api\|Meta Graph API]] | [[wiki/conceptos/evolution-api\|Evolution API]] |
| **Chatwoot** | `chatwoot.arnaldoayalaestratega.cloud` | `chatwoot.lovbot.ai` (Hetzner) | `chatwoot.arnaldoayalaestratega.cloud` (compartido) |
| **n8n** | [[wiki/conceptos/n8n\|n8n]] `n8n.arnaldoayalaestratega.cloud` | [[wiki/conceptos/n8n\|n8n]] `n8n.lovbot.ai` | [[wiki/conceptos/n8n\|n8n]] `sytem-ia-pruebas-n8n.6g0gdj.easypanel.host` |

### Caso especial: [[wiki/entidades/lau\|Lau]] (proyecto propio de Arnaldo)

| Recurso | Valor |
|---------|-------|
| **Proyecto** | 🟢 Producción propia de [[arnaldo-ayala]] (esposa). NO es de Mica. |
| **VPS / Orquestador** | [[vps-hostinger-arnaldo]] + [[coolify-arnaldo]] (el backend FastAPI corre acá) |
| **WhatsApp provider** | [[evolution-api]] (⚠️ mismo servicio Evolution que Mica usa en [[easypanel-mica]] — pendiente separar). Instancia: `Lau Emprende`. Número: `+54 9 3765 00-5345` |
| **Base de datos** | [[airtable]] base `app4WvGPank8QixTU` |
| **Path del worker** | `workers/clientes/system_ia/lau/` — **path legacy engañoso**: NO implica ownership de Mica |

### Caso especial: [[wiki/entidades/back-urbanizaciones\|Back Urbanizaciones (Maicol)]]

| Recurso | Valor |
|---------|-------|
| **Proyecto** | 🟢 Producción propia de [[arnaldo-ayala]] (cliente externo). |
| **VPS / Orquestador** | [[vps-hostinger-arnaldo]] + [[coolify-arnaldo]] |
| **WhatsApp provider** | [[ycloud]]. Número: `+54 9 3764 81-5689` |
| **Base de datos** | [[airtable]] (base de Arnaldo) |
| **CRM** | `crm.backurbanizaciones.com` |
| **Path del worker** | `workers/clientes/arnaldo/maicol/` |

## Reglas críticas (errores que ya ocurrieron)

- ❌ Decir que **Robert usa Airtable** → Robert usa **PostgreSQL `robert_crm`**. Airtable es de Mica y Arnaldo únicamente.
- ❌ Mezclar `LOVBOT_OPENAI_API_KEY` con `OPENAI_API_KEY`:
  - `LOVBOT_OPENAI_API_KEY` = cuenta propia de Robert (la paga él)
  - `OPENAI_API_KEY` = cuenta de Arnaldo (compartida con Mica y Maicol)
- ❌ Configurar webhook de Mica en backend de Robert o viceversa.
- ❌ Usar la base Airtable vieja de Mica `appXPpRAfb6GH0xzV` — la correcta es `appA8QxIhBYYAHw0F`.
- ❌ Crear funciones que asumen Airtable cuando el cliente usa PostgreSQL (o viceversa).

## Protocolo obligatorio antes de tocar código de bot

1. **¿De qué cliente es?** Arnaldo / Robert / Mica
2. **¿Qué base de datos usa?** → mirar la tabla de arriba
3. **¿Qué cuenta OpenAI?** → mirar la tabla
4. **¿Qué WhatsApp provider?** → mirar la tabla
5. **¿Qué VPS/orquestador?** → mirar la tabla

Solo entonces escribir/modificar código.

## Worker → cliente → infraestructura (mapping rápido)

```
workers/clientes/arnaldo/maicol/                 → Maicol  → Airtable Arnaldo + YCloud + OpenAI Arnaldo
workers/clientes/arnaldo/prueba/                 → Test    → idem Arnaldo
workers/clientes/lovbot/robert_inmobiliaria/     → Robert  → PostgreSQL + Meta Graph + OpenAI Robert propio
workers/clientes/system_ia/lau/   ⚠️ LEGACY      → Lau     → PROYECTO PROPIO DE ARNALDO (NO de Mica) — Airtable Arnaldo + Evolution + OpenAI Arnaldo
workers/demos/inmobiliaria/                      → Demos   → Usado por Mica bajo path /mica/demos/inmobiliaria (genérico, Airtable)
workers/demos/gastronomia/                       → Demos
```

### ⚠️ Trampa del path — Lau

El worker de [[wiki/entidades/lau|Lau]] está en `workers/clientes/system_ia/lau/` por razones históricas, pero **Lau NO es cliente de [[wiki/entidades/micaela-colmenares|Mica]]**. Es proyecto propio de [[wiki/entidades/arnaldo-ayala|Arnaldo]] (su esposa, negocio "Creaciones Lau"). La ubicación del path es engañosa — tratar el proyecto según su dueño real, no según la carpeta.

## Sub-orquestadores (router) — subagentes de Claude Code

- Si path contiene `workers/clientes/arnaldo/*` → activar subagente `proyecto-arnaldo`
- Si path contiene `workers/clientes/lovbot/*` → activar subagente `proyecto-robert`
- Si path contiene `workers/clientes/system_ia/*` → activar subagente `proyecto-mica`

Cada subagente tiene su propia página en `.claude/agents/` y carga SOLO la columna de su proyecto.

## Fuentes que lo mencionan

_Aún no hay fuentes ingestadas. Esta página es **semilla** derivada de `feedback_REGLA_infraestructura_clientes.md` y la sesión de reestructuración del 2026-04-17._

## Perspectivas / contradicciones detectadas

Ninguna — esta matriz es la verdad única.
