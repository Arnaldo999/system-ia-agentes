---
name: Runbook Meta Social Automation (FB + IG) — onboarding cliente nuevo
description: Pasos exactos, en orden, para activar publicación automática en FB + IG + bot de comentarios para un cliente nuevo de Arnaldo (o cualquier agencia del ecosistema). Evita 4-6 horas de debugging innecesario por sesión.
type: reference
proyecto: compartido
tags: [meta, facebook, instagram, onboarding, cliente-nuevo, social-automation, runbook]
ultima_actualizacion: 2026-04-23
probado_con: Maicol (Back Urbanizaciones) — sesión 2026-04-23
---

# Runbook — Meta Social Automation (FB + IG posts + bot comentarios)

> **Origen**: después de 6+ horas de debugging en sesión 2026-04-23 con Maicol, destilamos el proceso exacto. Para próximos clientes (Cesar Posada, futuros Arnaldo, Mica, Robert) debe tomar **20-30 min** si se sigue este runbook al pie.
>
> **Casos de uso ya cubiertos**:
> - Maicol (Arnaldo) — FB ✅ / IG pendiente solo link Maicol
> - Arnaldo Ayala agencia — funciona (workflow `aJILcfjRoKDFvGWY`)
> - System User permanente para Mica / Robert — pendiente mismo patrón

---

## Arquitectura del sistema (lo que hay que entender UNA vez)

```
┌──────────────────────────────────────────────────────────────────┐
│  SUPABASE ArnaldoAyalaAgencia — tabla `clientes` (multi-tenant)  │
│     cliente_id, fb_page_id, ig_account_id,                       │
│     meta_access_token, airtable_base_id, airtable_table_id       │
└──────────────────────────────────────────────────────────────────┘
                           ↓ worker busca por fb_page_id/ig_account_id
┌──────────────────────────────────────────────────────────────────┐
│  AIRTABLE del cliente — tabla `Branding`                         │
│     Todas las props: Industria, Servicio, Tono, Reglas, Colores, │
│     Logo, Estilo Visual, Público, CTA, Facebook Page ID, IG ID   │
└──────────────────────────────────────────────────────────────────┘
                           ↓ lee brandbook completo
┌──────────────────────────────────────────────────────────────────┐
│  BACKEND FastAPI — worker social                                 │
│  POST /social/publicar-completo                                  │
│     1. Gemini genera copy IG + LI + FB diferenciados             │
│     2. Gemini genera imagen con branding del cliente             │
│     3. Cloudinary hostea la imagen                               │
│     4. Publica en IG, LI, FB con Page Access Token del cliente   │
└──────────────────────────────────────────────────────────────────┘
                           ↓ dispara diariamente
┌──────────────────────────────────────────────────────────────────┐
│  n8n — workflow "📱 [Cliente] — Publicación Diaria Redes"        │
│     Schedule cron → Airtable brandbook → POST endpoint           │
└──────────────────────────────────────────────────────────────────┘
```

**Atajo mental**: Supabase = directorio de credenciales. Airtable = brandbook. Backend = orquestador. n8n = scheduler.

---

## Los 2 grandes gotchas que te salvan horas

### Gotcha #1 — User Token ≠ Page Access Token

**Error típico**: generás token desde Graph API Explorer con "Token del usuario" + los 10 scopes correctos, lo cargás en Supabase, disparás el endpoint y te da:

```
400: {"error":{"message":"Invalid JSON for postcard","type":"OAuthException","code":190}}
```

**Causa**: el token es **User Token** (te autentica a vos como persona), no **Page Access Token** (autentica la publicación en nombre de la página). Meta rechaza porque un user no puede publicar directo en una página ajena.

**Solución**: desde Graph API Explorer, hacer query:

```
<fb_page_id>?fields=access_token
```

Ejemplo: `985390181332410?fields=access_token`

Devuelve el **Page Access Token** derivado (y si el User Token era de 60 días = long-lived, este Page Token **no expira nunca** mientras no cambies password FB).

Ese es el token que va en Supabase.

### Gotcha #2 — System User Admin requiere 7 días de antigüedad

**Error típico**: querés crear System User con rol **Admin** en el BM del cliente (forma más limpia de token permanente) y Meta te bloquea con:

> *"El usuario administrador del sistema debe tener al menos 7 días de antigüedad para poder crear otros usuarios administradores del sistema."*

**Causa**: regla de seguridad de Meta. Si recién te agregaron al BM cliente como admin hoy, tenés que esperar 7 días.

**Soluciones** (en orden de preferencia):

