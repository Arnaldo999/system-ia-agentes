---
title: Sesión Claude 2026-04-22 — CRM v3 Robert completo (contratos polimórficos + persona única)
date: 2026-04-22
type: sesion-claude
proyecto: robert
tags: [proyecto-robert, crm-v2, postgres, contratos-polimorficos, persona-unica, refactor]
---

# Sesión 2026-04-22 — CRM v3 Robert

Maratón de refactor del CRM v2 de Robert. Partimos de un CRM donde Clientes/Leads/Inquilinos/Propietarios/Activos estaban desconectados y terminamos con un modelo normalizado de **persona única + contratos polimórficos + alquileres**, todo con UI unificada y en producción.

## Contexto inicial

El usuario detectó que:
1. Los paneles de "GESTION - Agencia" (InmueblesRenta, Inquilinos, ContratosAlquiler, Liquidaciones) eran placeholders puros en el HTML.
2. Cuando se asignaba un cliente a un lote vendido, no se mostraba ningún dato del cliente al clickear el lote.
3. Los leads del bot no se podían "convertir" a clientes activos con un click.
4. Un mismo Pedro podía ser lead + comprador + inquilino + propietario sin que el sistema supiera que son la misma persona.

## Decisiones clave del usuario (no discutidas, solo implementadas)

1. **"Opción C — 3 puertas, 1 modal, 1 endpoint"** para crear contratos:
   - Puerta A: desde panel Clientes Activos
   - Puerta B: desde click en lote disponible del mapa
   - Puerta C: desde botón "Convertir" en lead del kanban

2. **Leads y Clientes NO se fusionan** — son entidades distintas, pero un lead se puede convertir a cliente manteniendo trazabilidad con `lead_id`.

3. **Persona única con roles múltiples** — una misma persona puede ser comprador + inquilino + propietario simultáneamente. Los únicos que le interesan a la inmobiliaria son las personas para controlar, cobrar, vender.

4. **Visualmente el UI queda igual** — refactor es solo lógica. Los paneles (Clientes Activos, Inquilinos, Propietarios, Inmuebles en renta) mantienen su tabla y estructura.

## Arquitectura implementada

### Base de datos Postgres `lovbot_crm_modelo`

Schema final:

```sql
-- Persona única (antes "clientes_activos")
clientes_activos
  id, tenant_slug
  nombre, apellido, telefono, email, documento
  lead_id NULL REFERENCES leads(id)         -- trazabilidad al lead origen
  origen_creacion                           -- 'lead_convertido' | 'manual_directo' | 'activo_mapa' | 'migracion_inquilino' | 'migracion_propietario'
  roles TEXT[] DEFAULT ['comprador']        -- NUEVO: array de roles
  created_at, updated_at
  -- (columnas legacy: Propiedad string, estado_pago, cuotas_* — quedan por compat)

-- Contratos polimórficos (nuevo nodo central)
contratos
  id, tenant_slug
  cliente_activo_id REFERENCES clientes_activos(id)
  tipo        -- venta_lote | venta_casa | venta_terreno | venta_unidad | alquiler | reserva | boleto
  item_tipo   -- lote | propiedad | inmueble_renta
  item_id     -- FK lógica según item_tipo
  asesor_id REFERENCES asesores(id)
  fecha_firma, monto, moneda
  cuotas_total, cuotas_pagadas, monto_cuota, proximo_vencimiento, estado_pago
  notas, created_at, updated_at

-- Alquileres (subset de contratos tipo='alquiler' con campos extra)
alquileres
  id, tenant_slug
  contrato_id UNIQUE REFERENCES contratos(id) ON DELETE CASCADE
  fecha_inicio, fecha_fin
  monto_mensual, deposito_pagado
  estado      -- vigente | atrasado | finalizado | rescindido
  garante_nombre, garante_telefono, garante_dni
  created_at, updated_at

-- Tablas de items físicos (ya existían)
lotes_mapa    -- con UNIQUE(tenant, loteo_id, manzana, numero_lote)
propiedades
inmuebles_renta
  id, titulo, tipo, ciudad, barrio, propietario_id REFERENCES clientes_activos(id)
  precio_mensual, expensas, moneda, disponible, asesor_asignado
  disponible_desde, amoblado, permite_mascotas

inquilinos    -- tabla legacy, mantenida por compat
propietarios  -- tabla legacy, mantenida por compat
```

