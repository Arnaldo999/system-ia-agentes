# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🚨 REGLA #0 (LA MÁS IMPORTANTE) — Router de proyectos obligatorio

Este Mission Control orquesta **3 proyectos físicamente separados** que NO comparten stack:

| Proyecto | Carpeta del proyecto | Workers (monorepo) | Stack EXCLUSIVO |
|----------|----------------------|---------------------|-----------------|
| **Arnaldo Ayala** (agencia propia) | `01_PROYECTOS/01_ARNALDO_AGENCIA/` | `workers/clientes/arnaldo/` | Airtable + YCloud + Coolify Hostinger + OpenAI Arnaldo |
| **Micaela Colmenares** (System IA) | `01_PROYECTOS/02_SYSTEM_IA_MICAELA/` | `workers/clientes/system_ia/` | Airtable `appA8QxIhBYYAHw0F` + Evolution API + Easypanel + OpenAI Arnaldo |
| **Robert Bazán** (Lovbot) | `01_PROYECTOS/03_LOVBOT_ROBERT/` | `workers/clientes/lovbot/` | **PostgreSQL `robert_crm`** + Meta Graph API + Coolify Hetzner + **OpenAI propio Robert** |

> El monorepo FastAPI físicamente vive en `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/` pero los workers DENTRO se asignan lógicamente a cada proyecto según su subcarpeta `workers/clientes/[arnaldo|lovbot|system_ia]/`.

### Disparadores OBLIGATORIOS de subagente por proyecto

**ANTES de leer/editar cualquier archivo o ejecutar cualquier acción, identificar el proyecto y delegar al subagente correcto:**

| Si la tarea menciona o el path contiene… | Delegar SIEMPRE a subagente |
|-------------------------------------------|------------------------------|
| `arnaldo`, `maicol`, `back urbanizaciones`, `workers/clientes/arnaldo/*`, `demos/back-urbanizaciones/`, `01_PROYECTOS/01_ARNALDO_AGENCIA/` (excepto si es código compartido del backend) | `proyecto-arnaldo` |
| `robert`, `lovbot`, `lovbot.ai`, `robert_crm`, `workers/clientes/lovbot/*`, `demos/INMOBILIARIA/`, `01_PROYECTOS/03_LOVBOT_ROBERT/`, `coolify.lovbot.ai`, `agentes.lovbot.ai`, Meta Graph WABA Robert | `proyecto-robert` |
| `mica`, `micaela`, `system ia` (la marca), `lau`, `workers/clientes/system_ia/*`, `demos/SYSTEM-IA/`, `01_PROYECTOS/02_SYSTEM_IA_MICAELA/`, base Airtable `appA8QxIhBYYAHw0F`, Evolution API, Easypanel | `proyecto-mica` |

**Si la tarea menciona 2 proyectos** (ej: "compará el bot de Robert con el de Mica"), invocar los 2 subagentes en paralelo, nunca trabajar mezclando contexto.

**Si la tarea es genuinamente compartida** (infra global, scripts en `02_OPERACION_COMPARTIDA/`, hooks, skills) → mantener trabajo en agente principal.

### Errores típicos a evitar (ya pasaron muchas veces)

- ❌ Editar Airtable mientras trabajás en código de Robert (Robert NO usa Airtable, usa PostgreSQL)
- ❌ Usar `OPENAI_API_KEY` en código de Robert (es `LOVBOT_OPENAI_API_KEY`)
- ❌ Asumir Coolify Hostinger para deploy de Robert (es Coolify Hetzner)
- ❌ Mezclar `demos/INMOBILIARIA/` (Robert) con `demos/SYSTEM-IA/` (Mica) o `demos/back-urbanizaciones/` (Arnaldo)
- ❌ Usar Evolution API en código Arnaldo (es YCloud) o YCloud en código Robert (es Meta Graph)

> **Memoria detallada**: `feedback_REGLA_infraestructura_clientes.md` en `~/.claude/projects/.../memory/` — leer antes de operar si hay duda.

---

## 🗂️ REGLA #0bis — Arquitectura de silos (dónde va cada cosa)

El ecosistema tiene **4 silos separados** con roles no solapados. Cada información vive en **UN solo silo**. Si duplicás entre silos, uno va a mentirle al otro.

### Los 4 silos

