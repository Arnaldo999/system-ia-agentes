---
title: Contratos polimórficos (venta/alquiler/reserva) con FK variable
tags: [arquitectura, data-model, crm, postgres]
source_count: 2
proyectos_aplicables: [robert, mica]
proyecto: compartido
---

# Contratos polimórficos — arquitectura CRM

## Definición

Tabla `contratos` única que modela cualquier tipo de relación económica entre un cliente y un activo del negocio, con campos `tipo` + `item_tipo` + `item_id` que definen qué está contratado.

```sql
contratos
  ├─ id, tenant_slug
  ├─ cliente_activo_id → clientes_activos(id)
  ├─ tipo        -- venta_lote | venta_casa | venta_terreno | venta_unidad | alquiler | reserva | boleto
  ├─ item_tipo   -- lote | propiedad | inmueble_renta
  ├─ item_id     -- FK lógica (no constraint real) a la tabla según item_tipo
  ├─ asesor_id → asesores(id)
  ├─ fecha_firma, monto, moneda
  ├─ cuotas_total, cuotas_pagadas, monto_cuota, proximo_vencimiento, estado_pago
  └─ notas, created_at, updated_at
```

## Por qué polimórfico y no N tablas específicas

Modelo alternativo (descartado): `contratos_venta_lote`, `contratos_venta_casa`, `contratos_alquiler`... — N tablas con estructura similar. Problema: consultar "todos los contratos de Pedro" requiere UNION ALL de N tablas, agregar un tipo nuevo requiere migración, y la UI tiene que branchear para cada caso.

Modelo elegido (polimórfico): 1 sola tabla, query simple, fácil extender. Las relaciones específicas de cada tipo se hacen con tablas extra opcionales:

- `alquileres` (1:1 con contratos donde tipo='alquiler') tiene fechas, garante, monto_mensual
- Los contratos de venta usan las columnas cuotas_* directamente en `contratos`
- Si mañana aparece tipo `leasing` o `permuta`, se agrega el valor al enum sin schema changes

## FK polimórfica — cómo resolverlo

`item_id` apunta a 3 tablas distintas según `item_tipo`. Postgres no tiene FK polimórfica real, así que:

**Opción A** (elegida): FK lógica sin constraint + resolver en app.
```sql
-- NO hay FK real en item_id. La app valida item_tipo + item_id antes del INSERT.
INSERT INTO contratos (cliente_activo_id, tipo, item_tipo, item_id, ...) VALUES (...);

-- Al consultar, la app hace el JOIN dinámico según item_tipo:
SELECT c.*, 
  CASE c.item_tipo
    WHEN 'lote' THEN (SELECT l.numero_lote || '-' || l.manzana FROM lotes_mapa l WHERE l.id = c.item_id)
    WHEN 'propiedad' THEN (SELECT p.titulo FROM propiedades p WHERE p.id = c.item_id)
    WHEN 'inmueble_renta' THEN (SELECT ir.titulo FROM inmuebles_renta ir WHERE ir.id = c.item_id)
  END as item_descripcion
FROM contratos c;
```

**Opción B descartada**: 3 columnas separadas (`lote_id NULL`, `propiedad_id NULL`, `inmueble_renta_id NULL`) con CHECK constraint de que solo una esté setteada. Más rígido y no escala bien.

Trade-off Opción A: pierdes integridad referencial automática a nivel DB. Se acepta porque el control está en la capa de aplicación y las operaciones son transaccionales.

## Endpoint unificado

`POST /crm/contratos` es atómico — recibe:

```json
{
  "tenant_slug": "demo",

  // Una sola de estas 3 opciones para el cliente:
  "cliente_activo_id": 23,           // cliente existente
  "convertir_lead_id": 47,           // convertir un lead del pipeline
  "cliente_nuevo": {                 // crear directo
    "nombre": "Pedro", "apellido": "Pérez",
    "telefono": "+549...", "email": "...", "documento": "..."
  },

  // Siempre:
  "tipo": "venta_lote",
  "item_tipo": "lote",
  "item_id": 5,
  "asesor_id": 3,
  "fecha_firma": "2026-04-22",
  "monto_total": 45000,
  "cuotas_total": 24,
  "cuotas_pagadas": 0,
  "monto_cuota": 1875,
  "estado_pago": "al_dia",
  "notas": "..."
}
```

Handler ejecuta en una transacción:
1. Si `cliente_nuevo` → INSERT clientes_activos con `origen_creacion='manual_directo'` o `'activo_mapa'`
2. Si `convertir_lead_id` → SELECT del lead + INSERT clientes_activos con `lead_id=47, origen='lead_convertido'` + UPDATE lead.estado='cerrado_ganado'
3. Si `cliente_activo_id` → usar existente
4. INSERT en contratos
5. Según item_tipo: UPDATE del item a estado='vendido'/'reservado' + asignar cliente_id
6. Si tipo='alquiler' → INSERT en alquileres con campos específicos
7. COMMIT

## 3 puertas, 1 modal, 1 endpoint

Patrón UX clave del CRM Robert: tres puntos de entrada disparan el mismo modal wizard, pre-llenando distintos pasos según el contexto:

```
Puerta A — Panel Clientes Activos      Puerta B — Click lote mapa         Puerta C — Botón "Convertir" en lead
  [+ Nuevo contrato]                    (ítem pre-cargado en paso 2)       (cliente pre-seleccionado en paso 1)
       ↓                                       ↓                                    ↓
       └───────────────────────────────────────┴────────────────────────────────────┘
                                      │
                          Modal "Nuevo contrato" (3 pasos)
                          1. Cliente (existente/convertir/nuevo)
                          2. Activo (tipo + item)
                          3. Contrato (asesor + monto + cuotas + estado)
                                      │
                                      ↓
                            POST /crm/contratos (atómico)
```

Beneficio: el asesor puede arrancar el flujo desde cualquier contexto mental ("este cliente", "este lote vendido", "este lead cerró") y el sistema se adapta.

## Fuentes

- [[sintesis/2026-04-22-crm-v3-robert]]
- [[raw/robert/sesion-2026-04-22-crm-v3-robert]]

## Aplicabilidad cross-proyecto

**Robert** (Postgres): implementado y en producción. Tabla contratos con CHECK en tipo.

**Mica** (Airtable): pendiente de replicar. En Airtable se modelará con una tabla `Contratos` con campo `Tipo` (singleSelect) + campos `linkedRecord` separados para cada item_tipo (Loteos, Propiedades, InmueblesRenta) en vez de item_tipo/item_id polimórfico. Menos elegante pero necesario por las limitaciones de Airtable (no tiene FK polimórfica ni UNION).

**Arnaldo** (Maicol): no aplica hoy — el CRM de Maicol es más simple (Airtable directo con Gemini). Si en el futuro se extiende a alquileres, aplicaría el mismo patrón Mica.

## Contradicciones detectadas

Ninguna. El modelo pasó 14 smoke tests end-to-end en producción Robert.
