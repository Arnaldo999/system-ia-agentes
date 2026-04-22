---
title: Persona única con roles múltiples — arquitectura CRM inmobiliario
tags: [arquitectura, data-model, crm, postgres, airtable]
source_count: 2
proyectos_aplicables: [robert, mica]
proyecto: compartido
---

# Persona única con roles múltiples — CRM inmobiliario

## Definición

Modelo de datos donde una persona del ecosistema (lead/cliente/inquilino/propietario) se representa como **UN solo registro** en la base de datos, con un array de roles que puede acumular.

```sql
clientes_activos (Postgres Robert) o CLIENTES_ACTIVOS (Airtable Mica)
  ├─ id, nombre, apellido, telefono, email, documento
  ├─ lead_id         (trazabilidad al origen lead si vino del bot)
  ├─ origen_creacion (lead_convertido / manual_directo / activo_mapa / migracion_*)
  └─ roles           (array: comprador | inquilino | propietario)
```

Los **roles no son mutuamente excluyentes**. Pedro puede simultáneamente:
- Haber comprado un lote → rol `comprador`
- Alquilar un local para su comercio → rol `inquilino`
- Listar su departamento para alquiler en la misma agencia → rol `propietario`

Sigue siendo UN Pedro en DB.

## Motivación

La inmobiliaria piensa en **personas**, no en roles técnicos. Para controlar, cobrar, vender y atender, lo que importa es "¿quién es Pedro y cuál es su historia completa con nosotros?".

Modelo anterior (fragmentado): 4 tablas separadas (`leads`, `clientes_activos`, `inquilinos`, `propietarios`). Mismo Pedro aparecía 4 veces sin que el sistema supiera que son la misma persona. Si Pedro cambiaba de teléfono, había que actualizar 4 veces. La búsqueda "Pedro Pérez" daba resultados fragmentados.

Modelo nuevo (persona única): Pedro es 1 fila. Su historia es:
- Sus **contratos** (tabla polimórfica `contratos` con tipo=venta_*/alquiler y FK a items físicos)
- Sus **alquileres** (datos extras cuando tipo=alquiler)
- Sus **inmuebles propios** (lookups en `inmuebles_renta WHERE propietario_id = pedro.id`)
- Su **origen** como lead si vino del bot WhatsApp

## Relaciones con otras entidades

```
leads (pipeline bot, persistente)
  └─ id, tel, estado_seguimiento  
      ↓ (trazabilidad — no se borra al convertir)
       
clientes_activos (persona única con roles)
  │
  ├── contratos (polimórfico N:1)
  │     ├─ tipo: venta_lote / alquiler / ...
  │     ├─ item_tipo + item_id → lotes_mapa / propiedades / inmuebles_renta
  │     └─ estado_pago, cuotas
  │
  ├── alquileres (1:1 con contratos tipo='alquiler')
  │     └─ fechas, garante, monto_mensual
  │
  └── inmuebles_renta (cuando rol='propietario')
        └─ propietario_id = clientes_activos.id
```

## Implementación en Postgres (Robert)

Rol como array nativo:
```sql
ALTER TABLE clientes_activos ADD COLUMN roles TEXT[] DEFAULT ['comprador'];

-- Agregar rol sin duplicar:
UPDATE clientes_activos 
SET roles = array_append(roles, 'inquilino')
WHERE id = :id AND NOT 'inquilino' = ANY(roles);

-- Buscar por rol:
SELECT * FROM clientes_activos WHERE 'propietario' = ANY(roles);
```

Endpoints relevantes (worker Robert):
- `GET /crm/personas/buscar?q=pedro` → autocomplete para modales (previene duplicados)
- `GET /crm/personas/{id}` → ficha 360 (persona + lead_origen + contratos + alquileres + inmuebles_propios)
- `POST /crm/personas/agregar-rol` → `{cliente_id, rol}` → `ARRAY_APPEND` defensivo
- `POST /crm/contratos/alquiler` → crea cliente (si nuevo) + contrato tipo=alquiler + registro en `alquileres` + agrega rol inquilino

## Implementación en Airtable (Mica — pendiente)

En Airtable los roles se representan como `multipleSelects` en vez de `TEXT[]`:
```
CLIENTES_ACTIVOS
  └─ Roles (Multiple select): [comprador, inquilino, propietario]
```

Los "contratos polimórficos" en Airtable se modelan con campos `linkedRecord` opcionales apuntando a `Loteos`, `Propiedades`, `InmueblesRenta` según tipo. Menos elegante que Postgres pero funcional para Mica.

## Fuentes que lo mencionan

- [[sintesis/2026-04-22-crm-v3-robert]] — implementación completa en Robert
- [[raw/robert/sesion-2026-04-22-crm-v3-robert]] — contexto y trade-offs

## Perspectivas distintas

**Trade-off conocido**: el modelo permite casos extraños como persona sin ningún rol (si se crea manualmente antes de agregarle contratos). Mitigación: `DEFAULT ['comprador']` si es el caso más común, o constraint opcional `CHECK (cardinality(roles) > 0)`.

**Alternativa descartada**: tabla `persona_roles` separada (normalización 3FN estricta). Descartado porque el usuario quiere UI simple donde roles aparecen como badges en la ficha del cliente — el array nativo es más directo y performante para la query típica "mostrar roles de este cliente".

## Contradicciones detectadas

Ninguna hasta el momento. El modelo es estable y fue validado con smoke tests E2E.

## Ejemplos de uso

### María González — lead convertida multi-rol

```
persona: {id:15, nombre:"María", apellido:"González", telefono:"+549..."}
lead_id: 10  (vino del bot WhatsApp 2026-03-15)
origen_creacion: "lead_convertido"
roles: ["comprador", "inquilino"]

contratos:
  - {id:4, tipo:"venta_casa", item_id:10, monto:150000, cuotas:1/36}
  - {id:6, tipo:"alquiler", item_id:3, monto:180000 ARS/mes}

alquileres:
  - {contrato_id:6, fecha_inicio:"2026-05-01", fecha_fin:"2028-05-01", 
     monto_mensual:180000, garante_nombre:"Juan Garante"}

inmuebles_propios: []
```

Ficha en el CRM muestra los 3 bloques unificados. Al cambiar su teléfono se actualiza UN solo registro.
