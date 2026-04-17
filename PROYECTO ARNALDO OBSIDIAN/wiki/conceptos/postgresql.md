---
title: "PostgreSQL (robert_crm)"
tags: [postgresql, base-de-datos, robert]
source_count: 0
proyectos_aplicables: [robert]
---

# PostgreSQL — `robert_crm`

## Definición

Base de datos relacional PostgreSQL, corriendo como container Docker dentro de [[coolify-robert]] (red interna Coolify). Es la **única base de datos del bot** del proyecto [[robert-bazan]]. **Ningún otro proyecto usa PostgreSQL** — Arnaldo y Mica usan [[airtable]].

## Quién la usa

- ✅ [[robert-bazan]] → único usuario. Datos de leads, propiedades, clientes activos, sesiones del bot, pipeline CRM.
- ❌ [[arnaldo-ayala]] → usa Airtable.
- ❌ [[micaela-colmenares]] → usa Airtable.
- ❌ [[maicol]], [[lau]] → usan Airtable.

## Ubicación

- Container: `lovbot-crm-postgres` (nombre viejo: `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck`)
- Database: `robert_crm` (anteriormente `lovbot_crm` con tenant_slug)
- User: `lovbot`
- Red: Docker red interna de Coolify en [[vps-hetzner-robert]]

## Tablas principales

- `leads` — leads del bot WhatsApp (incluye historial, BANT, score)
- `propiedades` — inventario de Robert
- `clientes_activos` — clientes en proceso / cerrados
- `bot_sessions` — estado efímero de sesiones WhatsApp
- `asesores`, `propietarios`, `loteos`, `lotes_mapa`, `contratos`, `visitas` — CRM completo multi-subnicho (Sprint 1)

## Módulo Python del bot

`workers/clientes/lovbot/robert_inmobiliaria/db_postgres.py` — capa de acceso (`psycopg2`). Funciones: `get_lead_by_telefono`, `save_lead`, `get_propiedades`, etc.

## Env vars

- `DATABASE_URL` apuntando al container `lovbot-crm-postgres` en red Coolify Robert.
- Flag `USE_POSTGRES` en worker → PostgreSQL principal, Airtable fallback (legacy).

## ⚠️ Trampa común

Si ves `AIRTABLE_TOKEN` o `airtable_api_key` en código del worker de Robert → **es un bug legacy**. Robert NO usa Airtable. Reportar al usuario, no "completar" agregando más código Airtable.

## Fuentes que lo mencionan

_Pendiente ingestar: `project_postgres_migration.md`, `project_robert_bot_sprint1.md`, `docs/CRM-COMPLETO-MULTISUBNICHO.md` en `01_PROYECTOS/03_LOVBOT_ROBERT/docs/`._
