# Plan: Bot voz inmobiliaria Robert con ElevenLabs + Twilio

**Creado**: 2026-04-27
**Estado**: Implementado
**Proyecto**: robert
**Pedido**: Construir agente de voz independiente del bot WhatsApp de Robert que reuse `robert_crm` (Airtable + futuro Postgres), Cal.com y lógica BANT, listo para enchufar cuando Robert pague ElevenLabs y compre número Twilio AR.

---

## Descripción general

### Qué logra este plan

Entregar un **agente de voz inmobiliaria production-ready** que conteste llamadas telefónicas (futuro número Twilio AR) y resuelva consultas de búsqueda de propiedades, agendamiento de visitas y captura de leads, **reutilizando 100% la capa de datos** del bot WhatsApp existente de Robert. El cerebro conversacional vive en ElevenLabs (Gemini 2.5 Flash + voz español); el backend FastAPI expone endpoints-tool que ElevenLabs consume. Worker físicamente independiente del worker WhatsApp pero compartiendo módulos `shared/`.

### Por qué importa ahora

1. **Diferenciador comercial**: agente de voz es uno de los servicios más demandados actualmente y muy pocos lo ofrecen integrado al CRM.
2. **Costo marginal bajo**: reusamos Postgres `lovbot_crm_modelo` + Cal.com + catálogo de propiedades existente. Solo agregamos ElevenLabs (USD 22/mes) + Twilio (~USD 3/mes) que asume Robert.
3. **Ventana de tiempo**: Robert está esperando aprobación final de Meta. En paralelo podemos construir esto sin bloquearnos por dependencias externas.
4. **Reusable como producto**: el patrón sirve para Maicol, Lau, Cesar Posada y futuros clientes — primer cliente de voz arma el playbook para todos.

---

## Estado actual

### Estructura existente relevante

**Worker WhatsApp Robert (LIVE)**:
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/lovbot/robert_inmobiliaria/worker.py` — bot WhatsApp Meta Graph
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/lovbot/robert_inmobiliaria/db_postgres.py` — capa BD
- Usa Postgres `lovbot_crm_modelo` (`ROBERT_AIRTABLE_BASE`) con tablas `Props`, `Clientes`, `Activos`
- Cal.com integrado vía `INMO_DEMO_CAL_API_KEY` + `INMO_DEMO_CAL_EVENT_ID` + `INMO_DEMO_CAL_TIMEZONE`
- LLM: Gemini (`GEMINI_API_KEY` compartida) + OpenAI Robert (`LOVBOT_OPENAI_API_KEY`)
- Provider: Meta Graph API (`META_ACCESS_TOKEN` + `META_PHONE_NUMBER_ID`)

**Demo inmobiliaria**:
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/demos/inmobiliaria/worker.py` — sandbox compartido
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/demos/inmobiliaria/db_postgres.py`

**Módulos shared existentes** (`workers/shared/`):
- `message_buffer.py` — debounce 8s Redis
- `image_describer.py` — análisis imagen Meta
- `typing_indicator.py` — indicador "escribiendo" Meta
- `message_splitter.py` — splitter saludo/mensaje

**Infraestructura Robert**:
- Coolify Hetzner — `agentes.lovbot.ai/*`
- BD Postgres `lovbot_crm_modelo` en Coolify Hetzner (host `5.161.235.99`, container `lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc`)
- Cal.com **compartido de Arnaldo** (servicio compartido — Robert lo usa via `INMO_DEMO_CAL_*`)
- Cuenta ElevenLabs trabajada en workspace **ElevenCreative** (Arnaldo) durante dev

### Brechas o problemas que se abordan

1. **No hay módulos `shared/` para BANT, queries de catálogo y Cal.com**: la lógica BANT vive duplicada dentro de cada worker. Para reusar entre WhatsApp y Voz hay que extraerla.
2. **No existe worker de voz**: ningún cliente del ecosistema tiene canal voz hoy.
3. **No hay integración ElevenLabs documentada**: primera vez que tocamos esta API en el ecosistema.
4. **No hay matching cross-channel**: si alguien habla por WhatsApp y después llama por voz, el sistema no lo reconoce como mismo lead.

### Playbook/concepto relacionado

**No existe playbook de bot voz aún.** Este plan crea el primer caso del ecosistema y debe terminar generando:
- `wiki/playbooks/worker-voz-elevenlabs.md` (nuevo)
- `wiki/conceptos/elevenlabs-conversational-ai.md` (nuevo)

Playbooks existentes que aplican parcialmente:
- `wiki/playbooks/worker-whatsapp-bot.md` — patrón general de worker FastAPI + BANT
- `wiki/conceptos/persona-unica-crm.md` — modelo de leads que se respeta cross-channel

---

## Cambios propuestos

### Resumen de cambios

