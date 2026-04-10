import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

# ── Logging estructurado ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("system-ia")

# Registro global de errores en memoria (últimos 100)
_error_log: list[dict] = []

def registrar_error(endpoint: str, error: Exception, contexto: dict = {}):
    """Registra un error en el log interno y en stdout para Coolify/Render."""
    import traceback, datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "endpoint": endpoint,
        "error": str(error),
        "tipo": type(error).__name__,
        "traceback": traceback.format_exc(),
        **contexto
    }
    _error_log.append(entry)
    if len(_error_log) > 100:
        _error_log.pop(0)
    logger.error(f"[{endpoint}] {type(error).__name__}: {error}")

# ── Clientes Arnaldo ──────────────────────────────────────────────────────────
from workers.clientes.arnaldo.maicol.worker import router as maicol_router
from workers.clientes.arnaldo.prueba.worker import router as prueba_router

# ── Clientes Lovbot ───────────────────────────────────────────────────────────
from workers.clientes.lovbot.robert_inmobiliaria.worker import router as robert_inmo_router
from workers.clientes.lovbot.robert_inmobiliaria.worker import _procesar as robert_inmo_procesar

# ── Demos ─────────────────────────────────────────────────────────────────────
from workers.demos.inmobiliaria.worker  import router as demo_inmobiliaria_router
from workers.demos.gastronomico.worker  import router as demo_gastronomico_router

# ── SaaS ──────────────────────────────────────────────────────────────────────
from workers.shared.tenants import router as tenants_router, crm_router, admin_router

# ── System IA — Clientes ──────────────────────────────────────────────────────
from workers.clientes.system_ia.lau.worker import router as lau_router

# ── System IA ─────────────────────────────────────────────────────────────────
from workers.social.worker import router as social_router

