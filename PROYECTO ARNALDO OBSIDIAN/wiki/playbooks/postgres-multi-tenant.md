---
name: Playbook — PostgreSQL multi-tenant (workspaces por cliente)
description: Crear BD Postgres aislada para cada cliente de Lovbot (o similar). Patrón "workspaces" tipo Airtable — cada cliente su BD separada, nunca tenant_slug compartido. Aplica principalmente a Robert (Lovbot) y futuros clientes pagos.
type: playbook
proyecto: compartido
tags: [postgres, multi-tenant, workspaces, robert, lovbot, bd, playbook]
version: 1
ultima_actualizacion: 2026-04-24
casos_aplicados: [lovbot_crm_modelo, robert_demo, maria_crm_planned]
regla_padre: feedback_REGLA_postgres_workspaces.md
---

# Playbook — PostgreSQL multi-tenant (workspaces)

> **Regla irrompible padre**: cada cliente Lovbot tiene **su propia BD Postgres** separada. NUNCA `tenant_slug` compartido dentro de una misma BD. Mezclar datos de clientes = catastrófico.
>
> Ver `feedback_REGLA_postgres_workspaces.md` en auto-memory.

## Principio: "Workspaces" tipo Airtable

Igual que Airtable: cada cliente tiene su propio "workspace" (BD) con sus tablas. Datos físicamente separados. Solo comparten:
- El servidor Postgres (mismo Coolify Hetzner)
- El schema (duplicado de `lovbot_crm_modelo`)
- El backend FastAPI (routing por `cliente_id` → BD correspondiente)

## BDs en el ecosistema

| BD | Cliente | Estado | Notas |
|----|---------|--------|-------|
| `lovbot_crm_modelo` | — (template) | ✅ Modelo único | 10 leads + 10 props + 3 activos + 15 tablas schema completo |
| `lovbot_crm` | Demo Lovbot (tenant `demo`) | ✅ Activo | Usado por bot demo Robert |
| `lovbot_agencia` | Agencia Lovbot (interno Robert) | ✅ Activo | CRM que usa Robert internamente |
| `maria_crm` | Cliente María (hipotético/pendiente) | 📋 Patrón a replicar | |

**Principio**: solo `lovbot_crm_modelo` es el template. Nuevas BDs se **duplican** desde ahí, no desde `lovbot_crm` (que tiene datos demo específicos).

---

## Pasos exactos — crear BD cliente nuevo (total ~15 min)

### Precondiciones

- [ ] Cliente firmó contrato (es pago)
- [ ] Cliente tiene Postgres en el Coolify Hetzner de Robert o uno dedicado
- [ ] Conectividad verificada desde el backend `agentes.lovbot.ai`
- [ ] Decidido nombre de BD: convención `{cliente_slug}_crm` (ej: `maria_crm`, `juan_inmob_crm`)

### Paso 1 — Verificar BD modelo actualizada (2 min)

Antes de duplicar, asegurarse que `lovbot_crm_modelo` está al día con el último schema:

```sql
\c lovbot_crm_modelo

-- Listar tablas
\dt

-- Debe tener al menos:
-- clientes_activos, contratos, alquileres, leads, lotes, propiedades,
-- inmuebles, sesiones, mensajes, waba_clients, ... (15 tablas v3)
```

Si hay una tabla nueva que el modelo NO tiene (ej: `waba_clients` agregado después), ver **Gotcha #1** antes de continuar.

### Paso 2 — Endpoint admin para crear BD (5 min)

Existe endpoint (ver `feedback_postgres_workspaces_implementado.md`):

```bash
curl -X POST "https://agentes.lovbot.ai/admin/crear-db-cliente" \
  -H "Authorization: Bearer $LOVBOT_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cliente_slug": "maria",
    "nombre_db": "maria_crm",
    "copiar_desde": "lovbot_crm_modelo",
    "incluir_datos_seed": false
  }'

# Respuesta esperada:
# {"success": true, "db_created": "maria_crm", "tables_cloned": 15}
```

