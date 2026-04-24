# Debug y errores frecuentes

## [2026-04-24 mañana] feature + 3 bugs | Humanización v2 — typing + splitter + horarios + sanitización

Sesión matutina ~3h (07:30→10:30 ART). Completamos features #3 (typing indicator) y #4 (partición saludo) más ajustes derivados (horarios + sanitize nombre Robert). Durante el camino aparecieron 3 bugs que ya tienen regla durable en auto-memory.

### Bug #1 — Python 3.11 no soporta f-strings con comillas triples anidadas

**Síntoma**: ambos backends crashearon tras push del commit `5fd48de`. Log:
```
File "/app/workers/clientes/system_ia/demos/inmobiliaria/worker.py", line 1751
    {f"""1. En este PRIMER turno tenés que hacer DOS cosas en UN solo mensaje:
    ^^
SyntaxError: f-string: expecting '}'
```

**Diagnóstico**: intenté usar ternaria inline `{f"""..."""  if X else f"""..."""}` dentro de un f-string padre. Python 3.11 no parsea ese patrón (Python 3.12+ sí, pero Coolify usa 3.11).

**Fix** (commit `570a473` — lo hizo otro agente Claude paralelo): variable intermedia `regla_1` fuera del f-string padre:
```python
if es_primer_turno_saludo:
    regla_1 = "En este PRIMER turno tenés que hacer DOS cosas..."
else:
    regla_1 = f"SOLO podés preguntar por **{siguiente_campo}**..."

bloque_siguiente = f"""...
🚫 REGLAS IRROMPIBLES:
{regla_1}
..."""
```

**Regla durable**: ver `feedback_REGLA_python311_fstring_triples.md` en auto-memory. Es el segundo incidente del mismo patrón (antes fue `re.sub()` con backslash dentro de f-string).

### Bug #2 — Coolify v4 beta no rebuildea automáticamente aunque haya commits nuevos

**Síntoma**: después de pushear commits `105e113` (horarios Robert) y luego `91b9924` (refactor a variable `HORARIO_ATENCION`), el bot seguía respondiendo SIN horarios. Verificación por terminal Coolify confirmó que el código estaba en el container, pero el container runtime usaba imagen cacheada.

**Diagnóstico**:
- `last_online_at` del API Coolify mostraba timestamp de un deploy anterior al commit nuevo
- El endpoint `/api/v1/deploy?force=false` marcaba `status: finished` pero no rebuildeaba
- Incluso `/api/v1/applications/{uuid}/restart` dejaba el mismo timestamp

**Fix**: siempre disparar con `force=true`:
```bash
curl -X POST -H "Authorization: Bearer TOKEN" \
  "COOLIFY/api/v1/deploy?uuid=XXX&force=true"
```

O en UI: botón naranja **"Redeploy"** (NO "Restart").

**Señal temprana**: si hacés push y `last_online_at` del API no cambia en ~5 min, auto-deploy falló. Disparar manual.

**Regla durable**: ver `feedback_REGLA_coolify_cache_force.md` en auto-memory.

### Bug #3 — Reglas del prompt BANT se anulan entre sí

**Síntoma**: agregué horarios al `ejemplo_saludo` del worker Robert. Código deployado OK (verificado con grep en container). Pero el LLM respondía sin mencionar horarios.

**Diagnóstico**: línea 1745 del prompt decía *"Mensajes cortos: máximo 3-4 líneas"*. Esa regla de brevedad general chocaba contra "incluir bienvenida + empresa + zonas + horarios + pregunta nombre". El LLM elige la restricción más dura y descarta contenido nuevo.

**Fix** (commit `5a99bb1`): excepción explícita en la regla:
> *"máximo 3-4 líneas **en turnos BANT (después del saludo)**. EXCEPCIÓN: en el PRIMER turno, el mensaje DEBE incluir bienvenida + empresa + zonas + HORARIOS DE ATENCIÓN + pregunta de nombre. No lo recortes por brevedad."*

Aplicado en ambos workers (Mica y Robert) para prevención.

**Regla durable**: ver `feedback_REGLA_prompt_bant_conflictos.md` en auto-memory. Antes de agregar requisitos al prompt BANT, grep de restricciones existentes (`máximo\|breve\|corto`) y coordinar con excepciones explícitas.

### Docs relacionadas

- Wiki: `wiki/sintesis/2026-04-24-humanizacion-v2-horarios-sanitizacion.md`, `wiki/conceptos/typing-indicator-pattern.md`, `wiki/conceptos/message-splitter-pattern.md`
- Auto-memory: 3 feedback_REGLA_* nuevos detallados arriba

---

## [2026-04-23 noche] feature + 3 bugs | Humanización workers — Redis buffer + Vision GPT + fix routing WABA

Sesión ~5h (17:00→22:30 ART). Workers demo de Mica y Robert ahora consolidan mensajes fragmentados y describen imágenes. Validado end-to-end con WhatsApp real. Durante la implementación aparecieron 3 bugs — 2 son clase de error que se van a repetir.

### Bug #1 — Coolify v4 beta marca env vars nuevas con `is_preview: True` por default

**Síntoma**: `os.environ['REDIS_BUFFER_URL']` levanta `KeyError` en runtime aunque la API de Coolify confirma que la env var existe con valor correcto.

**Diagnóstico**: la env var aparece en `/api/v1/applications/{uuid}/envs` con `is_runtime: True` y valor correcto — PERO también con `is_preview: True`. El flag hace que la var SOLO se inyecte en deploys preview, no en production. El container productivo levanta SIN esa env var.

**Cómo detectarlo**: `curl -H "Authorization: Bearer TOKEN" https://coolify.xxx/api/v1/applications/{uuid}/envs | grep -A5 REDIS_BUFFER_URL`. Si ves `is_preview: True`, es este bug.

**Fix**: borrar la env var (`DELETE /api/v1/applications/{uuid}/envs/{env_uuid}`) y recrearla por UI desmarcando explícitamente "Is Preview" si aparece. La API pública no permite editar ese flag después de crear.

**Regla**: al crear una env var nueva por UI de Coolify, **explícitamente desmarcar "Is Preview"**. Si ya la creaste y ves comportamiento raro, borrá y recreá — no pierdas tiempo debugeando el código del worker.

### Bug #2 — Tabla `waba_clients` faltante en `lovbot_crm_modelo` tras migración Coolify

**Síntoma**: bot Robert demo deja de responder a WhatsApp. Logs del webhook Meta multi-tenant:
```
POST /webhook/meta/events HTTP/1.1 200 OK
[META-EVENTS] phone_id='735319949657644' no registrado en waba_clients — ignorado
[DB] Error obtener_waba_client_por_phone: relation "waba_clients" does not exist
```

**Diagnóstico**: Meta Graph entrega el webhook al router centralizado `/webhook/meta/events` que hace lookup en tabla `waba_clients` para enrutar por `phone_number_id`. Tras la migración Lovbot a Coolify Hetzner del 2026-04-23 mañana, el worker apunta a DB `lovbot_crm_modelo` que NO tiene esa tabla (seed SQL de la DB modelo no la incluye).

