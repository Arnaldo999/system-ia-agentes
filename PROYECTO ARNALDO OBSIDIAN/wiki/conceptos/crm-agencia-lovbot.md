---
title: "CRM Gestión Agencia Lovbot (CRM propio Robert+Arnaldo)"
tags: [crm-agencia, lovbot, gestion-leads, supabase, postgres, landing, decision-arquitectural, mockup-deployado-coolify]
source_count: 1
proyectos_aplicables: [robert]
status: mockup-deployado-coolify-pendiente-backend
fecha_propuesta: 2026-04-22
propuesto_por: [robert-bazan, arnaldo-ayala]
---

# CRM Gestión Agencia Lovbot (CRM propio)

> **Status**: Mockup HTML deployado en Coolify Hetzner (2026-04-22) — URL pública `https://admin.lovbot.ai/agencia.html`. Backend + BD pendientes. Propuesto por [[robert-bazan]] el 2026-04-22 en chat WhatsApp con [[arnaldo-ayala]].

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

## Comparativa de los 3 productos Lovbot

| Producto | Para quién | Backend | Storage | URL |
|----------|-----------|---------|---------|-----|
| [[crm-v2-modelo-robert]] | Cliente inmobiliaria final | `agentes.lovbot.ai` | Postgres por cliente (clonado de `lovbot_crm_modelo`) | `crm.lovbot.ai/dev/crm-v2?tenant=X` |
| [[panel-gestion-robert]] | Robert+Arnaldo (gestión clientes que compraron CRM) | `agentes.arnaldoayalaestratega.cloud/admin/tenants` | [[supabase-tenants\|Supabase]] | `lovbot-demos.vercel.app/dev/admin` |
| 🆕 **CRM Agencia Lovbot** (este) | Robert+Arnaldo (gestión leads agencia) | A definir (probablemente `agentes.lovbot.ai/agencia/...`) | 🆕 Postgres Hetzner BD `lovbot_agencia_crm` | A definir (`gestion.lovbot.ai`?) |

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

- ¿Subdomino dedicado (`gestion.lovbot.ai`) o subruta (`crm.lovbot.ai/agencia`)?
- ¿Mismo backend FastAPI Arnaldo o nuevo en Lovbot Hetzner?
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

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22]] — sesión donde Robert propuso la idea + Arnaldo decidió Postgres + mockup HTML implementado
- Chat WhatsApp Arnaldo↔Robert 2026-04-22 (capturas en sesión)
