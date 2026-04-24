---
title: "Sesión 2026-04-23 — CRM Agencia Lovbot LIVE end-to-end"
date: 2026-04-23
type: sesion-claude
proyecto: robert
tags: [proyecto-robert, crm-agencia, lovbot, postgres, fastapi, coolify-hetzner, sesion-claude, live-production]
---

# Sesión 2026-04-23 — CRM Agencia Lovbot LIVE end-to-end

## Resumen

Se llevó el CRM de Gestión Agencia Lovbot de estado mockup (solo frontend HTML estático) a LIVE end-to-end: BD PostgreSQL `lovbot_agencia` creada en Hetzner, backend FastAPI con 15 endpoints `/agencia/*` deployado en `agentes.lovbot.ai`, y frontend `admin.lovbot.ai/agencia` conectado al backend real con login, CRUD completo y modales funcionales. El sistema está listo para registrar leads reales de la agencia y tiene el slot preparado para integrar el flujo lead.center/Zapier de Robert cuando mande los detalles.

## Contexto de origen

Robert preguntó por WhatsApp cómo reemplazar Zapier en su flujo FB Ads → lead.center. Mientras se esperaba que Robert mandara adelantos del flujo, Arnaldo decidió avanzar en paralelo con el backend del CRM Agencia Lovbot (`admin.lovbot.ai/agencia`) que estaba en estado mockup desde 2026-04-22.

## Pasos ejecutados en orden

1. **Audit inicial**: detectado que el frontend `agencia.html` existía como mockup funcional pero NO había backend, NO había BD, NO había env vars configuradas en Coolify. Todos los botones de acción mostraban tooltip "Backend pendiente".

2. **Schema SQL propuesto** (6 tablas + vista + triggers + 8 seeds): diseño completo con `agencia_fuentes`, `agencia_leads`, `agencia_clientes`, `agencia_contactos_log`, `agencia_propuestas`, `agencia_pagos`, vista `agencia_funnel_resumen`, 3 triggers de `updated_at`, y 8 seeds de fuentes (`landing`, `fb_ads`, `referido`, `bot_whatsapp`, `evento`, `lead_center`, `zapier`, `otro`). Guardado en `01_PROYECTOS/03_LOVBOT_ROBERT/backends/agencia_crm/schema_lovbot_agencia.sql`.

3. **Aprobación de nombre**: Arnaldo decidió llamar la BD `lovbot_agencia` (más corto que `lovbot_agencia_crm`). Razonamiento: "hace referencia a todo el proyecto de Robert, no solo al CRM".

4. **BD creada via Coolify Terminal**: acceso al container `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck` → `CREATE DATABASE lovbot_agencia;` → descarga del schema SQL desde branch temporal en GitHub → `psql -U postgres -d lovbot_agencia -f schema.sql`. Verificado: 6 tablas + 1 vista + 8 seeds de fuentes presentes.

5. **Env var agregada**: `LOVBOT_AGENCIA_PG_DB=lovbot_agencia` vía Coolify API (`POST /api/v1/applications/{uuid}/envs` con `COOLIFY_ROBERT_TOKEN`).

6. **Router FastAPI creado**: `workers/clientes/lovbot/agencia_crm/router.py` con 15 endpoints + `__init__.py`. Registrado en `main.py` con prefijo `/agencia`.

7. **Push `master:main` → redeploy automático** Coolify Hetzner. Container reiniciado limpio con la nueva env var y el nuevo código.

8. **Smoke test completo**:
   - `GET /agencia/funnel-resumen` → 200 OK, `{ok: true, funnel: {}, rows: []}`.
   - `GET /agencia/fuentes` → 200 OK con las 8 fuentes seed.
   - `POST /agencia/leads` → 201 con row creado.
   - `DELETE /agencia/leads/1` → soft delete funcional (estado → eliminado).

9. **Frontend `agencia.html` actualizado**: login real contra `/agencia/fuentes` (como handshake de auth), persistencia en `sessionStorage` key `lovbot_agencia_token`, CRUD completo conectado al backend (GET funnel-resumen, GET leads, POST leads, PATCH leads, DELETE leads, POST leads/convertir-cliente), modal con todos los campos del schema Pydantic, vista embudo con 6 cards clickables.