**Fix aplicado** desde terminal del container Hetzner:
```bash
# 1) Crear tabla (idempotente)
curl -X POST "http://localhost:8000/clientes/lovbot/inmobiliaria/admin/waba/setup-table" \
  -H "X-Admin-Token: lovbot-admin-2026"

# 2) Registrar el bot (usa $META_ACCESS_TOKEN del env del container)
curl -X POST "http://localhost:8000/clientes/lovbot/inmobiliaria/admin/waba/register-existing" \
  -H "X-Admin-Token: lovbot-admin-2026" \
  -H "Content-Type: application/json" \
  -d "{
    \"client_name\": \"Robert Demo Inmobiliaria\",
    \"client_slug\": \"robert-demo\",
    \"waba_id\": \"1416819116022399\",
    \"phone_number_id\": \"735319949657644\",
    \"access_token\": \"$META_ACCESS_TOKEN\",
    \"worker_url\": \"https://agentes.lovbot.ai/clientes/lovbot/inmobiliaria/whatsapp\",
    \"display_phone\": \"+52 1 998 743 4234\"
  }"
```

**Fix durable pendiente**: agregar schema `waba_clients` al seed SQL de `lovbot_crm_modelo` para que se clone automáticamente con cada cliente nuevo creado vía `/admin/crear-db-cliente`. Documentado en `feedback_bug_waba_clients_migraciones.md` del auto-memory.

**Regla**: si un bot Lovbot migrado o de cliente nuevo no responde después de que todos los checks usuales pasan (webhook OK, env vars OK), chequear primero que la tabla `waba_clients` existe y que el `phone_number_id` está registrado.

### Bug #3 — OpenAI Vision rechaza bytes de media Evolution (HTTP 400)

**Síntoma**: `image_describer: OpenAI HTTP 400 — "You uploaded an unsupported image. Please make sure your image has of one the following formats: ['png', 'jpeg', 'gif', 'webp']"`.

**Diagnóstico paso a paso**:
1. Primera sospecha: mime incorrecto. Evolution devolvía `Content-Type: application/octet-stream`. Implementamos sanitización de mime con magic numbers de los bytes. Siguió fallando.
2. Agregamos log defensivo `_looks_like_image()` + `size=X first_bytes_hex=Y` antes de llamar OpenAI. Confirmó que los bytes NO eran imagen real.
3. Causa real: las URLs `imageMessage.url` que Evolution devuelve en el webhook **apuntan a media encriptado de WhatsApp**. Un GET directo a esa URL NO descarga la imagen — devuelve bytes inútiles (encriptados o payload de error).

**Fix aplicado**: usar endpoint `/chat/getBase64FromMediaMessage/{instance}` de Evolution API. Ese endpoint descifra internamente el media de WhatsApp y devuelve base64 decodificable a JPEG real. Patrón copiado del worker de Lau que ya lo hacía bien.

**Regla**: para descargar media de Evolution, NUNCA usar la URL del payload. Siempre usar el endpoint `/chat/getBase64FromMediaMessage/{instance}` con el `message_id` extraído de `raw["key"]["id"]`. El endpoint prueba 3 variantes de payload (Evolution v1 y v2) para compatibilidad.

### Commits de esta sesión

`dbaca83` chore: redis>=5.0.0 | `58d5d85` feat: message_buffer | `3cafbc1`+`3d4753b` integrar buffer en Mica+Robert | `1de9697` feat: image_describer | `8236a0e` refactor wa_provider | `bb42bd5`+`153330e` integrar describer | `6158186` fix mime | `5f9e178` fix Evolution download

### Docs relacionados

- Wiki: `wiki/sintesis/2026-04-23-humanizacion-workers-redis.md`, `wiki/conceptos/message-buffer-debounce.md`, `wiki/conceptos/image-describer.md`
- Auto-memory: `feedback_buffer_debounce_workers.md`, `feedback_bug_waba_clients_migraciones.md`

---

## [2026-04-23] bug crítico + feature | Bot Mica WhatsApp Web + Maicol Social Automation LIVE

### Bug #1 — Bot Mica no respondía desde WhatsApp Web (5h diagnóstico, fix en 20 líneas)

**Síntoma**: Arnaldo le escribía "Hola" al bot demo Mica (+54 9 3765 00-5465) desde WhatsApp Web en la PC y el bot no respondía nada. Desde el celular SÍ respondía. Los otros bots del ecosistema (Lau, Robert) funcionaban normal desde PC.

**Falsos positivos descartados** (NO eran la causa, gastaron tiempo):
1. `EVOLUTION_INSTANCE` mal seteado en Coolify → el valor correcto `MICA_DEMO_EVOLUTION_INSTANCE=Demos` ya estaba bien.
2. Filtro `fromMe` de Evolution → el mensaje no venía marcado como fromMe.
3. Protocolo `@lid` de WhatsApp Web (Linked Devices) → agregué fallbacks por robustez pero no era la causa.

**Causa real identificada con logging temporal**: WhatsApp Web manda el campo `message` con **2 keys** en lugar de 1. Ejemplo de payload:
```json
"message": {
  "messageContextInfo": {...},    ← metadata, primer key
  "conversation": "hola"          ← texto real, segundo key
}
```

Mientras que desde el celular manda solo `{"conversation": "hola"}`.

El parser `wa_provider._parse_evolution()` línea 430 hacía `msg_type = list(message.keys())[0]` → tomaba `messageContextInfo` (metadata) como tipo → no matcheaba ninguna rama del if/elif → `texto` quedaba vacío → handler descartaba el mensaje con `return None`.

**Fix** (commit `2e4f905` en `wa_provider.py`):
```python
# ANTES:
msg_type = list(message.keys())[0] if message else ""

# DESPUÉS:
texto = ""
msg_type = ""
if "conversation" in message:
    msg_type = "conversation"
    texto = message.get("conversation", "")
elif "extendedTextMessage" in message:
    msg_type = "extendedTextMessage"
    texto = message.get("extendedTextMessage", {}).get("text", "")
# ... iteración similar para buttonsResponseMessage / listResponseMessage
```

El worker de Lau no tenía el bug porque usa su propio parser local con `.get()` encadenado robusto, no `wa_provider.parse_incoming()`.

**Impacto**: bug afectaba a TODOS los workers que usan `wa_provider` (Mica, Maicol si hubiera usado Evolution, social comments). Leads desde WhatsApp Web se caían silenciosamente desde hacía tiempo.

**Regla**: antes de confiar en `list(dict.keys())[0]` para tomar primera key, validar que el dict tenga UNA sola key esperada. WhatsApp Web / Desktop agrega metadata extra.

### Feature — Maicol Back Urbanizaciones primer cliente Arnaldo con Social Automation LIVE

