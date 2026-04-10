# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 1. Rol Activo — Leer Primero

**Al iniciar cualquier sesión, lee `ai.context.json` para saber qué agente encarnar:**

| `agente_activo` | Rol | AGENT.md |
|-----------------|-----|----------|
| `orquestador` | Gerente / coordinador | `.agents/01-orquestador/AGENT.md` |
| `ventas` | Cierre y propuestas | `.agents/02-ventas/AGENT.md` |
| `dev` | Ingeniero n8n + FastAPI | `.agents/03-dev/AGENT.md` |
| `crm` | Memoria y calidad de datos | `.agents/04-crm/AGENT.md` |

Actualiza `ai.context.json` al completar cada hito.

**Triggers de skill — activar ANTES de responder:**

| Pedido menciona... | Skill |
|--------------------|-------|
| `nuevo cliente`, `onboarding` | `/nuevo-cliente-onboarding` |
| `worker`, `bot`, `fastapi`, `endpoint` | `/fastapi-worker` |
| `debug`, `error`, `falla`, `no funciona` | `/debug-worker` |
| `n8n`, `workflow`, `flujo` | `/dev-n8n-architect` |
| `html`, `tailwind`, `crm`, `panel`, `landing` | `/tailwind-builder` |
| `airtable`, `tabla`, `campo`, `filtro` | `/airtable-expert` |
| `inmobiliaria`, `lote`, `terreno` | `/nicho-inmobiliaria` |
| `restaurante`, `cafetería`, `delivery` | `/nicho-gastronomia` |
| `wordpress`, `elementor`, `astra` | `/wordpress-elementor` |
| `copy`, `landing copy`, `propuesta` | `/copywriting` |
| `redes sociales`, `contenido`, `post` | `/social-content` |
| `pdf`, `excel`, `presentación` | `/pdf` `/xlsx` `/pptx` |

---

## 2. Arquitectura

Mission Control de **Agencia System IA** — automatizaciones para clientes en LATAM.

**Repo backend**: `github.com/Arnaldo999/system-ia-agentes` — push siempre `master:main`

### Workers monorepo

```
workers/
  clientes/
    arnaldo/maicol/worker.py    ← bot inmobiliario LIVE (YCloud + Airtable + Gemini)
    arnaldo/prueba/worker.py    ← bot prueba Arnaldo
    lovbot/                     ← clientes Robert (Meta Graph API)
    system-ia/                  ← clientes Mica (Evolution API)
  demos/
    inmobiliaria/worker.py      ← NUNCA editar, copiar para cliente nuevo
    gastronomia/worker.py       ← idem
  social/worker.py              ← comentarios IG/FB + publicación Pillow overlay
```

**Regla**: comentarios IG/FB → FastAPI, NO n8n. Nunca compartir workers entre proyectos.

### Infraestructura

| Proyecto | Backend | n8n |
|----------|---------|-----|
| Arnaldo | Coolify Hostinger → `agentes.arnaldoayalaestratega.cloud` | `n8n.arnaldoayalaestratega.cloud` |
| Robert/lovbot | Coolify Hetzner → `agentes.lovbot.ai` | `n8n.lovbot.ai` |
| Backup | Render → `system-ia-agentes.onrender.com` | — |
| Demos | Vercel → `lovbot-demos.vercel.app` | — |

**Regla crítica**: confirmar "¿Arnaldo / Robert / Mica?" antes de cualquier operación MCP, Coolify o Airtable.

### Estructura de carpetas (post-reorganización 2026-04-10)

```
00_GOBERNANZA_GLOBAL/    ← políticas, skills, hooks, agentes, memoria global
01_PROYECTOS/
  01_ARNALDO_AGENCIA/    ← backends, workflows, demos, clientes, memory
  02_SYSTEM_IA_MICAELA/  ← idem para Mica
  03_LOVBOT_ROBERT/      ← idem para Robert
02_OPERACION_COMPARTIDA/ ← scripts, tools, tests, execution, handoff, logs
99_ARCHIVO/              ← archive legacy
```

**Rutas actualizadas:**
- backends monorepo → `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/` (era `02_DEV_N8N_ARCHITECT/backends/`)
- demos → `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/` (era `DEMOS/`)
- execution → `02_OPERACION_COMPARTIDA/execution/` (era `execution/`)
- handoff → `02_OPERACION_COMPARTIDA/handoff/` (era `handoff/`)
- scripts → `02_OPERACION_COMPARTIDA/scripts/` (era `scripts/`)
- directives/ — **permanece en raíz** (sin cambios)
- memory/ — **permanece en raíz** (sin cambios)

### Handoff entre agentes

`ai.context.json` es el tablero compartido:
1. Orquestador escribe `agente_activo` + contexto
2. Agente ejecuta y escribe output en el JSON
3. Cambia `agente_activo` al siguiente
4. CRM documenta en `memory/`

Handoffs activos en `02_OPERACION_COMPARTIDA/handoff/brief-[cliente].md`.

