"""
Worker — Robert Bazán / Lovbot — Inmobiliaria Completa v2
==========================================================
Inmobiliaria completa con:
  - Captación y precalificación inteligente de leads (Gemini)
  - Búsqueda de propiedades en Airtable con filtros
  - Fichas completas con imagen
  - Score caliente/tibio/frío + notificación al asesor
  - Registro automático de leads en Airtable
  - Canal: Meta Graph API (WhatsApp Business API)

Variables de entorno:
  META_ACCESS_TOKEN        Token permanente del System User
  META_PHONE_NUMBER_ID     ID del número de WhatsApp
  GEMINI_API_KEY           Compartida
  AIRTABLE_TOKEN           Token Airtable
  ROBERT_AIRTABLE_BASE     Base ID de Robert en Airtable
  ROBERT_TABLE_PROPS       ID tabla propiedades
  ROBERT_TABLE_CLIENTES    ID tabla clientes/leads

  INMO_DEMO_NOMBRE         Nombre empresa (def: "Lovbot — Inmobiliaria")
  INMO_DEMO_CIUDAD         Ciudad (def: "México")
  INMO_DEMO_ASESOR         Nombre asesor (def: "Roberto")
  INMO_DEMO_NUMERO_ASESOR  Número asesor para notificaciones
  INMO_DEMO_ZONAS          Zonas separadas por coma
  INMO_DEMO_MONEDA         Moneda (def: USD)
  INMO_DEMO_SITIO_WEB      URL del sitio web (opcional)
"""

import os
import re
import json
import threading
import requests
from google import genai
from fastapi import APIRouter, Request

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_PHONE_ID     = os.environ.get("META_PHONE_NUMBER_ID", "")

# Chatwoot
CHATWOOT_API_TOKEN  = os.environ.get("LOVBOT_CHATWOOT_API_TOKEN", "")
CHATWOOT_URL        = os.environ.get("LOVBOT_CHATWOOT_URL", "https://chatwoot.lovbot.ai")
CHATWOOT_ACCOUNT_ID = os.environ.get("LOVBOT_CHATWOOT_ACCOUNT_ID", "2")
CHATWOOT_INBOX_ID   = os.environ.get("LOVBOT_CHATWOOT_INBOX_ID", "4")

AIRTABLE_TOKEN         = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID       = os.environ.get("ROBERT_AIRTABLE_BASE", "")
AIRTABLE_TABLE_PROPS   = os.environ.get("ROBERT_TABLE_PROPS", "")
AIRTABLE_TABLE_LEADS   = os.environ.get("ROBERT_TABLE_CLIENTES", "")
AIRTABLE_TABLE_ACTIVOS = os.environ.get("ROBERT_TABLE_ACTIVOS", "tblpfSE6qkGCV6e99")

NOMBRE_EMPRESA = os.environ.get("INMO_DEMO_NOMBRE",  "Lovbot — Inmobiliaria")
CIUDAD         = os.environ.get("INMO_DEMO_CIUDAD",  "México")
NOMBRE_ASESOR  = os.environ.get("INMO_DEMO_ASESOR",  "Roberto")
NUMERO_ASESOR  = os.environ.get("INMO_DEMO_NUMERO_ASESOR", "")
MONEDA         = os.environ.get("INMO_DEMO_MONEDA",  "USD")
SITIO_WEB      = os.environ.get("INMO_DEMO_SITIO_WEB", "")
CAL_API_KEY    = os.environ.get("INMO_DEMO_CAL_API_KEY", "")
CAL_EVENT_ID   = os.environ.get("INMO_DEMO_CAL_EVENT_ID", "")
CAL_TIMEZONE   = os.environ.get("INMO_DEMO_CAL_TIMEZONE", "America/Argentina/Buenos_Aires")

# Mapeo timezone → offset UTC para conversión de slots
_TZ_OFFSETS = {
    "America/Argentina/Buenos_Aires": -3,
    "America/Mexico_City": -6,
    "America/Bogota": -5,
    "America/Santiago": -4,
    "America/Lima": -5,
}
_TZ_OFFSET_HOURS = _TZ_OFFSETS.get(CAL_TIMEZONE, -3)

_zonas_raw = os.environ.get("INMO_DEMO_ZONAS", "Zona Norte,Zona Sur,Zona Centro")
ZONAS_LIST = [z.strip() for z in _zonas_raw.split(",") if z.strip()]

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Importar módulo PostgreSQL
try:
    from workers.clientes.lovbot.robert_inmobiliaria import db_postgres as db
    USE_POSTGRES = db._available()
    if USE_POSTGRES:
        print("[ROBERT] ✅ PostgreSQL disponible — usando DB directa")
    else:
        print("[ROBERT] ⚠️ PostgreSQL no configurado — usando Airtable")
except ImportError:
    USE_POSTGRES = False
    db = None
    print("[ROBERT] ⚠️ db_postgres no encontrado — usando Airtable")

router = APIRouter(prefix="/clientes/lovbot/inmobiliaria", tags=["Robert — Inmobiliaria"])

# ─── SESIONES EN MEMORIA ──────────────────────────────────────────────────────
SESIONES: dict[str, dict] = {}

# ─── HISTORIAL DE CONVERSACIÓN ────────────────────────────────────────────────
# Guarda los últimos mensajes de cada lead para que el asesor vea contexto
HISTORIAL: dict[str, list[str]] = {}
MAX_HISTORIAL = 20  # últimos 20 mensajes


def _agregar_historial(telefono: str, quien: str, texto: str):
    """Agrega un mensaje al historial del lead."""
    tel = re.sub(r'\D', '', telefono)
    if tel not in HISTORIAL:
        HISTORIAL[tel] = []
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M")
    HISTORIAL[tel].append(f"[{ts}] {quien}: {texto[:150]}")
    if len(HISTORIAL[tel]) > MAX_HISTORIAL:
        HISTORIAL[tel] = HISTORIAL[tel][-MAX_HISTORIAL:]


def _guardar_historial_at(telefono: str):
    """Guarda el historial en Airtable campo Notas_Bot (async)."""
    tel = re.sub(r'\D', '', telefono)
    hist = HISTORIAL.get(tel, [])
    if not hist or not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return
    resumen = "\n".join(hist[-10:])  # últimos 10 mensajes
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    try:
        buscar = requests.get(url, headers=AT_HEADERS,
            params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
        records = buscar.json().get("records", []) if buscar.status_code == 200 else []
        if records:
            requests.patch(f"{url}/{records[0]['id']}", headers=AT_HEADERS,
                json={"fields": {"Notas_Bot": resumen[:5000]}}, timeout=8)
    except Exception as e:
        print(f"[ROBERT] Error guardando historial: {e}")


# ─── CHATWOOT BRIDGE ─────────────────────────────────────────────────────────

def _chatwoot_headers():
    return {"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"}


def _chatwoot_buscar_contacto(telefono: str) -> dict | None:
    """Busca un contacto en Chatwoot por teléfono."""
    if not CHATWOOT_API_TOKEN:
        return None
    tel = "+" + re.sub(r'\D', '', telefono)
    try:
        r = requests.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search",
            headers=_chatwoot_headers(),
            params={"q": tel, "include_contacts": True},
            timeout=8,
        )
        if r.status_code == 200:
            contacts = r.json().get("payload", [])
            for c in contacts:
                if c.get("phone_number", "").replace(" ", "") == tel:
                    return c
    except Exception as e:
        print(f"[CHATWOOT] Error buscando contacto: {e}")
    return None


def _chatwoot_buscar_conversacion(contacto_id: int) -> dict | None:
    """Busca conversación abierta del contacto en inbox WhatsApp."""
    if not CHATWOOT_API_TOKEN:
        return None
    try:
        r = requests.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/{contacto_id}/conversations",
            headers=_chatwoot_headers(),
            timeout=8,
        )
        if r.status_code == 200:
            convs = r.json().get("payload", [])
            for c in convs:
                if c.get("inbox_id") == int(CHATWOOT_INBOX_ID) and c.get("status") == "open":
                    return c
    except Exception as e:
        print(f"[CHATWOOT] Error buscando conversación: {e}")
    return None


def _chatwoot_escalar(telefono: str, sesion: dict, calificacion: dict = None):
    """Escala conversación a Chatwoot: busca contacto, añade label atiende-humano, envía nota."""
    if not CHATWOOT_API_TOKEN:
        print("[CHATWOOT] Sin token — skip escalamiento")
        return

    contacto = _chatwoot_buscar_contacto(telefono)
    if not contacto:
        print(f"[CHATWOOT] Contacto no encontrado para {telefono}")
        return

    contacto_id = contacto.get("id")
    conv = _chatwoot_buscar_conversacion(contacto_id)
    if not conv:
        print(f"[CHATWOOT] Sin conversación abierta para contacto {contacto_id}")
        return

    conv_id = conv.get("id")
    nombre = sesion.get("nombre", "")
    score = calificacion.get("score", "?") if calificacion else "?"
    nota = calificacion.get("nota_para_asesor", "") if calificacion else ""
    hist = HISTORIAL.get(re.sub(r'\D', '', telefono), [])
    historial_texto = "\n".join(hist[-10:]) if hist else "Sin historial"

    try:
        # Agregar labels: atiende-humano + score (caliente/tibio/frio)
        labels = conv.get("labels", [])
        if "atiende-humano" not in labels:
            labels.append("atiende-humano")
        if "atiende-agenteai" in labels:
            labels.remove("atiende-agenteai")
        # Agregar label del score y quitar los otros scores
        for s in ("caliente", "tibio", "frio"):
            if s in labels:
                labels.remove(s)
        if score in ("caliente", "tibio", "frio"):
            labels.append(score)
        # Agregar automatizacion
        if "automatizacion" not in labels:
            labels.append("automatizacion")

        requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/labels",
            headers=_chatwoot_headers(),
            json={"labels": labels},
            timeout=8,
        )

        # Enviar nota privada con contexto para el asesor
        nota_asesor = (
            f"🤖 Bot escaló esta conversación al asesor\n\n"
            f"👤 Nombre: {nombre}\n"
            f"📊 Score: {score.upper()}\n"
            f"📝 Nota: {nota}\n\n"
            f"💬 Últimos mensajes:\n{historial_texto}"
        )
        requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/messages",
            headers=_chatwoot_headers(),
            json={"content": nota_asesor, "message_type": "activity", "private": True},
            timeout=8,
        )
        print(f"[CHATWOOT] Escalado conv {conv_id} — label atiende-humano + nota privada")
    except Exception as e:
        print(f"[CHATWOOT] Error escalando: {e}")


# ─── PAUSA BOT (cuando asesor interviene) ────────────────────────────────────
# Formato: {telefono: timestamp_pausa}
# El bot NO responde si el lead está pausado (asesor activo)
LEADS_PAUSADOS: dict[str, float] = {}
PAUSA_TIMEOUT_HORAS = 4  # después de 4h sin actividad del asesor, bot retoma


def pausar_bot(telefono: str):
    """Pausa el bot para este lead — asesor tomó control."""
    import time
    LEADS_PAUSADOS[re.sub(r'\D', '', telefono)] = time.time()


def despausar_bot(telefono: str):
    """Reactiva el bot para este lead."""
    LEADS_PAUSADOS.pop(re.sub(r'\D', '', telefono), None)


def bot_pausado(telefono: str) -> bool:
    """Retorna True si el bot debe estar en silencio para este lead."""
    import time
    tel = re.sub(r'\D', '', telefono)
    if tel not in LEADS_PAUSADOS:
        return False
    # Auto-despausar después de PAUSA_TIMEOUT_HORAS
    elapsed = time.time() - LEADS_PAUSADOS[tel]
    if elapsed > PAUSA_TIMEOUT_HORAS * 3600:
        LEADS_PAUSADOS.pop(tel, None)
        return False
    return True

AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


# ─── CHATWOOT MIRROR ─────────────────────────────────────────────────────────
def _cw_mirror_msg(telefono: str, contenido: str, es_bot: bool) -> None:
    """
    Espeja un mensaje en Chatwoot para que la conversación completa sea visible.
    es_bot=True  → message_type='outgoing' (respuesta del bot)
    es_bot=False → message_type='incoming' (mensaje del cliente)
    Corre en hilo daemon — no agrega latencia al flujo principal.
    """
    if not CHATWOOT_API_TOKEN or not contenido.strip():
        return

    def _enviar():
        try:
            contacto = _chatwoot_buscar_contacto(telefono)
            if not contacto:
                return
            conv = _chatwoot_buscar_conversacion(contacto["id"])
            if not conv:
                return
            conv_id = conv["id"]
            msg_type = "outgoing" if es_bot else "incoming"
            requests.post(
                f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/messages",
                headers=_chatwoot_headers(),
                json={"content": contenido, "message_type": msg_type, "private": False},
                timeout=8,
            )
            print(f"[CW-MIRROR] {'🤖 bot' if es_bot else '👤 lead'} → conv {conv_id}")
        except Exception as e:
            print(f"[CW-MIRROR] Error: {e}")

    threading.Thread(target=_enviar, daemon=True).start()


# ─── META GRAPH API ───────────────────────────────────────────────────────────
def _enviar_texto(telefono: str, mensaje: str) -> bool:
    _agregar_historial(telefono, "Bot", mensaje)
    if not META_ACCESS_TOKEN or not META_PHONE_ID:
        print(f"[ROBERT-META] Sin token/phone_id. Msg: {mensaje[:80]}")
        return False
    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{META_PHONE_ID}/messages",
            headers={
                "Authorization": f"Bearer {META_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": re.sub(r'\D', '', telefono),
                "type": "text",
                "text": {"body": mensaje, "preview_url": False},
            },
            timeout=10,
        )
        if r.status_code not in (200, 201):
            print(f"[ROBERT-META] Error {r.status_code}: {r.text[:300]}")
        ok = r.status_code in (200, 201)
        if ok:
            _cw_mirror_msg(telefono, mensaje, es_bot=True)
        return ok
    except Exception as e:
        print(f"[ROBERT-META] Excepción: {e}")
        return False


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    if not META_ACCESS_TOKEN or not META_PHONE_ID or not url_imagen:
        return False
    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{META_PHONE_ID}/messages",
            headers={
                "Authorization": f"Bearer {META_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": re.sub(r'\D', '', telefono),
                "type": "image",
                "image": {"link": url_imagen, "caption": caption},
            },
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[ROBERT-META] Excepción imagen: {e}")
        return False


# ─── AIRTABLE ─────────────────────────────────────────────────────────────────
_TIPO_MAP = {
    "casa": "casa", "casas": "casa",
    "departamento": "departamento", "depto": "departamento", "apartamento": "departamento",
    "terreno": "terreno", "lote": "terreno",
    "local": "otro", "oficina": "otro",
}
_ZONA_MAP = {
    "apostoles": "Apóstoles", "apóstoles": "Apóstoles",
    "gdor roca": "Gdor Roca", "gobernador roca": "Gdor Roca", "gdorroca": "Gdor Roca",
    "san ignacio": "San Ignacio", "sanignacio": "San Ignacio",
    "otra zona": "Otra Zona", "otra": "Otra Zona", "no sé": "Otra Zona", "no se": "Otra Zona",
}


def _normalizar_tipo(tipo: str) -> str:
    return _TIPO_MAP.get(tipo.lower().strip(), "") if tipo else ""


def _normalizar_zona(zona: str) -> str:
    return _ZONA_MAP.get(zona.lower().strip(), "") if zona else ""


def _at_registrar_lead(telefono: str, nombre: str, score: str = "",
                       tipo: str = "", zona: str = "", notas: str = "",
                       presupuesto: str = "", operacion: str = "",
                       ciudad: str = "", subniche: str = "",
                       fuente_detalle: str = "") -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        print("[ROBERT-AT] Sin base/tabla configurada — skip registro lead")
        return
    from datetime import date
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    buscar = requests.get(url, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []

    campos = {"Telefono": telefono, "Llego_WhatsApp": True, "Fuente": "whatsapp_directo"}
    if nombre:
        partes = nombre.strip().split(" ", 1)
        campos["Nombre"] = partes[0]
        if len(partes) > 1:
            campos["Apellido"] = partes[1]
    if score == "caliente":
        campos["Estado"] = "calificado"
    elif score == "tibio":
        campos["Estado"] = "contactado"
    elif score:
        campos["Estado"] = "no_contactado"
    tipo_norm = _normalizar_tipo(tipo)
    if tipo_norm:
        campos["Tipo_Propiedad"] = tipo_norm
    zona_norm = _normalizar_zona(zona)
    if zona_norm:
        campos["Zona"] = zona_norm
    if operacion in ("venta", "alquiler"):
        campos["Operacion"] = operacion
    if ciudad:
        campos["Ciudad"] = ciudad
    if notas:
        campos["Notas_Bot"] = notas
    if presupuesto:
        campos["Presupuesto"] = presupuesto
    if subniche:
        campos["Sub_nicho"] = subniche
    if fuente_detalle:
        campos["Fuente"] = "meta_ads" if fuente_detalle.startswith("ad:") else "whatsapp_directo"
        campos["Fuente_Detalle"] = fuente_detalle

    # Activar seguimiento automático para leads caliente/tibio
    from datetime import timedelta
    if score in ("caliente", "tibio"):
        campos["Estado_Seguimiento"] = "activo"
        campos["Cantidad_Seguimientos"] = 0
        campos["Proximo_Seguimiento"] = (date.today() + timedelta(days=1)).isoformat()
        campos["Ultimo_Contacto_Bot"] = date.today().isoformat()

    if records:
        rec_id = records[0]["id"]
        r = requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS,
                           json={"fields": campos}, timeout=8)
        print(f"[ROBERT-AT] PATCH tel={telefono} status={r.status_code}")
    else:
        campos["Fecha_WhatsApp"] = date.today().isoformat()
        if "Estado" not in campos:
            campos["Estado"] = "no_contactado"
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        print(f"[ROBERT-AT] POST tel={telefono} status={r.status_code}")


# Mapa respuesta usuario → valor singleSelect Airtable
_PRESUPUESTO_MAP = {
    "1": "hata_50k",
    "2": "50k_100k",
    "3": "100k_200k",
    "4": "mas_200k",
}


def _at_guardar_email(telefono: str, email: str) -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    buscar = requests.get(url, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []
    if records:
        rec_id = records[0]["id"]
        requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS,
                       json={"fields": {"Email": email}}, timeout=8)
        print(f"[ROBERT-AT] Email guardado tel={telefono}")


# ─── CAL.COM ──────────────────────────────────────────────────────────────────
def _cal_disponible() -> bool:
    return bool(CAL_API_KEY and CAL_EVENT_ID)


def _cal_obtener_slots(dias: int = 7) -> list[dict]:
    """Retorna hasta 6 slots disponibles en los próximos N días (Cal.com API v2)."""
    if not _cal_disponible():
        return []
    from datetime import datetime, timedelta, timezone
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    end   = (datetime.now(timezone.utc) + timedelta(days=dias)).strftime("%Y-%m-%dT00:00:00Z")
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
        if r.status_code == 200:
            slots_raw = r.json().get("data", {})
            slots = []
            for fecha, lista in slots_raw.items():
                for slot in lista[:2]:
                    if slot.get("start"):
                        slots.append({"fecha": fecha, "time": slot["start"]})
            return slots[:6]
        print(f"[ROBERT-CAL] Error slots {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[ROBERT-CAL] Error slots: {e}")
    return []


