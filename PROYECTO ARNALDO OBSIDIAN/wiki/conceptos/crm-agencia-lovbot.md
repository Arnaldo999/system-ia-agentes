---
title: "CRM Gestión Agencia Lovbot (CRM propio Robert+Arnaldo)"
tags: [crm-agencia, lovbot, gestion-leads, supabase, postgres, landing, decision-arquitectural, mockup-deployado-coolify, live-en-produccion]
source_count: 1
proyectos_aplicables: [robert]
status: LIVE-end-to-end-2026-04-23
fecha_propuesta: 2026-04-22
fecha_implementacion: 2026-04-23
propuesto_por: [robert-bazan, arnaldo-ayala]
---

# CRM Gestión Agencia Lovbot (CRM propio)

> **Status**: LIVE end-to-end desde 2026-04-23. BD Postgres `lovbot_agencia` corriendo en Hetzner, backend FastAPI `/agencia/*` LIVE en `agentes.lovbot.ai`, frontend LIVE en `https://admin.lovbot.ai/agencia`. Propuesto por [[robert-bazan|Robert]] el 2026-04-22, implementado en sesión con [[arnaldo-ayala|Arnaldo]] el 2026-04-23.

## Qué es

CRM propio de la **agencia Lovbot** (no de los clientes inmobiliarias). Sirve para que [[robert-bazan|Robert]] y [[arnaldo-ayala|Arnaldo]] (como socios) gestionen sus propios leads y clientes activos: gente que llega vía landing, bot WhatsApp de agencia o referidos, y termina comprando alguno de los servicios de la agencia (hoy CRM, a futuro otros).

**Distinto a [[crm-v2-modelo-robert]]**: ese es el modelo que se vende a clientes inmobiliarias. El CRM agencia que se documenta acá es para uso interno de los socios.

**Distinto a [[panel-gestion-robert]]**: ese gestiona a los clientes que ya compraron el CRM (catálogo en [[supabase-tenants]]). El CRM agencia gestiona el funnel previo (leads → prospectos → clientes).

## Arquitectura propuesta (decisión 2026-04-22)

### División de datos por capa

| Capa | Storage | Rol |
|------|---------|-----|
| **Catálogo de clientes que ya compraron CRM** | [[supabase-tenants\|Supabase Arnaldo]] (tabla `tenants`) — YA EXISTE | Lo que muestra [[panel-gestion-robert]] |
| **Leads agencia + clientes activos agencia** | 🆕 **Postgres Robert (Hetzner)** — nueva BD a crear | Lo que va a mostrar el CRM agencia |
| **Datos del CRM de cada cliente inmobiliaria** | Postgres por cliente (ej: `lovbot_crm_robert_x`) | Lo que muestra [[crm-v2-modelo-robert]] con `?tenant=X` |

### Por qué Postgres y NO Supabase para los leads

Decisión de Arnaldo el 2026-04-22:

1. **Aislamiento de datos**: los leads de la agencia son data privada de Robert+Arnaldo. No tienen relación funcional con la tabla `tenants` de Supabase (que es solo el catálogo público de clientes activos). Mezclarlos rompe el límite conceptual.
2. **Reuso de infra ya operativa**: el cluster Postgres de Hetzner ([[vps-hetzner-robert]]) ya tiene `lovbot_crm_modelo` corriendo, [[sistema-auditoria|monitoreado]], con backup, etc. Sumar una BD nueva en el mismo cluster es trivial.
3. **Coherencia de stack**: Lovbot ya usa Postgres como stack canónico (ver [[matriz-infraestructura]]). Mantener todo Postgres simplifica la operación.
4. **Mismo modelo de datos del CRM v3**: se puede aprovechar el patrón [[persona-unica-crm]] + [[contratos-polimorficos]] que ya está implementado en `lovbot_crm_modelo`.

### Esquema BD propuesto

Nueva BD en cluster Hetzner Robert: `lovbot_agencia_crm` (nombre tentativo).

Tablas iniciales (siguiendo patrón v3):

```
leads                  -- prospectos que llegaron por landing/bot/referidos
clientes_activos       -- leads que se convirtieron en clientes pagos
contratos              -- contratos firmados (CRM mensual, setup, etc.)
canales_origen         -- landing, bot-whatsapp, referido, etc. (catalogo)
notas_interaccion      -- log de cada contacto/conversación
```

> **No es necesario** replicar todas las tablas del CRM inmobiliaria (`propiedades`, `loteos`, `inmuebles_renta`, etc.). Acá los "items" son los **servicios de la agencia** (CRM, futuros productos).

**Implementado tal cual 2026-04-23**: BD `lovbot_agencia` (no `lovbot_agencia_crm` como se proponía — Arnaldo decidió nombre más corto).

