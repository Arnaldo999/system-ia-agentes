---
name: fastapi-worker
description: Especialista en crear y modificar workers FastAPI para System IA. Activar SIEMPRE que el pedido involucre crear un nuevo worker de WhatsApp, agregar un endpoint al backend, modificar la lógica de conversación de un bot, integrar Gemini en un worker, trabajar con YCloud o Meta Graph API, agregar un paso al flujo conversacional, modificar SESIONES/estado del bot, integrar Airtable desde Python, o debuggear un worker existente. También activar ante "modificá el bot", "el bot no responde bien", "agregá un paso", "integrá [API] al worker", "creá el worker para [cliente]".
---

# SKILL: FastAPI Worker Expert

## Estructura del monorepo (CRÍTICO — leer antes de tocar cualquier archivo)

```
01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/
├── main.py                          ← entry point, rutas principales
├── workers/
│   ├── clientes/
│   │   ├── arnaldo/
│   │   │   ├── maicol/worker.py    ← bot Maicol (YCloud + Airtable) LIVE
│   │   │   └── prueba/worker.py    ← bot prueba Arnaldo
│   │   ├── lovbot/                 ← clientes Robert (Meta Graph API)
│   │   └── system-ia/              ← clientes Mica
│   ├── demos/
│   │   ├── inmobiliaria/worker.py  ← NUNCA editar, solo copiar
│   │   └── gastronomia/worker.py   ← NUNCA editar, solo copiar
│   └── social/worker.py            ← comentarios IG/FB + publicación
└── requirements.txt
```

**Regla de oro**: Nunca compartir workers entre proyectos. Para cliente nuevo: copiar demo → renombrar → adaptar.

## Plantilla de worker WhatsApp (YCloud)

```python
"""
Worker [NOMBRE_CLIENTE] — [DESCRIPCION]
API: YCloud / Meta Graph API
"""
import os, re, logging, httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Config ──────────────────────────────────────────────────────────────────
YCLOUD_API_KEY    = os.getenv("YCLOUD_API_KEY", "")
NUMERO_BOT        = os.getenv("NUMERO_BOT_[CLIENTE]", "")
NUMERO_ASESOR     = os.getenv("NUMERO_ASESOR_[CLIENTE]", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
AIRTABLE_TOKEN    = os.getenv("AIRTABLE_TOKEN", "")
AIRTABLE_BASE     = os.getenv("AIRTABLE_BASE_[CLIENTE]", "")

# ── Estado en memoria ────────────────────────────────────────────────────────
SESIONES: dict[str, dict] = {}
MENSAJES_PROCESADOS: set[str] = set()  # deduplicación YCloud retries

# ── Constantes de mapeo ──────────────────────────────────────────────────────
MAPA_OPCIONES = {
    "1": "Opción A",
    "2": "Opción B",
}

# ── Helpers Airtable ─────────────────────────────────────────────────────────
async def _at_buscar_registros(filtro: str) -> list[dict]:
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/Tabla"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    params = {"filterByFormula": filtro, "maxRecords": 10}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json().get("records", [])

async def _at_guardar_cliente(phone: str, datos: dict) -> None:
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE}/Clientes"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    payload = {"fields": {"Teléfono": phone, **datos}}
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(url, headers=headers, json=payload)

# ── Helpers YCloud ───────────────────────────────────────────────────────────
async def _enviar_mensaje(phone: str, texto: str) -> None:
    url = "https://api.ycloud.com/v2/whatsapp/messages"
    headers = {"X-API-Key": YCLOUD_API_KEY, "Content-Type": "application/json"}
    payload = {
        "from": NUMERO_BOT,
        "to": phone,
        "type": "text",
        "text": {"body": texto}
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code not in (200, 201):
            logger.error(f"YCloud error {r.status_code}: {r.text}")

# ── Helper Gemini ────────────────────────────────────────────────────────────
async def _call_gemini_text(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

# ── Máquina de estados ───────────────────────────────────────────────────────
async def _procesar_mensaje(phone: str, texto: str) -> None:
    texto = texto.strip()
    
    # Reset universal
    if texto == "0":
        SESIONES.pop(phone, None)
        await _enviar_mensaje(phone, "Sesión reiniciada. Escribí *hola* para comenzar.")
        return

    sesion = SESIONES.setdefault(phone, {"step": "inicio"})
    step = sesion["step"]

    if step == "inicio":
        sesion["step"] = "nombre"
        await _enviar_mensaje(phone, "¡Hola! ¿Cuál es tu nombre?")

    elif step == "nombre":
        sesion["nombre"] = texto.title()
        sesion["step"] = "siguiente_paso"
        await _enviar_mensaje(phone, f"Hola {sesion['nombre']}! [siguiente pregunta]")

    # ... agregar más steps según el flujo

# ── Endpoint principal ───────────────────────────────────────────────────────
@router.post("/[cliente]/webhook")
async def webhook(payload: dict):
    try:
        msg = payload.get("message", {})
        msg_id = msg.get("id", "")
        
        # Deduplicación
        if msg_id in MENSAJES_PROCESADOS:
            return {"status": "duplicate"}
        MENSAJES_PROCESADOS.add(msg_id)
        if len(MENSAJES_PROCESADOS) > 1000:
            MENSAJES_PROCESADOS.clear()

        phone = msg.get("from", "")
        texto = msg.get("text", {}).get("body", "").strip()
        
        if not phone or not texto:
            return {"status": "ignored"}

        await _procesar_mensaje(phone, texto)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error webhook: {e}")
        return {"status": "error", "detail": str(e)}
```

