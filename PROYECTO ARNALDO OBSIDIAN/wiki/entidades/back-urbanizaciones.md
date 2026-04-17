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
- **Base de datos**: [[airtable]] (base de Arnaldo)
- **Backend**: `agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/*` — vive en [[coolify-arnaldo]]
- **n8n**: workflows en [[n8n]] Arnaldo — alerta vencimientos 8am ARG (SMTP + WhatsApp asesor)

## 6 loteos gestionados

San Ignacio (163 pins) · Apóstoles (332 pins, 331 lotes + 1 EV Mz17 ✅) · Gdor Roca · Leandro N. Alem · La Paulina · Altos San Ignacio · Altos Roca

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