---

## 3. Comandos

```bash
# Backend FastAPI
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
python -m py_compile main.py

# Frontend
npm install && npm run dev

# CrewAI sandbox
cd 01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/ai-sandbox/pruebas_crewai/ && source venv/bin/activate

# Agente no-interactivo
claude -p "Lee ai.context.json. Tu rol es [agente]. Tarea: [descripción]."

# Instalar nueva skill desde skills.sh
npx skills add <owner/repo> -y
```

---

## 4. Directivas & Ejecución (Arquitectura 3 Capas)

**Antes de hacer algo manual, revisar si existe un script en `02_OPERACION_COMPARTIDA/execution/`.**

### Directivas (`directives/`) — SOPs formales — permanecen en raíz

| Directiva | Cuándo usar |
|-----------|-------------|
| `directives/deploy_worker.md` | Deploy a Coolify/Render |
| `directives/debug_worker.md` | Error, falla, comportamiento inesperado |
| `directives/onboard_client.md` | Cliente nuevo, implementación completa |

### Scripts (`02_OPERACION_COMPARTIDA/execution/`) — ejecución determinista

| Script | Propósito | Uso |
|--------|-----------|-----|
| `02_OPERACION_COMPARTIDA/execution/deploy_service.py` | Deploy completo GitHub + Coolify | `--name --workdir --vps` |
| `02_OPERACION_COMPARTIDA/execution/coolify_manager.py` | API Coolify (trigger, env vars, status) | importar como clase |
| `02_OPERACION_COMPARTIDA/execution/github_manager.py` | Crear repo, push, GitHub App | importar como módulo |
| `02_OPERACION_COMPARTIDA/execution/create_tenant.py` | Crear tenant CRM SaaS en Supabase | `--slug --nombre --proyecto` |

**Ciclo auto-reparación**: error → fix script → test → actualizar directiva → `memory/debug-log.md`.

---

## 5. Memoria Operativa

`memory/` — no reinventar, seguir lo documentado.

- `memory/infraestructura.md` — URLs, UUIDs Coolify, IDs Airtable
- `memory/nuevo-cliente-redes-sociales.md` — onboarding cliente social
- `memory/debug-log.md` — bugs conocidos y sus fixes

---

## 5. Skills del Proyecto

### Propias (`.claude/skills/`) — conocimiento de System IA

| Skill | Cuándo |
|-------|--------|
| `/tailwind-builder` | HTML + Tailwind, CRM, dashboards, demos |
| `/fastapi-worker` | Workers Python, bots WhatsApp, endpoints |
| `/airtable-expert` | CRUD, filtros, schemas, bugs API |
| `/nuevo-cliente-onboarding` | Cliente nuevo, brief de Ventas recibido |
| `/debug-worker` | Errores, fallas, diagnóstico |
| `/nicho-inmobiliaria` | Lotes, terrenos, inmobiliarias (LATAM) |
| `/nicho-gastronomia` | Restaurantes, cafeterías, delivery (LATAM) |
| `/wordpress-elementor` | WordPress + Elementor + Astra |
| `/dev-n8n-architect` | n8n + FastAPI, implementación técnica |
| `/orquestador-mission-control` | Coordinación, handoffs |
| `/ventas-consultivo` | Discovery, propuestas, cierre |
| `/crm-analyst` | Documentar, memoria, reportes |
| `/deploy` | Deploy en Coolify |

### Instaladas desde skills.sh (`.agents/skills/`) — symlink a Claude Code

**Anthropics (18):** `frontend-design`, `brand-guidelines`, `canvas-design`, `theme-factory`,
`pdf`, `xlsx`, `pptx`, `docx`, `doc-coauthoring`, `mcp-builder`, `webapp-testing`,
`web-artifacts-builder`, `skill-creator`, `claude-api`, `internal-comms`,
`slack-gif-creator`, `algorithmic-art`, `template-skill`

**Marketing/Vercel (34+):** `copywriting`, `social-content`, `seo-audit`, `marketing-psychology`,
`content-strategy`, `find-skills`, `frontend-design`, `web-design-guidelines`,
`cold-email`, `email-sequence`, `paid-ads`, `ad-creative`, `lead-magnets`,
`launch-strategy`, `pricing-strategy`, `ab-test-setup`, `competitor-alternatives`,
`customer-research`, `revops`, `sales-enablement`, y más CRO/SEO

**Supabase (2):** `supabase`, `supabase-postgres-best-practices`

**n8n especializadas (8):** `n8n-mcp-tools-expert`, `n8n-code-javascript`, `n8n-code-python`,
`n8n-expression-syntax`, `n8n-node-configuration`, `n8n-validation-expert`,
`n8n-workflow-patterns`, `n8n-debugging`

> **Principio**: solo nombre+descripción de cada skill vive en contexto siempre.
> El cuerpo completo se carga únicamente cuando la skill se activa.
> Usar `/find-skills [descripción]` para buscar skills adicionales en skills.sh.
