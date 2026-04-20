# ESTADO ACTUAL

Fecha: 2026-04-20 07:30
Responsable última actualización: Claude Opus 4.7 / Arnaldo

## Sesión 2026-04-20 — Número test Tech Provider + Fase 1 ecosistema Mica

**Objetivo de la sesión**: aprovechar que Robert es Tech Provider Meta para:
1. Que Arnaldo tenga un número WhatsApp oficial testeable que rutee a cualquier
   worker del ecosistema (demos de las 3 agencias) via la app Meta de Robert.
2. Replicar el ecosistema CRM de Robert para Mica (Fase 1 — CRM actualizado).

### Parte A — Número test via Tech Provider Robert
**Implementado**:
- `workers/shared/wa_provider.py` — capa abstracción Meta/Evolution/YCloud (send + parse).
- `workers/demos/inmobiliaria/worker.py` (Arnaldo) adaptado provider-agnostic. Default YCloud, Meta si `WHATSAPP_PROVIDER=meta`.
- `workers/clientes/system_ia/demos/inmobiliaria/worker.py` (Mica) adaptado provider-agnostic. Default Evolution, Meta si `WHATSAPP_PROVIDER=meta`.
- `02_OPERACION_COMPARTIDA/scripts/probar_worker.sh` — CLI switch rápido con aliases (arnaldo-demo, mica-demo, robert-demo).
- Wiki: `wiki/conceptos/numero-test-tech-provider.md` documentando el patrón.

**Intactos (producción)**: `arnaldo/maicol/`, `system_ia/lau/`, `lovbot/robert_inmobiliaria/`.

**Pendiente**: Meta App Review aprobado (Embedded Signup bloqueado hasta aprobación — screenshot 06:46 confirmó "app no está disponible"). Tiempo espera 2-10 días desde 2026-04-19.

**Update 2026-04-20 FINAL — Curso Kevin "Tech Provider + Embedded Signup" COMPLETADO 100%**:
- Validadas 12 clases de Kevin contra stack Robert (2 submódulos: "Cómo convertirte en Tech Provider" + "Embedded Signup + Coexistence").
- Conclusión: Robert SUPERA lo que enseña Kevin en arquitectura (FastAPI multi-tenant vs n8n manual), solo faltaban 3 cosas que se completaron hoy.

**Lo que SE HIZO HOY (6 commits backend + 1 config Vercel)**:
- `64c7ad0` Compliance webhooks deauthorize + data_deletion (GDPR/LGPD)
- `063a58e` Fix bug Python 3.11 backslash en f-string worker Mica demo
- `52a7fad` Activar Coexistence en frontend (featureType correcto)
- `b21305e` Trigger primer auto-deploy Vercel post Git-link
- `3aa76c0` Bump Graph API v21.0 → v24.0 en webhook_meta.py
- `b940288` Override callback URI por phone_number_id (para multi-numeros)
- Config: lovbot-onboarding Vercel conectado a Git + Root Directory configurado

**URLs LIVE verificadas**:
- https://agentes.lovbot.ai/webhook/meta/events ✅ (principal)
- https://agentes.lovbot.ai/webhook/meta/deauthorize ✅ (compliance)
- https://agentes.lovbot.ai/webhook/meta/data-deletion ✅ (compliance)
- https://agentes.lovbot.ai/webhook/meta/deletion-status?code=X ✅ (público)
- https://agentes.lovbot.ai/webhook/meta/override + /override-phone ✅ (admin)
- https://lovbot-onboarding.vercel.app/?client=slug ✅ (Coexistence v2.0)

**Pendiente único**:
- 🟡 App Review Meta en curso desde 2026-04-19 (restan ~8 días hábiles).
- Al aprobarse: Embedded Signup desbloqueado para clientes reales externos.

**Nada más por hacer en este módulo.** Robert es Tech Provider 100% funcional a nivel infra.

**Update 2026-04-20 13:45 — Coexistence ACTIVO en producción + Vercel auto-deploy**:
- ✅ `lovbot-onboarding.vercel.app` actualizado a v2.0 con Coexistence:
  - `featureType: 'whatsapp_business_app_onboarding'` (era `feature: 'whatsapp_embedded_signup'`)
  - `sessionInfoVersion: '3'` string (era número 3)
  - FB SDK v24.0 (era v21.0)
