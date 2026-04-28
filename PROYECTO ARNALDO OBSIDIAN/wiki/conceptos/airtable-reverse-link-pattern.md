---
title: Airtable — Patrón Reverse-Link para evitar filterByFormula fallido
tags: [airtable, linked-record, reverse-link, bug, patron-tecnico, compartido]
source_count: 1
proyectos_aplicables: [mica, arnaldo, robert]
proyecto: compartido
---

# Airtable — Patrón Reverse-Link

## Definición

Cuando se usan campos de tipo `linkedRecord` en Airtable, el endpoint `filterByFormula` puede retornar **0 resultados** aunque el link exista en la base de datos. Esto ocurre especialmente cuando:

- El campo linkedRecord es un campo de muchos-a-uno que apunta a la tabla actual.
- La fórmula referencia un campo linkedRecord con sintaxis `{Campo}="valor"`.
- La tabla tiene un campo de reverse-link (el lado "uno" de la relación).

## Problema observado

En el CRM Jurídico v2 de Mica (2026-04-27), endpoint `GET /crm/marcas/{id}/ficha-completa`:

```python
# ❌ Esto devuelve 0 resultados aunque existan socios para esa marca
formula = f"{{Marca}}='{marca_id}'"
socios = airtable.get("Socios_Marca", filterByFormula=formula)
```

El campo `Marca` en `Socios_Marca` es un linkedRecord. Airtable no filtra por ID de linkedRecord con esta sintaxis.

## Solución — Leer reverse-link del padre

```python
# ✅ Leer el array reverse-link del record Marca
marca_record = airtable.get_record("Marcas", marca_id)
socio_ids = marca_record["fields"].get("Socios_Marca", [])  # array de IDs

# GET individual de cada socio
socios = []
for sid in socio_ids:
    socio = airtable.get_record("Socios_Marca", sid)
    socios.append(socio["fields"])
```

El campo `Socios_Marca` en el record de `Marcas` es el reverse-link que Airtable mantiene automáticamente. Siempre está actualizado.

## Cuándo aplicar

- Cuando se necesita obtener los registros "hijos" de un record "padre" en una relación linkedRecord.
- Siempre preferir reverse-link sobre filterByFormula cuando el campo de filtro es linkedRecord.
- Solo usar filterByFormula cuando el campo de filtro es texto plano, número o fecha.

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-27-crm-juridico-v2]] — commit `a095867`

## Notas

- El reverse-link solo existe si Airtable creó el campo automáticamente al vincular las tablas. En bases creadas via Metadata API, verificar que el campo reverso fue creado.
- Este patrón es más eficiente que hacer N llamadas con filterByFormula y también más confiable.
