# ESTADO ACTUAL

Fecha: 2026-04-27 (tarde) ART
Responsable última actualización: Claude Opus 4.7 / Arnaldo

## 🎙️ Hito 2026-04-27 — Bot voz Robert dev-ready + limpieza workers legacy

Construcción completa del primer agente de voz del ecosistema (cuenta dev ElevenCreative Arnaldo, pendiente Twilio AR + pago Robert).

### 🎯 Entregado

| Componente | Estado | Path |
|---|---|---|
| Limpieza `workers/clientes/lovbot/` | ✅ Borrados `_base/`, `inmobiliaria_garcia/`, `test_arnaldo/` | Solo quedan `agencia_crm/`, `robert_inmobiliaria/`, `tech_provider/` |
| `workers/shared/calcom_client.py` | ✅ Nuevo | wrapper Cal.com v2 reusable |
| `workers/shared/catalog.py` | ✅ Nuevo | wrapper búsqueda Postgres |
| `workers/shared/lead_matcher.py` | ✅ Nuevo | match cross-channel últimos 10 dígitos |
| `workers/shared/bant.py` | ✅ Nuevo | extracción señales BANT + scoring |
| `workers/demos/inmobiliaria_voz/worker.py` | ✅ Nuevo | 5 endpoints `/voz/*` + healthz |
| `main.py` registro router voz | ✅ | prefix `/demos/voz/inmobiliaria` |
| Handoff doc Robert (5 archivos) | ✅ | `02_OPERACION_COMPARTIDA/handoff/elevenlabs-robert/` |
| Playbook wiki `worker-voz-elevenlabs.md` | ✅ v1 con 11 gotchas | `wiki/playbooks/` |
| Concepto wiki ElevenLabs + Twilio | ✅ | `wiki/conceptos/` |

### 📋 Pendiente para activación productiva

- [ ] Deploy backend a Coolify Hetzner Robert (`agentes.lovbot.ai`)
- [ ] Validar `curl https://agentes.lovbot.ai/demos/voz/inmobiliaria/healthz`
- [ ] Configurar agente en ElevenLabs (cuenta dev ElevenCreative Arnaldo) siguiendo `README-handoff.md` pasos 2-5
- [ ] Test desde "Test AI agent" — 5 flujos mínimo
- [ ] Robert paga ElevenLabs Creator (USD 22/mes)
- [ ] Robert compra Twilio AR (KYC 3-10 días)
- [ ] Conectar Twilio ↔ ElevenLabs en cuenta Robert
- [ ] Promover `workers/demos/inmobiliaria_voz/` → `workers/clientes/lovbot/robert_voz/`

### 🐛 Aprendizaje crítico de la sesión

Casi caí en asumir info errónea (worker Robert con Airtable LIVE en prod). Verdad real estaba en wiki Obsidian (Postgres + nada productivo aún). **Regla nueva**: consultar `PROYECTO ARNALDO OBSIDIAN/wiki/` ANTES de inferir stack desde código. Los docstrings de archivos pueden estar desactualizados (caso `robert_inmobiliaria/worker.py` decía Airtable cuando ya era Postgres).

### 📦 Commits pendientes (no ejecutados — esperan validación + push manual)

```
limpieza: remove workers legacy (_base, test_arnaldo, inmobiliaria_garcia)
feat(shared): calcom_client + catalog + lead_matcher + bant
feat(voz): worker demo voz inmobiliaria con 5 endpoints ElevenLabs
docs(handoff): elevenlabs-robert handoff completo (system prompt + tools + KB + README)
docs(wiki): playbook worker-voz-elevenlabs + conceptos ElevenLabs/Twilio
```

---

## 🕑 Hito mediodía 2026-04-24 — Bot comentarios + DMs Messenger + fix Robert horario

Sesión ~4h (06:30→12:30 ART) continuación directa de la sesión de la madrugada que dejó publicación FB + comentarios funcionando. Hoy expandimos a DM y emparejamos el saludo de Robert al de Mica.

### 🎯 Features completadas

