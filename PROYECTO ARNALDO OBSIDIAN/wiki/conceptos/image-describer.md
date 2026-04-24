---
proyecto: compartido
tipo: concepto
created: 2026-04-23
tags: [workers, whatsapp, vision, openai, gpt-4o-mini, imagen, normalizador]
---

# Image Describer — normalizador de imágenes WhatsApp a texto

## Qué es

Módulo compartido `workers/shared/image_describer.py` que convierte imágenes entrantes de WhatsApp (plano, ficha, foto de propiedad) a descripciones textuales usando GPT-4o-mini Vision. El texto resultante se concatena al mensaje del usuario ANTES del buffer y del LLM conversacional.

## Por qué existe

Sin describer, cuando un lead manda una foto, el LLM solo ve el caption (muchas veces vacío) y responde genérico. Con describer, el LLM recibe contexto visual completo:

**Antes:**
- Usuario: [foto plano de loteo] + caption "¿cuánto sale?"
- LLM ve: "¿cuánto sale?" → responde "¿cuánto sale qué?"

**Después:**
- Usuario: [foto plano de loteo] + caption "¿cuánto sale?"
- LLM ve: "[Imagen: plano de loteo con 12 parcelas numeradas zona norte, frente urbano] ¿cuánto sale?"
- LLM responde contextual.

## Flujo técnico

1. Webhook recibe mensaje tipo `image`
2. Worker detecta provider (Meta Graph vs Evolution)
3. Worker descarga bytes usando el helper correcto del módulo:
   - **Meta**: `download_media_meta(media_id, META_ACCESS_TOKEN)` — usa `graph.facebook.com/v21.0/{id}` para obtener URL + descarga con bearer token
   - **Evolution**: `download_media_evolution(message_id, url, instance, key)` — usa endpoint `/chat/getBase64FromMediaMessage/{instance}` que **descifra internamente** el media de WhatsApp (URLs directas no sirven, vienen encriptadas)
4. `describe_image(bytes, mime)` valida que sean bytes de imagen real (magic numbers), sanitiza mime si es genérico, llama a OpenAI Vision
5. Devuelve descripción string ≤80 palabras o `""` si falla

## Formatos soportados

OpenAI Vision acepta solo: **JPEG, PNG, GIF, WEBP**.

El módulo incluye:
- `_detect_mime_from_bytes()` — inspecciona magic numbers (FF D8 FF para JPEG, 89 50 4E 47 para PNG, GIF 47 49 46, RIFF...WEBP)
- `_sanitize_mime()` — si el mime declarado no está en la lista permitida, detecta el real por bytes
- `_looks_like_image()` — guard antes de llamar OpenAI. Si los bytes no son imagen, log de diagnóstico (tamaño + hex prefix) y no gasta tokens

## Configuración

Env vars:
- `OPENAI_API_KEY` — requerida
- `IMAGE_DESCRIBER_ENABLED` (default true) — feature flag para bypass
- `IMAGE_DESCRIBER_MODEL` (default `gpt-4o-mini`)
- Para Evolution: `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, + instance específica del tenant (ej `MICA_DEMO_EVOLUTION_INSTANCE`)
- Para Meta: `META_ACCESS_TOKEN`

## Costo

gpt-4o-mini Vision ≈ **$0.00015 por imagen pequeña**. Despreciable.

Latencia agregada: ~2-3s por imagen (descarga + llamada OpenAI).

## Failure modes

- `OPENAI_API_KEY` faltante → return `""`, log warning
- Bytes vacíos o no-imagen → return `""`, log con size + hex_prefix para diagnóstico
- Timeout (15s) → return `""`
- OpenAI HTTP error → return `""`, log body del error
- Import falla → worker con flag `_IMAGE_DESCRIBER_OK = False` usa comportamiento pre-feature

Todos los failure modes devuelven string vacío — **nunca levanta excepción**. El worker trata `""` como "no hay descripción" y sigue con su fallback (caption crudo o "[imagen recibida]").

## Uso en worker

```python
from workers.shared.image_describer import describe_image, download_media_meta

def _describir_imagen_meta(media_id: str) -> str:
    if not META_ACCESS_TOKEN:
        return ""
    bytes_img, mime = download_media_meta(media_id, META_ACCESS_TOKEN)
    if not bytes_img:
        return ""
    descripcion = describe_image(bytes_img, mime=mime)
    return f"[Imagen: {descripcion}]" if descripcion else ""

# En webhook:
if msg_type == "image":
    media_id = msg["image"]["id"]
    caption = msg["image"].get("caption", "")
    descripcion = _describir_imagen_meta(media_id)
    if descripcion and caption:
        texto = f"{descripcion} {caption}"
    elif descripcion:
        texto = descripcion
    else:
        texto = caption or "[imagen recibida]"
```

## Bug histórico — mime no-imagen desde Evolution

2026-04-23: Evolution devolvía `Content-Type: application/octet-stream` al descargar media por URL directa. OpenAI rechazaba con HTTP 400. Causa real detectada después: **las URLs de imageMessage en Evolution apuntan a media encriptado de WhatsApp**, un GET directo no devuelve bytes de imagen sino payloads no-imagen.

Fix: usar `download_media_evolution()` que llama al endpoint `/chat/getBase64FromMediaMessage/{instance}` — Evolution descifra internamente y devuelve base64 decodable a JPEG válido. Patrón extraído del worker [[wiki/entidades/lau]] que ya lo hacía bien.

## Origen y validación

- Diseñado e implementado 2026-04-23 por [[wiki/entidades/arnaldo-ayala]] + Claude
- Commits: `1de9697` (módulo inicial), `6158186` (sanitización mime), `5f9e178` (download Evolution correcto + guard bytes)
- Integrado en ambos demos — validado end-to-end con fotos reales (Robert: mansión con pileta, Mica: casa una planta)

## Relacionado

- [[wiki/conceptos/message-buffer-debounce]] — el texto consolidado entra al buffer antes del LLM
- Worker audio hermano: `_transcribir_audio_meta()` en cada worker usa Whisper — mismo patrón pero para audio
- Endpoint Evolution usado: ya estaba probado en `workers/clientes/system_ia/lau/worker.py`