- Refactor `workers/shared/` agregando módulos compartidos BANT + queries catálogo + Cal.com
- Crear worker demo voz en `workers/demos/inmobiliaria-voz/` (sandbox)
- Crear worker cliente voz en `workers/clientes/lovbot/robert_voz/` (cuando demo esté validado)
- Configurar agente ElevenLabs en cuenta ElevenCreative (Arnaldo) con 5 custom tools
- Endpoints `/voz/*` deployados en `agentes.lovbot.ai` desde día 1
- Documentación de handoff a Robert (export JSON + checklist Twilio + setup minutos)
- Crear playbook + concepto wiki

### Archivos nuevos a crear

| Ruta | Propósito |
|------|-----------|
| `workers/shared/bant.py` | Lógica BANT reutilizable (extracción budget/authority/need/timeline desde transcripción) |
| `workers/shared/catalog.py` | Búsqueda propiedades en Postgres `lovbot_crm_modelo` con filtros (tipo, zona, precio, dormitorios) — wrapper sobre `db_postgres.buscar_propiedades` |
| `workers/shared/calcom_client.py` | Wrapper Cal.com (disponibilidad, agendar, cancelar) reusable |
| `workers/shared/lead_matcher.py` | Match cross-channel: por `caller_id` (voz) o `wa_id` (whatsapp) busca lead en Airtable |
| `workers/demos/inmobiliaria-voz/__init__.py` | Init demo voz |
| `workers/demos/inmobiliaria-voz/worker.py` | Worker FastAPI con endpoints `/voz/*` (sandbox) |
| `workers/demos/inmobiliaria-voz/README.md` | Cómo testear desde ElevenLabs "Test AI agent" |
| `workers/clientes/lovbot/robert_voz/__init__.py` | Init worker cliente Robert |
| `workers/clientes/lovbot/robert_voz/worker.py` | Worker voz Robert (clonado del demo después de validación) |
| `02_OPERACION_COMPARTIDA/handoff/elevenlabs-agent-robert.json` | Export del agente ElevenLabs configurado (para import en cuenta Robert) |
| `02_OPERACION_COMPARTIDA/handoff/handoff-voz-robert.md` | Checklist paso a paso para Robert (pagar, comprar Twilio, importar JSON, conectar) |
| `PROYECTO ARNALDO OBSIDIAN/wiki/playbooks/worker-voz-elevenlabs.md` | Playbook para futuros bots voz |
| `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/elevenlabs-conversational-ai.md` | Concepto wiki ElevenLabs |
| `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/twilio-numeros-telefonicos.md` | Concepto wiki Twilio para AR/MX |

### Archivos a modificar

| Ruta | Cambios |
|------|---------|
| `workers/clientes/lovbot/robert_inmobiliaria/worker.py` | Refactor: importar BANT desde `shared/bant.py` (eliminar duplicación). NO cambiar comportamiento del bot WhatsApp. |
| `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py` | Agregar `app.include_router()` para demo voz y robert_voz |
| `memory/ESTADO_ACTUAL.md` | Reflejar nueva feature al terminar |
| `CLAUDE.md` raíz | Sección "Workers monorepo" — agregar canal voz |
| `MEMORY.md` (auto-memory) | Agregar entrada `project_robert_voz_2026.md` |

### Archivos a eliminar

Ninguno en esta fase. Se preserva worker WhatsApp intacto.

### Cambios en infraestructura externa

**ElevenLabs (cuenta ElevenCreative Arnaldo, dev)**:
- Crear nuevo agente "Robert Inmobiliaria — Voz" con onboarding `Business Agent` → `Real Estate` → `Scheduling`
- Configurar 5 custom tools apuntando a `https://agentes.lovbot.ai/voz/*`
- Subir knowledge base inicial (FAQ inmobiliaria + planes de servicios Robert)
- Seleccionar voz español acento argentino/mexicano (a definir en sesión)
- Configurar `system_time_utc`, `timezone` `America/Argentina/Buenos_Aires`
- Habilitar dynamic variable `caller_id` en custom tools

**Coolify Hetzner Robert** (`agentes.lovbot.ai`):
- Sin servicio nuevo — usa el mismo backend FastAPI que ya corre el WhatsApp worker
- Env vars adicionales (todas con prefijo `LOVBOT_`):
  - `LOVBOT_ELEVENLABS_API_KEY` (en dev: cuenta Arnaldo; en prod Robert: la suya)
  - `LOVBOT_ELEVENLABS_AGENT_ID`
  - `LOVBOT_ELEVENLABS_WEBHOOK_SECRET` (firma HMAC opcional)

**Postgres `lovbot_crm_modelo`**:
- NO se modifica schema. Reusa `Props`, `Clientes`, `Activos` existentes.
- (Opcional fase 2): agregar campo `canal_origen` a `Clientes` con valores `whatsapp`/`voz`/`web` para reportería

**Twilio**:
- En fase de dev: NADA. Se valida todo con widget web ElevenLabs.
- En handoff a Robert: Robert compra número AR siguiendo checklist `handoff-voz-robert.md`

**Cal.com**:
- Sin cambios. Reusa la misma cuenta Robert con `INMO_DEMO_CAL_API_KEY` que ya usa WhatsApp.

