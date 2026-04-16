# Proveedor de WhatsApp — Cómo elegir

Tabla comparativa de los 3 proveedores usados en producción del ecosistema Arnaldo / Lovbot / System IA, más guía de selección por caso de uso.

## Tabla comparativa

| Característica | Meta Graph API | Evolution API | YCloud |
|---|---|---|---|
| **Tipo** | API oficial WhatsApp Business | Wrapper community sobre WhatsApp Web | Provider BSP comercial sobre WhatsApp Business API |
| **Costo** | Por conversación (~$0.005-0.05 USD) | Self-hosted (gratis) | Por mensaje (~$0.003-0.02 USD) |
| **Setup** | Verificación Meta Business + número | Solo levantar Docker + escanear QR | Crear cuenta YCloud + plantear número |
| **Templates HSM** | Obligatorios para iniciar conversación | No requiere | Soporta plantillas y conversaciones libres |
| **Click-to-WhatsApp Ads (referral)** | ✅ Soportado | ❌ No | ✅ Soportado |
| **Lead Ads forms (nombre + email)** | ✅ Pre-loaded en `contacts.profile` | ❌ No | ✅ Pre-loaded |
| **Botones interactivos** | ✅ button + interactive (list/button_reply) | ⚠️ Soportado pero limitado | ⚠️ Soportado en plantillas |
| **Audio** | ✅ Whisper transcription | ✅ Whisper transcription | ✅ Whisper transcription |
| **Webhook events** | `messages` único endpoint | `MESSAGES_UPSERT` (uppercase!) | `whatsapp.message.received` |
| **Verificación handshake** | GET con `hub.challenge` | No requiere | No requiere |
| **Bot pause** | Manual via flags | Manual via flags | Manual via flags |
| **Estabilidad WhatsApp Web** | N/A (es API oficial) | ⚠️ Frágil — bans esporádicos | N/A (oficial) |
| **Cliente actual** | Robert/Lovbot, Robert prueba | Mica/System IA (Lau, demo) | Arnaldo/Maicol, Arnaldo prueba |
| **Integración Meta Ads** | Nativa | No | Nativa |
| **Audio recibido** | media_id → fetch URL → download | base64 inline o URL | media_id → fetch URL |
| **Imagen enviada** | URL pública o media_id | base64 o URL | URL pública o media_id |

## Cuándo elegir cada uno

### Meta Graph API → elegir si:
- Cliente tiene volumen alto y necesita **plantillas HSM** para iniciar
- Vienen leads desde **Click-to-WhatsApp Ads** o **Lead Ads forms** de Meta
- Cliente puede pagar la verificación oficial WhatsApp Business
- Necesita **botones interactivos** confiables (Lista, Quick Replies)
- Usado en: **Robert/Lovbot**, **Robert prueba bot**

### Evolution API → elegir si:
- Cliente quiere **costo cero** (self-hosted, ya tenemos VPS)
- Volumen bajo a moderado (< 1000 mensajes/día)
- No necesita iniciar conversaciones desde el bot (solo responde)
- Está dispuesto a aceptar el riesgo de WhatsApp Web (ban esporádico)
- Usado en: **Mica/System IA demo**, **Lau/System IA**, **demos genéricas**

### YCloud → elegir si:
- Cliente quiere API oficial pero **sin verificación Meta Business directa**
- Volumen medio
- Vienen leads de **Meta Ads forwards** (YCloud los reenvía)
- Documentación más simple que Meta Graph
- Usado en: **Arnaldo/Maicol** (Back Urbanizaciones, live)

## Estructura de payload comparada