Lo que hace internamente:
1. `CREATE DATABASE maria_crm TEMPLATE lovbot_crm_modelo`
2. Registra la BD en `lovbot_agencia.clientes_pagos`
3. Inyecta env var `MARIA_DB_URL` en Coolify (automático)
4. Opcionalmente carga seed data (10 leads demo, 10 props demo) si `incluir_datos_seed=true`

### Paso 3 — Configurar routing en backend (3 min)

El backend debe poder resolver "cliente X → BD Y". Patrón:

```python
# En workers/clientes/lovbot/maria/worker.py
import os
from sqlalchemy import create_engine

DB_URL = os.getenv("MARIA_DB_URL")  # inyectada por admin endpoint
engine = create_engine(DB_URL, pool_pre_ping=True)

def get_session():
    # sesión por request, NO global
    ...
```

### Paso 4 — Verificar schema clonó completo (2 min)

```bash
# Listar tablas en la nueva BD
psql $MARIA_DB_URL -c "\dt"

# Debe mostrar las 15 tablas del modelo
# Si falta alguna, ir a Gotcha #1
```

### Paso 5 — Setup tabla `waba_clients` si aplica (3 min)

**Gotcha crítico** (2026-04-23): la BD modelo NO incluye `waba_clients` por migración histórica. Si el cliente usa Meta Graph API, agregar manualmente:

```bash
# Setup tabla
curl -X POST "https://agentes.lovbot.ai/admin/waba/setup-table" \
  -H "Authorization: Bearer $LOVBOT_ADMIN_TOKEN" \
  -d '{"db_name": "maria_crm"}'

# Registrar número existente
curl -X POST "https://agentes.lovbot.ai/admin/waba/register-existing" \
  -H "Authorization: Bearer $LOVBOT_ADMIN_TOKEN" \
  -d '{
    "db_name": "maria_crm",
    "phone_id": "<META_PHONE_ID>",
    "tenant_slug": "maria"
  }'
```

Ver `feedback_bug_waba_clients_migraciones.md`. **Fix durable pendiente**: incluir `waba_clients` en el seed de `lovbot_crm_modelo`.

### Paso 6 — Smoke test (2 min)

```bash
# 1. Conectividad
psql $MARIA_DB_URL -c "SELECT current_database(), now();"

# 2. Schema OK
psql $MARIA_DB_URL -c "SELECT count(*) FROM clientes_activos;"

# 3. Worker puede conectar
curl "https://agentes.lovbot.ai/clientes/lovbot/maria/health"
```

### Paso 7 — Documentar en wiki (3 min)

Crear `wiki/entidades/cliente-maria.md` con:
- Nombre de BD
- Tipo de contrato
- Fecha alta
- Scopes configurados (WhatsApp provider, CRM, social)
- Link a ficha comercial

---

## Gotchas conocidos

### Gotcha #1 — `waba_clients` NO está en modelo

**Síntoma**: bot nuevo deja de responder tras migración. Error 500 buscando `waba_clients`.

**Causa**: tabla `waba_clients` se agregó al schema después de que `lovbot_crm_modelo` fue congelado. Las nuevas BDs clonadas del modelo NO la tienen.

**Solución temporal** (hasta arreglar modelo): correr scripts `setup-table` + `register-existing` (ver paso 5).

**Fix durable pendiente**: agregar `waba_clients` al seed de `lovbot_crm_modelo`. Ver `feedback_bug_waba_clients_migraciones.md`.

### Gotcha #2 — No compartir tenant_slug

**Síntoma**: en una BD "compartida", dos clientes con `tenant_slug='demo'` pisan datos entre sí.

**Causa**: alguien pensó "uso una sola BD con `tenant_slug` para ahorrar recursos".

**Solución**: regla padre **`feedback_REGLA_postgres_workspaces.md`** — NUNCA. Cada cliente su BD. No es optimización, es seguridad.

### Gotcha #3 — Demo `lovbot_crm` tenant `demo`

**Caso excepción permitido**: la BD `lovbot_crm` tiene `tenant_slug='demo'` para el bot demo. Pero es sandbox público, **NO clientes reales**. Los clientes reales van a BD dedicada desde día 1.

