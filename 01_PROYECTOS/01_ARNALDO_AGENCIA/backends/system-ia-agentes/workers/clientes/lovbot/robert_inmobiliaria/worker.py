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
OPENAI_API_KEY    = os.environ.get("LOVBOT_OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
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

# ─── SESIONES + HISTORIAL — cache en RAM + persistencia PostgreSQL ─────────────
# Estrategia: RAM es el cache primario (sin latencia por mensaje).
# PostgreSQL persiste en background → sobrevive reinicios y deploys.
# Multi-tenant: cada cliente de Robert tiene su propio LOVBOT_TENANT_SLUG.

HISTORIAL: dict[str, list[str]] = {}
MAX_HISTORIAL = 20


def _bg_save_session(telefono: str, sesion: dict) -> None:
    """Guarda sesión + historial en PostgreSQL (llamar desde background thread)."""
    if not USE_POSTGRES:
        return
    tel = re.sub(r'\D', '', telefono)
    hist = HISTORIAL.get(tel, [])
    try:
        db.save_bot_session(telefono, sesion, hist)
    except Exception as e:
        print(f"[ROBERT-SESSION] Error save: {e}")


def _bg_delete_session(telefono: str) -> None:
    """Elimina sesión de PostgreSQL (llamar desde background thread)."""
    if not USE_POSTGRES:
        return
    try:
        db.delete_bot_session(telefono)
    except Exception as e:
        print(f"[ROBERT-SESSION] Error delete: {e}")


class _SessionStore(dict):
    """Dict que auto-persiste en PostgreSQL en background en cada write/delete."""

    def __setitem__(self, telefono: str, sesion: dict):
        super().__setitem__(telefono, sesion)
        if USE_POSTGRES:
            threading.Thread(target=_bg_save_session, args=(telefono, sesion), daemon=True).start()

    def pop(self, telefono, *args):
        result = super().pop(telefono, *args)
        if USE_POSTGRES:
            threading.Thread(target=_bg_delete_session, args=(telefono,), daemon=True).start()
        return result


SESIONES: _SessionStore = _SessionStore()

# Inicializar tabla bot_sessions al arrancar
if USE_POSTGRES:
    try:
        db.setup_bot_sessions()
    except Exception as _e:
        print(f"[ROBERT-SESSION] setup_bot_sessions error: {_e}")


def _cargar_sesion_db(telefono: str) -> None:
    """Carga sesión y historial desde PostgreSQL al cache en RAM (si no existe en RAM)."""
    if not USE_POSTGRES:
        return
    tel = re.sub(r'\D', '', telefono)
    try:
        data = db.get_bot_session(telefono)
        if data:
            sesion = data.get("sesion", {})
            historial = data.get("historial", [])
            if sesion:
                # Cargar directo al dict base para no triggear otro save
                super(_SessionStore, SESIONES).__setitem__(telefono, sesion)
                print(f"[ROBERT-SESSION] Sesión restaurada para {tel[-4:]}*** ({sesion.get('step','?')})")
            if historial:
                HISTORIAL[tel] = historial
    except Exception as e:
        print(f"[ROBERT-SESSION] Error carga: {e}")


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
            # Mensajes del bot: private=True para que Chatwoot NO los reenvíe por WhatsApp
            # (evita duplicados — el bot ya los envió directo por Meta Graph API)
            private = es_bot
            msg_type = "outgoing" if es_bot else "incoming"
            requests.post(
                f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/messages",
                headers=_chatwoot_headers(),
                json={"content": contenido, "message_type": msg_type, "private": private},
                timeout=8,
            )
            print(f"[CW-MIRROR] {'🤖 bot (privado)' if es_bot else '👤 lead'} → conv {conv_id}")
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
    """Llama a GPT-5-mini (principal) → Gemini 2.5 Flash (fallback)."""
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
                json={"model": "gpt-5-mini", "messages": messages, "max_completion_tokens": 1500},
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
def _build_system_prompt(sesion: dict, referral: dict, telefono: str) -> str:
    """Construye el system prompt dinámico según el estado actual de la sesión."""
    import time as _t

    # ── Datos extraídos hasta ahora ──
    # Este bot es para un DESARROLLADOR INMOBILIARIO (vende sus propios
    # desarrollos: lotes, terrenos, casas en country, etc.).
    # NO preguntar al lead qué tipo de perfil tiene — eso ya lo sabemos.
    nombre      = sesion.get("nombre", "")
    email       = sesion.get("email", "")
    ciudad      = sesion.get("ciudad_resp", "")
    objetivo    = sesion.get("resp_objetivo", "")
    tipo        = sesion.get("resp_tipo", "")
    zona        = sesion.get("resp_zona", "")
    presupuesto = sesion.get("resp_presupuesto", "")
    urgencia    = sesion.get("resp_urgencia", "")
    score       = sesion.get("score", "")
    step        = sesion.get("step", "inicio")
    props       = sesion.get("props", [])
    slots       = sesion.get("slots", [])
    tiene_ref   = bool(referral and (referral.get("source_url") or referral.get("body") or referral.get("headline")))
    ad_info     = referral.get("headline") or referral.get("body") or referral.get("source_url") or ""

    # ── Historial de la conversación (últimos 10 turnos) ──
    historial = HISTORIAL.get(re.sub(r'\D', '', telefono), [])
    historial_txt = ""
    if historial:
        # El historial guarda strings tipo "[14:32] Lead: mensaje"
        # Normalizamos para el system prompt
        lineas = []
        for h in historial[-10:]:
            if isinstance(h, dict):
                rol = "Cliente" if h.get("rol") == "Lead" else "Vos (bot)"
                lineas.append(f"{rol}: {h.get('msg','')}")
            else:
                # String format: "[HH:MM] Quien: texto"
                # Reemplazar "Lead:" → "Cliente:" y "Bot:" → "Vos (bot):"
                h2 = h.replace("] Lead:", "] Cliente:").replace("] Bot:", "] Vos (bot):")
                lineas.append(h2)
        historial_txt = "\n".join(lineas)

    # ── Zonas disponibles ──
    zonas_str = ", ".join(ZONAS_LIST) if ZONAS_LIST else "sin zonas definidas"

    # ── Estado actual de la sesión en lenguaje natural ──
    datos_conocidos = []
    if nombre:        datos_conocidos.append(f"Nombre: {nombre}")
    if email:         datos_conocidos.append(f"Email: {email}")
    if ciudad:        datos_conocidos.append(f"Ciudad: {ciudad}")
    if objetivo:      datos_conocidos.append(f"Objetivo: {objetivo}")
    if tipo:          datos_conocidos.append(f"Tipo de propiedad: {tipo}")
    if zona:          datos_conocidos.append(f"Zona: {zona}")
    if presupuesto:   datos_conocidos.append(f"Presupuesto: {presupuesto}")
    if urgencia:      datos_conocidos.append(f"Urgencia: {urgencia}")
    if score:         datos_conocidos.append(f"Score lead: {score}")
    datos_txt = "\n".join(datos_conocidos) if datos_conocidos else "Ninguno aún — primer contacto"

    # ── Qué falta obtener ──
    faltantes = []
    if not nombre:      faltantes.append("nombre")
    if not email:       faltantes.append("email (opcional, puede omitir)")
    if not ciudad:      faltantes.append("ciudad")
    if not objetivo:    faltantes.append("qué busca (comprar/alquilar/invertir)")
    if not tipo:        faltantes.append("tipo de propiedad")
    if not zona:        faltantes.append(f"zona preferida (opciones: {zonas_str})")
    if not presupuesto: faltantes.append("presupuesto aproximado")
    if not urgencia:    faltantes.append("urgencia / timing de compra")
    faltantes_txt = ", ".join(faltantes) if faltantes else "TODOS los datos ya obtenidos — proceder a calificar"

    # ── Propiedades disponibles para mostrar ──
    props_txt = ""
    if props:
        props_txt = "\n\nPROPIEDADES YA ENCONTRADAS (ya las mostraste o estás por mostrar):\n"
        for i, p in enumerate(props, 1):
            titulo = p.get("Titulo") or p.get("Nombre") or p.get("fields", {}).get("Titulo", "Propiedad")
            precio = p.get("Precio") or p.get("fields", {}).get("Precio", "")
            zona_p = p.get("Zona") or p.get("fields", {}).get("Zona", "")
            props_txt += f"  {i}. {titulo} — {zona_p} — {precio} {MONEDA}\n"

    # ── Slots de cita disponibles ──
    slots_txt = ""
    if slots:
        slots_txt = f"\n\nSLOTS DE CITA DISPONIBLES (ya los obtuviste de Cal.com, están en sesión):\n"
        slots_txt += _formatear_slots(slots)

    # ── Step actual → instrucción específica ──
    instruccion_step = {
        "inicio": (
            f"Es el PRIMER contacto. El cliente llegó desde un anuncio: '{ad_info}'. "
            f"{'Ya tenemos su nombre (' + nombre + ') — saludalo por su nombre. ' if nombre else 'NO pidas el nombre todavía — vino de un ad. '}"
            "Confirmá la información de la propiedad anunciada (precio, ubicación, "
            "highlights, disponibilidad). Después preguntá UNA cosa BANT — "
            "preferentemente '¿es para vivir o invertir?' (Need)."
            if tiene_ref else
            f"Es el PRIMER contacto. {'Ya tenemos su nombre (' + nombre + ') — saludalo por su nombre. ' if nombre else ''}"
            f"Saludo cálido y UNA pregunta abierta de calificación. "
            "Ej: 'Hola, soy el asistente de Lovbot. ¿Estás buscando para vivir o invertir?' "
            f"{'' if nombre else 'NO pidas el nombre todavía — primero entendé qué busca. '}"
            "NO muestres propiedades hasta calificar Need + Budget."
        ),
        "subnicho": "DEPRECATED — este bot solo atiende clientes de un desarrollador. Avanzar a 'objetivo' directamente.",
        "nombre": "Obtener el nombre del cliente. Ya tenés el perfil. Ser cálido.",
        "email": "Pedir email. Aclarar que es opcional para enviarle fichas antes que salgan al público.",
        "ciudad": f"Preguntar desde qué ciudad escribe. Contexto: empresa en {CIUDAD}.",
        "objetivo": "Preguntar qué busca: comprar, alquilar o invertir. Adaptar al subniche.",
        "tipo": "Preguntar tipo de propiedad (casa, departamento, terreno, local, oficina). Natural, sin listar opciones como menú.",
        "zona": f"Preguntar zona preferida. Zonas disponibles: {zonas_str}. Si no tiene preferencia, también es válido.",
        "presupuesto": f"Preguntar presupuesto aproximado en {MONEDA}. Dar rangos de referencia naturalmente.",
        "urgencia": "Preguntar cuándo piensa concretar: ¿ya está buscando activamente, en los próximos meses, o explorando?",
        "calificado": "Datos completos. Mostrar propiedades encontradas o derivar al asesor según score.",
        "lista": "El cliente está viendo la lista de propiedades. Invitarlo a pedir más detalles de alguna. Si pregunta '#' o quiere hablar con alguien → ACCION: ir_asesor.",
        "ficha": "El cliente está viendo una ficha. Preguntarle si quiere agendar una visita o tiene preguntas.",
        "ofrecer_cita": f"Ofrecer ver horarios disponibles con {NOMBRE_ASESOR} o que el asesor lo contacte. Natural, sin opciones numeradas.",
        "agendar_slots": f"Mostrar horarios disponibles y pedir que elija. Slots: {slots_txt}",
        "confirmar_cita": "Confirmar la cita elegida. Pedir que confirme o cambie.",
        "recuperacion": f"El cliente volvió después de un tiempo. Saludarlo por nombre ({nombre}) y preguntar si quiere retomar donde estaban o empezar de nuevo.",
    }.get(step, "Continuar la conversación según el contexto.")

    # ── ORIGEN DEL LEAD (Caso A vs Caso B) ──
    if tiene_ref:
        bloque_origen = f"""## 🎯 ORIGEN DEL LEAD: CASO A — VINO DESDE UN ANUNCIO ESPECÍFICO
Propiedad anunciada: '{ad_info}'

ACCIÓN INICIAL OBLIGATORIA (si es el primer mensaje):
- Confirmá info de ESA propiedad (precio, ubicación, highlights, disponibilidad)
- NO empieces preguntando datos personales
- Después calificá con BANT (Need → Budget → Authority → Timeline)
- Anclá toda la conversación en LA propiedad anunciada
- Si pide más opciones → ahí sí abrís catálogo filtrado (2-4 máx)"""
    else:
        bloque_origen = """## 📨 ORIGEN DEL LEAD: CASO B — GENÉRICO (sin anuncio específico)

ACCIÓN INICIAL OBLIGATORIA (si es el primer mensaje):
- Saludo cálido + UNA pregunta abierta de calificación
- Ej: "Hola, soy el asistente de Lovbot. ¿Estás buscando para vivir, invertir o alquilar?"
- NO mostrés propiedades hasta tener al menos Need + Budget mínimo
- Una vez calificado → mostrar 2-4 opciones (no más)"""

    system = f"""Sos el asistente virtual de *{NOMBRE_EMPRESA}*, una agencia inmobiliaria en {CIUDAD}.
El asesor humano se llama *{NOMBRE_ASESOR}*.

## TU MISIÓN — FILTRO PROFESIONAL BANT
Calificar leads inmobiliarios usando metodología BANT (Budget, Authority, Need, Timeline)
en menos de 2 minutos. NO sos un menú, sos un consultor que charla por WhatsApp.

OBJETIVO: identificar 3 tipos de leads:
🔥 CALIENTE → presupuesto claro + forma de pago definida + urgencia <3m → AGENDAR YA
🌡️ TIBIO   → presupuesto amplio o urgencia 3-6m → MOSTRAR 2-4 opciones + nurturing
❄️ FRÍO    → "solo viendo", sin presupuesto/urgencia → CERRAR amable + nurturing

{bloque_origen}

## METODOLOGÍA BANT (orden estricto, una pregunta por turno)

1. **NEED** (qué busca)
   - "¿Es para vivir, invertir o alquilar?"
   - "¿Qué tipo de propiedad? (casa, departamento, terreno…)"
   - "¿En qué zona te imaginás?"

2. **BUDGET** (filtro #1 de curiosos)
   - "¿Qué presupuesto manejás aproximadamente?"
   - "¿Pagás al contado o con crédito hipotecario?" ← PREGUNTA CRÍTICA
   - ⚠️ Si dice "no sé" o "depende" en presupuesto/pago → frío, educar, no avanzar a agendar

3. **AUTHORITY** (quién decide la compra)
   - "¿La decisión la tomás vos o con tu pareja/socio/familia?"

4. **TIMELINE** (urgencia real)
   - "¿Estás buscando activamente o aún explorando?"
   - "¿Para cuándo te gustaría concretar?"

5. **MOTIVO** (anchor emocional, filtra curiosos)
   - "¿Qué te llevó a buscar ahora?"
   - Respuestas concretas (mudanza, hijo, trabajo nuevo) = lead REAL
   - "no sé, miraba" = curioso, cerrar amable

## PERSONALIDAD Y TONO
- Cálido, profesional, cercano. Como un consultor que sabe del rubro.
- Mensajes cortos: máximo 3-4 líneas. UNA pregunta por mensaje.
- *Negrita* solo para datos importantes (precios, fechas).
- Emojis con moderación: máximo 1 por mensaje (🏡 📅 ✅ ❤️).
- Nunca uses "opción 1, 2, 3" para preguntas conversacionales (sí para slots o propiedades).
- Si el cliente dice "hola", "menú" o "0" → reconocer y continuar donde quedó la sesión.

## REGLAS CRÍTICAS

✅ HACER:
- Una pregunta por mensaje (NUNCA dos a la vez)
- Si Caso A: anclar conversación en LA propiedad anunciada
- Mostrar máximo 2-4 propiedades (NO 10)
- Forma de pago es PREGUNTA OBLIGATORIA antes de agendar visita
- Después de agendar, ofrecer UNA sola cosa más (no agenda + info juntos)

🟡 EXCEPCIÓN IMPORTANTE — PEDIDOS EXPLÍCITOS DEL CLIENTE:
Si el cliente pide explícitamente ver opciones con frases como:
"qué opciones tenés / qué hay / muéstrame / qué tienen / qué propiedades /
opciones para mi bolsillo / mostrame / quiero ver"
→ MOSTRAR 2-4 PROPIEDADES INMEDIATAMENTE con la ACCION: mostrar_props
   (con un rango amplio si aún no sabés Budget). NUNCA repetir la pregunta
   de presupuesto en este caso.
→ Usá las opciones mostradas como ancla para preguntar después:
   "De estas opciones, ¿cuál se acerca a tu rango?"
   "¿Cuál te llama la atención?"

❌ NO HACER:
- "¿En qué puedo ayudarte?" — sos consultor, no portero
- Pedir email al inicio
- Mostrar propiedades por iniciativa propia sin que el cliente lo pida
  o sin haber calificado Need mínimo
- Repetir la misma pregunta cuando el cliente PIDE algo distinto
- Bombardear con info que el cliente no pidió
- Agendar visita sin haber preguntado forma de pago
- Insistir 3+ veces si el lead da respuestas evasivas
- Ofrecer "alquilar" como opción cuando el ad es de un LOTE/TERRENO
  (los lotes solo se venden, no se alquilan — adaptá al tipo de propiedad)

## DETECCIÓN DE CAÍDA
Si el lead deja de responder, da monosílabos repetidos, o evade calificación
→ cambiar a modo recuperación con UNA frase tipo:
- "¿Qué te faltó para decidirte?"
- "¿Te puedo enviar comparativo de otras opciones similares?"
- "Decime un buen día/hora y te llamo personalmente."

Si después de 2 intentos no hay engagement → ACCION: cerrar_curioso

## DATOS YA CONOCIDOS DEL CLIENTE
{datos_txt}

## DATOS QUE TODAVÍA FALTAN
{faltantes_txt}

## STEP ACTUAL: {step.upper()}
{instruccion_step}

## HISTORIAL DE LA CONVERSACIÓN
{historial_txt if historial_txt else "(Primer mensaje)"}
{props_txt}
{slots_txt}

## EXTRACCIÓN DE DATOS (formato ESTRICTO)

⚠️ REGLAS CRÍTICAS DE FORMATO — el cliente NUNCA debe ver estas líneas:
1. NO uses headers tipo "EXTRACCIÓN DE DATOS:", "ACCIONES:" o similares
2. NO uses bullets (• - * ▪) antes de las líneas
3. NO uses ** ** alrededor de las KEYS
4. NO uses separadores --- ni ===
5. NUNCA pongas estas líneas en medio del mensaje, SIEMPRE al final
6. Cada línea debe ser EXACTAMENTE: KEY: valor (sin nada más)
7. Solo incluí las líneas que apliquen en ESTE turno

Formato CORRECTO (ejemplo):
NOMBRE: Juan García
OBJETIVO: vivir
ACCION: continuar

Formato INCORRECTO (NO hagas esto):
EXTRACCIÓN DE DATOS:
  • OBJETIVO: vivir
  • ACCION: continuar

Lista de KEYS válidas (usar EXACTAMENTE estas):
NOMBRE: Juan García
EMAIL: correo@ejemplo.com
CIUDAD: NombreCiudad
OBJETIVO: vivir | invertir | alquilar
TIPO: casa | departamento | terreno | lote | local | oficina
ZONA: nombre_zona
PRESUPUESTO: ej USD 100k-200k
FORMA_PAGO: contado | credito_aprobado | credito_sin_aprobar | indefinido
AUTORIDAD: solo | pareja | socios | familia
URGENCIA: inmediata | 1_3_meses | 3_6_meses | explorando
MOTIVO: ej se muda a Posadas por trabajo nuevo
SCORE: caliente | tibio | frio
ACCION: continuar | mostrar_props | agendar | ir_asesor | cerrar_curioso | nurturing
"""
    return system


def _procesar(telefono: str, texto: str, referral: dict = None) -> None:
    referral = referral or {}
    # Si el asesor tomó control, el bot NO responde
    if bot_pausado(telefono):
        print(f"[ROBERT] Bot pausado para {telefono} — asesor activo, ignorando mensaje")
        return

    # ── Restaurar sesión desde PostgreSQL si no está en RAM (post-deploy) ──────
    if telefono not in SESIONES:
        _cargar_sesion_db(telefono)

    # Registrar mensaje del lead en historial
    _agregar_historial(telefono, "Lead", texto)

    import time as _time
    texto   = texto.strip()
    texto_lower = texto.lower()
    sesion  = SESIONES.get(telefono, {})
    ahora_ts = _time.time()
    nombre  = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""

    # ── Tareas de background (no bloquean) ────────────────────────────────
    def _bg_desactivar_seguimiento():
        if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
            r = requests.get(url, headers=AT_HEADERS,
                params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
            records = r.json().get("records", []) if r.status_code == 200 else []
            if records:
                est = records[0].get("fields", {}).get("Estado_Seguimiento", "")
                if est in ("activo", "dormido"):
                    requests.patch(f"{url}/{records[0]['id']}", headers=AT_HEADERS,
                        json={"fields": {"Estado_Seguimiento": "pausado"}}, timeout=8)
    threading.Thread(target=_bg_desactivar_seguimiento, daemon=True).start()

    def _bg_update_interaccion():
        from datetime import datetime, timezone
        if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
            r = requests.get(url, headers=AT_HEADERS,
                params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
            records = r.json().get("records", []) if r.status_code == 200 else []
            if records:
                requests.patch(f"{url}/{records[0]['id']}", headers=AT_HEADERS,
                    json={"fields": {"fecha_ultimo_contacto": datetime.now(timezone.utc).isoformat()}}, timeout=8)
    threading.Thread(target=_bg_update_interaccion, daemon=True).start()

    # ── Comando # → asesor inmediato ─────────────────────────────────────
    if texto_lower == "#":
        _ir_asesor(telefono, sesion)
        return

    # ── Timeout de sesión (>30 min) → modo recuperación via LLM ──────────
    SESSION_TIMEOUT = 30 * 60
    ultimo_ts = sesion.get("_ultimo_ts", 0)
    step = sesion.get("step", "inicio")
    if ultimo_ts and step not in ("inicio",) and (ahora_ts - ultimo_ts) > SESSION_TIMEOUT:
        sesion["step"] = "recuperacion"
    if telefono in SESIONES:
        SESIONES[telefono]["_ultimo_ts"] = ahora_ts

    # ── Guardar referral en sesión si es lead nuevo desde Ads ─────────────
    if referral and telefono not in SESIONES:
        fuente_det = (f"ad:{referral.get('source_id','')}|{referral.get('headline','')[:50]}"
                      if referral.get("source_id") else
                      f"referral:{referral.get('source_url','')[:80]}")
        SESIONES[telefono] = {
            "step": "inicio",
            "subniche": "agencia_inmobiliaria",
            "_referral": referral,
            "_fuente_detalle": fuente_det,
            "_ultimo_ts": ahora_ts,
        }
        sesion = SESIONES[telefono]
        print(f"[ROBERT] Lead desde anuncio: {referral.get('headline') or referral.get('body','')}")

    # ── Step especiales que NO pasan por LLM (agendamiento) ───────────────
    step = sesion.get("step", "inicio")

    if step == "agendar_slots":
        slots = sesion.get("slots", [])
        if texto.strip() == "0":
            _enviar_texto(telefono,
                f"¡Perfecto! *{NOMBRE_ASESOR}* te va a contactar a la brevedad. 🏡\n"
                f"¡Gracias por confiar en *{NOMBRE_EMPRESA}*! 🌟")
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
                SESIONES[telefono] = {**sesion, "step": "confirmar_cita",
                                      "slot_elegido": slot, "fecha_str": fecha_str}
                _enviar_texto(telefono,
                    f"📅 Te confirmo:\n\n"
                    f"📆 *{fecha_str}*\n"
                    f"👤 Con *{NOMBRE_ASESOR}*\n\n"
                    f"¿Lo confirmamos? Respondé *sí* o *no*.")
            else:
                _enviar_texto(telefono, f"Elegí un número del 1 al {len(slots)}, o *0* para cancelar.")
        except ValueError:
            _enviar_texto(telefono, f"Respondé con el número del horario (1-{len(slots)}) o *0*.")
        return

    if step == "confirmar_cita":
        slot = sesion.get("slot_elegido", {})
        fecha_str = sesion.get("fecha_str", "")
        email_cita = sesion.get("email", "")
        if texto_lower in ("si", "sí", "1", "confirmar", "dale", "ok", "yes"):
            notas = (f"Busca: {sesion.get('resp_tipo','')} en {sesion.get('resp_zona','')} "
                     f"— Presupuesto: {sesion.get('resp_presupuesto','')}")
            resultado = _cal_crear_reserva(nombre, email_cita, telefono, slot.get("time", ""), notas)
            if resultado["ok"]:
                threading.Thread(target=_at_guardar_cita, args=(telefono, slot.get("time","")), daemon=True).start()
                _enviar_texto(telefono,
                    f"✅ *¡Cita confirmada{', ' + nombre_corto if nombre_corto else ''}!*\n\n"
                    f"📅 *{fecha_str}* con *{NOMBRE_ASESOR}*\n\n"
                    f"Te llega confirmación por email. Si necesitás reagendar, escribime. 😊\n"
                    f"¡Gracias por confiar en *{NOMBRE_EMPRESA}*! 🌟")
                SESIONES.pop(telefono, None)
            else:
                _enviar_texto(telefono,
                    f"Ese horario ya no está disponible 😔 ¿Elegimos otro? Escribí *2* o *0* para cancelar.")
        elif texto_lower in ("no", "2", "otro", "cambiar"):
            slots = sesion.get("slots", [])
            SESIONES[telefono] = {**sesion, "step": "agendar_slots"}
            _enviar_texto(telefono,
                f"Sin problema 😊 Elegí otro horario:\n\n{_formatear_slots(slots)}")
        else:
            _enviar_texto(telefono, "Respondé *sí* para confirmar o *no* para elegir otro horario.")
        return

    # ── NÚCLEO LLM CONVERSACIONAL ─────────────────────────────────────────
    system_prompt = _build_system_prompt(sesion, referral, telefono)

    respuesta_llm = _llm(texto, system=system_prompt)

    if not respuesta_llm:
        _enviar_texto(telefono,
            f"Disculpá, tuve un problema técnico. ¿Podés repetir tu mensaje? 🙏")
        return

    # ── Extraer ACCIONES del LLM (líneas ocultas al final) ────────────────
    # Parser tolerante: detecta keys aunque vengan con bullets, espacios, ** o emojis
    KEYS_INTERNAS = {
        "ACCION", "EMAIL", "NOMBRE", "SUBNICHE", "CIUDAD", "OBJETIVO", "TIPO",
        "ZONA", "PRESUPUESTO", "URGENCIA", "FORMA_PAGO", "AUTORIDAD", "MOTIVO", "SCORE"
    }
    HEADERS_INTERNOS = {
        "EXTRACCIÓN DE DATOS", "EXTRACCION DE DATOS", "ACCIONES", "DATOS EXTRAÍDOS",
        "DATOS EXTRAIDOS", "---", "===",
    }

    def _normalizar_linea_extraccion(linea_raw):
        """Devuelve (key, value) si la línea es de extracción, sino None."""
        # Limpia bullets, *, espacios, emojis comunes al inicio
        cleaned = re.sub(r'^[\s\-•*·▪►◦●◾▶➤→\u2022\u2023]+', '', linea_raw).strip()
        # Quita ** ** alrededor de la KEY (markdown)
        cleaned = re.sub(r'^\*+\s*', '', cleaned)
        # Match KEY: VALUE (case-insensitive)
        m = re.match(r'^([A-ZÁÉÍÓÚÑ_]+)\s*:\s*(.*)$', cleaned)
        if not m:
            return None
        key_upper = m.group(1).upper().strip("*").strip()
        if key_upper in KEYS_INTERNAS:
            return key_upper, m.group(2).strip()
        return None

    def _es_header_interno(linea_raw):
        cleaned = re.sub(r'^[\s\-•*·#=]+', '', linea_raw).strip().rstrip(':').strip()
        cleaned_upper = cleaned.upper()
        return any(h in cleaned_upper for h in HEADERS_INTERNOS)

    lineas = respuesta_llm.strip().split("\n")
    acciones = {}
    texto_visible = []
    for linea in lineas:
        # Headers tipo "EXTRACCIÓN DE DATOS:" o "===" → ocultar
        if _es_header_interno(linea):
            continue
        # Línea KEY: VALUE → extraer y ocultar
        parsed = _normalizar_linea_extraccion(linea)
        if parsed:
            key, value = parsed
            if key == "ACCION":
                acciones["accion"] = value
            elif key == "EMAIL":
                acciones["email"] = value
            elif key == "NOMBRE":
                acciones["nombre"] = value.title()
            elif key == "SUBNICHE":
                acciones["subniche"] = value.lower()
            elif key == "CIUDAD":
                acciones["ciudad"] = value.title()
            elif key == "OBJETIVO":
                acciones["objetivo"] = value.lower()
            elif key == "TIPO":
                acciones["tipo"] = value.lower()
            elif key == "ZONA":
                acciones["zona"] = value
            elif key == "PRESUPUESTO":
                acciones["presupuesto"] = value
            elif key == "URGENCIA":
                acciones["urgencia"] = value.lower()
            elif key == "FORMA_PAGO":
                acciones["forma_pago"] = value.lower()
            elif key == "AUTORIDAD":
                acciones["autoridad"] = value.lower()
            elif key == "MOTIVO":
                acciones["motivo"] = value
            elif key == "SCORE":
                acciones["score"] = value.lower()
            continue
        texto_visible.append(linea)

    mensaje_final = "\n".join(texto_visible).strip()
    # Cleanup final: quitar líneas vacías repetidas y separadores residuales
    mensaje_final = re.sub(r'\n\s*\n\s*\n+', '\n\n', mensaje_final).strip()
    mensaje_final = re.sub(r'^\s*[-=]{3,}\s*$', '', mensaje_final, flags=re.MULTILINE).strip()

    # ── Actualizar sesión con datos extraídos ──────────────────────────────
    sesion_nueva = dict(sesion)
    sesion_nueva["_ultimo_ts"] = ahora_ts

    if "nombre" in acciones and not sesion_nueva.get("nombre"):
        sesion_nueva["nombre"] = acciones["nombre"]
        nombre = acciones["nombre"]
        nombre_corto = nombre.split()[0]

    if "email" in acciones and not sesion_nueva.get("email"):
        email_val = acciones["email"]
        sesion_nueva["email"] = email_val
        threading.Thread(target=_at_guardar_email, args=(telefono, email_val), daemon=True).start()

    if "subniche" in acciones and not sesion_nueva.get("subniche"):
        sesion_nueva["subniche"] = acciones["subniche"]

    if "ciudad" in acciones and not sesion_nueva.get("ciudad_resp"):
        sesion_nueva["ciudad_resp"] = acciones["ciudad"]

    if "objetivo" in acciones and not sesion_nueva.get("resp_objetivo"):
        sesion_nueva["resp_objetivo"] = acciones["objetivo"]
        for kw, val in [("comprar","venta"),("alquilar","alquiler"),("invertir","venta")]:
            if kw in acciones["objetivo"]:
                sesion_nueva["operacion_at"] = val
                break

    if "tipo" in acciones and not sesion_nueva.get("resp_tipo"):
        sesion_nueva["resp_tipo"] = acciones["tipo"]

    if "zona" in acciones and not sesion_nueva.get("resp_zona"):
        sesion_nueva["resp_zona"] = acciones["zona"]

    if "presupuesto" in acciones and not sesion_nueva.get("resp_presupuesto"):
        sesion_nueva["resp_presupuesto"] = acciones["presupuesto"]

    if "urgencia" in acciones and not sesion_nueva.get("resp_urgencia"):
        sesion_nueva["resp_urgencia"] = acciones["urgencia"]

    # ── Campos BANT ampliados (Sprint 1) ────────────────────────────────────
    if "forma_pago" in acciones:
        sesion_nueva["forma_pago"] = acciones["forma_pago"]
    if "autoridad" in acciones:
        sesion_nueva["autoridad"] = acciones["autoridad"]
    if "motivo" in acciones:
        sesion_nueva["motivo"] = acciones["motivo"]
    if "score" in acciones:
        sesion_nueva["score"] = acciones["score"]

    # ── Inferir datos desde el texto del usuario (backup si LLM no puso directive) ──
    if not sesion_nueva.get("resp_objetivo"):
        for kw, val in [("comprar","venta"),("alquiler","alquiler"),("alquilar","alquiler"),("invertir","venta"),("venta","venta")]:
            if kw in texto_lower:
                sesion_nueva["resp_objetivo"] = kw
                sesion_nueva["operacion_at"] = val
                break

    if not sesion_nueva.get("resp_tipo"):
        tipo_det = _normalizar_tipo(texto)
        if tipo_det:
            sesion_nueva["resp_tipo"] = tipo_det

    if not sesion_nueva.get("resp_zona"):
        zona_det = _normalizar_zona(texto)
        if zona_det:
            sesion_nueva["resp_zona"] = zona_det

    # ── Actualizar step según datos acumulados ─────────────────────────────
    datos_completos = all([
        sesion_nueva.get("nombre"),
        sesion_nueva.get("resp_objetivo") or sesion_nueva.get("operacion_at"),
        sesion_nueva.get("resp_tipo"),
        sesion_nueva.get("resp_presupuesto") or sesion_nueva.get("presupuesto_at"),
        sesion_nueva.get("resp_urgencia"),
    ])

    SESIONES[telefono] = sesion_nueva

    # ── Ejecutar ACCION ────────────────────────────────────────────────────
    accion = acciones.get("accion", "")

    if accion == "ir_asesor":
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)
        _ir_asesor(telefono, sesion_nueva)
        return

    if accion == "cerrar_curioso":
        # Lead no interesado / evasivo — cerramos sin escalar al asesor.
        # Se registra como frío en Airtable para métrica, pero no notifica al asesor.
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)
        sesion_nueva["score"] = "frio"
        sesion_nueva["step"]  = "cerrado_curioso"
        threading.Thread(target=_at_registrar_lead, args=(
            telefono, nombre or "Sin nombre", "frio",
            sesion_nueva.get("resp_tipo",""),
            sesion_nueva.get("resp_zona",""),
            "Lead no calificado — evasivo/curioso (filtrado por bot)",
            sesion_nueva.get("presupuesto_at",""),
            sesion_nueva.get("operacion_at",""),
            sesion_nueva.get("ciudad_resp", CIUDAD),
            sesion_nueva.get("subniche",""),
            sesion_nueva.get("_fuente_detalle",""),
        ), daemon=True).start()
        SESIONES.pop(telefono, None)
        return

    if accion == "calificar" or datos_completos:
        # Enviar respuesta del LLM primero (puede ser transición)
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)

        # Calificar con Gemini
        calificacion = _gemini_calificar(sesion_nueva)
        score     = calificacion.get("score", "tibio")
        derivar   = calificacion.get("derivar_sitio_web", False)
        tipo      = calificacion.get("tipo") or sesion_nueva.get("resp_tipo", "")
        zona      = calificacion.get("zona") or sesion_nueva.get("resp_zona", "")
        operacion = calificacion.get("operacion") or sesion_nueva.get("operacion_at", "venta")
        nota      = calificacion.get("nota_para_asesor", "")
        if tipo in (None, "null", ""): tipo = sesion_nueva.get("resp_tipo", "")
        if zona in (None, "null", ""): zona = sesion_nueva.get("resp_zona", "")

        sesion_nueva["score"] = score
        sesion_nueva["step"]  = "calificado"
        SESIONES[telefono] = sesion_nueva

        # Registrar lead (background)
        threading.Thread(target=_at_registrar_lead, args=(
            telefono, nombre, score, tipo, zona, nota,
            sesion_nueva.get("presupuesto_at",""),
            sesion_nueva.get("operacion_at",""),
            sesion_nueva.get("ciudad_resp", CIUDAD),
            sesion_nueva.get("subniche",""),
            sesion_nueva.get("_fuente_detalle",""),
        ), daemon=True).start()

        threading.Thread(target=_notificar_asesor, args=(telefono, sesion_nueva, calificacion), daemon=True).start()
        threading.Thread(target=_chatwoot_escalar, args=(telefono, sesion_nueva, calificacion), daemon=True).start()

        if derivar or score == "frio":
            web_line = f"🌐 *{SITIO_WEB}*\n\n" if SITIO_WEB else ""
            _enviar_texto(telefono, MSG_SITIO_WEB.format(
                nombre=nombre_corto or nombre, web_line=web_line, asesor=NOMBRE_ASESOR))
            def _nurturing():
                from datetime import date, timedelta
                if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
                    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
                    r = requests.get(url, headers=AT_HEADERS,
                        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
                    recs = r.json().get("records", []) if r.status_code == 200 else []
                    if recs:
                        requests.patch(f"{url}/{recs[0]['id']}", headers=AT_HEADERS,
                            json={"fields": {"Estado_Seguimiento": "activo",
                                "Cantidad_Seguimientos": 0,
                                "Proximo_Seguimiento": (date.today() + timedelta(days=3)).isoformat()}}, timeout=8)
            threading.Thread(target=_nurturing, daemon=True).start()
            SESIONES.pop(telefono, None)
            return

        # Caliente/tibio → buscar propiedades
        props = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona,
                                       presupuesto=sesion_nueva.get("presupuesto_at",""))
        if not props:
            if _cal_disponible():
                slots = _cal_obtener_slots()
                if slots:
                    SESIONES[telefono] = {**sesion_nueva, "step": "agendar_slots", "slots": slots}
                    _enviar_texto(telefono,
                        f"Ahora mismo no tenemos propiedades con esas características publicadas, "
                        f"pero *{NOMBRE_ASESOR}* maneja opciones exclusivas. 🏡\n\n"
                        f"Te muestro sus horarios disponibles para una charla rápida:\n\n"
                        f"{_formatear_slots(slots)}\n\nElegí un número o *0* para que te contactemos.")
                    return
            _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
                nombre=nombre_corto or nombre, asesor=NOMBRE_ASESOR, empresa=NOMBRE_EMPRESA))
            pausar_bot(telefono)
            SESIONES.pop(telefono, None)
            return

        # Mostrar propiedades
        props_iniciales = props[:2]
        props_restantes = props[2:]
        SESIONES[telefono] = {**sesion_nueva, "step": "lista",
                              "props": props_iniciales, "props_extra": props_restantes,
                              "tipo": tipo, "zona": zona, "operacion": operacion}
        _enviar_texto(telefono,
            f"Encontré propiedades que coinciden con lo que buscás. Te muestro las mejores 👇")
        _enviar_texto(telefono, _lista_titulos(props_iniciales))
        if props_restantes:
            _enviar_texto(telefono,
                f"Tengo *{len(props_restantes)}* opción{'es' if len(props_restantes)>1 else ''} más — "
                f"escribí *+* para verlas o elegí un número para ver el detalle.")
        return

    # ── Step lista → navegación por propiedades ───────────────────────────
    if step == "lista":
        props = sesion.get("props", [])
        props_extra = sesion.get("props_extra", [])
        if texto.strip() == "+":
            if props_extra:
                props_todas = props + props_extra
                SESIONES[telefono] = {**sesion_nueva, "props": props_todas, "props_extra": []}
                _enviar_texto(telefono, _lista_titulos(props_todas))
            else:
                _enviar_texto(telefono, "Ya te mostré todas las opciones disponibles. ¿Cuál te interesa?")
            return
        try:
            idx = int(texto) - 1
            if 0 <= idx < len(props):
                prop = props[idx]
                SESIONES[telefono] = {**sesion_nueva, "step": "ficha", "ficha_actual": idx}
                _enviar_ficha(telefono, prop)
                prop_nombre = f"{prop.get('Tipo','')} {prop.get('Zona','')} - {prop.get('Titulo', prop.get('Nombre',''))}".strip()
                def _guardar_interes():
                    if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
                        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
                        r = requests.get(url, headers=AT_HEADERS,
                            params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
                        recs = r.json().get("records", []) if r.status_code == 200 else []
                        if recs:
                            requests.patch(f"{url}/{recs[0]['id']}", headers=AT_HEADERS,
                                json={"fields": {"Propiedad_Interes": prop_nombre[:200]}}, timeout=8)
                threading.Thread(target=_guardar_interes, daemon=True).start()
                return
        except ValueError:
            pass
        # Si no eligió número → LLM maneja
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)
        return

    if step == "ficha":
        if texto.strip() == "0":
            props = sesion.get("props", [])
            SESIONES[telefono] = {**sesion_nueva, "step": "lista"}
            _enviar_texto(telefono, _lista_titulos(props))
            return
        # Cualquier respuesta en ficha → LLM decide si ofrecer cita o responder pregunta
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)
        return

    # ── Respuesta LLM estándar ─────────────────────────────────────────────
    if mensaje_final:
        _enviar_texto(telefono, mensaje_final)
        _agregar_historial(telefono, "Bot", mensaje_final)

    # Actualizar step si el LLM extrajo datos suficientes para avanzar
    if not sesion_nueva.get("resp_presupuesto") and any(
        kw in texto_lower for kw in ["50", "100", "200", "presupuesto", "precio", "cuánto", "cuanto"]
    ):
        sesion_nueva["resp_presupuesto"] = texto
        presupuesto_map = {"menos": "hasta_50k", "50": "50k_100k", "100": "100k_200k", "200": "mas_200k"}
        for k, v in presupuesto_map.items():
            if k in texto_lower:
                sesion_nueva["presupuesto_at"] = v
                break
        SESIONES[telefono] = sesion_nueva

    if not sesion_nueva.get("resp_urgencia") and any(
        kw in texto_lower for kw in ["ahora", "urgente", "ya", "meses", "año", "explorando", "viendo"]
    ):
        sesion_nueva["resp_urgencia"] = texto
        SESIONES[telefono] = sesion_nueva


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
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "lovbot_webhook_2026")

