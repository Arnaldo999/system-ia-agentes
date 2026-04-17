---
title: "VPS Hetzner — Robert"
type: vps
proyecto: robert
tags: [vps, hetzner, robert, lovbot, infraestructura]
---

# VPS Hetzner — Robert

## Descripción

Servidor virtual privado de Hetzner propiedad de [[robert-bazan]] (Lovbot.ai). **NO pertenece a Arnaldo** — Robert contrata y paga su propia infraestructura. Arnaldo opera acá solo como proveedor técnico.

## Qué corre en este VPS

- **Orquestador**: [[coolify-robert]] → `https://coolify.lovbot.ai/`
- **Backend FastAPI**: `agentes.lovbot.ai` (monorepo FastAPI deployado vía GitHub App)
- **n8n**: `https://n8n.lovbot.ai/`
- **Chatwoot**: `https://chatwoot.lovbot.ai/` (inbox WhatsApp de Robert)
- **PostgreSQL `robert_crm`**: container `lovbot-crm-postgres` dentro de Coolify — base de datos del bot + CRM SaaS de Robert.

## 🚫 NO corre acá (importante)

- ❌ Airtable (Robert no usa Airtable — los datos del bot viven en PostgreSQL local).
- ❌ Evolution API (Robert usa Meta Graph API directo, es Tech Provider).
- ❌ YCloud.
- ❌ Clientes de Arnaldo (Maicol, Lau) ni clientes de Mica (corren en sus VPS respectivos).

## Relaciones con otras entidades

- Pertenece a → [[robert-bazan]]
- Corre → [[coolify-robert]]
- Hospeda bots de → [[robert-bazan]] (Lovbot Inmobiliaria Demo)
- Conecta con servicios compartidos en → [[vps-hostinger-arnaldo]] (Cal.com, Supabase)

## Dirección / Acceso

- IP interna (no accesible desde clientes): `5.161.235.99:8000` — para API Coolify desde herramientas Arnaldo usar el dominio HTTPS.
- Tokens/env vars: `COOLIFY_ROBERT_URL`, `COOLIFY_ROBERT_TOKEN`, `COOLIFY_ROBERT_APP_UUID=ywg48w0gswwk0skokow48o8k`.