1. **Que el dueño original del BM** (cliente, ej: Maicol) cree el System User. Él ya tiene >7 días de antigüedad.
2. **Usar Page Access Token permanente** (gotcha #1). Deriva de User Token long-lived y no tiene esa restricción. Cubre 90% de los casos.
3. **Esperar 7 días y después crear System User**. Si el deploy no urge.

---

## Pasos exactos — onboarding nuevo cliente (total ~30 min)

### Precondiciones (antes de empezar)

- [ ] Cliente ya tiene BM de Meta creado con Página FB + IG Business conectados al BM
- [ ] Tú (Arnaldo) fuiste agregado al BM del cliente como **Administrador**
- [ ] Cliente tiene Instagram Business Account vinculado a la Página FB (**crítico** — ver sección final)
- [ ] Base Airtable del cliente creada con tabla `Branding` populada con:
  - ID Cliente (ej: `Back_Urbanizaciones`)
  - Nombre Comercial, Industria, Servicio Principal, Público Objetivo
  - Tono de Voz, Reglas Estrictas, Estilo Visual, Colores de Marca, CTA
  - Logo (attachment)
  - Facebook Page ID (columna vacía, se llena ahora)
  - IG Business Account ID (columna vacía, se llena ahora)

### Paso 1 — Obtener Facebook Page ID + IG Business Account ID (3 min)

**Facebook Page ID**:
1. `business.facebook.com` → BM del cliente → Configuración → Cuentas → Páginas
2. Click en la página → panel derecho muestra **"Identificador"**
3. Copiar el número (15-16 dígitos)

**Instagram Business Account ID**:
1. Misma vista, menú lateral → **Cuentas de Instagram**
2. Click en `@usuario` → panel derecho muestra **"Identificador"**
3. Copiar el número (17-18 dígitos, empieza con `17841`)

**Cargar ambos en Airtable del cliente** (tabla Branding, fila del cliente):
- `Facebook Page ID` = `<page_id>`
- `IG Business Account ID` = `<ig_id>`

### Paso 2 — Compartir app Meta Developer con el BM del cliente (3 min)

**Contexto**: usamos **una sola app Meta** del ecosistema: `Social Media Automator AI` (App ID: `895855323149729`). Vive en el BM personal de Arnaldo (`Emprender en lo Digital`). Se comparte con cada BM cliente.

**Pasos**:
1. `business.facebook.com` → seleccionar BM **Emprender en lo Digital** (Arnaldo)
2. Configuración → Cuentas → **Apps** → click en `Social Media Automator AI`
3. Tab **"Socios"** → click **"+ Agregar"** → **"Compartir esta app con un socio"**
4. **Enter partner business ID**: pegar el ID del BM del cliente (está en la URL cuando el cliente entra a su BM, ej: `business_id=1633606387950668`)
5. Permisos (toggles):
   - ✅ **Desarrollar app** (ya viene activado)
   - ✅ **Ver estadísticas**
   - ✅ **Probar app** ← crítico para que puedan crear System Users
   - ❌ **Administrar app** (NO activar — mantiene control en tu BM)
6. Click **Asignar**

### Paso 3 — Aceptar la app desde el BM del cliente (1 min)

1. Cambiar al BM del cliente (selector arriba izquierda)
2. Configuración → Cuentas → **Apps** → aparece `Social Media Automator AI` como **"Pendiente"** (o ya aceptada)
3. Si está pendiente, click **Aceptar** / **Conectar**

### Paso 4 — Generar Page Access Token permanente (5 min)

**Método recomendado**: Gotcha #1 explicado arriba.

1. Entrar a https://developers.facebook.com/tools/explorer/
2. **App**: seleccionar `Social Media Automator AI`
3. **User or Page**: click → **"Token del usuario"**
4. **Permisos** — agregar estos 10 scopes:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_read_user_content`
   - `pages_manage_posts`
   - `pages_manage_engagement`
   - `pages_manage_metadata`
   - `instagram_basic`
   - `instagram_content_publish`
   - `instagram_manage_comments`
   - `business_management`
5. Click **Generate Access Token** → login con Facebook personal (email asociado al BM cliente)
6. En el diálogo de selección de páginas: marcar SOLO la página del cliente (ej: Back Urbanizaciones), NO otras
7. Aceptar permisos
8. Se genera el **User Token** corto (2 horas)

**Extender a 60 días** (convierte a "long-lived"):

9. Ir a https://developers.facebook.com/tools/debug/accesstoken/
10. Pegar el User Token corto → **Debug**
11. Click **"Extend Access Token"** → confirmar
12. Copiar el User Token extendido (60 días)

**Intercambiar User Token → Page Access Token** (truco clave):

13. Volver a Graph API Explorer
14. Pegar el User Token extendido en el campo "Token de acceso"
15. En el campo de query, pegar: `<fb_page_id>?fields=access_token`
    - Ejemplo: `985390181332410?fields=access_token`
16. Click **Enviar**
17. La respuesta JSON te da el **Page Access Token permanente**:
    ```json
    { "access_token": "EAA...TOKEN_PAGE...", "id": "985390181332410" }
    ```
18. Copiar ese `access_token` (largo, empieza con `EAA`)

**⚠️ VERIFICACIÓN CRÍTICA antes de cargarlo en Supabase (Gotcha #4 — aprendizaje 2026-04-24)**:

19. Volver a https://developers.facebook.com/tools/debug/accesstoken/
20. Pegar el **Page Token recién generado** → click **Debug**
21. El resultado debe decir:
    - **Expires**: `Never` ← si dice esto, el token es permanente y podés cargarlo en Supabase
    - **Issued**: fecha de hoy
    - **Scopes**: los 10 que cargaste al User Token original
22. Si dice **"Expires in 1-2 hours"** o **"Expires in X seconds"** → el User Token origen NO era long-lived. Volver al paso 9 (Extender a 60 días) y asegurarse de que el User Token extendido diga "Expires in 60 days" ANTES de hacer el intercambio a Page Token.

**Ejemplo real de falla (Maicol 2026-04-23/24)**: se cargó en Supabase un Page Token creyendo que era permanente, pero expiró 6h después con error 190 subcode 463 "Session has expired".

**Causa raíz descubierta el 2026-04-24**: aunque el debugger de Meta mostraba el User Token extendido diciendo "caducará en 60 días", Meta liga el Page Token derivado a la **sesión de Facebook del navegador** en el momento del intercambio. Si la sesión FB ya es vieja (cerraste navegador, pasaron horas, reinicio PC), el Page Token hereda ese estado "sesión ya expirando" y muere al día siguiente.

**Regla de oro para el intercambio User → Page**:

1. **Antes de empezar**: cerrar sesión FB y volver a entrar (sesión fresca)
2. Hacer TODO el flujo en **una sola sesión de navegador sin pausas**:
   - Generar User Token
   - Extender a 60d (mismo tab)
   - Intercambiar a Page Token (mismo tab)
   - Verificar Page Token dice "Expires: Never" (mismo tab)
   - UPDATE Supabase (mismo tab o inmediato)
3. Si en algún momento te ausentás > 1-2h entre pasos, reempezar desde el paso 1 (sesión fresca).

**Alternativa robusta (requiere 7 días de antigüedad BM)**: usar **System User Token** desde día 8+, que NO depende de sesión de Facebook porque es un usuario del BM, no de tu perfil personal.

### Paso 5 — Insertar/Actualizar registro en Supabase tabla `clientes` (2 min)

**⚠️ Gotcha #5 — Columna correcta (aprendizaje 2026-04-24)**:

El token DEBE ir en la columna **`meta_access_token`** (es la que el worker lee via `supa_creds.get("meta_access_token", "")`). La columna `token_notas` es solo para metadata humana ("cuándo venció, por qué, cómo se regeneró"), NO para el token real.

Si pegás el token en `token_notas` por error, el backend sigue leyendo el token viejo de `meta_access_token` sin tirar error — el bug es silencioso y muy difícil de diagnosticar sin mirar la columna exacta.

**Este bug se repitió 2 veces en la misma sesión 2026-04-24**: pegar token en Table Editor de Supabase es propenso a errores con strings largos (el editor a veces no guarda el valor correctamente, o el usuario confunde columnas cuando ambas tienen type `text`).

**Regla operativa — SIEMPRE usar SQL Editor para tokens**:

En vez de editar celdas en Table Editor, ejecutar siempre:
```sql
UPDATE clientes
SET meta_access_token = 'EAA...TOKEN_NUEVO...',
    token_notas = 'Contexto breve del regen: fecha, scopes nuevos, razón',
    updated_at = NOW()
WHERE cliente_id = '<ID_CLIENTE>';

-- Verificar
SELECT cliente_id, substring(meta_access_token, 1, 30) as preview, updated_at
FROM clientes WHERE cliente_id = '<ID_CLIENTE>';
```

Si ya cometiste el error de pegar en `token_notas`, el fix rápido:
```sql
UPDATE clientes
SET meta_access_token = token_notas,
    token_notas = 'Contexto breve',
    updated_at = NOW()
WHERE cliente_id = '<ID_CLIENTE>';
```

**⚠️ Gotcha #8 — Agente NO debe escribir tokens via bash curl con vars de shell (aprendizaje 2026-04-24)**:

Tokens tienen ~200+ chars incluyendo caracteres que bash interpreta (`&`, `$`, `(`, `)`). Escapar correctamente una variable shell que viaja por `curl -d` → Python heredoc embedido → HTTP body JSON es frágil y falla silenciosamente escribiendo string vacío.

**Caso real**: el agente intentó `curl -X PATCH "$SUPABASE_URL/..." -d "$(python3 -c "...")"` donde el python leía `PAGE_TOKEN_VAL=$PAGE_TOKEN` como env var. El shell no propagó la variable correctamente y el JSON payload terminó con `"meta_access_token": ""`. Supabase aceptó el UPDATE con string vacío, sobrescribiendo el token real. Efecto: **token perdido, hay que regenerar**.

**Regla**: el agente NO debe escribir tokens a Supabase via curl con variables de shell. Preparar el SQL como texto para que el usuario lo ejecute en Supabase SQL Editor. El agente puede **leer** tokens (para testear validez) pero la escritura de tokens largos se hace manualmente via SQL Editor para evitar este bug.

Si el agente absolutamente necesita escribir, usar archivo temp:
```bash
echo "$PAGE_TOKEN" > /tmp/token.txt
curl -X PATCH ... -d "$(python3 -c "import json; t=open('/tmp/token.txt').read().strip(); print(json.dumps({'meta_access_token': t}))")"
rm /tmp/token.txt
```


URL: https://supabase.com/dashboard/project/pczrezpmdugdsjrxspjh/sql/new

```sql
-- Columnas de trackeo (solo primera vez si no existen)
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS token_tipo VARCHAR(50);
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS token_expira_at TIMESTAMPTZ;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS token_notas TEXT;

INSERT INTO clientes (
  cliente_id,
  nombre_negocio,
  estado,
  meta_access_token,
  fb_page_id,
  ig_account_id,
  whatsapp_numero_notificacion,
  airtable_base_id,
  airtable_table_id,
  token_tipo,
  token_expira_at,
  token_notas,
  created_at,
  updated_at
) VALUES (
  '<ID_CLIENTE>',           -- ej: Back_Urbanizaciones
  '<NOMBRE_COMERCIAL>',     -- ej: Back Urbanizaciones
  'activo',
  '<PAGE_ACCESS_TOKEN>',    -- el del paso 4
  '<FB_PAGE_ID>',
  '<IG_ACCOUNT_ID>',
  '<WHATSAPP_NUMERO>',      -- ej: 5493764815689 (bot del cliente)
  '<AIRTABLE_BASE_ID>',     -- ej: appaDT7uwHnimVZLM (Maicol)
  '<AIRTABLE_TABLE_ID>',    -- ej: tbl0QeaY3oO2P5WaU (tabla Branding)
  'page_access_token_permanente',
  NULL,
  'Page Access Token permanente (derivado de User Token 60d). No expira mientras no se cambie password FB ni se revoque la app.',
  NOW(),
  NOW()
);

-- Verificar
SELECT cliente_id, nombre_negocio, estado, fb_page_id, ig_account_id, token_tipo
FROM clientes
WHERE cliente_id = '<ID_CLIENTE>';
```

### Paso 6 — Duplicar workflow n8n (5 min)

1. Entrar al n8n del proyecto que corresponde (Arnaldo: `n8n.arnaldoayalaestratega.cloud`)
2. Buscar workflow base: `📱 Arnaldo — Publicación Diaria Redes Sociales (IG + FB + LI)` (ID: `aJILcfjRoKDFvGWY`)
3. Click "..." → **Duplicar**
4. Renombrar: `📱 <Cliente> — Publicación Diaria Redes Sociales`
5. Editar node **📋 Obtener Brandbook**:
   - URL: cambiar a `https://api.airtable.com/v0/<BASE_ID>/<TABLE_ID>?maxRecords=1&filterByFormula={ID%20Cliente}='<ID_CLIENTE>'`
   - Ejemplo Maicol: `https://api.airtable.com/v0/appaDT7uwHnimVZLM/tbl0QeaY3oO2P5WaU?maxRecords=1&filterByFormula={ID%20Cliente}='Back_Urbanizaciones'`
6. Credencial HTTP Header Auth:
   - Si el cliente tiene base Airtable propia → crear credencial nueva `Header Auth Airtable <Cliente>` con `Bearer <AIRTABLE_TOKEN_CLIENTE>` en Authorization
   - Si usa la base Arnaldo → reusar credencial existente
7. Node **🚀 Publicar en Redes** — NO tocar (el endpoint resuelve credenciales por `cliente_id`)
8. Ajustar **Schedule** si querés evitar horario pico (ej: Arnaldo 9am, Maicol 10am, próximo cliente 11am)
9. **Activar** workflow

**Alternativa**: usar MCP n8n (`mcp__n8n__n8n_create_workflow`) con el payload documentado más abajo.

### Paso 7 — Test end-to-end (3 min)

Disparar el endpoint manualmente desde terminal:

```bash
AIRTABLE_TOKEN="<TOKEN_AIRTABLE_CLIENTE>"
BRANDBOOK=$(curl -s -H "Authorization: Bearer $AIRTABLE_TOKEN" \
  "https://api.airtable.com/v0/<BASE_ID>/<TABLE_ID>?maxRecords=1&filterByFormula=%7BID%20Cliente%7D%3D%27<ID_CLIENTE>%27")

PAYLOAD=$(echo "$BRANDBOOK" | python3 -c "
import json, sys
d = json.load(sys.stdin)
fields = d['records'][0]['fields']
print(json.dumps({'cliente_id': fields.get('ID Cliente'), 'datos_marca': fields}))
")

curl -s -X POST "https://agentes.arnaldoayalaestratega.cloud/social/publicar-completo" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" --max-time 180
```

**Respuesta esperada** (éxito total):
```json
{
  "status": "success",
  "publicaciones": {
    "instagram": {"success": true, "post_id": "..."},
    "facebook":  {"success": true, "post_id": "985390181332410_..."},
    "linkedin_perfil": {"success": false, "error": "Faltan credenciales de LinkedIn"}
  }
}
```

**Respuesta parcial** (FB OK, IG falla):
```json
{
  "status": "partial",
  "publicaciones": {
    "instagram": {"success": false, "error": "(#10) Application does not have permission for this action"},
    "facebook":  {"success": true, "post_id": "..."}
  }
}
```

Si IG falla con error `#10` → ir a sección siguiente (IG no conectado a FB Page).

---

## Gotcha #3 — IG debe estar conectado a la Page FB (no solo "en el mismo BM")

**Error típico**:
```
(#10) Application does not have permission for this action
```

**Causa**: aunque ambos activos (Página FB + IG Business) estén en el BM del cliente, Meta requiere **vínculo explícito IG ↔ Page FB** para que un token FB pueda publicar en IG.

**Cómo detectarlo**: entrar a `business.facebook.com → BM cliente → Configuración → Cuentas → Páginas → click en página → ver si aparece "Conectar con Instagram"`. Si aparece ese botón → **no está conectado**.

**Solución** (link directo que podés mandar al cliente):

```
https://www.facebook.com/settings/?tab=linked_instagram
```

El cliente entra (logueado con SU Facebook) → Click **"Conectar cuenta"** → pone sus credenciales de Instagram → acepta permisos.

**Importante**: este paso lo tiene que hacer el **dueño del IG** porque requiere las credenciales de IG. Nosotros no las tenemos ni queremos tenerlas.

**Mensaje plantilla para el cliente**:

```
Hola [Nombre], última cosa para que Instagram publique automático.

Tu página de Facebook [Página] no tiene Instagram conectado. Te paso el link directo, 30 segundos:

👉 https://www.facebook.com/settings/?tab=linked_instagram

1. Abrís el link (logueado con tu Facebook)
2. Click en "Conectar cuenta"
3. Ponés usuario y contraseña de tu Instagram
4. Aceptás permisos

Cuando termines me avisás y pruebo que también publique en IG.
```

---

## Migración a System User permanente (día 8+ del onboarding)

Después de que pasen **7 días de antigüedad** de Arnaldo como admin del BM cliente, migrar del Page Access Token al System User Token permanente (más robusto, no depende de tu cuenta personal de Facebook):

1. BM cliente → Configuración → Usuarios → **Usuarios del sistema** → **+ Agregar**
2. Nombre: `<Cliente> Automation` (ej: `BackUrban Automation`)
3. Rol: **Admin**
4. Asignar activos: Página FB + IG Business + Cuenta Publicitaria (todos con rol "Control total")
5. Generar token permanente con app `Social Media Automator AI` + los 10 scopes (mismos que Page Token)
6. **UPDATE en Supabase**:

```sql
UPDATE clientes
SET meta_access_token = '<NUEVO_SYSTEM_USER_TOKEN>',
    token_tipo = 'system_user_token_permanente',
    token_expira_at = NULL,
    token_notas = 'System User permanente desde <fecha>. Independiente de cuenta personal.',
    updated_at = NOW()
WHERE cliente_id = '<ID_CLIENTE>';
```

---

## Bot de comentarios automáticos (Fase 2)

Una vez publicación OK, activar bot que responde comentarios IG/FB + invita a DM. El endpoint `POST /social/meta-webhook` ya está implementado en `workers/social/worker.py` y es multi-tenant (resuelve credenciales por `page_id` via Supabase). Solo falta **configurar webhook en la app Meta + suscribir cada Page/IG del cliente**.

### Paso 1 — Configurar webhook en la app Meta Developer (una sola vez por app)

1. https://developers.facebook.com/apps/895855323149729/webhooks/
2. Si no está configurado, agregar:
   - **Callback URL**: `https://agentes.arnaldoayalaestratega.cloud/social/meta-webhook`
   - **Verify Token**: el valor de `META_WEBHOOK_VERIFY_TOKEN` en Coolify (env var del backend `system-ia-agentes`)
3. Suscribir a objetos:
   - **Page** → campos: `feed`, `mention`, `messages`
   - **Instagram** → campos: `comments`, `mentions`, `messages`
4. Verificar que el status diga "Active" o "Verified"

### Paso 2 — Suscribir la Page de cada cliente vía API Graph

Meta NO suscribe automáticamente las pages al webhook solo porque la app tiene webhooks configurados — hay que suscribir cada Page individualmente usando su Page Access Token:

```bash
# Suscribir Page al webhook (recibe eventos feed, mention, messages)
curl -X POST "https://graph.facebook.com/v22.0/<PAGE_ID>/subscribed_apps" \
  -d "subscribed_fields=feed,mention,messages" \
  -d "access_token=<PAGE_ACCESS_TOKEN_DEL_CLIENTE>"

# Respuesta esperada: {"success": true}
```

Ejemplo Maicol:
```bash
curl -X POST "https://graph.facebook.com/v22.0/985390181332410/subscribed_apps" \
  -d "subscribed_fields=feed,mention,messages" \
  -d "access_token=$PAGE_TOKEN_MAICOL"
```

### Paso 3 — Suscribir el IG Business Account del cliente

Instagram usa un endpoint distinto (se suscribe por el IG_ID, no por Page):

```bash
# Suscribir IG Business Account al webhook (recibe comments, mentions, messages)
curl -X POST "https://graph.facebook.com/v22.0/<IG_ACCOUNT_ID>/subscribed_apps" \
  -d "subscribed_fields=comments,mentions,messages" \
  -d "access_token=<PAGE_ACCESS_TOKEN_DEL_CLIENTE>"

# Respuesta esperada: {"success": true}
```

### Paso 4 — Verificar suscripciones

```bash
# Ver apps suscritas a la Page
curl "https://graph.facebook.com/v22.0/<PAGE_ID>/subscribed_apps?access_token=<TOKEN>"

# Ver apps suscritas al IG
curl "https://graph.facebook.com/v22.0/<IG_ACCOUNT_ID>/subscribed_apps?access_token=<TOKEN>"
```

Debe aparecer `Social Media Automator AI` con los campos suscritos.

### Paso 5 — Test end-to-end

1. Ir al post publicado automáticamente en Facebook de la Page del cliente
2. Escribir un comentario desde otra cuenta (o pedirle a alguien) tipo: *"Precio?"* o *"¿En qué zona queda?"*
3. En ~5-10 segundos el bot debe responder con el tono del brandbook del cliente
4. Revisar logs Coolify: debería aparecer `[WEBHOOK] field='feed' item='comment' verb='add'` + `[WEBHOOK] reply_result=...`

### Qué hace el backend cuando llega un comentario

El código de `workers/social/worker.py` (endpoint `/social/meta-webhook`) hace:
1. **Parse entry**: extrae `page_id` del webhook body
2. **Carga credenciales**: `_get_supa_credenciales_by_page(page_id)` → Supabase `clientes`
3. **Carga brandbook**: `_get_cliente_por_page_id(page_id, base_airtable, table_airtable)` → Airtable del cliente
4. **Anti-loop**: compara `from_id` del comentario vs IDs propios (evita responder comentarios hechos por la propia página/bot)
5. **Genera respuesta** con Gemini usando el tono del brandbook + context del comentario
6. **Publica reply** al comentario:
   - IG: `POST /{comment_id}/replies`
   - FB: `POST /{comment_id}/comments`
7. **(Opcional)** Envía DM al comentarista invitando a hablar con el bot WhatsApp para info profunda

### Prompt del bot de comentarios

El prompt de `_responder_comentario` (definido en `workers/social/worker.py`):
- Agradece cálido el comentario
- NO revela precios/ubicaciones específicas en público
- SIEMPRE termina con link literal `https://wa.me/<numero_bot>` (precedido por flecha 👉)
- Tope de 2 líneas
- Respeta tono y restricciones del brandbook del cliente (leídas de Airtable)
- Diferencia por tipo de comentario (interés real / positivo genérico / objeción / spam)

---

## Bot de DMs (Mensajes Directos Messenger) — Fase 3

Idéntico patrón al bot de comentarios pero para mensajes privados a la Page de Facebook.

### Scopes adicionales necesarios

Agregar al User Token inicial (paso 4 del setup):
- `pages_messaging` ← CRÍTICO para enviar DMs desde la Page

Total de scopes ahora: **11** (los 10 iniciales + `pages_messaging`).

### Paso 1 — Regenerar token con nuevo scope

Seguir mismo flujo del Paso 4 del setup principal, pero agregando `pages_messaging` a la lista de permisos en Graph API Explorer antes de "Generate Access Token". Meta pedirá aprobar el nuevo scope en el popup.

Extender a 60 días → intercambiar a Page Token → verificar "Expires: Never" → UPDATE Supabase.

### Paso 2 — Suscribir la Page al field `messages`

```bash
# Agregar 'messages' a los fields suscritos (feed, mention, ratings ya están)
curl -X POST "https://graph.facebook.com/v22.0/<PAGE_ID>/subscribed_apps" \
  -d "subscribed_fields=feed,mention,ratings,messages" \
  -d "access_token=<PAGE_TOKEN_CON_pages_messaging>"
```

Verificar:
```bash
curl "https://graph.facebook.com/v22.0/<PAGE_ID>/subscribed_apps?access_token=<TOKEN>"
# Respuesta debe incluir "messages" en subscribed_fields
```

### Paso 3 — Código del backend (ya implementado commit 675dc9e)

El endpoint `POST /social/meta-webhook` ya maneja los DMs:

1. **Detecta estructura distinta**: DMs llegan en `entry.messaging` (no en `entry.changes` que usan comentarios).
2. **Anti-loop para DMs**:
   - Ignora `message.is_echo` (mensajes que la propia Page envió)
   - Ignora si `sender.id` es la propia Page
   - Ignora si `recipient.id` != Page (no es para nosotros)
3. **Llama `_responder_dm()`**: genera respuesta con Gemini + link wa.me + envía via Messenger Send API (`POST /me/messages`).
4. **Guardrail final**: si Gemini omite el link wa.me por error, lo appendea al final antes de enviar.

### Test end-to-end de DM

1. Desde una cuenta de FB que NO sea admin de la Page, mandá DM a la Page del cliente
2. En 5-10 seg el bot debe responder con link `wa.me/<numero>` clickeable
3. Logs Coolify deben mostrar:
   ```
   [WEBHOOK-DM] from=<user_id> to=<page_id> texto='...'
   [DM-REPLY] status=200 body={"recipient_id":...,"message_id":...}
   [WEBHOOK-DM] result={'success': True, 'respuesta': '...wa.me/...'}
   ```

### Gotcha #6 — Messenger requiere primer mensaje del usuario (24h window)

Meta solo permite que la Page envíe DM a un usuario **si el usuario le escribió primero dentro de las últimas 24h** (política de anti-spam). Esto significa:

- ✅ Si un usuario escribe DM → tenemos 24h para responder automáticamente
- ❌ No podemos iniciar conversaciones DM en frío
- ❌ Después de 24h del último mensaje del usuario, necesitamos Message Tags (pagados o específicos) para responder

El bot actual solo responde cuando el usuario escribió PRIMERO, así que esto no bloquea nada — pero para futuras features (remarketing por DM, etc.) hay que tenerlo en cuenta.

### Gotcha #7 — Messenger Send API usa "RESPONSE" messaging_type

Cuando enviás el DM, el payload incluye `messaging_type: "RESPONSE"` que indica "estoy respondiendo un mensaje del usuario". Otros valores posibles:
- `UPDATE`: actualización de una conversación activa
- `MESSAGE_TAG`: respuesta fuera de 24h con un tag válido

Usar siempre `RESPONSE` para auto-responses dentro de 24h del mensaje del usuario.

---

## Checklist final onboarding

- [ ] Paso 1 — Page ID + IG ID obtenidos y cargados en Airtable
- [ ] Paso 2 — App `Social Media Automator AI` compartida con BM cliente
- [ ] Paso 3 — App aceptada en BM cliente
- [ ] Paso 4 — Page Access Token permanente generado
- [ ] Paso 5 — Registro insertado en Supabase tabla `clientes`
- [ ] Paso 6 — Workflow n8n duplicado y activo
- [ ] Paso 7 — Test endpoint exitoso (al menos Facebook OK)
- [ ] Gotcha #3 — IG conectado a Page FB (verificar con test hasta success)
- [ ] Fase 2 (opcional) — Webhook comentarios activo
- [ ] Día 8+ — Migrar a System User permanente

---

## Referencias del ecosistema

### Credenciales clave (en `.env` o Supabase)
- `SUPABASE_URL` + `SUPABASE_KEY` — backend lee de tabla `clientes`
- `GEMINI_API_KEY` — generación de copy + imagen
- `CLOUDINARY_*` — hosting de imágenes generadas

### Recursos Meta
- **App ID ecosistema**: `895855323149729` (Social Media Automator AI)
- **App Owner BM**: `Emprender en lo Digital` (Arnaldo)
- **Graph API Explorer**: https://developers.facebook.com/tools/explorer/
- **Debug Token**: https://developers.facebook.com/tools/debug/accesstoken/

### Clientes activos en el sistema
| Cliente | ID Cliente | FB Page ID | Airtable Base | Estado |
|---------|-----------|------------|---------------|--------|
| Arnaldo Ayala | `Arnaldo_Ayala` | (propio) | `appOUtGnMYHrbLaMa` / `tblgFvYebZcJaYM07` | ✅ activo workflow `aJILcfjRoKDFvGWY` |
| Maicol Back Urbanizaciones | `Back_Urbanizaciones` | `985390181332410` | `appaDT7uwHnimVZLM` / `tbl0QeaY3oO2P5WaU` | ✅ FB activo workflow `xp49TY9WSjMtPvZK` — IG pendiente link cliente |

### Workflows n8n
- Base / plantilla: `aJILcfjRoKDFvGWY` (Arnaldo) — 5 nodos: Schedule → Airtable → POST publicar → IF error → Telegram alert
- Cliente Maicol: `xp49TY9WSjMtPvZK`

### Endpoint backend
- `POST /social/publicar-completo` — orquesta TODO el flujo (IA + imagen + publish)
- `POST /social/meta-webhook` — recibe comentarios IG/FB
- Backend: `agentes.arnaldoayalaestratega.cloud`

### Worker social — archivo
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/social/worker.py` (1900+ líneas)

---

## Decisiones de diseño (por qué X y no Y)

- **¿Por qué una sola app Meta compartida y no una por cliente?** Más simple de mantener (review de Meta, permisos, secrets). Cada cliente tiene su propio token, no comparten. La app solo es el "namespace" de auth.
- **¿Por qué Supabase y no env vars de Coolify?** Multi-tenant real (N clientes sin redeploy), editable por UI, query por `page_id/cliente_id`, cada cliente aislado.
- **¿Por qué Airtable del cliente y no Supabase solo?** Airtable es la UX de **branding** que el cliente (o el equipo) edita. Supabase es solo para credenciales. Separación cleaner.
- **¿Por qué Page Token y no User Token directo?** User Token no tiene permiso para publicar en nombre de página (error 190). Page Token sí.
- **¿Por qué no System User desde día 1?** Regla 7 días de Meta bloquea a admins nuevos del BM. Page Token salva la espera.

---

## Checklist "5 min debugging" cuando algo falla

| Síntoma | Causa probable | Fix |
|---------|----------------|-----|
| `code 190` "Invalid JSON for postcard" | Token es User, no Page | Gotcha #1: derivar Page Token |
| `code 190 subcode 463` "Session has expired" | Token Page derivó de User NO extendido | Gotcha #4: regenerar con User Token verificado de 60d ANTES del intercambio |
| `code 10` "Application does not have permission" | IG no conectado a Page FB | Gotcha #3: link settings linked_instagram |
| `Faltan credenciales de Evolution` | No crítico si worker es social puro | Ignorar si cliente no usa Evolution |
| `Faltan credenciales de LinkedIn` | Cliente no tiene LinkedIn configurado | Ignorar o cargar LI en Supabase |
| Post no aparece en FB | Demora hasta 1 min por cache | Esperar + refrescar. Si sigue, revisar logs Coolify |
| Imagen sin logo o colores mal | Branding Airtable incompleto | Llenar campos Logo, Colores de Marca, Estilo Visual |
| Workflow n8n falla en el cron | Credencial Airtable inválida | Regenerar token Airtable + actualizar credencial n8n |
| Bot no responde comentarios | Page/IG no suscritas a webhook | Hacer POST `/{page_id}/subscribed_apps?subscribed_fields=feed,mention,messages` con Page Token |

---

## Histórico de descubrimientos

- **2026-04-07**: workflow base Arnaldo creado (`aJILcfjRoKDFvGWY`)
- **2026-04-10**: versión estable del workflow (versión 31)
- **2026-04-23**: primer onboarding cliente (Maicol Back Urbanizaciones). Descubiertos los 3 gotchas. Facebook publicando OK. IG pendiente de link del cliente. Documentado este runbook.
- **2026-04-30** (pendiente): regla de 7 días de Meta se cumple para Arnaldo en BM Back Urbanizaciones. Migrar a System User permanente.
