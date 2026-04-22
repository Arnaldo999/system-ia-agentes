---
title: Sesión Claude 2026-04-22 — CRM v3 Mica completo (persona única + contratos polimórficos Airtable)
date: 2026-04-22
type: sesion-claude
proyecto: mica
tags: [proyecto-mica, system-ia, crm-v2, airtable, persona-unica, contratos-polimorficos, refactor]
---

# Sesión 2026-04-22 — CRM v3 Mica

Replicación completa del modelo v3 que se implementó en Robert (Postgres), adaptado al stack Airtable de Mica. **UI visualmente idéntica** a Robert pero con paleta ámbar + endpoints Mica + IDs Airtable strings.

## Contexto

En la sesión anterior (misma fecha, más temprano) se completó el refactor CRM v3 en Robert:
- Persona única con roles[] acumulables
- Contratos polimórficos (tabla central + tipo + item_tipo + item_id)
- Alquileres como subset con FK 1:1 a contratos
- Modal unificado 3 pasos + 3 puertas de entrada
- Sidebar acordeón 3 grupos (Desarrolladora / Agencia / Mixto)
- Tab Relaciones en ficha de cliente
- Lotes granulares editables
- Paneles GESTIÓN-Agencia editables

El usuario pidió replicar el mismo modelo en Mica **respetando su propio ecosistema** (Airtable + Evolution + Easypanel, paleta ámbar).

## Fase 1 — Schema Airtable

### Base `appA8QxIhBYYAHw0F` antes

17 tablas. Las relevantes tenían gaps para modelo v3:
- `CLIENTES_ACTIVOS`: sin Roles, Apellido, Documento, Origen_Creacion, ni linkedRecord
- `Contratos`: sin links a personas/activos, sin campos cuotas
- `ContratosAlquiler`, `PagosAlquiler`, `Liquidaciones`: tablas flotantes sin links a nada
- `InmueblesRenta`: Asesor como texto libre, sin link a Propietario
- `LotesMapa`: sin link al Loteo padre
- `Visitas`: sin links a entidades

### Cambios aplicados via Metadata API (idempotentes)

39 campos creados en 8 tablas — todos agregados, ninguno eliminado.

**`CLIENTES_ACTIVOS`** (+14 campos):
- `Roles` (multipleSelects: `comprador | inquilino | propietario`)
- `Apellido`, `Documento`, `Ciudad`
- `Origen_Creacion` (singleSelect: `manual_directo | lead_convertido | activo_mapa | migracion_inquilino | migracion_propietario`)
- `Lead_Origen` (link → Clientes)
- `Asesor_Asignado` (link → Asesores)
- 7 inversos automáticos que crea Airtable al linkear

**`Contratos`** (+11 campos):
- `Cliente` (link → CLIENTES_ACTIVOS)
- `Asesor` (link → Asesores)
- 3 linkedRecord separados (polimorfismo en Airtable): `Lote_Asignado`, `Propiedad_Asignada`, `Inmueble_Asignado`
- `Cuotas_Total`, `Cuotas_Pagadas`, `Monto_Cuota`, `Proximo_Vencimiento`, `Estado_Pago`
- `Item_Descripcion` (texto para subtipo granular: "venta_lote - Palo Alto L-5")

**`ContratosAlquiler`** (+5): links a Contrato, Inquilino, Inmueble, Propietario, Asesor.

**`PagosAlquiler`** (+3), **`Liquidaciones`** (+3), **`InmueblesRenta`** (+2), **`LotesMapa`** (+1), **`Visitas`** (+6) también extendidas con links apropiados.

### Decisión importante — polimorfismo en Airtable

Robert usa `item_tipo + item_id` (dos columnas) para polimorfismo. Airtable NO tiene FK polimórfica — usa 3 campos `linkedRecord` separados (`Lote_Asignado`, `Propiedad_Asignada`, `Inmueble_Asignado`). Solo UNO viene setteado por contrato. Adapter serializa a la misma forma JSON que Robert al responder del endpoint.

### Limitación del campo `Tipo` en Contratos

El singleSelect `Tipo` tiene opciones pre-existentes: `venta | reserva | alquiler | boleto`. Airtable Metadata API no permite PATCH aditivo sin reescribir todo el array (operación destructiva que requiere autorización).

**Solución**: backend mapea `venta_lote/venta_casa/venta_terreno/venta_unidad` → guarda `venta` en Airtable + usa `Item_Descripcion` para el subtipo granular. Si el usuario quiere granularidad, hay que autorizar un PATCH del campo Tipo a futuro.

### Subnicho tenant mica-demo

Supabase tenant `mica-demo`: subniche cambiado de `inmobiliaria` → `mixto`. Combinado con el fix del sidebar acordeón Robert (3 grupos siempre visibles), Mica verá todos los grupos GESTIÓN desde el minuto 1.

## Fase 2 — Backend adapter `db_airtable.py`

