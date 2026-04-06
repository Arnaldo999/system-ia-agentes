import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

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
from workers.shared.tenants import router as tenants_router

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

# ── Registrar routers ─────────────────────────────────────────────────────────
app.include_router(tenants_router)
app.include_router(maicol_router)
app.include_router(prueba_router)
app.include_router(robert_inmo_router)
app.include_router(demo_inmobiliaria_router)
app.include_router(demo_gastronomico_router)
app.include_router(social_router)


# ── Meta Webhook — Tech Provider Robert/Lovbot ───────────────────────────────
_META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")

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
