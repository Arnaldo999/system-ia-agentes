---
title: CRM v3 Robert — refactor completo (contratos polimórficos + persona única)
date: 2026-04-22
query_origin: sesion-claude
tags: [proyecto-robert, crm-v2, postgres, persona-unica, contratos-polimorficos, refactor-arquitectura]
fuentes_citadas: [[raw/robert/sesion-2026-04-22-crm-v3-robert]]
proyecto: robert
---

# CRM v3 Robert — refactor completo

## Síntesis ejecutiva

El 22 de abril de 2026 se completó un refactor arquitectónico del CRM v2 de Robert/Lovbot, pasando de un modelo fragmentado donde Clientes, Leads, Inquilinos, Propietarios y Activos estaban desconectados, a un modelo normalizado con:

1. **Persona única** — una sola tabla `clientes_activos` con campo `roles TEXT[]` donde cada persona puede ser simultáneamente `['comprador', 'inquilino', 'propietario']`. Ficha 360 consolidada.

2. **Contratos polimórficos** — tabla central `contratos` con `tipo` (venta_lote/venta_casa/alquiler/etc) + `item_tipo` + `item_id` apuntando a lote/propiedad/inmueble_renta.

3. **Alquileres extendidos** — tabla `alquileres` con datos específicos (fechas, garante) vinculada 1:1 a contratos tipo alquiler.

4. **3 puertas → 1 modal** — crear contrato desde panel Clientes, desde mapa de lotes, o convirtiendo un lead. Todas abren el mismo modal wizard unificado y hacen POST al mismo endpoint.

5. **Lotes granulares editables** — cada lote es un registro real en `lotes_mapa`. La inmobiliaria puede agregar/renombrar/eliminar manzanas y lotes individualmente. Antes era un número fijo dividido visualmente.

6. **GESTIÓN-Agencia funcional** — paneles Inmuebles en renta, Inquilinos, Pagos alquiler, Liquidaciones, Propietarios ahora tienen CRUD real. Antes eran placeholders.

Todo esto con UI visualmente idéntica a la anterior — el usuario dijo explícitamente "visualmente quiero que sea lo mismo, asi como está lo veo bien organizado", así que el refactor es solo lógica.

## Pregunta de origen

¿Cómo hacer que el CRM de Robert soporte personas con múltiples roles (comprador + inquilino + propietario), que los clientes estén sincronizados con todos los activos del negocio (lotes, casas, inmuebles de alquiler), que los leads puedan convertirse a clientes con un click manteniendo trazabilidad, y que la inmobiliaria pueda cargar/editar lotes sin limitaciones de grilla fija?

## Modelo de datos final

```
leads (pipeline del bot, no tocado)
  └─ id, nombre, tel, email, estado_seguimiento, score

clientes_activos (persona única — sufrió refactor)
  ├─ id, nombre, apellido, tel, email, documento
  ├─ lead_id → leads (trazabilidad origen)
  ├─ origen_creacion (manual/lead_convertido/activo_mapa/migracion_inquilino/etc)
  └─ roles TEXT[] — ['comprador', 'inquilino', 'propietario']

contratos (NUEVO nodo polimórfico central)
  ├─ cliente_activo_id → clientes_activos
  ├─ tipo (venta_lote/venta_casa/venta_terreno/venta_unidad/alquiler/reserva/boleto)
  ├─ item_tipo (lote/propiedad/inmueble_renta)
  ├─ item_id
  ├─ asesor_id, fecha_firma, monto, moneda
  └─ cuotas + vencimientos + estado_pago

alquileres (NUEVO subset de contratos)
  └─ contrato_id UNIQUE + fecha_inicio/fin + monto_mensual + garante + estado

lotes_mapa (refactorizado granular)
  └─ UNIQUE(tenant, loteo_id, manzana, numero_lote) — antes solo (tenant, loteo, nro)

inmuebles_renta, inquilinos, propietarios, pagos_alquiler, liquidaciones
  → tablas nuevas para GESTIÓN-Agencia, antes inexistentes
```

## Decisiones arquitectónicas clave

### 1. Persona única con roles array
Postgres `TEXT[]` + `ARRAY_APPEND` para agregar roles sin duplicar. Buscar con `'comprador' = ANY(roles)`. Al crear alquiler, si el cliente es nuevo se crea con `roles=['inquilino']`; si ya existía como comprador, se hace `UPDATE SET roles = array_append(roles, 'inquilino')`.

### 2. Compatibilidad total con tablas legacy
Las tablas `inquilinos` y `propietarios` se mantienen (no se dropean) para que los endpoints legacy sigan funcionando. Los registros nuevos van a `clientes_activos + contratos + alquileres`, pero los viejos de `inquilinos/propietarios` siguen mostrándose en sus paneles. La migración masiva fue idempotente.

### 3. Endpoint unificado POST /crm/contratos
3 ramas mutuamente excluyentes:
- `cliente_activo_id: 23` → usa cliente existente
- `convertir_lead_id: 47` → lee lead + crea cliente_activo con `lead_id=47, origen='lead_convertido'` + marca lead como `cerrado_ganado`
- `cliente_nuevo: {...}` → crea cliente directo con `origen='manual_directo'` o `'activo_mapa'`

