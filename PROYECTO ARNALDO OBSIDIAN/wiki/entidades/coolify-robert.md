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

## Notas

- Frontend CRM de Robert se sirve desde Vercel (`crm.lovbot.ai`, `lovbot-demos.vercel.app/dev/*`), no desde Coolify.
- El PostgreSQL convive en la misma red Docker que la app FastAPI — conexión via hostname del container.
