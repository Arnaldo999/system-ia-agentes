---
name: Publicación Diaria Redes Sociales — Arnaldo + Mica
description: Sistema automático de publicación IG+FB+LinkedIn vía worker social + n8n, con brandbook en Airtable y credenciales en Supabase tabla clientes
type: project
---

Sistema de publicación diaria automatizada — activo desde 2026-04-07.

**Why:** Arnaldo y Mica publican contenido de valor en redes todos los días sin intervención manual.
**How to apply:** Cualquier nuevo cliente de redes sociales sigue este mismo patrón.

## Arquitectura

```
n8n Schedule (9am ARG, lun-sáb)
  → GET Airtable Brandbook (tabla Branding-Marca)
  → POST /social/publicar-completo
      → Gemini genera texto por canal (retry 3x en 503/429)
      → Gemini genera imagen con overlay título+subtítulo+logo
      → Cloudinary (almacena imagen)
      → Publica IG + FB + LinkedIn simultáneo
      → IF status=error → Alerta Telegram
```

## Estado actual (2026-04-09)

| Cliente | IG | FB | LinkedIn | Estado |
|---------|----|----|----------|--------|
| `Arnaldo_Ayala` | ✅ | ✅ | ✅ | LIVE |
| `SystemIA` (Mica) | ✅ | ✅ | ✅ | LIVE — token vence en 2 meses |

## Supabase — tabla `clientes` (multi-tenant)

El worker busca credenciales por `cliente_id` automáticamente. **n8n NO manda credenciales** — solo `cliente_id` + `datos_marca`.

**CRÍTICO**: La tabla en Supabase se llama `clientes` (no `Datos Proyecto X`). El worker busca en `/rest/v1/clientes`.

Campos requeridos por fila:
- `cliente_id` — ID único (ej: `SystemIA`, `Arnaldo_Ayala`)
- `meta_access_token` — token Meta (IG + FB)
- `ig_account_id` — ID cuenta IG Business
- `fb_page_id` — ID página Facebook
- `linkedin_access_token` — token OAuth2 LinkedIn (vence en 2 meses)
- `linkedin_person_id` — sub del usuario (ej: `Pq2P-idpM8`)

## Airtable Brandbooks

| Cliente | Base | Tabla | Campos clave |
|---------|------|-------|-------------|
| Arnaldo | `appOUtGnMYHrbLaMa` | `tblgFvYebZcJaYM07` | ID Cliente, Nombre Comercial, Industria, Público Objetivo, Tono de Voz, Colores de Marca, Estilo Visual, Logo, Reglas Estrictas |
| Mica | `appejn9ep8JMLJmPG` | `tblgFvYebZcJaYM07` | mismos campos, tabla se llama `Branding-Marca` |

Token Airtable: el mismo `AIRTABLE_TOKEN` global funciona para ambas bases.

**Bug conocido (resuelto 2026-04-09)**: el nodo "Obtener Brandbook Mica" en n8n tenía una credencial "Header Auth N8N" inexistente en la instancia de Mica + token Airtable incorrecto. Fix: `authentication: none` + token correcto hardcodeado en headers.

## n8n Workflows

| Cliente | n8n | Workflow ID | Estado |
|---------|-----|-------------|--------|
| Arnaldo | `n8n.arnaldoayalaestratega.cloud` | `aJILcfjRoKDFvGWY` | ✅ activo |
| Mica | `sytem-ia-pruebas-n8n.6g0gdj.easypanel.host` | `aOiZFbmvMoPSE0vB` | ✅ activo |

## Alertas Telegram

Ambos workflows tienen IF node: detecta `$json.status === "error"` → alerta Telegram chat `863363759` (Arnaldo).

## Retry Gemini 503/429 (agregado 2026-04-09)

`_call_gemini_text()` reintenta hasta 3 veces con backoff 5s/10s/15s. Aplica a todos los clientes.

## Rotación de temas (worker social)

6 días × 4 rubros automáticos — sin configuración:
- Lunes/Miércoles/Viernes → Gastronomía
- Martes/Jueves/Sábado → PyMEs genérico

---

## Checklist — Nuevo cliente redes sociales

### Lo que hay que pedir al cliente

**Meta (IG + FB):**
1. `Meta Access Token` — desde Meta Business Suite → Configuración → Usuarios del sistema → token con permisos `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`
2. `IG Business Account ID` — desde Meta Business Suite o Graph API Explorer: `GET /me/accounts` → buscar la página → campo `instagram_business_account.id`
3. `Facebook Page ID` — desde Meta Business Suite → Configuración → Info de la página → ID de página

**LinkedIn:**
1. Crear app en `linkedin.com/developers` → tab Products → agregar "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect"
2. Ir a `linkedin.com/developers/tools/oauth` → Create token → seleccionar app → marcar scopes: `openid`, `profile`, `email`, `w_member_social` → Request access token
3. Copiar el `Access token` generado
4. El `linkedin_person_id` (sub) se obtiene automáticamente llamando: `GET https://api.linkedin.com/v2/userinfo` con el token → campo `sub` del response

**Airtable Brandbook:**
- Nombre Comercial, Industria, Servicio Principal, Público Objetivo, Tono de Voz, Colores de Marca, Logo (URL), Reglas Estrictas

### Lo que hay que configurar

1. Agregar fila en tabla `clientes` de Supabase con todos los campos
2. Crear registro en Airtable Brandbook con `ID Cliente` = el `cliente_id` de Supabase
3. Crear workflow n8n en la instancia del cliente (copiar estructura de Arnaldo/Mica)
4. Activar toggle del workflow en la UI de n8n

### Notas críticas LinkedIn
- El token vence en **2 meses** — hay que renovarlo periódicamente
- El `sub` del `/v2/userinfo` es el person ID correcto (formato `Pq2P-idpM8`, NO `urn:li:person:...` ni número de URL)
- El worker construye el author URN internamente: `urn:li:person:{sub}`
- Si la app no tiene "Sign In with LinkedIn using OpenID Connect" → el endpoint `/v2/userinfo` da 403
- **Incógnito obligatorio** al generar tokens — extensiones del navegador rompen el state parameter OAuth2
