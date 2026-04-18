# ESTADO ACTUAL

Fecha: 2026-04-18 10:45
Responsable última actualización: Claude Opus 4.7 / Arnaldo

## Sesión 2026-04-18 — Limpieza Supabase tenants + sincronización silos

**Decisión arquitectural**: eliminado tenant `robert` de Supabase porque era
duplicado funcional con `demo` (ambos mostraban datos demo). Dejar solo 1 tenant
demo por agencia es más limpio y se presta menos a confusión.

**Estado final Supabase tenants** (2 agencias):
- `demo` (agencia=lovbot) — Demo presentación Robert
- `mica-demo` (agencia=system-ia) — Demo presentación Mica

**NO se tocó**:
- `waba_clients` en PG robert_crm (bot productivo +52 998 sigue vivo)
- Worker `robert_inmobiliaria/` (activo en producción)
- Ningún proyecto Vercel (todos siguen en uso)

**Aclaración Lau**: corregida en los 3 silos (auto-memory + ESTADO_ACTUAL + wiki
ya lo decía bien). Lau = proyecto propio Arnaldo (Creaciones Lau), NO de Mica.
Path legacy `workers/clientes/system_ia/lau/` es engañoso pero el dueño real
es Arnaldo.

**Clientes productivos documentados** (solo 2 confirmados 100%):
- Maicol (Back Urbanizaciones) — Arnaldo
- Lau (Creaciones Lau) — Arnaldo
- Robert = alianza técnica (no cliente pagando)
- Mica = sociedad comercial (sin clientes productivos aún)

---

## Sesión 2026-04-17 — Tech Provider Meta WABA Onboarding Fase 1 COMPLETADA ✅

**Arquitectura final** (después de pivote n8n → Python consolidado):
- 5 workflows n8n reemplazados por módulo Python: `workers/clientes/lovbot/tech_provider/webhook_meta.py`
- Webhook Meta apunta a `https://agentes.lovbot.ai/webhook/meta/events` (NO n8n)
- Multi-tenant router dinámico por `phone_number_id` consulta PG `waba_clients`
- Los 5 workflows n8n (OyTCUWbtnigfu5Oh, vF3bMbCzFz3D2W9z, zEyLpnNJeapT9auj, r7xmihHdyTDYRQyA, Sc2DO2ernl4MnkqA) quedan de backup pero YA NO SE USAN

**Completado**:
- ✅ Nurturing 24h endpoint `/admin/nurturing/24h` + columnas `nurturing_24h_enviado` en leads Robert
- ✅ Tabla `waba_clients` creada en PG `robert_crm` (1 tenant: Robert db_id=1)
- ✅ Endpoints Tech Provider: `/admin/waba/setup-table`, `/public/waba/onboarding`, `/admin/waba/onboarding`, `/admin/waba/register-existing`, `/admin/waba/clients`, `/admin/waba/client/{phone_id}`
- ✅ Módulo consolidado Python: `/webhook/meta/verify`, `/webhook/meta/events` (GET+POST), `/webhook/meta/subscribe-webhooks`, `/webhook/meta/override`
- ✅ Env var `LOVBOT_ADMIN_TOKEN` en Coolify Hetzner (valor: e55b1340d6a3ddb6c2e96a874402767e362ba5ab53bacdc359af2fca9b9caf13)
- ✅ HTML embedded signup en Vercel: **https://lovbot-onboarding.vercel.app**
  - APP_ID: 704986485248523 | CONFIG_ID: 1264527552112117
- ✅ Meta Developers — permisos whatsapp_business_management + whatsapp_business_messaging, dominio lovbot-onboarding.vercel.app autorizado, webhook apuntado a FastAPI, campo `messages` suscripto
- ✅ **Prueba real end-to-end exitosa**: mensaje de WhatsApp de Arnaldo → Meta → Python webhook → PG router → worker Robert → respuesta GPT-4.1-mini con memoria persistente
- ✅ Fase transitoria: clientes nuevos vía `/public/waba/onboarding` comparten worker `/clientes/lovbot/inmobiliaria/whatsapp` hasta que se armen workers dedicados por vertical

**URL operativa para registrar clientes**:
```
https://lovbot-onboarding.vercel.app/?client=NombreDelCliente
```

**Commits hoy**:
- `99f9ccd` feat(robert-bot): sistema de nurturing 24h
- `421997e` feat(robert-bot): Tech Provider WABA onboarding Fase 1
- `e38f9ed` feat(robert-bot): endpoint /admin/waba/register-existing
- `df2693d` feat(robert-bot): ruta /public/waba/onboarding sin admin token + HTML Vercel listo
- `df48ba9` feat(robert-bot): módulo Python `webhook_meta.py` consolidando 5 workflows n8n
- `7807ab2` fix(robert-bot): aceptar GET en /webhook/meta/events para handshake Meta
- `c67bad7` feat(robert-bot): clientes nuevos comparten worker inmobiliaria por default (revertido luego)
- `8f1a8f7` revert: worker_url dinamico + endpoint admin update-worker-url
- `9cecb25` feat(robert-bot): validar que worker exista antes de onboarding (409 si no)
- `76e7a28` feat(lovbot): formulario brief HTML + script clonar_worker_lovbot.py
- `c7e6866` fix(clonar-worker): dry-run usa template cuando dest no existe

**Pendientes para mañana / sprint 2**:
- 🟡 Deploy Vercel del form-brief (hoy rate-limited en plan free — 100/día)
- Reemplazar placeholder `5493765XXXXXX` en form-brief con nro WhatsApp real de Lovbot
- Templates Meta aprobados para nurturing 3d/15d/30d
- Cuando llegue primer cliente real: probar flow completo (form → YAML → script → URL → onboarding)
- Eventualmente: desactivar oficialmente los 5 workflows n8n (hoy son backup)