**Qué**: publicación automática diaria en Facebook (y pronto Instagram) para la página Back Urbanizaciones de Maicol, usando el worker social del backend + Gemini para generar copy + imagen con branding + Page Access Token de Meta.

**Stack implementado**:
- App Meta única del ecosistema: `Social Media Automator AI` (App ID `895855323149729`, dueño BM `Emprender en lo Digital` de Arnaldo) compartida con BM cliente como Socio.
- Tabla multi-tenant Supabase: `clientes` (proyecto `pczrezpmdugdsjrxspjh`). Cada fila = un cliente con su `fb_page_id`, `ig_account_id`, `meta_access_token`, `airtable_base_id`, `airtable_table_id`.
- Airtable Maicol: `appaDT7uwHnimVZLM` tabla Branding `tbl0QeaY3oO2P5WaU` record `rec8ZOSA7fZaAQAd4`. Tiene: Industria, Servicio, Público, Tono, Reglas, Estilo Visual, Colores, CTA, Logo, Facebook Page ID, IG Business Account ID.
- Endpoint orquestador: `POST /social/publicar-completo` en backend `agentes.arnaldoayalaestratega.cloud`. Recibe `cliente_id` + `datos_marca` (brandbook), genera copy + imagen + publica en las 3 redes.
- Workflow n8n: `xp49TY9WSjMtPvZK` (📱 Maicol — Publicación Diaria) schedule 10am ARG diario. Trigger → Airtable brandbook → POST endpoint → IF error → Telegram alert.

**Gotchas descubiertos (documentados en runbook)**:
1. **User Token ≠ Page Access Token**. Primer intento falló con error 190 "Invalid JSON for postcard". Fix: desde Graph API Explorer query `<fb_page_id>?fields=access_token` devuelve Page Token derivado. Si el User Token era long-lived (60 días), el Page Token es **permanente** (no expira mientras no cambie password FB).
2. **System User Admin requiere 7 días de antigüedad** del admin del BM cliente. Arnaldo fue agregado al BM Back Urbanizaciones hoy, no puede crear System User Admin hasta 2026-04-30. Workaround: Page Access Token permanente cubre el gap.
3. **IG debe estar conectado a Page FB**. Error 10 "Application does not have permission for this action" apareció al publicar en IG. Causa: Back Urbanizaciones IG no estaba vinculado a la Page FB (aunque ambos estén en el mismo BM). Solución: link directo para el dueño del IG `https://www.facebook.com/settings/?tab=linked_instagram` → Click "Conectar cuenta" → login IG → aceptar permisos. Este paso lo hace el cliente (tiene sus creds IG).

**Resultado sesión**:
- ✅ Facebook publicando automático. Primera publicación verificada visualmente: imagen aérea generada por IA con zonas rojas/amarillas, headline "Zonas de mayor crecimiento en Misiones para invertir", logo BACK en esquina, colores de marca aplicados. Post ID `985390181332410_122106926216809418`.
- ⚠️ Instagram pendiente solo de que Maicol conecte su IG a la Page FB (link ya enviado).
- ✅ Documentación completa en [wiki runbook](../PROYECTO%20ARNALDO%20OBSIDIAN/wiki/conceptos/runbook-meta-social-automation.md) + auto-memory `feedback_REGLA_meta_social_onboarding.md` para replicar en 30 min con próximos clientes.

**Regla**: onboarding social de cliente nuevo **SIEMPRE** consultar el runbook ANTES de improvisar. Los 3 gotchas no son obvios de docs oficiales de Meta y cuestan 6h si se re-debugean.

---

## [2026-04-23] feature | CRM Agencia Lovbot LIVE end-to-end — incidentes menores durante el build

Durante la construcción end-to-end del CRM Agencia Lovbot (commits `aa6ba94`, `f0d85f4`, `43c36c9`, `b4178a2`) aparecieron 2 incidentes menores que se resolvieron en sesión. Dejo registro para no repetir.

### Incidente 1 — Puerto Coolify Hetzner no accesible desde fuera (IP:puerto directo)

**Síntoma**: `curl http://5.161.235.99:8000/api/v1/...` timeout después de 136 segundos. Intento de llamar API Coolify Hetzner vía IP directa para agregar env var nueva.

**Causa**: El puerto 8000 de Coolify Hetzner solo está accesible por HTTPS en `https://coolify.lovbot.ai` (el IP:puerto directo está firewalleado en el VPS Hetzner).

**Fix**: Siempre usar `https://coolify.lovbot.ai/api/v1/...` para llamadas a la API Coolify de Robert. La var `COOLIFY_ROBERT_URL=http://5.161.235.99:8000` del `.env` es LEGACY — hay que actualizarla a `https://coolify.lovbot.ai`.

**Regla**: Si la llamada a Coolify Hetzner timeouta, chequear que estés usando el dominio HTTPS y no el IP:puerto. Para Coolify Hostinger (Arnaldo) el patrón es el mismo: `https://coolify.arnaldoayalaestratega.cloud`.

### Incidente 2 — Contrato frontend/backend desajustado en primer smoke test del CRM Agencia

**Síntoma**: Primer `POST /agencia/leads` desde el frontend devolvía `422 {"type":"missing","loc":["body","nombre_contacto"],"msg":"Field required"}`.

**Causa**: El frontend mandaba campos con nombres viejos del mockup (`nombre`, `contacto_nombre`) pero el schema Pydantic del backend espera el contrato real:
- `nombre_contacto` (required) + `apellido_contacto` (opcional) + `nombre_empresa` (opcional) — tres campos SEPARADOS, no un "nombre" único
- `fuente_id` (INT, required) — no `fuente_slug` (string)

**Fix aplicado**: Frontend adaptado al contrato real del backend:
- Modal de "Nuevo Lead" con inputs separados: `nombre_contacto`, `apellido_contacto`, `nombre_empresa`
- Select de fuente guarda el **slug visible** para UX pero internamente mapea a `fuente_id` INT usando `FUENTES_CACHE` local (se carga al iniciar desde `GET /agencia/fuentes`)

**Regla**: Antes de conectar frontend a backend nuevo, hacer **1 POST de prueba desde curl** con el contrato exacto del schema Pydantic, confirmar la shape real del payload, y recién ahí construir el formulario. Evita ciclos fix/deploy/test por discrepancias de nombres de campos.

---

## [2026-04-23] migración completa | Lovbot 100% en Coolify Hetzner — sale de Vercel productivo

**DNS propagado** (Arnaldo cambió en cPanel):
- `crm.lovbot.ai`: CNAME Vercel → A `5.161.235.99` ✅
- `admin.lovbot.ai`: CNAME Vercel → A `5.161.235.99` ✅

**Estado post-migración (validado con `--resolve` + ventana incógnito)**:
- `https://crm.lovbot.ai/dev/crm-v2` → nginx Coolify, "CRM — Powered by LovBot IA" ✅
- `https://admin.lovbot.ai/clientes` → nginx Coolify, "Lovbot Admin — Gestión de Clientes" ✅
- `https://admin.lovbot.ai/agencia` → nginx Coolify, "Lovbot Agencia — CRM Gestión de Leads" ✅
- SSL Let's Encrypt automático (Traefik provisionó solo cuando DNS resolvió)
- Server header: `nginx/1.29.8` (ya no Vercel)

