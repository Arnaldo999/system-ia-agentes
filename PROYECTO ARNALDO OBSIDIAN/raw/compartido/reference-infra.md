---
name: Referencias de infraestructura
description: URLs, IDs, endpoints y carpetas clave de la infraestructura de produccion
type: reference
originSessionId: 7accf720-af36-49d0-bc07-ba7e60eb27c2
---
## Servicios

| Recurso | Valor | Notas |
|---------|-------|-------|
| FastAPI Coolify (PRIMARIO) | `http://system-ia-agentes:8000` | Red interna Docker — alias `system-ia-agentes` |
| FastAPI FQDN público | `https://agentes.arnaldoayalaestratega.cloud` | Para YCloud webhooks — DNS A record pendiente usuario |
| Coolify App UUID | `ygjvl9byac1x99laqj4ky1b5` | Proyecto `microservicios`, env `production` |
| Coolify base_directory | `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes` | Post-reorganización 2026-04-10 — verificar en Coolify antes de redeploy |
| FastAPI Render (backup) | https://system-ia-agentes.onrender.com | Mantener activo, NO eliminar |
| Render Service ID | `srv-d6g8qg5m5p6s73a00llg` | Para API calls de config |
| GitHub repo | github.com/Arnaldo999/system-ia-agentes | Push: `master:main` |
| n8n Produccion (Arnaldo) | https://n8n.arnaldoayalaestratega.cloud | Coolify / Hostinger VPS |
| n8n Staging (Mica) | https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host | Easypanel VPS Mica |
| Airtable Maicol | base `appaDT7uwHnimVZLM` | props: `tbly67z1oY8EFQoFj` |
| Airtable Demo Inmobiliaria | base `appXPpRAfb6GH0xzV` | Clientes: `tblonoyIMAM5kl2ue`. Props: `tbly67z1oY8EFQoFj`. Token: var `AIRTABLE_API_KEY` — mismo PAT que Maicol, scope "todas las bases". ✅ Verificado 2026-03-31 |
| Airtable Gastronomico | base `appdA5rJOmtVvpDrx` | Demo "La Parrilla de Don Alberto" |
| n8n Keep-alive | workflow `kjmQdyTGFzMSfzov` | Pinga /health cada 14min |
| n8n Maicol bot | workflow `o4CrjByltFurUWox` | Webhook /inmobiliaria |

## Vercel (Demo Pack)

| Recurso | Valor |
|---------|-------|
| Vercel project | `lovbot-demos` |
| Vercel URL | `lovbot-demos.vercel.app` |
| Routing | `vercel.json` en raíz — rewrites actualizados 2026-04-12 a rutas `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/` |
| Repo conectado | `Arnaldo999/system-ia-agentes` branch `main` |
| Framework | Other (HTML estático, sin build) |

## Demos folder structure (actualizado 2026-04-12)

| Carpeta | Contenido |
|---------|-----------|
| `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/` | demo-crm-mvp.html, formulario-*.html, informe-mercado, dev/ |
| `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/GASTRONOMIA/` | gastronomia.html (subniche switcher) |
| `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/back-urbanizaciones/` | crm.html, formulario.html, mapa-publico.html (Maicol prod) |
| `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/` | admin.html, crm.html (Mica CRM SaaS) |

## PostgreSQL Arnaldo/Mica (Coolify Arnaldo — Hostinger VPS) — creado 2026-04-15

| Recurso | Valor |
|---------|-------|
| Coolify UUID | `oknk8w69xzw6ma5j3ugqwykb` |
| DB interna | `oknk8w69xzw6ma5j3ugqwykb:5432` |
| DB name | `system_ia_db` |
| User | `system_ia` |
| Env vars app | `ARNALDO_PG_*` (para clientes Arnaldo) / `MICA_PG_*` (para clientes Mica) |
| Tabla sesiones | `bot_sessions` (telefono+tenant PK, sesion_data JSONB, historial JSONB) |
| Tenant Mica demo | `MICA_TENANT_SLUG=demo` |