@router.get("/whatsapp")
async def verificar_webhook_meta(request: Request):
    """Handshake de verificación de Meta (GET con hub.challenge)."""
    from fastapi.responses import PlainTextResponse, Response
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=200)
    return Response(status_code=403)


@router.post("/whatsapp")
async def webhook_whatsapp(request: Request):
    """Recibe mensajes — soporta payload bridge interno y Meta Graph API completo.

    Si viene de Meta extrae automáticamente:
    - Teléfono del cliente (msg.from)
    - Nombre del contacto (contacts[0].profile.name) → precarga en sesión
    - Texto del mensaje
    - Referral del anuncio (msg.referral) si vino de un Click-to-WhatsApp ad
      → headline, body, source_url, source_id, image_url, etc.
    """
    data = await request.json()

    # Caso 1: payload directo del bridge interno {from, text, referral?, nombre?}
    telefono = data.get("from", "")
    texto    = data.get("text", "")
    referral = data.get("referral", {}) or {}
    nombre_meta = data.get("nombre", "")

    # Caso 2: payload crudo de Meta Graph API
    if not telefono and "entry" in data:
        try:
            entry = data["entry"][0]
            change = entry["changes"][0]
            value = change["value"]
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])

            if messages:
                msg = messages[0]
                telefono = msg.get("from", "")
                # Soportar varios tipos de mensaje
                msg_type = msg.get("type", "")
                if msg_type == "text":
                    texto = msg.get("text", {}).get("body", "")
                elif msg_type == "button":
                    texto = msg.get("button", {}).get("text", "")
                elif msg_type == "interactive":
                    inter = msg.get("interactive", {})
                    if inter.get("type") == "button_reply":
                        texto = inter.get("button_reply", {}).get("title", "")
                    elif inter.get("type") == "list_reply":
                        texto = inter.get("list_reply", {}).get("title", "")

                # Referral del anuncio (CRÍTICO para Caso A)
                if "referral" in msg:
                    ref = msg["referral"]
                    referral = {
                        "source_url": ref.get("source_url", ""),
                        "source_id": ref.get("source_id", ""),
                        "source_type": ref.get("source_type", ""),
                        "headline": ref.get("headline", ""),
                        "body": ref.get("body", ""),
                        "media_type": ref.get("media_type", ""),
                        "image_url": ref.get("image_url", ""),
                        "thumbnail_url": ref.get("thumbnail_url", ""),
                    }

            # Nombre del contacto (Meta lo trae aunque no sea Lead Ads form)
            if contacts:
                profile = contacts[0].get("profile", {})
                nombre_meta = profile.get("name", "")
        except (KeyError, IndexError, TypeError) as e:
            print(f"[WEBHOOK] Error parseando Meta payload: {e}")
            return {"status": "ignored", "reason": "payload no reconocido"}

    if not telefono or not texto:
        return {"status": "ignored"}

    # Pre-cargar nombre en sesión si vino del payload y no está ya guardado
    tel_clean = re.sub(r'\D', '', telefono)
    if nombre_meta:
        sesion_pre = SESIONES.get(tel_clean, {})
        if not sesion_pre.get("nombre"):
            sesion_pre["nombre"] = nombre_meta.title()
            SESIONES[tel_clean] = sesion_pre
            print(f"[WEBHOOK] Nombre precargado desde Meta: {nombre_meta} → {tel_clean}")

    if referral and (referral.get("headline") or referral.get("source_url")):
        print(f"[WEBHOOK] Lead vino de ad: {referral.get('headline', '')[:60]}")

    threading.Thread(target=_procesar, args=(tel_clean, texto, referral), daemon=True).start()
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

