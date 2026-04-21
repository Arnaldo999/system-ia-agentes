---
title: "Meta Tech Provider — Onboarding, Embedded Signup y Coexistence"
tags: [meta, tech-provider, embedded-signup, coexistence, waba, robert, documentacion-oficial]
source_count: 1
proyectos_aplicables: [robert]
---

# Meta Tech Provider — Onboarding, Embedded Signup y Coexistence

## Definición

Conjunto de mecanismos oficiales de Meta para que una agencia/SaaS (como [[lovbot-ai]]) pueda:

1. **Actuar como Tech Provider verificado** — gestionar activos WhatsApp Business (WABAs, números, templates) de múltiples clientes finales.
2. **Onboardear clientes vía Embedded Signup** — que otra empresa conecte su WhatsApp Business dentro del propio SaaS en minutos, sin pedir accesos manuales.
3. **Permitir Coexistence** — que el cliente siga usando la app WhatsApp Business en su celular mientras el bot automatiza desde el Cloud API.

Esto es el modelo que usa [[robert-bazan]] con su app `APP WorkFlow Whats Lovbot V2` (ID `704986485248523`).

## Quién lo usa

- ✅ **[[robert-bazan]] / [[lovbot-ai]]** — Tech Provider verificado con [[meta-graph-api]]. App en revisión desde 2026-04-19 para obtener advanced access de `whatsapp_business_management` + `whatsapp_business_messaging`.
- ❌ [[arnaldo-ayala]] → usa [[ycloud]], no es Tech Provider.
- ❌ [[micaela-colmenares]] → usa [[evolution-api]] self-hosted.

## Modelo "Tech Provider SaaS" vs "Tech Provider Agencia"

Kevin Belier (mentor Arnaldo) distingue en su curso "Cómo convertirte en Tech Provider SaaS" 2 modelos diferentes ante Meta:

| Dimensión | Modelo SaaS | Modelo Agencia |
|---|---|---|
| Responsabilidad de datos | **TÚ sos responsable** (almacenás conversaciones, leads, etc.) | Cliente maneja sus propios datos |
| Escalabilidad | Miles de clientes en 1 infra | 1-dashboard no escala a múltiples |
| Restricciones Meta | **MÁS restricciones** (Data Handling form estricto, Access Verification obligatoria) | Menos responsabilidad técnica |
| Caso de uso | Plataforma multi-tenant que vende "WhatsApp como servicio" | Consultora que implementa 1-a-1 con infra del cliente |

**Importante para Lovbot**: Robert **está operando modelo SaaS** aunque lo venda como "agencia":
- Multi-tenant en 1 backend (`agentes.lovbot.ai` + PG `robert_crm`)
- Almacena datos de clientes finales (conversaciones, leads)
- Responsable del uptime + compliance
- Columna `agencia_origen` permite operar como **SaaS compartido entre agencias** del ecosistema Arnaldo (decisión 2026-04-20).

Esto significa que las lecciones de Kevin del curso SaaS **aplican al 100%** a Lovbot, no solo en teoría.

## Los 4 pilares técnicos

### 1. App en Meta for Developers
- Tipo: **Negocios**
- Debe pasar **Business Verification** del Business Portfolio dueño de la app.
- Requiere **Access Verification** para que Meta te reconozca como Tech Provider (proceso ~5 días, revisión de políticas de uso de datos).

### 2. Permisos necesarios (App Review obligatoria)
| Permiso | Uso | Estado típico |
|---|---|---|
| `public_profile` | Leer datos básicos del user que conecta vía Facebook Login | Advanced automático (Meta lo otorga solo) |
| `whatsapp_business_management` | Gestionar WABAs, suscribir webhooks, crear templates, consultar phone_numbers | Requiere app review con video + justificación |
| `whatsapp_business_messaging` | POST a `/{phone_number_id}/messages` para enviar mensajes | Requiere app review con video + justificación |

### 3. Embedded Signup
Flujo OAuth embebido en tu SaaS (popup Meta). Al completar:
- Devuelve un `code` que tu backend intercambia por `access_token` permanente.
- Tu backend suscribe el WABA del cliente a tu app (POST `/{waba_id}/subscribed_apps`).
- A partir de ahí recibís webhooks de mensajes de ese cliente.