### Endpoints nuevos en worker Robert

| Método | Path | Uso |
|--------|------|-----|
| POST | `/crm/contratos` | Endpoint unificado — 3 ramas: cliente_activo_id / convertir_lead_id / cliente_nuevo |
| POST | `/crm/contratos/alquiler` | Extensión con campos específicos de alquiler + crea registro en tabla alquileres |
| GET | `/crm/clientes-activos/{id}/contratos` | Lista contratos de un cliente |
| GET | `/crm/personas/buscar?q={termino}` | Autocomplete — busca por nombre/tel/email/documento en clientes_activos |
| GET | `/crm/personas/{id}` | Ficha 360 — devuelve persona + lead_origen + contratos + alquileres + inmuebles_propios |
| POST | `/crm/personas/agregar-rol` | Agrega un rol al array (`ARRAY_APPEND`) |
| GET/POST/PATCH/DELETE | `/crm/inmuebles-renta` | CRUD completo |
| GET/POST/PATCH/DELETE | `/crm/inquilinos` | CRUD legacy |
| GET/POST/PATCH/DELETE | `/crm/pagos-alquiler` | CRUD |
| GET/POST/PATCH/DELETE | `/crm/liquidaciones` | CRUD |
| GET | `/crm/loteos/{id}/lotes` | Lista lotes agrupados por manzana |
| POST | `/crm/lotes-mapa/seguro` | Crea lote individual con anti-duplicado |
| DELETE | `/crm/lotes-mapa/{id}/seguro` | Solo si estado=libre |
| POST/PATCH/DELETE | `/crm/loteos/{id}/manzana[/{nombre}]` | Crear/renombrar/borrar manzana completa |
| POST | `/admin/migrar-v3-normalizado` | Idempotent — crea tablas si no existen + migra datos legacy |
| POST | `/admin/migrar-lotes-individuales` | Convierte total_lotes=N en N registros lotes_mapa |
| POST | `/admin/fix-lotes-constraint-v2` | Dropea UNIQUE sin manzana, crea el correcto |
| POST | `/admin/diagnosticar-lotes` | Lista constraints de lotes_mapa |
| POST | `/admin/limpiar-urls-airtable` | UPDATE imagen_url=NULL donde matche airtableusercontent |
| POST | `/admin/limpiar-smoke-tests` | Borra registros con "test" en nombre |
| POST | `/admin/refactor-persona-unica` | Agrega roles[], crea alquileres, migra inquilinos/propietarios |

### Frontend

#### Modal unificado "Nuevo contrato" (3 pasos)

Archivo: `demos/INMOBILIARIA/dev/js/panel-contrato-unificado.js`

3 pasos wizard:
1. **Cliente**: radio ¿Existente / Convertir lead / Nuevo? + dropdown o form según elección
2. **Activo**: tipo (lote/casa/terreno/unidad/alquiler/otro) + dropdown de item disponible
3. **Contrato**: asesor, fecha, monto, cuotas, estado pago, notas

Submit hace POST `/crm/contratos` atómico — crea cliente (si nuevo) + contrato + marca item vendido.

3 puertas de entrada que abren el mismo modal pre-llenado según contexto.

#### Modales con autocomplete "Nuevo inquilino / propietario"

Archivo: `panel-inquilinos.js`, `panel-propietarios.js`

Paso 1: input "Buscar cliente existente" → `/crm/personas/buscar` con debounce 300ms. Si matchea → autollena (evita duplicado). Si no → crear nuevo.

Paso 2 (inquilino): datos alquiler — inmueble disponible + fechas + monto + garante.

#### Tab "Relaciones" en ficha de cliente

Modal `#modalActivo` ahora tiene 2 tabs:
- **Datos**: formulario de edición existente (no tocado)
- **Relaciones**: llama `/crm/personas/{id}` y renderiza:
  - Badges de roles (comprador/inquilino/propietario con colores distintos)
  - Lead origen (si vino del bot) con botón "Ver lead"
  - Contratos activos (tarjetas con borde izquierdo coloreado según tipo)
  - Alquileres (inmueble + fechas + monto + estado)
  - Inmuebles propios (listado)

Lazy load: solo fetch cuando el usuario clickea el tab.

#### Sistema granular de lotes

Archivo: `panel-loteos.js` (reescrito)