### Helpers genéricos creados
- `_at_get_all(table)` — lista con paginación
- `_at_create(table, fields)` — crear registro
- `_at_update(table, record_id, fields)` — PATCH
- `_at_delete(table, record_id)` — DELETE
- `_at_filter(table, formula)` — filterByFormula
- `_at_get_one(table, record_id)` — SELECT by id

### Tablas v3 reales (reemplazan stubs vacíos)
- Asesores, Propietarios, Loteos, LotesMapa
- Contratos con `_at_serialize_contrato()` que unifica los 3 linkedRecord polimórficos en la respuesta JSON
- InmueblesRenta, Inquilinos, PagosAlquiler, Liquidaciones, Visitas

### Funciones persona única

- `buscar_personas(q)` — autocomplete via `filterByFormula=OR(FIND(LOWER(q), LOWER({Nombre}&"")), FIND(...Telefono...), FIND(...Email...))`, max 10
- `get_ficha_persona(id)` — ficha 360:
  1. Registro de CLIENTES_ACTIVOS por id
  2. Resuelve Lead_Origen si existe
  3. Filtra Contratos donde Cliente incluya este id
  4. Filtra Alquileres donde Contrato esté en los contratos anteriores
  5. Filtra InmueblesRenta donde Propietario incluya este id
  6. Ensambla JSON con misma estructura que Robert
- `agregar_rol_persona(cliente_id, rol)` — lee Roles actuales, si no incluye el nuevo, PATCH con array concatenado
- `crear_contrato_unificado(data)` — 3 ramas (cliente_activo_id / convertir_lead_id / cliente_nuevo). Sin transacciones Airtable — hace paso a paso con log de warnings si falla medio.
- `crear_contrato_alquiler(data)` — extensión que además crea registro en Alquileres + agrega rol inquilino al cliente
- `get_all_alquileres`, `get_contratos_by_cliente`

### Endpoints nuevos en worker.py Mica (+12)
- `GET /crm/clientes-activos/{id}/contratos`
- CRUD inmuebles-renta, inquilinos, pagos-alquiler, liquidaciones
- `GET /crm/personas/buscar?q=`
- `GET /crm/personas/{id}`
- `POST /crm/personas/agregar-rol`
- `POST /crm/contratos/alquiler`
- `GET /crm/alquileres`

### Fixes aplicados durante Fase 2
- `_check_pg()` → no-op (Mica usa Airtable, no Postgres)
- `_check_at()` — guard real sobre `db._available()`
- Todos los `record_id: int` → `record_id: str` (IDs Airtable son strings `rec...`, no enteros)
- `POST /crm/contratos` — modo v3 unificado + legacy passthrough

### CORS

Ya cubierto por `allow_origin_regex=r"https://.*\.vercel\.app"` en `main.py` del monorepo. Mica usa el mismo backend FastAPI compartido que Robert (diferente worker, mismo middleware).

### Smoke tests producción Mica
11/11 endpoints HTTP 200. Búsqueda, crear propietario con ID string, delete con ID string — todo OK.

### Commits fase 2
- `5ef5303` feat(mica): backend adapter v3 completo
- `a9dc86a` fix: quitar Origen_Creacion de tabla Contratos
- `a616f70` fix: record_id int→str en todos los endpoints CRM

## Fase 3 — Frontend

### Archivos creados en `demos/SYSTEM-IA/dev/js/`
- `panel-contrato-unificado.js` (16KB) — wizard 3 pasos, 3 puertas. IDs strings sin `parseInt`.
- `panel-inmuebles-renta.js` — CRUD
- `panel-inquilinos.js` — 2 pasos con autocomplete persona
- `panel-pagos-alquiler.js` — CRUD
- `panel-liquidaciones.js` — CRUD con cálculo neto auto

### Archivos modificados
- `_crm-helpers.js` — Authorization Bearer token en crmFetch (compat con login PIN Mica)
- `panel-propietarios.js` — reemplazado con autocomplete persona + agregar-rol
- `panel-loteos.js`, `panel-contratos.js` — paleta `#7c3aed` (purple Robert) → `#f59e0b` (ámbar Mica)

### Cambios en `crm-v2.html`
De 6467 → 7124 líneas (+657 netas):
- CSS `sg-*` del acordeón con dot ámbar
- Sidebar: 3 grupos `sg-group` reemplazando el layout plano anterior
- `modalActivo` expandido con tabs Datos / Relaciones + función `cargarRelacionesCliente`
- Paneles reales para `inmueblesRentaBody`, `inquilinosBody`, `pagosAlquilerBody`, `liquidacionesBody` (antes placeholders)
- Modal `modalInquilino` flujo 2 pasos
- Modales nuevos: `modalContratoUnificado`, `modalInmueble`, `modalPago`, `modalLiquidacion`
- Funciones inline: `sgToggle`, `sgSaveState`, `sgLoadState`, `sgUpdateDots`, `activarTabActivo`, `renderRelaciones`

