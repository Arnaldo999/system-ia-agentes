---
name: CRM IA Chat — Asistente Inmobiliario (Robert + Mica)
description: Asistente IA en CRM con consultas a BD, búsqueda web Tavily, resúmenes IA, kanban drag&drop sincronizado con bot
type: project
originSessionId: ff264427-3f05-4e1a-a9c9-a3061566ef37
---
# CRM IA Chat + Pipeline Kanban + Resúmenes IA

Implementado en sesiones 2026-04-16. Funcional y desplegado en producción para Robert (Lovbot) y Mica (System IA).

## ARQUITECTURA

### Robert (Lovbot)
- **Frontend dev**: `lovbot-demos.vercel.app/dev/crm?tenant=robert` → `demos/INMOBILIARIA/dev/crm.html`
- **Frontend prod**: `crm.lovbot.ai?tenant=robert` → `demos/INMOBILIARIA/demo-crm-mvp.html`
- **Backend**: `agentes.lovbot.ai/clientes/lovbot/inmobiliaria/*` (Coolify Hetzner)
- **n8n**: `n8n.lovbot.ai` (instancia Robert)
- **DB**: PostgreSQL container `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck`, **database `robert_crm`** (NO `lovbot_crm`)

### Mica (System IA)
- **Frontend dev**: `system-ia-agencia.vercel.app/system-ia/dev/crm?tenant=mica-demo` → `demos/SYSTEM-IA/dev/crm.html`
- **Backend**: `agentes.arnaldoayalaestratega.cloud/mica/demos/inmobiliaria/*` (Coolify Arnaldo)
- **n8n**: `n8n.arnaldoayalaestratega.cloud` (instancia Arnaldo)
- **DB**: Airtable base `appA8QxIhBYYAHw0F` (NO `appXPpRAfb6GH0xzV` que estaba en .env desactualizado)

## WORKFLOWS N8N

### Robert — n8n.lovbot.ai
| Workflow | ID | Función |
|---|---|---|
| CRM IA - Asistente Inmobiliario | `fKeUXQXxpI0xUKGs` | Orquestador GPT-4.1-mini |
| CRM IA - Ejecutar SQL | `0t32XZ9AuQXB9fOn` | Validador SQL + inyección tenant + Postgres |
| CRM IA - Buscar en Web | `mRwlkAD4TQQuhrpE` | Tavily API para sector inmobiliario |

### Mica — n8n.arnaldoayalaestratega.cloud
| Workflow | ID | Función |
|---|---|---|
| CRM IA - Asistente Inmobiliario Mica | `G9Qtc0V6JDHqoVf8` | Orquestador GPT-4.1-mini |
| CRM IA - Consultar Airtable Mica | `U0WCURPGpudMwuDX` | Validador filterByFormula + Airtable |
| CRM IA - Buscar en Web Mica | `odRLe6Pzpljv14zi` | Tavily |

Webhooks:
- Robert: `https://n8n.lovbot.ai/webhook/crm-ia-chat`
- Mica: `https://n8n.arnaldoayalaestratega.cloud/webhook/crm-ia-chat-mica`

## SCHEMA REAL POSTGRESQL (Robert)

**leads** (no usar `tipo` sino `tipo_propiedad`, no `notas` sino `notas_bot`):
- id, tenant_slug, telefono, nombre, apellido, email
- score (string: 'caliente'/'tibio'/'frio'), estado (no_contactado/contactado/calificado/cita_agendada/visita_agendada/cerrado/descartado)
- tipo_propiedad, zona, operacion, ciudad, presupuesto, sub_nicho, notas_bot
- fuente, fuente_detalle, fecha_whatsapp, llego_whatsapp, fecha_ultimo_contacto
- **fecha_cita** (DATE) — si NOT NULL = lead con cita

**propiedades** (no `estado` sino `disponible`, no `superficie` sino `metros_cubiertos`/`metros_terreno`):
- id, tenant_slug, titulo, descripcion, tipo, operacion, zona
- precio, moneda, presupuesto, **disponible** (string con emoji: '✅ Disponible' / '⏳ Reservado' / '❌ No disponible')
- dormitorios, banios, metros_cubiertos, metros_terreno
- imagen_url, maps_url, direccion, propietario_*, comision_pct, tipo_cartera, asesor_asignado, loteo, numero_lote

**clientes_activos**:
- id, tenant_slug, nombre, apellido, telefono, email, propiedad
- estado_pago ('Al día'/'Atrasado' — capitalizado con tilde)
- monto_cuota, cuotas_pagadas, cuotas_total, proximo_vencimiento, notas