| # | Silo | Path | Rol |
|---|------|------|-----|
| 1 | **Auto-memory global** | `~/.claude/projects/-home-arna-PROYECTOS-SYSTEM-IA-SYSTEM-IA-MISSION-CONTROL/memory/` | Preferencias y reglas IRROMPIBLES del usuario (feedback personal). Claude lo inyecta automáticamente en cada sesión. |
| 2 | **Wiki Obsidian** | `PROYECTO ARNALDO OBSIDIAN/` | Base de conocimiento permanente del ecosistema: entidades, conceptos, fuentes, síntesis. **Verdad única** sobre estructura. |
| 3 | **Mission Control operativo** | `memory/` (raíz) + `ai.context.json` | Estado operativo **efímero** (cambia frecuentemente): TODOs de sesión, ESTADO_ACTUAL, debug-log, handoffs entre agentes. |
| 4 | **Código y archivos físicos** | `01_PROYECTOS/*/backends,clientes,demos,workflows` | Código ejecutable + docs específicos por cliente (briefs, contratos, contextos). |

### Matriz "dónde guardo X"

| Tipo de información | Silo | Ejemplo de path |
|---------------------|------|------------------|
| Preferencia del usuario ("Arnaldo quiere respuestas cortas") | 1 | `~/.claude/.../memory/feedback_tono.md` |
| Regla irrompible de comportamiento ("nunca mezclar stacks") | 1 | `~/.claude/.../memory/feedback_REGLA_*.md` |
| Datos de agencia (VPS, DB, provider, dueños) | 2 | `PROYECTO ARNALDO OBSIDIAN/wiki/entidades/*.md` |
| Conceptos técnicos compartidos (Airtable, PostgreSQL, Meta Graph) | 2 | `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/*.md` |
| Brief/doc oficial de un cliente (fuente original) | 2 + 4 | `raw/[agencia]/brief-X.pdf` + archivo físico en `01_PROYECTOS/[agencia]/clientes/X/` |
| Exploración guardada / análisis cruzado | 2 | `PROYECTO ARNALDO OBSIDIAN/wiki/sintesis/*.md` |
| Qué se hizo hoy / TODO en curso | 3 | `memory/ESTADO_ACTUAL.md` |
| Bug a medias, fix aplicado hoy | 3 | `memory/debug-log.md` |
| Cuál agente está activo + handoff | 3 | `ai.context.json` |
| Worker del bot | 4 | `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/.../workers/clientes/[agencia]/[cliente]/` |
| Landing HTML / CRM frontend | 4 | `01_PROYECTOS/[agencia]/demos/[vertical]/` |
| Workflow n8n exportado | 4 | `01_PROYECTOS/[agencia]/workflows/` |

### 2 reglas irrompibles de los silos

1. **Regla de no-duplicación** — Una información vive en UN solo silo.
   - Si un dato está en wiki (silo 2), **NO** está en `memory/` (silo 3) ni en auto-memory (silo 1).
   - Si hay una regla en auto-memory (silo 1), **NO** se repiten sus datos en wiki.
   - Cuando detectes duplicación: elegí el silo correcto según la matriz y eliminá del otro.

2. **Regla de flujo efímero → duradero** — La info se promociona, no se duplica.
   - Arranca como estado (silo 3): "bug del día", "decisión tomada hoy".
   - Si estabiliza como conocimiento estructural (cambió el stack, regla nueva), **se mueve** al silo 2 (wiki) o silo 1 (auto-memory) y se elimina del silo 3.

### Flujo de trabajo por sesión

1. Al arrancar: auto-memory (silo 1) ya está cargado. Leo `CLAUDE.md` (router) + `ai.context.json` (silo 3) para saber estado actual.
2. Si la tarea toca una agencia específica: invoco subagente `proyecto-[arnaldo|robert|mica]`, que consulta la wiki (silo 2) para cargar stack.
3. Para estado operativo del día (qué falta, qué quedó a medias): leo `memory/ESTADO_ACTUAL.md` (silo 3).
4. Trabajo en el código (silo 4).
5. Al terminar:
   - Decisión durable / conocimiento nuevo → ingestar a wiki (silo 2) vía `raw/[agencia]/sesion-YYYY-MM-DD.md`.
   - Estado efímero del día → actualizar `memory/ESTADO_ACTUAL.md` o `debug-log.md` (silo 3).
   - Preferencia nueva del usuario → auto-memory (silo 1).

---

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
    inmobiliaria/worker.py      ← SANDBOX DE PRUEBAS — primero acá, después a cliente
    gastronomia/worker.py       ← idem
  social/worker.py              ← comentarios IG/FB + publicación Pillow overlay
