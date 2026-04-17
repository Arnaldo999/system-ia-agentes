# Migración Webhook Comentarios Meta — 2026-03-05

## Resumen

El sistema de respuesta automática a comentarios de Instagram y Facebook fue migrado
de un workflow de n8n a **FastAPI en Render** de forma directa.

---

## Arquitectura ANTERIOR (con bugs)

```
Comentario IG/FB
      ↓
Meta → n8n Webhook /meta-comentarios
      ↓ (10 nodos con errores)
- Busca cliente en Airtable (base maestra, no la del cliente)
- Llama Gemini directamente (sin fallback)
- Publicaba con /replies para AMBAS plataformas (ERROR en Facebook)
- Facebook: usaba texto del webhook (vacío, ERROR)
- Token: de Airtable (no de Supabase)
```

**Bugs corregidos por la migración:**
- ❌ Facebook usaba endpoint incorrecto `/replies` (debe ser `/comments`)
- ❌ Facebook texto vacío (el webhook de Meta no envía el texto — hay que fetchearlo)
- ❌ Token venía de Airtable en lugar de Supabase
- ❌ No había protección anti-loop (podría responder a propios comentarios)

---

## Arquitectura ACTUAL (FastAPI directo)

```
Comentario IG/FB
      ↓
Meta → FastAPI Render /social/meta-webhook
      ↓
1. _get_supa_credenciales_by_page(page_id)  → Supabase
2. _get_cliente_por_page_id(page_id, base)  → Airtable del cliente
3. Anti-loop: ignora comentarios propios (from_id check)
4. Facebook: fetch texto via GET /{comment_id}?fields=message
5. Genera respuesta con Gemini (tono del cliente)
6. Publica:
   - Instagram → POST /{comment_id}/replies
   - Facebook  → POST /{comment_id}/comments (Page Token automático)
```

---

## Cambios realizados

### 1. Meta for Developers — Webhooks
- **URL anterior:** `https://sytem-ia-pruebas-agente.6g0gdj.easypanel.host/social/meta-webhook`
  _(typo + instancia de pruebas de Easypanel)_
- **URL nueva:** `https://system-ia-agentes.onrender.com/social/meta-webhook`
- **Token de verificación:** `SystemIA2026`
- **Campos suscritos:**
  - Page: `feed` ✅
  - Instagram: `comments` ✅

### 2. Workflow n8n `LKfHv7GMM5N75ehk`
- Nombre: "💬 Responder Comentarios - Instagram & Facebook"
- **Estado:** ⏸️ Desactivado (ya no recibe tráfico)
- Puede eliminarse en el futuro si todo funciona bien

---

## Código FastAPI relevante

**Archivo:** `workers/social/worker.py`

- `_get_supa_credenciales_by_page(page_id)` → Busca cliente en Supabase por FB/IG ID
- `_get_cliente_por_page_id(page_id, base)` → Brandbook en Airtable del cliente
- `_responder_comentario(comentario_id, texto, cliente, page_id)` → Genera + publica reply
- `_get_page_token(page_id, user_token)` → Intercambia user token por page token
- `meta_webhook_verificar()` → GET: verificación de Meta
- `meta_webhook_eventos()` → POST: procesa comentarios

---

## Multi-tenant

El sistema funciona para TODOS los clientes con un solo endpoint.
Identifica el cliente por `page_id` (FB Page ID o IG Account ID) en la tabla `clientes` de Supabase.

### Clientes activos
| Cliente | FB Page ID | IG Account ID |
|---------|-----------|---------------|
| Micaela (Agencia System IA) | 1010424822153264 | 17841480610317297 |
| Arnaldo (System IA) | 355053299059556 | 17841452133822887 |

Para agregar nuevo cliente: insertar fila en tabla `clientes` de Supabase con sus IDs.
**No hay que tocar código ni n8n.**

---

## Variables de entorno necesarias en Render

```
SUPABASE_URL=...
SUPABASE_KEY=...
GEMINI_API_KEY=...
META_WEBHOOK_VERIFY_TOKEN=SystemIA2026
AIRTABLE_TOKEN=...
AIRTABLE_BASE_ID=appejn9ep8JMLJmPG   (base maestra fallback)
AIRTABLE_TABLE_ID=tblgFvYebZcJaYM07
```