## Flujo conversacional — patrón Maicol (referencia)

```python
# steps en orden: inicio → nombre → objetivo → zona → presupuesto → urgencia
#   → [Gemini scoring] → propiedades (caliente/tibio) | sitio_web (frío)
#   → ficha → pedir_email → fin

# Mapas de opciones (SIEMPRE convertir número → texto antes de guardar en sesión)
MAPA_ZONA = {"1": "San Ignacio", "2": "Gdor Roca", "3": "Apóstoles",
             "4": "Leandro N. Alem", "5": "Lote Urbano", "6": "Otra zona"}

# Scoring con Gemini
async def _scoring_gemini(sesion: dict) -> str:
    prompt = f"""Eres un asesor inmobiliario. Evalúa este lead:
    - Nombre: {sesion.get('nombre')}
    - Objetivo: {sesion.get('objetivo')}
    - Zona: {sesion.get('zona')}
    - Presupuesto: {sesion.get('presupuesto')}
    - Urgencia: {sesion.get('urgencia')}
    
    Responde SOLO con una palabra: caliente, tibio, o frío."""
    resultado = await _call_gemini_text(prompt)
    return resultado.lower().strip()
```

## Integración Meta Graph API (para workers lovbot/Robert)

```python
META_ACCESS_TOKEN  = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")

async def _enviar_meta(phone: str, texto: str) -> None:
    url = f"https://graph.facebook.com/v21.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": texto}
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code not in (200, 201):
            logger.error(f"Meta error {r.status_code}: {r.text}")

# Webhook Meta (verificación + recepción)
@router.get("/meta/webhook")
async def meta_verify(hub_mode: str = "", hub_verify_token: str = "", hub_challenge: str = ""):
    if hub_mode == "subscribe" and hub_verify_token == os.getenv("META_VERIFY_TOKEN"):
        return int(hub_challenge)
    return {"error": "forbidden"}, 403

@router.post("/meta/webhook")
async def meta_webhook(payload: dict):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                phone = msg.get("from")
                texto = msg.get("text", {}).get("body", "").strip()
                msg_id = msg.get("id", "")
                phone_number_id = value.get("metadata", {}).get("phone_number_id")
                # routear por phone_number_id al worker correcto
                await _procesar_mensaje(phone, texto, msg_id, phone_number_id)
    return {"status": "ok"}
```

## Env vars por proyecto

| Variable | Proyecto | Dónde cargar |
|----------|----------|-------------|
| `YCLOUD_API_KEY` | Todos (YCloud) | Coolify Arnaldo |
| `NUMERO_BOT_MAICOL` | Maicol | Coolify Arnaldo |
| `NUMERO_ASESOR_MAICOL` | Maicol | Coolify Arnaldo |
| `META_ACCESS_TOKEN` | Robert | Coolify Robert |
| `META_PHONE_NUMBER_ID` | Robert | Coolify Robert |
| `META_VERIFY_TOKEN` | Robert | Coolify Robert + n8n Settings |
| `GEMINI_API_KEY` | Todos | Coolify por proyecto |
| `AIRTABLE_TOKEN` | Todos | Coolify por proyecto |
| `AIRTABLE_BASE_MAICOL` | Maicol | `appaDT7uwHnimVZLM` |
| `AIRTABLE_BASE_ROBERT` | Robert | `appPSAVCmDgHOlRDp` |

## Convenciones de código (OBLIGATORIAS)

- `snake_case` funciones y variables, `UPPER_SNAKE_CASE` constantes
- DTOs Pydantic con prefijo `Datos` (ej: `DatosWebhook`)
- Retornar siempre `{"status": "success"|"error"|"partial", ...}`
- Imports: stdlib → third-party → local
- Helpers con `_` prefijo: `_call_gemini_text`, `_at_buscar_propiedades`
- Config SOLO desde `os.getenv()`, nunca hardcoded
- `async/await` para todo I/O (httpx, no requests)
- Timeout en todas las llamadas httpx: `timeout=15` (Airtable/YCloud), `timeout=30` (Gemini)

## Checklist antes de hacer deploy

- [ ] Variables de entorno definidas en Coolify (nunca en código)
- [ ] Router registrado en `main.py` (`app.include_router(worker.router)`)
- [ ] Deduplicación de mensajes implementada (`MENSAJES_PROCESADOS`)
- [ ] Reset con "0" implementado
- [ ] Todos los `httpx` calls con timeout
- [ ] `logger.error()` en todos los except
- [ ] Probado localmente con `uvicorn main:app --reload`
- [ ] Push a `master` → Coolify auto-deploy