En Lovbot: `lovbot-onboarding.vercel.app/?client=slug-del-cliente` → exchange en `agentes.lovbot.ai` → persistencia en [[postgresql]] `robert_crm`.

### 4. Coexistence
El cliente NO pierde la app WhatsApp Business de su celular. Puede seguir respondiendo manual mientras el bot opera en paralelo via Cloud API. Es el método **recomendado por Meta**, no un hack.

## Documentación oficial (URLs verificadas 2026-04-20)

### Embedded Signup
- **Raíz Embedded Signup** → https://developers.facebook.com/docs/whatsapp/embedded-signup/ (última act. 25 nov 2025)
- **Overview** → https://developers.facebook.com/docs/whatsapp/embedded-signup/overview/ (última act. 25 nov 2025)
- **Implementation v4** → https://developers.facebook.com/docs/whatsapp/embedded-signup/implementation/ (última act. 25 mar 2026)
- **Coexistence (onboarding business app users)** → https://developers.facebook.com/docs/whatsapp/embedded-signup/custom-flows/onboarding-business-app-users/ (última act. 3 abr 2026)
- **Postman collection oficial** → https://www.postman.com/meta/whatsapp-business-platform/collection/du6gzjv/embedded-signup

### Facebook Login for Business (OAuth que habilita Embedded Signup)
- **Facebook Login for Business (canónica)** → https://developers.facebook.com/docs/facebook-login/facebook-login-for-business (última act. 25 mar 2026)
  - ⚠️ Kevin linkea la legacy `/docs/facebook-login/business/` que **devuelve 404** desde 2025. Usar la canónica.
- **Security — redirect URIs, HTTPS, appsecret_proof** → https://developers.facebook.com/docs/facebook-login/security/ (última act. 16 oct 2024, sin updates recientes pero vigente)

### Tech Provider
- **Tech Providers — qué es + permisos restringidos** → https://developers.facebook.com/docs/development/release/tech-providers/
- **Access Verification — proceso ~5 días** → https://developers.facebook.com/docs/development/release/access-verification/

### Permisos WhatsApp
- **Permissions Reference (índice único)** → https://developers.facebook.com/docs/permissions/
  - ⚠️ Meta **ya no mantiene páginas individuales por permiso**. `whatsapp_business_management` y `whatsapp_business_messaging` viven dentro de este índice alfabético.

### Migración de número existente
- **Migrar número WABA a Cloud API** → https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/migrate-existing-whatsapp-number-to-a-business-account/ (última act. 31 oct 2025)

## Frontend Embedded Signup — código JS

Patrón completo (verificado en `lovbot-onboarding.vercel.app`, post-fix Coexistence 2026-04-20):

```html
<script async defer crossorigin="anonymous"
  src="https://connect.facebook.net/es_LA/sdk.js"></script>

<meta name="meta-app-id"     content="704986485248523">
<meta name="meta-config-id"  content="1264527552112117">

<script>
  const META_APP_ID = document.querySelector('meta[name="meta-app-id"]').content;
  const CONFIG_ID   = document.querySelector('meta[name="meta-config-id"]').content;

  // Identificar al cliente desde URL: /?client=NombreCliente
  const urlParams  = new URLSearchParams(window.location.search);
  const clientName = urlParams.get('client') || 'sin-nombre';
  const clientSlug = clientName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  window.fbAsyncInit = function() {
    FB.init({ appId: META_APP_ID, autoLogAppEvents: true, xfbml: true, version: 'v24.0' });
  };

  // Listener mensajes Meta (waba_id + phone_number_id llegan acá)
  window.addEventListener('message', function(event) {
    if (event.origin !== 'https://www.facebook.com' && event.origin !== 'https://web.facebook.com') return;
    try {
      const data = JSON.parse(event.data);
      if (data.type !== 'WA_EMBEDDED_SIGNUP') return;
      if (data.event === 'FINISH') {
        // Capturar data.data.waba_id, data.data.phone_number_id, data.data.phone_number
        // y enviarlos al backend (junto con el code que llega en FB.login callback)
      }
    } catch (e) {}
  });

  function launchWhatsAppSignup() {
    FB.login(function(response) {
      if (response.authResponse?.code) {
        // Code OAuth listo — intercambiar server-side con APP_SECRET
      }
    }, {
      config_id: CONFIG_ID,
      response_type: 'code',
      override_default_response_type: true,
      extras: {
        setup: {},
        featureType: 'whatsapp_business_app_onboarding',  // 🔥 CLAVE para Coexistence
        sessionInfoVersion: '3'
      }
    });
  }
</script>

<button onclick="launchWhatsAppSignup()">Conectar mi WhatsApp</button>
```

