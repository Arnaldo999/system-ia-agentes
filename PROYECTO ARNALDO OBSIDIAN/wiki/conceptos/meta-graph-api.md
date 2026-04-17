---
title: "Meta Graph API (WhatsApp Business)"
tags: [whatsapp-provider, meta, waba, robert]
source_count: 0
proyectos_aplicables: [robert]
---

# Meta Graph API

## Definición

API oficial de Meta para WhatsApp Business Platform. Requiere ser **Tech Provider** (verificado por Meta) o cliente de uno. Permite enviar/recibir mensajes directamente, sin intermediarios como YCloud o Evolution.

## Quién la usa

- ✅ [[robert-bazan]] — Robert **es Tech Provider verificado de Meta**, con WABA propia. Número del bot: `+52 1 998 743 4234`.
- ❌ [[arnaldo-ayala]] → usa [[ycloud]] (no es Tech Provider).
- ❌ [[micaela-colmenares]] → usa [[evolution-api]] self-hosted.

## Env vars (solo en worker de Robert)

- `META_ACCESS_TOKEN` — token de la app de Meta
- `META_PHONE_NUMBER_ID` — ID del número del bot
- `META_WABA_ID` — ID del WABA de Robert
- `META_VERIFY_TOKEN` — para verificar el webhook

## Endpoints principales

- Recibir mensajes: webhook configurado en `agentes.lovbot.ai/meta/webhook`
- Enviar mensajes: POST `graph.facebook.com/v19.0/{phone_number_id}/messages`

## ⚠️ Trampas comunes

- El webhook **solo dispara con Graph API**, no desde WhatsApp Web. Probar desde el WhatsApp oficial del usuario final.
- Los audios vienen con mime `audio/ogg; codecs=opus` — transcribir con Whisper requiere conversión.

## 🚫 No usar en otros proyectos

- Mica usa [[evolution-api]] → NO mezclar endpoints Meta Graph en código de Mica.
- Arnaldo usa [[ycloud]] → idem.

## Fuentes que lo mencionan

_Pendiente ingestar: `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/guia-tech-provider-meta-robert.html` y `embedded-signup.html`._