Antes: `loteos.total_lotes=200` dividido visualmente en manzanas fijas de 8.
Ahora: lee `lotes_mapa` agrupado por manzana. El usuario puede:
- `[+ Manzana]` crear nueva con N lotes iniciales
- `[+ lote]` en cada manzana — sugiere siguiente número libre
- `[✏️]` renombrar manzana (ej: "A" → "Norte")
- `[🗑️]` borrar manzana completa (si está vacía)
- Click derecho en lote libre → eliminar
- Click en lote libre → abre modal unificado puerta B
- Click en lote vendido → muestra cliente asignado con todos sus datos

UNIQUE constraint: `(tenant_slug, loteo_id, manzana, numero_lote)` — permite A-1, B-1, C-1 coexistir (antes bloqueaba porque solo era `(tenant, loteo, numero_lote)`).

#### Sidebar acordeón GESTIÓN

3 grupos colapsables **siempre visibles** (independientes del subnicho del tenant):
- 🏗️ DESARROLLADORA (Propiedades, Loteos, Contratos de venta)
- 🏢 AGENCIA (Inmuebles en renta, Propietarios, Inquilinos, Pagos alquiler, Liquidaciones)
- 🔀 MIXTO (Asesores, Visitas agendadas)

Persiste estado en `localStorage[crm_sidebar_groups_{tenant}]`. El subnicho solo decide cuál abre por default.

## Bugs fixeados (muchos)

| Bug | Commit | Causa raíz |
|-----|--------|-----------|
| HTTP 404 al guardar cliente activo | `b39264c` | CORS no configurado + botón modal viejo llamaba `/crm/activos/pq_N` (IDs con prefijo legacy) |
| "Resource is limited" en Vercel | — | Plan Hobby 100 deploys/día. Solución: esperar 24h. Cupo se resetea a medianoche UTC. |
| Sidebar agrupaba subnichos mezclados | — | Pre-acordeón todos planos. Migrado a sistema acordeón colapsable. |
| `tenant_slug` column does not exist | `36350ca` | DB tenía tablas preexistentes creadas por `/admin/ampliar-schema-agencia` sin `tenant_slug`. Fix: agregar columna con `IF NOT EXISTS` + cubrir ALTERs por schema real. |
| `monto_total` col inexistente en contratos | `62323f9` | Tabla `contratos` tenía `monto`, script esperaba `monto_total`. Fix: INSERT con `monto`. |
| `tenant_slug specified more than once` | `d26d634` | `_crud_generico()` construía `cols=["tenant_slug"] + keys` donde keys ya incluía tenant_slug. Fix: filtrar del dict antes. |
| UNIQUE constraint no incluía manzana (A-1 bloqueaba B-1) | `0fa97c6` + `ba5c42d` | Había DOS constraints UNIQUE — uno correcto con manzana + uno auto-generado de Postgres sin manzana. Fix: drop TODOS los UNIQUE sin manzana por **definición**, no por nombre. |
| HTTP 410 masivo en consola | `9b7eb4f` + `8fb0d73` | 10 propiedades tenían `imagen_url` apuntando a URLs firmadas `airtableusercontent.com` expiradas (data legacy de seed). Fix: UPDATE SET NULL + frontend ignora URLs Airtable con helper `getPropertyImage(p)`. |
| Lote vendido no mostraba cliente | `d5002d6` | Triple bug: (1) cargaba `/crm/clientes` (leads) en vez de `/crm/activos` (2) comparaba `c.id === "pg_16"` vs `cliente_id=16` (3) campos con mayúsculas inconsistentes `Nombre` vs `nombre`. Fix: helper `clienteMatches()` + fallback `c.Nombre || c.nombre`. |
| Auditoría 165 botones — 2 bugs confirmados | `81df11d` | (1) Panel Visitas huérfano sin nav-item en sidebar (2) función `moverLead()` muerta con `COL_MAP` obsoleto. Fix: agregar item en grupo Mixto + eliminar código muerto. |
| Vercel no tomaba pushes | — | Cupo 100 deploys/día Plan Hobby. Trigger manual con commit vacío una vez se resetea. |

## Commits principales (orden cronológico)