---

## Decisiones de diseño

### Decisiones clave tomadas

1. **Worker independiente, capa de datos compartida**: voz worker NO toca código del WhatsApp worker. Comparten módulos `shared/`. Justificación: si voz se rompe, WhatsApp sigue. Despliegue independiente.

2. **ElevenLabs cuenta Arnaldo en dev, transferencia por export JSON al final**: vos construís en ElevenCreative, validás todo, exportás JSON del agente y lo importás en cuenta de Robert cuando él pague. Justificación: Robert no paga hasta que vea el agente funcionando. Si construyéramos directo en cuenta Robert, él paga desde día 1 sin ver valor.

3. **Tool `buscar_propiedad` en vivo a Airtable, no PDF en knowledge base**: el catálogo cambia seguido. Aceptamos +500ms de latencia por query a cambio de datos siempre actualizados. Justificación: agente que cita propiedad ya vendida es peor que uno que tarda 1s más.

4. **Match cross-channel por `caller_id` (Twilio) y `wa_id` (Meta)**: ambos canales buscan lead por número de teléfono normalizado en `Clientes` Airtable. Si existe, cargan contexto BANT previo. Justificación: diferencial de producto fuerte; cero costo extra (1 query).

5. **System prompt en inglés, respuestas en español**: best practice ElevenLabs (mejora precisión de tool calling). Mismo patrón que demo de Kevin.

6. **LLM dentro de ElevenLabs = Gemini 2.5 Flash**: validado por Kevin como el mejor para tool calling + deletreo de emails. NO usar GPT-5/Claude en el agente. Justificación: latencia voz <500ms es crítica.

7. **Webhook URL `agentes.lovbot.ai/voz/*` desde día 1**: nunca pasar por dominio Arnaldo. Justificación: cuando se transfiera a Robert, no hay que reconfigurar URLs en ElevenLabs (solo cambia API key).

8. **Demo→Producción**: primero `workers/demos/inmobiliaria-voz/`, después `workers/clientes/lovbot/robert_voz/`. Justificación: REGLA Demo→Producción del CLAUDE.md.

9. **No comprar Twilio en dev**: validamos todo con widget web ElevenLabs ("Test AI agent"). Twilio recién al final cuando Robert lo compre. Justificación: ahorra USD 5-10 + KYC AR de 3-10 días.

### Alternativas consideradas

- **Construir directo en cuenta ElevenLabs Robert**: rechazado. Robert paga sin haber visto producto = mala UX comercial.
- **Twilio number en dev a nombre de Arnaldo**: rechazado. KYC argentino tarda y migrar el número a Robert después es papeleo Twilio innecesario.
- **Embeber catálogo en knowledge base ElevenLabs (PDF estático)**: rechazado. Catálogo cambia seguido.
- **Bot voz mete el lead directamente en Airtable sin pasar por backend Robert**: rechazado. Salta lógica de scoring + notificación al asesor + matching cross-channel.
- **Compartir worker WhatsApp para que también atienda voz**: rechazado. Acopla canales, deploys conjuntos riesgosos, latencia voz no tolera lo que tolera WhatsApp.
- **Usar Cal.com de Arnaldo (compartido)**: rechazado. Robert tiene Cal.com propio que ya usa el WhatsApp. Mantener consistencia para que las visitas no se dupliquen entre canales.

### Preguntas abiertas (resueltas 2026-04-27)

- [x] **Voz seleccionada**: `16UXUey4OpoKrC9IiRNt` (decidida por Arnaldo)
- [x] **Tono del agente**: profesional pero cálido, semi-formal argentino (similar al WhatsApp existente de Robert que ya está calibrado)
- [x] **Knowledge base inicial**: Claude arma FAQ desde el demo existente (worker `robert_inmobiliaria` + variables `INMO_DEMO_*`)
- [x] **Cuenta ElevenLabs Robert**: se crea en handoff. Dev en cuenta ElevenCreative de Arnaldo, export JSON al final.
- [x] **Refactor primero o voz primero**: refactor `shared/` PRIMERO (camino limpio, evita duplicación de BANT)

---

## Tareas paso a paso

Ejecutar en este orden durante `/implementar`.

### Paso 1 — Refactor a `shared/` (módulos compartidos BANT + Catalog + Cal.com)

Extraer lógica reutilizable del worker WhatsApp Robert a módulos `shared/` para que voz worker la consuma sin duplicar.

**Acciones**:
- Crear `workers/shared/bant.py` con funciones puras: `extract_bant_signals(message: str, history: list) -> dict`, `score_lead(bant_data: dict) -> str`, `should_transfer_to_human(bant_data: dict) -> bool`
- Crear `workers/shared/catalog.py` con: `search_properties(filters: dict) -> list`, `get_property_detail(prop_id: str) -> dict`
- Crear `workers/shared/calcom_client.py` con: `get_availability(date_iso: str) -> list[slots]`, `book_slot(slot: str, lead: dict) -> dict`, `cancel_booking(booking_id: str) -> bool`
- Crear `workers/shared/lead_matcher.py` con: `find_lead_by_phone(phone: str) -> dict | None`, `upsert_lead(phone: str, channel: str, data: dict) -> dict`
- Modificar `workers/clientes/lovbot/robert_inmobiliaria/worker.py` para importar desde `shared/` (NO romper comportamiento WhatsApp)
- Test que bot WhatsApp Robert sigue contestando OK después del refactor

