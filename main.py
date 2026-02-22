import os
from fastapi import FastAPI
from workers.social.worker import router as social_router
from workers.whatsapp.worker import router as whatsapp_router
from workers.crm.worker import router as crm_router
from workers.agenda.worker import router as agenda_router
from workers.comercio.worker import router as comercio_router

app = FastAPI(
    title="System IA — Cerebro Central",
    description=(
        "Orquestador de Workers IA para la agencia de automatizaciones System IA. "
        "Servicios: WhatsApp · Redes Sociales · CRM · Agendamiento de Citas"
    ),
    version="2.0.0"
)

# ── Routers de los 5 Workers ─────────────────────────────────────────────────
app.include_router(social_router)
app.include_router(whatsapp_router)
app.include_router(crm_router)
app.include_router(agenda_router)
app.include_router(comercio_router)


# ── Rutas de sistema ─────────────────────────────────────────────────────────
@app.get("/", tags=["Sistema"])
def root():
    """Mapa completo de endpoints disponibles."""
    return {
        "status": "online",
        "version": "2.0.0",
        "agencia": "System IA — Automatizaciones para LATAM",
        "workers": {
            "social": [
                "POST /social/crear-post",
                "POST /social/generar-imagen",
                "POST /social/seleccionar-tema"
            ],
            "whatsapp": [
                "POST /whatsapp/clasificar-mensaje",
                "POST /whatsapp/generar-respuesta",
                "POST /whatsapp/transcribir-audio"
            ],
            "crm": [
                "POST /crm/calificar-lead",
                "POST /crm/enriquecer-lead",
                "POST /crm/generar-seguimiento"
            ],
            "agenda": [
                "POST /agenda/parsear-fecha",
                "POST /agenda/verificar-slot",
                "POST /agenda/generar-recordatorio"
            ],
            "comercio": [
                "POST /comercio/procesar-whatsapp"
            ]
        }
    }


@app.get("/health", tags=["Sistema"])
def health_check():
    """Health check para monitoreo de Easypanel/Coolify."""
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY"))
    return {
        "status": "healthy",
        "gemini_api": "configured" if gemini_ok else "ERROR — falta GEMINI_API_KEY",
        "workers_activos": 4
    }
