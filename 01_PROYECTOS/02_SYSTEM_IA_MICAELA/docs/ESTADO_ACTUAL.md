# ESTADO ACTUAL DEL PROYECTO

Proyecto: System IA — Micaela
Fecha: 2026-04-10 18:30
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
- [2026-04-21] CRM v2 de Mica creado en `demos/SYSTEM-IA/dev/crm-v2.html`: paleta ámbar/rojo, branding System IA, endpoints /clientes/system_ia/demos/inmobiliaria, tenant default mica-demo
- [2026-04-21] Airtable base `appA8QxIhBYYAHw0F`: 12 tablas creadas (Asesores, Propietarios, Loteos, LotesMapa, Contratos, Visitas, InmueblesRenta, Inquilinos, ContratosAlquiler, PagosAlquiler, Liquidaciones, ConfigCliente)
- Monitor vencimiento token LinkedIn ACTIVO en n8n Mica (`jUBWVBMR6t3iPF7l`) — testeado ✅ 60 días restantes al 2026-06-09
- Worker Lau creado en `workers/clientes/system-ia/lau/worker.py` — pendiente deploy
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
- Cuando renueve token LinkedIn: actualizar `FECHA_VENCIMIENTO` en nodo `🧮 Calcular días restantes` (workflow `jUBWVBMR6t3iPF7l`)
- Deploy worker Lau — confirmar detalles del negocio con Mica
- n8n Mica: actualizar a 2.47.5 desde Easypanel (verificar N8N_ENCRYPTION_KEY antes)

## Riesgos
- Token LinkedIn Mica vence ~2026-06-09 — monitor activo, alertará según severidad (30/14/7/3 días)
- Worker Lau creado pero sin deploy — cliente sin bot aún
- n8n Mica en versión 2.35.6 — usar typeVersion 4.1 en httpRequest, formato antiguo en IF

## Próxima acción recomendada
Coordinar con Mica los detalles del negocio de Lau → adaptar worker → deploy en Easypanel. Verificar N8N_ENCRYPTION_KEY antes de actualizar n8n.