### Gotcha #4 — Duplicar con CREATE DATABASE TEMPLATE

**Funciona solo si NADIE está conectado al template**. Si hay una sesión activa en `lovbot_crm_modelo`, Postgres bloquea la duplicación.

**Solución**: matar sesiones primero:

```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE datname = 'lovbot_crm_modelo' AND pid <> pg_backend_pid();
```

### Gotcha #5 — Env var `{CLIENTE}_DB_URL` en Coolify

El endpoint admin inyecta la env var, pero Coolify a veces NO rebuildea el container automáticamente. Después de crear la BD, **force rebuild manual** del worker que la va a consumir.

Ver `feedback_REGLA_coolify_cache_force.md`.

### Gotcha #6 — Backup antes de DROP

Jamás hacer `DROP DATABASE cliente_crm` sin:
1. `pg_dump cliente_crm > backup_YYYYMMDD.sql`
2. Confirmar con el usuario
3. Verificar que el cliente canceló contrato

Las BDs de clientes son intocables. Solo el dueño (Robert/Arnaldo) autoriza destruir.

---

## Checklist antes de dar por lista una BD nueva

- [ ] BD creada con `CREATE DATABASE ... TEMPLATE lovbot_crm_modelo`
- [ ] Registrada en `lovbot_agencia.clientes_pagos`
- [ ] Env var `{CLIENTE}_DB_URL` inyectada en Coolify
- [ ] 15 tablas clonadas del modelo (verificar con `\dt`)
- [ ] `waba_clients` agregada si cliente usa Meta Graph
- [ ] Worker del cliente puede conectar (`/health` OK)
- [ ] Smoke test: insertar lead test + borrar
- [ ] Wiki: página `wiki/entidades/cliente-{slug}.md`
- [ ] Sin `tenant_slug` compartido con otro cliente

---

## Otros patrones relacionados

### Migraciones sobre BDs en producción

**Regla**: cambios de schema van primero a `lovbot_crm_modelo`, se testean en `lovbot_crm` (demo), y SOLO después se aplican a BDs de clientes reales con backup previo.

Nunca tocar schema de BD cliente sin:
1. Backup (`pg_dump`)
2. Diff del cambio
3. Ventana de mantenimiento coordinada con el cliente

### Onboarding desde `/public/waba/onboarding`

Los clientes nuevos del ecosistema Lovbot **no se crean manualmente**. Entran por:

```
https://agentes.lovbot.ai/public/waba/onboarding
```

Ese endpoint:
1. Pide datos del cliente (nombre, phone_id Meta, agencia)
2. Crea BD automática (`{slug}_crm`)
3. Registra tenant en `lovbot_agencia.clientes`
4. Inyecta env vars
5. Redirige al cliente a login

Ver `feedback_embedded_signup_compartido.md`.

### Tenants Supabase (caso Mica)

Mica NO usa Postgres — usa Airtable. Los "tenants" Mica son registros en Supabase `clientes` (multi-tenant por filas). Ver playbook #5 `airtable-schema-setup`.

---

## Histórico de descubrimientos

- **2026-04-18** — Limpieza tenants Supabase. Solo `demo` (lovbot→PG) y `mica-demo` (system-ia→Airtable) válidos.
- **2026-04-21** — Postgres workspaces IMPLEMENTADO. `lovbot_crm_modelo` como BD modelo única. Endpoints admin listos.
- **2026-04-21** — Embedded signup compartido via TP Robert. Routing condicional por agencia.
- **2026-04-23** — Bug `waba_clients` no clona. Fix manual via setup-table + register-existing.
- **2026-04-23** — CRM agencia Lovbot LIVE (`lovbot_agencia`).

---

## Referencias cruzadas

- `feedback_REGLA_postgres_workspaces.md` — regla padre irrompible
- `feedback_postgres_workspaces_implementado.md` — estado técnico
- `feedback_bug_waba_clients_migraciones.md` — bug conocido
- `feedback_embedded_signup_compartido.md` — onboarding automático
- `wiki/conceptos/postgresql.md` — referencia general
- `wiki/entidades/lovbot-crm-modelo.md` — ficha BD modelo
