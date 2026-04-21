---
title: Sesión Claude — setup CRM v2 Mica + decisión Embedded Signup compartido
date: 2026-04-21
source_path: ff264427-3f05-4e1a-a9c9-a3061566ef37
type: sesion-claude
proyecto: mica
tags: [crm-v2, airtable, setup, embedded-signup, tech-provider-robert, tenant-demo]
---

# Sesión 2026-04-21 — Setup CRM v2 Mica

## Contexto

Después de terminar el refactor Postgres workspaces de Robert y deployar su CRM v2 a producción, Arnaldo decidió replicar el mismo trabajo para System IA (proyecto de Mica), adaptando al stack Mica (Airtable + Evolution API + Coolify Arnaldo).

La sesión terminó con el CRM v2 Mica funcionando en local + decisión estratégica de Embedded Signup compartido.

## Decisiones y trabajo realizado

### 1. Decisión arquitectónica — mismo modelo que Robert, distinto stack

Mica replica la lógica del CRM v2 de Robert pero adaptada:

| Aspecto | Robert (Lovbot) | Mica (System IA) |
|---------|-----------------|-------------------|
| DB | Postgres `lovbot_crm_modelo` | Airtable `appA8QxIhBYYAHw0F` ("Inmobiliaria Demo (Micaela)") |
| WhatsApp | Meta Graph API (TP propio) | Evolution API (ahora), Meta Graph via TP Robert (próximo) |
| Orquestador | Coolify Hetzner Robert | Coolify Arnaldo (`coolify.arnaldoayalaestratega.cloud`) |
| Backend | `agentes.lovbot.ai` | `agentes.arnaldoayalaestratega.cloud` |
| Color marca | Purple/Cyan `#7c3aed` + `#06b6d4` | Ámbar/Rojo `#f59e0b` + `#dc2626` |
| Frontend Vercel | proyecto `lovbot-demos` → `crm.lovbot.ai` | proyecto `system-ia-agencia` → `system-ia-agencia.vercel.app` |

### 2. CRM v2 Mica creado en `demos/SYSTEM-IA/dev/crm-v2.html`

Clonado del de Robert, adaptado:
- Paleta ámbar/dorado + rojo (72 reemplazos de color)
- Branding "System IA" / "Inmobiliaria Demo Mica" (16 reemplazos texto)
- Endpoints apuntando a `/clientes/system_ia/*` en vez de `/clientes/lovbot/*`
- Sidebar por subnichos (desarrolladora/agencia/agente) igual que Robert

3 commits relevantes:
- `01c98f3` — feat(system-ia/crm-v2): adaptar CRM v2 a branding y stack de Mica
- `8b32da1` — feat(system-ia/airtable): crear 12 tablas CRM en base appA8QxIhBYYAHw0F
- `31a85f9` — feat(vercel): agregar rewrite /system-ia/dev/crm-v2 para CRM v2 de Mica

### 3. 12 tablas nuevas creadas en Airtable `appA8QxIhBYYAHw0F`

Base "Inmobiliaria Demo (Micaela)" pasó de **5 tablas a 17 tablas**:

**Pre-existentes (5)**:
- Clientes (19 registros reales)
- Propiedades (29)
- CLIENTES_ACTIVOS (3)
- BotSessions (2)
- Clientes_Agencia (0)

**Nuevas creadas via Airtable Metadata API (12)**:
- Core: Asesores, Propietarios, Loteos, LotesMapa, Contratos, Visitas
- Agencia: InmueblesRenta, Inquilinos, ContratosAlquiler, PagosAlquiler, Liquidaciones
- Config: ConfigCliente

Todas vacías excepto ConfigCliente que se sembró con `tipo_subnicho='desarrolladora'`.

Table IDs documentados en Obsidian: ver [[wiki/entidades/inmobiliaria-demo-mica-airtable]].

### 4. Tenant `mica-demo` en Supabase corregido

Detectado bug: `airtable_base_id` apuntaba a la base de Arnaldo (`appXPpRAfb6GH0xzV` — Inmobiliaria Demo de Maicol), pero las tablas apuntaban a Mica. El backend armaba URLs inválidas.

Fix vía PATCH directo a Supabase REST API:
- `airtable_base_id`: `appXPpRAfb6GH0xzV` → `appA8QxIhBYYAHw0F`
- `color_primario`: `#0f5c3b` (verde oscuro histórico) → `#f59e0b` (ámbar Mica)
- `color_acento`: `#b6ae9a` (beige histórico) → `#dc2626` (rojo Mica)
- `nombre`: "Inmobiliaria Demo" → "Inmobiliaria Demo Mica"
- `ciudad`: "Buenos Aires" → "Apóstoles, Misiones"

### 5. PIN de `mica-demo` reseteado a `1234`

El tenant tenía `pin_hash` pero Arnaldo no recordaba el PIN original. Se reseteó vía Supabase REST API (PATCH con SHA-256 de "1234"). Verificado con auth real: devuelve status ok + token.

### 6. 3 bugs críticos del CRM local encontrados y arreglados

**Bug 1 — HTML apuntaba a Vercel como backend** (commit 92617fe):
```js
// Mal (subagente usó Vercel como backend):
const SAAS_API = 'https://agentes.system-ia-agencia.vercel.app';
// Correcto:
const SAAS_API = 'https://agentes.arnaldoayalaestratega.cloud';
```
Vercel solo sirve HTML estático, no tiene FastAPI. Este bug causaba que no pidiera PIN, no cargara leads, y no aplicara colores (el `initTenant()` fallaba silenciosamente porque el fetch devolvía 404).

