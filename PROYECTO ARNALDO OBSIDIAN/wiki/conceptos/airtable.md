---
title: "Airtable"
tags: [airtable, base-de-datos, saas]
source_count: 0
proyectos_aplicables: [arnaldo, mica]
---

# Airtable

## Definición

Base de datos SaaS low-code con interfaz tipo planilla + API REST. Usada como datastore principal por **2 de los 3 proyectos**: [[arnaldo-ayala]] (cuenta propia) y [[micaela-colmenares]] (base propia de Mica). **[[robert-bazan]] NO usa Airtable** — usa [[postgresql]].

## Quién la usa

| Proyecto | Cuenta / Base | Uso |
|----------|---------------|-----|
| [[arnaldo-ayala]] / [[back-urbanizaciones]] | Base de Arnaldo | Propiedades, Clientes, Pipeline, Clientes Activos, Loteos (datos del CRM de Maicol) |
| [[arnaldo-ayala]] / [[lau]] | Base `app4WvGPank8QixTU` | Productos + Leads de Creaciones Lau |
| [[micaela-colmenares]] / [[system-ia]] | Base `appA8QxIhBYYAHw0F` (Inmobiliaria Demo Micaela) | Datos del bot demo inmobiliaria de Mica |
| [[robert-bazan]] | ❌ No usa | Robert usa [[postgresql]] local en [[vps-hetzner-robert]] |

## Bugs conocidos

- **singleSelect estricto**: si mandás un valor que no existe como opción, la API tira 422. Ver `bugs_integraciones.md` en memory del Mission Control.
- **date campo**: requiere formato ISO 8601 exacto; timezone afecta qué día aparece en UI.
- **Base vieja Mica `appXPpRAfb6GH0xzV`**: esa NO es la correcta. La correcta es `appA8QxIhBYYAHw0F`. Si ves `.env` con la vieja, actualizar.

## Env vars

- `AIRTABLE_API_KEY` (o `AIRTABLE_TOKEN` en versiones viejas) → cuenta de Arnaldo (compartida con Mica).
- **JAMÁS** en código de Robert.

## Fuentes que lo mencionan

_Pendiente ingestar — fuentes candidatas en `02_OPERACION_COMPARTIDA/handoff/` y memory de Mission Control._

## Perspectivas distintas / Contradicciones

Ninguna detectada — stack estable.
