---
title: "System IA (agencia)"
type: agencia
proyecto: mica
tags: [system-ia, mica, agencia, marca-comercial]
---

# System IA

## Descripción

Agencia comercial de [[micaela-colmenares]]. **Una de las 3 agencias del ecosistema** (las otras 2 son [[agencia-arnaldo-ayala]] y [[lovbot-ai]]). [[arnaldo-ayala]] es **socio** (no dueño) y aporta construcción técnica; Mica es la dueña, aporta clientes y gestión comercial.

**System IA ≠ el ecosistema Mission Control de Arnaldo** — son cosas distintas aunque compartan infraestructura (backend FastAPI de Arnaldo, Cal.com, Supabase, OpenAI).

## ⚠️ Desambiguación obligatoria

- **Mission Control** → repo `SYSTEM_IA_MISSION_CONTROL` — es el workspace de Arnaldo (orquesta todos los proyectos del ecosistema). El nombre del repo menciona "system ia" por razones históricas pero NO es propiedad de Mica.
- **System IA (agencia)** → agencia comercial de Mica — esta página. Sus propios clientes.
- **[[agencia-arnaldo-ayala|Arnaldo Ayala — Estratega en IA y Marketing]]** → agencia propia de Arnaldo (Maicol, Lau).
- **[[lovbot-ai|Lovbot.ai]]** → agencia de Robert.

Las 3 agencias son entidades separadas. Jamás atribuir clientes de una a otra.

## Dominios y servicios

- **Frontend CRM SaaS**: `https://system-ia-agencia.vercel.app/system-ia/crm?tenant=[slug]` (Vercel)
- **Admin panel**: `https://system-ia-agencia.vercel.app/system-ia/admin` (token: `system-ia-admin-2026`)
- **Backend**: `agentes.arnaldoayalaestratega.cloud/mica/*` + `/clientes/system-ia/*` — monorepo compartido con Arnaldo
- **n8n**: en [[easypanel-mica]] (o n8n de Arnaldo cuando workflow toca infra compartida)
- **WhatsApp provider**: [[evolution-api]] self-hosted en [[vps-hostinger-mica]]
- **Base de datos**: [[airtable]] base `appA8QxIhBYYAHw0F` (Inmobiliaria Demo Mica)
- **Número demo**: `+54 9 3765 00-5465`

## Relaciones con otras entidades

- Propiedad de → [[micaela-colmenares]]
- Socio técnico → [[arnaldo-ayala]]
- Infra propia → [[vps-hostinger-mica]] + [[easypanel-mica]]
- Infra compartida con Arnaldo → backend FastAPI en [[coolify-arnaldo]]
- Base de datos → [[airtable]] (base modelo: [[inmobiliaria-demo-mica-airtable]])
- WhatsApp provider → [[evolution-api]]
- **CRM modelo (frontend HTML)** → [[crm-v2-modelo-mica]] (`/system-ia/dev/crm-v2`, desde 2026-04-22)
- **Panel Gestión (admin)** → [[panel-gestion-mica]] (`system-ia-agencia.vercel.app/system-ia/admin`, lee tenants de [[supabase-tenants]])
- Catálogo de clientes (Supabase compartida con Lovbot) → [[supabase-tenants]]
- Clientes comerciales propios → (pendiente ingestar briefs)
- Agencia hermana → [[agencia-arnaldo-ayala]]
- Agencia hermana → [[lovbot-ai]]

## Estado (2026-04-17)

- 🟡 En desarrollo — bot demo inmobiliaria LIVE, sin clientes productivos documentados aún.