| Feature | Estado | Notas |
|---|---|---|
| Bot comentarios FB con link `wa.me` dinámico | ✅ LIVE | Confirmado con comentario real ("¡Hola! Entiendo tu interés en conocer más...") |
| Fix Robert saludo menciona horario (igual que Mica) | ✅ Deployado (commit 91b9924) | Replicación del patrón `HORARIO_ATENCION` env var |
| Page Access Token permanente (Back Urbanizaciones) | ✅ En Supabase | Type PAGE, Expires NEVER, 12 scopes incluido `pages_messaging` |
| Persistent Menu eliminado | ✅ DELETE via Graph API | Liberó el channel de DMs para que lleguen al webhook |
| Handler `_responder_dm` código deployado | ✅ commit 675dc9e | Multi-tenant via Supabase. Responde con link wa.me. Probado con simulación |
| Webhook subscription `messages` | ✅ Subscrito | `feed`, `mention`, `ratings`, `messages` |

### 🐛 Bugs descubiertos + fixeados hoy (cadena)

1. **Python 3.11 f-string con comillas simples en `{}`** (commit 8be66c7) — UPDATE triple anidado con ternario crasheaba backend.
2. **Python 3.11 f-string triple anidado con ternario** (commit 570a473) — caso distinto del worker Mica demo. Misma raíz.
3. **Token lost via bash curl** — mi propio bug: intenté hacer UPDATE de Supabase via `curl -d ... python3 -c ...` con env vars mal escapadas → sobreescribió token con string vacío. Documentado en Gotcha #8 del runbook. **Regla nueva**: agente NO escribe tokens via bash. Solo usuario via SQL Editor.
4. **Tokens pegados en columna equivocada** (token_notas en vez de meta_access_token) — 2 veces en la misma sesión con Table Editor Supabase. Fix: regla de usar siempre SQL Editor.
5. **Automatizaciones Meta ocultas** — toggle "Preguntas frecuentes" decía gris pero seguía respondiendo. Persistent Menu era lo que interceptaba.

### ⏸️ Pendiente (no resuelto hoy)

**DMs reales de Messenger NO llegan al webhook del backend** aunque:
- Token válido con `pages_messaging`
- Suscripción al field `messages` activa
- Persistent Menu eliminado
- Automatización "Preguntas frecuentes" desactivada

**Código + simulación funcionan**: `_responder_dm` responde perfecto con link wa.me cuando se llama con payload manual. Pero Meta no dispara webhook cuando llega un DM real.

**Causas posibles a verificar** (documentadas en `feedback_meta_dm_webhook_debugging.md`):
- Automatizaciones adicionales ocultas en Business Suite Inbox
- Meta Argentina requiere opt-in previo del usuario
- Propagación de subscribe tarda 30+ min
- Config webhook a nivel App vs Page (verificar en developers.facebook.com)
- Otra capa de config que no mapeamos

**Dejar para próxima sesión** con screenshot completo de Business Suite Inbox Automations + verificación de webhook config en el developer console.

### 📦 Commits de la sesión (6 en master:main)

- `2e4f905` ← fix bug bot Mica WhatsApp Web (ayer madrugada, para contexto)
- `b450ac0` feat wa.me bot comentarios
- `8be66c7` fix syntax Python 3.11 #1
- `570a473` fix syntax Python 3.11 #2 (Mica demo)
- `91b9924` fix Robert horario HORARIO_ATENCION
- `675dc9e` feat bot DM Messenger

### 📝 Docs sincronizadas (4 silos)

- Silo 1 auto-memory: `feedback_meta_dm_webhook_debugging.md` nuevo
- Silo 2 wiki: `runbook-meta-social-automation.md` actualizado con Gotchas #5, #6, #7, #8
- Silo 3 operativo: este ESTADO_ACTUAL + debug-log actualizados
- Silo 4 código: 6 commits

### ⏭️ Próxima sesión

1. Screenshot completo Business Suite Inbox Automations para detectar automations ocultas
2. Verificar webhook config a nivel App en developers.facebook.com (tab Page → field messages activo?)
3. Si nada de eso resuelve → test con cuenta que nunca interactuó con la Page (opt-in AR)
4. Agregar soporte Instagram DMs cuando Maicol conecte IG a Page (scope `instagram_manage_messages`)
5. 2026-04-30: migrar a System User Admin permanente (regla 7 días Meta)

---

## ☀️ Hito mañana 2026-04-24 — Humanización v2: typing + splitter + horarios + sanitización

