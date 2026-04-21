---
title: "Inmobiliaria Demo (Micaela) — base Airtable modelo"
type: producto
proyecto: mica
tags: [airtable, base-modelo, system-ia, workspaces]
---

# Inmobiliaria Demo (Micaela) — base Airtable modelo

## Qué es

Base Airtable única y canónica del ecosistema System IA (proyecto de [[micaela-colmenares]]). Es la **plantilla maestra** que se va a duplicar para cada cliente real futuro de Mica, manteniendo aislamiento físico entre clientes (regla #0 del ecosistema).

Equivalente conceptual a [[lovbot-crm-modelo]] pero en Airtable en vez de Postgres.

## Identificación

- **Base ID**: `appA8QxIhBYYAHw0F`
- **Nombre**: "Inmobiliaria Demo (Micaela)"
- **Workspace Airtable**: System IA (cuenta de Arnaldo)
- **URL UI**: `https://airtable.com/appA8QxIhBYYAHw0F`

## Datos de ejemplo ("demo")

- **19 leads reales** en tabla `Clientes` (Héctor Vargas, Jorge Ramírez, Lucas Romero, Fernanda Aguirre, Innovación Digital, Sebastián Torres, Valeria Ríos, Nicolás Herrera, Bobo, Sofía Fernández, Patricia Molina, Claudia Benítez, Florencia Castro, etc.). Mix de formulario + whatsapp_directo.
- **29 propiedades** en tabla `Propiedades` (casas, terrenos, deptos en San Ignacio, Apóstoles, Gdor Roca)
- **3 clientes activos** en `CLIENTES_ACTIVOS`
- **2 sesiones de bot** en `BotSessions`

Sirven como seed para demos comerciales. Los 19 leads vienen de interacciones reales de testing con el bot Evolution.

## Schema completo (17 tablas)

### Pre-existentes (5 tablas con datos)

| Tabla | Table ID | Rol | Registros |
|-------|----------|-----|-----------|
| `Clientes` | `tblonoyIMAM5kl2ue` | Leads / pipeline | 19 |
| `Propiedades` | `tbly67z1oY8EFQoFj` | Catálogo | 29 |
| `CLIENTES_ACTIVOS` | `tblpfSE6qkGCV6e99` | Compradores con cuotas | 3 |
| `BotSessions` | `tblfV9IJKv1jTCRQt` | Sesiones efímeras del bot | 2 |
| `Clientes_Agencia` | `tblclTG5G9SiNyIXj` | (rol histórico, sin uso actual) | 0 |

### Creadas 2026-04-21 (12 tablas vacías listas para usar)

#### Core (los 3 subnichos)

| Tabla | Table ID | Rol |
|-------|----------|-----|
| `Asesores` | `tblfso1JAoJaDUTLf` | Equipo de la inmobiliaria |
| `Propietarios` | `tbl7XoZ9NOfkfqQAG` | Dueños de propiedades |
| `Loteos` | `tbluM3b8vHShORORO` | Loteos del desarrollador |
| `LotesMapa` | `tblglWTmEsQ7n8ANf` | Lotes individuales con estado |
| `Contratos` | `tblQvGFwL5sZdf1jU` | Venta / reserva / alquiler |
| `Visitas` | `tblu3EHwh8eJkOPjI` | Agenda de visitas a propiedades |

#### Agencia inmobiliaria (subnicho alquileres)

| Tabla | Table ID | Rol |
|-------|----------|-----|
| `InmueblesRenta` | `tblRlLK8doYDCZIiK` | Propiedades en alquiler |
| `Inquilinos` | `tblCs0nMKxExE6lp5` | Personas que alquilan + garante |
| `ContratosAlquiler` | `tbluxdLR0bnpfLay9` | Contratos con índice IPC/ICL/UVA |
| `PagosAlquiler` | `tblUKoTFkJzk31N2m` | Mensuales con mora + comprobante |
| `Liquidaciones` | `tbl3ELdKQOTlKj4Wz` | Transferencias netas al propietario |

#### Config

| Tabla | Table ID | Rol |
|-------|----------|-----|
| `ConfigCliente` | `tblFQIoH3t7PAPNyL` | Define `tipo_subnicho` (desarrolladora/agencia/agente) |

## Conexiones actuales

| Componente | Cómo conecta |
|------------|--------------|
| Worker Mica FastAPI | env `MICA_AIRTABLE_BASE_ID=appA8QxIhBYYAHw0F` en Coolify Arnaldo |
| Backend productivo | `agentes.arnaldoayalaestratega.cloud/clientes/system_ia/demos/inmobiliaria/*` |
| CRM v2 frontend | `demos/SYSTEM-IA/dev/crm-v2.html` (dev) · `system-ia-agencia.vercel.app/system-ia/dev/crm-v2` (prod cuando Vercel redeploy) |
| Bot WhatsApp demo | Via worker FastAPI + Evolution API |
| Tenant Supabase | `mica-demo` (slug) — ver `tenants` en Supabase |

## Cuándo se usa

1. **Como demo público** — cualquier prospecto que vea `system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo` ve estos datos
2. **Como fuente para duplicación** — cuando Mica firma cliente real, se duplica esta base (via Airtable duplicate + script onboarding)
3. **Como referencia de schema** — cualquier migración de schema futura arranca acá primero

## Regla crítica

- ✅ **Nunca poner datos de clientes pagos** en esta base. Es pública a cualquiera con la URL demo.
- ✅ **Nunca borrar esta base**. Es la plantilla maestra.
- ✅ **Cuando se actualice schema** (nueva columna en Clientes, por ejemplo), aplicar primero acá.

## Onboarding cliente nuevo Mica (futuro)

Cuando llegue primer cliente pago de Mica:

1. **Duplicar base Airtable** vía la UI o API:
   ```
   POST /v0/meta/bases (con baseId=appA8QxIhBYYAHw0F, nombre nuevo)
   ```
   O más simple: "Duplicar base" desde la UI → "Inmobiliaria Demo (Micaela)" → rename a `{cliente}_crm`.

2. **Limpiar datos** (eliminar los 19 leads + 29 props + 3 activos de ejemplo).

3. **Nuevo tenant en Supabase** (`tabla tenants`):
   - slug: `{cliente}-demo` o `{cliente}` (sin guión si es definitivo)
   - `airtable_base_id`: el ID nuevo
   - `api_prefix`: `/clientes/system_ia/{cliente}`

4. **Nuevo worker en Coolify** (copiar de `workers/clientes/system_ia/demos/inmobiliaria/` a `workers/clientes/system_ia/{cliente}/`) con env vars específicas del cliente.

5. **Evolution instance** nueva para el cliente (env `{CLIENTE}_EVOLUTION_INSTANCE`).

## Historial

- **Pre-existente**: base creada por Arnaldo para demos comerciales de System IA. Tenía 5 tablas básicas (Clientes, Propiedades, CLIENTES_ACTIVOS, BotSessions, Clientes_Agencia).
- **2026-04-21**: ampliada a 17 tablas con schema completo para los 3 subnichos inmobiliarios (desarrolladora / agencia / agente). Ver [[sintesis/2026-04-21-crm-v2-mica]].

## Aparece en

- [[postgresql]] — comparar con equivalente Robert
- [[lovbot-crm-modelo]] — contraparte en Postgres para Robert
- [[sintesis/2026-04-21-crm-v2-mica]] — sesión que la amplió
- [[system-ia]] — la agencia
- [[micaela-colmenares]] — dueña de System IA

## Relaciones

- Plantilla de → `{cliente}_crm` (cada cliente real futuro de Mica)
- Consumida por → worker FastAPI Mica (repo `system-ia-agentes`)
- Tenant slug Supabase → `mica-demo`
- Provider WhatsApp actual → [[evolution-api]] (migración futura a [[meta-graph-api]] via TP Robert)