**Archivos afectados**:
- `workers/shared/bant.py` (nuevo)
- `workers/shared/catalog.py` (nuevo)
- `workers/shared/calcom_client.py` (nuevo)
- `workers/shared/lead_matcher.py` (nuevo)
- `workers/clientes/lovbot/robert_inmobiliaria/worker.py` (modificación quirúrgica)

**Validación**:
- Bot WhatsApp Robert responde a mensaje de prueba igual que antes (smoke test manual desde número de prueba)
- `python -m py_compile workers/shared/*.py` pasa sin errores
- Logs Coolify Robert sin errores tras redeploy

---

### Paso 2 — Crear worker demo voz (`workers/demos/inmobiliaria-voz/`)

Implementar endpoints `/voz/*` en sandbox antes de tocar carpeta `clientes/`.

**Acciones**:
- `cp workers/demos/inmobiliaria/worker.py workers/demos/inmobiliaria-voz/worker.py` y limpiar (es punto de partida estructural)
- Implementar 5 endpoints FastAPI:
  - `POST /voz/disponibilidad` — query Cal.com slots disponibles
  - `POST /voz/agendar-visita` — book slot + crear/actualizar lead Airtable
  - `POST /voz/buscar-propiedad` — search en Airtable Props con filtros
  - `POST /voz/enviar-ficha` — mail con ficha de propiedad (reusar Mailgun/SendGrid si existe, sino skip fase 2)
  - `POST /voz/cancelar-visita` — cancelar booking Cal.com
- Cada endpoint:
  - Recibe payload de ElevenLabs custom tool (query params + body)
  - Hace lookup `lead_matcher.find_lead_by_phone(caller_id)` al inicio
  - Llama `shared/*` correspondiente
  - Retorna JSON `{"success": bool, "data": {...}, "message": "texto que el agente dirá"}`
- Registrar router en `main.py`: `app.include_router(inmobiliaria_voz_router, prefix="/demos/voz/inmobiliaria")` (en dev) y dejar comentario para futuro `prefix="/voz"` cuando vaya a `clientes/`
- README.md con curl examples para test directo

**Archivos afectados**:
- `workers/demos/inmobiliaria-voz/__init__.py`
- `workers/demos/inmobiliaria-voz/worker.py`
- `workers/demos/inmobiliaria-voz/README.md`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`

**Validación**:
- `curl -X POST localhost:8000/demos/voz/inmobiliaria/disponibilidad -d '{"fecha":"2026-04-28"}'` retorna slots Cal.com
- `curl POST .../buscar-propiedad -d '{"tipo":"casa","zona":"posadas"}'` retorna props Airtable
- Tests manuales todos los endpoints

---

### Paso 3 — Deploy demo voz a Coolify Hetzner

Subir endpoints a producción para que ElevenLabs los pueda consumir desde el "Test AI agent".

**Acciones**:
- Commit + push (master:main)
- Trigger redeploy backend en Coolify Hetzner Robert (mismo service que ya corre WhatsApp)
- Verificar `agentes.lovbot.ai/demos/voz/inmobiliaria/disponibilidad` responde 200
- Verificar logs Coolify sin errores
- Configurar CORS si necesario (ElevenLabs llama desde su infra)

**Archivos afectados**: ninguno (solo deploy)

**Validación**:
- `curl https://agentes.lovbot.ai/demos/voz/inmobiliaria/disponibilidad -X POST -d '...'` → 200 OK
- `last_online_at` Coolify > timestamp del commit

---

### Paso 4 — Configurar agente en ElevenLabs (cuenta Arnaldo)

Crear el agente conversacional siguiendo el flujo del video de Kevin.

**Acciones**:
- En `elevenlabs.io/app/agents` → New Agent → Business Agent → Real Estate → Scheduling
- Nombre: "Robert Inmobiliaria — Voz (Dev)"
- Idioma principal: Español. Additional languages: English (auto-detect ON)
- System prompt (en inglés) — basado en plantilla del video de Kevin adaptado a inmobiliaria + BANT. Incluir:
  - Identidad: "You are the voice assistant of Lovbot Inmobiliaria, helping clients find properties and schedule visits"
  - Tools disponibles (con descripciones específicas)
  - Reglas: deletreo letra por letra para emails, confirmar antes de agendar, BANT discovery natural
  - Knowledge base reference
  - Instrucción: respuestas en español, system prompt en inglés
- Knowledge base: subir 2 docs:
  - `faq-inmobiliaria-robert.md` (preguntas frecuentes operativa Robert)
  - `planes-y-servicios-robert.md` (tipos de propiedades + zonas + rangos de precio)
