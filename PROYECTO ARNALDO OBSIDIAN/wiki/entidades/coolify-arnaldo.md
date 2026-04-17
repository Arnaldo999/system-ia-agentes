---
title: "Coolify Arnaldo (Hostinger)"
type: orquestador
proyecto: arnaldo
tags: [coolify, arnaldo, orquestador, paas]
---

# Coolify Arnaldo

## Descripción

Instancia de Coolify (self-hosted PaaS open-source) instalada en [[vps-hostinger-arnaldo]]. Es donde Arnaldo deploya y gestiona todos sus servicios: backend FastAPI, n8n, Chatwoot, Cal.com, Supabase, bases de datos auxiliares.

## Acceso

- URL: `https://coolify.arnaldoayalaestratega.cloud/`
- Tokens en `.env` del Mission Control:
  - `COOLIFY_URL` → URL arriba
  - `COOLIFY_TOKEN` → Bearer token para API
  - `COOLIFY_PROJECT_UUID=wo3e9mp1r5s6i3zep7xvuhv1`
  - `COOLIFY_ENVIRONMENT_UUID=lqihvkxtpakw2gi4oyrtda5d`
  - `COOLIFY_GITHUB_APP_ID=ys607xo8wcu1k14wk98mac5y`
  - `COOLIFY_GITHUB_INSTALLATION_ID=121329895`

## Servicios que orquesta

- **FastAPI monorepo** `agentes.arnaldoayalaestratega.cloud` — bots de [[maicol]], [[lau]], prueba Arnaldo, demos, CRM endpoints
- **n8n** `n8n.arnaldoayalaestratega.cloud` — workflows
- **Chatwoot** `chatwoot.arnaldoayalaestratega.cloud` — inbox WhatsApp compartido con Mica
- **Cal.com** — agenda compartida (la usan Arnaldo, Robert y Mica)
- **Supabase** — CRM SaaS multi-tenant

## Relaciones con otras entidades

- Corre sobre → [[vps-hostinger-arnaldo]]
- Pertenece a → [[arnaldo-ayala]]
- Deploya workers de → [[maicol]], [[lau]]

## Convenciones de deploy

- Push al repo `github.com/Arnaldo999/system-ia-agentes` (rama `master:main`) → webhook Coolify redeploya.
- Script de deploy determinista: `02_OPERACION_COMPARTIDA/execution/deploy_service.py` + `coolify_manager.py`.
- Slash command: `/deploy`.

## Notas

- base_directory del monorepo post-reorg: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/`.
- NO usar este Coolify para código de Robert — ese tiene su propio [[coolify-robert]].
