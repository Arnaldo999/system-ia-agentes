# Evolution API — Webhook Parser & Send

Wrapper community sobre WhatsApp Web. Self-hosted (gratuito). Usado en producción para **Mica/System IA demo** y **Lau**.

## Configuración

```bash
# Variables de entorno requeridas
EVOLUTION_API_URL=https://evolution.lovbot.ai     # tu instancia self-hosted
EVOLUTION_API_KEY=tu_apikey_global                # apikey global de la instancia
EVOLUTION_INSTANCE=mica-demo                      # nombre de la instancia (1 por número)
```

## Setup de instancia

1. Levantar Docker (ver repo `EvolutionAPI/evolution-api`)
2. Crear instancia:
   ```bash
   curl -X POST "$EVOLUTION_API_URL/instance/create" \
     -H "apikey: $EVOLUTION_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"instanceName":"mica-demo","qrcode":true,"integration":"WHATSAPP-BAILEYS"}'
   ```
3. Escanear QR desde WhatsApp del cliente
4. Configurar webhook:
   ```bash
   curl -X POST "$EVOLUTION_API_URL/webhook/set/mica-demo" \
     -H "apikey: $EVOLUTION_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "url":"https://agentes.arnaldoayalaestratega.cloud/mica/demos/inmobiliaria/whatsapp",
       "webhook_by_events":false,
       "webhook_base64":false,
       "events":["MESSAGES_UPSERT"]
     }'
   ```

## POST — parser de eventos

```python
@router.post("/whatsapp")
async def webhook_evolution(request: Request):
    payload = await request.json()
    try:
        # Evolution manda event en uppercase: MESSAGES_UPSERT, no messages.upsert
        event = payload.get("event", "").lower().replace("_", ".")
        if event != "messages.upsert":
            return {"status": "ok", "info": f"event-ignored-{event}"}

        data = payload.get("data", {})
        key = data.get("key", {})

        # Filtrar mensajes propios (fromMe=True)
        if key.get("fromMe", False):
            return {"status": "ok", "info": "from-me-ignored"}

        # remoteJid: "5493765xxx@s.whatsapp.net" → solo el número
        remote_jid = key.get("remoteJid", "")
        telefono = re.sub(r'\D', '', remote_jid.split("@")[0])
        msg_id = key.get("id", "")

        # Filtrar grupos (terminan en @g.us)
        if "@g.us" in remote_jid:
            return {"status": "ok", "info": "group-ignored"}

        # Deduplicación
        with _MSG_DEDUP_LOCK:
            if msg_id in _MSG_PROCESADOS:
                return {"status": "ok", "info": "duplicate"}
            _MSG_PROCESADOS.add(msg_id)
            if len(_MSG_PROCESADOS) > 1000:
                _MSG_PROCESADOS.clear()

        # Extraer texto según tipo de mensaje
        message = data.get("message", {})
        message_type = data.get("messageType", "")
        texto = ""

        if "conversation" in message:
            texto = message["conversation"]
        elif "extendedTextMessage" in message:
            texto = message["extendedTextMessage"].get("text", "")
        elif "audioMessage" in message:
            # Audio viene en base64 inline
            audio_b64 = message["audioMessage"].get("base64", "")
            if audio_b64:
                texto = _transcribir_audio_b64(audio_b64)  # Whisper
            else:
                # O puede venir media_id → fetch
                media_url = message["audioMessage"].get("url", "")
                texto = _transcribir_audio_url(media_url) if media_url else "[audio sin contenido]"
        elif "imageMessage" in message:
            texto = message["imageMessage"].get("caption", "") or "[imagen recibida]"
        elif "buttonsResponseMessage" in message:
            texto = message["buttonsResponseMessage"].get("selectedDisplayText", "")
        elif "listResponseMessage" in message:
            texto = message["listResponseMessage"].get("title", "")

        if not texto:
            return {"status": "ok", "info": f"unsupported-{message_type}"}

        # Nombre del perfil (puede venir vacío)
        nombre_evo = data.get("pushName", "").strip()
        if not nombre_evo:
            nombre_evo = telefono  # fallback

        if nombre_evo and telefono not in SESIONES:
            SESIONES[telefono] = {"nombre": nombre_evo.title(), "_ultimo_ts": time.time()}

        # Evolution NO tiene referral (no soporta Click-to-WhatsApp Ads)
        referral = {}

        threading.Thread(
            target=_procesar,
            args=(telefono, texto, referral),
            daemon=True
        ).start()

        return {"status": "processing"}
    except Exception as e:
        print(f"[EVOLUTION] Error: {e}")
        return {"status": "error", "detail": str(e)}
```