Todo en una transacción Postgres: crea cliente → crea contrato → marca item vendido/reservado.

### 4. Modal wizard único con 3 puertas de entrada
```
Modal "Nuevo contrato" (3 pasos: Cliente → Activo → Contrato)
  ↑                    ↑                    ↑
Puerta A             Puerta B              Puerta C
Panel Clientes       Click lote mapa       Botón "Convertir"
  Activos            (lote pre-cargado)    en lead del kanban
```

### 5. Persona única no implica fusionar leads + clientes
El usuario fue claro: "Leads y Clientes no se deben mezclar, son dos activos distintos". El `lead_id` en clientes_activos es trazabilidad, no fusión. Los paneles Leads y Clientes Activos siguen siendo paneles separados con datos separados.

## Implementación distribuida

| Capa | Qué hace |
|------|----------|
| Postgres | Schema normalizado + UNIQUE constraints correctos + 5 scripts de migración idempotentes |
| Worker FastAPI | 20+ endpoints nuevos para CRUD y búsqueda + helper `_crud_generico()` corregido |
| Frontend HTML | 5 modales nuevos (contrato unificado, nueva manzana, agregar lote, inmueble, liquidación) + sidebar acordeón + tab Relaciones |
| Frontend JS | 5 archivos helper nuevos (`panel-contrato-unificado`, `panel-inmuebles-renta`, `panel-inquilinos`, `panel-pagos-alquiler`, `panel-liquidaciones`) + reescritos (`panel-loteos`, `panel-propietarios`) |
| Infra | CORSMiddleware explícito, Vercel deploy, Coolify auto-deploy, limpieza URLs Airtable legacy |

## Bugs derrotados

Lista destacada (el raw tiene tabla completa):
- `tenant_slug` duplicado en `_crud_generico()` bloqueaba todos los POST a tablas nuevas.
- UNIQUE constraint `lotes_mapa` tenía 2 constraints simultáneos (uno auto-generado de Postgres sin manzana), bloqueando coexistencia A-1 + B-1.
- 10 URLs `airtableusercontent.com` expiradas en `propiedades.imagen_url` generaban HTTP 410 masivos en consola.
- Modal viejo "Cliente solo" con `PATCH /crm/activos/pq_15` — IDs legacy con prefijo que no existían en Postgres.
- CORS no configurado → frontend en `crm.lovbot.ai` bloqueado para hacer requests a `agentes.lovbot.ai`.
- Lote vendido no mostraba cliente — triple bug: endpoint equivocado (`/crm/clientes` en vez de `/crm/activos`) + IDs con prefijo (`pg_16` vs `16`) + campos con mayúsculas inconsistentes (`Nombre` vs `nombre`).
- Vercel cupo 100 deploys/día agotado — 5 commits quedaron esperando 24h.

## Verificación

14 smoke tests E2E corridos contra producción `agentes.lovbot.ai`, todos verdes:
- 3 ramas del endpoint unificado de contratos
- CRUD de 5 tablas GESTIÓN
- Lotes granulares (constraint por manzana + CRUD + renombrar)
- Persona única con roles múltiples
- Búsqueda autocomplete
- Ficha 360 con contratos + alquileres + inmuebles propios

## Impacto

### Antes
- Pedro aparecía 4 veces (lead + cliente_activo + inquilino + propietario) sin relación
- Click en lote vendido no mostraba nada
- Modal "Nuevo cliente" saltaba tipos de activo
- Los paneles de GESTIÓN eran placeholders vacíos
- Leads pasaban a clientes copiando datos a mano

### Después
- Pedro es **UN** registro con `roles=['comprador','inquilino','propietario']`
- Click en lote vendido → modal con ficha completa del cliente + datos del contrato
- Modal unificado de 3 pasos cubre todos los tipos de activo
- Paneles GESTIÓN con CRUD real conectado a Postgres
- Botón "Convertir a cliente activo" en kanban de leads crea el cliente_activo con trazabilidad completa

### Pendiente para Mica (sesión 3)
Replicar el mismo modelo conceptual pero en Airtable base `appA8QxIhBYYAHw0F`. El adapter `db_airtable.py` debe espejar las funciones del `db_postgres.py` de Robert. Además arreglar subnicho para que Mica vea GESTIÓN-Agencia.

## Ejecución

16+ commits en 18h de trabajo (`e71028e` → `d7b05d0`). Repos:
- Backend: `Arnaldo999/system-ia-agentes` rama `main`
- Frontend: Mission Control `master` → auto-deploy Vercel `lovbot-demos`

## Fuentes

- [[raw/robert/sesion-2026-04-22-crm-v3-robert]] (raw completo)
- [[lovbot-ai]]
- [[lovbot-crm-modelo]]
- [[postgresql]]
- [[robert-bazan]]
- [[sintesis/2026-04-21-refactor-postgres-workspaces]] (contexto anterior — workspaces 1 DB por cliente)