**resumenes_conversacion** (nueva, sesión 2026-04-16):
- id, tenant_slug, lead_id, telefono, nombre, resumen
- presupuesto, zona, urgencia, financiamiento, score (1-5), cantidad_mensajes, duracion_minutos, fecha_conversacion
- UNIQUE(tenant_slug, telefono) → upsert por teléfono

## LÓGICA DEL AGENTE IA

**Datos internos (CLASE 1):** leads, clientes, pagos, pipeline, propiedades
- Consulta BD → muestra resultados o "no hay registros con esos criterios"
- NUNCA sugiere buscar en internet para datos internos
- Distingue: "agenda/citas" → leads WHERE fecha_cita NOT NULL | "clientes activos" → tabla clientes_activos

**Conocimiento del sector (CLASE 2):** mercado, inversiones, tendencias, consejos
- Busca en web (Tavily) directamente sin pedir confirmación
- Agrega valor profesional al comercial inmobiliario
- NUNCA busca datos de bases externas o listados de terceros

**Búsquedas flexibles (anti-typos):**
- ILIKE con wildcards %% para todos los enums (tipo, operacion, score, ciudad)
- Abreviaturas: depto/depa/dpto, alq/alquiler/renta, lote/terreno
- Tildes: '%apostol%' matchea Apóstoles/Apostoles, '%ignaci%' matchea Ignacio/Igancio
- EXCEPCIÓN `disponible`: usar = exacto con emoji ('✅ Disponible')

## ENDPOINTS NUEVOS — RESÚMENES IA (Robert)

| Método | Ruta | Función |
|---|---|---|
| POST | `/admin/setup-resumenes` | Crea tabla `resumenes_conversacion` |
| POST | `/crm/resumenes/generar/{telefono}` | Genera 1 resumen via GPT |
| POST | `/crm/resumenes/generar-todos?solo_pendientes=true` | Itera leads con cita y genera batch |
| GET | `/crm/resumenes?limit=20&score_min=3&desde=YYYY-MM-DD&search=texto` | Lista con filtros |

GPT-4.1-mini lee `notas_bot + presupuesto + zona + tipo + score` del lead y devuelve JSON estructurado con `resumen + presupuesto + zona + urgencia + financiamiento + score 1-5`.

Filtro: solo leads con `fecha_cita IS NOT NULL` (los que llegaron a agendar).

## PIPELINE KANBAN — 5 ESTADOS (Robert)

Reemplaza el pipeline genérico de 6 columnas por 5 enfocadas en inmobiliaria:

| # | Columna | Estados BD | Score badge | Drag |
|---|---|---|---|---|
| 1 | 📥 Nuevo | no_contactado, nuevo | Real (frío/tibio/caliente) | ❌ Bot |
| 2 | 💬 En conversación | contactado, seguimiento | 🌡️ Tibio (preterminado) | ❌ Bot |
| 3 | 📅 Cita agendada | cita_agendada, visita_agendada, leads con fecha_cita | 🔥 Caliente (preterminado) | ❌ Bot |
| 4 | 🤝 En negociación | en_negociacion, calificado, visito | — | ✅ Comercial |
| 5 | ✅/❌ Cerrado / Perdido | cerrado, cerrado_ganado, cerrado_perdido, descartado | — (badge verde/rojo) | ✅ Comercial |

**Drag & drop:**
- Solo columnas 4 y 5 son arrastrables (las otras las maneja el bot)
- PATCH `/crm/clientes/{atId}` con Estado válido del backend
- Optimistic update + rollback si falla
- Drop en "Cerrado" pregunta vía `confirm()` si fue ganado o perdido

**ESTADO_REVERSE** (frontend → backend):
- nuevo → 'no_contactado' | conversacion → 'contactado'
- cita → 'visita_agendada' | negociacion → 'en_negociacion'
- cerrado_ganado → 'cerrado_ganado' | cerrado_perdido → 'cerrado_perdido'

⚠️ Backend rechaza valores fuera de: `no_contactado, contactado, calificado, visita_agendada, visito, en_negociacion, seguimiento, cerrado_ganado, cerrado_perdido`

## AUTO-REFRESH 30s

CRM se sincroniza con BD cada 30 segundos:
- Solo refresca el panel activo
- Pausa si la pestaña está en background (`document.hidden`)
- Refresh inmediato al volver al tab tras estar afuera (`visibilitychange`)

## BUGS CRÍTICOS RESUELTOS

**Bug 1 — SQL `/CREATE/` matcheaba `created_at`:**
- Fix: word boundaries `\bCREATE\b` en regex de keywords prohibidos del validador SQL

