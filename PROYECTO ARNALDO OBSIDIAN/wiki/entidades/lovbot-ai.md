---
title: "Lovbot.ai (agencia)"
type: agencia
proyecto: robert
tags: [agencia, lovbot, robert, marca-comercial]
---

# Lovbot.ai

## Descripción

Agencia comercial de [[robert-bazan]]. **Una de las 3 agencias del ecosistema** (las otras 2 son [[agencia-arnaldo-ayala]] y [[system-ia]]). [[arnaldo-ayala]] es **socio** (no dueño) y aporta construcción técnica; Robert es el dueño y pone infraestructura + clientes + operación comercial.

## Servicios que ofrece

Bots WhatsApp, CRMs, automatizaciones — enfocada inicialmente en nicho inmobiliario (Robert es desarrollador inmobiliario y conoce el vertical).

## Estado (2026-04-18)

- 🟢 Tech Provider Meta: Fase 1 completada, pendiente solicitud Advanced Access (lunes 2026-04-21)
- Bot demo inmobiliaria LIVE en `+52 1 998 743 4234` (Meta Graph API)
- CRM demo: `crm.lovbot.ai/?tenant=demo` (único tenant Supabase Lovbot)
- Admin panel: `https://admin.lovbot.ai/clientes` con `LOVBOT_ADMIN_TOKEN` (Coolify Hetzner desde 2026-04-23)
- Clientes externos: **NINGUNO productivo aún**. Robert es alianza técnica, no cliente pagando.
- NOTA arquitectural 2026-04-18: eliminado tenant `robert` de Supabase (era duplicado funcional con `demo`). Ahora solo hay 1 tenant demo por agencia. Los clientes reales se crean vía `/public/waba/onboarding` cuando se apruebe Meta Advanced Access.

## Infraestructura propia

- VPS: [[vps-hetzner-robert]]
- Orquestador: [[coolify-robert]] (`coolify.lovbot.ai`)
- Backend: `agentes.lovbot.ai`
- n8n: `n8n.lovbot.ai`
- Chatwoot: `chatwoot.lovbot.ai`
- Base de datos: [[postgresql]] (`robert_crm` en container `lovbot-crm-postgres`)
- WhatsApp provider: [[meta-graph-api]] (Robert es Tech Provider oficial)
- OpenAI: cuenta propia de Robert (`LOVBOT_OPENAI_API_KEY`) — NO la de Arnaldo

## 🚫 Stack PROHIBIDO en esta agencia

- ❌ [[airtable]] → usar [[postgresql]] siempre
- ❌ [[evolution-api]] o [[ycloud]] → usar [[meta-graph-api]]
- ❌ Infra de [[agencia-arnaldo-ayala]] o [[system-ia]] para datos del bot

## Servicios compartidos con Arnaldo

Robert usa servicios que corren en [[vps-hostinger-arnaldo]]:
- Cal.com de Arnaldo para agendar citas
- Supabase de Arnaldo para guardar tenants (solo gestión del SaaS, NO datos del bot)

## Relaciones con otras entidades

- Propiedad de → [[robert-bazan]]
- Socio técnico → [[arnaldo-ayala]]
- Infra → [[vps-hetzner-robert]] + [[coolify-robert]]
- Stack DB → [[postgresql]] (BD modelo: [[lovbot-crm-modelo]])
- Stack WA → [[meta-graph-api]]
- **CRM modelo (frontend HTML)** → [[crm-v2-modelo-robert]] (`crm.lovbot.ai/dev/crm-v2`, desde 2026-04-22)
- **Panel Gestión (admin de clientes que compraron CRM)** → [[panel-gestion-robert]] (`https://admin.lovbot.ai/clientes`, lee tenants de [[supabase-tenants]] — Coolify Hetzner desde 2026-04-23)
- 🆕 **CRM Gestión Agencia (uso interno Robert+Arnaldo) — pendiente** → [[crm-agencia-lovbot]] (Postgres Hetzner, captura leads de [[landing-lovbot-ai]] + bot agencia)
- 🆕 **Landing pública** → [[landing-lovbot-ai]] (`https://lovbot.ai/`)
- Catálogo de clientes ya activos (Supabase compartida) → [[supabase-tenants]]
- Agencia hermana → [[agencia-arnaldo-ayala]]
- Agencia hermana → [[system-ia]]

## Notas

- Domain: `lovbot.ai` (propiedad de Robert).
- Tech Provider Meta verificado → habilita WABA propia sin intermediarios.
