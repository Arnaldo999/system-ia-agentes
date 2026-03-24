# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 1. Rol Activo — Leer Primero

**Al iniciar cualquier sesión, lee `ai.context.json` para saber qué agente debes encarnar:**

| `agente_activo` | Rol | AGENT.md a leer |
|-----------------|-----|-----------------|
| `orquestador` | Gerente / coordinador de misión | `.agents/01-orquestador/AGENT.md` |
| `ventas` | Experto en cierre y propuestas | `.agents/02-ventas/AGENT.md` o `01_VENTAS_CONSULTIVO/AGENT.md` |
| `dev` | Ingeniero n8n + FastAPI | `.agents/03-dev/AGENT.md` o `02_DEV_N8N_ARCHITECT/AGENT.md` |
| `crm` | Analista de memoria y calidad | `.agents/04-crm/AGENT.md` o `03_CRM_ANALYST/AGENT.md` |

Actualiza `ai.context.json` al completar cada hito importante.

**Trigger especial**: Si el pedido menciona `nuevo cliente`, `redes sociales`, `instagram`, `facebook` o `comentarios` → leer `memory/nuevo-cliente-redes-sociales.md` antes de responder.

---

## 2. Arquitectura del Proyecto

Este proyecto es Mission Control de **Agencia System IA** (automatizaciones para clientes). Combina:

| Componente | Tech | Ubicación |
|------------|------|-----------|
| Respuesta automática a comentarios IG/FB | FastAPI | `02_DEV_N8N_ARCHITECT/backends/system-ia-agentes/workers/social/worker.py` |
| Publicación automática de posts | n8n | Workflow "Publicar en Redes (Easypanel)" |
| Webhook Meta | FastAPI | `GET/POST /social/meta-webhook` |
| Frontend demo | Vite + React | `02_DEV_N8N_ARCHITECT/` (carpeta `electronica-web`) |
| Sandbox CrewAI | Python | `02_DEV_N8N_ARCHITECT/ai-sandbox/pruebas_crewai/` |

**Regla crítica**: La respuesta a comentarios de IG/FB es **FastAPI**, no n8n. No duplicar en workflows.

**Producción**: Easypanel — proyecto `sytem_ia_pruebas` (typo intencional), servicio `agente`
**Repo backend**: `github.com/Arnaldo999/system-ia-agentes`

### Protocolo de Handoff entre Agentes

El archivo `ai.context.json` es el tablero de estado compartido. El flujo de handoff:
1. Orquestador escribe `ai.context.json` con `agente_activo` + contexto de la tarea
2. El agente activo lee el JSON, ejecuta su tarea, escribe su output en el JSON
3. Cambia `agente_activo` al siguiente agente antes de terminar
4. CRM documenta el resultado final en `memory/`

Los handoffs activos se registran en `handoff/` (ejemplo: `handoff/brief-agencia-automotriz-vip.md`).

---

## 3. Comandos

### Backend FastAPI (sistema principal)
```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload  # desde system-ia-agentes/
python -m py_compile main.py                           # validación rápida
pytest tests/path/test_file.py::test_case_name -q     # test único
docker build -t system-ia-agentes . && docker run --rm -p 8000:8000 --env-file .env system-ia-agentes
```

### Frontend (electronica-web)
```bash
npm install && npm run dev
npm run build && npm run preview
```

### Sandbox CrewAI
```bash
cd 02_DEV_N8N_ARCHITECT/ai-sandbox/pruebas_crewai/
source venv/bin/activate
python test_basico.py           # validación rápida
python demo_pro_restaurante.py  # demo completo
```

### Disparar agente en modo no-interactivo
```bash
claude -p "Lee ai.context.json. Tu rol es [agente]. Tarea: [descripción]."
```

---

## 4. Flujo n8n (Agente Dev)

```
search_nodes → get_node → n8n_create_workflow → validate_node → fix → validate_workflow → activateWorkflow
```

Validar siempre con `profile: "runtime"` antes de deployar. 2-3 iteraciones de validate→fix son normales.

### Patrones de código n8n

**JS estándar:**
```javascript
const items = $input.all();
return items.map(item => ({ json: { ...item.json, processed: true } }));
```

**Webhook data**: siempre bajo `$json.body`, nunca `$json` directamente.

**Code nodes**: JavaScript por defecto. Python solo si necesitás módulos de stdlib específicos.

---

## 5. Convenciones de Código (FastAPI/Python)

- `snake_case` para funciones/variables, `UPPER_SNAKE_CASE` para constantes, `Datos...` para DTOs Pydantic
- Retornar JSON estructurado con `status`: `success` | `error` | `partial`
- Imports: stdlib → third-party → local
- Helpers internos con `_` prefijo (ej: `_call_gemini_text`)
- Config solo desde env vars. Nunca hardcodear tokens/IDs.

---

## 6. Memoria Operativa

`memory/` contiene casos de uso documentados y ya probados. **No reinventar — seguir el proceso documentado.**

Archivos clave:
- `memory/nuevo-cliente-redes-sociales.md` — proceso completo onboarding cliente social
- `memory/infraestructura.md` — estado de la infraestructura
- `memory/guia-ventas-micaela.md` — guía comercial
- `ai/core/` — reglas compartidas para todos los modelos LLM
