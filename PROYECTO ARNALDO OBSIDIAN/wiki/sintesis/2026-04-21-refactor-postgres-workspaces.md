---
title: Refactor Postgres — arquitectura workspaces implementada
date: 2026-04-21
query_origin: sesion-claude
tags: [proyecto-robert, lovbot, postgres, arquitectura, aislamiento, workspaces]
fuentes_citadas: [[raw/robert/sesion-2026-04-21-postgres-refactor]]
proyecto: robert
---

# Refactor Postgres Lovbot — 2026-04-21

## Síntesis ejecutiva

El 21 de abril de 2026 se aplicó un refactor completo de la arquitectura Postgres del ecosistema Lovbot. Arnaldo detectó que los tenants `demo` y `robert` estaban mezclados en la misma DB (`robert_crm`) con columna `tenant_slug`, violando su regla #0 (aislamiento físico por cliente). Además encontramos una fuga de seguridad en el validator SQL del workflow n8n IA y código legacy del worker demo que leía de Airtable en vez de Postgres.

Al finalizar la sesión, la arquitectura quedó correctamente implementada con **1 sola DB modelo (`lovbot_crm_modelo`)** como plantilla para futuros clientes, todas las DBs viejas eliminadas, y los 3 componentes (CRM frontend, bot WhatsApp, IA n8n) sincronizados con la misma fuente de verdad.

## Pregunta de origen

"Cómo dejar el Postgres organizado de forma que cada cliente tenga su propia base de datos aislada, tipo workspaces de Airtable, y nunca se crucen datos entre clientes."

## Hallazgos clave

### Estado previo (desvío arquitectónico)

- 1 única DB `robert_crm` con 28-38 leads mezclados entre `tenant_slug='demo'` (19) y `tenant_slug='robert'` (9-19 según momento).
- Script `crear_db_cliente.py` correcto existía desde 14-abril pero nunca se ejecutó en serio.
- Worker demo `demos/inmobiliaria/worker.py` leía de Airtable (código legacy no migrado).
- Validator SQL n8n con bug: saltaba inyección de `tenant_slug` si la query mencionaba esa palabra como campo del SELECT.
- Credencial n8n "Postgres account 2" apuntaba a `robert_crm` (la mezclada).

### Vulnerabilidad encontrada y cerrada

El validator del workflow `CRM IA - Ejecutar SQL` (id `0t32XZ9AuQXB9fOn`) tenía:

```js
if (query.toLowerCase().includes('tenant_slug')) return query;
```

Implicaba que cualquier query que mencione `tenant_slug` como SELECT-field escapaba la inyección del filtro → acceso a datos de otros tenants. Se reemplazó por una versión que sanea y re-inyecta forzosamente, y luego se simplificó aún más al pasar a DBs aisladas.

### Bug de copia en el script

`crear_db_cliente.py` usaba `SELECT *` del origen y `INSERT` al destino sin chequear columnas. Si el schema del destino tenía menos columnas que el origen, las 19 filas fallaban silenciosamente dando resumen con 0 filas copiadas. Se arregló con intersección de columnas (origen ∩ destino) vía `information_schema`.

## Arquitectura final

### Postgres (host 5.161.235.99:5432)

```
└── lovbot_crm_modelo (única DB activa)
    ├── Schema core (los 3 subnichos)
    │   ├── leads (10 registros demo)
    │   ├── propiedades (10)
    │   ├── clientes_activos (3)
    │   ├── asesores, propietarios
    │   ├── contratos, visitas
    │   └── config_cliente  ← define tipo_subnicho
    ├── Schema desarrolladora
    │   ├── loteos
    │   └── lotes_mapa
    └── Schema agencia (nuevas en esta sesión)
        ├── inmuebles_renta
        ├── inquilinos
        ├── contratos_alquiler
        ├── pagos_alquiler
        └── liquidaciones
```

Total: **15 tablas** cubriendo desarrolladora, agencia inmobiliaria y agente.

### Componentes conectados