## Chatwoot (Coolify — Hostinger VPS)

| Recurso | Valor |
|---------|-------|
| UUID Coolify | `cw4u5edbafqxo411nb7o38ck` |
| URL | `chatwoot.arnaldoayalaestratega.cloud` |
| VPS IP | `187.77.254.33` |
| Inbox "Bot Prueba Arnaldo" | ID=1, identifier=`2ATjA4F6GNZ7XkDhSazpUyMN` |
| API Token Prueba | var `CHATWOOT_API_TOKEN_PRUEBA` en Coolify (migrado desde Render) |
| Account ID | 1 |
| Webhook FastAPI | `POST /clientes/arnaldo/prueba/chatwoot-webhook` |
| Nota | No hay integración nativa YCloud↔Chatwoot — bridge FastAPI es el único camino |

## Coolify — VPS Arnaldo (Hostinger)

| Recurso | Valor |
|---------|-------|
| URL panel | `https://coolify.arnaldoayalaestratega.cloud` |
| VPS IP | `187.77.254.33` |
| Proyecto deploy | `microservicios` — UUID `wo3e9mp1r5s6i3zep7xvuhv1` |
| Environment | `production` — UUID `lqihvkxtpakw2gi4oyrtda5d` |
| GitHub App | `microservicios-agenticos` — UUID `ys607xo8wcu1k14wk98mac5y`, installation_id `121329895` |
| GitHub App scope | "All repositories" ✅ |
| Server UUID | `z8pqb6hs23yw3lfio9iif23m` |
| Token | var `COOLIFY_TOKEN` en `.env` raíz Mission Control |
| Scripts deploy | `execution/coolify_manager.py`, `execution/github_manager.py`, `execution/deploy_service.py` |
| Slash command | `/deploy` — orquesta deploy completo autónomo |
| Estado | ✅ Listo para primer deploy autónomo — todos los tests pasaron |

## Coolify — VPS Robert (Hetzner)

| Recurso | Valor |
|---------|-------|
| URL panel | `https://coolify.lovbot.ai` |
| IP pública | `5.161.235.99` |
| Proyecto "Lovbot Projects" UUID | `ygwkgwsos0wgwgwscc4c8c40` — n8n de Robert |
| Proyecto "Agentes" UUID | `ck0kccsws4occ88488kw0g80` — workers FastAPI |
| Token | var `COOLIFY_ROBERT_TOKEN` en `.env` |
| GitHub App | `agentes-lovbot` → repo `Arnaldo999/system-ia-agentes` |
| DNS configurado | `coolify.lovbot.ai` + `agentes.lovbot.ai` → `5.161.235.99` (cPanel lovbot.ai) |
| API verificada | ✅ 2026-04-06 |

## Carpetas de proyecto en monorepo (post-reorganización 2026-04-10)

| Carpeta | Proyecto | Contenido |
|---------|----------|-----------|
| `00_GOBERNANZA_GLOBAL/` | Políticas globales | Skills, hooks, agentes, memoria global |
| `01_PROYECTOS/01_ARNALDO_AGENCIA/` | Arnaldo | Backends, workflows, demos, clientes, memory |
| `01_PROYECTOS/02_SYSTEM_IA_MICAELA/` | Mica | Idem para Mica |
| `01_PROYECTOS/03_LOVBOT_ROBERT/` | Robert | Idem para Robert |
| `02_OPERACION_COMPARTIDA/` | Compartido | scripts, tools, tests, execution, handoff, logs |
| `99_ARCHIVO/` | Archivo | Legacy archivado |
| `directives/` | SOPs | Permanece en raíz |
| `memory/` | Memoria Claude | Permanece en raíz |

⚠️ Rutas actualizadas (antes → después):
- `02_DEV_N8N_ARCHITECT/backends/` → `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/`
- `DEMOS/` → `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/`
- `execution/` → `02_OPERACION_COMPARTIDA/execution/`
- `handoff/` → `02_OPERACION_COMPARTIDA/handoff/`
- `scripts/` → `02_OPERACION_COMPARTIDA/scripts/`