### Paleta respetada
64 ocurrencias de `#f59e0b` (ámbar), **0** de `#7c3aed` (purple) en todo el HTML + JS.

### SAAS_API correcto
Frontend Mica apunta a `https://agentes.arnaldoayalaestratega.cloud` (Coolify Arnaldo donde corre el worker Mica), NO a `agentes.lovbot.ai`.

### Commit fase 3
`e3817bb` feat(crm-v2 mica): modelo v3 completo — modal unificado + sidebar + tab relaciones + paneles GESTION

## Verificación end-to-end

### Vercel producción Mica
`https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2`:
- modalContratoUnificado: 1 ✅
- sg-group: 13 ✅
- data-group="agencia": 1 ✅
- cargarRelacionesCliente: 2 ✅
- f59e0b: 64 ✅
- 7c3aed: 0 ✅

Vercel Mica deployó inmediato (cupo separado del de Robert lovbot-demos).

### Backend producción
8/8 endpoints GESTIÓN responden 200. Búsqueda persona devuelve JSON válido.

## Diferencias implementadas Mica vs Robert (inevitables por stack)

| Aspecto | Robert (Postgres) | Mica (Airtable) |
|---------|-------------------|-----------------|
| Roles | `TEXT[]` + `array_append` | `multipleSelects` + PATCH con array concatenado |
| Polimorfismo contratos | `item_tipo + item_id` (2 cols) | 3 `linkedRecord` separados + serializer unifica |
| IDs | Enteros (`15`) | Strings (`rec...`) |
| Transacciones | `BEGIN/COMMIT/ROLLBACK` | Sin transacciones — log warnings si falla parcial |
| Búsqueda | `ILIKE '%...%'` | `filterByFormula=OR(FIND(LOWER(...), LOWER({}&"")))` |
| Tipo contrato granular | CHECK + valores libres | Mapeo `venta_*` → `venta` + `Item_Descripcion` |
| DB connection | `psycopg2` con pool | Airtable REST API + helpers `_at_*` |
| Paleta UI | Purple `#7c3aed` + cyan `#06b6d4` | Ámbar `#f59e0b` + rojo `#dc2626` |
| Endpoint base URL | `agentes.lovbot.ai/clientes/lovbot/inmobiliaria` | `agentes.arnaldoayalaestratega.cloud/clientes/system_ia/demos/inmobiliaria` |

## Pendientes para sesión siguiente

1. **Validación visual del usuario** en `system-ia-agencia.vercel.app/system-ia/dev/crm-v2` — probar los flujos principales (modal unificado, tab Relaciones, paneles GESTIÓN editables, sidebar acordeón).

2. **Panel loteos granular de Mica**: hoy tiene `33KB` vs Robert `46KB` — falta portar el CRUD granular por manzana/lote (agregar manzana, agregar lote, renombrar, borrar). El backend Mica ya tiene `/crm/lotes-mapa/seguro` y `/crm/loteos/{id}/lotes`, solo falta el frontend.

3. **Granular `Tipo` en Contratos Airtable**: si el usuario quiere diferenciar `venta_lote` vs `venta_casa` dentro de la tabla Airtable, hay que autorizar un PATCH al campo `Tipo` agregando esas opciones al singleSelect.

4. **Duplicado potencial modal inquilino**: verificar que en el HTML Mica solo quede la versión nueva "2 pasos" y no coexista con una versión vieja.

## Archivos tocados (resumen)

**Backend** (`01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/system_ia/demos/inmobiliaria/`):
- `db_airtable.py` — +978 líneas
- `worker.py` — +197 líneas netas

**Frontend** (`01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/`):
- `crm-v2.html` — +657 líneas
- `js/panel-contrato-unificado.js` — NUEVO 16KB
- `js/panel-inmuebles-renta.js` — NUEVO
- `js/panel-inquilinos.js` — NUEVO
- `js/panel-pagos-alquiler.js` — NUEVO
- `js/panel-liquidaciones.js` — NUEVO
- `js/panel-propietarios.js` — reescrito
- `js/_crm-helpers.js` — Authorization header
- `js/panel-loteos.js` — paleta ámbar (CRUD granular pendiente)
- `js/panel-contratos.js` — paleta ámbar

**Doc operativo**:
- `01_PROYECTOS/02_SYSTEM_IA_MICAELA/memory/schema-airtable-v3.md` — snapshot del schema actualizado

## Fuentes

- [[wiki/entidades/system-ia]]
- [[wiki/entidades/inmobiliaria-demo-mica-airtable]]
- [[wiki/conceptos/airtable]]
- [[wiki/conceptos/persona-unica-crm]]
- [[wiki/conceptos/contratos-polimorficos]]
- [[wiki/sintesis/2026-04-22-crm-v3-mica]]
- [[raw/robert/sesion-2026-04-22-crm-v3-robert]] (hermano Robert)