def _cal_crear_reserva(nombre: str, email: str, telefono: str, slot_time: str, notas: str = "") -> dict:
    """Crea una reserva en Cal.com (API v2)."""
    if not _cal_disponible():
        return {"ok": False, "error": "Cal.com no configurado"}
    try:
        r = requests.post(
            "https://api.cal.com/v2/bookings",
            headers={
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-08-13",
                "Content-Type": "application/json",
            },
            json={
                "eventTypeId": int(CAL_EVENT_ID),
                "start": slot_time,
                "attendee": {
                    "name": nombre,
                    "email": email or (re.sub(r'\D', '', telefono) + "@lovbot.ai"),
                    "timeZone": CAL_TIMEZONE,
                    "language": "es",
                    "phoneNumber": "+" + re.sub(r'\D', '', telefono),
                },
                "metadata": {"fuente": "WhatsApp Bot Lovbot", "notas": notas[:200] if notas else ""},
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json().get("data", {})
            return {"ok": True, "uid": data.get("uid", ""), "start": data.get("start", slot_time)}
        print(f"[ROBERT-CAL] Error {r.status_code}: {r.text[:300]}")
        return {"ok": False, "error": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_DIAS_ES = {
    "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
    "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo",
}


def _formatear_slots(slots: list[dict]) -> str:
    """Formatea slots para mostrar en WhatsApp (en español)."""
    from datetime import datetime, timezone, timedelta
    lineas = []
    for i, s in enumerate(slots, 1):
        try:
            dt = datetime.fromisoformat(s["time"].replace("Z", "+00:00"))
            mx = dt.astimezone(timezone(timedelta(hours=_TZ_OFFSET_HOURS)))
            dia_en = mx.strftime("%A")
            dia_es = _DIAS_ES.get(dia_en, dia_en)
            lineas.append(f"*{i}️⃣* {dia_es} {mx.strftime('%d/%m')} a las *{mx.strftime('%H:%M')}* hs")
        except Exception:
            lineas.append(f"*{i}️⃣* {s['time']}")
    return "\n".join(lineas)


def _at_guardar_cita(telefono: str, fecha_cita: str) -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    buscar = requests.get(url, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []
    if records:
        rec_id = records[0]["id"]
        requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS,
                       json={"fields": {"Fecha_Cita": fecha_cita[:10], "Estado": "visita_agendada"}},
                       timeout=8)
        print(f"[ROBERT-AT] Cita guardada tel={telefono}")


def _at_buscar_propiedades(tipo: str = None, operacion: str = None,
                           zona: str = None, presupuesto: str = None) -> list[dict]:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return []
    filtros = ["OR({Disponible}='✅ Disponible',{Disponible}='⏳ Reservado')"]
    if tipo:
        filtros.append(f"LOWER({{Tipo}})='{tipo.lower()}'")
    if operacion:
        filtros.append(f"LOWER({{Operacion}})='{operacion.lower()}'")
    if zona and zona.lower() not in ("otra zona", "otra", "no sé", "no se"):
        filtros.append(f"{{Zona}}='{zona}'")
    if presupuesto and presupuesto in ("hata_50k", "50k_100k", "100k_200k", "mas_200k"):
        filtros.append(f"{{Presupuesto}}='{presupuesto}'")
    formula = "AND(" + ",".join(filtros) + ")" if len(filtros) > 1 else filtros[0]
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}"
    try:
        r = requests.get(url, headers=AT_HEADERS,
            params={"filterByFormula": formula, "maxRecords": 5,
                    "sort[0][field]": "Precio", "sort[0][direction]": "asc"}, timeout=8)
        return [rec["fields"] for rec in r.json().get("records", [])]
    except Exception as e:
        print(f"[ROBERT-AT] Error buscar props: {e}")
        return []


# ─── LLM (OpenAI principal → Gemini fallback) ───────────────────────────────

def _llm(prompt: str, system: str = "") -> str:
    """Llama a GPT-4o (principal) → Gemini 2.5 Flash (fallback)."""
    # ── OpenAI (principal) ──
    if OPENAI_API_KEY:
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o", "messages": messages, "temperature": 0.3, "max_tokens": 1500},
                timeout=15,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            print(f"[ROBERT-LLM] OpenAI error {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[ROBERT-LLM] OpenAI excepción: {e}")

    # ── Gemini (fallback) ──
    if _gemini_client:
        try:
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            resp = _gemini_client.models.generate_content(
                model="gemini-2.5-flash", contents=full_prompt)
            return resp.text.strip()
        except Exception as e:
            print(f"[ROBERT-LLM] Gemini fallback error: {e}")

    return ""


def _gemini(prompt: str) -> str:
    """Wrapper legacy — redirige a _llm."""
    return _llm(prompt)


def _interpretar_respuesta(texto: str, opciones: dict, contexto: str = "") -> str | None:
    """Usa GPT-4o para interpretar respuesta abierta y mapear a opción válida.
    opciones: {"1": "comprar", "2": "alquilar", "3": "invertir"}
    Retorna la key ("1", "2", etc.) o None si no matchea.
    """
    # Primero intentar match directo (si escribió el número)
    if texto.strip() in opciones:
        return texto.strip()

    # Intentar match por valor (si escribió la palabra)
    for key, val in opciones.items():
        if val.lower() in texto.lower() or texto.lower() in val.lower():
            return key

    # Si no matchea, usar LLM para interpretar
    opts_str = "\n".join([f"{k}: {v}" for k, v in opciones.items()])
    result = _llm(
        f"El usuario respondió: \"{texto}\"\n\nOpciones válidas:\n{opts_str}\n\n"
        f"¿A cuál opción corresponde? Respondé SOLO con el número de la opción. "
        f"Si no corresponde a ninguna, respondé 'null'.",
        system="Sos un clasificador. Respondé SOLO con el número o 'null'. Sin explicaciones."
    )
    result = result.strip().strip('"').strip("'")
    return result if result in opciones else None


def _gemini_calificar(sesion: dict) -> dict:
    zonas_str = "|".join(ZONAS_LIST)
    prompt = f"""Sos un analista comercial inmobiliario senior de {NOMBRE_EMPRESA} en {CIUDAD}.
Tu trabajo es clasificar leads con precisión para que el asesor no pierda tiempo con curiosos
y tampoco descarte leads tibios que pueden madurar.

Analizá las respuestas del lead y devolvé SOLO un JSON válido:
{{
  "score": "caliente|tibio|frio",
  "tipo": "casa|departamento|terreno|local|oficina|null",
  "zona": "{zonas_str}|null",
  "operacion": "venta|alquiler|null",
  "presupuesto_detectado": "alto|medio|bajo|sin_info",
  "derivar_sitio_web": true|false,
  "nota_para_asesor": "texto breve con lo más relevante del lead"
}}

Criterios de clasificación:
- CALIENTE: urgencia 1-2 (menos de 6 meses) + presupuesto definido. Asesor debe contactar HOY.
- TIBIO: interesado con intención clara pero sin urgencia inmediata O presupuesto indefinido.
  → derivar_sitio_web: false — mostrar propiedades y ofrecer cita igual, pueden madurar.
  → NUNCA marcar tibio como derivar_sitio_web true, son leads recuperables.
- FRÍO: urgencia 3-4 ("próximo año", "explorando") O respuestas evasivas sin intención clara.
  → derivar_sitio_web: true

Señales que elevan el score (aunque la urgencia sea baja):
- Mencionó zona específica (no "cualquiera" o "no sé")
- Preguntó por precio, cuota, financiamiento, escritura
- Tiene presupuesto definido (opciones 1-4)
- Mencionó familia, hijos, mudanza, proyecto concreto

Señales que bajan el score:
- Solo dijo "info", "quiero saber", sin contexto
- Eligió "explorando" + sin zona + sin presupuesto
- Respuestas de una sola palabra sin contexto

Nota para asesor: mencionar zona, tipo, urgencia real y cualquier señal de compra seria.
Si el lead preguntó por escritura, financiamiento o mencionó familia → indicarlo.

Respuestas del lead:
- Objetivo/intención: "{sesion.get('resp_objetivo', '')}"
- Tipo de propiedad: "{sesion.get('resp_tipo', '')}"
- Zona: "{sesion.get('resp_zona', '')}"
- Presupuesto: "{sesion.get('resp_presupuesto', '')}"
- Urgencia: "{sesion.get('resp_urgencia', '')}"

Devolvé SOLO el JSON, sin explicaciones."""
    try:
        texto = _llm(prompt, system="Sos un analista comercial inmobiliario. Respondé SOLO con JSON válido, sin markdown ni explicaciones.")
        # Limpiar backticks si los hay
        if "```" in texto:
            texto = texto.split("```")[1] if texto.startswith("```") else texto.split("```")[0]
            if texto.startswith("json"):
                texto = texto[4:]
        return json.loads(texto.strip())
    except Exception:
        return {"score": "tibio", "tipo": None, "zona": None, "operacion": None,
                "presupuesto_detectado": "sin_info", "derivar_sitio_web": False,
                "nota_para_asesor": "Error en calificación"}


def _pregunta(paso: str, nombre: str = "", subniche: str = "") -> str:
    """Preguntas adaptadas por subniche — sin llamadas a Gemini."""
    n = nombre.split()[0] if nombre else ""
    nt = f", {n}" if n else ""
    zonas_ops = "\n".join(f"{i+1}️⃣ {z}" for i, z in enumerate(ZONAS_LIST))
    ultimo_num = len(ZONAS_LIST) + 1

    # ── Desarrolladora: el cliente compra unidades de proyecto ────────────
    if subniche == "desarrolladora":
        msgs = {
            "objetivo": (
                f"Perfecto{nt}, con gusto le ayudo 😊\n\n"
                f"¿Qué le interesa de nuestros proyectos?\n\n"
                f"*1️⃣* 🏠 Comprar una unidad en preventa\n"
                f"*2️⃣* 🌿 Adquirir un lote / terreno\n"
                f"*3️⃣* 📈 Invertir en un proyecto inmobiliario\n\n"
                f"_(También puede escribirme libremente)_"
            ),
            "tipo": (
                f"¡Excelente{nt}! 🌟\n\n"
                f"¿Qué tipo de unidad le interesa?\n\n"
                f"*1️⃣* 🏡 Casa en proyecto residencial\n"
                f"*2️⃣* 🏢 Departamento / Apartamento\n"
                f"*3️⃣* 🌿 Lote / Terreno urbanizado\n"
                f"*4️⃣* 🏪 Local comercial en desarrollo\n"
                f"*5️⃣* 💼 Oficina en edificio nuevo\n\n"
                f"_(También puede describirme lo que busca)_"
            ),
            "zona": (
                f"Entendido{nt} 📍\n\n"
                f"¿En qué zona de *{CIUDAD}* le interesa nuestro proyecto?\n\n"
                f"{zonas_ops}\n"
                f"{ultimo_num}️⃣ 🗺️ Otra zona / Me es indiferente\n\n"
                f"_(Puede escribir la zona directamente)_"
            ),
            "presupuesto": (
                f"Perfecto{nt} 💰\n\n"
                f"¿Con qué rango de inversión cuenta?\n\n"
                f"*1️⃣* Menos de 50,000 {MONEDA}\n"
                f"*2️⃣* 50,000 — 100,000 {MONEDA}\n"
                f"*3️⃣* 100,000 — 200,000 {MONEDA}\n"
                f"*4️⃣* Más de 200,000 {MONEDA}\n"
                f"*5️⃣* 💬 Prefiero hablarlo con el asesor comercial\n\n"
                f"_(Una referencia es suficiente para orientarlo mejor)_"
            ),
            "urgencia": (
                f"¡Casi terminamos{nt}! 🙌\n\n"
                f"¿En qué etapa de compra se encuentra?\n\n"
                f"*1️⃣* 🔥 Listo para reservar — quiero asegurar precio de preventa\n"
                f"*2️⃣* 📅 Decidiendo en los próximos 6 meses\n"
                f"*3️⃣* 🗓️ Planifico para el próximo año\n"
                f"*4️⃣* 🔍 Estoy explorando proyectos y comparando"
            ),
        }
        return msgs[paso]

    # ── Agencia / Agente Independiente (flujo estándar) ──────────────────
    msgs = {
        "objetivo": (
            f"Perfecto{nt}, con gusto le ayudo 😊\n\n"
            f"Para mostrarle las mejores opciones, ¿qué está buscando?\n\n"
            f"*1️⃣* 🏠 Comprar una propiedad\n"
            f"*2️⃣* 🔑 Alquilar una propiedad\n"
            f"*3️⃣* 📈 Invertir en bienes raíces\n\n"
            f"_(También puede escribirme libremente)_"
        ),
        "tipo": (
            f"¡Excelente elección{nt}! 🌟\n\n"
            f"¿Qué tipo de propiedad está buscando?\n\n"
            f"*1️⃣* 🏡 Casa\n"
            f"*2️⃣* 🏢 Departamento / Apartamento\n"
            f"*3️⃣* 🌿 Terreno\n"
            f"*4️⃣* 🏪 Local comercial\n"
            f"*5️⃣* 💼 Oficina\n\n"
            f"_(También puede describirme lo que busca)_"
        ),
        "zona": (
            f"Entendido{nt} 📍\n\n"
            f"¿En qué zona de *{CIUDAD}* le interesa buscar?\n\n"
            f"{zonas_ops}\n"
            f"{ultimo_num}️⃣ 🗺️ Otra zona / Aún no lo sé\n\n"
            f"_(Puede escribir el nombre de la zona directamente)_"
        ),
        "presupuesto": (
            f"Perfecto{nt} 💰\n\n"
            f"¿Con qué rango de presupuesto cuenta aproximadamente?\n\n"
            f"*1️⃣* Menos de 50,000 {MONEDA}\n"
            f"*2️⃣* 50,000 — 100,000 {MONEDA}\n"
            f"*3️⃣* 100,000 — 200,000 {MONEDA}\n"
            f"*4️⃣* Más de 200,000 {MONEDA}\n"
            f"*5️⃣* 💬 Prefiero hablarlo con el asesor\n\n"
            f"_(No hace falta que sea exacto, una referencia es suficiente)_"
        ),
        "urgencia": (
            f"¡Casi terminamos{nt}! 🙌\n\n"
            f"¿En qué tiempo está pensando concretar?\n\n"
            f"*1️⃣* 🔥 Lo antes posible — 1 a 3 meses\n"
            f"*2️⃣* 📅 En los próximos 6 meses\n"
            f"*3️⃣* 🗓️ Durante el próximo año\n"
            f"*4️⃣* 🔍 Estoy explorando opciones por ahora"
        ),
    }
    return msgs[paso]


# ─── FORMATEO PROPIEDADES ─────────────────────────────────────────────────────
def _lista_titulos(props: list[dict]) -> str:
    lineas = ["🏘️ *PROPIEDADES DISPONIBLES PARA USTED*\n"]
    for i, p in enumerate(props, 1):
        precio = p.get("Precio", 0)
        moneda = p.get("Moneda", MONEDA)
        precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar precio"
        estado = p.get("Disponible", "")
        tag = " ⏳ _Reservada_" if "Reservado" in str(estado) else " ✅"
        tipo = p.get("Tipo", "")
        zona = p.get("Zona", "")
        tipo_zona = f" · {tipo}" if tipo else ""
        if zona:
            tipo_zona += f" · {zona}"
        lineas.append(f"*{i}.* 🏠 {p.get('Titulo', 'Propiedad')}{tipo_zona}\n    💰 {precio_str}{tag}")
    lineas.append(
        "\n📲 Responda con el *número* de la propiedad para ver todos los detalles y fotos.\n\n"
        "*0* 🔄 Ver otras opciones  |  *#* 👤 Hablar con el asesor"
    )
    return "\n".join(lineas)


def _ficha_propiedad(p: dict) -> str:
    precio = p.get("Precio", 0)
    moneda = p.get("Moneda", MONEDA)
    precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar precio"
    estado = p.get("Disponible", "✅ Disponible")
    es_reservado = "Reservado" in str(estado)
    titulo = p.get("Titulo", "Propiedad")
    lineas = [f"🏠 *{titulo}*"]
    if es_reservado:
        lineas.append("⏳ *RESERVADO* — Puede anotarse por si se libera\n")
    else:
        lineas.append("")
    desc = p.get("Descripcion", "")
    if desc:
        lineas.append(f"{desc}\n")
    lineas.append(f"💰 *Precio:* {precio_str}")
    operacion = p.get("Operacion", "")
    if operacion:
        lineas.append(f"📋 *Operación:* {operacion.capitalize()}")
    tipo = p.get("Tipo", "")
    if tipo:
        lineas.append(f"🏡 *Tipo:* {tipo}")
    dorm = p.get("Dormitorios", "")
    banios = p.get("Banos", "")
    metros_c = p.get("Metros_Cubiertos", "")
    metros_t = p.get("Metros_Terreno", "")
    if dorm:
        lineas.append(f"🛏 *Dormitorios:* {dorm}")
    if banios:
        lineas.append(f"🚿 *Baños:* {banios}")
    if metros_c:
        lineas.append(f"📐 *Sup. cubierta:* {metros_c}m²")
    if metros_t:
        lineas.append(f"🌿 *Terreno:* {metros_t}m²")
    zona = p.get("Zona", "")
    if zona:
        lineas.append(f"📍 *Zona:* {zona}")
    maps = p.get("Google_Maps_URL", "")
    if maps:
        lineas.append(f"\n🗺 *Ver en Maps:* {maps}")
    lineas.append(
        f"\n¿Le interesa esta propiedad? 😊\n\n"
        f"*#* 👤 Hablar con {NOMBRE_ASESOR}  |  *0* 🔄 Ver otras propiedades"
    )
    return "\n".join(lineas)


def _enviar_ficha(telefono: str, p: dict) -> None:
    img_field = p.get("Imagen_URL", "")
    if isinstance(img_field, list) and img_field:
        img = img_field[0].get("url", "")
    elif isinstance(img_field, str):
        img = img_field
    else:
        img = ""
    if img:
        _enviar_imagen(telefono, img, caption=p.get("Titulo", ""))
    _enviar_texto(telefono, _ficha_propiedad(p))


# ─── NOTIFICACIONES ──────────────────────────────────────────────────────────
def _notificar_asesor(telefono: str, sesion: dict, calificacion: dict) -> None:
    if not NUMERO_ASESOR:
        return
    nombre = sesion.get("nombre", telefono)
    score = calificacion.get("score", "tibio")
    emoji = {"caliente": "🔥", "tibio": "🌡️", "frio": "🧊"}.get(score, "📋")
    nota = calificacion.get("nota_para_asesor", "")
    tipo = calificacion.get("tipo") or sesion.get("resp_tipo", "")
    zona = calificacion.get("zona") or sesion.get("resp_zona", "")
    msg = (
        f"{emoji} *Nuevo Lead — {NOMBRE_EMPRESA}*\n\n"
        f"👤 *Nombre:* {nombre}\n"
        f"📱 *WhatsApp:* +{re.sub(r'[^0-9]', '', telefono)}\n"
        f"📊 *Score:* {score.upper()}\n"
    )
    if tipo:
        msg += f"🏡 *Busca:* {tipo}\n"
    if zona:
        msg += f"📍 *Zona:* {zona}\n"
    msg += f"📝 *Nota:* {nota}"
    _enviar_texto(NUMERO_ASESOR, msg)


# ─── MENSAJES FIJOS ───────────────────────────────────────────────────────────
MSG_SUBNICHO = (
    "¡Hola! 👋 Bienvenido/a a *{empresa}* — la plataforma de automatización "
    "inmobiliaria con WhatsApp + IA 🤖🏡\n\n"
    "Para mostrarte cómo funciona el bot según tu perfil, dime:\n\n"
    "*1️⃣* 🏢 Soy *Agencia Inmobiliaria* (equipo de asesores)\n"
    "*2️⃣* 🧑‍💼 Soy *Agente Independiente* (trabajo solo)\n"
    "*3️⃣* 🏗️ Soy *Desarrolladora / Constructora*\n\n"
    "_(Elige una opción para ver la demo de tu subniche)_"
)

MSG_BIENVENIDA = (
    "¡Hola! 👋 Bienvenido/a a *{empresa}*.\n\n"
    "Para no hacerle perder el tiempo, le voy a hacer *4 preguntas rápidas* "
    "y le muestro las propiedades que mejor encajan con lo que busca. ⚡\n\n"
    "¿Me dice su nombre para llamarle bien? 😊"
)

# Contexto por subniche (adapta nombre empresa, copy y asesor)
_SUBNICHO_CONFIG = {
    "1": {
        "subniche": "agencia_inmobiliaria",
        "label": "Agencia Inmobiliaria",
        "empresa": "Lovbot — Agencia Inmobiliaria",
        "intro": "💼 *Agencia Inmobiliaria*\n\nEsta demo muestra cómo el bot filtra leads y los distribuye entre tu equipo de asesores automáticamente.",
    },
    "2": {
        "subniche": "agente_independiente",
        "label": "Agente Independiente",
        "empresa": "Lovbot — Agente Inteligente",
        "intro": "🧑‍💼 *Agente Independiente*\n\nEsta demo muestra cómo el bot trabaja 24/7 por vos, califica leads y agenda citas mientras te enfocás en cerrar ventas.",
    },
    "3": {
        "subniche": "desarrolladora",
        "label": "Desarrolladora / Constructora",
        "empresa": "Lovbot — Desarrollos Inmobiliarios",
        "intro": "🏗️ *Desarrolladora / Constructora*\n\nEste bot atiende a compradores interesados en tus proyectos: preventa, lotes urbanizados, unidades en construcción. Filtra inversores serios, califica por presupuesto y agenda reuniones con tu equipo comercial.",
    },
}

MSG_SITIO_WEB = (
    "¡Muchas gracias por su tiempo, *{nombre}*! 🙏\n\n"
    "Entendemos perfectamente — tomarse el tiempo para explorar es lo más inteligente "
    "al momento de invertir en una propiedad. 😊\n\n"
    "Mientras tanto, le invitamos a conocer nuestro portafolio completo con propiedades, "
    "precios y disponibilidad actualizada:\n\n"
    "{web_line}"
    "Cuando esté listo para dar el siguiente paso, escríbanos *hola* aquí mismo y "
    "nuestro asesor *{asesor}* le ayudará personalmente. ¡Estamos para servirle! 🏡"
)

MSG_ASESOR_CONTACTO = (
    "¡Muchas gracias, {nombre}! 🎉\n\n"
    "Con la información que nos compartió, nuestro asesor *{asesor}* "
    "se pondrá en contacto con usted a la brevedad para presentarle "
    "las mejores opciones disponibles. 🏠\n\n"
    "Mientras tanto, si tiene alguna pregunta adicional, estoy aquí para ayudarle.\n\n"
    "¡Gracias por confiar en *{empresa}*! 🌟"
)

MSG_EMAIL_CTA = (
    "📬 *Una última cosa, {nombre}...*\n\n"
    "En *{empresa}* publicamos nuevas propiedades con frecuencia — "
    "algunas se reservan en días por sus precios de lanzamiento. 🏷️\n\n"
    "¿Le gustaría que le avisemos cuando salga algo que coincida con lo que busca? "
    "Solo necesito su *correo electrónico* para enviarle información "
    "exclusiva antes de que salga al público.\n\n"
    "_(Opcional — responda con su email o escriba *\"no\"* si prefiere no recibirlo)_"
)


# ─── FLUJO PRINCIPAL ──────────────────────────────────────────────────────────
def _procesar(telefono: str, texto: str, referral: dict = None) -> None:
    referral = referral or {}
    # Si el asesor tomó control, el bot NO responde
    if bot_pausado(telefono):
        print(f"[ROBERT] Bot pausado para {telefono} — asesor activo, ignorando mensaje")
        return

    # Guardar referral en sesión si es nuevo lead (para Caso A)
    if referral and telefono not in SESIONES:
        print(f"[ROBERT] Lead desde anuncio: {referral.get('source_url', referral.get('body', ''))}")

    # Registrar mensaje del lead en historial
    _agregar_historial(telefono, "Lead", texto)

    # Si lead estaba en seguimiento/dormido y responde → desactivar seguimiento
    def _desactivar_seguimiento():
        if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
            buscar = requests.get(url, headers=AT_HEADERS,
                params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
            records = buscar.json().get("records", []) if buscar.status_code == 200 else []
            if records:
                estado_seg = records[0].get("fields", {}).get("Estado_Seguimiento", "")
                if estado_seg in ("activo", "dormido"):
                    requests.patch(f"{url}/{records[0]['id']}", headers=AT_HEADERS,
                        json={"fields": {"Estado_Seguimiento": "pausado"}}, timeout=8)
                    print(f"[ROBERT] Lead {telefono} respondió — seguimiento pausado (era {estado_seg})")
    threading.Thread(target=_desactivar_seguimiento, daemon=True).start()

    # Actualizar última interacción en Airtable (async para no bloquear)
    def _update_interaccion():
        from datetime import datetime, timezone
        if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
            buscar = requests.get(url, headers=AT_HEADERS,
                params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
            records = buscar.json().get("records", []) if buscar.status_code == 200 else []
            if records:
                requests.patch(f"{url}/{records[0]['id']}", headers=AT_HEADERS,
                    json={"fields": {"fecha_ultimo_contacto": datetime.now(timezone.utc).isoformat()}}, timeout=8)
    threading.Thread(target=_update_interaccion, daemon=True).start()

    import time as _time

    texto = texto.strip()
    texto_lower = texto.lower()
    sesion = SESIONES.get(telefono, {})
    step = sesion.get("step", "inicio")
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""
    subniche = sesion.get("subniche", "")

    # ── Detección de caída: si pasaron >30 min desde último mensaje ────────
    SESSION_TIMEOUT = 30 * 60  # 30 minutos
    ultimo_ts = sesion.get("_ultimo_ts", 0)
    ahora_ts = _time.time()

    if ultimo_ts and step not in ("inicio", "subnicho") and (ahora_ts - ultimo_ts) > SESSION_TIMEOUT:
        # Lead volvió después de mucho tiempo → modo recuperación
        if nombre:
            _enviar_texto(telefono,
                f"¡Hola de nuevo, *{nombre_corto}*! 👋\n\n"
                f"¿Seguís interesado en las propiedades que estuvimos viendo?\n\n"
                f"*1️⃣* Sí, quiero retomar\n"
                f"*2️⃣* Quiero ver otras opciones\n"
                f"*3️⃣* Quiero hablar con *{NOMBRE_ASESOR}*\n"
                f"*0️⃣* Empezar de nuevo"
            )
            SESIONES[telefono] = {**sesion, "step": "recuperacion", "_ultimo_ts": ahora_ts}
            return

    # Actualizar timestamp de sesión
    if telefono in SESIONES:
        SESIONES[telefono]["_ultimo_ts"] = ahora_ts

    # ── Step recuperación ─────────────────────────────────────────────────
    if step == "recuperacion":
        if texto_lower in ("1", "si", "sí"):
            # Retomar desde donde estaba
            prev_step = sesion.get("_prev_step", "inicio")
            SESIONES[telefono] = {**sesion, "step": prev_step, "_ultimo_ts": ahora_ts}
            _enviar_texto(telefono, f"¡Perfecto, *{nombre_corto}*! Retomamos donde quedamos. 🏡")
            return
        elif texto_lower in ("2", "otras", "opciones"):
            SESIONES.pop(telefono, None)
            SESIONES[telefono] = {"step": "objetivo", "nombre": nombre, "subniche": subniche, "_ultimo_ts": ahora_ts}
            _enviar_texto(telefono, _pregunta("objetivo", nombre, subniche))
            return
        elif texto_lower in ("3", "#"):
            _ir_asesor(telefono, sesion)
            return
        else:
            SESIONES.pop(telefono, None)
            step = "inicio"

    # Guardar step previo para recuperación
    if step not in ("inicio", "subnicho", "recuperacion"):
        SESIONES.get(telefono, {})["_prev_step"] = step

    # Comandos globales
    if texto_lower in ("0", "menú", "menu", "inicio", "hola", "hi", "buenas"):
        SESIONES.pop(telefono, None)
        SESIONES[telefono] = {"step": "subnicho", "_ultimo_ts": ahora_ts}
        _enviar_texto(telefono, MSG_SUBNICHO.format(empresa=NOMBRE_EMPRESA))
        return

    if texto_lower == "#":
        _ir_asesor(telefono, sesion)
        return

    # ── CASO A: Lead desde anuncio específico (Meta Ads referral) ────────────
    if step == "inicio" and referral and (referral.get("source_url") or referral.get("body")):
        ad_source = referral.get("source_url", "")
        ad_body = referral.get("body", "")
        ad_headline = referral.get("headline", "")
        fuente_detalle = f"ad:{referral.get('source_id', '')}|{ad_headline[:50]}" if referral.get("source_id") else f"referral:{ad_source[:80]}"

        SESIONES[telefono] = {
            "step": "nombre", "_ultimo_ts": ahora_ts,
            "subniche": "agencia_inmobiliaria",
            "_referral": referral,
            "_fuente_detalle": fuente_detalle,
        }
        # Respuesta contextual con info del anuncio
        intro = ad_headline or ad_body or "la propiedad que viste"
        _enviar_texto(telefono,
            f"¡Hola! 👋 Gracias por tu interés en *{intro}*.\n\n"
            f"Soy el asistente de *{NOMBRE_EMPRESA}*. "
            f"Para darte la mejor atención, ¿me decís tu *nombre*?"
        )
        return

    # ── INICIO → MENÚ SUBNICHO (Caso B: lead genérico) ───────────────────────
    if step == "inicio":
        SESIONES[telefono] = {"step": "subnicho", "_ultimo_ts": ahora_ts}
        _enviar_texto(telefono, MSG_SUBNICHO.format(empresa=NOMBRE_EMPRESA))
        return

    # ── SUBNICHO ──────────────────────────────────────────────────────────────
    if step == "subnicho":
        cfg = _SUBNICHO_CONFIG.get(texto.strip())
        if not cfg:
            _enviar_texto(telefono,
                "Por favor elige una opción:\n\n"
                "*1️⃣* Agencia Inmobiliaria\n"
                "*2️⃣* Agente Independiente\n"
                "*3️⃣* Desarrolladora / Constructora"
            )
            return
        SESIONES[telefono] = {
            "step": "nombre",
            "subniche": cfg["subniche"],
            "empresa_demo": cfg["empresa"],
        }
        empresa_show = cfg["empresa"]
        _enviar_texto(telefono,
            cfg["intro"] + f"\n\n"
            f"Perfecto 🎯 Ahora simulás ser un *cliente real* que escribe a *{empresa_show}*.\n\n"
            f"¡Empecemos! — ¿cuál es tu nombre? 😊"
        )
        return

    # ── Detector de objeción familiar (cualquier paso post-nombre) ───────────
    _OBJECION_FAMILIAR = (
        "lo hablo con", "lo consulto con", "lo veo con", "lo comento con",
        "mi esposa", "mi esposo", "mi marido", "mi pareja", "mi socio", "mi socia",
        "mi papa", "mi papá", "mi mama", "mi mamá", "mi hijo", "mi hija",
        "tengo que consultar", "tenemos que ver", "lo decidimos juntos"
    )
    if step not in ("inicio", "subnicho", "nombre") and any(p in texto_lower for p in _OBJECION_FAMILIAR):
        n = nombre_corto or nombre or "estimado/a"
        _enviar_texto(telefono,
            f"¡Por supuesto, *{n}*! Es una decisión importante y está muy bien consultarlo. 😊\n\n"
            f"Le mando la información para que la puedan revisar juntos 👇\n\n"
            f"¿Le gustaría que *{NOMBRE_ASESOR}* los llame cuando estén los dos disponibles, "
            f"o prefieren seguir por aquí a su ritmo?"
        )
        # No reseteamos sesión — esperamos su respuesta y continuamos
        SESIONES[telefono] = {**sesion, "step": sesion.get("step", step), "_espera_familiar": True}
        return

    # Si venía de objeción familiar y responde, retomamos el flujo donde estaba
    if sesion.get("_espera_familiar"):
        SESIONES[telefono] = {**{k: v for k, v in sesion.items() if k != "_espera_familiar"}}
        sesion = SESIONES[telefono]
        step = sesion.get("step", "inicio")
        n = nombre_corto or nombre
        if "asesor" in texto_lower or "llame" in texto_lower or "llamada" in texto_lower or texto.strip() in ("1", "si", "sí"):
            _ir_asesor(telefono, sesion)
            return
        _enviar_texto(telefono,
            f"¡Perfecto, *{n}*! Sin apuro. Seguimos cuando quieran 😊\n\n"
            f"Retomamos donde lo dejamos — " + _pregunta(step, nombre_corto, subniche)
        )
        return

    # ── NOMBRE ────────────────────────────────────────────────────────────────
    if step == "nombre":
        nombre = texto.title()
        SESIONES[telefono] = {**sesion, "step": "email", "nombre": nombre}
        n = nombre.split()[0]
        _enviar_texto(telefono,
            f"¡Mucho gusto, *{n}*! 😊\n\n"
            f"¿Me comparte su *correo electrónico*? Lo usamos para enviarle fichas "
            f"de propiedades antes de que salgan al público. 📬\n\n"
            f"_(Escriba *no* si prefiere omitirlo)_"
        )
        return

    # ── EMAIL ─────────────────────────────────────────────────────────────────
    if step == "email":
        rechazos = ("no", "no gracias", "nop", "nel", "paso", "no quiero", "omitir", "sin email")
        if texto_lower in rechazos:
            SESIONES[telefono] = {**sesion, "step": "ciudad", "email": ""}
            _enviar_texto(telefono,
                f"Sin problema 😊 ¿Desde qué *ciudad* nos escribe? 📍"
            )
        elif "@" in texto and "." in texto:
            email = texto.strip()
            threading.Thread(target=_at_guardar_email, args=(telefono, email), daemon=True).start()
            SESIONES[telefono] = {**sesion, "step": "ciudad", "email": email}
            _enviar_texto(telefono,
                f"¡Perfecto! 📬 Anotado.\n\n¿Desde qué *ciudad* nos escribe? 📍"
            )
        else:
            _enviar_texto(telefono,
                f"Por favor ingrese un email válido (ej: nombre@gmail.com) o escriba *no* para omitir. 😊"
            )
        return

    # ── CIUDAD ────────────────────────────────────────────────────────────────
    if step == "ciudad":
        ciudad_resp = texto.strip().title()
        SESIONES[telefono] = {**sesion, "step": "objetivo", "ciudad_resp": ciudad_resp}
        _enviar_texto(telefono,
            f"📍 *{ciudad_resp}*, anotado.\n\n" + _pregunta("objetivo", nombre, subniche)
        )
        return

    # ── OBJETIVO (comprar/alquilar + para qué) ────────────────────────────────
    _ACUSE_OBJETIVO = {
        "1": "Comprar, perfecto. 🏠",
        "2": "Alquilar, entendido. 🔑",
        "3": "Invertir, excelente decisión. 📈",
    }
    if step == "objetivo":
        mapa_op = {"1": "comprar", "2": "alquilar", "3": "invertir"}
        opcion = _interpretar_respuesta(texto, mapa_op)
        if not opcion:
            opcion = "1"  # default: comprar
        operacion_map = {"1": "venta", "2": "alquiler", "3": "venta"}
        operacion = operacion_map.get(opcion, "venta")
        acuse = _ACUSE_OBJETIVO.get(opcion, "Entendido. 👍")
        SESIONES[telefono] = {**sesion, "step": "tipo", "resp_objetivo": texto,
                              "operacion_at": operacion}
        _enviar_texto(telefono, acuse + "\n\n" + _pregunta("tipo", nombre_corto, subniche))
        return

    # ── TIPO DE PROPIEDAD ─────────────────────────────────────────────────────
    _ACUSE_TIPO = {
        "1": "Casa, perfecto. 🏡",
        "2": "Departamento, anotado. 🏢",
        "3": "Terreno, muy bien. 🌿",
        "4": "Local comercial, entendido. 🏪",
        "5": "Oficina, anotado. 💼",
    }
    if step == "tipo":
        mapa_tipo = {"1": "casa", "2": "departamento", "3": "terreno", "4": "local comercial", "5": "oficina"}
        opcion = _interpretar_respuesta(texto, mapa_tipo)
        if opcion:
            tipo_final = {"1": "casa", "2": "departamento", "3": "terreno", "4": "otro", "5": "otro"}.get(opcion, "otro")
            acuse = _ACUSE_TIPO.get(opcion, "Entendido. 👍")
        else:
            tipo_final = _normalizar_tipo(texto) or texto.lower()
            acuse = "Entendido. 👍"
        SESIONES[telefono] = {**sesion, "step": "zona", "resp_tipo": tipo_final}
        _enviar_texto(telefono, acuse + "\n\n" + _pregunta("zona", nombre_corto, subniche))
        return

    # ── ZONA ──────────────────────────────────────────────────────────────────
    if step == "zona":
        zona_detectada = texto
        zona_label = texto
        try:
            idx = int(texto) - 1
            if 0 <= idx < len(ZONAS_LIST):
                zona_detectada = ZONAS_LIST[idx]
                zona_label = ZONAS_LIST[idx]
            elif idx == len(ZONAS_LIST):
                zona_detectada = ""
                zona_label = "cualquier zona"
        except ValueError:
            zona_detectada = _normalizar_zona(texto) or texto
            zona_label = zona_detectada
        acuse_zona = f"📍 *{zona_label}*, anotado." if zona_label != "cualquier zona" else "Sin zona preferida, le muestro todo lo disponible."
        SESIONES[telefono] = {**sesion, "step": "presupuesto", "resp_zona": zona_detectada}
        _enviar_texto(telefono, acuse_zona + "\n\n" + _pregunta("presupuesto", nombre_corto, subniche))
        return

    # ── PRESUPUESTO ───────────────────────────────────────────────────────────
    if step == "presupuesto":
        mapa_presu = {
            "1": f"menos de 50,000 {MONEDA}",
            "2": f"50,000 a 100,000 {MONEDA}",
            "3": f"100,000 a 200,000 {MONEDA}",
            "4": f"más de 200,000 {MONEDA}",
            "5": "hablar con asesor",
        }
        opcion = _interpretar_respuesta(texto, mapa_presu)
        if opcion == "5":
            _ir_asesor(telefono, sesion)
            return
        presupuesto_at = _PRESUPUESTO_MAP.get(opcion or texto.strip(), "")
        SESIONES[telefono] = {**sesion, "step": "urgencia",
                              "resp_presupuesto": texto, "presupuesto_at": presupuesto_at}
        _enviar_texto(telefono, _pregunta("urgencia", nombre_corto, subniche))
        return

    # ── URGENCIA → CALIFICAR → BUSCAR PROPIEDADES ─────────────────────────────
    if step == "urgencia":
        sesion_act = {**sesion, "step": "calificado", "resp_urgencia": texto}
        SESIONES[telefono] = sesion_act

        calificacion = _gemini_calificar(sesion_act)
        score      = calificacion.get("score", "tibio")
        derivar    = calificacion.get("derivar_sitio_web", False)
        tipo       = calificacion.get("tipo") or sesion_act.get("resp_tipo", "")
        zona       = calificacion.get("zona") or sesion_act.get("resp_zona", "")
        operacion  = calificacion.get("operacion")
        nota       = calificacion.get("nota_para_asesor", "")

        # Normalizar nulls de Gemini
        if tipo in (None, "null", ""):
            tipo = sesion_act.get("resp_tipo", "")
        if zona in (None, "null", ""):
            zona = sesion_act.get("resp_zona", "")
        if operacion in (None, "null", ""):
            operacion = sesion_act.get("operacion_at", None)

        presupuesto_at = sesion_act.get("presupuesto_at", "")
        operacion_at   = sesion_act.get("operacion_at", "")
        ciudad_at      = sesion_act.get("ciudad_resp", CIUDAD)
        subniche_at    = sesion_act.get("subniche", "")
        email          = sesion_act.get("email", "")

        # Registrar lead en Airtable (background)
        fuente_det = sesion_act.get("_fuente_detalle", "")
        threading.Thread(
            target=_at_registrar_lead,
            args=(telefono, nombre, score, tipo, zona, nota, presupuesto_at,
                  operacion_at, ciudad_at, subniche_at, fuente_det), daemon=True
        ).start()

        # Lead frío → derivar a sitio web + activar nurturing automático
        if derivar or score == "frio":
            web_line = f"🌐 *{SITIO_WEB}*\n\n" if SITIO_WEB else ""
            _enviar_texto(telefono, MSG_SITIO_WEB.format(
                nombre=nombre_corto or nombre, web_line=web_line,
                asesor=NOMBRE_ASESOR))
            threading.Thread(
                target=_notificar_asesor,
                args=(telefono, sesion_act, calificacion), daemon=True
            ).start()
            # Escalar a Chatwoot con score label
            threading.Thread(
                target=_chatwoot_escalar,
                args=(telefono, sesion_act, calificacion), daemon=True
            ).start()
            # Activar seguimiento para leads fríos también (nurturing)
            def _activar_nurturing():
                from datetime import date, timedelta
                if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
                    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
                    buscar = requests.get(url, headers=AT_HEADERS,
                        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
                    records = buscar.json().get("records", []) if buscar.status_code == 200 else []
                    if records:
                        requests.patch(f"{url}/{records[0]['id']}", headers=AT_HEADERS,
                            json={"fields": {
                                "Estado_Seguimiento": "activo",
                                "Cantidad_Seguimientos": 0,
                                "Proximo_Seguimiento": (date.today() + timedelta(days=3)).isoformat(),
                            }}, timeout=8)
            threading.Thread(target=_activar_nurturing, daemon=True).start()
            SESIONES.pop(telefono, None)
            return

        # Lead caliente/tibio → buscar propiedades en Airtable
        props = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona,
                                       presupuesto=presupuesto_at)

        threading.Thread(
            target=_notificar_asesor,
            args=(telefono, sesion_act, calificacion), daemon=True
        ).start()
        # Actualizar labels en Chatwoot con score
        threading.Thread(
            target=_chatwoot_escalar,
            args=(telefono, sesion_act, calificacion), daemon=True
        ).start()

        if not props:
            _enviar_texto(telefono,
                f"*{nombre_corto or nombre}*, en este momento no tenemos propiedades "
                f"con exactamente esas características en nuestro portal, "
                f"pero *{NOMBRE_ASESOR}* trabaja con opciones que no siempre están publicadas. 🏡\n\n"
                f"Le coordino una reunión rápida para que le cuente lo que hay disponible."
            )
            # Ir directo a Cal.com si hay slots
            if _cal_disponible():
                email = sesion_act.get("email", "")
                slots = _cal_obtener_slots()
                if slots:
                    SESIONES[telefono] = {**sesion_act, "step": "ofrecer_cita",
                                          "slots": slots, "email": email}
                    _enviar_texto(telefono,
                        f"¿Prefiere ver los horarios disponibles con *{NOMBRE_ASESOR}* "
                        f"ahora mismo, o que él se contacte con usted?\n\n"
                        f"*1️⃣* Ver horarios disponibles 📅\n"
                        f"*0️⃣* Que me contacten a la brevedad"
                    )
                    return
            # Sin Cal.com o sin slots → despedida con asesor
            _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
                nombre=nombre_corto or nombre, asesor=NOMBRE_ASESOR, empresa=NOMBRE_EMPRESA))
            pausar_bot(telefono)
            SESIONES.pop(telefono, None)
            return
        else:
            # Mostrar las 2 mejores propiedades primero (no saturar)
            props_iniciales = props[:2]
            props_restantes = props[2:]
            SESIONES[telefono] = {**sesion_act, "step": "lista", "props": props_iniciales,
                                  "props_extra": props_restantes,
                                  "tipo": tipo, "zona": zona, "operacion": operacion}
            _enviar_texto(telefono,
                f"*{nombre_corto or nombre}*, encontré opciones que coinciden con lo que busca. "
                f"Le muestro las *{len(props_iniciales)} mejores* 👇"
            )
            _enviar_texto(telefono, _lista_titulos(props_iniciales))
            if props_restantes:
                _enviar_texto(telefono,
                    f"Tengo *{len(props_restantes)} opción{'es' if len(props_restantes) > 1 else ''}* más. "
                    f"Escriba *+* si desea verlas.")
            return  # queda en step lista para que elija ficha

        # Ofrecer cita con Cal.com — primero pregunta binaria, luego slots
        if _cal_disponible():
            slots = _cal_obtener_slots()
            if slots:
                SESIONES[telefono] = {**sesion_act, "step": "ofrecer_cita",
                                      "slots": slots, "email": email}
                _enviar_texto(telefono,
                    f"¿Prefiere que *{NOMBRE_ASESOR}* lo llame *hoy* o *mañana* para "
                    f"mostrarle opciones personalizadas?\n\n"
                    f"*1️⃣* Ver horarios disponibles 📅\n"
                    f"*0️⃣* Que me contacten ellos a la brevedad"
                )
                return

        # Sin Cal.com → despedida
        _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
            nombre=nombre_corto or nombre,
            asesor=NOMBRE_ASESOR,
            empresa=NOMBRE_EMPRESA,
        ))
        SESIONES.pop(telefono, None)
        return

    # ── LISTA → FICHA ─────────────────────────────────────────────────────────
    if step == "lista":
        props = sesion.get("props", [])
        props_extra = sesion.get("props_extra", [])

        # "+" → mostrar más propiedades
        if texto.strip() == "+" and props_extra:
            props_todas = props + props_extra
            SESIONES[telefono] = {**sesion, "step": "lista", "props": props_todas, "props_extra": []}
            _enviar_texto(telefono, f"Estas son las *{len(props_extra)} opciones adicionales* 👇")
            _enviar_texto(telefono, _lista_titulos(props_todas))
            return

        try:
            idx = int(texto) - 1
            if 0 <= idx < len(props):
                prop = props[idx]
                SESIONES[telefono] = {**sesion, "step": "ficha", "ficha_actual": idx}
                _enviar_ficha(telefono, prop)
                # Guardar propiedad de interés en Airtable (async)
                prop_nombre = f"{prop.get('Tipo', '')} {prop.get('Zona', '')} - {prop.get('Titulo', prop.get('Nombre', ''))}".strip()
                def _guardar_interes():
                    if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
                        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
                        buscar = requests.get(url, headers=AT_HEADERS,
                            params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
                        records = buscar.json().get("records", []) if buscar.status_code == 200 else []
                        if records:
                            requests.patch(f"{url}/{records[0]['id']}", headers=AT_HEADERS,
                                json={"fields": {"Propiedad_Interes": prop_nombre[:200]}}, timeout=8)
                threading.Thread(target=_guardar_interes, daemon=True).start()
            else:
                _enviar_texto(telefono,
                    f"Por favor elija un número del 1 al {len(props)}, "
                    f"*+* para ver más, *0* para volver o *#* para hablar con el asesor.")
        except ValueError:
            _enviar_texto(telefono,
                "Responda con el *número* de la propiedad que desea ver, "
                "*+* para ver más, *0* para volver o *#* para hablar con el asesor. 😊")
        return

    # ── FICHA → ACCIONES ─────────────────────────────────────────────────────
    if step == "ficha":
        props = sesion.get("props", [])
        if texto == "0":
            SESIONES[telefono] = {**sesion, "step": "lista"}
            _enviar_texto(telefono, _lista_titulos(props))
            return
        # Cualquier otra respuesta → ofrecer cita
        _ir_asesor(telefono, sesion)
        return

    # ── OFRECER CITA — PREGUNTA BINARIA ANTES DE MOSTRAR SLOTS ──────────────
    if step == "ofrecer_cita":
        slots = sesion.get("slots", [])
        if texto.strip() == "1" or texto_lower in ("si", "sí", "ver", "horarios", "dale"):
            SESIONES[telefono] = {**sesion, "step": "agendar_slots"}
            _enviar_texto(telefono,
                f"Estos son los horarios disponibles con *{NOMBRE_ASESOR}* 📅\n\n"
                f"{_formatear_slots(slots)}\n\n"
                f"Responda con el *número* del horario que prefiere."
            )
        else:
            _enviar_texto(telefono,
                f"¡Perfecto! *{NOMBRE_ASESOR}* se pondrá en contacto con usted a la brevedad. 🏡\n\n"
                f"¡Gracias por confiar en *{NOMBRE_EMPRESA}*! 🌟"
            )
            SESIONES.pop(telefono, None)
        return

    # ── AGENDAMIENTO — SELECCIÓN DE SLOT ─────────────────────────────────────
    if step == "agendar_slots":
        slots = sesion.get("slots", [])
        nombre_corto2 = nombre.split()[0] if nombre else ""
        if texto.strip() == "0":
            _enviar_texto(telefono,
                f"¡De acuerdo, {nombre_corto2}! Nuestro asesor *{NOMBRE_ASESOR}* "
                f"estará en contacto con usted a la brevedad. 🏡\n\n"
                f"¡Gracias por confiar en *{NOMBRE_EMPRESA}*! 🌟"
            )
            SESIONES.pop(telefono, None)
            return
        try:
            idx = int(texto.strip()) - 1
            if 0 <= idx < len(slots):
                slot = slots[idx]
                from datetime import datetime, timezone, timedelta
                try:
                    dt = datetime.fromisoformat(slot["time"].replace("Z", "+00:00"))
                    mx = dt.astimezone(timezone(timedelta(hours=_TZ_OFFSET_HOURS)))
                    dia_es = _DIAS_ES.get(mx.strftime("%A"), mx.strftime("%A"))
                    fecha_str = f"{dia_es} {mx.strftime('%d/%m a las %H:%M hs')}"
                except Exception:
                    fecha_str = slot["time"]
                # Guardar slot elegido y pedir confirmación
                SESIONES[telefono] = {**sesion, "step": "confirmar_cita",
                                      "slot_elegido": slot, "fecha_str": fecha_str}
                _enviar_texto(telefono,
                    f"📅 Perfecto, *{nombre_corto2}*. Le confirmo:\n\n"
                    f"📆 *Fecha:* {fecha_str}\n"
                    f"👤 *Asesor:* {NOMBRE_ASESOR}\n\n"
                    f"¿Confirmamos esta cita?\n\n"
                    f"*1️⃣* ✅ Sí, confirmar\n"
                    f"*2️⃣* 🔄 Elegir otro horario\n"
                    f"*0️⃣* ❌ No agendar"
                )
            else:
                _enviar_texto(telefono,
                    f"Por favor elija un número del 1 al {len(slots)}, o *0* para omitir. 😊")
        except ValueError:
            _enviar_texto(telefono,
                f"Responda con el *número* del horario (1-{len(slots)}) o *0* para omitir. 😊")
        return

    # ── CONFIRMAR CITA ───────────────────────────────────────────────────────
    if step == "confirmar_cita":
        email = sesion.get("email", "")
        nombre_corto2 = nombre.split()[0] if nombre else ""
        slot = sesion.get("slot_elegido", {})
        fecha_str = sesion.get("fecha_str", "")
        if texto.strip() == "1" or texto_lower in ("si", "sí", "confirmar", "dale", "ok"):
            notas = (f"Busca: {sesion.get('resp_tipo','')} en {sesion.get('resp_zona','')} "
                     f"— Presupuesto: {sesion.get('resp_presupuesto','')}")
            resultado = _cal_crear_reserva(nombre, email, telefono, slot.get("time", ""), notas)
            if resultado["ok"]:
                threading.Thread(
                    target=_at_guardar_cita,
                    args=(telefono, slot.get("time", "")), daemon=True
                ).start()
                _enviar_texto(telefono,
                    f"✅ *¡Cita confirmada, {nombre_corto2}!*\n\n"
                    f"📅 *Fecha:* {fecha_str}\n"
                    f"👤 *Asesor:* {NOMBRE_ASESOR}\n\n"
                    f"Recibirá una confirmación por email. "
                    f"Si necesita reagendar, escríbanos aquí. 😊\n\n"
                    f"¡Gracias por confiar en *{NOMBRE_EMPRESA}*! 🌟"
                )
                SESIONES.pop(telefono, None)
            else:
                _enviar_texto(telefono,
                    f"Lo sentimos, ese horario ya no está disponible. 😔\n\n"
                    f"Por favor escriba *2* para elegir otro horario o *0* para omitir."
                )
        elif texto.strip() == "2" or texto_lower in ("no", "otro", "cambiar"):
            slots = sesion.get("slots", [])
            if slots:
                SESIONES[telefono] = {**sesion, "step": "agendar_slots"}
                _enviar_texto(telefono,
                    f"Sin problema 😊 Elija otro horario:\n\n"
                    f"{_formatear_slots(slots)}\n\n"
                    f"Responda con el *número* del horario que prefiere, o *0* para omitir."
                )
            else:
                _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
                    nombre=nombre_corto2, asesor=NOMBRE_ASESOR, empresa=NOMBRE_EMPRESA))
                SESIONES.pop(telefono, None)
        elif texto.strip() == "0":
            _enviar_texto(telefono,
                f"¡De acuerdo, {nombre_corto2}! Nuestro asesor *{NOMBRE_ASESOR}* "
                f"estará en contacto con usted a la brevedad. 🏡\n\n"
                f"¡Gracias por confiar en *{NOMBRE_EMPRESA}*! 🌟"
            )
            SESIONES.pop(telefono, None)
        else:
            _enviar_texto(telefono,
                f"Responda *1* para confirmar, *2* para elegir otro horario, o *0* para no agendar. 😊")
        return

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    _enviar_texto(telefono,
        "Disculpe, no entendí su mensaje. 😊\n\n"
        "Puede usar estas opciones:\n\n"
        "▪️ Escriba *hola* para iniciar una nueva consulta\n"
        "▪️ Escriba *#* para hablar directamente con el asesor\n"
        "▪️ Escriba *0* para volver al menú anterior")
    SESIONES.pop(telefono, None)


