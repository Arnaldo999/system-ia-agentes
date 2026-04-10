# ESTADO ACTUAL DEL PROYECTO

Proyecto: Arnaldo Agencia
Fecha: 2026-04-10 13:00
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
- Reorganización workspace: backend movido de `02_DEV_N8N_ARCHITECT/backends/` a ruta actual
- Bot Maicol reconectado tras desconexión YCloud (migración número al celular de Maicol)
- Firewall n/a (Hostinger, no Hetzner)
- Password n8n reseteada vía Terminal Coolify

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
- Verificar base_directory en Coolify apunta a nueva ruta post-reorganización
- Activar toggle workflow redes `aJILcfjRoKDFvGWY` en n8n UI
- DNS: agregar A record `agentes → 187.77.254.33` en Hostinger panel
- Crear monitor proactivo YCloud (ping bot + alerta Telegram si no responde)
- Migrar webhooks YCloud de Render a Coolify si aún hay alguno apuntando a Render

## Riesgos
- base_directory Coolify puede seguir en ruta legacy — verificar antes del próximo deploy
- YCloud puede desconectarse si Maicol cambia de celular sin avisar — sin alerta automática
- Monitor Telegram no cubre desconexión YCloud, solo errores del backend

## Próxima acción recomendada
Entrar a Coolify → servicio backend → verificar base_directory apunta a `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`. Luego crear workflow n8n "Monitor YCloud Maicol" (Schedule 30min → ping → alerta Telegram si falla).
