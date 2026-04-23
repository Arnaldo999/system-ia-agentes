---
title: Sistema de Auditoría — Capa 1 (cada 5 min) + Capa 2 (diaria 8am)
tags: [compartido, auditoria, monitoreo, coolify, n8n, telegram, capa-1, capa-2]
source_count: 1
proyectos_aplicables: [arnaldo, robert, mica]
---

# Sistema de Auditoría — 2 capas

## Definición

El ecosistema tiene **2 monitores complementarios** corriendo en paralelo, ambos en el mismo container Coolify Hostinger Arnaldo (`system-ia-agentes`):

| Capa | Script | Frecuencia | Propósito |
|------|--------|------------|-----------|
| **1 — Healthchecks** | `guardia_critica.py` | Cada 5 min | Detectar caídas en tiempo real (frontends, backends, n8n, Coolify, CORS) |
| **2 — Auditoría profunda** | `auditor_runner.py` | Diaria 8am ARG | Verificar workflows n8n, tokens OAuth, instancias WhatsApp, schemas DB, etc. |

Ambos avisan vía Telegram al chat de Arnaldo (`863363759`). La Capa 2 también dispara `auto_reparador.py` ante alertas conocidas.

## Arquitectura (3 capas)

```
n8n Arnaldo
  └── "🔍 Auditoría Diaria — Ecosistema Agencia (Fase 2)" [IuHJLy2hQhOIDlYK]
        ⏰ Schedule 8am ARG
        └── GET https://agentes.arnaldoayalaestratega.cloud/auditor/fase2
              └── main.py → auditor_runner.py
                    ├── 7 auditores (ver abajo)
                    ├── auto_reparador.py (si hay alertas)
                    └── Telegram → chat_id Arnaldo
```

## Los 7 auditores

| Auditor | Módulo | Qué verifica |
|---|---|---|
| Infraestructura | `auditor_infra.py` | FastAPI Arnaldo UP, workers activos en Coolify |
| Workflows | `auditor_workflows.py` | n8n Arnaldo — workflows activos vs esperados |
| YCloud | `auditor_ycloud.py` | Credenciales YCloud Maicol operativas |
| Tokens | `auditor_tokens.py` | Expiración de tokens OAuth (LinkedIn, Meta, etc.) |
| Evolution API | `auditor_evolution.py` | Instancias Evolution conectadas (Mica) |
| Meta Tech Provider | `auditor_meta_provider.py` | WABA Robert — estado de la cuenta Meta |
| CRM / Tenants | `auditor_crm.py` | Tenants activos en PostgreSQL / Airtable |

## Auto-reparación (solo Capa 2)

Si hay alertas, `auto_reparador.py` intenta:
1. **FastAPI Arnaldo caído** → restart Coolify → si falla → deploy completo con force
2. **Evolution instancia desconectada** → restart instancia via API

Resultado incluido en el reporte Telegram como sección "🔧 AUTO-REPARACIÓN".

## Capa 1 — `guardia_critica.py` (refactor 2026-04-22)

### Configuración

- **Schedule Coolify**: `*/5 * * * *  cd /app/scripts && python guardia_critica.py` (Scheduled Task UUID `fo5l5or8bbz3bl8d0n47dj9a`, activa desde 2026-04-11).
- **Cooldown**: 30 min por servicio (no spamea si un servicio queda caído mucho tiempo).
- **Mensaje Telegram CONSOLIDADO**: 1 ciclo = 1 mensaje con TODOS los servicios caídos juntos (refactor 2026-04-22 a pedido de Arnaldo — antes era 1 mensaje por servicio).
- **Kill switch**: env var `GUARDIA_DISABLED=1` desactiva el script sin tocar el cron.
- **Estado persistido**: `/tmp/guardia_estado.json` (cooldown por servicio).

### 18 checks activos + 2 preparados (deshabilitados)

#### Arnaldo
| Check | URL / acción |
|---|---|
| `fastapi` | `https://agentes.arnaldoayalaestratega.cloud/health` (status=healthy + workers≥6) |
| `n8n` | `https://n8n.arnaldoayalaestratega.cloud/healthz` |
| `n8n_mica` | `https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/healthz` |
| `n8n_lovbot` | `https://n8n.lovbot.ai/healthz` |
| `coolify` | API Coolify Arnaldo — app `system-ia-agentes` status `running:healthy` |
| `chatwoot_arnaldo` | `https://chatwoot.arnaldoayalaestratega.cloud/` HTTP 200/302 |
| `maicol_crm_frontend` | `https://crm.backurbanizaciones.com/` HTTP 200 |
| `maicol_crm_cors` | OPTIONS preflight con Origin del CRM (ver [[cors-preflight-monitoreo]]) |