def _ir_asesor(telefono: str, sesion: dict) -> None:
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""
    email = sesion.get("email", "")

    # Notificar al asesor
    if NUMERO_ASESOR:
        numero_limpio = re.sub(r"[^0-9]", "", NUMERO_ASESOR)
        tipo  = sesion.get("resp_tipo", "")
        zona  = sesion.get("resp_zona", "")
        _enviar_texto(numero_limpio,
            f"🔔 *{NOMBRE_EMPRESA}*\n\n"
            f"Un cliente solicita hablar con vos:\n"
            f"👤 *{nombre or 'Sin nombre'}*\n"
            f"📱 +{re.sub(r'[^0-9]', '', telefono)}\n"
            + (f"🏡 Busca: {tipo}" if tipo else "")
            + (f" en {zona}" if zona else "")
        )

    # Ofrecer cita — primero pregunta binaria, luego slots
    if _cal_disponible():
        slots = _cal_obtener_slots()
        if slots:
            SESIONES[telefono] = {**sesion, "step": "ofrecer_cita", "slots": slots, "email": email}
            _enviar_texto(telefono,
                f"¡Con gusto, {nombre_corto}! ¿Prefiere ver los horarios disponibles "
                f"con *{NOMBRE_ASESOR}* ahora mismo, o que él se contacte con usted?\n\n"
                f"*1️⃣* Ver horarios disponibles 📅\n"
                f"*0️⃣* Que me contacten a la brevedad"
            )
            return

    _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
        nombre=nombre_corto or nombre,
        asesor=NOMBRE_ASESOR,
        empresa=NOMBRE_EMPRESA,
    ))
    # Guardar historial para que el asesor vea la conversación
    threading.Thread(target=_guardar_historial_at, args=(telefono,), daemon=True).start()
    # Escalar a Chatwoot (label atiende-humano + nota privada con contexto)
    threading.Thread(target=_chatwoot_escalar, args=(telefono, sesion), daemon=True).start()
    # Pausar bot — asesor tomó control
    pausar_bot(telefono)
    SESIONES.pop(telefono, None)