**Bug fix nav del sidebar (commit `1851623`)**:
- Sintoma: click en "Clientes CRM" desde `agencia` daba 404
- Causa: hrefs apuntaban a `/dev/admin/clientes` (path Vercel viejo). En Coolify los archivos están en raíz.
- Fix: `/dev/admin/clientes` → `/clientes`, `/dev/admin/agencia` → `/agencia` (4 ocurrencias en 2 archivos).

**Bug autodeploy `lovbot-admin-internal` no funcionaba**:
- Causa: app fue creada con source "Public Repository" en lugar de "GitHub App oficial"
- Resultado: GitHub no avisaba a Coolify Hetzner cuando había push (solo a Coolify Hostinger Arnaldo)
- Fix: configurar webhook manual en GitHub Settings → Webhooks
  - URL: `https://coolify.lovbot.ai/webhooks/source/github/events/manual`
  - Secret: `a8f3d2e1b9c7456082f1a3d4e5b6c7d8a9e0f1b2c3d4e5f6a7b8c9d0e1f2a3b4`
  - Validado con ping ✅
- **Lección**: cuando se crea app Coolify nueva, SIEMPRE elegir "GitHub App oficial" para autodeploy automático sin trámites.

**Token admin (LOVBOT_ADMIN_TOKEN)**:
- Valor actual: `lovbot-admin-2026` (default del código en `workers/shared/tenants.py:213`)
- ⚠️ Pendiente seguridad: rotar a token random fuerte (`openssl rand -hex 32`) + override en Coolify env vars

**Hoy NO se tocó** (mantenido como fallback):
- `vercel.json` raíz Mission Control → sigue sirviendo URLs Lovbot via Vercel
- App Mica (`system-ia-agencia.vercel.app/system-ia/*`) → sigue en Vercel hasta dominio propio
- Maicol (`crm.backurbanizaciones.com`) → sigue en Vercel

**Wiki Obsidian actualizada masivamente**:
- 7 páginas Robert con info Vercel desactualizada → actualizadas a Coolify Hetzner
- Síntesis nueva: `wiki/sintesis/2026-04-23-migracion-lovbot-coolify.md`
- Memoria persistente Silo 1: `feedback_lovbot_100_coolify_2026_04_23.md`
- 3 feedbacks actualizados: `feedback_crm_dev_prod`, `feedback_no_tocar_lovbot_robert`, `feedback_supabase_tenants_lovbot`

---

## [2026-04-23] deploy | CRM modelo Lovbot migrado a Coolify Hetzner

**Razón**: cuota Vercel Hobby cerca del límite. CRM es el frontend principal de clientes Lovbot.

**App Coolify creada**:
- Nombre: `lovbot-crm-modelo`
- UUID: `wcgg4kk0sw0g0wgw4swowog0`
- Project: `Agentes` (`ck0kccsws4occ88488kw0g80`) / Env: `production`
- Repo: `Arnaldo999/system-ia-agentes` / branch `main`
- base_directory: `/01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev`
- Dockerfile: `dev/Dockerfile` (nginx:alpine, nombre estándar — Coolify lo busca automaticamente)
- FQDN: `https://crm.lovbot.ai`
- Deploy status: `running:healthy` (2026-04-23)
- Commit: `27367cf`

**DNS pendiente (Arnaldo debe hacer manualmente)**:
- Proveedor DNS: cPanel de `lovbot.ai`
- Registro: A record `crm` → `5.161.235.99`
- TTL recomendado: 300 (5 min para propagación rápida)
- Hasta que el DNS propague: Vercel sigue respondiendo en `crm.lovbot.ai` (fallback OK)

**Validación pre-DNS (via Host header al VPS)**:
- `https://5.161.235.99/` con `Host: crm.lovbot.ai` → HTTP 200 (CRM v2)
- `https://5.161.235.99/dev/crm-v2.html` → HTTP 200
- `https://5.161.235.99/dev/js/panel-loteos.js` → HTTP 200
- `https://5.161.235.99/health` → HTTP 200
- Title del HTML: `CRM — Powered by LovBot IA` (correcto)

**Monitor**: 2 checks nuevos en `guardia_critica.py`:
- `robert_crm_modelo_internal` → `https://crm.lovbot.ai/dev/crm-v2.html`
- `robert_crm_js_panel_loteos` → `https://crm.lovbot.ai/dev/js/panel-loteos.js`

**Vercel**: `lovbot-demos.vercel.app/dev/crm-v2` intacto como fallback (NO tocar vercel.json)

**Nota técnica**: Coolify beta.442 no acepta `dockerfile_location` via API — el Dockerfile debe llamarse `Dockerfile` (nombre estándar) en el `base_directory`. Por eso el archivo físico es `dev/Dockerfile` y `dev/Dockerfile.crm` queda solo como referencia/doc.

---

## [2026-04-22] deploy | Admin Robert migrado a Coolify Hetzner

**Razón**: cuota Vercel Hobby cerca del límite. Admin es uso interno — no necesita CDN global.

**App Coolify creada**:
- Nombre: `lovbot-admin-internal`
- UUID: `v0k8480sw800o00og0oo04g8`
- Project: `Agentes` (`ck0kccsws4occ88488kw0g80`) / Env: `production`
- Repo: `Arnaldo999/system-ia-agentes` / branch `main`
- base_directory: `/01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/admin`
- Dockerfile: `dev/admin/Dockerfile` (nginx:alpine)
- FQDN: `https://admin.lovbot.ai`

**DNS pendiente (Arnaldo debe hacer manualmente)**:
- Proveedor DNS de `lovbot.ai`: cambiar A record `admin` → `5.161.235.99`
- TTL recomendado: 300 (5 min para propagación rápida)
- Hasta que el DNS propague: Vercel sigue respondiendo en `admin.lovbot.ai` (fallback OK)

**Deploy status**: running:healthy (2026-04-23 01:03:40 UTC) — commit d969e90

**Historial de fixes en el Dockerfile**:
- `3ab0ce0` — Dockerfile inicial con printf (healthcheck via HEALTHCHECK NONE)
- `bb412f4` — HEALTHCHECK NONE (fallido: Coolify no puede leer State.Health sin esa key)
- `9640318` — wget healthcheck (fallido: Connection refused — nginx no arrancaba porque printf malformaba nginx.conf)
- `6403c32` — nginx.conf como archivo separado + wget --spider (fallido: Connection refused aún)
- `d969e90` — wget con 127.0.0.1 -O /dev/null + start-period 15s (EXITOSO — running:healthy)

**Causa raíz del problema de healthcheck**: el `printf` en el Dockerfile generaba nginx.conf mal formateado (los `\n` no se interpretaban correctamente), nginx no arrancaba → Connection refused en el healthcheck.