### 🔥 Activar Coexistence (clave para Tech Providers)

Sin estos parámetros, el popup solo permite crear números NUEVOS en Cloud API. Con ellos, ofrece la pantalla *"Do you want to use an existing number from WhatsApp Business App?"* — permitiendo que el cliente mantenga su número actual.

**Parámetros obligatorios** (en `extras`):
- `setup: {}` — vacío, requerido por spec.
- `featureType: 'whatsapp_business_app_onboarding'` — ⚠️ NO es `feature`, es `featureType`. Trampa común.
- `sessionInfoVersion: '3'` — STRING `'3'`, no número 3. Otra trampa.

### ⚠️ Requisito del CONFIG_ID

El `config_id` debe haberse creado en:
```
Facebook Login → Settings → WhatsApp Embedded Signup
Tipo de onboarding: WhatsApp Business App  ← OBLIGATORIO
```

Si el `config_id` se creó para "Cloud API normal", Coexistence NO se activa aunque pongas `featureType` correcto.

### ⚠️ Patrón de race condition entre code y waba_id

El `code` OAuth llega via callback de `FB.login`. El `waba_id` + `phone_number_id` llegan via `window.message` en evento `FINISH`. **No hay garantía de orden**. Solución: guardar ambos en variables de scope superior y enviar cuando los 2 estén listos.

### ❌ Patrón Kevin con n8n + Header Auth — NO usar en Lovbot

Kevin propone enviar payload del frontend a 2 webhooks n8n separados con `x-tuempresa-secret` header. **Robert NO usa esto** porque:
- Tiene backend FastAPI propio (`agentes.lovbot.ai`) con `META_APP_SECRET` server-side.
- Un solo POST al endpoint `/clientes/lovbot/inmobiliaria/public/waba/onboarding` resuelve todo.
- El intercambio de `code` por `access_token` se hace en el server (más seguro que en n8n).
- Sin Header Auth porque el `code` solo es canjeable con APP_SECRET — no necesita auth extra.

## Configuración de Facebook Login para Embedded Signup

Panel: `developers.facebook.com/apps/{APP_ID}/fb-login/settings/`

**Toggles correctos** (según mentor Kevin, validado contra flujo real):

| Setting | Valor correcto | Por qué |
|---|---|---|
| Validador de URI de redireccionamiento | **Vacío** | Campo de prueba manual, no requerido |
| Acceso del cliente de OAuth | ✅ Sí | Habilita flujo OAuth estándar |
| Acceso de OAuth web | ✅ Sí | Embedded Signup ocurre en navegador |
| Aplicar HTTPS | ✅ Sí | Obligatorio para dominios reales |
| Forzar reautenticación OAuth web | ❌ No | Evita fricción innecesaria |
| Inicio sesión OAuth de navegador integrado | ✅ Sí | Permite contexto embebido |
| Modo estricto URI redireccionamiento | ❌ No | Embedded Signup maneja redirect internamente |

**Campos de texto críticos**:

- **URI de redireccionamiento de OAuth válidos**: URL HTTPS EXACTA donde vive el botón "Conectar WhatsApp".
  - Debe ser HTTPS, no localhost, no ngrok en prod.
  - Si no coincide → error de OAuth al cerrar el popup.
  - Lovbot: `https://lovbot-onboarding.vercel.app/` (verificar en panel).

- **Dominios admitidos para el SDK de JavaScript**: solo el dominio, sin paths, sin `https://`, sin slash final.
  - Lovbot (verificado 2026-04-20): `lovbot-onboarding.vercel.app`
  - Si falta → Meta bloquea la carga del SDK y el popup nunca abre.
  - ⚠️ Trampa: si ponés `https://dominio.com/` aquí Meta lo acepta pero algunos navegadores fallan al validar. Forma correcta = solo dominio.

**Campos opcionales que pueden quedar vacíos**:

