---
title: "Meta Webhooks de Compliance — Deauthorize + Data Deletion"
tags: [meta, compliance, gdpr, webhooks, n8n, cloudflare, robert, documentacion-oficial]
source_count: 1
proyectos_aplicables: [robert]
---

# Meta Webhooks de Compliance — Deauthorize + Data Deletion

## Definición

Meta exige que toda app tipo Tech Provider (que maneja datos de otros negocios) implemente **2 webhooks de cumplimiento legal** para notificar eventos relacionados con la revocación de permisos y solicitudes de eliminación de datos:

1. **Deauthorize callback URL** — Meta te notifica cuando un usuario/negocio revoca los permisos concedidos a tu app.
2. **Data deletion request URL** — Meta te notifica cuando un usuario solicita formalmente eliminar sus datos.

Son requisitos de **GDPR / LGPD / políticas de protección de datos Meta**, NO son parte del flujo Embedded Signup ni del flujo de mensajes WhatsApp.

## Quién lo necesita

- ✅ **[[robert-bazan]] / [[lovbot-ai]]** — como Tech Provider que almacena datos de clientes (WABA IDs, phone_number_ids, conversaciones) está obligado.
- ❌ [[arnaldo-ayala]] (usa [[ycloud]], no es Tech Provider)
- ❌ [[micaela-colmenares]] (usa [[evolution-api]] self-hosted)

## Ubicación en el panel Meta

Panel: `developers.facebook.com/apps/{APP_ID}/fb-login/settings/`

Sección **"Cancelar autorización"** (al final de la página Facebook Login → Configuración):
- Campo: **URL de devolución de llamada de retirada de autorización** (deauthorize)
- Campo: **URL de la solicitud de eliminación de datos** (data_deletion)

## Arquitectura recomendada por Kevin

```
Meta App
   │
   │ POST signed_request
   ▼
n8n webhook (n8n.lovbot.ai/webhook/meta-deauthorize-XXXX)
   │
   │ forward signed_request a Cloudflare Worker
   ▼
Cloudflare Worker /verify
   │ (verifica HMAC SHA-256 con META_APP_SECRET)
   │
   ▼ respuesta {is_valid_signature, user_id, algorithm, issued_at}
   │
   ▼
n8n registra evento en data table "logs"
   │
   ▼
n8n envía email SMTP notificación (opcional)
```

**Por qué el Cloudflare Worker**: verificar `signed_request` HMAC requiere acceso al `META_APP_SECRET`. Meter eso en un nodo n8n expone el secret. Un Worker separado con secrets inyectados es más seguro y timing-safe.

## Endpoints sugeridos (patrón Kevin)

| Evento | URL sugerida | Propósito |
|---|---|---|
| Deauthorize | `https://n8n.tudominio.com/webhook/meta-deauthorize-{token}` | Recibir revocación de permisos |
| Data deletion | `https://n8n.tudominio.com/webhook/meta-data-deletion-{token}` | Recibir solicitud eliminación |
| Verify (interno) | `https://{worker}.workers.dev/verify` | Cloudflare Worker HMAC |

El `{token}` es un sufijo random para que no se adivine la URL externa.

## Cloudflare Worker — código verify

Código JS completo (fuente: Kevin):

```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/verify") return json({ ok: false, errorMessage: "Not Found" }, 404);
    if (request.method !== "POST") return json({ ok: false, errorMessage: "Method Not Allowed" }, 405);

    // Auth opcional interno
    const authHeader = request.headers.get("authorization") || "";
    if (env.INTERNAL_AUTH_TOKEN) {
      if (authHeader !== `Bearer ${env.INTERNAL_AUTH_TOKEN}`) {
        return json({ ok: false, errorMessage: "Unauthorized" }, 401);
      }
    }

    let body;
    try { body = await request.json(); } catch { return json({ ok: false, errorMessage: "Invalid JSON body" }, 400); }

    const signed_request = body?.signed_request;
    if (!signed_request) return json({ ok: false, errorMessage: "Missing signed_request" }, 400);

    const parts = signed_request.split(".");
    if (parts.length !== 2) return json({ ok: false, errorMessage: "Invalid signed_request format" }, 400);

    const [encodedSig, encodedPayload] = parts;
    const sigBytes = base64UrlToBytes(encodedSig);
    const payloadBytes = base64UrlToBytes(encodedPayload);

    let payload;
    try { payload = JSON.parse(new TextDecoder().decode(payloadBytes)); } catch { return json({ ok: false, errorMessage: "Payload is not valid JSON" }, 400); }

    if (!env.META_APP_SECRET) return json({ ok: false, errorMessage: "Server missing META_APP_SECRET" }, 500);

    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(env.META_APP_SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );

    const expectedSig = new Uint8Array(
      await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(encodedPayload))
    );

    const is_valid_signature = timingSafeEqual(sigBytes, expectedSig);

    return json({
      ok: true,
      is_valid_signature,
      algorithm: payload?.algorithm ?? null,
      issued_at: payload?.issued_at ?? null,
      user_id: payload?.user_id ?? null,
      decoded_payload: payload,
    });
  },
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function base64UrlToBytes(str) {
  str = str.replace(/-/g, "+").replace(/_/g, "/");
  const pad = str.length % 4;
  if (pad) str += "=".repeat(4 - pad);
  const bin = atob(str);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}
```