@router.get("/crm/leads")
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
# RESÚMENES DE CONVERSACIÓN — IA
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/admin/setup-resumenes")
def setup_resumenes():
    """Crea la tabla resumenes_conversacion en PostgreSQL."""
    _check_pg()
    return db.crear_tabla_resumenes()


@router.post("/admin/reset-sesion/{telefono}")
def reset_sesion_bot(telefono: str):
    """Borra la sesión del bot para empezar fresh (útil para testing)."""
    tel = re.sub(r'\D', '', telefono)
    if tel in SESIONES:
        del SESIONES[tel]
    if tel in HISTORIAL:
        del HISTORIAL[tel]
    if USE_POSTGRES:
        try:
            db.delete_bot_session(tel)
        except Exception as e:
            return {"status": "partial", "ram": "ok", "db_error": str(e)}
    return {"status": "ok", "telefono": tel, "mensaje": "Sesión y historial borrados"}


@router.post("/admin/simular-lead-anuncio/{telefono}")
async def simular_lead_anuncio(telefono: str, request: Request):
    """Simula un lead llegando desde un anuncio Meta Ads (para testing Caso A).
    Body: {
      "headline": "Casa 3 dorm en San Ignacio - USD 145k",
      "body": "...",
      "nombre": "Arnaldo Ayala",   # opcional — simula Lead Ads form
      "email": "arnaldo@gmail.com" # opcional — simula Lead Ads form
    }"""
    tel = re.sub(r'\D', '', telefono)
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    referral = {
        "headline": body.get("headline", "Casa 3 dorm en San Ignacio - USD 145k"),
        "body": body.get("body", "Hermosa casa con piscina"),
        "source_url": body.get("source_url", "fb.com/ad/123"),
    }

    # Si el ad es "Lead Ads" (form), Meta nos pasa nombre y email — los pre-cargamos
    nombre_ads = body.get("nombre", "").strip()
    email_ads = body.get("email", "").strip()
    if nombre_ads or email_ads:
        sesion_pre = SESIONES.get(tel, {})
        if nombre_ads:
            sesion_pre["nombre"] = nombre_ads.title()
        if email_ads:
            sesion_pre["email"] = email_ads
        sesion_pre["origen_lead"] = "meta_ads_form"
        SESIONES[tel] = sesion_pre

    primer_mensaje = body.get("mensaje", "Hola, me interesa la propiedad que vi en el anuncio")
    threading.Thread(target=_procesar, args=(tel, primer_mensaje, referral), daemon=True).start()
    return {
        "status": "processing",
        "telefono": tel,
        "referral": referral,
        "mensaje": primer_mensaje,
        "datos_precargados": {"nombre": nombre_ads, "email": email_ads} if (nombre_ads or email_ads) else None
    }


