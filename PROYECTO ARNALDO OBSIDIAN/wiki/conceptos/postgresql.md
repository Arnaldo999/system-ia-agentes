---
title: "PostgreSQL Lovbot — arquitectura workspaces"
tags: [postgresql, base-de-datos, robert, lovbot, workspaces, regla-0]
source_count: 2
proyectos_aplicables: [robert]
---

# PostgreSQL Lovbot — arquitectura workspaces (estilo Airtable)

## Definición

Base de datos relacional PostgreSQL, corriendo como container Docker dentro de [[coolify-robert]] en [[vps-hetzner-robert]]. Es la **única base de datos del ecosistema Lovbot** del proyecto [[robert-bazan]].

Desde **2026-04-21** adopta arquitectura de **workspaces** (1 DB por cliente, tipo Airtable):
- **1 instancia Postgres** física (Coolify Hetzner)
- **1 database aislada por cliente** dentro (cada cliente su workspace)
- **Ningún `tenant_slug` compartido** entre clientes — aislamiento físico por engine

Ver [[sintesis/2026-04-21-refactor-postgres-workspaces]] para el detalle del refactor.

## Quién la usa

- ✅ [[robert-bazan]] (Lovbot.ai) → único proyecto que usa PostgreSQL
- ❌ [[arnaldo-ayala]] → usa [[airtable]] (distinto stack)
- ❌ [[micaela-colmenares]] → usa [[airtable]] `appA8QxIhBYYAHw0F`
- ❌ [[maicol]], [[lau]] → usan Airtable (son clientes de Arnaldo)

## Estado actual del cluster

### DBs activas (post-limpieza 2026-04-21)

| DB | Rol | Contenido |
|----|-----|-----------|
| **`lovbot_crm_modelo`** | 🎯 **BD modelo — plantilla para clientes nuevos** | 10 leads + 10 props + 3 activos demo; 15 tablas schema completo |

**Total: 1 DB.** De 29 DBs que había el 21-04 (por tests + legacy), se depuró a la modelo única.

### Ubicación

- Host interno Docker: `lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc` (Coolify id)
- Host público: `5.161.235.99`
- Port: `5432`
- User admin: `lovbot`
- Database default: `lovbot_crm_modelo`

## Schema completo — soporte 3 subnichos desde día 0

La DB modelo incluye **15 tablas** para cubrir los 3 tipos de cliente inmobiliario sin migraciones posteriores.

### Core (los 3 subnichos usan)

- `leads` — prospectos del bot WhatsApp (BANT, score, estado)
- `propiedades` — catálogo inmueble
- `clientes_activos` — clientes en proceso o con cuotas
- `asesores` — equipo
- `propietarios` — dueños de inmuebles
- `contratos` — contratos genéricos (venta, reserva, alquiler)
- `visitas` — agenda

### Desarrolladora (loteos)

- `loteos` — loteos del desarrollador
- `lotes_mapa` — cada lote individual con coordenadas y estado

### Agencia inmobiliaria (alquileres) — nuevas en 2026-04-21

- `inmuebles_renta` — propiedades en alquiler con estado y propietario
- `inquilinos` — personas que alquilan, con garante y documentación
- `contratos_alquiler` — contratos con índice de ajuste (IPC/ICL/UVA)
- `pagos_alquiler` — mensuales con mora, comprobante, estado
- `liquidaciones` — transferencias netas al propietario

### Config

- `config_cliente` — define `tipo_subnicho` del cliente (desarrolladora/agencia/agente)

## Conexiones actuales

| Componente | Cómo conecta |
|------------|--------------|
| Worker demo FastAPI | env `LOVBOT_PG_DB=lovbot_crm_modelo` en Coolify Hetzner |
| Credencial n8n "Postgres account 2" (id `KrrcaHvOt03n78e8`) | Database: `lovbot_crm_modelo` |
| Bot WhatsApp demo | (a través del worker FastAPI) |
| CRM frontend `/dev/crm-v2` | (a través del worker FastAPI) |

## Endpoints admin disponibles

Todos bajo `https://agentes.lovbot.ai/admin/`. Requieren conocer la URL (sin auth adicional por ahora — ojo con exponerlos públicamente).

