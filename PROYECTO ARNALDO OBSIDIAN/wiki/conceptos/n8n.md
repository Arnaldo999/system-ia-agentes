---
title: "n8n"
tags: [n8n, automatizacion, workflows]
source_count: 0
proyectos_aplicables: [arnaldo, robert, mica]
---

# n8n

## Definición

Plataforma open-source de automatización visual (competidor de Zapier/Make). Los 3 proyectos tienen **instancias n8n separadas e independientes** — NO comparten workflows ni credenciales.

## Una instancia por proyecto

| Proyecto | URL | Host | Repo de backup |
|----------|-----|------|----------------|
| [[arnaldo-ayala]] | `https://n8n.arnaldoayalaestratega.cloud/` | [[coolify-arnaldo]] | `N8N-REPOSITORIO` (pendiente setup) |
| [[robert-bazan]] | `https://n8n.lovbot.ai/` | [[coolify-robert]] | `N8N-REPOSITORIO-LOVBOT` (pendiente setup) |
| [[micaela-colmenares]] | `https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/` | [[easypanel-mica]] | `N8N-REPOSITORIO-SYSTEM-IA-DEMO` (pendiente setup) |

## Workflows activos destacados

- **Arnaldo — redes sociales**: workflow `aJILcfjRoKDFvGWY` (publicación IG/FB/LI diaria). Activar toggle manual en UI.
- **Arnaldo — alerta vencimientos Maicol**: Schedule 8am ARG → SMTP + WhatsApp asesor (3 días antes).
- **Mica — publicación redes**: workflow `aOiZFbmvMoPSE0vB` activo en Easypanel desde 2026-04-09.
- **Mica — CRM IA chat**: activo en `n8n.arnaldoayalaestratega.cloud` (no en Easypanel) — usa Airtable `appA8QxIhBYYAHw0F`.
- **Robert — CRM IA chat + pipeline kanban**: activo en `n8n.lovbot.ai` — usa database `robert_crm`.

## MCP Servers de n8n en Claude Code

Tres MCPs configurados en `.mcp.json` del Mission Control: `mcp__n8n__*` (Arnaldo), `mcp__n8n-mica__*`, `mcp__n8n-lovbot__*` (Robert). Cada uno apunta a una instancia distinta — **jamás usar el MCP equivocado** para el proyecto que estás operando.

## ⚠️ Reglas críticas

- Nunca copiar un workflow de una instancia a otra sin revisar credenciales (apuntan a bases de datos distintas).
- Nunca editar directamente un workflow productivo — exportar → modificar → importar.
- Robert usa credenciales de PostgreSQL `robert_crm`; Mica usa credenciales Airtable `appA8QxIhBYYAHw0F`; Arnaldo usa Airtable + YCloud.

## Bugs conocidos

- Mica: al actualizar n8n verificar `N8N_ENCRYPTION_KEY` antes — si se pierde, se desencriptan mal todas las credenciales.
- Robert CRM: usar database `robert_crm` (NO `lovbot_crm`) en credenciales Postgres.
- Mica CRM: usar base Airtable `appA8QxIhBYYAHw0F` (NO la vieja `appXPpRAfb6GH0xzV`).

## Fuentes que lo mencionan

_Pendiente ingestar: `project_crm_ia_chat.md`, `project_auditoria_agencia.md`, `project_social_publishing.md` en memory del Mission Control._
