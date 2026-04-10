# MIGRACION_ESTRUCTURA.md
Reorganización del workspace — 2026-04-10

## Tabla origen → destino

| Origen (raíz) | Destino nuevo | Estado |
|---|---|---|
| `AGENTS.md` | `00_GOBERNANZA_GLOBAL/AGENTS.md` | COPIADO |
| `AI_START.md` | `00_GOBERNANZA_GLOBAL/AI_START.md` | COPIADO |
| `CLAUDE.md` | `00_GOBERNANZA_GLOBAL/CLAUDE.md` (+ original en raíz actualizado) | COPIADO |
| `ai/core/` | `00_GOBERNANZA_GLOBAL/memory-global/` | COPIADO |
| `.agents/skills/` | `00_GOBERNANZA_GLOBAL/skills/shared/` | COPIADO |
| `.claude/hooks/` | `00_GOBERNANZA_GLOBAL/hooks/` | COPIADO |
| `.claude/agents/` | `00_GOBERNANZA_GLOBAL/agents/` | COPIADO |
| `02_DEV_N8N_ARCHITECT/backends/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/` | COPIADO |
| `02_DEV_N8N_ARCHITECT/workflows/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/` | COPIADO |
| `02_DEV_N8N_ARCHITECT/ai-sandbox/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/workflows/ai-sandbox/` | COPIADO |
| `DEMOS/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/` | COPIADO |
| `01_VENTAS_CONSULTIVO/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/ventas-consultivo/` | COPIADO |
| `02_DEV_N8N_ARCHITECT/memory/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/memory/` | COPIADO |
| `02_DEV_N8N_ARCHITECT/docs/` | `01_PROYECTOS/01_ARNALDO_AGENCIA/docs/` | COPIADO |
| `PROYECTO MICAELA/` | `01_PROYECTOS/02_SYSTEM_IA_MICAELA/clientes/` | COPIADO |
| `PROYECTO AGENCIA ROBERT-ARNALDO AYALA/` | `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/` | COPIADO |
| `scripts/` | `02_OPERACION_COMPARTIDA/scripts/` | COPIADO |
| `tools/` | `02_OPERACION_COMPARTIDA/tools/` | COPIADO |
| `tests/` | `02_OPERACION_COMPARTIDA/tests/` | COPIADO |
| `execution/` | `02_OPERACION_COMPARTIDA/execution/` | COPIADO |
| `handoff/` | `02_OPERACION_COMPARTIDA/handoff/` | COPIADO |
| `logs/` | `02_OPERACION_COMPARTIDA/logs/` | COPIADO |
| `archive/` | `99_ARCHIVO/archive/` | COPIADO |

## Carpetas que NO existían en origen (destinos vacíos creados)

| Carpeta destino | Motivo |
|---|---|
| `01_PROYECTOS/01_ARNALDO_AGENCIA/frontend/` | No había carpeta `frontend/` en origen |
| `01_PROYECTOS/02_SYSTEM_IA_MICAELA/{backends,workflows,frontend,demos,memory,docs}/` | Proyecto no tenía estructura de carpetas aún |
| `01_PROYECTOS/03_LOVBOT_ROBERT/{backends,workflows,frontend,demos,memory,docs}/` | Idem |
| `00_GOBERNANZA_GLOBAL/policies/` | Nueva, sin origen |
| `00_GOBERNANZA_GLOBAL/templates/` | Nueva, sin origen |

## Notas sobre carpetas en 02_DEV_N8N_ARCHITECT

La carpeta `02_DEV_N8N_ARCHITECT/backends/` contiene el repo git `system-ia-agentes/`.
**Solo se copió** el contenedor — el repo git interno NO fue tocado ni movido.
El repo sigue operativo en su ubicación original para git/Coolify.

La carpeta `02_DEV_N8N_ARCHITECT/` también tenía subdirectorios no mapeados explícitamente:
- `deploy-scripts/` — no incluido en la migración (sin destino definido)
- `fastapi-modules/` — no incluido en la migración (sin destino definido)
- `.agents/skills/` — carpeta interna del subproyecto, no migrada

## Conflictos encontrados

Ninguno. Todos los destinos estaban vacíos al momento de la copia.

## Pendientes manuales (el usuario debe ejecutar cuando confirme)

1. **Borrar carpetas originales** una vez validado que las copias están correctas:
   - `02_DEV_N8N_ARCHITECT/` (conservar el repo git `system-ia-agentes/` en su lugar)
   - `DEMOS/`
   - `01_VENTAS_CONSULTIVO/`
   - `PROYECTO MICAELA/`
   - `PROYECTO AGENCIA ROBERT-ARNALDO AYALA/`
   - `scripts/`
   - `tools/`
   - `tests/`
   - `execution/`
   - `handoff/`
   - `logs/`
   - `archive/`

2. **Actualizar referencias en otros archivos** que apunten a rutas antiguas:
   - `ai.context.json` — revisar si tiene rutas hardcodeadas
   - `memory/infraestructura.md` — puede tener rutas locales
   - Scripts en `execution/` — pueden tener paths relativos

3. **Decidir qué hacer con** carpetas no mapeadas:
   - `02_DEV_N8N_ARCHITECT/deploy-scripts/`
   - `02_DEV_N8N_ARCHITECT/fastapi-modules/`
   - `docs/` (raíz — sin destino asignado)
   - `PROYECTO PROPIO ARNALDO AUTOMATIZACION/` (no estaba en el plan)
   - `LOGO/` (raíz)
   - `ai/claude/`, `ai/gemini/` (solo `ai/core/` fue migrado)
   - `memory/` (raíz — sin mover, usada por CLAUDE.md)
   - `modify_form.py`, `update_html.py`, `vercel.json`, `get-docker.sh` (raíz — scripts sueltos)
   - `skills-lock.json` (raíz)

## Riesgos detectados

- **Repo git `system-ia-agentes`**: está dentro de `02_DEV_N8N_ARCHITECT/backends/`. Al copiar con `cp -r`, el contenido fue duplicado pero el `.git/` interno también se copió. Si en el futuro se borra la carpeta original, la copia en `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/` quedará como repo independiente (sin remote configurado igual). Recomendación: para trabajar con el repo git, seguir usando la ruta original hasta confirmar que la copia es correcta y re-clonar si es necesario.
- **Directives en raíz**: se mantienen en raíz por decisión del plan. CLAUDE.md ya refleja esto.
- **Memory raíz**: no fue movida (correctamente). CLAUDE.md sigue apuntando a `memory/` sin prefijo.
- **`.claude/skills/`**: no migrado a gobernanza (solo `.claude/hooks/` y `.claude/agents/`). Las skills del proyecto siguen accesibles en su lugar original.