# ─── ENDPOINTS DE CONTROL BOT ────────────────────────────────────────────────

@router.post("/chatwoot/webhook")
async def chatwoot_webhook(request: Request):
    """Recibe eventos de Chatwoot para pausa/retoma del bot."""
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}

    event = data.get("event", "")

    # Cuando el asesor resuelve la conversación → despausar bot
    if event == "conversation_resolved":
        contact = data.get("meta", {}).get("sender", {})
        phone = contact.get("phone_number", "")
        if phone:
            despausar_bot(phone)
            print(f"[CHATWOOT-WEBHOOK] Conversación resuelta — bot despausado para {phone}")

    # Cuando se asigna label atiende-humano → pausar bot
    elif event == "conversation_updated":
        labels = data.get("labels", [])
        contact = data.get("meta", {}).get("sender", {})
        phone = contact.get("phone_number", "")

        if "atiende-humano" in labels:
            if phone:
                pausar_bot(phone)
                print(f"[CHATWOOT-WEBHOOK] Label atiende-humano — bot pausado para {phone}")
        elif "atiende-agenteai" in labels:
            if phone:
                despausar_bot(phone)
                print(f"[CHATWOOT-WEBHOOK] Label atiende-agenteai — bot despausado para {phone}")

        # Sync score: si el asesor cambió label de score en Chatwoot → actualizar PostgreSQL
        if phone and USE_POSTGRES:
            score_label = next((s for s in ("caliente", "tibio", "frio") if s in labels), None)
            if score_label:
                try:
                    db.actualizar_score_por_telefono(phone, score_label)
                    print(f"[CHATWOOT-WEBHOOK] Score sincronizado a CRM: {phone} → {score_label}")
                except Exception as e:
                    print(f"[CHATWOOT-WEBHOOK] Error sync score: {e}")

    return {"status": "ok"}