| Endpoint | Uso |
|----------|-----|
| `GET /listar-dbs` | Inventario completo de DBs + conteos por tabla + tenant_slugs detectados |
| `GET /crear-db-cliente?db=X&from_tenant=Y&from_db=Z` | Duplicar DB: crea `X`, copia schema, opcionalmente copia filas de `from_db` donde tenant_slug=`from_tenant` |
| `GET /ampliar-schema-agencia?db=X` | Agregar 6 tablas de subnicho agencia (idempotente) |
| `GET /reducir-modelo?db=X&leads=N&propiedades=N&clientes_activos=N` | Trunca a N filas por tabla (deja los IDs más bajos) |
| `GET /debug-db?db=X` | Inspecciona tenant_slugs literales + muestras de leads |
| `GET /debug-worker-demo` | Muestra env vars y config que el worker tiene en RAM |
| `GET /borrar-db?db=X&confirmar=si` | DROP DATABASE (protegido contra `postgres`, `template0/1`, `lovbot_crm_modelo`) |

## Onboarding nuevo cliente

```bash
# 1. Duplicar BD modelo para el cliente (con o sin datos demo)
curl "https://agentes.lovbot.ai/admin/crear-db-cliente?db={slug}_crm&from_db=lovbot_crm_modelo"
# → crea `{slug}_crm` con schema completo + datos de muestra

# 2. En Coolify: crear nuevo servicio worker con env vars específicos
#    LOVBOT_PG_DB={slug}_crm
#    LOVBOT_TENANT_SLUG=demo
#    + resto de stack Lovbot (CLOUDINARY, OPENAI, etc.)

# 3. En n8n: nueva credencial Postgres (idealmente) apuntando a {slug}_crm
#    O cambiar dinámicamente si se mantiene 1 workflow

# 4. Crear tenant en Supabase (tabla tenants) con slug, api_url, api_prefix
```

## Módulo Python del bot

- `workers/demos/inmobiliaria/db_postgres.py` — capa de acceso del demo ([[lovbot-crm-modelo]])
- `workers/clientes/lovbot/robert_inmobiliaria/db_postgres.py` — capa del worker de Robert real (histórico)
- `workers/clientes/lovbot/inmobiliaria_garcia/db_postgres.py` — capa de García (histórico)

Funciones estándar: `get_all_leads`, `get_all_propiedades`, `get_all_activos`, `registrar_lead`, `update_lead`, `delete_lead`, etc.

## Seguridad del workflow n8n IA

Validator SQL (nodo "Validar SQL" del workflow `CRM IA - Ejecutar SQL` id `0t32XZ9AuQXB9fOn`):
- Solo permite `SELECT`
- Bloquea `DROP`, `TRUNCATE`, `DELETE`, `UPDATE`, `ALTER`, `INSERT`, `CREATE`, `GRANT`, `REVOKE`, `COPY`, `information_schema`, `pg_catalog`
- Post-refactor 2026-04-21: ya no inyecta `tenant_slug` (aislamiento garantizado por DB separada)

## Regla crítica

Ver [[aislamiento-entre-agencias]] y `feedback_REGLA_postgres_workspaces.md` en auto-memory.

**Nunca más** crear DB compartida con `tenant_slug`. Si se detecta, refactorizar a DBs separadas inmediatamente. El riesgo de cross-tenant leak es catastrófico.

## ⚠️ Trampa común

- Si ves código del worker que apunta a Airtable: es **legacy sin migrar**. Lovbot se migró completamente a Postgres. Refactorizar, no preservar.
- Si ves `tenant_slug` como columna: es **residuo histórico**. Al duplicar la DB modelo para un cliente nuevo, la columna queda pero solo tiene un valor único — es inofensiva. El aislamiento es por DB, no por columna.

## Fuentes que lo mencionan

- [[sintesis/2026-04-21-refactor-postgres-workspaces]] (refactor a workspaces)
- `raw/robert/sesion-2026-04-21-postgres-refactor.md`
- _Pendiente ingestar_: `project_postgres_migration.md`, `project_robert_bot_sprint1.md`, `docs/CRM-COMPLETO-MULTISUBNICHO.md` en `01_PROYECTOS/03_LOVBOT_ROBERT/docs/`.
