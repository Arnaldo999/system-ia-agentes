---
title: "Back Urbanizaciones (marca)"
type: marca-comercial
proyecto: arnaldo
tags: [back-urbanizaciones, maicol, marca, inmobiliaria, produccion-live]
---

# Back Urbanizaciones

## Descripción

Marca comercial del proyecto inmobiliario de [[maicol]]. Empresa que vende lotes urbanos en Misiones, Argentina. Es **proyecto cliente externo de [[arnaldo-ayala]]** — Arnaldo construyó y opera el bot WhatsApp + CRM + n8n workflows.

## Dominios y servicios

- **CRM LIVE**: `https://crm.backurbanizaciones.com/` — Tailwind CSS, 7 paneles (Inicio, Propiedades, Pipeline, Leads, Clientes Activos, Galería, Loteos)
- **Bot WhatsApp**: número `+54 9 3764 81-5689` → [[ycloud]] (cuenta Arnaldo)
- **Base de datos**: [[airtable]] base `appaDT7uwHnimVZLM`
  - Tabla Propiedades: `tbly67z1oY8EFQoFj`
  - Tabla Clientes: `tblonoyIMAM5kl2ue`
- **Backend**: `agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/*` — vive en [[coolify-arnaldo]]
- **Worker path**: `workers/clientes/arnaldo/maicol/` (producción ✅)
- **n8n**: workflows en [[n8n]] Arnaldo — alerta vencimientos 8am ARG (SMTP + WhatsApp asesor)

## Variables de entorno específicas

- `YCLOUD_API_KEY_MAICOL` — YCloud de Maicol
- `AIRTABLE_BASE_ID_MAICOL` — base Airtable (`appaDT7uwHnimVZLM`)
- `AIRTABLE_TOKEN` — token general compartido entre todos los clientes Arnaldo
- `GEMINI_API_KEY` — general
- `CLOUDINARY_CLOUD_NAME=dmqkqcreo` — cuenta Cloudinary de Arnaldo
- `CLOUDINARY_UPLOAD_PRESET=social_media_posts` — unsigned, usado por CRM y worker social

## Endpoints del CRM Maicol

- `POST /clientes/arnaldo/maicol/whatsapp` — webhook YCloud → worker bot
- `POST /clientes/arnaldo/maicol/crm/upload-imagen` — multipart → retorna `{url}` Cloudinary
- Endpoints CRUD: `/clientes/arnaldo/maicol/crm/propiedades`, `/clientes`, `/activos`, `/lotes`
- `POST /clientes/arnaldo/maicol/lead` — captura desde formularios web
- `POST /clientes/arnaldo/maicol/send-email-alerta` — alertas vencimiento

## 6 loteos gestionados

San Ignacio (163 pins) · Apóstoles (332 pins, 331 lotes + 1 EV Mz17 ✅) · Gdor Roca · Leandro N. Alem · La Paulina · Altos San Ignacio · Altos Roca

## Schema Clientes (Airtable)

- **Campo Estado** (singleSelect): `no_contactado`, `contactado`, `en_negociacion`, `cerrado`, `descartado`
- **Campo Imagen_URL**: attachment (array de objetos) — leer: `imgField[0].url`, escribir: `[{url:"..."}]`
- ⚠️ **Bug conocido Airtable API**: no permite editar choices de singleSelect con PAT sin scope `schema.bases:write` → hacerlo manualmente en UI.

## Relaciones con otras entidades

- Propiedad comercial de → [[maicol]]
- Construido y operado por → [[arnaldo-ayala]]
- Corre en → [[vps-hostinger-arnaldo]] vía [[coolify-arnaldo]]
- Bot provider → [[ycloud]]
- Base de datos → [[airtable]]
- Automatizaciones → [[n8n]] Arnaldo

## Estado (2026-04-17)

- 🟢 Producción LIVE con clientes reales cargados desde 2026-04-06.
- Regla: NUNCA tocar el worker directo — primero `workers/demos/inmobiliaria/`, validar, copiar.

## Notas

- Domain: `backurbanizaciones.com` (registrado por Arnaldo, apunta a Coolify Arnaldo).
- Cloudinary carpeta: `back-urbanizaciones/` (imágenes propiedades).