Sesión matutina ~3h (07:30→10:30 ART). Continuación de la sesión nocturna del 2026-04-23 que dejó buffer debounce + image describer funcionando. Hoy completamos las 2 features restantes de humanización + fixes derivados.

### 🎯 Features completadas (ambos bots demo)

| Feature | Mica | Robert |
|---|---|---|
| Typing indicator en todas las respuestas | ✅ Evolution + Meta | ✅ Meta context-aware con msg_id |
| Partición saludo en 2-3 chunks (solo primer turno) | ✅ GPT-4o-mini | ✅ GPT-4o-mini |
| Horarios de atención en saludo | ✅ hardcoded | ✅ variable `HORARIO_ATENCION` |
| Sanitización de nombre (`@rn@ldo → Arnaldo`) | ✅ ya existía | ✅ copiado de Mica |

### 🧱 Módulos nuevos en `workers/shared/`

- `typing_indicator.py` — wrapper genérico Meta + Evolution + YCloud fallback
- `message_splitter.py` — partición con gpt-4o-mini + fallback a 3 env keys (`OPENAI_API_KEY`, `LOVBOT_OPENAI_API_KEY`, `MICA_OPENAI_API_KEY`)

### 🐛 3 bugs descubiertos y fixeados (LECCIONES DURABLES)

1. **Python 3.11 no soporta f-strings triples anidadas** — commit `5fd48de` crasheó ambos backends ~15 min. Fix: variable intermedia `regla_1`. Ver `feedback_REGLA_python311_fstring_triples.md`.
2. **Coolify v4 beta no rebuildea automáticamente** — commits `105e113` y `91b9924` no se deployaron solos. Fix: `force=true` en API/UI. Ver `feedback_REGLA_coolify_cache_force.md`.
3. **Reglas del prompt BANT chocan entre sí** — "máximo 3-4 líneas" anulaba horarios. Fix: excepción explícita para primer turno. Ver `feedback_REGLA_prompt_bant_conflictos.md`.

### 🤹 Observación importante — múltiples agentes Claude paralelos

Durante la sesión aparecieron commits que no hice yo: `570a473`, `91b9924`, `b450ac0`, `8be66c7`. Arnaldo tiene sesiones Claude paralelas corriendo sobre el mismo repo. No hubo conflictos de merge (tocaron líneas distintas). Regla implícita: antes de tocar archivos del monorepo, `git pull` + `git log --oneline -5` para ver si otro agente ya hizo algo.

### 📦 Commits de la sesión (10 en master:main)

`6a2617e` módulos, `15eeda0` fix api_key, `888a258` Mica integrado, `5b21e15` Robert integrado, `5fd48de` primer fix (rompió), `570a473` fix Python 3.11 (otro agente), `017badb` horarios Mica, `105e113` horarios+sanitize Robert, `91b9924` refactor HORARIO_ATENCION (otro agente), `5a99bb1` excepción brevedad.

### 📝 Docs sincronizadas en 4 silos

- **Silo 1** (auto-memory): 3 reglas irrompibles nuevas — Python 3.11 triples, Coolify cache force, prompt BANT conflictos
- **Silo 2** (wiki): 2 conceptos nuevos (`typing-indicator-pattern`, `message-splitter-pattern`) + 1 síntesis (`2026-04-24-humanizacion-v2-horarios-sanitizacion`)
- **Silo 3** (memory operativo): este ESTADO_ACTUAL + debug-log
- **Silo 4** (código): 10 commits

### ⏳ Pendiente próxima sesión

1. **Deuda técnica `waba_clients`**: incluir schema en seed SQL de `lovbot_crm_modelo` para auto-clone
2. **Rotación de secrets** expuestos en screenshots de ayer (no urgente): `LOVBOT_OPENAI_API_KEY`, `OPENAI_API_KEY`, Redis Hetzner password
3. **Configuración de horarios por cliente** — hoy hardcoded, a futuro `INMO_DEMO_HORARIO` env var o campo Airtable/Postgres
4. **Replicar humanización a workers reales de clientes** — hoy solo en demos

---

## 🌅 Hito madrugada 2026-04-24 — Maicol Social Automation LIVE + bug bot Mica WhatsApp Web resuelto

Sesión ~6h (19:00 ART 23/04 → 01:30 ART 24/04). 2 logros grandes + documentación de runbook para no repetir debugging.

