# YCloud API — Webhook Parser & Send

Provider BSP comercial sobre WhatsApp Business API oficial. Más simple que Meta Graph directo. Usado en producción para **Arnaldo/Maicol** (Back Urbanizaciones, live) y **Arnaldo prueba bot**.

## Configuración

```bash
# Variables de entorno requeridas
YCLOUD_API_KEY=sk_live_xxx                     # API key de YCloud
YCLOUD_WEBHOOK_SECRET=whsec_xxx                # Para validar firma
YCLOUD_PHONE_NUMBER=5493764815689              # Número de WhatsApp del cliente
```

## Setup

1. Crear cuenta en [ycloud.com](https://ycloud.com) (o panel que use la agencia)
2. Plantear número WhatsApp (verificación similar a Meta)
3. Configurar webhook:
   - URL: `https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/whatsapp`
   - Events: `whatsapp.message.received`, `whatsapp.message.updated`
4. Copiar API key y webhook secret a env vars

## POST — parser de eventos

```python
@router.post("/whatsapp")
async def webhook_ycloud(request: Request):
    payload = await request.json()
    try:
        event_type = payload.get("type", "")
        if event_type != "whatsapp.message.received":
            return {"status": "ok", "info": f"event-ignored-{event_type}"}

        msg = payload.get("whatsappMessage", {})
        msg_id = msg.get("id", "")
        telefono = re.sub(r'\D', '', msg.get("from", ""))

        # Deduplicación (YCloud hace muchos retries)
        with _MSG_DEDUP_LOCK:
            if msg_id in _MSG_PROCESADOS:
                return {"status": "ok", "info": "duplicate"}
            _MSG_PROCESADOS.add(msg_id)
            if len(_MSG_PROCESADOS) > 1000:
                _MSG_PROCESADOS.clear()

        # Extraer texto según tipo
        tipo = msg.get("type", "")
        texto = ""

        if tipo == "text":
            texto = msg.get("text", {}).get("body", "")
        elif tipo == "audio":
            # YCloud devuelve URL del media directamente
            media_url = msg.get("audio", {}).get("link", "")
            texto = _transcribir_audio_url(media_url) if media_url else "[audio]"
        elif tipo == "image":
            texto = msg.get("image", {}).get("caption", "") or "[imagen recibida]"
        elif tipo == "button":
            texto = msg.get("button", {}).get("text", "")
        elif tipo == "interactive":
            inter = msg.get("interactive", {})
            if inter.get("type") == "button_reply":
                texto = inter.get("button_reply", {}).get("title", "")
            elif inter.get("type") == "list_reply":
                texto = inter.get("list_reply", {}).get("title", "")

        if not texto:
            return {"status": "ok", "info": f"unsupported-{tipo}"}

        # Extraer referral (Click-to-WhatsApp Ads) — YCloud lo soporta
        referral = msg.get("referral", {})
        # Estructura YCloud:
        # {
        #   "sourceUrl": "...",
        #   "sourceType": "ad",
        #   "sourceId": "...",
        #   "headline": "...",
        #   "body": "...",
        #   "mediaType": "image",
        #   "imageUrl": "...",
        #   "ctwaClid": "..."
        # }
        # Normalizar a nuestro formato interno (source_url en snake_case)
        referral_normalized = {
            "headline": referral.get("headline", ""),
            "body": referral.get("body", ""),
            "source_url": referral.get("sourceUrl", ""),
            "source_id": referral.get("sourceId", ""),
            "ctwa_clid": referral.get("ctwaClid", ""),
        } if referral else {}

        # Nombre del perfil
        contact = msg.get("contact", {})
        nombre_yc = contact.get("profile", {}).get("name", "").strip()

        if nombre_yc and telefono not in SESIONES:
            SESIONES[telefono] = {"nombre": nombre_yc.title(), "_ultimo_ts": time.time()}

        threading.Thread(
            target=_procesar,
            args=(telefono, texto, referral_normalized),
            daemon=True
        ).start()

        return {"status": "processing"}
    except Exception as e:
        print(f"[YCLOUD] Error: {e}")
        return {"status": "error", "detail": str(e)}
```

## Envío de mensajes

```python
def _enviar_texto_ycloud(telefono: str, texto: str) -> bool:
    """Envía texto vía YCloud v2."""
    url = "https://api.ycloud.com/v2/whatsapp/messages"
    r = requests.post(url,
        headers={"X-API-Key": YCLOUD_API_KEY, "Content-Type": "application/json"},
        json={
            "from": YCLOUD_PHONE_NUMBER,
            "to": telefono,
            "type": "text",
            "text": {"body": texto}
        },
        timeout=10)
    if r.status_code not in (200, 201):
        print(f"[YCLOUD] Error {r.status_code}: {r.text[:200]}")
    return r.status_code in (200, 201)


def _enviar_imagen_ycloud(telefono: str, url_img: str, caption: str = "") -> bool:
    """Envía imagen vía YCloud."""
    url = "https://api.ycloud.com/v2/whatsapp/messages"
    r = requests.post(url,
        headers={"X-API-Key": YCLOUD_API_KEY, "Content-Type": "application/json"},
        json={
            "from": YCLOUD_PHONE_NUMBER,
            "to": telefono,
            "type": "image",
            "image": {"link": url_img, "caption": caption[:1024]}
        },
        timeout=15)
    return r.status_code in (200, 201)


def _enviar_template_ycloud(telefono: str, template_name: str, lang: str = "es_AR",
                              components: list = None) -> bool:
    """Envía plantilla HSM vía YCloud (para iniciar conversación)."""
    url = "https://api.ycloud.com/v2/whatsapp/messages"
    r = requests.post(url,
        headers={"X-API-Key": YCLOUD_API_KEY, "Content-Type": "application/json"},
        json={
            "from": YCLOUD_PHONE_NUMBER,
            "to": telefono,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": lang},
                "components": components or []
            }
        },
        timeout=10)
    return r.status_code in (200, 201)
```

## Particularidades de YCloud

### 1. **API v1 deprecada → siempre v2**
URL correcta: `https://api.ycloud.com/v2/whatsapp/messages`

### 2. **Header de auth es `X-API-Key`** (no `Authorization: Bearer`)

### 3. **Reintentos agresivos en error**
Si el webhook no responde 200 rápido, YCloud reintenta hasta 10 veces. Esto puede generar costo extra en mensajes o procesamiento duplicado.

Fix: responder `{"status": "processing"}` con 200 inmediatamente y hacer el procesamiento real en un thread background.

### 4. **Soporte Click-to-WhatsApp Ads**
YCloud propaga el `referral` de Meta Ads en el payload igual que Meta Graph, pero usa camelCase (`sourceUrl`, `sourceId`, `ctwaClid`) en lugar de snake_case. Normalizar siempre.

### 5. **CTA Buttons de templates no funcionan** (bug conocido)
De la memoria del proyecto: los botones CTA en plantillas YCloud no se renderizan bien en todos los clientes de WhatsApp. Usar texto plano con instrucciones ("responde 1 para X") como fallback.

### 6. **Para iniciar conversación → obligatorio plantilla HSM**
Si el cliente no escribió en > 24h, hay que usar `_enviar_template_ycloud()`. Las plantillas deben estar aprobadas previamente en el panel de YCloud.

## Validación de firma del webhook (opcional)

```python
import hmac, hashlib

def _verificar_firma_ycloud(request_body: bytes, signature_header: str) -> bool:
    """YCloud firma los webhooks con HMAC-SHA256."""
    expected = hmac.new(
        YCLOUD_WEBHOOK_SECRET.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.post("/whatsapp")
async def webhook_ycloud(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-YCloud-Signature", "")
    if YCLOUD_WEBHOOK_SECRET and not _verificar_firma_ycloud(raw_body, signature):
        return {"status": "error", "detail": "invalid-signature"}
    # ... resto del parser
```

## Cliente actual: Arnaldo/Maicol (Back Urbanizaciones)

- Backend: `agentes.arnaldoayalaestratega.cloud` (Coolify Hostinger)
- Worker: `workers/clientes/arnaldo/maicol/worker.py`
- Número: `5493764815689`
- Webhook: `https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/whatsapp`
- Integración con Airtable (Leads, Propiedades, Clientes Activos)
- CRM en `crm.backurbanizaciones.com`
- Live desde 2026-04-06 con datos reales
