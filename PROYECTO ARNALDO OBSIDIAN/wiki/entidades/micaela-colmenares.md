---
title: "Micaela Colmenares"
type: persona
proyecto: mica
tags: [mica, micaela, socia, system-ia, proyecto-mica]
---

# Micaela Colmenares

## Descripción

Socia comercial de [[arnaldo-ayala]] en la marca **System IA**. System IA es la marca bajo la que Mica comercializa servicios de bots y automatización a sus propios clientes. Arnaldo aporta infraestructura compartida (backend FastAPI, Cal.com, Supabase, OpenAI) y construcción técnica; Mica aporta clientes y gestión comercial.

> ⚠️ **Nota importante**: [[lau]] NO es cliente de Mica, aunque el worker viva en `workers/clientes/system_ia/lau/`. Esa carpeta contiene código legacy — Lau es proyecto propio de Arnaldo.

## Stack asociado (System IA)

Ver [[wiki/conceptos/matriz-infraestructura]] columna "Mica".

- **VPS**: Easypanel propio.
- **Orquestador**: Easypanel.
- **Backend FastAPI**: `agentes.arnaldoayalaestratega.cloud` (compartido con Arnaldo, via paths `/mica/*` y `/clientes/system-ia/*`).
- **Base de datos del bot**: 🔒 **Airtable base `appA8QxIhBYYAHw0F`** (base propia de Mica).
- **WhatsApp provider**: Evolution API (self-hosted en su VPS Easypanel).
- **Chatwoot**: `chatwoot.arnaldoayalaestratega.cloud` (compartido con Arnaldo).
- **n8n**: `sytem-ia-pruebas-n8n.6g0gdj.easypanel.host` (Easypanel Mica) o `n8n.arnaldoayalaestratega.cloud`.

## Stack compartido con Arnaldo

- Cal.com de Arnaldo (citas).
- Supabase de Arnaldo (CRM SaaS — solo tenants, no datos de bot).
- Cuenta OpenAI de Arnaldo (`OPENAI_API_KEY`).
- Cuenta Gemini de Arnaldo.

## 🚫 NO usa bajo ninguna circunstancia

- ❌ PostgreSQL `robert_crm` — eso es solo de Robert.
- ❌ Meta Graph API directo — Mica usa Evolution API.
- ❌ YCloud — eso es solo de Arnaldo.
- ❌ `LOVBOT_OPENAI_API_KEY` — esa es de Robert.
- ❌ Base Airtable vieja `appXPpRAfb6GH0xzV` — la correcta es `appA8QxIhBYYAHw0F`.

## Aparece en

_Pendiente ingestar fuentes._

## Relaciones con otras entidades

- Socia de → [[arnaldo-ayala]] (marca System IA)
- Clientes propios → (ninguno documentado todavía — pendiente ingestar brief)
- Demo inmobiliaria → `workers/demos/inmobiliaria/` servida bajo path `/mica/demos/inmobiliaria`
- **NO es cliente suyo**: [[lau]] (aunque el path diga `system_ia/` — es proyecto propio de Arnaldo)

## Notas

- Marca comercial: **System IA**
- CRM producción: `system-ia-agencia.vercel.app/system-ia/crm?tenant=[slug]`
- Admin panel: `system-ia-agencia.vercel.app/system-ia/admin` (token `system-ia-admin-2026`)
- Número WhatsApp demo inmobiliaria de Mica: `5493765005465`
- Nombres asesores/email personal: pendiente documentar al ingestar fuentes.