```

## 🚨 REGLA IRROMPIBLE — Flujo Demo → Producción

**NUNCA modificar directamente workers en `clientes/`. SIEMPRE primero en `demos/`.**

Flujo obligatorio al implementar cualquier feature nueva:
1. **Desarrollar en el worker demo** (`workers/demos/inmobiliaria/worker.py` o `gastronomia/worker.py`)
2. **Probar funcionalidad** en el demo con datos de sandbox
3. **Cuando esté validado**, **copiar los cambios** al worker del cliente (`workers/clientes/*/`)
4. **Deploy del cliente** (redeploy Coolify)

Por qué esta regla existe:
- Los workers de `clientes/` atienden bots con tráfico REAL — un bug afecta conversaciones reales
- La demo es el **sandbox** donde experimentamos sin riesgo
- La demo es el **template** que se copia a clientes nuevos

Si un agente IA (incluyéndome a mí) pide modificar algo en `clientes/` sin haber probado en demo,
el usuario debe detenerme y recordarme esta regla.

**Misma regla aplica al CRM HTML**:
- Desarrollo: `demos/INMOBILIARIA/dev/crm.html` (sandbox)
- Producción: `demos/INMOBILIARIA/demo-crm-mvp.html` (nunca editar directo)

**Misma regla aplica a bases de datos**:
- Cada cliente tiene su propia DB PostgreSQL dedicada (ej: `robert_crm`, `maria_crm`)
- Demo usa `lovbot_crm` con `tenant_slug='demo'` como sandbox compartido
- Nunca mezclar datos de cliente con datos de demo

**Regla adicional**: comentarios IG/FB → FastAPI, NO n8n. Nunca compartir workers entre proyectos.

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

## 5bis. Wiki Obsidian — Memoria persistente del ecosistema

**Bóveda Obsidian**: `PROYECTO ARNALDO OBSIDIAN/` en la raíz del Mission Control. Es la **memoria persistente compartida** entre sesiones, complementaria a `memory/`.

### Estructura

```
PROYECTO ARNALDO OBSIDIAN/
├── CLAUDE.md              ← esquema de la wiki (reglas, convenciones, naming)
├── index.md               ← catálogo de todas las páginas
├── log.md                 ← registro cronológico append-only
├── raw/                   ← fuentes originales INMUTABLES
│   ├── arnaldo/ robert/ mica/ compartido/ assets/
└── wiki/                  ← páginas sintetizadas por Claude
    ├── entidades/ conceptos/ fuentes/ sintesis/
```

### Skill obligatoria

`.claude/skills/llm-wiki/` (Método Karpathy) — se activa cuando el usuario dice "ingerí esta fuente", "qué dice mi wiki sobre X", "hacé lint de la wiki", "guardá como síntesis", etc.

### Regla de ingesta — qué va a la wiki

Ingerir a la wiki cuando:
- El usuario comparte un **PDF, transcripción, artículo o URL** que agrega conocimiento duradero al ecosistema.
- Termina una **sesión importante con Claude** con decisiones o fixes relevantes → proponer archivar el resumen como `sesion-claude` en `raw/[proyecto]/sesion-YYYY-MM-DD.md`.
- Se define una **nueva entidad** (cliente nuevo, stack nuevo, persona nueva del equipo) → crear `wiki/entidades/[nombre].md`.
- Se descubre un **concepto/patrón reutilizable** (técnica de BANT, pattern de parsing LLM, bug recurrente) → `wiki/conceptos/[nombre].md`.

NO ingerir a la wiki:
- Errores efímeros (eso va a `memory/debug-log.md`).
- Estado de sesión en curso (eso va a `ai.context.json` o `memory/ESTADO_ACTUAL`).
- Tokens, secrets, credenciales (JAMÁS en la wiki — son datos sensibles).

### Regla de consulta

Antes de responder preguntas del usuario sobre stack, cliente, decisiones pasadas o integraciones, **considerá consultar la wiki**:
1. Leé `PROYECTO ARNALDO OBSIDIAN/index.md`.
2. Si hay una página relevante, leela antes de responder.
3. Citá páginas con `[[wiki/conceptos/X]]` o `[[wiki/entidades/Y]]`.

### Etiquetado obligatorio

Cada página de la wiki DEBE tener `proyecto:` en frontmatter (`arnaldo`/`robert`/`mica`/`compartido`/`global`). Sin esta etiqueta la página es inválida — corregirla al detectarla.

### Relación con `memory/`

| Uso | `memory/` | Wiki Obsidian |
|-----|-----------|---------------|
| Estado en vivo (sesión actual, TODOs, bugs del día) | ✅ | ❌ |
| Convenciones ya decididas, reglas irrompibles | ✅ (feedback_*) | ✅ (conceptos/) |
| Brief de clientes, transcripciones, PDFs | ❌ | ✅ (raw/) |
| Infraestructura (URLs, UUIDs) | ✅ (infraestructura.md) | ✅ (conceptos/matriz-infraestructura) |
| Exploraciones/comparaciones guardadas | ❌ | ✅ (sintesis/) |

**Principio**: `memory/` es memoria **operativa** (cambia frecuentemente); la Wiki es memoria **de conocimiento** (acumula para siempre).

---

## 6. Skills del Proyecto

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