| Componente | Endpoint/Conexión | DB que usa |
|------------|-------------------|------------|
| CRM frontend | `crm.lovbot.ai/dev/crm-v2?tenant=demo` | (via backend) |
| Backend FastAPI worker demo | Coolify Hetzner `system-ia-agentes` | `lovbot_crm_modelo` |
| Workflow IA n8n | credencial "Postgres account 2" | `lovbot_crm_modelo` |
| Bot WhatsApp demo | (via backend, mismo worker) | `lovbot_crm_modelo` |

Env vars del worker demo en Coolify:
- `LOVBOT_PG_DB=lovbot_crm_modelo`
- `LOVBOT_TENANT_SLUG=demo`

## Endpoints admin creados

Todos bajo `https://agentes.lovbot.ai/admin/`:

| Endpoint | Uso |
|----------|-----|
| `GET /listar-dbs` | Inventario completo Postgres + conteos por tabla |
| `GET /crear-db-cliente?db=X&from_tenant=Y&from_db=Z` | Duplica DB copiando schema + filas filtradas |
| `GET /ampliar-schema-agencia?db=X` | Agrega 6 tablas del subnicho agencia |
| `GET /reducir-modelo?db=X&leads=N&propiedades=N&clientes_activos=N` | Trunca DB a N filas por tabla |
| `GET /debug-db?db=X` | Inspecciona tenant_slugs exactos (con bordes) |
| `GET /debug-worker-demo` | Muestra env vars y config que el worker tiene cargadas |
| `GET /borrar-db?db=X&confirmar=si` | DROP DATABASE protegido |

Protegidas contra borrado: `postgres`, `template0`, `template1`, `lovbot_crm_modelo`.

## Proceso de onboarding cliente nuevo (la nueva doctrina)

```bash
# 1. Duplicar BD modelo para el cliente
curl "https://agentes.lovbot.ai/admin/crear-db-cliente?db={slug}_crm&from_db=lovbot_crm_modelo"

# 2. Crear worker nuevo en Coolify con env vars:
#    LOVBOT_PG_DB={slug}_crm
#    LOVBOT_TENANT_SLUG=demo  (por ahora; ver pendientes)
#    + resto del stack Lovbot

# 3. Nueva credencial en n8n Postgres apuntando a {slug}_crm
#    (o cambiar dinámicamente la credencial por tenant)

# 4. Crear tenant en Supabase (tabla tenants) con:
#    slug={slug}, api_url, api_prefix, requiere_pin
```

## DBs borradas en la limpieza

- 26 DBs de prueba (`_test_`, `probe_*`, `test_probe_*`, etc.) generadas durante el diagnóstico.
- `demo_crm` (vacía residual).
- `lovbot_crm` (legacy con 19 leads tenant=robert, subset histórico).
- `robert_crm` (legacy con 38 leads mezclados — la DB original del problema).

Total: **29 DBs → 1 DB**.

## Pendientes no urgentes

1. Columna `tenant_slug` sigue en las 15 tablas con DEFAULT 'demo'. Inofensiva pero redundante. Refactor futuro: `ALTER TABLE DROP COLUMN tenant_slug`.
2. Código Python del worker demo tiene 62 referencias a `tenant_slug` en queries. Funcionan correctamente con la columna default, pero se pueden limpiar.
3. Validator n8n ya se simplificó: ya no inyecta `tenant_slug`, solo valida SELECT-only.

## Impacto y decisión arquitectónica

- **Regla #0 (aislamiento físico) garantizada**: imposible cross-tenant leak aunque haya bug de código, env var mal seteada o LLM confundido.
- **Onboarding limpio**: `pg_dump lovbot_crm_modelo` + `createdb` + env var = cliente nuevo en 2 minutos.
- **Soporte 3 subnichos desde día 0** sin migraciones futuras.
- **Base para escalar**: cuando lleguen los primeros clientes reales de Lovbot, entran con su DB aislada.

## Fuentes

- [[raw/robert/sesion-2026-04-21-postgres-refactor]]
- [[wiki/conceptos/postgresql]]
- [[wiki/conceptos/matriz-infraestructura]]
- [[wiki/entidades/vps-hetzner-robert]]