- ⚠️ Problema resuelto: `lovbot-onboarding` proyecto Vercel NO estaba conectado a Git → 3 días de desfase entre código repo y producción.
- ✅ **Git conectado** a `Arnaldo999/system-ia-agentes` con Root Directory `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/onboarding-vercel`.
- ✅ Desde ahora cualquier `git push` con cambios al onboarding HTML auto-deploya solo (sin `vercel deploy` manual).
- Commits: `52a7fad` (Coexistence) + `b21305e` (trigger primer deploy via Git).
- Monitor confirmó endpoint productivo sirviendo HTML nuevo (cache age=18s).

**Update 2026-04-20 13:15 — Compliance webhooks LIVE + bug Python 3.11 fixeado**:
- ✅ 4 endpoints compliance verificados LIVE en `agentes.lovbot.ai`:
  - POST /webhook/meta/deauthorize → 200
  - POST /webhook/meta/data-deletion → 200 (responde {url, confirmation_code})
  - GET /webhook/meta/deletion-status?code=X → 200/404 según corresponda
  - POST /webhook/meta/setup-compliance-table → ejecutado, tabla `meta_compliance_logs` creada en PG `robert_crm`.
- ✅ URLs configuradas en panel Meta Facebook Login → Cancelar autorización + Solicitudes de eliminación.
- ✅ `LOVBOT_ADMIN_TOKEN` rotado por Arnaldo (token viejo `e55b...` ya rechaza con 403).
- 🐛 Bug latente Python 3.11 detectado y arreglado:
  - `workers/clientes/system_ia/demos/inmobiliaria/worker.py:1934` tenía `re.sub(r'\D','',telefono)` dentro de f-string.
  - Python 3.11 NO permite backslash en expresión f-string (3.12+ sí). Coolify Hetzner usa 3.11.
  - Bug existía desde antes pero solo se manifestó al primer redeploy (commit 063a58e fix).
  - Documentado en auto-memory `feedback_python311_fstring_backslash.md`.

**Update 2026-04-20 09:30 — Compliance webhooks implementados**:
- Implementados endpoints en `webhook_meta.py` (FastAPI Robert, NO en n8n):
  - `POST /webhook/meta/deauthorize` — verifica HMAC SHA-256 + marca tenant revoked
  - `POST /webhook/meta/data-deletion` — verifica HMAC + responde {url, confirmation_code}
  - `GET /webhook/meta/deletion-status?code=X` — consulta pública del user
  - `POST /webhook/meta/setup-compliance-table` — admin, crea tabla idempotente
- Nueva tabla PG: `meta_compliance_logs` (event_type, user_id, signature_valid, raw_payload, action_taken, confirmation_code).
- Nuevos helpers DB: `setup_meta_compliance_logs_table()`, `log_meta_compliance_event()`, `marcar_waba_revoked_por_user()`, `eliminar_datos_por_user()`.
- Commit `64c7ad0` pusheado a master:main → Coolify Hetzner auto-deploy en curso.
- URLs ya configuradas por Arnaldo en panel Meta (Facebook Login → Cancelar autorización + Solicitudes de eliminación).
- PENDIENTE post-deploy: ejecutar `POST /webhook/meta/setup-compliance-table` con X-Admin-Token para crear la tabla.
- Decisión arquitectural: NO usamos el patrón n8n+Cloudflare Worker de Kevin porque Robert ya tiene infra FastAPI propia y `META_APP_SECRET` cargado en Coolify (más limpio, un solo lugar para webhooks Meta).

**Update 2026-04-20 08:58**: Paquete completo ENVIADO a revisión. Estado "Revisión en curso" (hasta 10 días). Incluye:
- `whatsapp_business_management` → en revisión
- `whatsapp_business_messaging` → en revisión
- `public_profile` → revisión acceso existente
- Videos 1 y 2 grabados y enviados por Robert ✅
- Ícono 1024×1024, URLs legales (privacidad lovbot.mx, términos+eliminación lovbot-legal.vercel.app) ✅
- App ID: `704986485248523` ("APP WorkFlow Whats Lovbot V2")
- Dominio app: `lovbot-onboarding.vercel.app`
- Email contacto Meta: `sawueso@hotmail.com` (⚠️ considerar cambiar a @lovbot.ai post-aprobación)