### 🏆 Logro #1 — Facebook publicando automático para Maicol (Back Urbanizaciones)

Primer cliente Arnaldo con social automation LIVE. Stack validado end-to-end:
- App Meta única: `Social Media Automator AI` (895855323149729) compartida con BM Back Urbanizaciones como Socio.
- Tabla multi-tenant Supabase `clientes` con registro `Back_Urbanizaciones` (Page Access Token permanente).
- Airtable Maicol `appaDT7uwHnimVZLM/tbl0QeaY3oO2P5WaU` populada con branding completo.
- Workflow n8n `xp49TY9WSjMtPvZK` schedule 10am ARG diario.
- Primera publicación FB verificada: Post ID `985390181332410_122106926216809418` con imagen IA aérea + branding (verde/dorado) + copy "Zonas de mayor crecimiento en Misiones para invertir".

**Pendiente**: Maicol debe conectar su IG `@backurbanizaciones` a la Page FB vía link `https://www.facebook.com/settings/?tab=linked_instagram` (30 seg de su parte). Cuando lo haga, IG se suma automático al feed diario sin tocar nada más.

### 🐛 Logro #2 — Bug bot Mica WhatsApp Web resuelto (commit 2e4f905)

Arnaldo reportó que el bot demo Mica (`+54 9 3765 00-5465`) no respondía cuando él escribía desde WhatsApp Web en la PC. Desde el celular sí respondía. Tras 5h descartando 3 falsos positivos (EVOLUTION_INSTANCE, fromMe filter, protocolo @lid), la causa real fue:

WhatsApp Web envía `message = {messageContextInfo: {...}, conversation: "hola"}` (2 keys). El parser `wa_provider._parse_evolution()` hacía `list(message.keys())[0]` → tomaba `messageContextInfo` como tipo → texto vacío → mensaje descartado silenciosamente.

Fix: iterar tipos conocidos (`conversation`, `extendedTextMessage`, `buttonsResponseMessage`, `listResponseMessage`) buscándolos por nombre en lugar de tomar primera key ciegamente. Mismo patrón robusto que ya usaba el worker de Lau.

Impacto: bug afectaba a todos los workers que usan `wa_provider` compartido. Leads desde WhatsApp Web se caían silenciosamente hace tiempo.

### 📚 Logro #3 — Documentación completa para próximos clientes

Sesión generó runbook definitivo para que onboarding social de cliente nuevo tome **30 min** en lugar de 6h:
- Silo 2 Wiki: `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/runbook-meta-social-automation.md` (300+ líneas con los 3 gotchas, SQL snippets, comandos curl de test, checklist).
- Silo 1 auto-memory: `feedback_REGLA_meta_social_onboarding.md` (regla irrompible: consultar runbook ANTES de improvisar) + `project_maicol_social_automation_live.md` (estado hito Maicol).
- Silo 3 operativo: este ESTADO_ACTUAL + `debug-log.md` con bug Mica + feature Maicol detallados.
- Silo 4 código: commit `2e4f905` (fix wa_provider) + `setup-social-automation.md` en `clientes/maicol/`.

### Estado técnico global al cierre sesión

| Componente | Estado |
|------------|--------|
| Bot Mica demo WhatsApp Web | ✅ Funciona desde PC y celular |
| Workflow social Arnaldo | ✅ Activo (`aJILcfjRoKDFvGWY`, 9am ARG) |
| Workflow social Maicol | ✅ Activo (`xp49TY9WSjMtPvZK`, 10am ARG) |
| Facebook Maicol | ✅ Publicando automático |
| Instagram Maicol | ⚠️ Bloqueado hasta Maicol conecte IG↔Page |
| LinkedIn Maicol | ⚠️ N/A (Maicol no tiene cuenta) |
| Bot comentarios Maicol | ⏸️ Fase 2 (endpoint `/social/meta-webhook` listo, solo falta suscribir webhook) |
| Token Maicol | ⏸️ Page Token permanente hoy — migrar a System User Admin 2026-04-30 |

### Próxima sesión — pendientes

1. Esperar que Maicol conecte IG (link enviado). Re-disparar test manual cuando confirme.
2. Activar webhook Meta para bot de comentarios automáticos (Fase 2).
3. Considerar generar 20 posts educativos pre-cargados para Back Urbanizaciones (rotación manual vs automática del worker).
4. Aplicar runbook para onboardear Cesar Posada cuando devuelva el brief.
5. 2026-04-30: migrar Maicol a System User Admin permanente (regla 7 días Meta se cumple).

