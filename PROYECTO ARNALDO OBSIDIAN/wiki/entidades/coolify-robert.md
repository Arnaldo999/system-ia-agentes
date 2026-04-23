---
title: "Coolify Robert (Hetzner)"
type: orquestador
proyecto: robert
tags: [coolify, robert, lovbot, orquestador, paas]
---

# Coolify Robert

## Descripción

Instancia de Coolify (self-hosted PaaS) instalada en [[vps-hetzner-robert]]. Es donde corren todos los servicios de [[robert-bazan]] — **es infraestructura propia de Robert**, no de Arnaldo. Arnaldo tiene credenciales de API para operar en nombre del cliente (deploys, monitoring).

## Acceso

- URL: `https://coolify.lovbot.ai/`
- Tokens en `.env` del Mission Control:
  - `COOLIFY_ROBERT_URL=http://5.161.235.99:8000` (IP interna — para API)
  - `COOLIFY_ROBERT_TOKEN` → Bearer token
  - `COOLIFY_ROBERT_APP_UUID=ywg48w0gswwk0skokow48o8k`

## Servicios que orquesta

- **FastAPI monorepo** `agentes.lovbot.ai` — bot [[robert-bazan]] (Lovbot Inmobiliaria Demo) y endpoints CRM
- **n8n** `n8n.lovbot.ai`
- **Chatwoot** `chatwoot.lovbot.ai`
- **PostgreSQL** container `lovbot-crm-postgres` — base `robert_crm` (datos del bot y del CRM SaaS de Robert)
- **Admin panel** `admin.lovbot.ai`

## 🚫 NO deployar acá

- ❌ Workers de Arnaldo (Maicol, Lau) — van a [[coolify-arnaldo]].
- ❌ Workers de Mica — van a [[easypanel-mica]] (o al monorepo de Arnaldo via paths compartidos).
- ❌ Servicios que usen Airtable / Evolution / YCloud — incompatibles con el stack Robert.

## Relaciones con otras entidades

- Corre sobre → [[vps-hetzner-robert]]
- Pertenece a → [[robert-bazan]]
- Deploya bot de → [[robert-bazan]]

## Convenciones de deploy

- Mismo repo que Arnaldo (`github.com/Arnaldo999/system-ia-agentes`) pero deploy a `coolify.lovbot.ai` en vez de `coolify.arnaldoayalaestratega.cloud`.
- Scripts de deploy: pasar `--vps robert` a `deploy_service.py` o usar `CoolifyManager(vps="robert")`.

## Apps deployadas (al 2026-04-23)

| App | UUID | FQDN | Stack | Autodeploy |
|-----|------|------|-------|-----------|
| `system-ia-agentes` | `ywg48w0gswwk0skokow48o8k` | `agentes.lovbot.ai` | FastAPI Python (Dockerfile) | ✅ GitHub App oficial |
| `lovbot-crm-modelo` | `wcgg4kk0sw0g0wgw4swowog0` | `crm.lovbot.ai` | nginx alpine estático | ✅ GitHub App oficial |
| `lovbot-admin-internal` | `v0k8480sw800o00og0oo04g8` | `admin.lovbot.ai` | nginx alpine estático (sirve `clientes.html` + `agencia.html`) | ✅ Webhook manual GitHub (configurado 2026-04-23) |

> **Cambio histórico 2026-04-23**: el frontend CRM de Robert (`crm.lovbot.ai`) y el panel admin (`admin.lovbot.ai`) se migraron de Vercel a [[coolify-robert]] para escapar del límite Vercel Hobby. Ahora **toda la stack productiva de Lovbot vive en Hetzner** (cero Vercel productivo). Solo Mica y los demás demos siguen en Vercel. Ver [[crm-v2-modelo-robert]] y [[panel-gestion-robert]].

## Notas

- El PostgreSQL convive en la misma red Docker que la app FastAPI — conexión via hostname del container.
- Las apps estáticas nginx alpine consumen <10MB RAM cada una — el VPS Hetzner las maneja sin problema sumadas a backend + Postgres + n8n + Chatwoot.