def _generar_resumen_lead(lead: dict) -> dict:
    """Llama a GPT con los datos del lead para generar resumen sintético."""
    nombre = f"{lead.get('nombre', '')} {lead.get('apellido', '')}".strip() or "Lead sin nombre"
    presupuesto = lead.get("presupuesto") or "no informado"
    zona = lead.get("zona") or "no informada"
    tipo = lead.get("tipo_propiedad") or "no especificado"
    operacion = lead.get("operacion") or "no especificada"
    score_str = lead.get("score") or ""
    notas = lead.get("notas_bot") or ""
    fecha_cita = lead.get("fecha_cita")
    estado = lead.get("estado") or ""
    ciudad = lead.get("ciudad") or ""

    contexto = f"""Lead: {nombre}
Telefono: {lead.get('telefono', '')}
Operacion: {operacion}
Tipo de propiedad: {tipo}
Zona/Ciudad: {zona} {ciudad}
Presupuesto: {presupuesto}
Score: {score_str}
Estado: {estado}
Fecha de cita: {fecha_cita}
Notas del bot: {notas}"""

    system = "Sos un asistente comercial. Generá resúmenes claros, profesionales y concisos para que el comercial llegue preparado a la cita."
    prompt = f"""Datos del lead que tuvo conversación con el bot y agendó una cita:

{contexto}

Devolvé SOLO un JSON válido con esta estructura exacta (sin markdown, sin explicaciones):
{{
  "resumen": "Resumen ejecutivo de 2-3 oraciones para el comercial. Mencionar interés principal, presupuesto y notas relevantes.",
  "presupuesto": "Texto corto del presupuesto (ej: 'USD 100k-200k')",
  "zona": "Zona de interés",
  "urgencia": "Alta / Media / Baja según las notas",
  "financiamiento": "Tipo de pago si aparece en notas (ej: 'Contado', 'Crédito', 'No especificado')",
  "score": 1-5 según calidad del lead (5 = muy caliente, 1 = frío)
}}"""
    try:
        respuesta = _llm(prompt, system)
        import re as _re
        match = _re.search(r'\{[\s\S]*\}', respuesta)
        if not match:
            return {"error": "GPT no devolvió JSON válido", "raw": respuesta[:200]}
        data = json.loads(match.group(0))
        data["telefono"] = lead.get("telefono")
        data["nombre"] = nombre
        data["lead_id"] = lead.get("id")
        return {"ok": True, "data": data}
    except Exception as e:
        return {"error": f"Error generando resumen: {e}"}