### Meta Graph (POST `/whatsapp`)
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "...",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "...", "phone_number_id": "..."},
        "contacts": [{"profile": {"name": "..."}, "wa_id": "..."}],
        "messages": [{
          "from": "...", "id": "wamid.xxx", "timestamp": "...",
          "type": "text", "text": {"body": "..."},
          "referral": {"headline": "...", "body": "...", "source_url": "..."}
        }]
      },
      "field": "messages"
    }]
  }]
}
```

### Evolution API (POST `/whatsapp` o el webhook configurado)
```json
{
  "event": "messages.upsert",
  "instance": "mica-demo",
  "data": {
    "key": {"remoteJid": "5493765xxx@s.whatsapp.net", "fromMe": false, "id": "..."},
    "pushName": "Arnaldo",
    "message": {"conversation": "Hola, hay propiedades?"},
    "messageType": "conversation",
    "messageTimestamp": 1713320000
  },
  "destination": "https://agentes.arnaldoayalaestratega.cloud/...",
  "date_time": "2026-04-16T17:30:00.000Z",
  "sender": "5493765xxx",
  "server_url": "https://evolution.lovbot.ai",
  "apikey": "..."
}
```

### YCloud (POST webhook)
```json
{
  "id": "evt_xxx",
  "type": "whatsapp.message.received",
  "created_time": "2026-04-16T17:30:00Z",
  "whatsappMessage": {
    "id": "wamid.xxx",
    "wabaId": "...",
    "phoneNumberId": "...",
    "from": "5493765xxx",
    "to": "...",
    "type": "text",
    "text": {"body": "Hola"},
    "contact": {"profile": {"name": "Arnaldo"}},
    "context": {"id": "...", "from": "..."},
    "referral": {"sourceUrl": "...", "headline": "...", "body": "..."}
  }
}
```

## Capa de abstracción común

Independiente del proveedor, el worker normaliza a este formato interno:

```python
# Estructura interna estándar
mensaje_normalizado = {
    "telefono": "5493765xxx",         # Sin + ni @s.whatsapp.net
    "msg_id": "unique-id",            # Para deduplicación
    "tipo": "text",                   # text|audio|image|button|interactive
    "texto": "Hola, hay propiedades?", # Texto extraído (audio→transcripción)
    "nombre_perfil": "Arnaldo",       # De contacts/profile/pushName
    "referral": {                     # Solo Meta y YCloud
        "headline": "...",
        "body": "...",
        "source_url": "...",
    },
    "lead_form": {                    # Solo Meta Lead Ads
        "nombre": "...",
        "email": "...",
    },
    "timestamp": 1713320000,
}
```

Cada `providers/{nombre}.md` documenta cómo extraer estos campos del payload nativo del proveedor.

## Patrón recomendado en código

```python
# main.py — un endpoint por proveedor, todos llaman al mismo _procesar()
from workers.clientes.lovbot.robert_inmobiliaria.worker import _procesar as procesar_robert

@app.post("/clientes/lovbot/inmobiliaria/whatsapp")  # Meta
async def webhook_meta_robert(request: Request):
    payload = await request.json()
    msg = parse_meta_payload(payload)  # → mensaje_normalizado
    if msg:
        threading.Thread(target=procesar_robert, args=(msg["telefono"], msg["texto"], msg["referral"]), daemon=True).start()
    return {"status": "ok"}

@app.post("/mica/demos/inmobiliaria/whatsapp")  # Evolution
async def webhook_evolution_mica(request: Request):
    payload = await request.json()
    msg = parse_evolution_payload(payload)  # → mensaje_normalizado
    if msg:
        threading.Thread(target=procesar_mica, args=(msg["telefono"], msg["texto"], msg["referral"]), daemon=True).start()
    return {"status": "ok"}

@app.post("/clientes/arnaldo/maicol/whatsapp")  # YCloud
async def webhook_ycloud_maicol(request: Request):
    payload = await request.json()
    msg = parse_ycloud_payload(payload)  # → mensaje_normalizado
    if msg:
        threading.Thread(target=procesar_maicol, args=(msg["telefono"], msg["texto"], msg["referral"]), daemon=True).start()
    return {"status": "ok"}
```

## Bugs conocidos por proveedor

| Proveedor | Bug | Workaround |
|---|---|---|
| Meta | Webhook URL apuntando a workflow viejo n8n | Verificar URL en Meta Business → WhatsApp → Configuration |
| Meta | Falta GET handshake → webhook no se puede configurar | Agregar GET endpoint con `hub.verify_token` |
| Meta | Click-to-WhatsApp dispara doble webhook | Deduplicación por `msg_id` con set + lock |
| Evolution | `MESSAGES_UPSERT` viene en uppercase, no `messages.upsert` | Comparar case-insensitive: `event.lower() == "messages.upsert"` |
| Evolution | WhatsApp Web no dispara webhook esporádicamente | Reescanear QR + restart Docker container |
| Evolution | `pushName` puede venir vacío → usar `sender` como fallback | `nombre = data.pushName or sender.split("@")[0]` |
| YCloud | CTA buttons del bot no funcionan | Usar texto plano con instrucciones tipo "responde 1 / 2" |
| YCloud | Reintentos masivos en error → costo extra | Implementar deduplicación por `id` + responder 200 rápido |
| YCloud | API v1 deprecada → migrar a v2 | Usar `https://api.ycloud.com/v2/whatsapp/messages` |
