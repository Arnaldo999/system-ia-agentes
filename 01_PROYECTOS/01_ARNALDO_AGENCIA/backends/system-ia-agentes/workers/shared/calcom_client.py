"""
Cal.com client — wrapper compartido API v2
===========================================
Wrapper reusable de Cal.com para múltiples canales (WhatsApp, voz, web).
Consume las mismas env vars `INMO_DEMO_CAL_*` que ya usa el worker WhatsApp.

Uso típico desde voz worker:
    from workers.shared import calcom_client as cal
    slots = cal.get_availability(days=7, timezone="America/Argentina/Buenos_Aires")
    booking = cal.book_slot(slot_iso, name, email, phone, channel="voz")
    cal.cancel_booking(uid, reason="cliente reagendó")

Cuenta Cal.com: compartida de Arnaldo (servicio compartido entre las 3 agencias).
API: https://api.cal.com/v2 — versiones distintas por endpoint.
"""

import os
import re
import requests
from datetime import datetime, timedelta, timezone

CAL_API_KEY = os.environ.get("INMO_DEMO_CAL_API_KEY", "")
CAL_EVENT_ID = os.environ.get("INMO_DEMO_CAL_EVENT_ID", "")
CAL_TIMEZONE = os.environ.get("INMO_DEMO_CAL_TIMEZONE", "America/Argentina/Buenos_Aires")

_TZ_OFFSETS = {
    "America/Argentina/Buenos_Aires": -3,
    "America/Mexico_City": -6,
    "America/Bogota": -5,
    "America/Santiago": -4,
    "America/Lima": -5,
}

_DIAS_ES = {
    "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
    "Thursday": "Jueves", "Friday": "Viernes",
    "Saturday": "Sábado", "Sunday": "Domingo",
}


def is_configured() -> bool:
    return bool(CAL_API_KEY and CAL_EVENT_ID)


def get_availability(days: int = 7, max_slots: int = 6, slots_per_day: int = 2) -> list[dict]:
    """Retorna slots disponibles para los próximos N días.

    Returns: lista de {"fecha": "YYYY-MM-DD", "time": "ISO-8601 UTC"}
    """
    if not is_configured():
        return []
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    end = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    try:
        r = requests.get(
            "https://api.cal.com/v2/slots",
            params={"eventTypeId": CAL_EVENT_ID, "start": start, "end": end},
            headers={
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-09-04",
            },
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[CAL] availability error {r.status_code}: {r.text[:200]}")
            return []
        slots_raw = r.json().get("data", {})
        slots = []
        for fecha, lista in slots_raw.items():
            for slot in lista[:slots_per_day]:
                if slot.get("start"):
                    slots.append({"fecha": fecha, "time": slot["start"]})
        return slots[:max_slots]
    except Exception as e:
        print(f"[CAL] availability exc: {e}")
        return []


def book_slot(slot_iso: str, name: str, email: str, phone: str,
              notes: str = "", channel: str = "whatsapp") -> dict:
    """Crea una reserva en Cal.com.

    Returns: {"ok": bool, "uid": str, "start": str, "error": str}
    `channel` se guarda en metadata para reportería cross-channel.
    """
    if not is_configured():
        return {"ok": False, "error": "Cal.com no configurado"}
    try:
        digits = re.sub(r"\D", "", phone)
        fallback_email = email or f"{digits}@lovbot.ai"
        r = requests.post(
            "https://api.cal.com/v2/bookings",
            headers={
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-08-13",
                "Content-Type": "application/json",
            },
            json={
                "eventTypeId": int(CAL_EVENT_ID),
                "start": slot_iso,
                "attendee": {
                    "name": name,
                    "email": fallback_email,
                    "timeZone": CAL_TIMEZONE,
                    "language": "es",
                    "phoneNumber": "+" + digits,
                },
                "metadata": {
                    "fuente": f"Lovbot Bot ({channel})",
                    "canal": channel,
                    "notas": (notes or "")[:200],
                },
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json().get("data", {})
            return {"ok": True, "uid": data.get("uid", ""), "start": data.get("start", slot_iso)}
        print(f"[CAL] book error {r.status_code}: {r.text[:300]}")
        return {"ok": False, "error": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cancel_booking(uid: str, reason: str = "") -> dict:
    """Cancela una reserva existente."""
    if not is_configured() or not uid:
        return {"ok": False, "error": "Cal.com no configurado o uid vacío"}
    try:
        r = requests.post(
            f"https://api.cal.com/v2/bookings/{uid}/cancel",
            headers={
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-08-13",
                "Content-Type": "application/json",
            },
            json={"cancellationReason": reason[:200] if reason else "Cancelado por bot"},
            timeout=10,
        )
        if r.status_code in (200, 201, 204):
            return {"ok": True}
        return {"ok": False, "error": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def format_slot_for_voice(slot: dict) -> str:
    """Convierte slot ISO a frase natural para que el agente de voz la lea.

    Ej: "Martes 28 de abril a las 10 de la mañana"
    """
    try:
        dt = datetime.fromisoformat(slot["time"].replace("Z", "+00:00"))
        offset = _TZ_OFFSETS.get(CAL_TIMEZONE, -3)
        local = dt.astimezone(timezone(timedelta(hours=offset)))
        dia_en = local.strftime("%A")
        dia_es = _DIAS_ES.get(dia_en, dia_en)
        hora = local.hour
        ampm = "de la mañana" if hora < 12 else ("del mediodía" if hora == 12 else "de la tarde")
        hora_12 = hora if hora <= 12 else hora - 12
        return f"{dia_es} {local.day} a las {hora_12} {ampm}"
    except Exception:
        return slot.get("time", "")