@router.post("/crm/resumenes/generar/{telefono}")
def generar_resumen_telefono(telefono: str):
    """Genera resumen para un lead específico (debe tener fecha_cita)."""
    _check_pg()
    leads = db.get_leads_con_cita(solo_sin_resumen=False)
    lead = next((l for l in leads if l.get("telefono") == telefono), None)
    if not lead:
        return {"error": "Lead no encontrado o sin cita agendada"}
    res = _generar_resumen_lead(lead)
    if "error" in res:
        return res
    saved = db.guardar_resumen(res["data"])
    return {"ok": True, "resumen": res["data"], "saved": saved}


@router.post("/crm/resumenes/generar-todos")
def generar_resumenes_todos(solo_pendientes: bool = True):
    """Itera sobre leads con cita y genera resúmenes."""
    _check_pg()
    leads = db.get_leads_con_cita(solo_sin_resumen=solo_pendientes)
    if not leads:
        return {"ok": True, "procesados": 0, "mensaje": "No hay leads pendientes de resumen"}
    resultados = {"procesados": 0, "ok": 0, "errores": []}
    for lead in leads:
        resultados["procesados"] += 1
        res = _generar_resumen_lead(lead)
        if "error" in res:
            resultados["errores"].append({"telefono": lead.get("telefono"), "error": res["error"]})
            continue
        saved = db.guardar_resumen(res["data"])
        if "error" in saved:
            resultados["errores"].append({"telefono": lead.get("telefono"), "error": saved["error"]})
        else:
            resultados["ok"] += 1
    return {"ok": True, **resultados}


@router.get("/crm/resumenes")
def crm_resumenes(limit: int = 20, score_min: int = None,
                   desde: str = None, search: str = None):
    """Lista resúmenes con filtros: limit, score_min, desde (YYYY-MM-DD), search (texto libre)."""
    _check_pg()
    rows = db.listar_resumenes(limit=limit, score_min=score_min, desde=desde, search=search)
    for r in rows:
        for k in ("fecha_conversacion", "created_at"):
            if r.get(k):
                r[k] = r[k].isoformat()
    return {"total": len(rows), "records": rows}


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
