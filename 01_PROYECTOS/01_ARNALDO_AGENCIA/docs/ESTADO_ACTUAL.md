# ESTADO ACTUAL DEL PROYECTO

Proyecto: Arnaldo Agencia
Fecha: 2026-04-10 18:30
Responsable: Claude Sonnet 4.6 / Arnaldo

## Estado
En producción parcial

## Resumen corto
Agencia de automatización de Arnaldo. Bot WhatsApp inmobiliario de Maicol en producción real con clientes desde 2026-04-06. CRM propio en `crm.backurbanizaciones.com`. Publicación automática diaria en redes sociales (IG + FB + LI). Bot de prueba propio activo.

## Entorno
- Producción: ✅ `https://agentes.arnaldoayalaestratega.cloud`
- Staging: No
- Repo/backend principal: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/`
- Workflows principales: n8n `https://n8n.arnaldoayalaestratega.cloud` — 7 workflows activos
- CRM Maicol: `https://crm.backurbanizaciones.com`

## Últimos cambios
- `base_directory` Coolify corregido: ruta legacy → `/01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes` ✅
- Fix nodo Telegram workflow redes (`aJILcfjRoKDFvGWY`): `specifyBody keypair → json` — alertas ahora funcionan ✅
- Workflow Monitor YCloud Maicol ACTIVO (`5nWay88239sreaj7`) — credencial cargada por Arnaldo, testeado ✅ quality:GREEN
- Reorganización workspace: backend movido de `02_DEV_N8N_ARCHITECT/backends/` a ruta actual
- Bot Maicol reconectado tras desconexión YCloud (migración número al celular de Maicol)

## Rutas clave
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/arnaldo/maicol/worker.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/arnaldo/prueba/worker.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/social/worker.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/maicol/`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/`

## No tocar sin validar
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/arnaldo/maicol/worker.py` — PRODUCCIÓN LIVE
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py` — registra todos los routers
- `.env` raíz — vault centralizado con tokens de Coolify y GitHub
- `crm.backurbanizaciones.com` — CRM con datos reales de clientes Maicol

## Pendientes
- DNS: agregar A record `agentes → 187.77.254.33` en Hostinger panel

## Riesgos
- YCloud puede desconectarse si Maicol cambia de celular sin avisar (monitor activo alertará en 30min)

## Próxima acción recomendada
Diseñar Fase 2 del sistema de auditoría (infraestructura, workflows, integraciones, CRM/tenants, reporte).