---

## 🌙 Hito previo — noche 2026-04-23 — Humanización workers con Redis buffer + Vision GPT

Sesión nocturna ~5h (17:00→22:30 ART). Workers demo de Mica y Robert ahora **consolidan mensajes fragmentados** y **describen imágenes** antes de que el LLM responda. Validado end-to-end con WhatsApp real en ambos.

**Infra nueva**:
- Redis `redis-workers` en Coolify Hostinger (project microservicios) y Coolify Hetzner (project Agentes). Imagen `redis:7.2`, no expuesto al host.
- Env var `REDIS_BUFFER_URL` en `system-ia-agentes` de ambos VPS.
- Paquete `redis>=5.0.0` agregado a requirements.txt.

**Módulos nuevos** en `workers/shared/`:
- `message_buffer.py` — buffer debounce 8s (patrón Kevin Bellier). API: `buffer_and_schedule(tenant_slug, wa_id, texto, callback, extra, debounce_seconds)`.
- `image_describer.py` — normalizador imágenes → texto con GPT-4o-mini Vision. Helpers `download_media_meta()` (Meta) y `download_media_evolution()` (endpoint `/chat/getBase64FromMediaMessage`).

**Workers integrados** (tenant slugs):
- `workers/clientes/system_ia/demos/inmobiliaria/worker.py` → `mica-demo`
- `workers/clientes/lovbot/robert_inmobiliaria/worker.py` → `robert-demo`

