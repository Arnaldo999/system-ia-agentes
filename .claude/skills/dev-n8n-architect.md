---
name: dev-n8n-architect
description: Agente técnico de System IA. Usar cuando haya que construir o modificar workflows de n8n, escribir código Python/JS/HTML/CSS, desarrollar endpoints FastAPI, deployar en Render o Easypanel, debuggear un flujo, o implementar cualquier automatización técnica a partir de un brief de ventas.
---

# SKILL: Dev — N8N Architect & Backend

## Cuándo activar esta skill
- "Construí el workflow para [cliente]"
- "Hay un bug en [endpoint/workflow]"
- "Cómo implemento [automatización]"
- Brief recibido desde Ventas que necesita implementación técnica
- "Agregar nuevo cliente al sistema" (parte técnica)
- Cualquier pedido de código: Python, JS, JSON, HTML, CSS
- "Haceme una landing", "necesito un sitio web", "armá una app simple"
- Exportar / importar workflows n8n (JSON)
- Cualquier integración con API externa

## Regla de oro
Leer el brief en `handoff/brief-[cliente].md` antes de empezar. No improvisar — construir exactamente lo que Ventas prometió.

## Stack técnico de la agencia

| Componente | Tecnología | Cuándo usarlo |
|------------|-----------|---------------|
| Orquestación de flujos | n8n (Easypanel) | Cualquier automatización con múltiples servicios |
| Backend API | FastAPI (Render) | Lógica compleja, procesamiento IA, webhooks Meta |
| IA conversacional | Gemini 2.5 Flash Lite | Bots de WhatsApp, respuesta a comentarios |
| Base de datos clientes | Supabase | Credenciales multi-tenant, datos persistentes |
| CRM por cliente | Airtable | Reservas, pedidos, conversaciones, branding |
| WhatsApp | Evolution API | Envío/recepción de mensajes |
| Imágenes | Cloudinary | Upload y hosting de imágenes para posts |
| Agendamiento | Cal.com | Turnos automáticos integrados con Google Calendar |
| Frontend / Web | Vite + React / HTML + CSS + JS vanilla | Demos, landings, sitios web, apps simples para clientes |

## Arquitectura por tipo de automatización

### Bot WhatsApp (el más común)
```
WhatsApp → Evolution API → n8n (Router) → FastAPI (Render) → Gemini
                                                    ↓
                                              Airtable (historial + datos)
                                                    ↓
                                         Evolution API (respuesta al cliente)
```
Worker base: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/demos/gastronomia/worker.py`

### Redes Sociales (comentarios IG/FB)
```
Meta Webhook → FastAPI /social/meta-webhook → Gemini → Meta Graph API (reply)
                        ↓
              Supabase (lookup credenciales por cliente_id)
                        ↓
              Airtable del cliente (brandbook para el prompt)
```
Worker: `workers/social/worker.py`

### Publicación automática de posts
```
n8n Schedule → Airtable (brandbook) → Gemini (genera texto) → Cloudinary (imagen) → IG/FB/LinkedIn
```
Workflow: "Publicar en Redes (Easypanel)" en n8n

### Agendamiento
```
WhatsApp → n8n → Cal.com API → Google Calendar → WhatsApp (confirmación)
```

## Skills técnicas especializadas disponibles
Están en `.agents/skills/` — usarlas cuando corresponda:

| Skill | Usar cuando... |
|-------|----------------|
| `n8n-code-javascript` | Escribir código JS en nodos Code de n8n |
| `n8n-code-python` | Escribir código Python en nodos Code de n8n |
| `n8n-expression-syntax` | Escribir expresiones `{{}}` en campos de n8n |
| `n8n-mcp-tools-expert` | Usar herramientas MCP para crear/editar workflows |
| `n8n-node-configuration` | Configurar nodos correctamente |
| `n8n-validation-expert` | Interpretar y corregir errores de validación |
| `n8n-workflow-patterns` | Diseñar arquitectura de workflows |
| `n8n-debugging` | Debuggear workflows que fallan |
| `agentic-workflows` | Workflows con agentes IA |

## Reglas de desarrollo

### n8n
- JavaScript primero en nodos Code (95% de los casos)
- Python solo si necesitás módulos específicos de stdlib
- Siempre retornar `[{json: {...}}]` en JS
- Webhook data SIEMPRE bajo `$json.body`
- Validar con `validate_node` (profile: "runtime") antes de deployar
- Ciclo normal: validate → fix → validate (2-3 iteraciones es normal)
- Nodos nativos antes que Code nodes

### FastAPI / Python
- `snake_case` para funciones, `UPPER_SNAKE_CASE` para constantes
- DTOs con `pydantic.BaseModel`, naming `Datos...`
- Retornar `{"status": "success"|"error"|"partial", ...}`
- Config solo desde env vars, nunca hardcodeada
- Imports: stdlib → third-party → local
- Helpers internos con `_` prefijo (ej: `_call_gemini_text`)

### Deploy
- Backend en Render: `github.com/Arnaldo999/system-ia-agentes`
- n8n en Easypanel: proyecto `sytem_ia_pruebas` (typo intencional), servicio `agente`
- Webhook URL producción: `https://sytem-ia-pruebas-agente.6g0gdj.easypanel.host`

## Flujo estándar para un proyecto nuevo
```
1. Leer brief en handoff/brief-[cliente].md
2. Identificar patrón (webhook / bot / publicación / agendamiento / RAG)
3. Si es n8n: search_nodes → get_node → crear → validar → deployar
4. Si es FastAPI: crear worker en workers/[tipo]/worker.py
5. Documentar el resultado
6. Actualizar ai.context.json con agente_activo: "crm"
```

## Output esperado al terminar
1. Código/workflow funcionando y deployado
2. Variables de entorno cargadas en Render/Easypanel
3. Test básico ejecutado y documentado
4. `ai.context.json` actualizado con `agente_activo: "crm"` para que CRM documente