- LLM: **Gemini 2.5 Flash**
- Temperatura: 0.5
- Token limit: -1 (ilimitado)
- Voz: seleccionar español acento AR/MX (a decidir con Arnaldo escuchando samples)
- Configurar dynamic variables: `system_time_utc`, `timezone=America/Argentina/Buenos_Aires`
- Configurar 5 custom tools apuntando a `https://agentes.lovbot.ai/demos/voz/inmobiliaria/*`
  - Cada tool con response timeout 40s
  - Pre-tool speech: "Un momento, dame un segundo mientras lo verifico"
  - Body parameters incluyen `conversation_id` (dynamic), `caller_id` (dynamic), parámetros LLM-prompt (start, name, email, etc.)
- Configuraciones avanzadas:
  - Turn timeout: 7s
  - Silence call timeout: 60s
  - Max conversation: 600s

**Archivos afectados**: ninguno local, todo en dashboard ElevenLabs

**Validación**:
- "Test AI agent" en navegador → llamar y validar:
  - Saludo natural en español
  - Detecta intención de búsqueda → llama `buscar-propiedad`
  - Recibe email letra por letra correctamente
  - Verifica disponibilidad → llama `disponibilidad`
  - Agenda visita → llama `agendar-visita` y confirma
  - Backend Robert recibe los 3 webhooks con payload correcto

---

### Paso 5 — Iteración fina del system prompt + tools

Calibrar comportamiento del agente con tests reales.

**Acciones**:
- 10-15 conversaciones de prueba simuladas
- Casos a validar:
  - Cliente busca propiedad por zona → bot lista 3 opciones, ofrece fichas
  - Cliente pide visita → bot pide fecha/hora preferida + datos contacto + confirma
  - Cliente pregunta precio → bot consulta catálogo y responde
  - Cliente quiere hablar con humano → bot toma datos y notifica asesor (vía endpoint `/notificar-asesor` en backend si existe, sino fase 2)
  - Cliente da email mal deletreado → bot pide confirmación letra por letra
  - Cliente cuelga abruptamente → no se traba el agente
- Ajustar system prompt según hallazgos (en inglés)
- Ajustar descripciones de tools para mejorar tool-calling accuracy
- Documentar findings en `wiki/playbooks/worker-voz-elevenlabs.md`

**Archivos afectados**:
- System prompt ElevenLabs (UI)
- `wiki/playbooks/worker-voz-elevenlabs.md` (escribir paralelo a iteración)

**Validación**:
- 8/10 conversaciones de prueba terminan en éxito (búsqueda completa o agendamiento)
- Tool-calling accuracy >90%

---

### Paso 6 — Promover demo a `clientes/lovbot/robert_voz/`

Una vez validado el demo, copiar a carpeta cliente Robert siguiendo REGLA Demo→Producción.

**Acciones**:
- `cp -r workers/demos/inmobiliaria-voz/ workers/clientes/lovbot/robert_voz/`
- Adaptar constantes:
  - `CLIENTE_ID = "robert"`
  - `TENANT_SLUG = "robert-voz"`
  - `VERTICAL = "inmobiliaria"`
- Cambiar prefix del router en `main.py`: `prefix="/clientes/lovbot/robert/voz"`
- Modificar URLs de tools en ElevenLabs: de `/demos/voz/inmobiliaria/*` a `/clientes/lovbot/robert/voz/*`
- Redeploy Coolify
- Re-test desde "Test AI agent" para verificar que las URLs nuevas funcionan