## Origen de los leads (canales)

### 1. Landing pública [[landing-lovbot-ai]]

Visitante en `https://lovbot.ai/` → CTA "Hablar por WhatsApp" → redirige a `wa.me/<numero-bot-agencia>` con mensaje pre-poblado → bot WhatsApp de la agencia atiende.

> Hoy la landing dice "Próximamente". El CTA WhatsApp se conecta cuando el bot agencia esté listo.

### 2. Bot WhatsApp Agencia Lovbot (NUEVO — pendiente de crear)

Bot conversacional propio de la agencia para responder consultas sobre los servicios.

**Stack confirmado** (decisión 2026-04-22):
- WhatsApp provider: [[meta-graph-api]] vía Tech Provider Robert (cuando esté habilitado)
- Número WABA: nuevo (a registrar via Embedded Signup en cuenta Lovbot)
- Worker: nuevo en `workers/clientes/lovbot/agencia/worker.py` (path tentativo)
- LLM: [[postgresql|cuenta OpenAI Robert]] (`LOVBOT_OPENAI_API_KEY`) — coherente con stack Lovbot
- BD: la nueva `lovbot_agencia_crm` (no `lovbot_crm_modelo` — ese es para clientes)

### 3. Otros canales (futuros)

- Formulario en landing (lead form HTML → API → Postgres)
- Anuncios pagos (UTMs)
- Referidos (tracking manual al inicio)
- Eventos / webinars

## Frontend propuesto

Replicar [[crm-v2-modelo-robert|crm-v2.html]] como base, pero **adaptar**:

- **Quitar** secciones específicas inmobiliarias: `panel-loteos`, `panel-inmuebles-renta`, `panel-inquilinos`, `panel-pagos-alquiler`, `panel-liquidaciones`, `panel-propietarios`.
- **Mantener**: dashboard, tabla de leads/clientes, contratos, notas, reportes.
- **Agregar**: vista de canales (cuántos leads vienen de cada origen), vista de embudo (lead → prospecto → cliente).

Path tentativo: `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/crm-agencia.html` (o carpeta nueva `demos/AGENCIA-LOVBOT/`).

URL pública sugerida (a decidir): `gestion.lovbot.ai` o `crm.lovbot.ai/agencia` (subruta).

## Acceso

Solo Robert + Arnaldo. Probable autenticación simple por PIN o sesión persistente como [[panel-gestion-robert]].

## Comparativa de los 3 productos Lovbot (todos en Coolify Hetzner desde 2026-04-23)

| Producto | Para quién | Backend | Storage | URL |
|----------|-----------|---------|---------|-----|
| [[crm-v2-modelo-robert]] | Cliente inmobiliaria final | `agentes.lovbot.ai` | Postgres por cliente (clonado de `lovbot_crm_modelo`) | `https://crm.lovbot.ai/dev/crm-v2?tenant=X` |
| [[panel-gestion-robert]] | Robert+Arnaldo (gestión clientes que compraron CRM) | `agentes.arnaldoayalaestratega.cloud/admin/tenants` | [[supabase-tenants\|Supabase]] | `https://admin.lovbot.ai/clientes` |
| 🆕 **CRM Agencia Lovbot** (este) | Robert+Arnaldo (gestión leads agencia) | A definir (probablemente `agentes.lovbot.ai/agencia/...`) | 🆕 Postgres Hetzner BD `lovbot_agencia_crm` | `https://admin.lovbot.ai/agencia` (mockup deployado) |

> Los 3 productos comparten el dominio `admin.lovbot.ai` (admin + agencia) o `crm.lovbot.ai` (modelo cliente). Todos vivos desde [[coolify-robert|Coolify Hetzner]]. Vercel queda solo como fallback temporal.

## Pasos de implementación (orden sugerido)

1. **Validar Tech Provider Robert habilitado** (precondición para crear nuevo número WABA agencia).
2. **Crear BD `lovbot_agencia_crm`** en cluster Hetzner Robert. Definir schema (5 tablas iniciales).
3. **Diseñar endpoints backend** en `agentes.lovbot.ai` (o `agentes.arnaldoayalaestratega.cloud` si conviene compartir): `/agencia/leads`, `/agencia/clientes`, `/agencia/contratos`, `/agencia/canales`.
4. **Adaptar frontend `crm-v2.html`** → `crm-agencia.html` con paneles relevantes.
5. **Onboarding número WABA agencia** vía Embedded Signup.
6. **Worker bot agencia** en `workers/clientes/lovbot/agencia/`.
7. **Conectar landing `lovbot.ai`** al bot (CTA WhatsApp).
8. **Sumar al [[sistema-auditoria]]**: checks para `gestion.lovbot.ai`, backend agencia, BD agencia.
9. **Documentar como entidad activa** (mover esta página de "pendiente" a "implementada" cuando esté LIVE).