**Bug 2 — AI generaba SQL con markdown ```sql...```:**
- Fix: función `extraerSQL()` que strips markdown y busca SELECT desde cualquier posición

**Bug 3 — "No prompt specified":**
- Fix: `promptType: "define"`, `text: "={{ $('Webhook CRM IA').item.json.body.message }}"`

**Bug 4 — Mica chat consultaba base equivocada (.env desactualizado):**
- .env local: `INMO_DEMO_AIRTABLE_BASE=appXPpRAfb6GH0xzV` (tenía 20 records sin "Bobo")
- Real Mica: `appA8QxIhBYYAHw0F` (18 records con "Bobo") ← este es el correcto
- Fix: hardcodear el correcto en el workflow Airtable Mica

**Bug 5 — Robert chat consultaba `lovbot_crm` en vez de `robert_crm`:**
- Backend Coolify usa env var `LOVBOT_PG_DB=robert_crm`
- n8n credential apuntaba a `lovbot_crm` (default)
- Fix: cambiar database de la credencial Postgres en n8n a `robert_crm`

**Bug 6 — Workflow Ejecutar SQL no devolvía nada con 0 records:**
- Por defecto n8n no ejecuta el siguiente nodo si el anterior devuelve 0 items
- Fix: setear `alwaysOutputData: true` en el nodo Postgres + nodo Code "Formatear Resultado SQL" que devuelve mensaje "Sin registros"

**Bug 7 — ESTADO_REVERSE enviaba valores que el backend rechaza:**
- Fix: alinear con `ESTADOS_VALIDOS` del worker (cita_agendada → visita_agendada, cerrado → cerrado_ganado)

**Bug 8 — Score "leads calientes" mal calculado en Mica:**
- Mica: criterio dashboard `score >= 12` pero AI usaba `>= 7`
- Fix: prompt actualizado con criterios oficiales (caliente >=12, tibio 7-11, frío <7)

**Bug 9 — Hay 2 PostgreSQL containers en Coolify Robert (Hetzner):**
- `lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc` (n8n's internal pg)
- `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck` (CRM, el real)
- Fix: usar el segundo + database `robert_crm`

**Bug 10 — Kanban duplicaba plan-chip "IA activa" + chat IA en sidebar:**
- Fix: eliminar el plan-chip estático, dejar solo el botón IA animado (igual que Robert)

## CONEXIÓN POSTGRESQL N8N (Robert)

```
Host: 5.161.235.99 (no internal hostname — n8n no resuelve via Docker DNS)
Port: 5432
Database: robert_crm  ← crítico, no lovbot_crm
User: lovbot
Password: 9C7i82bFVoscycGCF6f7XPbZyNpWvEXa  (LOVBOT_PG_PASS)
SSL: Disable
```

Credencial n8n: ID `KrrcaHvOt03n78e8` ("Postgres account 2")

## TENANT SECURITY (Robert)

SQL validator inyecta automáticamente `AND tenant_slug = 'X'` antes de ejecutar. El agente recibe `tenant_slug` del frontend (query param) y se propaga a todos los sub-workflows. Multi-tenant isolation garantizada.

## LIMITACIONES CONOCIDAS

1. **MCP n8n no preserva credenciales OpenAI** — al hacer update_full_workflow se rompe la asignación de credencial GPT-4.1-mini. Workaround: usar `update_partial_workflow` solo para cambios al system prompt, o re-asignar manualmente en n8n UI.

2. **Bobo en Mica tiene datos contradictorios** — ciudad="Waterloo" pero notas dicen "Cancún". El AI prioriza notas cuando son más específicas. No es bug, es data inconsistente del lead.

3. **Resúmenes IA son sintéticos**, no transcripts reales. Generan resumen leyendo campos del lead (notas_bot, presupuesto, etc), no la conversación textual del bot. Suficiente para el 80% de casos. Para resúmenes de conversación real habría que persistir mensajes en tabla `mensajes_bot`.

## PENDIENTES

- **Mica**: re-asignar credencial OpenAI manualmente en n8n.arnaldoayalaestratega.cloud (workflow `G9Qtc0V6JDHqoVf8` nodo GPT-4.1-mini) y hacer Save. Esto publica el draft con el prompt nuevo (con flexibilidad ILIKE, abreviaturas, etc.).
- **Mica**: replicar resúmenes IA + kanban si se valida en Robert primero.
- **Auto-generar resumen al cerrar conversación**: modificar worker Robert para llamar `/crm/resumenes/generar/{telefono}` cuando el lead llega a estado `cita_agendada` o `cerrado`. Sesión futura.