## Envío de mensajes

```python
def _enviar_texto_evo(telefono: str, texto: str) -> bool:
    """Envía texto vía Evolution API."""
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    r = requests.post(url,
        headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
        json={
            "number": telefono,
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": texto}
        },
        timeout=10)
    if r.status_code not in (200, 201):
        print(f"[EVOLUTION] sendText error {r.status_code}: {r.text[:200]}")
    return r.status_code in (200, 201)


def _enviar_imagen_evo(telefono: str, url_img: str, caption: str = "") -> bool:
    """Envía imagen vía Evolution API."""
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    r = requests.post(url,
        headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
        json={
            "number": telefono,
            "options": {"delay": 1200, "presence": "composing"},
            "mediaMessage": {
                "mediatype": "image",
                "media": url_img,
                "caption": caption[:1024]
            }
        },
        timeout=15)
    return r.status_code in (200, 201)


def _enviar_audio_evo(telefono: str, audio_url: str) -> bool:
    """Envía audio vía Evolution API."""
    url = f"{EVOLUTION_API_URL}/message/sendWhatsAppAudio/{EVOLUTION_INSTANCE}"
    r = requests.post(url,
        headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
        json={
            "number": telefono,
            "audioMessage": {"audio": audio_url}
        },
        timeout=15)
    return r.status_code in (200, 201)
```

## Particularidades de Evolution

### 1. **Event names en uppercase**
Evolution manda `MESSAGES_UPSERT` en lugar de `messages.upsert`. Comparar siempre case-insensitive:
```python
if payload.get("event", "").lower().replace("_", ".") == "messages.upsert":
    ...
```

### 2. **No soporta referral / Click-to-WhatsApp Ads**
Si el cliente quiere recibir leads de Meta Ads, debe usar Meta Graph API o YCloud.

### 3. **Audio en base64 inline**
A diferencia de Meta (que da `media_id` y hay que fetchear URL), Evolution puede mandar audio como base64 directamente.

### 4. **WhatsApp Web frágil**
- Bans esporádicos de WhatsApp si detecta uso automatizado abusivo
- QR puede expirar y hay que reescanear
- Fix: implementar endpoint `/admin/check-instance/{name}` para monitorear y alertar

### 5. **Bot pause con Chatwoot**
Evolution puede enviar y recibir desde Chatwoot. Cuando un agente humano toma la conversación, marcar `bot_pausado(telefono)` para que el bot no responda.

## Endpoint de check de instancia

```python
@router.get("/admin/evolution-status")
def evolution_status():
    """Verifica que la instancia esté conectada."""
    r = requests.get(
        f"{EVOLUTION_API_URL}/instance/connectionState/{EVOLUTION_INSTANCE}",
        headers={"apikey": EVOLUTION_API_KEY},
        timeout=5
    )
    if r.status_code != 200:
        return {"status": "error", "code": r.status_code}
    state = r.json().get("instance", {}).get("state", "unknown")
    return {"status": state, "instance": EVOLUTION_INSTANCE}
```

## Endpoint de simulación (testing)

```python
@router.post("/admin/simular-mensaje-evo/{telefono}")
async def simular_mensaje_evo(telefono: str, request: Request):
    """Simula mensaje entrante (sin necesitar Evolution real)."""
    tel = re.sub(r'\D', '', telefono)
    body = await request.json()
    texto = body.get("texto", "Hola")

    if telefono not in SESIONES and body.get("nombre"):
        SESIONES[tel] = {"nombre": body["nombre"], "_ultimo_ts": time.time()}

    threading.Thread(target=_procesar, args=(tel, texto, {}), daemon=True).start()
    return {"status": "processing", "telefono": tel, "texto": texto}
```

## Cliente actual: Mica/System IA

- Backend: `agentes.arnaldoayalaestratega.cloud` (Coolify Hostinger)
- Worker: `workers/demos/inmobiliaria/worker.py` (es la base, también Mica usa este)
- Instancia Evolution: `mica-demo`
- Número: `5493765005465`
- Webhook: `https://agentes.arnaldoayalaestratega.cloud/mica/demos/inmobiliaria/whatsapp`