@router.post("/bot/pausar/{telefono}")
async def api_pausar_bot(telefono: str):
    """Pausa el bot para un lead — asesor toma control."""
    pausar_bot(telefono)
    return {"status": "ok", "telefono": telefono, "bot_pausado": True}


@router.post("/bot/despausar/{telefono}")
async def api_despausar_bot(telefono: str):
    """Reactiva el bot para un lead — asesor terminó."""
    despausar_bot(telefono)
    return {"status": "ok", "telefono": telefono, "bot_pausado": False}


@router.get("/bot/estado/{telefono}")
async def api_estado_bot(telefono: str):
    """Consulta si el bot está pausado para un lead."""
    return {"telefono": telefono, "bot_pausado": bot_pausado(telefono)}


# ─── ENDPOINT WEBHOOK ─────────────────────────────────────────────────────────
@router.post("/whatsapp")
async def webhook_whatsapp(request: Request):
    """Recibe mensajes desde /meta/webhook (main.py lo redirige aquí)."""
    data = await request.json()
    telefono = data.get("from", "")
    texto    = data.get("text", "")
    if not telefono or not texto:
        return {"status": "ignored"}
    threading.Thread(target=_procesar, args=(telefono, texto), daemon=True).start()
    return {"status": "processing"}


# ─── MÉTRICAS ────────────────────────────────────────────────────────────────
@router.get("/crm/metricas")
def crm_metricas():
    """Retorna métricas del pipeline."""
    if USE_POSTGRES:
        return db.get_metricas()
    # Fallback Airtable
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return {"error": "DB no configurada"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    try:
        records, offset = [], None
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            r = requests.get(url, headers=AT_HEADERS, params=params, timeout=12)
            data = r.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        total = len(records)
        if total == 0:
            return {"total": 0, "por_estado": {}, "tasa_citas": 0, "tasa_cierre": 0}
        por_estado, con_cita, cerrados, scores, fuentes = {}, 0, 0, {"caliente":0,"tibio":0,"frio":0}, {}
        for rec in records:
            f = rec.get("fields", {})
            e = f.get("Estado", "no_contactado")
            por_estado[e] = por_estado.get(e, 0) + 1
            if f.get("Fecha_Cita"): con_cita += 1
            if e == "cerrado_ganado": cerrados += 1
            s = f.get("Score", 0) or 0
            if s >= 12: scores["caliente"] += 1
            elif s >= 7: scores["tibio"] += 1
            else: scores["frio"] += 1
            fu = f.get("Fuente", "desconocido")
            fuentes[fu] = fuentes.get(fu, 0) + 1
        return {"total": total, "por_estado": por_estado, "scores": scores, "fuentes": fuentes,
                "con_cita": con_cita, "cerrados_ganados": cerrados,
                "tasa_citas": round((con_cita/total)*100,1) if total else 0,
                "tasa_cierre": round((cerrados/total)*100,1) if total else 0}
    except Exception as e:
        return {"error": str(e)}


# ─── CRM ENDPOINTS (PostgreSQL principal → Airtable fallback) ────────────────

@router.get("/crm/clientes")
def crm_clientes():
    if USE_POSTGRES:
        records = db.get_all_leads()
        return {"total": len(records), "records": records}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return {"records": [], "error": "DB no configurada"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset: params["offset"] = offset
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset = data.get("offset")
        if not offset: break
    return {"total": len(records), "records": records}


@router.patch("/crm/clientes/{record_id}")
async def crm_actualizar_cliente(record_id: str, request: Request):
    from fastapi import HTTPException
    body = await request.json()
    fields = body.get("fields", body)
    ESTADOS_VALIDOS = {"no_contactado", "contactado", "calificado", "visita_agendada", "visito", "en_negociacion", "seguimiento", "cerrado_ganado", "cerrado_perdido"}
    if "Estado" in fields and fields["Estado"] not in ESTADOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Valores: {sorted(ESTADOS_VALIDOS)}")
    if USE_POSTGRES:
        ok = db.update_lead(record_id, fields)
        return {"status": "ok" if ok else "error", "record_id": record_id}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": fields}, timeout=8)
    if r.status_code in (200, 201):
        return {"status": "ok", "record_id": record_id}
    raise HTTPException(status_code=r.status_code, detail=r.text[:200])


@router.post("/crm/clientes")
async def crm_crear_cliente(request: Request):
    from fastapi import HTTPException
    data = await request.json()
    data.setdefault("Estado", "no_contactado")
    if USE_POSTGRES:
        result = db.create_lead(data)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return {"status": "ok", "record": result}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": data}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.get("/crm/propiedades")
def crm_propiedades():
    if USE_POSTGRES:
        records = db.get_all_propiedades()
        return {"total": len(records), "records": records}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return {"records": [], "error": "DB no configurada"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset: params["offset"] = offset
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset = data.get("offset")
        if not offset: break
    return {"total": len(records), "records": records}


@router.get("/crm/activos")
def crm_activos():
    if USE_POSTGRES:
        records = db.get_all_activos()
        return {"total": len(records), "records": records}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        return {"records": [], "error": "DB no configurada"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset: params["offset"] = offset
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset = data.get("offset")
        if not offset: break
    return {"total": len(records), "records": records}


@router.post("/crm/activos")
async def crm_crear_activo(request: Request):
    from fastapi import HTTPException
    data = await request.json()
    fields = data.get("fields", data)
    # TODO: implementar en PostgreSQL cuando se necesite
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        raise HTTPException(status_code=500, detail="DB no configurada")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.patch("/crm/activos/{record_id}")
async def crm_actualizar_activo(record_id: str, request: Request):
    from fastapi import HTTPException
    data = await request.json()
    fields = data.get("fields", data)
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        raise HTTPException(status_code=500, detail="DB no configurada")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": fields}, timeout=8)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.delete("/crm/activos/{record_id}")
def crm_eliminar_activo(record_id: str):
    from fastapi import HTTPException
    if USE_POSTGRES and record_id.startswith("pg_"):
        ok = db.delete_activo(record_id)
        return {"status": "ok" if ok else "error", "deleted": record_id}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        raise HTTPException(status_code=500, detail="DB no configurada")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}/{record_id}"
    r = requests.delete(url, headers=AT_HEADERS, timeout=8)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "deleted": record_id}


# ─── DELETE LEADS ───────────────────────────────────────────────────────────

@router.delete("/crm/clientes/{record_id}")
def crm_eliminar_cliente(record_id: str):
    from fastapi import HTTPException
    if USE_POSTGRES and record_id.startswith("pg_"):
        ok = db.delete_lead(record_id)
        return {"status": "ok" if ok else "error", "deleted": record_id}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        raise HTTPException(status_code=500, detail="DB no configurada")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}/{record_id}"
    r = requests.delete(url, headers=AT_HEADERS, timeout=8)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "deleted": record_id}


