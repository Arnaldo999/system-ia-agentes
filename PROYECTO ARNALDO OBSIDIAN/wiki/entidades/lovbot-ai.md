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

## Estado (2026-04-17)

- 🟠 En construcción / Sprint 1 BANT terminado
- Bot demo inmobiliaria LIVE en `+52 1 998 743 4234` (Meta Graph API)
- CRM demo: `lovbot-demos.vercel.app/dev/crm?tenant=robert`
- CRM producción: `crm.lovbot.ai?tenant=robert`
- Admin panel: `admin.lovbot.ai`
- Clientes externos: pendiente documentar (Robert trae prospectos del mercado inmobiliario).

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
- Stack DB → [[postgresql]]
- Stack WA → [[meta-graph-api]]
- Agencia hermana → [[agencia-arnaldo-ayala]]
- Agencia hermana → [[system-ia]]

## Notas

- Domain: `lovbot.ai` (propiedad de Robert).
- Tech Provider Meta verificado → habilita WABA propia sin intermediarios.