Repo `system-ia-agentes` (backend):
- `e71028e` feat(robert-crm-v3): contratos polimórficos + GESTIÓN agencia backend
- `17b899d` fix(robert-crm): v3 migration PARTE 0 legacy DB compat
- `e5b303e` → `36350ca` → `62323f9` → `d26d634` — fixes schema + tenant_slug duplicado
- `0671005` + `39812ef` — lotes granulares backend + frontend
- `94a93ed` — normalizar 'libre'/'disponible' en todo el stack
- `b419fdc` + `0fa97c6` + `ba5c42d` — UNIQUE constraint con manzana (v2)
- `9b7eb4f` — limpiar URLs Airtable expiradas
- `b39264c` — CORS + eliminar botón modal legacy
- `231eebf` — feedback visual de errores en panel-loteos
- `ca73425` + `9cff805` — persona única schema + modales autocomplete
- `d7b05d0` — tab Relaciones en ficha cliente

## Verificación end-to-end

Smoke tests en producción:
- ✅ POST /crm/contratos rama A (cliente_activo_id=1) → contrato_id=1
- ✅ POST /crm/contratos rama B (cliente_nuevo) → contrato_id=2
- ✅ POST /crm/contratos rama C (convertir_lead_id=1 Diego Sosa) → contrato_id=3, cliente=14
- ✅ GET /crm/clientes-activos/{id}/contratos → lista con JOIN completa
- ✅ CRUD GESTIÓN (propietarios + inmuebles-renta + inquilinos + pagos + liquidaciones) → 5/5 OK
- ✅ Lotes granulares: A-1 + B-1 + C-1 coexisten con constraint correcto
- ✅ GET /crm/personas/15 → María González con roles [comprador, inquilino], 2 contratos, 1 alquiler
- ✅ POST /crm/contratos/alquiler → contrato_id=6, alquiler_id=1, rol inquilino agregado a cliente_id=15

## Pendientes para sesión siguiente

1. **Sesión 3 — Replicar todo en Mica (Airtable)**: mismo modelo conceptual pero en Airtable base `appA8QxIhBYYAHw0F`. Adapter `db_airtable.py` tiene que espejar las funciones del `db_postgres.py` de Robert. Mica hoy tiene todas las tablas GESTIÓN como stubs `[]`.

2. **Fix subnicho Mica**: tenant `mica-demo` tiene `tipo='desarrolladora'` lo que ocultaba todo el grupo GESTIÓN-Agencia. Hoy en Robert se arregló mostrándolos todos siempre; replicar mismo patrón en Mica.

3. **Vercel deploy frontend Robert**: al momento de la sesión el cupo 100/día estaba agotado. Los commits están en GitHub, se van a deployar automáticamente cuando se resetee (~mediodía día siguiente ARG).

4. **Sync CRM dev → prod HTML** (`sync-crm-prod`) cuando el usuario valide visualmente.

5. **Precio editable por lote ya creado** — hoy se setea al crear, falta UI para editar precio de lote existente.

6. **Tab Relaciones en producción** — hoy implementado en local + pushed, pendiente deploy Vercel.

## Archivos tocados

**Backend** (`01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/`):
- `workers/clientes/lovbot/robert_inmobiliaria/worker.py` — 20+ endpoints nuevos
- `workers/clientes/lovbot/robert_inmobiliaria/db_postgres.py` — `_crud_generico()` fix + funciones nuevas
- `scripts/setup_postgres_robert_v3_normalizado.py` — migración idempotente
- `scripts/migrar_lotes_individuales.py`
- `scripts/fix_lotes_mapa_constraint.py`
- `scripts/limpiar_urls_airtable_expiradas.py`
- `main.py` — CORSMiddleware explícito

**Frontend** (`01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/`):
- `crm-v2.html` — 5 modales nuevos, sidebar acordeón, tab Relaciones, getPropertyImage helper
- `js/panel-contrato-unificado.js` NUEVO
- `js/panel-inmuebles-renta.js` NUEVO
- `js/panel-inquilinos.js` reescrito
- `js/panel-propietarios.js` reescrito con autocomplete
- `js/panel-pagos-alquiler.js` NUEVO
- `js/panel-liquidaciones.js` NUEVO
- `js/panel-loteos.js` reescrito (granular)
- `js/_crm-helpers.js` — Authorization Bearer token + error parsing

## Fuentes

- [[wiki/entidades/lovbot-ai]]
- [[wiki/entidades/lovbot-crm-modelo]]
- [[wiki/conceptos/postgresql]]
- [[wiki/sintesis/2026-04-22-crm-v3-robert]]