**Secrets Cloudflare Worker**:
- `META_APP_SECRET` — app secret de Meta (obligatorio)
- `INTERNAL_AUTH_TOKEN` — token para que solo n8n pueda llamar al worker (opcional pero recomendado)

## Plantillas n8n de Kevin (Drive)

- **Workflow deauthorize**: https://drive.google.com/file/d/1NgWyzlqgy8xJ6_wjtedXp0V0FdyNUtcc/view
- **Workflow data_deletion**: https://drive.google.com/file/d/11q5iBnlrywIvL-d8YoO__afuo8ig-m4g/view
- **CSV data table logs**: https://drive.google.com/file/d/156UemL2lfACJLj7WjfTHRz5a1qabIK7p/view

⚠️ Links son de Drive privado — hay que pedírselos a Kevin o descargarlos una vez para versionar localmente en `raw/robert/plantillas-kevin/`.

## Flujo de respuesta esperado por Meta

### Deauthorize
Meta envía `POST {deauth_url}` con body `signed_request=<HMAC.payload_base64url>`.

Response esperado: **HTTP 200** (Meta no exige body específico, pero tu app debe limpiar los datos del user que desautorizó).

### Data deletion
Meta envía `POST {deletion_url}` con body `signed_request=<HMAC.payload_base64url>`.

Response esperado: **HTTP 200** + JSON con formato:
```json
{
  "url": "https://tudominio.com/status-borrado?id=abc123",
  "confirmation_code": "abc123"
}
```
Meta usa `url` para que el user vea el status de su solicitud de borrado, y `confirmation_code` como identificador.

## Config verificada Lovbot (2026-04-20)

| Ítem | Estado |
|---|---|
| Webhook deauthorize en panel Meta | ❌ NO configurado |
| Webhook data_deletion en panel Meta | ❌ NO configurado |
| Cloudflare Worker /verify | ❌ NO creado |
| Workflows n8n compliance | ❌ NO existen |
| Data table "logs" en n8n | ❌ NO existe |

**Riesgo**: Meta puede pedir completarlo durante o después del App Review actual como condición de advanced access. GDPR/LGPD lo exigen a cualquier app que procese datos de residentes UE/Brasil.

## Decisión pragmática

Si el bot de Robert hoy **no procesa datos de residentes UE/Brasil** (solo LATAM no-Brasil), el riesgo legal directo es bajo, pero Meta igual puede pedirlo. Hacerlo después del review es OK; hacerlo antes reduce probabilidad de observaciones.

## ⚠️ Trampas comunes

- **No meter `META_APP_SECRET` en nodo n8n plano** — exponer secrets como variables en UI n8n es mala práctica. Usar Cloudflare Worker (o Functions de Vercel) con secrets gestionados.
- **HMAC se calcula sobre el STRING `encodedPayload`**, NO sobre el JSON decodificado. Trampa común de implementaciones custom.
- **Meta reintenta hasta 5 veces con backoff** si no recibe 200 — asegurate que n8n responda rápido aunque el worker esté lento.
- **`signed_request` viene con formato base64url**, no base64 estándar. Requiere decoder custom (está en el código del Worker arriba).

## Relaciones

- [[meta-tech-provider-onboarding]] — contexto general Tech Provider
- [[meta-graph-api]] — API principal para mensajes (distinta a estos webhooks compliance)
- [[n8n]] — donde viven los workflows que reciben los webhooks
- [[lovbot-ai]] — agencia que debe implementar esto