- **Validador de URI de redireccionamiento** — herramienta manual de prueba, no requerida.
- **URL de devolución de llamada para autorización cancelada** (sección "Cancelar autorización") — solo útil si querés trackear cuando un user revoca acceso a tu app desde su Business Manager. No impacta el flujo inicial.
- **Inicio de sesión desde dispositivos** → `No` (es para Smart TVs, no aplica a SaaS web).

**Config verificada Lovbot (2026-04-20)**: redirect URI + domain SDK JS confirmados OK contra screenshot del panel Meta.

## Trampa Vercel — proyecto sin Git conectado

**Pasó 2026-04-20**: el proyecto Vercel `lovbot-onboarding` se creó originalmente con `vercel deploy` desde CLI, sin linkear a GitHub. Resultado: durante 3 días el código del repo quedó desfasado de producción porque `git push` NO disparaba auto-deploy.

**Síntomas**:
- Push a `master:main` exitoso pero la URL pública (`lovbot-onboarding.vercel.app`) sirve código viejo.
- `last-modified` header del HTML deployado coincide con la fecha del último `vercel deploy` manual (3+ días atrás).
- En Vercel UI: aparece botón "Connect Git" en Overview (significa que NO está conectado).
- Source dice `>_ vercel deploy` en vez de mostrar el branch Git.
- Existe un proyecto distinto (ej: `lovbot-demos`) que SÍ tiene Git conectado y deploya el mismo monorepo, pero a una URL diferente.

**Solución**:
1. Vercel UI → proyecto → Settings → Git → "Connect Git" → seleccionar repo + branch.
2. Settings → Build and Deployment → Root Directory: `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/onboarding-vercel`.
3. Trigger un commit dummy (cualquier cambio) → push → Vercel auto-deploya.

Desde ahí, todo `git push` con cambios al onboarding se refleja en prod automáticamente.

## Paquete App Review (checklist obligatorio)

Kevin (mentor de Arnaldo) sintetiza lo que Meta exige:

1. **Política de privacidad pública** — en Lovbot: `lovbot.mx/politica-de-privacidad`
2. **Términos de servicio** — `lovbot-legal.vercel.app/terminos-de-servicio`
3. **URL de eliminación de datos** — `lovbot-legal.vercel.app/eliminacion-datos`
4. **Ícono 1024×1024** — cargado
5. **Video 1** (envío de mensaje vía API) — demuestra uso de `whatsapp_business_messaging`
6. **Video 2** (creación de template) — demuestra uso de `whatsapp_business_management`
7. **Justificación textual por permiso** — explicar exactamente cómo se usa
8. **Instrucciones paso-a-paso para revisor** — URL de prueba + flujo esperado
9. **Email DPO** (solo si operás en EU — Robert NO)

Paquete completo de Robert: [[raw/robert/project-meta-app-review-completo]] (archivo fuente: `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/meta-app-review/PAQUETE-COMPLETO.md`).

## Secuencia correcta para un nuevo Tech Provider

1. Crear app tipo **Negocios** en Meta for Developers.
2. Asociar a un Business Portfolio verificado.
3. Completar **Access Verification** (5 días).
4. Activar **Facebook Login for Business** (automático si `public_profile` ya está en advanced).
5. Publicar páginas legales (privacidad, términos, eliminación de datos).
6. Implementar Embedded Signup frontend + backend (exchange + subscribed_apps).
7. Grabar 2 videos demo.
8. Enviar **App Review** para los 2 permisos WhatsApp.
9. Esperar 2-10 días hábiles.
10. Al aprobarse → app pasa a modo **Live** → clientes pueden onboardear.

## ⚠️ Trampas comunes

- **Modo Desarrollo bloquea Embedded Signup para usuarios externos** — solo funciona para roles de la app hasta que Meta apruebe los permisos avanzados.
- **`public_profile` a veces aparece en "Acceso existente para revisar"** cuando pedís App Review — es formalidad, Meta re-confirma todo el bundle.
- **Los dominios de las URLs legales NO tienen que coincidir** — pueden vivir en sitios distintos (Lovbot mezcla `lovbot.mx` + `lovbot-legal.vercel.app`), Meta solo valida que respondan 200.
- **`lovbot.mx` bloquea `curl` sin user-agent** con 403 "Malware detected" (WAF Hostinger). Meta y navegadores reales sí acceden. No es un problema para el review.
- **No existe PDF oficial de Coexistence** — Meta lo documenta solo como página HTML en el link `/embedded-signup/custom-flows/onboarding-business-app-users/`.

