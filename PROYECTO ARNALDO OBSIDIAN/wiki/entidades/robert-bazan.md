---
title: "Robert Bazán"
type: persona
proyecto: robert
tags: [robert, cliente, lovbot, proyecto-robert, desarrollador-inmobiliario]
---

# Robert Bazán

## Descripción

Desarrollador inmobiliario, dueño de la marca comercial **Lovbot** (`lovbot.ai`). Cliente/aliado técnico de [[arnaldo-ayala]] — Arnaldo le construye bots, CRM y automatizaciones, Robert pone su propia infraestructura y sus propias cuentas.

Trabaja en **sector inmobiliario** (ventas de lotes/propiedades en desarrollos propios). Es Tech Provider oficial de Meta (WABA propia).

## Stack asociado (Lovbot)

Ver [[wiki/conceptos/matriz-infraestructura]] columna "Robert".

- **VPS**: Hetzner propio.
- **Orquestador**: Coolify Hetzner → `coolify.lovbot.ai`.
- **Backend FastAPI**: `agentes.lovbot.ai`.
- **Base de datos del bot**: 🔒 **PostgreSQL `robert_crm`** (en container `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck`, red Coolify).
- **OpenAI**: 🔒 **cuenta propia** (`LOVBOT_OPENAI_API_KEY`). NO es la cuenta de Arnaldo.
- **WhatsApp provider**: Meta Graph API (WABA oficial).
- **Chatwoot**: `chatwoot.lovbot.ai` (Hetzner).
- **n8n**: `n8n.lovbot.ai` (Hetzner).

## Stack compartido con Arnaldo

- Cal.com de Arnaldo (para agendar citas).
- Supabase de Arnaldo (para que Arnaldo vea los tenants del CRM SaaS — NO para datos del bot).
- Gemini de Arnaldo (compartido como fallback).

## 🚫 NO usa bajo ninguna circunstancia

- ❌ Airtable — usar PostgreSQL `robert_crm` siempre.
- ❌ Evolution API — Robert usa Meta Graph directo.
- ❌ YCloud — eso es solo de Arnaldo.
- ❌ `OPENAI_API_KEY` sin prefijo — usar `LOVBOT_OPENAI_API_KEY`.

## Aparece en

_Pendiente ingestar fuentes (brief-robert-bazan-reunion-24marzo.md, context-robert-bazan-completo.md, etc. en `clientes/` — candidatos a `raw/robert/`)._

## Relaciones con otras entidades

- Cliente/aliado de → [[arnaldo-ayala]]
- Marca comercial → Lovbot (lovbot.ai)
- Proyecto del bot → `workers/clientes/lovbot/robert_inmobiliaria/`
- Sprint 1 bot BANT — ver `project_robert_bot_sprint1.md` en memory Mission Control

## Notas

- Domain: `lovbot.ai`
- Admin panel: `https://admin.lovbot.ai/clientes` (token: `LOVBOT_ADMIN_TOKEN` = `lovbot-admin-2026`) — Coolify Hetzner desde 2026-04-23
- CRM demo Lovbot: `crm.lovbot.ai/dev/crm-v2?tenant=demo` (Coolify Hetzner desde 2026-04-23)
- CRM Gestión Agencia (uso interno Robert+Arnaldo): `https://admin.lovbot.ai/agencia` (mockup; backend Postgres pendiente — ver [[crm-agencia-lovbot]])
- Asesor humano configurado: "Roberto" (nombre asesor del bot = `INMO_DEMO_ASESOR`)
- Email/teléfono personal: `robert@lovbotagency.ca` (Chatwoot user id=2)
- Cambio 2026-04-18: eliminado tenant Supabase `robert` (duplicado con `demo`). El bot productivo en PG `robert_crm` / `waba_clients db_id=1` sigue intacto.