**Vercel**: `lovbot-demos.vercel.app/dev/admin/*` intacto como fallback (NO tocar vercel.json)

**Monitor**: 2 checks nuevos en `guardia_critica.py`:
- `robert_admin_clientes_internal` → `https://admin.lovbot.ai/clientes.html`
- `robert_admin_agencia_internal` → `https://admin.lovbot.ai/agencia.html`

---

## [2026-04-22] feature | CRM Agencia Lovbot — mockup HTML inicial deployado

**Commit**: `b56e4e4` — feat(crm-agencia-lovbot): HTML inicial mockeado + reorganizacion admin

**Cambios**:
- `demos/INMOBILIARIA/dev/admin.html` → movido a `demos/INMOBILIARIA/dev/admin/clientes.html` (git mv)
- `demos/SYSTEM-IA/admin.html` → movido a `demos/SYSTEM-IA/admin/clientes.html` (git mv)
- NUEVO: `demos/INMOBILIARIA/dev/admin/agencia.html` — CRM agencia mockup (5 leads mock, filtros, embudo)
- `vercel.json` actualizado: rutas `/dev/admin/clientes`, `/dev/admin/agencia`, `/system-ia/admin/clientes` + retro-compat
- Sidebar en ambos `clientes.html` con nav de Secciones (Robert: clientes activo + agencia; Mica: solo clientes)
- Paleta: Robert purple `#6c63ff` (active sidebar), Mica ambar `#f59e0b` (active sidebar)

**Pendiente Fase 2**:
- BD `lovbot_agencia_crm` en Hetzner Postgres
- Endpoints `agentes.lovbot.ai/agencia/leads`
- Conectar frontend al backend real

---

## 2026-04-22 — Migración CRM v2 definitiva Robert (Lovbot.ai)

**Decisión**: Robert (dueño Lovbot.ai) y Arnaldo (socio técnico) decidieron el 22/04/2026 que `dev/crm-v2.html` reemplaza definitivamente al CRM v1 (`dev/crm.html`) y al legacy MVP (`demo-crm-mvp.html`). El v2 estaba validado en producción.

**Archivos eliminados**:
- `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/demo-crm-mvp.html` (legacy v0)
- `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/crm.html` (legacy v1)

**Cambios en vercel.json**:
- Eliminada regla `/dev/crm` con host `crm.lovbot.ai` → apuntaba a `crm.html` (v1)
- Catch-all `crm.lovbot.ai` cambiado de `demo-crm-mvp.html` a `dev/crm-v2.html`
- Eliminadas rutas globales sin host: `/crm` (legacy MVP) y `/dev/crm` (legacy v1)
- Conservado `/dev/crm-v2` (con y sin host), `/dev/admin`, `/dev/js/:file`, `/js/:file`

**Validación post-deploy (Vercel desplegó commit 83d24c8)**:
- `https://crm.lovbot.ai/dev/crm-v2` → HTTP 200
- `https://crm.lovbot.ai/` (catch-all) → HTTP 200, sirve v2 (`panel-loteos`, `panel-contratos` confirmados via curl)
- `https://crm.lovbot.ai/dev/crm` (legacy) → HTTP 200 via catch-all, sirve v2
- `https://crm.lovbot.ai/dev/admin` → HTTP 200

**Commit**: `83d24c8` — `feat(robert/crm): migración v2 definitiva — eliminar v1 y legacy MVP`

**Modelo único Robert a partir de hoy**: `dev/crm-v2.html` en `https://crm.lovbot.ai/dev/crm-v2`



## 2026-04-22 — Migración CRM v2 definitiva Mica (System IA)

**Decisión**: Arnaldo y Mica decidieron el 22/04/2026 que `dev/crm-v2.html` reemplaza definitivamente al CRM v1 (`dev/crm.html`) y al legacy raiz (`crm.html`). El v2 estaba validado en `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo`. Mismo patron aplicado antes a Robert (commit `83d24c8`).

**Archivos eliminados**:
- `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/crm.html` (legacy v0 raiz)
- `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/crm.html` (legacy v1)

**Cambios en vercel.json**:
- `/system-ia/dev/crm` → antes apuntaba a `dev/crm.html`, ahora apunta a `dev/crm-v2.html` (alias, no rompe links viejos)
- `/system-ia/crm` → antes apuntaba a `crm.html` (raiz), ahora apunta a `dev/crm-v2.html` (alias)
- Conservadas: `/system-ia/dev/crm-v2`, `/system-ia/admin`, `/system-ia/dev/js/:file`

**Archivos de soporte actualizados**:
- `.claude/commands/sync-crm-prod.md` — mapeo Mica corregido: modelo unico, no hay prod separado
- `.claude/commands/rollback-crm-prod.md` — mapeo Mica corregido
- `.claude/agents/proyecto-mica.md` — regla de demo actualizada al v2
- `.claude/settings.json` — eliminadas reglas deny de crm.html (ya no existe)

**Validacion post-deploy (Vercel deploya commit `a674c3d`)**:
- `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2` → HTTP 200
- `https://system-ia-agencia.vercel.app/system-ia/dev/crm` (alias v1) → HTTP 200, sirve v2 (2 matches grep `crm-v2|panel-loteos`)
- `https://system-ia-agencia.vercel.app/system-ia/crm` (alias raiz) → HTTP 200, sirve v2 (2 matches grep)
- `https://system-ia-agencia.vercel.app/system-ia/admin` → HTTP 200

**Commit**: `a674c3d` — `feat(mica/crm): migracion v2 definitiva — eliminar v1 (dev/crm.html) y legacy raiz (crm.html)`

**Modelo unico Mica a partir de hoy**: `dev/crm-v2.html` en `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo`

**Pendiente (monitor guardia_critica.py)**: Los checks de Mica estan DESHABILITADOS hoy. Cuando Mica tenga dominio prod definitivo (no `vercel.app`), setear `MICA_CRM_URL` y `MICA_CRM_ENABLED=1` en Coolify.

---

## 2026-04-22 — Bug histórico de tokens: por qué pedíamos credenciales una y otra vez

**Síntoma**: Arnaldo mostró captura de Coolify con 4 tokens emitidos (`worker-arnaldo`, dos `agentes`, `flujos agenticos`). Cada subagente le pedía un token Coolify "porque no funcionaba", aunque ya había 1 guardado en `.env`.

**Causa raíz (3 capas)**:
1. **Quoting**: `COOLIFY_TOKEN='3|9jSOO...'` con comillas SIMPLES en `.env` raíz. `bash source .env` rompe en el `|` (lo lee como pipe) → "orden no encontrada" → token nunca se cargaba en variables de entorno → API auth devolvía 401.
2. **Lookup incompleto**: subagentes buscaban `COOLIFY_TOKEN` solo en `.env` del backend monorepo (donde NO estaba — solo `COOLIFY_ROBERT_TOKEN`). El de Arnaldo vivía solo en `.env` raíz Mission Control.
3. **Síntoma engaño**: 401 lo interpretaban como "token inválido/expirado" y pedían uno nuevo. La verdad era "token correcto, mal cargado".