#### Robert
| Check | URL / acción |
|---|---|
| `backend_robert` | `https://agentes.lovbot.ai/health` HTTP 200 |
| `robert_crm_modelo` | `https://crm.lovbot.ai/dev/crm-v2` ([[crm-v2-modelo-robert]]) |
| `robert_crm_dominio` | `https://crm.lovbot.ai/` |
| `robert_panel_gestion` | `https://admin.lovbot.ai/clientes` ([[panel-gestion-robert]]) — Coolify Hetzner desde 2026-04-23 |
| `robert_admin` | `https://admin.lovbot.ai/` |
| `robert_crm_cors` | OPTIONS preflight `agentes.lovbot.ai/health` con Origin `crm.lovbot.ai` |
| `robert_admin_clientes_internal` | `https://admin.lovbot.ai/clientes.html` — Coolify Hetzner (2026-04-22) |
| `robert_admin_agencia_internal` | `https://admin.lovbot.ai/agencia.html` — Coolify Hetzner (2026-04-22) |
| `robert_crm_modelo_internal` | `https://crm.lovbot.ai/dev/crm-v2.html` — Coolify Hetzner (lovbot-crm-modelo, 2026-04-23) |
| `robert_crm_js_panel_loteos` | `https://crm.lovbot.ai/dev/js/panel-loteos.js` — Coolify Hetzner (asset JS clave, 2026-04-23) |

#### Mica (deshabilitados, env var `MICA_CRM_ENABLED=0`)
| Check | URL / acción |
|---|---|
| `mica_crm` | URL pendiente — hoy `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2` ([[crm-v2-modelo-mica]]) |
| `mica_crm_cors` | OPTIONS preflight análogo cuando se defina dominio prod ([[panel-gestion-mica]]) |

> **Para activar Mica**: en Coolify → app `system-ia-agentes` → env vars: `MICA_CRM_URL=<dominio>` + `MICA_CRM_ENABLED=1`. Próximo ciclo cron picks up sin redeploy.

### Commits relevantes del refactor 2026-04-22

- `e628985` — refactor consolidado + 4 checks Arnaldo (agregó Maicol CRM CORS preflight + frontend + Chatwoot + Backend Robert)
- `e9604dd` — 3 checks Robert + 2 placeholders Mica
- `7856abd` — refinar Robert URL al CRM modelo real (`/dev/crm-v2`)

## Dónde vive el código

| Archivo | Path canónico (fuente de verdad) | Coolify usa |
|---|---|---|
| `auditor_runner.py` | `02_OPERACION_COMPARTIDA/scripts/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/scripts/` (sincronizado) |
| Módulos auditores | `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/scripts/` | misma ruta |
| `auto_reparador.py` | `02_OPERACION_COMPARTIDA/scripts/` | sincronizado en backends |
| Endpoint FastAPI | `main.py` línea ~365 (`GET /auditor/fase2`) | Coolify Hostinger |

> **Regla**: editar en `02_OPERACION_COMPARTIDA/scripts/` y luego copiar a `backends/scripts/` antes del deploy.

## Monitors adicionales (Fase 1)

| Workflow | Instancia n8n | ID | Estado |
|---|---|---|---|
| Monitor Vencimiento Tokens — LinkedIn Mica | n8n Mica | `jUBWVBMR6t3iPF7l` | ✅ ACTIVO |

## Remote Triggers (claude.ai/code/scheduled)

| Trigger | ID | Schedule | Función |
|---|---|---|---|
| Auditor de Código | `trig_01AJXYSDkvKtmfwfcejNmY3J` | Lunes 10:17 AM ARG | Secrets, naming, imports rotos, Cal.com v1, prints debug |
| Sync Docs + CLAUDE.md | `trig_01XDfSr6vFwZkNTiapRa1tba` | Miércoles 9:42 AM ARG | Escanea workers vs docs, actualiza CLAUDE.md |
| Generador de Workers | `trig_01FVyH3ywykvGR51fBKREMht` | Diario 12:33 (PAUSADO) | Lee INSTRUCCIONES_WORKER.md y genera worker con PR |

> Limitación: los Remote Triggers NO pueden hacer curl a URLs externas (sandbox bloqueado). Solo leen/escriben código en GitHub y abren PRs.

## Qué pasa si falla

| Escenario | Acción |
|---|---|
| `/auditor/fase2` no responde | n8n marca ejecución como error — sin alerta Telegram. Verificar Coolify. |
| Un auditor lanza excepción | Se loguea en el reporte con ❌, el resto sigue ejecutando |
| Auto-reparador no pudo reparar | Telegram muestra ❌ + "intervención manual" |
| Workflow n8n desactivado | La auditoría no corre — verificar `IuHJLy2hQhOIDlYK` en n8n Arnaldo |

## Fuentes relacionadas

- `[[wiki/entidades/vps-hostinger-arnaldo]]`
- `[[wiki/entidades/coolify-arnaldo]]`
- `[[wiki/conceptos/matriz-infraestructura]]`
