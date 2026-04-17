---
name: Claude Code — Infraestructura local (hooks, subagentes, skills)
description: Hooks, subagentes y skills implementados en Claude Code para automatizar validación, deploy y monitoreo
type: project
---

Sistema de automatización Claude Code implementado 2026-04-09.

**Why:** Detectar errores proactivamente, validar código antes de editar, y tener agentes especializados para tareas repetitivas.
**How to apply:** Estas herramientas están activas en toda sesión. Usarlas antes de hacer deploy o debuggear.

## Hooks (`.claude/hooks/`) — se ejecutan automáticamente

| Hook | Trigger | Acción |
|------|---------|--------|
| `validate-python.sh` | PreToolUse Edit/Write en .py | Advierte si el archivo tiene errores de sintaxis |
| `warn-production-edit.sh` | PreToolUse Edit/Write en workers Maicol | Devuelve JSON con advertencia "PRODUCCIÓN LIVE" |
| `pre-push-check.sh` | PreToolUse Bash con `git push` | Valida todos los workers, bloquea push si hay errores (exit 2) |

Configurados en `.claude/settings.json` sección `"hooks"`.

## Subagentes (`.claude/agents/`)

| Agente | Modelo | Tools | Cuándo usarlo |
|--------|--------|-------|---------------|
| `researcher.md` | Haiku | Read, Grep, Glob, Bash readonly | Explorar codebase sin modificar |
| `deployer.md` | Haiku | Bash | git push + Coolify API trigger + health check |
| `error-detector.md` | Sonnet | Read, Grep, Glob, Bash | Diagnóstico errores workers, sabe todos los bug patterns conocidos |

Coolify UUIDs en deployer: Arnaldo=`ygjvl9byac1x99laqj4ky1b5`, Robert=`ywg48w0gswwk0skokow48o8k`

## Skills (`.claude/skills/`)

| Skill | Comando | Qué hace |
|-------|---------|----------|
| `worker-deploy.md` | `/worker-deploy [proyecto] [entorno]` | Valida Python → git push → Coolify → health check |
| `monitor-errores.md` | `/monitor-errores` | Health check todos los FastAPI + n8n executions + `/debug/errors` → reporte |

## FastAPI — middleware de errores (`main.py`)

Agregado 2026-04-09:
- `registrar_error(endpoint, error, contexto)` — guarda en `_error_log` (max 100 entradas)
- `@app.middleware("http")` — captura 5xx y exceptions, loguea con `logger.error`
- `GET /debug/errors?limit=20` — endpoint para consultar errores recientes

## MCP — instancias n8n configuradas (`.mcp.json`)

| Key | Instancia | Versión n8n |
|-----|-----------|-------------|
| `n8n` | `n8n.arnaldoayalaestratega.cloud` | actual |
| `n8n-lovbot` | `n8n.lovbot.ai` | actual |
| `n8n-mica` | `sytem-ia-pruebas-n8n.6g0gdj.easypanel.host` | **2.35.6** (desactualizada) |

⚠️ **n8n Mica versión 2.35.6**: usar `typeVersion: 4.1` para httpRequest (NO 4.2), y formato antiguo de condiciones IF: `conditions.string[]` en vez de `conditions.conditions[]`. La UI crashea al abrir workflows con typeVersion incompatible.