**Fix definitivo**:
- Cambiar TODOS los tokens con `|` a comillas DOBLES: `COOLIFY_TOKEN="3|9jSOO..."`. Aplicado a `.env` raíz y `.env` backend (también el `COOLIFY_ROBERT_TOKEN`).
- Agregado `COOLIFY_TOKEN` (Arnaldo) al `.env` del backend monorepo, no solo al raíz, para que `guardia_critica.py` lo encuentre directo.
- Memoria persistente nueva: `feedback_REGLA_env_quoting_y_lookup.md` — antes de pedir token Coolify, agotar lookup en ambos `.env` y validar con curl.

**Validación**: `curl Bearer $COOLIFY_TOKEN /api/v1/applications` → HTTP 200 con app `system-ia-agentes` running:healthy.

**Acción pendiente para Arnaldo**: revocar manualmente desde panel Coolify los 3 tokens viejos no usados (dejar solo el `agentes` que figura como "Last used: 4 hours ago").

## 2026-04-22 — Hallazgo: la Guardia Crítica YA estaba programada hace 11 días, solo le faltaban env vars

**Descubierto al integrar guardia_critica.py**: la Scheduled Task "Guardia Crítica" (`*/5 * * * *  cd /app/scripts && python guardia_critica.py`) ya existía en Coolify desde 2026-04-11 (UUID `fo5l5or8bbz3bl8d0n47dj9a`). Llevaba 11 días corriendo sin alertar — no porque todo estuviera bien, sino porque le faltaban las env vars `COOLIFY_API_URL`, `COOLIFY_APP_UUID`, `FASTAPI_URL`, `N8N_URL` y el script crasheaba antes de poder mandar Telegram.

**Fix**: Agregadas las 4 env vars vía API Coolify (`POST /api/v1/applications/<uuid>/envs`). Disparado deploy `ph3xsqna8ag7vowvmsgzwjht` para que el container las recoja. Eliminada la Scheduled Task duplicada que mi subagente había creado.

**Lección**: antes de "crear" un cron en Coolify, listar `GET /scheduled-tasks` y verificar si ya existe.

## 2026-04-22 — CRM Maicol caído por CORS + monitor Capa 1 instalado

**Síntoma**: `crm.backurbanizaciones.com` mostraba "Failed to fetch" y "Cargando leads…" infinito. Maicol avisó.

**Causa**: El `CORSMiddleware` del backend FastAPI Arnaldo (`agentes.arnaldoayalaestratega.cloud`) no tenía `https://crm.backurbanizaciones.com` en `allow_origins`. Preflight OPTIONS rechazado sin header `Access-Control-Allow-Origin`.

**Fix**: Agregado el origen al `CORSMiddleware` en `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`. Commit `a681a5c`. Validado con preflight OPTIONS → `200` + header correcto.

**Lección y acción permanente — Monitor Capa 1 (guardia_critica.py)**:
- Script definitivo: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/scripts/guardia_critica.py`
- 9 checks: FastAPI Arnaldo, n8n Arnaldo, n8n Mica, n8n Lovbot, Coolify app, Maicol CRM CORS preflight, Maicol CRM frontend, Chatwoot Arnaldo, Backend Robert (ping externo)
- Envío CONSOLIDADO: 1 solo Telegram con todos los fallos juntos (no un mensaje por servicio)
- Cooldown 30 min por servicio (no spamea)
- Kill switch: env var `GUARDIA_DISABLED=1`
- Deploy: Coolify Hostinger → Scheduled Tasks `*/5 * * * *  python scripts/guardia_critica.py`
- Vars de entorno a configurar en Coolify (ver sección abajo)
- Commit: `[ver commit guardia_critica refactor]`

### Env vars a configurar en Coolify (app FastAPI Arnaldo — Hostinger)

Ir a `coolify.arnaldoayalaestratega.cloud` → app `system-ia-agentes` → Environment Variables → agregar:

```
TELEGRAM_BOT_TOKEN=<token del bot>
TELEGRAM_CHAT_ID=863363759
COOLIFY_API_URL=https://coolify.arnaldoayalaestratega.cloud
COOLIFY_TOKEN=<token API Coolify Arnaldo>
COOLIFY_APP_UUID=ygjvl9byac1x99laqj4ky1b5
FASTAPI_URL=https://agentes.arnaldoayalaestratega.cloud
N8N_URL=https://n8n.arnaldoayalaestratega.cloud
```

Luego en Coolify → Scheduled Tasks → agregar:
- Schedule: `*/5 * * * *`
- Command: `python scripts/guardia_critica.py`

Para deshabilitar temporalmente sin tocar el cron: agregar env var `GUARDIA_DISABLED=1`.

### Resultado del run local (2026-04-22)

Con COOLIFY_TOKEN correcto, los 9 checks pasan. Con token bogus y N8N_URL bogus, se mandó correctamente 1 Telegram consolidado con 2 alertas juntas — formato correcto.

## 2026-04-22 — Refinamiento checks Robert en guardia_critica.py (chat con Robert)

**Motivo**: Arnaldo habló con Robert y confirmó el esquema real del CRM Lovbot. La URL que se monitoreaba (`crm.lovbot.ai/` raíz) no era la que importaba — el modelo real del CRM vive en `/dev/crm-v2`.

**Esquema confirmado por Robert**:
- `https://crm.lovbot.ai/?tenant=robert` → YA NO EXISTE (URL legacy, descartada).
- `https://crm.lovbot.ai/dev/crm-v2` → CRM modelo real (template del que se replica para cada cliente futuro).
- `https://lovbot-demos.vercel.app/dev/admin` → Panel de Gestión (admin para crear/configurar tenants). Crítico.
- `https://crm.lovbot.ai/` (raíz) → sigue siendo 200 (sirve HTML), vale como check de disponibilidad de dominio.
- `https://admin.lovbot.ai/` → sin cambios.
- `https://agentes.lovbot.ai/health` → sin cambios.

**Cambios aplicados en `scripts/guardia_critica.py`**:
- `check_robert_crm_frontend` → renombrado a `check_robert_crm_modelo`, apunta a `/dev/crm-v2`.
- Nuevo `check_robert_crm_dominio` → GET `crm.lovbot.ai/` (raíz, 200 = dominio responde).
- Nuevo `check_robert_panel_gestion` → GET `lovbot-demos.vercel.app/dev/admin` (200).
- `check_robert_crm_cors` → sin cambios (preflight con Origin `crm.lovbot.ai` sigue siendo correcto).
- `check_robert_admin` → sin cambios.
- Vars env: `ROBERT_CRM_URL` → `ROBERT_CRM_MODELO_URL` + nuevas `ROBERT_CRM_DOMINIO_URL` y `ROBERT_PANEL_GESTION_URL`.