**Workers NO tocados** (respetando REGLA #0): Maicol, Lau, inmobiliaria_garcia, test_arnaldo, social, demos viejos Arnaldo, _legacy.

**Bugs fixeados en la misma sesión**:
1. Coolify v4 beta marca env vars nuevas con `is_preview: True` → no se inyectan al container. Fix: recrear sin marcar "Is Preview".
2. `waba_clients` faltaba en `lovbot_crm_modelo` tras migración → bot Robert descartaba webhooks Meta Graph. Fix: `setup-table` + `register-existing` con phone_id `735319949657644`.
3. OpenAI Vision rechazaba bytes de Evolution (URLs encriptadas). Fix: usar endpoint `/chat/getBase64FromMediaMessage/{instance}` que descifra internamente.

**Commits pusheados** a master:main de `Arnaldo999/system-ia-agentes`:
- `dbaca83` chore: redis>=5.0.0 en requirements
- `58d5d85` feat(shared): message_buffer
- `3cafbc1` feat(mica-demo): integrar buffer
- `3d4753b` feat(robert-demo): integrar buffer
- `1de9697` feat(shared): image_describer
- `8236a0e` refactor(wa_provider): normalizar tipos image/audio Evolution
- `bb42bd5` feat(mica-demo): integrar image_describer
- `153330e` feat(robert-demo): integrar image_describer
- `6158186` fix(image_describer): sanitizar mime
- `5f9e178` fix(image_describer,mica-demo): Evolution download correcto + guard bytes

**Documentación creada (4 silos sincronizados)**:
- Silo 1 auto-memory: `feedback_buffer_debounce_workers.md`, `feedback_bug_waba_clients_migraciones.md`
- Silo 2 wiki: `wiki/conceptos/message-buffer-debounce.md`, `wiki/conceptos/image-describer.md`, `wiki/sintesis/2026-04-23-humanizacion-workers-redis.md`
- Silo 3 memory operativo: este ESTADO_ACTUAL + debug-log + ai.context.json actualizados
- Silo 4 código: 10 commits en master:main

**Pendiente próxima sesión**:
1. Feature #3 — Typing indicator "escribiendo..." (~20 min, Evolution `/chat/sendPresence` + Meta typing_indicator)
2. Feature #4 — Partición respuesta 2-3 chunks SOLO en saludo/presentación/horarios (~40 min)
3. Deuda técnica: incluir `waba_clients` en seed SQL de `lovbot_crm_modelo` para que se clone automáticamente en onboarding de cada cliente nuevo

---

## 🚀 Hito tarde — CRM Gestión Agencia Lovbot ✅ LIVE end-to-end (2026-04-23)

El CRM de gestión de la agencia Lovbot (leads → clientes → facturación) pasó de mockup HTML (22/04) a **LIVE end-to-end** hoy: BD + backend + frontend conectados y funcionales.

**Stack**:
- **BD**: `lovbot_agencia` en Postgres Hetzner (container `lovbot-postgres-p8s8kcgckgoc484wwo4w8wck`)
  - 6 tablas + 1 vista + triggers `updated_at` + 8 seeds (fuentes + pipeline stages)
- **Backend**: `https://agentes.lovbot.ai/agencia/*` — router FastAPI con **15 endpoints** (leads CRUD + conversión a cliente + soft delete + fuentes + pipeline)
- **Frontend agencia**: `https://admin.lovbot.ai/agencia` — login + listado leads + filtros + modal "Nuevo Lead" + modal detalle + convertir a cliente + soft delete
- **Frontend clientes**: `https://admin.lovbot.ai/clientes` — simplificado hoy (panel único fusionado + sidebar minimalista + token persistente sessionStorage)
- **Auth**: env var `LOVBOT_ADMIN_TOKEN` (64 chars, override en Coolify — NO el hardcoded `lovbot-admin-2026`)

**Env var nueva en Coolify Hetzner**:
- `LOVBOT_AGENCIA_PG_DB=lovbot_agencia` agregada a app FastAPI Robert (uuid `wwww8kwc4s044ow4s8ckw8og`)

**Slots preparados para integración futura con lead.center + Zapier**:
- `agencia_leads.fb_lead_id` (TEXT, UNIQUE) — ID lead en Facebook Ads
- `agencia_leads.lead_center_id` (TEXT) — ID lead en lead.center
- `agencia_leads.zapier_data` (JSONB) — payload completo del webhook Zapier

**Commits pusheados a master:main de `Arnaldo999/system-ia-agentes`**:
- `aa6ba94` — backend inicial (BD + router 15 endpoints)
- `f0d85f4` — frontend agencia conectado al backend
- `43c36c9` — dashboard `/clientes` fusionado (panel único + sidebar minimalista)
- `b4178a2` — token persistente en sessionStorage

⏳ **Pendiente — adelantos de Robert sobre lead.center + Zapier**:
Robert dijo por WhatsApp "te explico la próxima semana, te muestro lo que tengo y uso". Esperando que mande info para armar el webhook FB Ads → lead.center → Zapier → `POST /agencia/leads` con payload completo (campos `fb_lead_id`, `lead_center_id`, `zapier_data` ya reservados en la tabla).

---

## 🎯 Regla operativa NUEVA — Coolify default (2026-04-22)

Desde ahora, **cualquier HTML/sitio/propuesta/formulario nuevo se deploya en Coolify Hostinger**, no en Vercel. Motivo: cupo Hobby Vercel 100 deploys/día se agotó en 2 sesiones seguidas.

Patrón: archivos en `backends/system-ia-agentes/clientes-publicos/{slug}/` → `git push` → auto-deploy en ~30s → URL `agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/archivo.html`.

**Vercel solo se mantiene para**:
- Apps existentes ya productivas (`crm.lovbot.ai` hasta migrarse, `system-ia-agencia.vercel.app` hasta que Mica compre dominio)

**Migraciones agendadas**:
- **Robert** → Coolify Hetzner Robert (2026-04-23, tras reset cupo Vercel de hoy)
- **Mica** → diferida (sin dominio propio aún)

Ver doc completa: `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/coolify-default-deploy.md`

---

## 🎯 Abierto — Cliente nuevo Cesar Posada (agencia turismo)

**Estado**: propuesta enviada, esperando brief.

**Contacto**: Cesar Posada (persona, la marca de su agencia se confirma en el brief)
**Vertical**: agencia de turismo / viajes
**Cliente de**: Arnaldo (directo, NO Mica ni Robert)

**Entregables LIVE**:
- Formulario: https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/brief.html
- Propuesta: https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/propuesta.html

**Precios enviados**:
- Implementación única: USD 300
- Mantenimiento: USD 80/mes

**Mensaje WhatsApp enviado**: Arnaldo ya le mandó los 2 links con el resumen.

**Próximos pasos** (cuando Cesar envíe el brief .md):
1. Copiar el brief recibido a `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/cesar-posada/brief-recibido-YYYY-MM-DD.md`
2. Crear base Airtable nueva para turismo (tablas: Leads, Clientes_Activos, Paquetes, Asesores, Conversaciones, Destinos)
3. Scaffold worker en `workers/clientes/arnaldo/cesar-posada/worker.py` basado en patrón Maicol
4. Scaffold CRM web en `demos/turismo/dev/crm-v2.html` como template del nicho
5. Onboarding WhatsApp YCloud
6. Deploy Coolify Hostinger + smoke tests
7. Capacitación

**Docs de referencia**:
- Entidad Obsidian: `PROYECTO ARNALDO OBSIDIAN/wiki/entidades/cesar-posada.md`
- Síntesis: `PROYECTO ARNALDO OBSIDIAN/raw/arnaldo/sesion-2026-04-22-brief-cesar-posada.md`
- Patrón reutilizable: `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/onboarding-cliente-nuevo-arnaldo.md`

---

## 🎯 Hito cerrado — CRM v3 Mica COMPLETO (misma jornada que Robert)

Replicado el modelo v3 en el stack Airtable de Mica con paridad funcional completa. Sesión 3 de 3 fases:

- **Fase 1** — Schema Airtable `appA8QxIhBYYAHw0F`: 39 campos nuevos agregados (roles, linkedRecords polimórficos, campos cuotas, etc.). Tenant mica-demo con subniche=mixto.
- **Fase 2** — Backend adapter `db_airtable.py` +978 líneas: helpers `_at_*`, serializer polimórfico, 12 endpoints nuevos espejo de Robert. Smoke tests 11/11 OK.
- **Fase 3** — Frontend `demos/SYSTEM-IA/dev/`: 5 JS nuevos, `crm-v2.html` +657 líneas, paleta ámbar respetada (64× `#f59e0b`, 0× purple). Deploy Vercel inmediato.

**Commits Mica**: `5ef5303` → `a9dc86a` → `a616f70` → `e3817bb`.
**Producción Vercel Mica**: `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo` (deployado).
**Backend Mica**: `https://agentes.arnaldoayalaestratega.cloud/clientes/system_ia/demos/inmobiliaria`.

## 🎯 Hito cerrado — CRM v3 Robert completo

Ayer y hoy terminamos el refactor arquitectónico del CRM v2 de Robert. 18h de trabajo, 16+ commits, todo en producción con smoke tests verdes.

### Qué cambió (backend — Postgres `lovbot_crm_modelo`)
- **Tabla `clientes_activos`** ahora es la persona única del ecosistema. Campo `roles TEXT[]` permite acumular [comprador, inquilino, propietario] sin duplicar registros.
- **Tabla `contratos`** polimórfica con `tipo` + `item_tipo` + `item_id`. Un endpoint unificado `POST /crm/contratos` con 3 ramas (cliente_activo_id / convertir_lead_id / cliente_nuevo).
- **Tabla `alquileres`** nueva para datos específicos del tipo='alquiler' (fechas, garante).
- **Tablas GESTIÓN-Agencia** con CRUD real: `inmuebles_renta`, `inquilinos`, `pagos_alquiler`, `liquidaciones`, `propietarios`. Antes eran placeholders.
- **Lotes granulares**: `lotes_mapa` con UNIQUE `(tenant, loteo_id, manzana, numero_lote)`. La inmobiliaria puede agregar/borrar/renombrar manzanas y lotes individualmente.
- **20+ endpoints nuevos** en el worker Robert cubriendo todo esto.

### Qué cambió (frontend — `crm.lovbot.ai/dev/crm-v2`)
- Modal unificado "Nuevo contrato" con **3 pasos** (Cliente → Activo → Contrato).
- **3 puertas de entrada** al modal: panel Clientes, click lote en mapa, botón Convertir en lead.
- **Sidebar GESTIÓN** con 3 grupos acordeón colapsables (Desarrolladora / Agencia / Mixto) — siempre todos visibles.
- Modales "Nuevo inquilino / propietario" con **autocomplete** que busca si la persona ya existe (evita duplicados).
- **Tab "Relaciones"** en ficha de cliente — ficha 360 con contratos + alquileres + inmuebles propios.
- **Panel Loteos reescrito** — lee `lotes_mapa` real, permite CRUD granular con feedback visual.
- **CORS corregido** en backend (whitelist explícita para crm.lovbot.ai + vercel.app + localhost).

### Estado producción
- ✅ Backend Coolify Hetzner `agentes.lovbot.ai` — todos los endpoints respondiendo 200
- ✅ DB Postgres `lovbot_crm_modelo` — schema v3 aplicado, datos limpios (smoke tests borrados)
- ✅ Frontend Vercel `crm.lovbot.ai/dev/crm-v2` — cupo se resetea cada 24h (Plan Hobby), a veces 5 commits se acumulan y deployan juntos

### Bugs destacados fixeados
1. `tenant_slug` duplicado en `_crud_generico` (commit `d26d634`) — rompía POST a propietarios/inmuebles/inquilinos/pagos/liquidaciones.
2. UNIQUE constraint `lotes_mapa` tenía 2 simultáneos (auto-generado sin manzana + el nuevo con manzana) — bloqueaba A-1 + B-1 coexistir (commit `0fa97c6` + `ba5c42d`).
3. Lote vendido no mostraba cliente — triple bug: endpoint equivocado `/crm/clientes` vs `/crm/activos` + ID con prefijo `pg_16` vs `16` + mayúsculas inconsistentes `Nombre` vs `nombre` (commit `d5002d6`).
4. HTTP 410 masivo en consola — 10 URLs `airtableusercontent.com` expiradas en `propiedades.imagen_url` (commit `9b7eb4f` + `8fb0d73`).
5. CORS no configurado + modal legacy llamando `/crm/activos/pq_15` (commit `b39264c`).

### Pendientes inmediatos
1. **Validación visual del usuario** en `crm.lovbot.ai/dev/crm-v2` — probar en navegador las 3 puertas del modal + tab Relaciones + lotes granulares + paneles GESTIÓN.
2. **Vercel deploy** del último commit `d7b05d0` (tab Relaciones) — puede estar esperando cupo.
3. **Sync dev → prod HTML** (`sync-crm-prod`) cuando el usuario valide todo.

## 🎯 Próximo paso — validación visual Mica + pendientes menores

1. **Hard reload** en `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo` y probar:
   - PIN demo `1234`
   - Modal unificado "Nuevo contrato" desde panel Clientes Activos
   - Tab "Relaciones" en ficha de cliente
   - Paneles GESTIÓN (Inmuebles, Inquilinos, Pagos, Liquidaciones, Propietarios) — crear 1 de cada para validar
   - Sidebar acordeón 3 grupos (Desarrolladora / Agencia / Mixto)

2. **Panel loteos granular Mica** — pendiente portar CRUD por manzana/lote (botones +Manzana, +lote, renombrar, borrar individual). Backend ya tiene `/crm/lotes-mapa/seguro` y `/crm/loteos/{id}/lotes`.

3. **Tipos granulares** Airtable Contratos.Tipo — autorizar PATCH si se quiere `venta_lote` vs `venta_casa` a nivel DB (hoy se guarda como `venta` + subtipo en `Item_Descripcion`).

4. **Sync dev → prod HTML** (`sync-crm-prod`) cuando el usuario valide todo.

## 🎯 Pendientes viejos del embedded signup (sigue abierto)

Hoy no se tocó. Sigue como estaba el 21 al final del día:

**Objetivo**: migrar el número demo inmobiliaria de Mica (`+54 9 3765 00-5465`, hoy en Evolution) a Meta Cloud API vía el Tech Provider de Robert.

**Bloqueante**: desconectar el número de Evolution + esperar 24-72h + desinstalar WhatsApp del celular antes del test end-to-end del signup.

Ver commits recientes: `e71028e`, `17b899d`, `d26d634`, `ba5c42d`, `b39264c`, `231eebf`, `d5002d6`, `b0d9a5c`, `9b7eb4f`, `8fb0d73`, `81df11d`, `ca73425`, `9cff805`, `d7b05d0`.

Ver docs detallados:
- `PROYECTO ARNALDO OBSIDIAN/raw/robert/sesion-2026-04-22-crm-v3-robert.md`
- `PROYECTO ARNALDO OBSIDIAN/wiki/sintesis/2026-04-22-crm-v3-robert.md`
- `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/persona-unica-crm.md`
- `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/contratos-polimorficos.md`