**Archivos afectados**:
- `workers/clientes/lovbot/robert_voz/*`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`

**Validación**:
- Endpoints producción `agentes.lovbot.ai/clientes/lovbot/robert/voz/*` responden 200
- Test AI agent ElevenLabs sigue funcionando con URLs actualizadas

---

### Paso 7 — Export JSON del agente ElevenLabs + handoff doc

Empaquetar todo para que Robert pueda importarlo cuando pague.

**Acciones**:
- Desde dashboard ElevenLabs: Agente → "Export as JSON" → guardar
- Guardar en `02_OPERACION_COMPARTIDA/handoff/elevenlabs-agent-robert.json`
- Crear `02_OPERACION_COMPARTIDA/handoff/handoff-voz-robert.md` con:
  - Paso 1: Crear cuenta ElevenLabs (link + plan Creator USD 22/mes)
  - Paso 2: Comprar número Twilio AR (link + KYC requerido + selección con prefijo Posadas si disponible)
  - Paso 3: Conectar Twilio a ElevenLabs (settings exactos)
  - Paso 4: Importar JSON del agente
  - Paso 5: Actualizar `LOVBOT_ELEVENLABS_API_KEY` en Coolify Hetzner Robert (con la key de su cuenta)
  - Paso 6: Test final llamando al número Twilio
  - Costos esperados mensuales (USD 22 + ~USD 3-10 Twilio + minutos)
  - Troubleshooting: tools no responden, voz se corta, etc.

**Archivos afectados**:
- `02_OPERACION_COMPARTIDA/handoff/elevenlabs-agent-robert.json`
- `02_OPERACION_COMPARTIDA/handoff/handoff-voz-robert.md`

**Validación**:
- JSON tiene tools, system prompt, voz, knowledge base
- Doc handoff es ejecutable por Robert sin nuestro soporte (test mental: ¿podría seguirlo solo?)

---

### Paso 8 — Documentación wiki + memory

Cerrar el ciclo: lo aprendido va a wiki, estado en memory, regla de auto-memory si aplica.

**Acciones**:
- Crear `wiki/playbooks/worker-voz-elevenlabs.md` con:
  - Cuándo usar
  - Arquitectura estándar (mismo formato que `worker-whatsapp-bot.md`)
  - Stack por agencia
  - Pasos exactos clonando demo
  - Gotchas descubiertos durante implementación (deletreo email, latencia tools, timezone, etc.)
- Crear `wiki/conceptos/elevenlabs-conversational-ai.md` con:
  - Qué es ElevenLabs Agents
  - Modelos disponibles
  - Pricing
  - Custom tools format
  - Dynamic variables disponibles
  - Limitaciones
- Crear `wiki/conceptos/twilio-numeros-telefonicos.md` con:
  - Compra número AR (KYC requerido, 3-10 días)
  - Compra número MX (más rápido)
  - Costo
  - Conectar con ElevenLabs
- Crear `wiki/entidades/agente-voz-robert.md` con:
  - Producto, owner, stack, infra
  - Estado (LIVE / handoff pendiente)
- Actualizar `memory/ESTADO_ACTUAL.md` con la feature
- Crear auto-memory `project_robert_voz_2026.md` con:
  - Qué se construyó, cuándo, costo Robert
  - Trigger handoff: "Robert pagó ElevenLabs"
- Actualizar `MEMORY.md` index
- Actualizar `CLAUDE.md` raíz sección Workers monorepo (agregar canal voz)

**Archivos afectados**:
- 4 archivos nuevos en wiki
- `memory/ESTADO_ACTUAL.md`
- Auto-memory `project_robert_voz_2026.md` + `MEMORY.md`
- `CLAUDE.md` raíz

**Validación**:
- `grep "voz" PROYECTO\ ARNALDO\ OBSIDIAN/index.md` muestra entradas nuevas
- `cat memory/ESTADO_ACTUAL.md | grep -i voz` muestra feature

---

## Conexiones y dependencias

### Qué referencia esta área

- **Worker WhatsApp Robert** importará desde `shared/` post-refactor — si rompemos `shared/bant.py`, el WhatsApp se rompe también.
- **n8n Robert** (si existe workflow de notificación al asesor) — voz worker debe disparar el mismo webhook que WhatsApp para no duplicar lógica de notificación.
- **Postgres `lovbot_crm_modelo`** — ambos canales escriben en `Clientes`. Cuidar que no creen duplicados (matcher por phone normalizado).
- **Cal.com Robert** — bookings entre WhatsApp y voz no deben colisionar (Cal.com lo maneja nativo, pero verificar).

### Actualizaciones necesarias para consistencia

- `CLAUDE.md` raíz — sección "Workers monorepo" mencionar canal voz
- `wiki/index.md` — listar nuevos playbooks/conceptos
- `wiki/entidades/lovbot-ai.md` — agregar canal voz al stack
- `wiki/conceptos/matriz-infraestructura.md` — Robert ahora tiene 2 canales
- `memory/ESTADO_ACTUAL.md` — feature LIVE
- `MEMORY.md` (auto-memory) — entrada del proyecto

### Impacto en flujos existentes

- **Bot WhatsApp Robert**: refactor `shared/` puede romperlo si no se hace con cuidado. Mitigación: smoke test post-refactor antes de seguir.
- **Bot WhatsApp demo**: mismo riesgo si también se refactoriza (NO se hace en este plan).
- **Bot WhatsApp Maicol/Lau**: NO se tocan (clientes Arnaldo, otro stack).
- **n8n workflows Robert**: si hay workflow de notificación asesor, ambos canales deben dispararlo idéntico.

### Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Refactor `shared/` rompe bot WhatsApp Robert LIVE | Smoke test obligatorio post-refactor. Rollback = revert commit. |
| ElevenLabs cobra créditos en cuenta Arnaldo durante dev | Plan trial alcanza para validar. Si necesita más → plan Starter USD 5 un mes. |
| Latencia tools >2s genera UX mala en voz | Optimizar queries Airtable, agregar caching si necesario. Pre-tool speech mitiga. |
| ElevenLabs cambia API/pricing en medio del proyecto | Documentar versión actual en `wiki/conceptos/elevenlabs-conversational-ai.md`. |
| Robert no aprueba el costo de ElevenLabs (USD 22+) | Mostrar el demo funcionando en cuenta Arnaldo antes de pedir pago. |
| Twilio AR rechaza KYC de Robert | Plan B: Twilio MX (Robert tiene clientes ahí también) o número virtual de otro provider. |
| Catálogo Airtable cambia schema | Tests de smoke que cubran cada tool. |

---

## Lista de validación

Cómo verificar que la implementación quedó completa:

- [ ] `workers/shared/bant.py`, `catalog.py`, `calcom_client.py`, `lead_matcher.py` existen y compilan
- [ ] Bot WhatsApp Robert sigue respondiendo OK post-refactor (mensaje de prueba real)
- [ ] `agentes.lovbot.ai/clientes/lovbot/robert/voz/disponibilidad` retorna 200 con slots
- [ ] `agentes.lovbot.ai/clientes/lovbot/robert/voz/buscar-propiedad` retorna 200 con propiedades
- [ ] `agentes.lovbot.ai/clientes/lovbot/robert/voz/agendar-visita` crea booking en Cal.com Robert + lead en Postgres `lovbot_crm_modelo`
- [ ] Test AI agent ElevenLabs completa flujo end-to-end: saludo → búsqueda → agendamiento → confirmación
- [ ] Match cross-channel: número que ya existe en `Clientes` Airtable (de WhatsApp) es reconocido al llamar
- [ ] Tool-calling accuracy >90% en 10 conversaciones de prueba
- [ ] Export JSON del agente guardado en `02_OPERACION_COMPARTIDA/handoff/elevenlabs-agent-robert.json`
- [ ] Doc `handoff-voz-robert.md` ejecutable por Robert sin soporte
- [ ] Playbook `wiki/playbooks/worker-voz-elevenlabs.md` creado
- [ ] Concepto `wiki/conceptos/elevenlabs-conversational-ai.md` creado
- [ ] `memory/ESTADO_ACTUAL.md` actualizado
- [ ] Auto-memory `project_robert_voz_2026.md` creado y linkeado en `MEMORY.md`
- [ ] `CLAUDE.md` raíz sección Workers monorepo actualizada

---

## Criterios de éxito

El plan está completo cuando:

1. **Demo funcional sin Twilio**: agente ElevenLabs en cuenta Arnaldo completa un flujo búsqueda+agendamiento end-to-end llamando a endpoints `agentes.lovbot.ai/clientes/lovbot/robert/voz/*` sin errores.
2. **Reuso real de datos**: una visita agendada por voz aparece en el mismo Cal.com Robert que las del WhatsApp y el lead se crea/matchea en el mismo Postgres `lovbot_crm_modelo`.
3. **Bot WhatsApp Robert intacto**: post-refactor `shared/`, smoke test confirma comportamiento idéntico al previo.
4. **Handoff ejecutable**: doc + JSON permite que Robert (con 30 min) tenga el bot LIVE en su número Twilio sin nuestro soporte directo.
5. **Conocimiento capturado**: playbook + 2 conceptos wiki permiten que el próximo bot voz (Maicol, Cesar Posada, etc.) tome 1/3 del tiempo.

---

## Notas

**Trabajos follow-up que NO entran en este plan**:

- Bot voz outbound (que el bot llame al lead). Requiere lógica adicional + permisos Twilio.
- Integración con Chatwoot Robert para que las conversaciones de voz también queden registradas en el CRM unificado.
- Transcripciones de las llamadas archivadas en Airtable (privacy compliance pendiente).
- A/B testing de voces (cuál convierte más).
- Bot voz multi-idioma activo (hoy es ES con detect EN, pero no se aprovecha).
- WhatsApp Voice via ElevenLabs (cuando GA en AR) — para unificar a un solo número.
- Replicar este patrón a Maicol (Arnaldo, vertical urbanizaciones) — primer cliente Arnaldo voz.

**Cobrabilidad estimada para Robert**:
- Setup one-time: USD 500-800
- Mensual: USD 80-150 sobre infra (margen sobre USD 25 ElevenLabs+Twilio)
- A acordar comercialmente con Robert antes de handoff

**Próximas reuniones técnicas necesarias**:
- 30 min con Arnaldo: elegir voz + tono + tipo de KB inicial
- (Eventual) 30 min con Robert: validar que el agente funciona como espera antes del pago

---

## Notas de implementación

_Esta sección se completa al final de `/implementar`._

**Implementado**: 2026-04-27

### Resumen

- **Limpieza inicial** (no estaba en plan original, surgió durante ejecución): borrados 3 workers legacy (`_base/`, `inmobiliaria_garcia/`, `test_arnaldo/`) que mezclaban contexto y me hicieron asumir info errónea. Imports y `include_router` huérfanos limpiados de `main.py`. Docstring de `robert_inmobiliaria/worker.py` corregido (decía Airtable, era Postgres).
- **4 módulos shared creados** (`workers/shared/`):
  - `calcom_client.py` — wrapper Cal.com v2 reusable (slots + book + cancel + format voz)
  - `catalog.py` — wrapper búsqueda Postgres (sobre `db_postgres.buscar_propiedades`)
  - `lead_matcher.py` — match cross-channel por últimos 10 dígitos del teléfono
  - `bant.py` — extracción señales BANT (presupuesto, urgencia, authority, need) + score caliente/tibio/frío
- **Worker voz demo** en `workers/demos/inmobiliaria_voz/` con 5 endpoints `/voz/*` + healthz, registrado en `main.py` con prefix `/demos/voz/inmobiliaria`. Compila OK.
- **Handoff Robert completo** en `02_OPERACION_COMPARTIDA/handoff/elevenlabs-robert/`:
  - `README-handoff.md` — 9 pasos ejecutables (deploy, ElevenLabs config, Twilio, costos, troubleshooting)
  - `system-prompt.md` — system prompt en inglés ready-to-paste
  - `tools.json` — 5 custom tools formato ElevenLabs con voice_id `16UXUey4OpoKrC9IiRNt`
  - `kb-faq-inmobiliaria.md` — Knowledge Base FAQ
  - `kb-planes-y-servicios.md` — Knowledge Base servicios
- **Wiki actualizada**:
  - `wiki/playbooks/worker-voz-elevenlabs.md` — playbook v1 con 11 gotchas y stack por agencia
  - `wiki/conceptos/elevenlabs-conversational-ai.md`
  - `wiki/conceptos/twilio-numeros-telefonicos.md`
  - `wiki/entidades/lovbot-ai.md` — agregado bot voz al estado
  - `wiki/index.md` — playbooks 7→8, total páginas 68→71

### Desviaciones del plan

1. **Limpieza de workers legacy** (no en plan original): Arnaldo solicitó borrar `_base/`, `test_arnaldo/`, `inmobiliaria_garcia/` durante la ejecución. Hecho antes de codear lo nuevo. Impacto: cero (ninguno tenía clientes prod, solo eran tests).
2. **Carpeta worker voz** se llama `inmobiliaria_voz` (snake_case Python) y no `inmobiliaria-voz` (kebab). Razón: Python no permite `-` en nombres de paquetes. Plan decía `inmobiliaria-voz`.
3. **Refactor BANT en `shared/`**: hecho como módulo nuevo NO extraído del worker WhatsApp Robert (que sigue intacto). El worker WhatsApp seguirá usando su BANT inline hasta el siguiente caso de voz que justifique consolidación.
4. **Promoción demo→cliente Robert (Paso 6 del plan)**: NO ejecutada. El worker queda en `demos/` por ahora. Se promueve cuando Robert pague ElevenLabs y haya tráfico real (esto es deseable según REGLA Demo→Producción).
5. **Iteración fina del system prompt (Paso 5)**: NO ejecutada — requiere conversaciones reales en ElevenLabs UI con Arnaldo presente. Documentado en handoff como paso 6 ("Test desde Test AI agent").

### Problemas encontrados

1. **Confusión inicial sobre stack Robert**: asumí Airtable + worker LIVE en producción. La verdad (ratificada por Arnaldo + wiki): Postgres `lovbot_crm_modelo` + ningún cliente prod aún + worker `robert_inmobiliaria` es modelo demo. Aprendizaje: **siempre consultar wiki Obsidian primero**, no hojear código a ciegas.
2. **Workers legacy con nombres engañosos** (`robert_inmobiliaria` con docstring Airtable obsoleta): el archivo se había migrado parcialmente a Postgres pero el comentario quedó. Fix: docstring reescrita con la verdad.
3. **Falso positivo del LSP**: import `demo_voz_inmobiliaria_router` marcado como unused cuando sí estaba usado en `include_router` agregado en otra edición. Causa: cache stale del LSP entre ediciones consecutivas. Sin impacto real.
4. **`__pycache__` legacy** quedó tras borrar carpetas. Limpiado con `find -name __pycache__ -exec rm -rf`.

### Descubrimientos nuevos

Para propagar:

- **Playbook nuevo** `worker-voz-elevenlabs.md` con 11 gotchas. Próximo cliente voz lo aplica directo y debería tomar <2h.
- **Auto-memory nueva**: regla "consultar wiki Obsidian antes de inferir stack" + "borrar legacy huérfano al detectarlo en lugar de preservarlo". Se agregan a `~/.claude/projects/.../memory/`.
- **Memory `ESTADO_ACTUAL.md`** se actualiza con la entrega del bot voz dev-ready.
- **Endpoints admin Postgres** existen (`/admin/listar-dbs`, `/admin/crear-db-cliente`, etc.) — útiles cuando el voz worker se promueva a cliente Robert. Documentados en `wiki/conceptos/postgresql.md` ya, pero no estaban en mi memoria operativa.

### Pendientes para handoff a Robert

- Robert paga ElevenLabs Creator (USD 22/mes) → crea cuenta o se le importa JSON
- Robert compra número Twilio AR (KYC 3-10 días)
- Robert conecta Twilio ↔ ElevenLabs en su cuenta
- Después: promover `workers/demos/inmobiliaria_voz/` → `workers/clientes/lovbot/robert_voz/` y actualizar URLs de tools en ElevenLabs