---


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
- Arnaldo: ✅ Estable — Maicol live, Lau pendiente deploy (proyecto propio "Creaciones Lau"), redes sociales activas, CRM operativo
- System IA Micaela: 🟡 En desarrollo — n8n activo, monitor LinkedIn creado
- Lovbot Robert: 🟡 En desarrollo — bot live en Coolify, CRM SaaS dev/prod separados

## Últimos cambios importantes (Fase 1 — 2026-04-10)
- `base_directory` Coolify Arnaldo corregido: `/02_DEV_N8N_ARCHITECT/...` → `/01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`
- Fix nodo `🚨 Alerta Telegram` workflow redes Arnaldo (`aJILcfjRoKDFvGWY`): `specifyBody keypair → json`
- Workflow `🔍 Monitor YCloud — Maicol` creado y ACTIVO (`5nWay88239sreaj7`) — testeado ✅ quality:GREEN, status:CONNECTED
- Workflow `🔐 Monitor Vencimiento Tokens — LinkedIn Mica` creado y ACTIVO (`jUBWVBMR6t3iPF7l`) — testeado ✅ 60 días restantes

## No tocar sin validar
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/arnaldo/maicol/worker.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/social/worker.py`
- `.env` raíz (vault centralizado con tokens de Coolify y GitHub)
- `crm.backurbanizaciones.com` — CRM Maicol con datos reales de clientes

## Pendientes prioritarios
- Deploy worker Lau (proyecto propio Arnaldo, NO Mica — negocio "Creaciones Lau" de su esposa)
- DNS Arnaldo: agregar A record `agentes → 187.77.254.33` en Hostinger panel
- n8n Mica: actualizar a 2.47.5 desde Easypanel (verificar N8N_ENCRYPTION_KEY antes)
- Cuando Mica renueve token LinkedIn: actualizar `FECHA_VENCIMIENTO` en nodo `🧮 Calcular días restantes`

## Riesgos abiertos
- Token Coolify Arnaldo expuesto en texto plano dentro de settings.json (entradas curl) — mitigar en Fase 2
- n8n Mica en versión 2.35.6 — desactualizada, workflows nuevos deben usar typeVersion compatibles
- Token LinkedIn Mica vence ~2026-06-09 — alerta activa cuando se active el workflow

## Últimos commits relevantes
- `16512af` — fix(gobernanza): corregir referencias ai/core + paths + commit docs pendientes
- `d7aa14a` — fix(gobernanza): actualizar rutas hooks + limpiar settings.json legacy
- `b88bf15` — refactor(workspace): eliminar carpetas legacy + normalizar rutas en docs

## Fase 2 — Auditoría (en curso, Capa 1+2 construidas)

### Guardia Crítica (script — Capa A)
- Script: `02_OPERACION_COMPARTIDA/scripts/guardia_critica.py`
- Setup: `guardia_critica_setup.md`
- Checks: FastAPI Arnaldo, n8n Arnaldo, Coolify app status
- Frecuencia: cada 5min via cron | Retry 1x | Cooldown 30min
- **Pendiente: configurar cron en VPS Arnaldo**

### Auditoría Diaria script-first — Capa B (Fase 2.2) ✅
- `auditor_infra.py` — n8n Mica + Lovbot health — testeado ✅
- `auditor_workflows.py` — 7 workflows críticos estado activo + ejecuciones — testeado ✅
- `auditor_runner.py` — orquestador, Telegram directo, silencioso si todo OK — testeado ✅
- Workflow n8n `IuHJLy2hQhOIDlYK` queda activo en paralelo hasta validar scripts en producción
- Nota: n8n Mica y Lovbot no exponen REST API con las keys actuales → checks de esas instancias se hacen via health check (infra) y se skipean en workflows (401 handled)

## Próximo paso recomendado
1. **Configurar cron en VPS Arnaldo** — guardia_critica (5min) + auditor_runner (8am ARG)
2. Correr en paralelo con workflows existentes por 2-3 días
3. Validar que no hay falsos positivos
4. Luego decidir qué workflows viejos se apagan
5. Fase 2.3: auditor_ycloud + auditor_tokens

### Auditoría Diaria script-first — Fase 2.3 ✅ TESTEADO
- `auditor_ycloud.py` — número WhatsApp Maicol (YCloud) — testeado ✅
- `auditor_tokens.py` — LinkedIn Arnaldo/Mica, Gemini, Airtable — testeado ✅
- Ambos integrados en auditor_runner.py

### Auditoría Diaria script-first — Fase 2.4 ✅ DEPLOYADO Y TESTEADO
- `auditor_evolution.py` — instancias WhatsApp Mica (Evolution API) — testeado en Coolify ✅
- `auditor_meta_provider.py` — credenciales Meta Robert (Lovbot) — testeado en Coolify ✅
- Ambos integrados en auditor_runner.py
- Endpoint testing: `/debug/auditor-runner` agrega al main.py para ejecución via HTTP
- **Deployado a Coolify Arnaldo el 2026-04-11 a las 07:40 ARG**
- Scheduled tasks habilitadas en Coolify:
  - "Auditoría Diaria" → 0 11 * * * (11 AM ARG) ✅
  - "Guardia Crítica" → */5 * * * * (cada 5 min) ✅

## Estado actual (2026-04-11 07:40 ARG)
- Fase 2.4: auditor_evolution + auditor_meta_provider LIVE en Coolify
- Scheduled task "Auditoría Diaria" esperando ejecución automática a las 11 AM
- Reporte Telegram se enviará cuando haya alertas
- Sistema listo para monitoreo continuo multi-proyecto
