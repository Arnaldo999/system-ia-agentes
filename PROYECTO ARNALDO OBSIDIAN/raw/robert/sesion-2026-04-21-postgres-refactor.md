---
title: Sesión Claude — refactor Postgres Lovbot a arquitectura workspaces
date: 2026-04-21
source_path: ff264427-3f05-4e1a-a9c9-a3061566ef37
type: sesion-claude
proyecto: robert
tags: [postgres, refactor, arquitectura, aislamiento, workspaces, regla-0]
---

# Sesión 2026-04-21 — Refactor Postgres Lovbot

## Contexto de inicio

La sesión arrancó con Arnaldo trabajando en el reskin del CRM v2 (HTML/CSS). A medida que verificábamos cada funcionalidad, surgieron discrepancias de datos entre componentes:

- CRM mostraba 9 leads
- IA n8n decía 19 leads
- Bot escribía a una tercera DB aparentemente

La investigación reveló que el Postgres de Lovbot tenía una arquitectura desviada de lo que Arnaldo había decidido meses atrás: **una sola DB con columna `tenant_slug` compartida** en lugar de **una DB por cliente**.

## Regla #0 reafirmada

> "Ningún cliente puede ver datos de otro cliente. Mezclar datos = catastrófico."

Implementación correcta = 1 DB Postgres física por cliente (tipo workspaces Airtable). Sin `tenant_slug` compartido. Sin dependencia de código correcto para garantizar aislamiento — la separación la hace el engine Postgres.

## Acciones ejecutadas

### 1. Fix de seguridad inmediato en validator SQL n8n

Workflow `CRM IA - Ejecutar SQL` (id `0t32XZ9AuQXB9fOn`) tenía bug de inyección:

```js
// Bug:
if (query.toLowerCase().includes('tenant_slug')) return query;
```

Si el LLM incluía `tenant_slug` como SELECT-field, el validator no inyectaba el `WHERE tenant_slug='X'` de aislamiento. Acceso a datos cruzados posible.

Fix: re-inyección forzada que sanea cualquier `WHERE tenant_slug='X'` pre-existente y agrega el correcto. Después, al pasar a DBs aisladas, el validator se simplificó aún más (ya no inyecta nada).

### 2. Endpoints admin nuevos

Agregados al backend FastAPI:
- `/admin/listar-dbs` — inventario completo
- `/admin/crear-db-cliente?db=X&from_tenant=Y&from_db=Z` — duplicación robusta
- `/admin/ampliar-schema-agencia?db=X` — schema agencia
- `/admin/reducir-modelo?db=X&leads=N` — truncar DB a N filas
- `/admin/debug-db?db=X` — inspecciona tenant_slugs literales
- `/admin/debug-worker-demo` — muestra env vars que el worker ve
- `/admin/borrar-db?db=X&confirmar=si` — DROP protegido

### 3. Bug del script de copia arreglado

`crear_db_cliente.py` hacía `SELECT *` y si origen tenía 34 columnas y destino 32, fallaban los INSERTs row por row silenciosamente. Fix: intersección de columnas via `information_schema`.

### 4. BD modelo creada

`lovbot_crm_modelo` con:
- **10 leads** (truncado de 19)
- **10 propiedades** (truncado de 116)
- **3 clientes_activos** (truncado de 12)
- **15 tablas totales** cubriendo los 3 subnichos

Tablas agregadas para agencia: `inmuebles_renta`, `inquilinos`, `contratos_alquiler`, `pagos_alquiler`, `liquidaciones`, `config_cliente`.

### 5. Worker demo refactorizado

Los 3 endpoints GET (`/crm/clientes`, `/crm/propiedades`, `/crm/activos`) leían de Airtable (código legacy que no se migró cuando se pasó a Postgres). Ahora priorizan Postgres igual que los workers de Robert-cliente-real y García.

### 6. Infraestructura configurada

Coolify Hetzner (`system-ia-agentes`):
- `LOVBOT_PG_DB` cambiado a `lovbot_crm_modelo`
- `LOVBOT_TENANT_SLUG` cambiado a `demo` (estaba en `robert`)
- Redeploy exitoso

n8n credencial "Postgres account 2" (id `KrrcaHvOt03n78e8`):
- Database cambiada a `lovbot_crm_modelo`

### 7. Verificación end-to-end

Captura de Arnaldo del CRM confirmó:
- Panel Inicio: "10 Total Leads · 4 Leads Calientes"
- Panel Propiedades: "10 propiedades · datos en tiempo real"
- Chat IA: "Tienes 10 leads en tu base de datos actualmente"

Los 3 componentes sincronizados con la única fuente de verdad.

### 8. Limpieza total

Borradas:
- 26 DBs de test creadas durante el diagnóstico
- `demo_crm` (vacía)
- `lovbot_crm` (legacy 19 leads)
- `robert_crm` (legacy 38 mezclados)

De 29 DBs a 1. Protegidas contra borrado futuro: `postgres`, `template0`, `template1`, `lovbot_crm_modelo`.

## Aprendizajes

1. **Trazar el flujo real antes de diagnosticar**. Durante horas asumí que el CRM leía de una DB diferente a la IA. Cuando por fin auditamos con `listar-dbs` + `debug-worker-demo`, todo se aclaró en 5 minutos.

2. **Los env vars silenciosos son un asesino**. `LOVBOT_TENANT_SLUG=robert` en un worker que ahora apunta a una DB con solo `tenant_slug='demo'` → 0 leads devueltos, sin error.

3. **El script `crear_db_cliente.py` existía desde el 14-abril pero nunca se ejecutó en serio**. La arquitectura correcta la tenía Arnaldo clara hace tiempo — fallamos en la ejecución.

4. **Errores silenciosos en psycopg2**: `INSERT` que falla por columna inexistente da error row-level pero el resumen del script mostraba 0 sin contexto. Agregar `primer_error` al resumen salvó una hora de debug.

## Recursos generados

- Endpoints admin listos para onboarding de cualquier cliente nuevo
- Script duplicación robusto (cols comunes)
- Validator n8n simplificado (sin lógica tenant)
- DB modelo `lovbot_crm_modelo` como plantilla única

## Próximos pasos (para otra sesión)

1. Refactor del código Python del worker demo: quitar referencias a `tenant_slug` (62 líneas). No urgente.
2. `ALTER TABLE DROP COLUMN tenant_slug` en las 15 tablas. No urgente, sin impacto.
3. Borrar env var `LOVBOT_TENANT_SLUG` después del refactor del código. No urgente.
4. Cuando llegue primer cliente real: ejecutar onboarding con `crear-db-cliente?db={slug}_crm&from_db=lovbot_crm_modelo`.

## Commits relevantes

En repo `Arnaldo999/system-ia-agentes` (branch master → main):
- `722617d` — feat(admin): from_db param en crear-db-cliente
- `859fc14` — feat(admin): /listar-dbs
- `34b16cd` — feat(admin): /borrar-db
- `e8f6bee` — feat(admin): /debug-db
- `35e91a7` — fix(admin): copiar_datos robusto con cols comunes
- `b4abac0` — feat(admin): reducir-modelo + ampliar-schema-agencia
- `b393eba` — fix(demo-worker): endpoints GET leen Postgres no Airtable
- `14481f5` — feat(admin): debug-worker-demo
- `b245635` — chore(admin): relajar protección borrar-db
