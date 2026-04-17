---
name: Mica Demo Inmobiliaria
description: Bot demo inmobiliaria de Mica (System IA) — clon de Robert, Evolution API, LIVE
type: project
---

## Bot Demo Inmobiliaria — Mica (System IA) — LIVE 2026-04-12

**Worker**: `workers/clientes/system_ia/demos/inmobiliaria/worker.py`
**Router**: `/mica/demos/inmobiliaria`
**Canal**: Evolution API (instancia "Demos", número `5493765005465`)
**Base**: Clon 1:1 del worker de Robert (`robert_inmobiliaria/worker.py`)

### Diferencias con Robert (solo 4 cambios):
1. Meta Graph API → Evolution API (`sendText/sendMedia` con `apikey` header)
2. Vars `ROBERT_*` / `INMO_DEMO_*` → `MICA_DEMO_*` / `MICA_AIRTABLE_*`
3. Router: `/clientes/lovbot/inmobiliaria` → `/mica/demos/inmobiliaria`
4. Webhook: parser Evolution (remoteJid, pushName, conversation) con fix event name uppercase

### Bugs conocidos y fixes aplicados:
- **MESSAGES_UPSERT uppercase**: Evolution manda `"MESSAGES_UPSERT"` pero el filtro esperaba `"messages.upsert"`. Fix: `.lower().replace("_", ".")` antes de comparar
- **Cal.com API v1 decommissioned**: Migrado a v2 — `/v2/slots` con header Bearer + `cal-api-version`, `/v2/bookings` con estructura `attendee`
- **WhatsApp Web vs Celular**: Evolution no dispara webhook para mensajes desde WhatsApp Web. Solo funciona desde celular. No es bug nuestro — limitación de Evolution

### Variables de entorno (Coolify Arnaldo):
- `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` (compartidas)
- `MICA_DEMO_EVOLUTION_INSTANCE` = "Demos"
- `MICA_AIRTABLE_BASE_ID` o `MICA_DEMO_AIRTABLE_BASE`
- `MICA_DEMO_AIRTABLE_TABLE_PROPS`, `MICA_DEMO_AIRTABLE_TABLE_CLIENTES`, `MICA_DEMO_AIRTABLE_TABLE_ACTIVOS`
- `MICA_DEMO_NOMBRE`, `MICA_DEMO_CIUDAD`, `MICA_DEMO_ASESOR`, `MICA_DEMO_NUMERO_ASESOR`
- `MICA_DEMO_CAL_API_KEY`, `MICA_DEMO_CAL_EVENT_ID`
- `MICA_DEMO_ZONAS`, `MICA_DEMO_MONEDA`, `MICA_DEMO_SITIO_WEB`

### CRM y Admin:
- CRM: `system-ia-agencia.vercel.app/system-ia/crm?tenant=mica-demo` (PIN: 1234)
- Admin: `system-ia-agencia.vercel.app/system-ia/admin` (token: system-ia-admin-2026)