# ─── CRUD PROPIEDADES ───────────────────────────────────────────────────────

@router.post("/crm/propiedades")
async def crm_crear_propiedad(request: Request):
    from fastapi import HTTPException
    data = await request.json()
    fields = data.get("fields", data)
    if USE_POSTGRES:
        result = db.create_propiedad(fields)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return {"status": "ok", "record": result}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        raise HTTPException(status_code=500, detail="DB no configurada")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.patch("/crm/propiedades/{record_id}")
async def crm_actualizar_propiedad(record_id: str, request: Request):
    from fastapi import HTTPException
    data = await request.json()
    fields = data.get("fields", data)
    if USE_POSTGRES and record_id.startswith("pg_"):
        ok = db.update_propiedad(record_id, fields)
        return {"status": "ok" if ok else "error", "record_id": record_id}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        raise HTTPException(status_code=500, detail="DB no configurada")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": fields}, timeout=8)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.delete("/crm/propiedades/{record_id}")
def crm_eliminar_propiedad(record_id: str):
    from fastapi import HTTPException
    if USE_POSTGRES and record_id.startswith("pg_"):
        ok = db.delete_propiedad(record_id)
        return {"status": "ok" if ok else "error", "deleted": record_id}
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        raise HTTPException(status_code=500, detail="DB no configurada")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}/{record_id}"
    r = requests.delete(url, headers=AT_HEADERS, timeout=8)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "deleted": record_id}