10. **Fix de contrato frontend→backend**: el frontend original del mockup enviaba `nombre`/`contacto_nombre`/`fuente_slug` pero el schema Pydantic del backend espera `nombre_contacto`/`apellido_contacto`/`nombre_empresa`/`fuente_id` (INT). Corregido el mapeo en el modal de nuevo lead y en las llamadas fetch.

11. **Cleanup de `clientes.html`**: fusión del panel Dashboard + Clientes CRM en un panel único más limpio. Sidebar minimalista (solo 2 links: Tenants Supabase + Leads Agencia). Token persistente en `sessionStorage` con misma mecánica que `agencia.html`.

## Decisiones clave

- **Nombre BD `lovbot_agencia`**: no `lovbot_agencia_crm`. Arnaldo decidió el nombre más corto porque "lovbot_agencia hace referencia a todo el proyecto de Robert". La BD no es exclusivamente para el CRM — puede albergar otras tablas de la agencia Lovbot en el futuro.

- **Tokens separados por panel**: los 2 admins (`/clientes` y `/agencia`) mantienen tokens separados porque apuntan a backends distintos (`agentes.arnaldoayalaestratega.cloud` para tenants Supabase vs `agentes.lovbot.ai` para CRM agencia). No se pudo unificar auth sin refactorizar la arquitectura completa.

- **Auth usa `LOVBOT_ADMIN_TOKEN` de Coolify** (64 chars), NO el hardcoded `lovbot-admin-2026`. El `lovbot-admin-2026` solo existe como valor default para dev local en `.env`. Arnaldo configuró un token personalizado que sabe de memoria.

- **Panel `/clientes` limpiado**: 5 stat cards + tabla completa con buscador. Sin tabs internos, diseño más directo.

- **Panel `/agencia` con 2 vistas**: Embudo (6 cards por estado) + Todos los leads (tabla completa), navegables desde sidebar interno.

## Slot preparado para integración lead.center

Campos `fb_lead_id`, `lead_center_id`, `zapier_data` (JSONB) ya presentes en `agencia_leads` desde el schema inicial. Fuentes seed `lead_center` y `zapier` ya cargadas en `agencia_fuentes`.

Cuando Robert mande detalles de su flujo actual (probablemente: FB Ads → lead.center → Zapier), el conector solo necesita hacer `POST /agencia/leads` con:
- `fuente_id`: ID de la fuente `lead_center` o `zapier` (se consulta con `GET /agencia/fuentes`)
- `zapier_data`: el payload original del webhook como JSONB para auditoría
- Campos estándar: `nombre_contacto`, `fuente_id`, `email`, `telefono`, etc. (los que FB Ads / lead.center provea)

Sin cambios de schema ni de backend requeridos para esa integración.

## URLs finales LIVE

| Recurso | URL |
|---------|-----|
| Backend (15 endpoints) | `https://agentes.lovbot.ai/agencia/*` |
| Frontend CRM Agencia | `https://admin.lovbot.ai/agencia` |
| Frontend Panel Clientes | `https://admin.lovbot.ai/clientes` |
| DB | `lovbot_agencia` en Postgres Hetzner container `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck` |

## Próximos pasos sugeridos

1. **Esperar adelantos de Robert** sobre su flujo lead.center/Zapier para armar el conector webhook → `POST /agencia/leads`.
2. **Migrar leads existentes de Arnaldo** (si hay leads pre-anotados en algún lado) via script CSV → `POST /agencia/leads`.
3. **Conectar stats del embudo** con la vista `agencia_funnel_resumen` que ya existe en el backend — las 6 cards del embudo ya consumen `GET /agencia/funnel-resumen`, confirmar que los conteos se actualicen en tiempo real al agregar leads.
4. **Agregar al [[sistema-auditoria]]** un check para `agentes.lovbot.ai/agencia/fuentes` (health check simple del nuevo router).
5. **Onboarding número WABA agencia** (cuando Tech Provider Robert esté aprobado por Meta) — pendiente desde la propuesta original.