## 🚫 No aplicable a otros proyectos

- Arnaldo NO es Tech Provider → usa [[ycloud]] con plan pago, no necesita App Review de Meta.
- Mica NO es Tech Provider → usa [[evolution-api]] self-hosted, evita la burocracia Meta.
- Si alguna vez Arnaldo o Mica quieren Tech Provider propio → seguir este documento paso-a-paso.

## Modelo multi-agencia (Robert como TP compartido del ecosistema)

**Decisión estratégica 2026-04-20**: la app TP de Robert actúa como tránsito técnico para clientes de Arnaldo (y eventualmente Mica) hasta que cada agencia verifique su propio portfolio + saque su propio TP.

**Implementado en schema `waba_clients`**:
- `agencia_origen` TEXT DEFAULT 'lovbot' — categoriza cada tenant por agencia vendedora (`arnaldo` / `mica` / `lovbot`).
- `meta_user_id` TEXT — ID del user Meta que hizo el Embedded Signup. Crítico para match automático en webhook `/deauthorize`.

**Endpoints admin nuevos** (commit `ec33418`):
- `GET /webhook/meta/tenants-por-agencia?agencia=X` — dashboards filtrados (access_token siempre redactado)
- `POST /webhook/meta/reclasificar-agencia` — corregir tenants con default 'lovbot' que son de otra agencia

**Lo que Robert VE en su Business Manager**: WABAs individuales de los clientes finales. Nombres, números, templates. Pero NO la metadata de agencia (es concepto 100% interno de Arnaldo en PG `robert_crm`).

**Lo que Robert NO ve**: `client_slug` interno, `agencia_origen`, `worker_url`, brief comercial, precios, clientes agrupados por quién los vendió.

## SOP — Migración futura de tenant a otro TP

Cuando Arnaldo (o cualquier agencia del ecosistema) verifique portfolio propio y saque su propia app TP, puede migrar sus clientes **SIN pérdida de datos** (número, templates, quality rating):

### Pasos de la migración

1. **Cliente abre nuevo onboarding** de la app TP destino (ej: `arnaldo-onboarding.vercel.app/?client=garcia`).
2. **Embedded Signup de la app nueva** — Meta automaticamente revoca acceso de la app anterior al autorizar la nueva (el `signed_request` llega al webhook `/deauthorize` de Robert, que marca el tenant como revoked).
3. **Webhook de la nueva app recibe**:
   - MISMO `waba_id`
   - MISMO `phone_number_id`
   - NUEVO `access_token` (generado por la app nueva)
4. **Backend de la agencia destino registra** el tenant en su propia PG.
5. **POST `/{waba_id}/subscribed_apps`** con el nuevo token suscribe los webhooks a la app nueva.
6. **Historial de chats** queda intacto en Chatwoot/PG de la agencia destino (no viajan por Meta).
7. **Templates aprobadas** quedan en la WABA del cliente (Meta las conserva), solo hay que refrescar cache del listado con el nuevo token.

### Lo que se mantiene
- ✅ Número WhatsApp del cliente
- ✅ WABA ID + phone_number_id
- ✅ Historial de conversaciones
- ✅ Templates aprobadas
- ✅ Quality rating del número
- ✅ Business Portfolio del cliente (es suyo, no de la agencia)

### Lo que cambia
- 🔄 `access_token` (generado por la app nueva)
- 🔄 Webhook que recibe eventos (de `agentes.lovbot.ai` a infra de la agencia destino)

### Pain points de la migración
- ⚠️ Ventana de ~5 min sin servicio (entre revocar + autorizar — hacer en horario nocturno del cliente)
- ⚠️ Cliente debe hacer 1 click en el nuevo Embedded Signup (mandarle email/WhatsApp con instrucciones)
- ⚠️ Meta no permite migración 100% automática — exige consentimiento explícito del cliente

## Implementación técnica actualizada — 2026-04-21 (tarde)

### Endpoint único de onboarding

Vive en `workers/clientes/lovbot/robert_inmobiliaria/worker.py` (aprox. línea 3701):

```
POST https://agentes.lovbot.ai/clientes/lovbot/inmobiliaria/public/waba/onboarding
```