**Resultado run local post-cambio**: 14 checks activos OK, 2 Mica deshabilitados (skip). Todo verde.

**TODOs futuros**:
- Cuando se replique el modelo para clientes reales de Lovbot (ej: subdominios o tenant-paths), agregar checks por cliente.
- Cuando Arnaldo y Robert armen el "CRM agencia" (hablado el 22/04), sumar check a la guardia.
- Nuevas env vars a agregar en Coolify Hostinger si se quieren cambiar las URLs por defecto:
  - `ROBERT_CRM_MODELO_URL` (default: `https://crm.lovbot.ai/dev/crm-v2`)
  - `ROBERT_CRM_DOMINIO_URL` (default: `https://crm.lovbot.ai`)
  - `ROBERT_PANEL_GESTION_URL` (default: `https://lovbot-demos.vercel.app/dev/admin`)

## 2026-04-22 — Guardia Crítica ampliada: checks Robert CRM/admin + Mica preparado

**Cambio**: se sumaron 5 checks nuevos a `guardia_critica.py` (total 14 en el dict, 12 activos + 2 deshabilitados).

**3 checks Robert (LIVE, habilitados)**:
- `robert_crm` → GET `https://crm.lovbot.ai/` → espera 200. Agnóstico a v1/v2 (el dominio no cambia con sync-crm-prod).
- `robert_crm_cors` → OPTIONS `https://agentes.lovbot.ai/health` con `Origin: https://crm.lovbot.ai`. Valida 200/204 + ACAO correcto.
- `robert_admin` → GET `https://admin.lovbot.ai/` → 200.

**2 checks Mica (deshabilitados — `enabled=False` via env var)**:
- `mica_crm` → GET `$MICA_CRM_URL` (default: `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2`).
- `mica_crm_cors` → preflight al backend Arnaldo con `Origin: $MICA_CRM_URL`.

**Patrón de deshabilitar**: las funciones retornan `None` si `MICA_CRM_ENABLED != "1"`. El loop de `main()` hace `continue` en `None` y loggea `deshabilitado (skip)`.

**Cómo activar Mica cuando entre a prod**:
1. Definir dominio prod con Arnaldo (ej: `crm.systemia.com`).
2. En Coolify → app `system-ia-agentes` → env vars: `MICA_CRM_URL=https://crm.systemia.com` y `MICA_CRM_ENABLED=1`.
3. Redeploy automático. Próximo ciclo cron ya los corre.

**Run local confirmado (2026-04-22)**:
```
[guardia] OK  FastAPI Arnaldo: healthy, workers=6
[guardia] OK  n8n Arnaldo: ok
[guardia] OK  n8n Mica: ok
[guardia] OK  n8n Lovbot: ok
[guardia] OK  Coolify app: status=running:healthy
[guardia] OK  Maicol CRM — preflight CORS: CORS ok (ACAO=https://crm.backurbanizaciones.com)
[guardia] OK  Maicol CRM — frontend: HTTP 200
[guardia] OK  Chatwoot Arnaldo: HTTP 200
[guardia] OK  Backend Robert (ping externo): HTTP 200
[guardia] OK  Robert CRM frontend: HTTP 200
[guardia] OK  Robert CRM CORS: CORS ok (ACAO=https://crm.lovbot.ai)
[guardia] OK  Robert admin: HTTP 200
[guardia] --- Mica CRM frontend: deshabilitado (skip)
[guardia] --- Mica CRM CORS: deshabilitado (skip)
[guardia] Todo OK — sin alertas a enviar
```


## n8n HTTP Request — JSON inválido
- Causa: JSON body pegado como literal o con prefijo incorrecto (por ejemplo "=={{").
- Solucion: usar modo Expression y un prefijo unico "={{...}}".

## Render — "failed to read dockerfile: open Dockerfile: no such file or directory"
- Causa: Render busca el Dockerfile en la raíz del repo, pero el proyecto es un monorepo y el Dockerfile está en un subdirectorio.
- Solución: Configurar `rootDir` en Render vía API o Dashboard → Settings → Build.
  ```bash
  curl -X PATCH "https://api.render.com/v1/services/<SERVICE_ID>" \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"rootDir": "ruta/al/subdirectorio"}'
  ```
