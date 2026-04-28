"""
Worker — Demo Inmobiliaria Voz (ElevenLabs)
============================================
Endpoints-tool que ElevenLabs Conversational AI consume durante una llamada
de voz. El agente de voz vive en ElevenLabs (Gemini 2.5 Flash + voz ES);
acá solo exponemos las herramientas que necesita para resolver intenciones.

Arquitectura:
    Cliente → Twilio → ElevenLabs Agent → POST /voz/* aquí → respuesta JSON

Stack:
    BD: Postgres `lovbot_crm_modelo` (vía workers.demos.inmobiliaria.db_postgres)
    Cal.com: cuenta Arnaldo compartida (vía workers.shared.calcom_client)
    BANT: workers.shared.bant
    Catálogo: workers.shared.catalog
    Match cross-channel: workers.shared.lead_matcher

Endpoints:
    POST /voz/disponibilidad   — slots Cal.com próximos N días
    POST /voz/agendar-visita    — book slot + upsert lead
    POST /voz/buscar-propiedad  — query catálogo Postgres
    POST /voz/cancelar-visita   — cancelar booking Cal.com
    POST /voz/identificar-lead  — match cross-channel por caller_id

Cada endpoint retorna `{success, data, message}` donde `message` es la
frase exacta que el agente dirá al usuario (mantenerla corta y natural).
"""

import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from workers.shared import calcom_client as cal
from workers.shared import catalog
from workers.shared import lead_matcher
from workers.shared import bant

router = APIRouter(prefix="/demos/voz/inmobiliaria", tags=["voz-demo-inmobiliaria"])

NOMBRE_EMPRESA = os.environ.get("INMO_DEMO_NOMBRE", "Lovbot Inmobiliaria")
ASESOR = os.environ.get("INMO_DEMO_ASESOR", "Roberto")


def _ok(message: str, **data) -> dict:
    return {"success": True, "data": data, "message": message}


def _fail(message: str, **data) -> dict:
    return {"success": False, "data": data, "message": message}


@router.post("/disponibilidad")
async def disponibilidad(req: Request):
    """Devuelve hasta 6 slots disponibles para visitas.

    Body esperado (de ElevenLabs):
        { "fecha_preferida": "YYYY-MM-DD" | null, "dias": int }
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    dias = int(body.get("dias", 7))
    slots = cal.get_availability(days=dias, max_slots=6, slots_per_day=2)
    if not slots:
        return _fail("No tengo horarios disponibles en este momento, prefiero pasarte con un asesor humano.")
    listado = "; ".join(cal.format_slot_for_voice(s) for s in slots[:3])
    return _ok(
        f"Tengo varias opciones disponibles. Las más cercanas son: {listado}. ¿Cuál te queda mejor?",
        slots=slots,
    )


@router.post("/agendar-visita")
async def agendar_visita(req: Request):
    """Agenda una visita: book Cal.com + upsert lead.

    Body esperado:
        {
            "slot_iso": "2026-04-28T13:00:00.000Z",
            "name": "Juan Pérez",
            "email": "juan@gmail.com",
            "caller_id": "+5493764999999",
            "notas": "interesado en casa zona centro"
        }
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    slot_iso = body.get("slot_iso") or body.get("start")
    name = body.get("name", "")
    email = body.get("email", "")
    phone = body.get("caller_id", "") or body.get("phone", "")
    notas = body.get("notas", "")
    if not (slot_iso and name and phone):
        return _fail("Necesito el horario, tu nombre y un número de contacto para agendar.")

    booking = cal.book_slot(slot_iso, name, email, phone, notes=notas, channel="voz")
    if not booking.get("ok"):
        return _fail(
            "No pude agendar en este momento, voy a pedirle a un asesor que te llame para coordinar.",
            error=booking.get("error", ""),
        )

    lead_matcher.upsert_lead_voice(
        phone=phone, name=name, email=email,
        score="caliente", notes=f"voz - agenda: {notas}"[:200],
    )
    return _ok(
        f"Listo, tu visita quedó agendada. {ASESOR} te va a estar esperando y vas a recibir la confirmación por correo.",
        booking_uid=booking.get("uid", ""),
        booking_start=booking.get("start", ""),
    )


@router.post("/buscar-propiedad")
async def buscar_propiedad(req: Request):
    """Busca propiedades en el catálogo Postgres.

    Body esperado:
        { "tipo": "casa", "operacion": "venta", "zona": "Posadas Centro",
          "presupuesto": "100k_200k" }
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    props = catalog.search_properties(
        tipo=body.get("tipo"),
        operacion=body.get("operacion"),
        zona=body.get("zona"),
        presupuesto=body.get("presupuesto"),
        limit=5,
    )
    if not props:
        return _fail(
            "No encontré opciones que coincidan exactamente. ¿Querés que te muestre algo similar o ampliamos el rango?"
        )
    top3 = props[:3]
    listado = "; ".join(catalog.format_property_for_voice(p) for p in top3)
    return _ok(
        f"Encontré {len(props)} opciones. Las que mejor encajan son: {listado}. ¿Te gustaría agendar una visita a alguna?",
        propiedades=top3,
        total=len(props),
    )


@router.post("/cancelar-visita")
async def cancelar_visita(req: Request):
    """Cancela un booking existente en Cal.com.

    Body esperado: { "booking_uid": "...", "razon": "cliente cambió de plan" }
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    uid = body.get("booking_uid", "")
    razon = body.get("razon", "")
    if not uid:
        return _fail("Necesito el código de tu reserva para cancelarla.")
    res = cal.cancel_booking(uid, reason=razon)
    if res.get("ok"):
        return _ok("Listo, cancelé tu visita. ¿Querés reagendar para otro día?")
    return _fail("No pude cancelar la reserva, voy a derivarte con un asesor.", error=res.get("error", ""))


@router.post("/identificar-lead")
async def identificar_lead(req: Request):
    """Match cross-channel: si el número que llama ya existe en `leads`,
    devuelve nombre + score + notas previas para que el agente personalice.

    Body esperado: { "caller_id": "+5493764999999" }
    """
    try:
        body = await req.json()
    except Exception:
        body = {}
    phone = body.get("caller_id", "") or body.get("phone", "")
    if not phone:
        return _fail("No recibí el número.")
    lead = lead_matcher.find_lead_by_phone(phone)
    if not lead:
        return _ok(
            "Parece ser un cliente nuevo, voy a presentarme normalmente.",
            existing=False,
        )
    nombre = (lead.get("nombre") or "").strip() or "el cliente"
    score = lead.get("score", "")
    notas = (lead.get("notas_bot") or "")[:150]
    return _ok(
        f"Cliente conocido: {nombre} (score {score}). Notas previas: {notas}",
        existing=True,
        nombre=nombre,
        score=score,
        notas_previas=notas,
        zona_interes=lead.get("zona", ""),
        operacion=lead.get("operacion", ""),
        tipo_propiedad=lead.get("tipo_propiedad", ""),
    )


@router.get("/healthz")
async def healthz():
    """Smoke test del worker voz (sin tocar BD)."""
    return JSONResponse({
        "ok": True,
        "service": "voz-demo-inmobiliaria",
        "calcom_configured": cal.is_configured(),
        "empresa": NOMBRE_EMPRESA,
    })