app = FastAPI(
    title="System IA — Agentes",
    description=(
        "Backend de automatizaciones IA para la agencia System IA. "
        "Arquitectura: clientes/ (producción) · demos/ (presentaciones) · social/ (System IA)"
    ),
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def middleware_deteccion_errores(request: Request, call_next):
    """Captura cualquier excepción no manejada y la registra."""
    import time
    start = time.time()
    try:
        response = await call_next(request)
        elapsed = round((time.time() - start) * 1000)
        if response.status_code >= 500:
            logger.warning(f"[{request.method}] {request.url.path} → {response.status_code} ({elapsed}ms)")
        return response
    except Exception as e:
        registrar_error(request.url.path, e, {"method": request.method})
        return PlainTextResponse(f"Error interno: {type(e).__name__}", status_code=500)

# ── Registrar routers ─────────────────────────────────────────────────────────
app.include_router(tenants_router)
app.include_router(crm_router)
app.include_router(admin_router)
app.include_router(maicol_router)
app.include_router(prueba_router)
app.include_router(robert_inmo_router)
app.include_router(demo_inmobiliaria_router)
app.include_router(demo_gastronomico_router)
app.include_router(lau_router)
app.include_router(social_router)


# ── Meta Webhook — Tech Provider Robert/Lovbot ───────────────────────────────
_META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")
_META_MSG_IDS_PROCESADOS: set[str] = set()  # deduplicación de reintentos Meta

@app.get("/meta/webhook", tags=["Meta"])
async def meta_webhook_verify(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == _META_VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Token inválido", status_code=403)

@app.post("/meta/webhook", tags=["Meta"])
async def meta_webhook_events(request: Request):
    """Recibe eventos de Meta (WhatsApp) y los despacha al worker correcto."""
    import threading
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}

    _ROBERT_PHONE_ID = os.environ.get("META_PHONE_NUMBER_ID", "")

    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                msg_id = msg.get("id", "")
                if msg_id and msg_id in _META_MSG_IDS_PROCESADOS:
                    print(f"[META-WEBHOOK] Duplicado ignorado: {msg_id}")
                    continue
                if msg_id:
                    _META_MSG_IDS_PROCESADOS.add(msg_id)
                    # Mantener el set acotado a 500 entradas
                    if len(_META_MSG_IDS_PROCESADOS) > 500:
                        _META_MSG_IDS_PROCESADOS.clear()

                telefono = msg.get("from", "")
                texto = msg.get("text", {}).get("body", "")
                if not telefono or not texto:
                    continue
                # Enrutar según phone_number_id
                if phone_number_id == _ROBERT_PHONE_ID:
                    threading.Thread(
                        target=robert_inmo_procesar,
                        args=(telefono, texto), daemon=True
                    ).start()

    return {"status": "received"}


# ── Rutas de sistema ──────────────────────────────────────────────────────────
@app.get("/", tags=["Sistema"])
def root():
    """Mapa de endpoints activos."""
    return {
        "status": "online",
        "version": "3.0.0",
        "agencia": "System IA — Automatizaciones para LATAM",
        "clientes": {
            "arnaldo/maicol": [
                "POST /clientes/arnaldo/maicol/lead",
                "POST /clientes/arnaldo/maicol/whatsapp",
                "GET  /clientes/arnaldo/maicol/propiedades",
                "GET  /clientes/arnaldo/maicol/crm/propiedades",
                "GET  /clientes/arnaldo/maicol/crm/clientes",
            ],
        },
        "demos": {
            "inmobiliaria": [
                "POST /demos/inmobiliaria/lead",
                "POST /demos/inmobiliaria/whatsapp",
                "GET  /demos/inmobiliaria/propiedades",
                "GET  /demos/inmobiliaria/crm/propiedades",
                "GET  /demos/inmobiliaria/crm/clientes",
                "GET  /demos/inmobiliaria/config",
            ],
            "gastronomico": [
                "POST /demos/gastronomico/whatsapp",
                "POST /demos/gastronomico/mensaje",
                "GET  /demos/gastronomico/crm/reservas",
                "GET  /demos/gastronomico/crm/pedidos",
                "GET  /demos/gastronomico/crm/clientes",
                "GET  /demos/gastronomico/config",
                "POST /demos/gastronomico/difusion",
            ],
        },
        "system_ia": {
            "social": [
                "GET  /social/meta-webhook",
                "POST /social/meta-webhook",
            ],
        },
    }


@app.get("/debug/errors", tags=["Sistema"])
def debug_errors(limit: int = 20):
    """Últimos errores capturados por el middleware. Útil para monitoreo."""
    ultimos = _error_log[-limit:] if _error_log else []
    return {
        "total_errores": len(_error_log),
        "mostrando": len(ultimos),
        "errores": list(reversed(ultimos))  # más reciente primero
    }


@app.get("/health", tags=["Sistema"])
def health_check():
    """Health check para monitoreo de Easypanel/Coolify."""
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY"))
    return {
        "status": "healthy",
        "gemini_api": "configured" if gemini_ok else "ERROR — falta GEMINI_API_KEY",
        "workers_activos": 6
    }


@app.get("/debug/linkedin-id", tags=["Sistema"])
def debug_linkedin_id():
    """Llama a LinkedIn con el token guardado y devuelve tu Person ID."""
    import requests
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        return {"error": "LINKEDIN_ACCESS_TOKEN no está configurado"}
    try:
        r = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        data = r.json()
        person_id = data.get("sub", "no encontrado")
        return {
            "LINKEDIN_PERSON_ID": person_id,
            "instruccion": f"Copia este valor y ponlo en Easypanel como LINKEDIN_PERSON_ID={person_id}",
            "nombre": data.get("name", ""),
            "email": data.get("email", "")
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/env", tags=["Sistema"])
def debug_env():
    """Muestra qué variables de entorno están configuradas (sin exponer valores)."""
    def check(key):
        val = os.environ.get(key, "")
        return f"✅ ({len(val)} chars)" if val else "❌ vacía"

    return {
        "gemini":     {"GEMINI_API_KEY": check("GEMINI_API_KEY")},
        "meta":       {
            "META_ACCESS_TOKEN":      check("META_ACCESS_TOKEN"),
            "IG_BUSINESS_ACCOUNT_ID": check("IG_BUSINESS_ACCOUNT_ID"),
            "FACEBOOK_PAGE_ID":       check("FACEBOOK_PAGE_ID"),
        },
        "linkedin":   {
            "LINKEDIN_ACCESS_TOKEN": check("LINKEDIN_ACCESS_TOKEN"),
            "LINKEDIN_PERSON_ID":    check("LINKEDIN_PERSON_ID"),
        },
        "cloudinary": {
            "CLOUDINARY_CLOUD_NAME":    check("CLOUDINARY_CLOUD_NAME"),
            "CLOUDINARY_UPLOAD_PRESET": check("CLOUDINARY_UPLOAD_PRESET"),
        },
        "whatsapp":   {
            "EVOLUTION_API_URL":       check("EVOLUTION_API_URL"),
            "EVOLUTION_INSTANCE":      check("EVOLUTION_INSTANCE"),
            "EVOLUTION_API_KEY":       check("EVOLUTION_API_KEY"),
            "WHATSAPP_APPROVAL_NUMBER": check("WHATSAPP_APPROVAL_NUMBER"),
        }
    }
