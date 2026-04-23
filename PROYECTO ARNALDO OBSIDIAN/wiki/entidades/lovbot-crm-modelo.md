---
title: "lovbot_crm_modelo (BD Postgres modelo)"
type: producto
proyecto: robert
tags: [postgres, lovbot, bd-modelo, workspaces, plantilla]
---

# `lovbot_crm_modelo` — la BD modelo de Lovbot

## Qué es

Base de datos PostgreSQL única y canónica del ecosistema Lovbot. **Plantilla maestra** que se duplica para cada cliente nuevo. Creada el 2026-04-21 durante el [[sintesis/2026-04-21-refactor-postgres-workspaces|refactor a arquitectura workspaces]].

## Dónde vive

- Cluster: PostgreSQL en [[coolify-robert]] (Coolify Hetzner, [[vps-hetzner-robert]])
- Host: `5.161.235.99:5432`
- Nombre: `lovbot_crm_modelo`
- Usuario admin: `lovbot`
- Protegida contra borrado via endpoint `/admin/borrar-db`

## Qué contiene

### Datos de ejemplo ("demo")

- **10 leads** (con tenant_slug='demo' histórico, columna que queda residual)
- **10 propiedades** (mix de casas, departamentos, terrenos en San Ignacio/Apóstoles/zona Misiones)
- **3 clientes activos** (con cuotas de ejemplo)

Estos datos se usan como "seed" para mostrar un CRM pre-poblado a nuevos clientes durante demos. Son ficticios, anonimizados.

### Schema (15 tablas)

Ver [[postgresql]] para detalle. Cubre los 3 subnichos inmobiliarios:

- **Core (los 3 subnichos)**: leads, propiedades, clientes_activos, asesores, propietarios, contratos, visitas
- **Desarrolladora**: loteos, lotes_mapa
- **Agencia**: inmuebles_renta, inquilinos, contratos_alquiler, pagos_alquiler, liquidaciones
- **Config**: config_cliente (define el tipo de cliente)

## Quién se conecta

| Componente | Conexión |
|------------|----------|
| Worker FastAPI demo (Coolify service `system-ia-agentes`) | env var `LOVBOT_PG_DB=lovbot_crm_modelo` |
| Workflow IA n8n (credencial "Postgres account 2") | Database: `lovbot_crm_modelo` |
| Bot WhatsApp demo | Via worker FastAPI |
| CRM frontend `/dev/crm-v2?tenant=demo` | Via worker FastAPI |

## Cuándo se usa

1. **Como demo público**: cualquier prospecto que vea `crm.lovbot.ai/dev/crm-v2?tenant=demo` ve estos datos.
2. **Como fuente para duplicación**: cuando Lovbot firma un cliente nuevo, se ejecuta:
   ```
   GET /admin/crear-db-cliente?db={cliente}_crm&from_db=lovbot_crm_modelo
   ```
   que crea `{cliente}_crm` vacía (o con datos de muestra según parámetros).
3. **Como referencia de schema**: cualquier migración de schema futura arranca acá primero para validar.

## Regla crítica

- ✅ **Nunca poner datos de clientes reales** en esta DB. Es pública a cualquiera con la URL demo.
- ✅ **Nunca eliminar**. Endpoint `/admin/borrar-db` la tiene protegida.
- ✅ **Cuando se actualice schema**, aplicar primero acá, después duplicar a clientes.

## Historial

- **2026-04-21**: Creada durante refactor a workspaces. Data copiada de `tenant=demo` en la vieja `robert_crm`. Schema ampliado con tablas de agencia. Reducida a 10/10/3.
- **Previamente**: la arquitectura era 1 sola DB (`lovbot_crm` o `robert_crm`) con columna `tenant_slug` compartida entre clientes — riesgo de cross-tenant leak. Ver [[sintesis/2026-04-21-refactor-postgres-workspaces]].
- **2026-04-22 — auditoría confirmó limpieza completa de legacy**: las 3 BDs viejas (`robert_crm`, `lovbot_crm`, `demo_crm`) que existían el 2026-04-21 **ya NO están** en el cluster. Fueron eliminadas por algún agente entre el 21 y el 22. Cluster actual contiene solo `lovbot_crm_modelo` + las 3 internas Postgres (`postgres`, `template0`, `template1`). Ver [[wiki/fuentes/sesion-2026-04-22]].

## Tablas que contiene (18-19 totales, confirmado 2026-04-22)

### CRM v3 (15 tablas)

`leads`, `propiedades`, `clientes_activos`, `asesores`, `propietarios`, `contratos`, `visitas`, `loteos`, `lotes_mapa`, `inmuebles_renta`, `inquilinos`, `pagos_alquiler`, `liquidaciones`, `alquileres`, `config_cliente`.

### Infraestructura del bot (4 tablas)

- **`bot_sessions`** — sesión BANT activa (estado JSON) + historial de mensajes (array, max 20). Persistencia de la memoria del worker entre reinicios.
- **`resumenes_conversacion`** — resúmenes post-calificación de leads calientes.
- **`waba_clients`** — clientes WABA onboardeados via Embedded Signup.
- **`meta_compliance_logs`** — logs de compliance Meta Graph API.

> **Memoria del worker NO está en otra DB**. Tampoco en Chatwoot. Confirmado 2026-04-22 — ver [[wiki/fuentes/sesion-2026-04-22]] sección 5.

## Aparece en

- [[postgresql]] — concepto de la arquitectura
- [[sintesis/2026-04-21-refactor-postgres-workspaces]] — sesión que la creó
- [[wiki/fuentes/sesion-2026-04-22]] — auditoría que confirmó limpieza de legacy
- [[lovbot-ai]] — el producto Lovbot.ai
- [[robert-bazan]] — dueño de Lovbot
- [[crm-v2-modelo-robert]] — frontend HTML que consume esta BD

## Relaciones

- Plantilla de → {cliente}_crm (cada cliente real futuro)
- Corre en → [[vps-hetzner-robert]]
- Orquestada por → [[coolify-robert]]
- Consumida por → worker FastAPI demo (repo `system-ia-agentes`)
- Consultada por → n8n workflow IA
- Frontend que la lee/escribe → [[crm-v2-modelo-robert]]
