# Meta Graph API Webhook Parser

Parser completo de payloads de Meta Graph API para WhatsApp Business. Cubre Click-to-WhatsApp Ads (referral), Lead Ads forms (form data), y todos los tipos de mensaje (text, audio, button, interactive).

## Endpoints requeridos

```python
@router.get("/whatsapp")  # GET handshake de verificación Meta
@router.post("/whatsapp") # POST para eventos
```

**CRÍTICO**: ambos en la misma URL. Meta hace GET primero, después POST. Si falta el GET, Meta no permite configurar el webhook.

## GET — verificación handshake

```python
from fastapi import Query
from fastapi.responses import PlainTextResponse

VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")

@router.get("/whatsapp")
async def verificar_webhook_meta(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("forbidden", status_code=403)
```

## POST — parser de eventos

```python
@router.post("/whatsapp")
async def webhook_whatsapp(request: Request):
    payload = await request.json()
    try:
        entry = payload.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok", "info": "no-messages"}

        msg = messages[0]
        telefono = re.sub(r'\D', '', msg.get("from", ""))
        msg_id = msg.get("id", "")

        # ── Deduplicación (Meta reintenta hasta 5 veces) ──
        with _META_DEDUP_LOCK:
            if msg_id in _META_MSG_IDS_PROCESADOS:
                return {"status": "ok", "info": "duplicate"}
            _META_MSG_IDS_PROCESADOS.add(msg_id)
            if len(_META_MSG_IDS_PROCESADOS) > 1000:
                _META_MSG_IDS_PROCESADOS.clear()

        # ── Extraer texto según tipo ──
        tipo = msg.get("type", "")
        texto = ""
        if tipo == "text":
            texto = msg.get("text", {}).get("body", "")
        elif tipo == "button":
            texto = msg.get("button", {}).get("text", "")
        elif tipo == "interactive":
            inter = msg.get("interactive", {})
            if inter.get("type") == "button_reply":
                texto = inter.get("button_reply", {}).get("title", "")
            elif inter.get("type") == "list_reply":
                texto = inter.get("list_reply", {}).get("title", "")
        elif tipo == "audio":
            media_id = msg.get("audio", {}).get("id", "")
            texto = _transcribir_audio_meta(media_id)  # Whisper
        elif tipo == "image":
            texto = msg.get("image", {}).get("caption", "") or "[imagen recibida]"

        if not texto:
            return {"status": "ok", "info": f"unsupported-type-{tipo}"}

        # ── Extraer referral (Click-to-WhatsApp Ad) ──
        referral = msg.get("referral", {})
        # Estructura referral:
        # {
        #   "source_url": "https://fb.com/...",
        #   "source_id": "ad_id",
        #   "source_type": "ad",
        #   "headline": "Título del ad",
        #   "body": "Cuerpo del ad",
        #   "media_type": "image",
        #   "image_url": "...",
        #   "ctwa_clid": "..."  ← Click ID único
        # }

        # ── Extraer datos de Lead Ads form (si existe contacts) ──
        contacts = value.get("contacts", [{}])
        nombre_meta = ""
        if contacts and isinstance(contacts, list):
            nombre_meta = contacts[0].get("profile", {}).get("name", "").strip()

        # ── Pre-cargar nombre si es lead nuevo ──
        if nombre_meta and telefono not in SESIONES:
            SESIONES[telefono] = {"nombre": nombre_meta.title(), "_ultimo_ts": time.time()}

        # ── Procesar en background (no bloquear webhook) ──
        threading.Thread(
            target=_procesar,
            args=(telefono, texto, referral),
            daemon=True
        ).start()

        return {"status": "processing"}
    except Exception as e:
        print(f"[WEBHOOK] Error parseando payload: {e}")
        return {"status": "error", "detail": str(e)}
```

## Sesión inicial desde referral

En `_procesar()`, cuando es lead nuevo desde un Ad:

```python
if referral and telefono not in SESIONES:
    fuente_det = (
        f"ad:{referral.get('source_id','')}|{referral.get('headline','')[:50]}"
        if referral.get("source_id")
        else f"referral:{referral.get('source_url','')[:80]}"
    )
    SESIONES[telefono] = {
        "step": "inicio",
        "subniche": "agencia_inmobiliaria",  # o el tipo que aplique
        "_referral": referral,
        "_fuente_detalle": fuente_det,
        "_ultimo_ts": time.time(),
    }
```

## Endpoint de simulación (para tests sin Meta real)

```python
@router.post("/admin/simular-lead-anuncio/{telefono}")
async def simular_lead_anuncio(telefono: str, request: Request):
    """Simula un lead llegando desde un anuncio Meta Ads (testing Caso A)."""
    tel = re.sub(r'\D', '', telefono)
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    referral = {
        "headline": body.get("headline", "Casa 3 dorm en San Ignacio - USD 145k"),
        "body": body.get("body", "Hermosa casa con piscina"),
        "source_url": body.get("source_url", "fb.com/ad/123"),
    }

    # Pre-cargar datos de Lead Ads form si vienen
    nombre_ads = body.get("nombre", "").strip()
    email_ads = body.get("email", "").strip()
    if nombre_ads or email_ads:
        sesion_pre = SESIONES.get(tel, {})
        if nombre_ads: sesion_pre["nombre"] = nombre_ads.title()
        if email_ads: sesion_pre["email"] = email_ads
        sesion_pre["origen_lead"] = "meta_ads_form"
        SESIONES[tel] = sesion_pre

    primer_mensaje = body.get("mensaje", "Hola, me interesa la propiedad que vi")
    threading.Thread(target=_procesar, args=(tel, primer_mensaje, referral), daemon=True).start()
    return {"status": "processing", "telefono": tel, "referral": referral, "mensaje": primer_mensaje}
```

## Bug histórico — Webhook URL incorrecta

Si el bot responde "Soy tu agente Lovbot, programar cita" (mensaje desconocido), es probable que el webhook de Meta esté apuntando a un workflow viejo de n8n con UUID inexistente.

**Fix**: en Meta Developer → WhatsApp → Configuration → Webhook callback URL debe ser:
- Robert: `https://agentes.lovbot.ai/clientes/lovbot/inmobiliaria/whatsapp`
- Mica: `https://agentes.arnaldoayalaestratega.cloud/mica/demos/inmobiliaria/whatsapp`
- Maicol: `https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/whatsapp`

## Variables de entorno requeridas

```bash
META_ACCESS_TOKEN=EAAxxxxxx           # System User token permanente
META_PHONE_NUMBER_ID=123456789012345  # Phone ID del número de WhatsApp
META_VERIFY_TOKEN=mi_token_secreto    # Para handshake GET
LOVBOT_OPENAI_API_KEY=sk-xxx          # Para Whisper (audio transcription)
```

## Envío de mensajes

```python
def _enviar_texto(telefono: str, texto: str) -> bool:
    if not META_ACCESS_TOKEN or not META_PHONE_ID:
        print(f"[META] Credenciales faltantes")
        return False
    url = f"https://graph.facebook.com/v18.0/{META_PHONE_ID}/messages"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "text",
            "text": {"body": texto}
        },
        timeout=10)
    return r.status_code == 200


def _enviar_imagen(telefono: str, url_img: str, caption: str = "") -> bool:
    url = f"https://graph.facebook.com/v18.0/{META_PHONE_ID}/messages"
    r = requests.post(url,
        headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": telefono,
            "type": "image",
            "image": {"link": url_img, "caption": caption[:1024]}
        },
        timeout=10)
    return r.status_code == 200
```
