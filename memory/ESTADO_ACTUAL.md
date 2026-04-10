# ESTADO ACTUAL

Fecha: 2026-04-10 13:00
Responsable última actualización: Claude Sonnet 4.6 / Arnaldo

## Resumen ejecutivo
El workspace fue reorganizado en una estructura de gobernanza global + proyectos separados (4 commits hoy).
Producción de Maicol está estable y operativa — bot funcionando, webhook en Coolify, YCloud reconectado tras migración al celular de Maicol.
El sistema de alertas Telegram detecta errores del backend pero NO detecta desconexión de YCloud (brecha conocida).
Prioridad actual: estabilizar monitoreo proactivo del bot y completar pendientes de infraestructura (DNS Arnaldo, workflow redes activo).

## Producción
- Maicol: ✅ OK — bot respondiendo, webhook activo en Coolify, YCloud conectado
- Social comments FastAPI: ✅ OK — worker activo, Arnaldo + Mica publicando diario
- n8n Arnaldo: ✅ OK — 7 workflows activos, SSL válido hasta Jun 2026
- Coolify Arnaldo (Hostinger): ✅ OK — healthy
- Coolify Robert (Hetzner): ✅ OK — firewall configurado hoy (22, 80, 443 TCP)

## Proyectos
- Arnaldo: ✅ Estable — Maicol live, redes sociales activas, CRM operativo
- System IA Micaela: 🟡 En desarrollo — worker Lau creado, deploy pendiente, n8n activo
- Lovbot Robert: 🟡 En desarrollo — bot live en Coolify, CRM SaaS dev/prod separados, firewall configurado hoy

## Últimos cambios importantes
- Reorganización workspace: estructura 4 carpetas (00_GOBERNANZA_GLOBAL, 01_PROYECTOS, 02_OPERACION_COMPARTIDA, 99_ARCHIVO)
- Firewall Hetzner configurado para VPS Robert (puertos 22, 80, 443 TCP)
- Hook pre-push-check.sh actualizado con rutas post-migración
- settings.json limpiado: 11 entradas obsoletas/riesgosas eliminadas
- Bot Maicol reconectado tras desconexión YCloud por migración de número al celular de Maicol

## No tocar sin validar
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/arnaldo/maicol/worker.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/social/worker.py`
- `.env` raíz (vault centralizado con tokens de Coolify y GitHub)
- `crm.backurbanizaciones.com` — CRM Maicol con datos reales de clientes

## Pendientes prioritarios
- Crear monitor proactivo YCloud: n8n workflow que envíe ping al bot cada 30min y alerte si no responde
- Activar toggle workflow redes `aJILcfjRoKDFvGWY` en n8n Arnaldo UI
- Deploy worker Lau (Mica) — confirmar detalles del negocio con Mica
- DNS Arnaldo: agregar A record `agentes → 187.77.254.33` en Hostinger panel
- Verificar base_directory Coolify post-reorganización: debe apuntar a `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`
- n8n Mica: actualizar a 2.47.5 desde Easypanel

## Riesgos abiertos
- Token Coolify Arnaldo expuesto en texto plano dentro de settings.json (en entradas curl) — riesgo pre-existente, mitigar moviendo a scripts que lean del .env
- Monitor Telegram no detecta desconexión de YCloud — solo detecta errores del backend FastAPI
- base_directory Coolify podría seguir apuntando a ruta legacy `02_DEV_N8N_ARCHITECT/backends/` — verificar en panel antes del próximo deploy
- YCloud puede desconectarse si Maicol cambia de celular sin previo aviso — sin alerta automática

## Últimos commits relevantes
- `d7aa14a` — fix(gobernanza): actualizar rutas hooks + limpiar settings.json legacy
- `b88bf15` — refactor(workspace): eliminar carpetas legacy + normalizar rutas en docs
- `e441499` — feat(workspace): nueva estructura de gobernanza global + proyectos separados
- `07b26dd` — revert(social): eliminar publicación LinkedIn página empresa
- `f25b653` — fix(social): cambiar modelos Gemini — 2.5-flash-lite + flash-latest

## Próximo paso recomendado
Verificar en el panel de Coolify que el base_directory del servicio apunta a la nueva ruta post-migración (`01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`) antes de hacer cualquier deploy. Luego crear el workflow n8n de monitor proactivo YCloud para cerrar la brecha de alertas detectada hoy.