# ─── UPLOAD IMAGEN A CLOUDINARY ─────────────────────────────────────────────

@router.post("/crm/upload-imagen")
async def crm_upload_imagen(request: Request):
    """Recibe imagen en base64 y la sube a Cloudinary. Devuelve URL."""
    from fastapi import HTTPException
    import hashlib, hmac, time
    data = await request.json()
    imagen_base64 = data.get("image", "")
    if not imagen_base64:
        raise HTTPException(status_code=400, detail="Falta 'image' (base64)")

    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    api_key = os.environ.get("CLOUDINARY_API_KEY", "")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET", "")

    if not (cloud_name and api_key and api_secret):
        raise HTTPException(status_code=500, detail="Cloudinary no configurado")

    timestamp = int(time.time())
    folder = "lovbot_propiedades"
    # Firma
    to_sign = f"folder={folder}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(to_sign.encode()).hexdigest()

    try:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload",
            data={
                "file": imagen_base64,
                "api_key": api_key,
                "timestamp": str(timestamp),
                "signature": signature,
                "folder": folder,
            },
            timeout=30,
        )
        if r.status_code == 200:
            result = r.json()
            return {"status": "ok", "url": result.get("secure_url"), "public_id": result.get("public_id")}
        raise HTTPException(status_code=r.status_code, detail=r.text[:300])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# CRM COMPLETO MULTI-SUBNICHO — Endpoints Sprints 3-8
# Asesores / Propietarios / Loteos / Lotes_Mapa / Contratos / Visitas / Reportes
# ═══════════════════════════════════════════════════════════════════════════

def _check_pg():
    from fastapi import HTTPException
    if not USE_POSTGRES:
        raise HTTPException(status_code=503, detail="PostgreSQL no disponible")


# ── Asesores (Sprint 3) ─────────────────────────────────────────────────────
@router.get("/crm/asesores")
def crm_asesores_list():
    _check_pg()
    return db.get_all_asesores()

@router.post("/crm/asesores")
async def crm_asesor_create(request: Request):
    _check_pg()
    return db.create_asesor(await request.json())

@router.patch("/crm/asesores/{record_id}")
async def crm_asesor_update(record_id: int, request: Request):
    _check_pg()
    return db.update_asesor(record_id, await request.json())

@router.delete("/crm/asesores/{record_id}")
def crm_asesor_delete(record_id: int):
    _check_pg()
    return db.delete_asesor(record_id)


# ── Propietarios (Sprint 4) ─────────────────────────────────────────────────
@router.get("/crm/propietarios")
def crm_propietarios_list():
    _check_pg()
    return db.get_all_propietarios()

@router.post("/crm/propietarios")
async def crm_propietario_create(request: Request):
    _check_pg()
    return db.create_propietario(await request.json())

@router.patch("/crm/propietarios/{record_id}")
async def crm_propietario_update(record_id: int, request: Request):
    _check_pg()
    return db.update_propietario(record_id, await request.json())

@router.delete("/crm/propietarios/{record_id}")
def crm_propietario_delete(record_id: int):
    _check_pg()
    return db.delete_propietario(record_id)


# ── Loteos (Sprint 5) ───────────────────────────────────────────────────────
@router.get("/crm/loteos")
def crm_loteos_list():
    _check_pg()
    return db.get_all_loteos()

@router.post("/crm/loteos")
async def crm_loteo_create(request: Request):
    _check_pg()
    return db.create_loteo(await request.json())

@router.patch("/crm/loteos/{record_id}")
async def crm_loteo_update(record_id: int, request: Request):
    _check_pg()
    return db.update_loteo(record_id, await request.json())

@router.delete("/crm/loteos/{record_id}")
def crm_loteo_delete(record_id: int):
    _check_pg()
    return db.delete_loteo(record_id)


# ── Lotes Mapa (Sprint 5) ───────────────────────────────────────────────────
@router.get("/crm/lotes-mapa")
def crm_lotes_mapa_list(loteo_id: int = None):
    _check_pg()
    return db.get_lotes_mapa(loteo_id)

@router.post("/crm/lotes-mapa")
async def crm_lote_mapa_create(request: Request):
    _check_pg()
    return db.create_lote_mapa(await request.json())

@router.patch("/crm/lotes-mapa/{record_id}")
async def crm_lote_mapa_update(record_id: int, request: Request):
    _check_pg()
    return db.update_lote_mapa(record_id, await request.json())

@router.delete("/crm/lotes-mapa/{record_id}")
def crm_lote_mapa_delete(record_id: int):
    _check_pg()
    return db.delete_lote_mapa(record_id)


# ── Contratos (Sprint 6) ────────────────────────────────────────────────────
@router.get("/crm/contratos")
def crm_contratos_list():
    _check_pg()
    return db.get_all_contratos()

@router.post("/crm/contratos")
async def crm_contrato_create(request: Request):
    _check_pg()
    return db.create_contrato(await request.json())

@router.patch("/crm/contratos/{record_id}")
async def crm_contrato_update(record_id: int, request: Request):
    _check_pg()
    return db.update_contrato(record_id, await request.json())

@router.delete("/crm/contratos/{record_id}")
def crm_contrato_delete(record_id: int):
    _check_pg()
    return db.delete_contrato(record_id)


# ── Visitas / Agenda (Sprint 8) ─────────────────────────────────────────────
@router.get("/crm/visitas")
def crm_visitas_list():
    _check_pg()
    return db.get_all_visitas()

@router.post("/crm/visitas")
async def crm_visita_create(request: Request):
    _check_pg()
    return db.create_visita(await request.json())

@router.patch("/crm/visitas/{record_id}")
async def crm_visita_update(record_id: int, request: Request):
    _check_pg()
    return db.update_visita(record_id, await request.json())

@router.delete("/crm/visitas/{record_id}")
def crm_visita_delete(record_id: int):
    _check_pg()
    return db.delete_visita(record_id)


# ── Reportes (Sprint 7) ─────────────────────────────────────────────────────
@router.get("/crm/reportes")
def crm_reportes(fecha_desde: str = None, fecha_hasta: str = None):
    _check_pg()
    return db.get_reportes(fecha_desde, fecha_hasta)


# ── Upload PDF Contratos (Sprint 6) ─────────────────────────────────────────
@router.post("/crm/upload-pdf")
async def crm_upload_pdf(request: Request):
    """Sube PDF de contrato a Cloudinary y devuelve URL."""
    from fastapi import HTTPException
    import hashlib, time
    data = await request.json()
    pdf_base64 = data.get("file", "")
    if not pdf_base64:
        raise HTTPException(status_code=400, detail="Falta 'file' (base64)")

    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    api_key = os.environ.get("CLOUDINARY_API_KEY", "")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET", "")

    if not (cloud_name and api_key and api_secret):
        raise HTTPException(status_code=500, detail="Cloudinary no configurado")

    timestamp = int(time.time())
    folder = "lovbot_contratos"
    to_sign = f"folder={folder}&resource_type=raw&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(to_sign.encode()).hexdigest()

    try:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/raw/upload",
            data={
                "file": pdf_base64,
                "api_key": api_key,
                "timestamp": str(timestamp),
                "signature": signature,
                "folder": folder,
            },
            timeout=30,
        )
        if r.status_code == 200:
            result = r.json()
            return {"status": "ok", "url": result.get("secure_url"), "public_id": result.get("public_id")}
        raise HTTPException(status_code=r.status_code, detail=r.text[:300])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