### Parte B — CRM Mica Fase 1 (actualización v1.1.1 → v1.4.0)
**Problema detectado**: el CRM Mica productivo (`system-ia-agencia.vercel.app/system-ia/crm`) tenía v1.1.1 con branding "LovBot IA" y bugs críticos que ya estaban arreglados en Robert pero nunca se propagaron.

**Aplicado**:
- `demos/SYSTEM-IA/dev/crm.html` + `demos/SYSTEM-IA/crm.html` bumped a v1.4.0 (dev: v1.4.0-dev).
- Fix seguridad `initTenant()`: bloquea acceso si tenant no existe (excepto slugs públicos `demo` y `mica-demo`).
- Fix banner versión: agregado `_compareSemver()` para comparación real (antes comparaba con `!==` causando loop infinito).
- Dev sincronizado con prod (ambos 3918 líneas, idénticos salvo versión).

**Stack confirmado para ecosistema Mica**:
- DB bot: Airtable `appA8QxIhBYYAHw0F` (sigue)
- WhatsApp clientes reales: Evolution API (hasta que Mica sea TP propio)
- WhatsApp tests internos: Meta via Tech Provider Robert + `WHATSAPP_PROVIDER=meta`
- Chatwoot: el de Arnaldo (compartido, worker Mica vive en VPS Arnaldo)
- Backend: `agentes.arnaldoayalaestratega.cloud/mica/*`
- Supabase tenant: `mica-demo` (reutilizar, no crear nuevo)
- Cotizador: n8n Arnaldo (ya adapta por tono/voz/logo del brief)
- Form brief: separado en `systemia-brief-form.vercel.app` (pendiente, Fase 2)
- Email welcome cliente: ❌ NO habilitado (Mica no tiene SMTP) — solo WhatsApp

### TAREAS PENDIENTES IDENTIFICADAS

#### ⏳ Mover worker Lau de system_ia/ → arnaldo/ (trampa del path)
El worker de Lau vive físicamente en `workers/clientes/system_ia/lau/` por error
histórico de organización. Lau es proyecto propio de Arnaldo (negocio "Creaciones
Lau" de su esposa), NO de Mica. La documentación en los 3 silos ya está correcta,
pero el código físico nunca se movió porque:
- Mover carpeta rompe imports
- Requiere cambiar config Coolify (working directory)
- Cambiar webhook Evolution API
- Redeploy con downtime ~2 min

**Decisión Arnaldo 2026-04-20**: dejar la trampa pendiente como tarea separada.
Hacer en una sesión dedicada, no mezclar con otro trabajo. Plan:
1. Nueva branch `refactor/lau-move-to-arnaldo`.
2. `mv workers/clientes/system_ia/lau workers/clientes/arnaldo/lau`.
3. Ajustar imports (`from workers.clientes.system_ia.lau` → `.arnaldo.lau`).
4. Ajustar rutas FastAPI si existen.
5. Cambiar working_directory en Coolify.
6. Actualizar webhook Evolution.
7. Redeploy controlado.
8. Eliminar "Trampa del path" de `wiki/entidades/lau.md` y memory silo 1.

#### ⏳ Fase 2 ecosistema Mica (próxima sesión)
- Form brief Mica (`systemia-brief-form.vercel.app`) clonado del de Robert.
- Script `onboard_mica_cliente.py` adaptado: Evolution en vez de Meta, Airtable, solo WhatsApp (sin email).
- Provisioning Evolution API automático por cliente.

#### ⏳ Cambios pendientes en lau/worker.py no relacionados
Hay cambios de otra sesión anterior en `workers/clientes/system_ia/lau/worker.py`
(fix Airtable singleSelect para CATEGORIAS_AIRTABLE = {Escolar, Eventos, Diseños,
Papelería, Invitaciones digitales}). NO commiteados hoy porque no son del alcance.
Revisar y commitear por separado cuando Arnaldo decida.

---

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
