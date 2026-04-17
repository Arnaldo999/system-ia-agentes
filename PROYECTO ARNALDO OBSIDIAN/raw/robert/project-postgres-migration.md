---
name: Migración PostgreSQL Robert
description: Estado de la migración de Airtable a PostgreSQL para Lovbot (Robert) — en progreso
type: project
originSessionId: 7accf720-af36-49d0-bc07-ba7e60eb27c2
---
## Migración Airtable → PostgreSQL (Robert/Lovbot)

**Estado**: En progreso (2026-04-13)
**Why**: Escalabilidad, cero costo, onboarding automático, sin límites de records

### Infraestructura creada
- PostgreSQL 16 Alpine corriendo en Coolify Robert (Hetzner: 5.161.235.99)
- Servicio UUID: `tkkk8owkg40ssoksk8ok4gsc`
- Container: `lovbot-postgres-tkkk8owkg40ssoksk8ok4gsc`
- Red: `coolify` (compartida con FastAPI y otros servicios)
- DB: `lovbot_crm` | User: `lovbot` | Pass: `9C7i82bFVoscycGCF6f7XPbZyNpWvEXa`
- Puerto interno: 5432 | Puerto externo: 5433

### Scripts creados
- `scripts/setup_postgres_lovbot.py` — crea 3 tablas (leads, propiedades, clientes_activos) con índices y triggers
- `scripts/onboard_inmobiliaria.py` — onboarding automático (Supabase + Chatwoot + labels)
- Endpoint `GET /admin/setup-postgres` — ejecuta el setup
- Endpoint `POST /admin/onboard` — ejecuta onboarding

### Pendiente (próxima sesión)
1. Ejecutar setup de tablas desde el FastAPI de Robert (ya comparten red Docker)
2. Reescribir funciones Airtable del worker a PostgreSQL (~300 líneas)
3. Actualizar endpoints CRM `/crm/clientes`, `/crm/propiedades`, `/crm/activos`
4. Migrar datos existentes de Airtable a PostgreSQL
5. Actualizar CRM HTML si los endpoints cambian
6. Testear flujo completo
7. Arreglar base_directory del app Robert: cambiar de `/02_DEV_N8N_ARCHITECT/...` a `/01_PROYECTOS/01_ARNALDO_AGENCIA/...`

### How to apply
Antes de modificar el worker de Robert, verificar que el PostgreSQL esté accesible desde el FastAPI de Robert con `GET /admin/setup-postgres`.