- Service ID Maicol: `srv-d6g8qg5m5p6s73a00llg`
- rootDir correcto: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`

## Render — Bot muestra versión vieja del código
- Causa: Render despliega branch `main` pero los commits iban a `master`.
- Solución: `git push origin master:main --force` para sincronizar branches.

## Dockerfile — wget falla en Render free tier
- Causa: `wget` de archivos de fuentes desde GitHub agota timeout en Render free.
- Solución: Eliminar descarga de fuentes Inter; usar solo `fonts-dejavu-core` desde apt (ya incluido en `python:3.11-slim`).

## import time mal ubicado en Python
- Causa: `import time` puesto dentro de un bloque de código (dentro de una función o sección) en lugar del top-level.
- Solución: Todos los imports al inicio del archivo, antes de cualquier código.

## 2026-04-22 — CORS bloqueaba CRM Maicol (Back Urbanizaciones)

### Bug: CRM crm.backurbanizaciones.com no podía hacer fetch al backend
**Síntoma**: Todos los endpoints `/clientes/arnaldo/maicol/crm/*` devolvían error CORS en consola Chrome. UI mostraba "Failed to fetch" / "Cargando leads..." infinito / funnels en 0.
**Causa raíz**: `main.py` CORSMiddleware tenía en `allow_origins` solo orígenes Lovbot (`crm.lovbot.ai`, `lovbot-demos.vercel.app`, `admin.lovbot.ai`) + localhost. El origen `https://crm.backurbanizaciones.com` NUNCA fue agregado — omisión histórica desde que se configuró CORS (commit `b39264c`).
**Fix**: agregar `"https://crm.backurbanizaciones.com"` como primer elemento de `allow_origins` en `main.py`, con comentario de sección para Arnaldo/Maicol.
**Commit**: `a681a5c` — push `master:main` — Coolify Hostinger autodeploy.
**Validación post-deploy**: esperar redeploy y confirmar preflight OPTIONS con `Access-Control-Allow-Origin: https://crm.backurbanizaciones.com`.
**Nota**: el backend estaba VIVO (respondía 405 al GET — correcto para rutas POST). El problema era 100% CORS, no caída del servidor.

## 2026-04-22 — Sesión CRM v3 Robert — bugs notables fixeados

### Bug: `tenant_slug specified more than once` al POST de GESTIÓN
**Síntoma**: HTTP 422 al crear propietario/inmueble/inquilino/pago/liquidación.
**Causa raíz**: `db_postgres.py _crud_generico()` hacía `cols = ["tenant_slug"] + list(campos.keys())` donde `campos` venía del body request y YA traía `tenant_slug` → tabla dobla la columna.
**Fix**: filtrar del dict antes: `campos_clean = {k:v for k,v in campos.items() if k != "tenant_slug"}`.
**Commit**: `d26d634` — aplicado a todos los endpoints que usan _crud_generico.

### Bug: UNIQUE constraint lotes_mapa bloqueaba A-1 + B-1 coexistir
**Síntoma**: crear B-777 devolvía 409 "Ya existe un lote con ese numero en esa manzana" aunque la constraint debería permitirlo (distinta manzana).
**Causa raíz**: había DOS constraints UNIQUE simultáneos:
- `lotes_mapa_tenant_slug_loteo_id_numero_lote_key` (auto-generado Postgres, sin manzana) — el culpable
- `uq_lotes_mapa_tenant_loteo_manzana_nro` (correcto, con manzana)
**Fix**: `fix-lotes-constraint-v2` — dropea TODOS los UNIQUE sin manzana **por definición** (no por nombre). El primer intento fallaba porque buscaba por nombre específico.
**Commits**: `0fa97c6` (endpoint) + `ba5c42d` (excluir PK del check).

### Bug: lote vendido no mostraba cliente asignado
**Síntoma**: click en A-01 (vendido) mostraba "LOTEO Palo Alto" pero no los datos del cliente que lo compró.
**Causa raíz**: triple bug concatenado.
1. `panel-loteos.js` cargaba `/crm/clientes` (leads) en vez de `/crm/activos` (clientes firmados). `cliente_id` del lote apunta a `clientes_activos`.
2. Backend devuelve IDs con prefijo `"pg_16"`, lote guarda `cliente_id=16` (int). `find(c => c.id === cliente_id)` siempre falso.
3. Backend devuelve campos capitalizados (`Nombre`, `Telefono`, `Propiedad`) pero código leía `c.nombre`, `c.telefono`.
**Fix**: 
- Cambiar endpoint en 3 puntos de `panel-loteos.js` a `/crm/activos`.
- Agregar helper `clienteMatches(c, id)` que normaliza quitando prefijo `pg_`.
- Fallback `c.Nombre || c.nombre` en todos los accesos.
**Commit**: `d5002d6`.

### Bug: CORS bloqueando fetch de frontend
**Síntoma**: consola con "has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header".
**Causa raíz**: `main.py` tenía `allow_origin_regex=r"https?://.*"` con `allow_credentials=True`. Spec CORS prohíbe esa combinación — browsers rechazan.
**Fix**: whitelist explícita de orígenes (`crm.lovbot.ai`, `lovbot-demos.vercel.app`, `*.vercel.app` regex, localhost puertos 8765/8766). Credentials=true compatible con orígenes concretos.
**Commit**: `b39264c`.

### Bug: HTTP 410 masivo en consola
**Síntoma**: 10+ errores `Failed to load resource: 410` al cargar CRM.
**Causa raíz**: columna `propiedades.imagen_url` tenía URLs firmadas `airtableusercontent.com` expiradas hace 10 días. Eran data de seed migrada desde Airtable al Postgres (Robert NO usa Airtable — eran strings legacy en DB).
**Fix**: 
- Backend: `UPDATE propiedades SET imagen_url = NULL WHERE imagen_url LIKE '%airtableusercontent%'`.
- Frontend: helper `getPropertyImage(p)` que ignora URLs de Airtable y devuelve placeholder 🏠.
**Commits**: `9b7eb4f` (backend) + `8fb0d73` (frontend).

### Bug: sidebar GESTIÓN ocultaba grupos por subnicho
**Síntoma**: tenant demo (desarrolladora) NO veía el grupo "AGENCIA" del sidebar.
**Causa raíz**: `groupConfig.desarrolladora.show = ['desarrolladora', 'mixto']` — el grupo agencia no figuraba en la lista, se seteaba `data-hidden="true"`.
**Fix**: todos los subnichos muestran TODOS los grupos. `show: ALL_GROUPS`. El subnicho solo decide cuál abre por default. UI más flexible para el usuario.
**Commit**: `b0d9a5c`.

### Bug: Vercel deploy cupo 100/día agotado
**Síntoma**: git push a main no se reflejaba en `crm.lovbot.ai`. Dashboard Vercel mostraba "Resource is limited - try again in 24 hours".
**Causa raíz**: Plan Hobby tiene límite 100 deploys/día. Hicimos 20+ commits y el límite se activó.
**Mitigación**: esperar reset (medianoche UTC). Redeploy del último commit (gratis, no cuenta). O upgrade a Pro ($20/mes, 6000/día).
**No requiere fix en código** — limitación de plan.

## 2026-04-22 — Sesión CRM v3 Mica — bugs/decisiones notables

### Decisión: polimorfismo Airtable con 3 linkedRecord
Airtable NO tiene FK polimórfica como Postgres. En vez de `item_tipo + item_id`, tabla Contratos Mica tiene 3 campos `linkedRecord` separados (Lote_Asignado, Propiedad_Asignada, Inmueble_Asignado). Solo UNO se setea por contrato. Adapter serializa a misma forma JSON que Robert para que el frontend sea portable.

### Bug: record_id int vs string en endpoints CRUD
**Síntoma**: crear/borrar propietarios/inmuebles/inquilinos devolvía 422 en Mica.
**Causa raíz**: los handlers del worker Mica estaban declarados con `record_id: int` (copiados de Robert) pero Airtable usa IDs tipo `rec12345abc...` (strings).
**Fix**: reemplazar `record_id: int` → `record_id: str` en todos los endpoints CRM del worker Mica.
**Commit**: `a616f70`.

### Decisión: Contratos.Tipo limitado a venta/reserva/alquiler/boleto en Airtable
**Síntoma**: el backend Robert usa `venta_lote/venta_casa/venta_terreno/venta_unidad` como valores válidos del campo Tipo. Mica no.
**Causa raíz**: el campo singleSelect en Airtable fue creado con opciones `venta/reserva/alquiler/boleto` de antes del refactor. Modificar las opciones vía Metadata API requiere PATCH del campo completo (destructivo si no se cuida).
**Decisión**: backend Mica mapea los subtipos granulares a `venta` en Airtable + guarda el subtipo en `Item_Descripcion` (texto libre). Si se quieren granulares explícitos en Airtable a futuro, requiere autorización del usuario.

### Decisión: sin transacciones — log warnings
**Síntoma**: operaciones multi-paso (crear cliente + contrato + update item) no son atómicas en Airtable.
**Fix**: el handler hace los pasos secuencialmente. Si uno falla, loguea WARNING y devuelve el estado parcial. El frontend puede reintentar. NO deshacer pasos exitosos anteriores (no hay ROLLBACK).

### Decisión: campo Origen_Creacion removido de Contratos
**Síntoma**: error 422 al crear contrato porque Airtable no tenía el campo `Origen_Creacion` en la tabla Contratos (sí lo tiene CLIENTES_ACTIVOS pero no Contratos).
**Fix**: el backend Mica quita ese campo del payload antes de enviar a Airtable. El origen se guarda solo en CLIENTES_ACTIVOS al crear el cliente.
**Commit**: `a9dc86a`.