Body JSON que recibe desde el HTML de Vercel:
```json
{
  "code": "AQDxxx...",               // code del Facebook Login (FB.login callback)
  "waba_id": "123...",               // del evento FINISH del embedded signup
  "phone_number_id": "456...",       // del evento FINISH
  "slug": "mica-demo-inmo",          // slug del tenant — lo elige la agencia
  "agencia": "system_ia"             // lovbot | system_ia | arnaldo (default: lovbot)
}
```

### Flujo interno

1. Intercambio `code → access_token` contra `graph.facebook.com/v24.0/oauth/access_token` con `APP_ID=704986485248523` + `APP_SECRET`.
2. **Registro Cloud API con PIN** (fix crítico aplicado 2026-04-21):
   - Genera `pin = random.randint(100000, 999999)`.
   - Llama `POST /v24.0/{phone_number_id}/register` con `Authorization: Bearer {access_token}` y body `{"messaging_product":"whatsapp","pin":"{pin}"}`.
   - Errores 133005/133008 (ya registrado) = OK. Otros errores se loggean no-fatal.
3. Suscripción webhook: `POST /v24.0/{waba_id}/subscribed_apps` con el access_token del cliente.
4. **Routing condicional por agencia** (fix aplicado 2026-04-21):
   - `lovbot` → `worker_url = agentes.lovbot.ai/clientes/lovbot/{slug}/whatsapp` + crea DB Postgres `{slug}_crm` (llamada a `/admin/crear-db-cliente` en background).
   - `system_ia` → `worker_url = agentes.lovbot.ai/clientes/system_ia/{slug}/whatsapp` + NO crea DB (Airtable).
   - `arnaldo` → `worker_url = agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/{slug}/whatsapp` + NO crea DB (Airtable).
5. Guarda registro en `waba_clients` (tabla en `robert_crm`, compartida como directorio de routing) con: `slug`, `agencia_origen`, `phone_number_id`, `waba_id`, `access_token`, `cloud_api_pin`, `worker_url`, `meta_user_id`, `webhook_subscrito`.

### Schema `waba_clients` actualizado

```sql
ALTER TABLE waba_clients ADD COLUMN IF NOT EXISTS cloud_api_pin VARCHAR(6);
-- Columnas previas: agencia_origen, meta_user_id, access_token, worker_url, ...
```

### Router de webhooks Meta

`webhook_meta.py:195-216` recibe en `POST /webhook/meta/events`, extrae `phone_number_id` del payload, consulta `waba_clients`, y forwardea al `worker_url` del tenant con header `X-Tenant-Slug`. Si no hay match → descarta.

### HTML frontend

Ubicado en `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/onboarding-vercel/index.html`, deployado en `lovbot-onboarding.vercel.app`. Tiene ahora `<select id="selAgencia">` con 3 opciones. URL `?agencia=system_ia` preselecciona.

### Slug reservados actualmente

| Slug | Agencia | Worker |
|------|---------|--------|
| `inmobiliaria` | lovbot | `robert_inmobiliaria/worker.py` (Robert productivo) |
| `mica-demo-inmo` | system_ia | `system_ia/demos/inmobiliaria/worker.py` router v2 (renombrado desde `inmobiliaria-v2` el 2026-04-21) |
| `demos/inmobiliaria` | system_ia (legacy Evolution) | mismo worker, router v1, sigue activo |

## Regla mental que NO se rompe

**Robert es Tech Provider técnico ante Meta. NO es dueño de los clientes.** Cuando veas:

- `waba_clients` en `robert_crm` → es directorio compartido, no implica pertenencia.
- Endpoint onboarding en worker de Robert → es la puerta de entrada técnica, no implica pertenencia.
- App de Meta a nombre de Lovbot → es solo el TP, no implica pertenencia.

Mirá SIEMPRE `waba_clients.agencia_origen` para saber a qué agencia pertenece cada cliente. Sin eso podés terminar cruzando datos o cobrando mal.

## Relaciones

- [[meta-graph-api]] — API que se desbloquea después del onboarding
- [[meta-business-portfolio-verificacion]] — paso 0 antes de ser TP propio
- [[meta-webhooks-compliance]] — webhooks deauth + data_deletion que complementan
- [[numero-test-tech-provider]] — patrón para usar WABA de Robert como número de test cross-agencia
- [[lovbot-ai]] — agencia dueña de la app
- [[robert-bazan]] — persona propietaria del Business Portfolio
