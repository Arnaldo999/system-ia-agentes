# ESTADO ACTUAL

Fecha: 2026-04-10 18:30
Responsable última actualización: Claude Sonnet 4.6 / Arnaldo

## Resumen ejecutivo
Fase 1 de estabilización operativa completada. 4 pendientes críticos resueltos:
base_directory Coolify corregido, alerta Telegram redes sociales arreglada, monitor YCloud creado, alerta vencimiento LinkedIn creada.
Producción de Maicol intacta — sin redeploy ni cambios en runtime.

## Producción
- Maicol: ✅ OK — bot respondiendo, webhook activo en Coolify, YCloud conectado
- Social comments FastAPI: ✅ OK — worker activo, Arnaldo + Mica publicando diario
- n8n Arnaldo: ✅ OK — 7+ workflows activos, SSL válido hasta Jun 2026
- Coolify Arnaldo (Hostinger): ✅ OK — healthy, base_directory corregido
- Coolify Robert (Hetzner): ✅ OK — firewall configurado

## Proyectos
- Arnaldo: ✅ Estable — Maicol live, redes sociales activas, CRM operativo
- System IA Micaela: 🟡 En desarrollo — worker Lau pendiente deploy, n8n activo, monitor LinkedIn creado
- Lovbot Robert: 🟡 En desarrollo — bot live en Coolify, CRM SaaS dev/prod separados

## Últimos cambios importantes (Fase 1 — 2026-04-10)
- `base_directory` Coolify Arnaldo corregido: `/02_DEV_N8N_ARCHITECT/...` → `/01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`
- Fix nodo `🚨 Alerta Telegram` workflow redes Arnaldo (`aJILcfjRoKDFvGWY`): `specifyBody keypair → json`
- Workflow `🔍 Monitor YCloud — Maicol` creado en n8n Arnaldo (ID: `5nWay88239sreaj7`) — inactivo, pendiente cargar credencial
- Workflow `🔐 Monitor Vencimiento Tokens — LinkedIn Mica` creado en n8n Mica (ID: `jUBWVBMR6t3iPF7l`) — inactivo, pendiente activar toggle

## No tocar sin validar
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/arnaldo/maicol/worker.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/social/worker.py`
- `.env` raíz (vault centralizado con tokens de Coolify y GitHub)
- `crm.backurbanizaciones.com` — CRM Maicol con datos reales de clientes

## Pendientes prioritarios
- **Activar** workflow Monitor YCloud Maicol (`5nWay88239sreaj7`) en n8n Arnaldo:
  1. Crear credencial HTTP Header Auth: nombre `YCloud API Key — Maicol`, header `X-API-Key`, valor desde Coolify env `YCLOUD_API_KEY_MAICOL`
  2. Asignar credencial al nodo `📡 GET YCloud phoneNumbers`
  3. Activar toggle
- **Activar** workflow Monitor LinkedIn Mica (`jUBWVBMR6t3iPF7l`) en n8n Mica UI — toggle ON
- Deploy worker Lau (Mica) — confirmar detalles del negocio con Mica
- DNS Arnaldo: agregar A record `agentes → 187.77.254.33` en Hostinger panel
- n8n Mica: actualizar a 2.47.5 desde Easypanel (verificar N8N_ENCRYPTION_KEY antes)
- Cuando Mica renueve token LinkedIn: actualizar `FECHA_VENCIMIENTO` en nodo `🧮 Calcular días restantes`

## Riesgos abiertos
- Monitor YCloud creado pero INACTIVO — no alertará hasta que Arnaldo cargue la credencial y active
- Monitor LinkedIn creado pero INACTIVO — no alertará hasta que Mica active el toggle
- Token Coolify Arnaldo expuesto en texto plano dentro de settings.json (entradas curl) — mitigar en Fase 2
- n8n Mica en versión 2.35.6 — desactualizada, workflows nuevos deben usar typeVersion compatibles
- Token LinkedIn Mica vence ~2026-06-09 — alerta activa cuando se active el workflow

## Últimos commits relevantes
- `16512af` — fix(gobernanza): corregir referencias ai/core + paths + commit docs pendientes
- `d7aa14a` — fix(gobernanza): actualizar rutas hooks + limpiar settings.json legacy
- `b88bf15` — refactor(workspace): eliminar carpetas legacy + normalizar rutas en docs

## Próximo paso recomendado
1. Arnaldo carga credencial YCloud en n8n UI y activa monitor Maicol
2. Mica activa toggle monitor LinkedIn en su n8n UI
3. Diseñar Fase 2: sistema formal de auditoría del ecosistema (infraestructura, workflows, workers, integraciones, CRM/tenants, reporte consolidado)
