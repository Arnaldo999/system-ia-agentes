# ESTADO ACTUAL DEL PROYECTO

Proyecto: System IA — Micaela
Fecha: 2026-04-10 13:00
Responsable: Claude Sonnet 4.6 / Arnaldo

## Estado
Activo — En desarrollo

## Resumen corto
Proyecto de Mica (Micaela) bajo la marca System IA. CRM SaaS multi-tenant live en Vercel. Publicación automática diaria en redes sociales activa. Worker de cliente Lau creado pero pendiente de deploy. n8n en Easypanel operativo.

## Entorno
- Producción: ✅ `https://system-ia-agencia.vercel.app` (CRM + admin)
- n8n: `https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host`
- Staging: No
- Repo/backend principal: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/` (monorepo compartido)
- Workers Mica: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/system-ia/`

## Últimos cambios
- Worker Lau creado en `workers/clientes/system-ia/lau/worker.py`
- Workflow redes sociales Mica activo en n8n Easypanel (`aOiZFbmvMoPSE0vB`) ✅
- CRM System IA live: admin + tenants en Supabase

## Rutas clave
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/system-ia/`
- `01_PROYECTOS/02_SYSTEM_IA_MICAELA/clientes/`
- Admin CRM: `https://system-ia-agencia.vercel.app/system-ia/admin` — token: `system-ia-admin-2026`

## No tocar sin validar
- Workers de clientes system-ia en producción (si los hay activos)
- Supabase tabla `tenants` — datos reales de clientes Mica
- Workflow redes `aOiZFbmvMoPSE0vB` en n8n Mica — activo y publicando

## Pendientes
- Deploy worker Lau — confirmar detalles del negocio con Mica
- n8n Mica: actualizar a 2.47.5 desde Easypanel (verificar N8N_ENCRYPTION_KEY antes)
- Confirmar Evolution API configurada para workers system-ia (API de WhatsApp de Mica)

## Riesgos
- Worker Lau creado pero sin deploy — si hay urgencia, el cliente no tiene bot aún
- n8n Mica desactualizado (versión < 2.47.5) — puede tener bugs conocidos

## Próxima acción recomendada
Coordinar con Mica los detalles del negocio de Lau → adaptar worker → deploy en Easypanel. Verificar N8N_ENCRYPTION_KEY antes de actualizar n8n.