## Decisiones diferidas

- ~~¿Subdomino dedicado (`gestion.lovbot.ai`) o subruta (`crm.lovbot.ai/agencia`)?~~ → **RESUELTO 2026-04-23**: vive en `https://admin.lovbot.ai/agencia` (mismo host que el panel de clientes — un solo dominio admin para todo lo interno).
- ~~¿Mismo backend FastAPI Arnaldo o nuevo en Lovbot Hetzner?~~ → **RESUELTO 2026-04-23**: backend nuevo en `agentes.lovbot.ai` (Hetzner), endpoints `/agencia/*` (pendientes de implementar).
- ¿Auth simple PIN o algo más robusto (JWT, OAuth Google)?
- Estructura definitiva de tablas (extender o no el patrón v3 completo).

## Reglas mientras esté pendiente

- ❌ NO confundir esta propuesta con [[crm-v2-modelo-robert]] (CRM para clientes) ni con [[panel-gestion-robert]] (admin de tenants Supabase).
- ❌ NO empezar a meter leads de agencia en la tabla `tenants` de [[supabase-tenants]] — esa tabla es solo para clientes que YA compraron CRM.
- ❌ NO crear el bot agencia hasta confirmar Tech Provider Robert habilitado.
- ✅ Cuando el flujo se implemente, esta página se promueve a entidad `crm-agencia-lovbot.md` con `status: implementada` y se mueve de `wiki/conceptos/` a `wiki/entidades/`.

## Implementación Fase 1 — Mockup HTML (2026-04-22)

### Commit

`b56e4e4` — feat(crm-agencia-lovbot): HTML inicial mockeado + reorganizacion admin

### URLs LIVE (post-deploy Vercel)

| URL | Archivo | Estado | Host |
|-----|---------|--------|------|
| `admin.lovbot.ai/agencia.html` | `dev/admin/agencia.html` | LIVE (mockup) | Coolify Hetzner (canónica) |
| `admin.lovbot.ai/clientes.html` | `dev/admin/clientes.html` | LIVE (productivo) | Coolify Hetzner (canónica) |
| `lovbot-demos.vercel.app/dev/admin/agencia` | `dev/admin/agencia.html` | LIVE (fallback Vercel) | Vercel |
| `lovbot-demos.vercel.app/dev/admin/clientes` | `dev/admin/clientes.html` | LIVE (fallback Vercel) | Vercel |
| `lovbot-demos.vercel.app/dev/admin` | → redirect a `clientes.html` | Retro-compatible | Vercel |

### Que tiene el mockup

- Vista embudo con 6 cards de estado (Nuevo / Contactado / Propuesta / Negociacion / Cliente / Perdido)
- Tabla completa de leads con filtros (buscar texto, canal, estado) funcionando en cliente
- 5 leads de ejemplo con datos reales plausibles
- Botones: WA funcional (abre wa.me), Editar / Convertir / Eliminar disabled con tooltip "Backend pendiente"
- Banner ámbar marcando claramente que es mockup
- Sidebar con navegacion entre Clientes CRM (→ `/dev/admin/clientes`) y Leads Agencia (active, `/dev/admin/agencia`)
- Paleta Robert: purple `#6c63ff`

### Reorganizacion de carpetas admin (también en este commit)

```
demos/INMOBILIARIA/dev/
  admin.html → admin/clientes.html   # git mv (retro-compatible via vercel.json)
  admin/agencia.html                 # NUEVO

demos/SYSTEM-IA/
  admin.html → admin/clientes.html   # git mv (retro-compatible via vercel.json)
```

### Proximos pasos — Fase 2 (pendientes)

1. Crear BD `lovbot_agencia_crm` en cluster Postgres Hetzner (5 tablas: `leads`, `clientes_activos`, `contratos`, `canales_origen`, `notas_interaccion`)
2. Implementar endpoints en `agentes.lovbot.ai`: `GET/POST /agencia/leads`, `PATCH /agencia/leads/:id`, `POST /agencia/leads/:id/convertir`
3. Conectar `agencia.html` al backend real (quitar mock, conectar fetch)
4. Decidir autenticacion: ¿mismo `LOVBOT_ADMIN_TOKEN` del panel clientes, o token separado?
5. Agregar al [[sistema-auditoria]] cuando el backend exista

## Implementación final (2026-04-23)

### BD Postgres `lovbot_agencia`

Creada en el cluster Hetzner [[vps-hetzner-robert]]. Container `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck`. 6 tablas implementadas:

| Tabla | Rol |
|-------|-----|
| `agencia_fuentes` | Catálogo de canales de origen (8 seeds cargados) |
| `agencia_leads` | Prospectos del funnel de la agencia |
| `agencia_clientes` | Leads convertidos a clientes activos |
| `agencia_contactos_log` | Log de cada interacción con un lead/cliente |
| `agencia_propuestas` | Propuestas enviadas (estado, monto, link) |
| `agencia_pagos` | Pagos registrados por cliente |

Adicionalmente: vista `agencia_funnel_resumen` (agrupa leads por estado para el embudo), 3 triggers de `updated_at` (en leads, clientes, propuestas), y 8 seeds de fuentes: `landing`, `fb_ads`, `referido`, `bot_whatsapp`, `evento`, `lead_center`, `zapier`, `otro`.

Env var Coolify: `LOVBOT_AGENCIA_PG_DB=lovbot_agencia`.

### Backend FastAPI

Router en `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/lovbot/agencia_crm/router.py`. Prefijo `/agencia`. Registrado en `main.py`.

15 endpoints disponibles:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/agencia/funnel-resumen` | GET | Datos del embudo por estado (usa vista PG) |
| `/agencia/leads` | GET | Lista leads con filtros opcionales |
| `/agencia/leads` | POST | Crear nuevo lead |
| `/agencia/leads/{id}` | PATCH | Editar lead |
| `/agencia/leads/{id}` | DELETE | Soft delete (estado=eliminado) |
| `/agencia/leads/{id}/convertir-cliente` | POST | Convierte lead en cliente activo |
| `/agencia/contactos-log` | GET | Historial de contactos |
| `/agencia/contactos-log` | POST | Registrar nuevo contacto |
| `/agencia/propuestas` | GET | Lista de propuestas |
| `/agencia/propuestas` | POST | Crear propuesta |
| `/agencia/propuestas/{id}` | PATCH | Actualizar propuesta |
| `/agencia/clientes` | GET | Lista de clientes activos |
| `/agencia/clientes/{id}` | GET | Detalle de cliente |
| `/agencia/fuentes` | GET | Catálogo de fuentes/canales |
| `/agencia/pagos` | GET + POST | Registro de pagos |

### Auth

Bearer token. Valor del env var `LOVBOT_ADMIN_TOKEN` en Coolify Hetzner (token largo de 64 chars, el mismo token que protege `/admin/*`). NO usar el hardcoded `lovbot-admin-2026` — ese solo es default para dev local. Arnaldo tiene un token personalizado que sabe de memoria.

### Schema Pydantic — campos clave

- `nombre_contacto`: str (obligatorio)
- `fuente_id`: INT (no slug de texto)
- `pais`: default `"Mexico"`
- `responsable`: default `"Robert"`

### Frontend

Archivo `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/admin/agencia.html`. URL pública `https://admin.lovbot.ai/agencia`.

Login con token persistido en `sessionStorage` bajo key `lovbot_agencia_token`. Dos vistas navegables desde sidebar interno:

- **Embudo**: 6 cards clickables (Nuevo / Contactado / Propuesta / Negociacion / Cliente / Perdido) — al hacer click filtra la tabla
- **Todos los leads**: tabla completa con filtros de búsqueda por texto, canal, estado

Modales implementados:
- **Nuevo Lead**: todos los campos del schema (nombre_contacto, apellido, empresa, fuente_id, email, teléfono, país, responsable, notas)
- **Editar lead**: mismos campos pre-populados
- **Convertir a cliente**: plan, monto mensual, tenant_slug
- **Marcar perdido**: motivo obligatorio

### Slot preparado para lead.center / Zapier

Campos `fb_lead_id`, `lead_center_id`, `zapier_data` (JSONB) ya presentes en `agencia_leads`. Fuentes seed `lead_center` y `zapier` ya cargadas. Cuando Robert mande detalles de su flujo actual, el conector solo tiene que hacer `POST /agencia/leads` con `fuente_id` correspondiente y `zapier_data` con el payload original. Sin cambios de schema requeridos.

### Decisiones tomadas en la implementación

- BD se llama `lovbot_agencia` (no `lovbot_agencia_crm`) — Arnaldo eligió nombre más corto porque "hace referencia a todo el proyecto Robert, no solo al CRM".
- Los 2 paneles admin (`/clientes` y `/agencia`) mantienen tokens separados porque apuntan a backends distintos (`agentes.arnaldoayalaestratega.cloud` vs `agentes.lovbot.ai`). No se unificó auth.
- Panel `/clientes` (gestión tenants Supabase): 5 stat cards + tabla con buscador, sin tabs internos.
- Panel `/agencia` (CRM leads agencia): 2 vistas navegables (Embudo + Todos los leads).

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22]] — sesión donde Robert propuso la idea + Arnaldo decidió Postgres + mockup HTML implementado
- Chat WhatsApp Arnaldo↔Robert 2026-04-22 (capturas en sesión)
