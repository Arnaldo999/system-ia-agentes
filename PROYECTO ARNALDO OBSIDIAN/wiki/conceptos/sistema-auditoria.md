---
title: Sistema de Auditoría Diaria
tags: [compartido, auditoria, monitoreo, coolify, n8n, telegram]
source_count: 0
proyectos_aplicables: [arnaldo, robert, mica]
---

# Sistema de Auditoría Diaria

## Definición

Sistema automatizado que corre cada mañana a las 8:00 AM ARG y verifica el estado de los 3 proyectos del ecosistema. Ante alertas, intenta auto-reparar y reporta por Telegram.

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

## Auto-reparación

Si hay alertas, `auto_reparador.py` intenta:
1. **FastAPI Arnaldo caído** → restart Coolify → si falla → deploy completo con force
2. **Evolution instancia desconectada** → restart instancia via API

Resultado incluido en el reporte Telegram como sección "🔧 AUTO-REPARACIÓN".

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