**Bug 2 — Faltaba carpeta `dev/js/`**:
El HTML referenciaba `js/_crm-helpers.js`, `js/panel-loteos.js`, etc., pero el directorio `demos/SYSTEM-IA/dev/` no tenía la carpeta `js/` que sí existe en Robert. Se copiaron los 7 archivos JS desde `demos/INMOBILIARIA/dev/js/`.

**Bug 3 — `/crm/resumenes` Mica devolvía HTTP 500**:
El handler llamaba a `_check_pg()` que exige Postgres (Mica usa Airtable). Y `db.listar_resumenes()` de Airtable no aceptaba los 4 params que el handler pasaba. Se reescribió el handler para no bloquear por Postgres + se extendió la firma del stub Airtable.

### 7. Verificación end-to-end Mica exitosa

Con todos los fixes:
- Login con PIN `1234` → OK
- Paleta ámbar correctamente aplicada
- 19 leads reales visibles en el CRM (Héctor Vargas, Jorge Ramírez, Lucas Romero, Fernanda Aguirre, Innovación Digital, Sebastián Torres, Bobo, etc.)
- Sidebar con secciones PRINCIPAL/VENTAS/GESTIÓN DESARROLLADORA/HERRAMIENTAS
- Endpoint `/crm/resumenes` ahora devuelve `{"total":0,"records":[]}` sin error
- Bot Mica webhook `/clientes/system_ia/demos/inmobiliaria/whatsapp` responde HTTP 200
- 14 de los 19 leads tienen `Llego_WhatsApp=true` (confirmación de que el bot escribe a Airtable)

### 8. Env vars Coolify Arnaldo auditadas

De las 28 env vars que el código del worker Mica busca, 23 ya están en Coolify Arnaldo. Las 5 que faltan no bloquean:
- `MICA_DEMO_AIRTABLE_TABLE_SESSIONS` — fallback hardcoded "BotSessions" (existe la tabla)
- `MICA_DEMO_MONEDA` — fallback "USD"
- `MICA_DEMO_SITIO_WEB` — opcional
- `MICA_OPENAI_API_KEY` — fallback a `OPENAI_API_KEY` genérico
- `MICA_DEMO_NUMERO_ASESOR` — Arnaldo agregó durante la sesión (= su propio número `+5493765384843`)
- `MICA_DEMO_ZONAS` — Arnaldo agregó (`San Ignacio, Gdor Roca, Apostoles, Otra Zona`)

## Decisión estratégica — Embedded Signup compartido via Tech Provider Robert

Arnaldo recibió aprobación del Embedded Signup de Meta para Robert durante esta sesión. Decisión tomada:

**El mismo número que hoy usa Mica (`+54 9 3765 00-5465`) se va a migrar del Evolution API actual al Meta Graph API oficial, conectándose al TP de Robert via Embedded Signup.**

Plan:
- Mica + clientes de Arnaldo onboardean sus números vía signup de Robert (tránsito técnico)
- Cada cliente queda en `waba_clients` con `agencia_origen=arnaldo` o `agencia_origen=mica`
- El día que Mica (o Arnaldo) saquen su propio TP, los clientes se migran con 1 click a su app propia (campo `agencia_origen` ya preparado para esto — ver [[sintesis/2026-04-20-multi-agencia-tech-provider]] si existe, o `ec33418` commit).

**Implicancia técnica**: el bot de Mica hoy corre sobre Evolution API. Cuando se migre a Meta Graph, hay que ajustar el worker para que use `workers.shared.wa_provider` con `WHATSAPP_PROVIDER=meta` y apunte al TP de Robert. **Trabajo pendiente para otra sesión.**

## Pendientes no urgentes

1. **Resúmenes IA en Mica**: stub `listar_resumenes()` retorna `[]`. Cuando Mica tenga clientes pagos se implementa tabla `ResumenesConversacion` en Airtable + función real + prompt generación con GPT-4.1-mini.

2. **Deploy Vercel Mica**: la URL de prod `system-ia-agencia.vercel.app/system-ia/dev/crm-v2` está en cola — Vercel alcanzó 100 deploys/día. Al resetearse la cuota mañana (UTC 00:00), el próximo push despliega automáticamente.

3. **Refactor a "1 base Airtable por cliente"**: igual que Robert tiene 1 DB Postgres por cliente, Mica debería tener 1 base Airtable por cliente (workspace Airtable aislado). Hoy todo está en `appA8QxIhBYYAHw0F` que es la base demo. Cuando llegue primer cliente pago de Mica: duplicar base, nuevo tenant Supabase, nuevo worker Coolify.

4. **Migración Evolution → Meta Graph via TP Robert**: según decisión estratégica arriba. Sesión futura.

## Recursos y URLs

- **CRM v2 Mica local** (mientras Vercel reabre): `http://localhost:8766/crm-v2.html?tenant=mica-demo`
- **CRM v2 Mica prod** (mañana): `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo`
- **PIN demo**: `1234`
- **Backend Mica**: `https://agentes.arnaldoayalaestratega.cloud`
- **Airtable base**: `appA8QxIhBYYAHw0F`
- **Supabase tenant slug**: `mica-demo`
- **Bot Evolution**: instancia Mica (env `MICA_DEMO_EVOLUTION_INSTANCE`)

## Fuentes relacionadas

- [[wiki/entidades/system-ia]] — la agencia
- [[wiki/entidades/micaela-colmenares]] — la dueña
- [[wiki/entidades/vps-hostinger-mica]] — infra propia Mica (no se usa para bot hoy)
- [[wiki/conceptos/airtable]] — stack Mica
- [[wiki/conceptos/evolution-api]] — WhatsApp provider actual
- [[wiki/conceptos/meta-tech-provider-onboarding]] — destino futuro
