"""
Worker — Mica (System IA) — Demo Inmobiliaria
==============================================
Clon del worker de Robert (Lovbot Inmobiliaria v2) adaptado a Mica.
Mismo flow: precalificación Gemini + Airtable + Cal.com.
Canal: Evolution API (en vez de Meta Graph API).

Variables de entorno:
  EVOLUTION_API_URL              URL base Evolution API (compartida)
  EVOLUTION_API_KEY              API key Evolution (compartida)
  MICA_DEMO_EVOLUTION_INSTANCE   Nombre instancia = "Demos"
  GEMINI_API_KEY                 Compartida
  AIRTABLE_API_KEY               Token Airtable compartido
  MICA_AIRTABLE_BASE_ID          Base ID Airtable Mica
  MICA_DEMO_AIRTABLE_TABLE_PROPS     ID tabla propiedades
  MICA_DEMO_AIRTABLE_TABLE_CLIENTES  ID tabla clientes/leads
  MICA_DEMO_AIRTABLE_TABLE_ACTIVOS   ID tabla activos

  MICA_DEMO_NOMBRE         Nombre empresa
  MICA_DEMO_CIUDAD         Ciudad
  MICA_DEMO_ASESOR         Nombre asesor
  MICA_DEMO_NUMERO_ASESOR  Número asesor para notificaciones
  MICA_DEMO_ZONAS          Zonas separadas por coma
  MICA_DEMO_MONEDA         Moneda (def: USD)
  MICA_DEMO_SITIO_WEB      URL del sitio web (opcional)
  MICA_DEMO_CAL_API_KEY    API Key Cal.com
  MICA_DEMO_CAL_EVENT_ID   Event Type ID Cal.com
"""

import os
import re
import json
import tempfile
import threading
import requests
import base64 as b64
from urllib.parse import quote
from google import genai
from fastapi import APIRouter, Request

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
EVOLUTION_API_URL  = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_API_KEY  = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("MICA_DEMO_EVOLUTION_INSTANCE", "Demos")

AIRTABLE_TOKEN         = os.environ.get("AIRTABLE_API_KEY", "") or os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID       = os.environ.get("MICA_AIRTABLE_BASE_ID", "") or os.environ.get("MICA_DEMO_AIRTABLE_BASE", "")
AIRTABLE_TABLE_PROPS   = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_PROPS", "")
AIRTABLE_TABLE_LEADS   = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_CLIENTES", "")
AIRTABLE_TABLE_ACTIVOS = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_ACTIVOS", "")

NOMBRE_EMPRESA = os.environ.get("MICA_DEMO_NOMBRE",  "System IA — Demo Inmobiliaria")
CIUDAD         = os.environ.get("MICA_DEMO_CIUDAD",  "Argentina")
NOMBRE_ASESOR  = os.environ.get("MICA_DEMO_ASESOR",  "Micaela")
NUMERO_ASESOR  = os.environ.get("MICA_DEMO_NUMERO_ASESOR", "")
MONEDA         = os.environ.get("MICA_DEMO_MONEDA",  "USD")
SITIO_WEB      = os.environ.get("MICA_DEMO_SITIO_WEB", "")
CAL_API_KEY    = os.environ.get("MICA_DEMO_CAL_API_KEY", "")
CAL_EVENT_ID   = os.environ.get("MICA_DEMO_CAL_EVENT_ID", "")

_zonas_raw = os.environ.get("MICA_DEMO_ZONAS", "Zona Norte,Zona Sur,Zona Centro")
ZONAS_LIST = [z.strip() for z in _zonas_raw.split(",") if z.strip()]

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(prefix="/mica/demos/inmobiliaria", tags=["Mica — Demo Inmobiliaria"])

# ─── DB POSTGRES — persistencia de sesiones ───────────────────────────────────
try:
    from workers.clientes.system_ia.demos.inmobiliaria import db_postgres as db_mica
    USE_POSTGRES = db_mica._available()
    if USE_POSTGRES:
        print("[MICA] ✅ PostgreSQL disponible — sesiones persistentes")
    else:
        print("[MICA] ⚠️ PostgreSQL no configurado — sesiones solo en RAM")
except ImportError:
    USE_POSTGRES = False
    db_mica = None
    print("[MICA] ⚠️ db_postgres no encontrado — sesiones solo en RAM")

# ─── SESIONES + HISTORIAL — cache RAM + PostgreSQL ────────────────────────────
HISTORIAL: dict[str, list[str]] = {}


def _bg_save_session_mica(telefono: str, sesion: dict) -> None:
    if not USE_POSTGRES:
        return
    tel = re.sub(r'\D', '', telefono)
    hist = HISTORIAL.get(tel, [])
    try:
        db_mica.save_bot_session(telefono, sesion, hist)
    except Exception as e:
        print(f"[MICA-SESSION] Error save: {e}")


def _bg_delete_session_mica(telefono: str) -> None:
    if not USE_POSTGRES:
        return
    try:
        db_mica.delete_bot_session(telefono)
    except Exception as e:
        print(f"[MICA-SESSION] Error delete: {e}")


class _SessionStoreMica(dict):
    """Dict que auto-persiste en PostgreSQL en background en cada write/delete."""

    def __setitem__(self, telefono: str, sesion: dict):
        super().__setitem__(telefono, sesion)
        if USE_POSTGRES:
            threading.Thread(target=_bg_save_session_mica, args=(telefono, sesion), daemon=True).start()

    def pop(self, telefono, *args):
        result = super().pop(telefono, *args)
        if USE_POSTGRES:
            threading.Thread(target=_bg_delete_session_mica, args=(telefono,), daemon=True).start()
        return result


SESIONES: _SessionStoreMica = _SessionStoreMica()

# Inicializar tabla al arrancar
if USE_POSTGRES:
    try:
        db_mica.setup_bot_sessions()
    except Exception as _e:
        print(f"[MICA-SESSION] setup_bot_sessions error: {_e}")


def _cargar_sesion_mica(telefono: str) -> None:
    """Restaura sesión + historial desde PostgreSQL al cache RAM (post-deploy)."""
    if not USE_POSTGRES:
        return
    tel = re.sub(r'\D', '', telefono)
    try:
        data = db_mica.get_bot_session(telefono)
        if data:
            sesion = data.get("sesion", {})
            historial = data.get("historial", [])
            if sesion:
                super(_SessionStoreMica, SESIONES).__setitem__(telefono, sesion)
                print(f"[MICA-SESSION] Sesión restaurada {tel[-4:]}*** step={sesion.get('step','?')}")
            if historial:
                HISTORIAL[tel] = historial
    except Exception as e:
        print(f"[MICA-SESSION] Error carga: {e}")

# ─── WHISPER — TRANSCRIPCIÓN DE AUDIO (Evolution API) ────────────────────────
def _transcribir_audio(data: dict, message: dict) -> str:
    """
    Transcribe una nota de voz de WhatsApp usando Whisper (OpenAI).
    Descarga el audio vía Evolution API getBase64FromMediaMessage.
    Fallback: URL directa con/sin apikey.
    Retorna el texto transcripto o "" si falla.
    """
    import openai as _openai

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        print("[Whisper-Mica] Sin OPENAI_API_KEY — omitiendo transcripción")
        return ""

    audio_bytes  = None
    content_type = ""
    audio_url    = ""

    MIME_EXT = {
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mpga": ".mp3",
        "audio/ogg":  ".ogg", "audio/opus": ".ogg",
        "audio/wav":  ".wav", "audio/x-wav": ".wav",
        "audio/mp4":  ".m4a", "audio/m4a": ".m4a",
        "audio/webm": ".webm", "audio/flac": ".flac",
    }

    def _ext(ct: str, url: str) -> str:
        for mime, ext in MIME_EXT.items():
            if mime in ct.lower(): return ext
        for ext in [".mp3", ".ogg", ".wav", ".m4a", ".webm", ".flac", ".oga", ".mpga"]:
            if url.lower().endswith(ext): return ext
        return ".ogg"  # WhatsApp PTT siempre es OGG/Opus

    # ── Método 0: Evolution getBase64FromMediaMessage (más confiable) ─────
    try:
        msg_payload = {"key": data.get("key", {}), "message": message}
        resp = requests.post(
            f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{quote(EVOLUTION_INSTANCE)}",
            json={"message": msg_payload, "convertToMp4": False},
            headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            b64_data = resp.json().get("base64", "")
            if b64_data:
                audio_bytes  = b64.b64decode(b64_data)
                audio_info   = message.get("audioMessage", message.get("pttMessage", {}))
                content_type = audio_info.get("mimetype", "audio/ogg")
                audio_url    = audio_info.get("url", "")
                print(f"[Whisper-Mica] getBase64 OK — {len(audio_bytes)} bytes — {content_type}")
            else:
                print("[Whisper-Mica] getBase64 sin base64 en respuesta")
        else:
            print(f"[Whisper-Mica] getBase64 status={resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Whisper-Mica] getBase64 FALLÓ: {e}")

    # ── Método 1: URL directa sin auth ────────────────────────────────────
    if not audio_bytes:
        audio_info = message.get("audioMessage", message.get("pttMessage", {}))
        audio_url  = audio_info.get("url", "")
        if audio_url:
            try:
                r = requests.get(audio_url, timeout=15)
                if r.status_code == 200 and len(r.content) > 100:
                    audio_bytes  = r.content
                    content_type = r.headers.get("Content-Type", "audio/ogg")
                    print(f"[Whisper-Mica] URL directa OK — {len(audio_bytes)} bytes")
            except Exception as e:
                print(f"[Whisper-Mica] URL directa FALLÓ: {e}")

    # ── Método 2: URL con apikey ──────────────────────────────────────────
    if not audio_bytes and audio_url:
        try:
            r = requests.get(audio_url, headers={"apikey": EVOLUTION_API_KEY}, timeout=15)
            if r.status_code == 200 and len(r.content) > 100:
                audio_bytes  = r.content
                content_type = r.headers.get("Content-Type", "audio/ogg")
                print(f"[Whisper-Mica] URL+auth OK — {len(audio_bytes)} bytes")
        except Exception as e:
            print(f"[Whisper-Mica] URL+auth FALLÓ: {e}")

    if not audio_bytes:
        print("[Whisper-Mica] Ningún método obtuvo el audio")
        return ""

    # ── Transcribir con Whisper ───────────────────────────────────────────
    ext = _ext(content_type, audio_url)
    try:
        cliente = _openai.OpenAI(api_key=openai_key)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as f:
            transcripcion = cliente.audio.transcriptions.create(
                model="whisper-1", file=f, language="es"
            )
        os.unlink(tmp_path)
        texto = transcripcion.text.strip()
        print(f"[Whisper-Mica] Transcripción: '{texto}'")
        return texto
    except Exception as e:
        print(f"[Whisper-Mica] Error al transcribir: {e}")
        return ""

AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


# ─── EVOLUTION API ────────────────────────────────────────────────────────────
def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        print(f"[MICA-EVO] Sin config. Msg: {mensaje[:80]}")
        return False
    try:
        r = requests.post(
            f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            headers={"Content-Type": "application/json", "apikey": EVOLUTION_API_KEY},
            json={"number": re.sub(r'\D', '', telefono), "text": mensaje},
            timeout=10,
        )
        if r.status_code not in (200, 201):
            print(f"[MICA-EVO] Error {r.status_code}: {r.text[:300]}")
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[MICA-EVO] Excepción: {e}")
        return False


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not url_imagen:
        return False
    try:
        r = requests.post(
            f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}",
            headers={"Content-Type": "application/json", "apikey": EVOLUTION_API_KEY},
            json={
                "number": re.sub(r'\D', '', telefono),
                "mediatype": "image",
                "media": url_imagen,
                "caption": caption,
            },
            timeout=10,
        )
        if r.status_code not in (200, 201):
            print(f"[MICA-EVO] Error imagen {r.status_code}: {r.text[:300]}")
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[MICA-EVO] Excepción imagen: {e}")
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
                       ciudad: str = "", subniche: str = "") -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        print("[MICA-AT] Sin base/tabla configurada — skip registro lead")
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
        campos["Estado"] = "en_negociacion"
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

    if records:
        rec_id = records[0]["id"]
        r = requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS,
                           json={"fields": campos}, timeout=8)
        print(f"[MICA-AT] PATCH tel={telefono} status={r.status_code}")
    else:
        campos["Fecha_WhatsApp"] = date.today().isoformat()
        if "Estado" not in campos:
            campos["Estado"] = "no_contactado"
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        print(f"[MICA-AT] POST tel={telefono} status={r.status_code}")


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
        print(f"[MICA-AT] Email guardado tel={telefono}")


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
        print(f"[MICA-CAL] Error slots {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[MICA-CAL] Error slots: {e}")
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
                    "email": email or (re.sub(r'\D', '', telefono) + "@system-ia.com"),
                    "timeZone": "America/Argentina/Buenos_Aires",
                    "language": "es",
                    "phoneNumber": "+" + re.sub(r'\D', '', telefono),
                },
                "metadata": {"fuente": "WhatsApp Bot System IA", "notas": notas[:200] if notas else ""},
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json().get("data", {})
            return {"ok": True, "uid": data.get("uid", ""), "start": data.get("start", slot_time)}
        print(f"[MICA-CAL] Error {r.status_code}: {r.text[:300]}")
        return {"ok": False, "error": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_DIAS_ES = {
    "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
    "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo",
}


def _formatear_slots(slots: list[dict]) -> str:
    """Formatea slots para mostrar en WhatsApp (en español, hora Argentina)."""
    from datetime import datetime, timezone, timedelta
    lineas = []
    for i, s in enumerate(slots, 1):
        try:
            dt = datetime.fromisoformat(s["time"].replace("Z", "+00:00"))
            ar = dt.astimezone(timezone(timedelta(hours=-3)))
            dia_en = ar.strftime("%A")
            dia_es = _DIAS_ES.get(dia_en, dia_en)
            lineas.append(f"*{i}️⃣* {dia_es} {ar.strftime('%d/%m')} a las *{ar.strftime('%H:%M')}* hs")
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
                       json={"fields": {"Fecha_Cita": fecha_cita[:10], "Estado": "en_negociacion"}},
                       timeout=8)
        print(f"[MICA-AT] Cita guardada tel={telefono}")


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
        print(f"[MICA-AT] Error buscar props: {e}")
        return []


# ─── GEMINI ───────────────────────────────────────────────────────────────────
def _gemini(prompt: str) -> str:
    if not _gemini_client:
        return ""
    try:
        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"[MICA-GEMINI] Error: {e}")
        return ""


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
        texto = _gemini(prompt)
        if texto.startswith("```"):
            texto = texto.split("```")[1]
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


MAX_HISTORIAL = 20

def _agregar_historial(telefono: str, quien: str, texto: str):
    tel = re.sub(r'\D', '', telefono)
    if tel not in HISTORIAL:
        HISTORIAL[tel] = []
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M")
    HISTORIAL[tel].append(f"[{ts}] {quien}: {texto[:150]}")
    if len(HISTORIAL[tel]) > MAX_HISTORIAL:
        HISTORIAL[tel] = HISTORIAL[tel][-MAX_HISTORIAL:]


# ─── LLM (OpenAI principal → Gemini fallback) ────────────────────────────────
def _llm(prompt: str, system: str = "") -> str:
    """Llama a GPT-5-mini (principal) → Gemini 2.5 Flash (fallback)."""
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            import openai as _openai
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={"model": "gpt-5-mini", "messages": messages, "max_completion_tokens": 1500},
                timeout=15,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            print(f"[MICA-LLM] OpenAI error {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[MICA-LLM] OpenAI excepción: {e}")
    if _gemini_client:
        try:
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            resp = _gemini_client.models.generate_content(
                model="gemini-2.5-flash", contents=full_prompt)
            return resp.text.strip()
        except Exception as e:
            print(f"[MICA-LLM] Gemini fallback error: {e}")
    return ""


# ─── SYSTEM PROMPT DINÁMICO ──────────────────────────────────────────────────
def _build_system_prompt(sesion: dict, telefono: str) -> str:
    """Construye el system prompt adaptado al estado actual de la sesión."""
    nombre     = sesion.get("nombre", "")
    email      = sesion.get("email", "")
    subniche   = sesion.get("subniche", "")
    ciudad     = sesion.get("ciudad_resp", "")
    objetivo   = sesion.get("resp_objetivo", "")
    tipo       = sesion.get("resp_tipo", "")
    zona       = sesion.get("resp_zona", "")
    presupuesto= sesion.get("resp_presupuesto", "")
    urgencia   = sesion.get("resp_urgencia", "")
    score      = sesion.get("score", "")
    step       = sesion.get("step", "inicio")
    props      = sesion.get("props", [])
    slots      = sesion.get("slots", [])

    # Historial
    historial = HISTORIAL.get(re.sub(r'\D', '', telefono), [])
    historial_txt = ""
    if historial:
        lineas = []
        for h in historial[-10:]:
            h2 = h.replace("] Lead:", "] Cliente:").replace("] Bot:", "] Vos (bot):")
            lineas.append(h2)
        historial_txt = "\n".join(lineas)

    zonas_str = ", ".join(ZONAS_LIST) if ZONAS_LIST else "sin zonas definidas"

    # Datos conocidos y faltantes
    datos_conocidos = []
    if nombre:      datos_conocidos.append(f"Nombre: {nombre}")
    if email:       datos_conocidos.append(f"Email: {email}")
    if subniche:    datos_conocidos.append(f"Perfil: {subniche}")
    if ciudad:      datos_conocidos.append(f"Ciudad: {ciudad}")
    if objetivo:    datos_conocidos.append(f"Objetivo: {objetivo}")
    if tipo:        datos_conocidos.append(f"Tipo de propiedad: {tipo}")
    if zona:        datos_conocidos.append(f"Zona: {zona}")
    if presupuesto: datos_conocidos.append(f"Presupuesto: {presupuesto}")
    if urgencia:    datos_conocidos.append(f"Urgencia: {urgencia}")
    if score:       datos_conocidos.append(f"Score: {score}")
    datos_txt = "\n".join(datos_conocidos) if datos_conocidos else "Primer contacto"

    faltantes = []
    if not subniche:    faltantes.append("perfil (agencia/agente independiente/desarrolladora)")
    if not nombre:      faltantes.append("nombre")
    if not email:       faltantes.append("email (opcional)")
    if not ciudad:      faltantes.append("ciudad")
    if not objetivo:    faltantes.append("qué busca (comprar/alquilar/invertir)")
    if not tipo:        faltantes.append("tipo de propiedad")
    if not zona:        faltantes.append(f"zona (opciones: {zonas_str})")
    if not presupuesto: faltantes.append("presupuesto")
    if not urgencia:    faltantes.append("urgencia / timing")
    faltantes_txt = ", ".join(faltantes) if faltantes else "TODOS los datos obtenidos — calificar"

    props_txt = ""
    if props:
        props_txt = "\n\nPROPIEDADES ENCONTRADAS (ya en sesión):\n"
        for i, p in enumerate(props, 1):
            props_txt += f"  {i}. {p.get('Titulo','Propiedad')} — {p.get('Zona','')} — {p.get('Precio','')} {MONEDA}\n"

    slots_txt = ""
    if slots:
        slots_txt = f"\n\nSLOTS DE CITA (ya obtenidos de Cal.com):\n{_formatear_slots(slots)}"

    instruccion_step = {
        "inicio": "Primer contacto. Preguntar qué tipo de perfil tiene (agencia inmobiliaria / agente independiente / desarrolladora). Cálido y breve. Esta es una DEMO — se lo podés aclarar si pregunta.",
        "subnicho": "Identificar perfil. Podés mencionar que es una demo según el subniche elegido.",
        "nombre": "Pedir nombre. Ya tenés el perfil.",
        "email": "Pedir email (opcional). Aclarar que se usa para enviar fichas exclusivas.",
        "ciudad": "Preguntar desde qué ciudad escribe.",
        "objetivo": "Preguntar qué busca: comprar, alquilar o invertir.",
        "tipo": "Preguntar tipo de propiedad (casa, departamento, terreno, local, oficina). Sin listas numeradas.",
        "zona": f"Preguntar zona preferida. Opciones: {zonas_str}.",
        "presupuesto": f"Preguntar presupuesto en {MONEDA}. Dar referencia de rangos de forma natural.",
        "urgencia": "Preguntar cuándo piensa concretar.",
        "calificado": "Datos completos. Mostrar propiedades o derivar según score.",
        "lista": "El cliente ve la lista de propiedades. Invitarlo a pedir detalle de alguna.",
        "ficha": "El cliente ve una ficha. Preguntar si quiere agendar o tiene preguntas.",
        "ofrecer_cita": f"Ofrecer ver horarios disponibles con {NOMBRE_ASESOR} o que lo contacten.",
        "recuperacion": f"El cliente volvió. Saludarlo por nombre ({nombre}) y retomar.",
    }.get(step, "Continuar la conversación según el contexto.")

    return f"""Sos el asistente virtual de *{NOMBRE_EMPRESA}*, empresa inmobiliaria en {CIUDAD}.
El asesor humano se llama *{NOMBRE_ASESOR}*. Esto es una *demo interactiva* del sistema.

## TU MISIÓN
Calificar leads inmobiliarios de forma natural y humana — como un consultor experto por WhatsApp, NO un bot con menús numerados. El objetivo es filtrar curiosos de compradores reales: los que están interesados de verdad elaboran sus respuestas.

## PERSONALIDAD Y TONO
- Cálido, profesional, cercano. Usás *negrita* para datos clave.
- Mensajes cortos, máximo 3-4 líneas. Sin listas 1-2-3 para preguntas abiertas.
- Emojis moderados (🏡 📅 ✅). Nunca "opción 1", "opción 2" salvo para propiedades o slots.
- Si dicen "hola", "0" o "menú" → empezar amablemente de cero.

## FILTRO DE CURIOSOS
- Respuestas de una sola palabra en pasos clave → pedí que elaboren.
- Respuestas evasivas ("no sé", "solo miro", "curioseando") → pedí contexto una vez. Si insiste → ACCION: cerrar_curioso.
- Preguntas abiertas, no cerradas. "¿Qué estás buscando?" en vez de "¿Comprar o alquilar?".
- Pedí contexto emocional: "¿Para vivir o para invertir? ¿Qué te motivó a buscar ahora?".

## REGLA DE CONTEXTO (crítico para interpretar respuestas)
Antes de responder, revisá el historial para saber en qué flujo estás:
- Si el bot preguntó el nombre → el cliente te está dando su nombre
- Si el bot preguntó el email → el cliente te da su email o lo rechaza
- Si el bot preguntó la ciudad → el cliente te dice su ciudad
- Si el bot preguntó qué busca → el cliente te dice su objetivo
- Si el bot preguntó tipo de propiedad → el cliente describe qué tipo quiere
- Si el bot preguntó la zona → el cliente dice qué zona prefiere
- Si el bot preguntó el presupuesto → el cliente da una cifra o rango
- Si el bot preguntó la urgencia → el cliente dice en qué tiempo quiere concretar
⛔ NUNCA interpretés un número como opción del menú principal si estás en medio de un flujo.

## DATOS CONOCIDOS
{datos_txt}

## DATOS QUE FALTAN
{faltantes_txt}

## STEP ACTUAL: {step.upper()}
{instruccion_step}

## HISTORIAL
{historial_txt if historial_txt else "(Primer mensaje)"}
{props_txt}
{slots_txt}

## REGLAS CRÍTICAS
1. Un dato por turno — no hagas varias preguntas a la vez.
2. No repitas info que ya sabés. Si algo ya figura en DATOS CONOCIDOS, no lo preguntes de nuevo.
3. Si el cliente pide hablar con alguien o usa "#" → ACCION: ir_asesor.
4. Cuando tenés todos los datos → ACCION: calificar.
5. Siempre terminás con UNA sola pregunta o acción clara. Nunca dejés un mensaje colgado sin dirección.

## EXTRACCIÓN DE DATOS (agregar al FINAL de tu respuesta, el cliente NUNCA las ve)
Cada vez que el cliente revele un dato, extraélo en la línea correspondiente:
- Nombre → NOMBRE: Juan García
- Email → EMAIL: correo@ejemplo.com
- Perfil → SUBNICHE: agencia_inmobiliaria | agente_independiente | desarrolladora
- Ciudad donde trabaja → CIUDAD: NombreCiudad
- Qué busca (comprar/alquilar/invertir) → OBJETIVO: comprar
- Tipo de propiedad → TIPO: casa | departamento | terreno | local | oficina
- Zona preferida → ZONA: nombre_zona
- Presupuesto → PRESUPUESTO: descripción del presupuesto que dio
- Urgencia/timing → URGENCIA: descripción del timing que dio
- Para derivar al asesor → ACCION: ir_asesor
- Para calificar cuando tenés todos los datos → ACCION: calificar
- Para cerrar a un curioso (ya intentaste pedir contexto y sigue evasivo) → ACCION: cerrar_curioso

Solo incluís los que aplican en este turno. Podés incluir varios si el cliente dio varios datos a la vez.
"""


# ─── FLUJO PRINCIPAL ──────────────────────────────────────────────────────────
def _procesar(telefono: str, texto: str) -> None:
    import time as _time
    texto = texto.strip()
    texto_lower = texto.lower()

    # ── Restaurar sesión desde PostgreSQL si no está en RAM (post-deploy) ──────
    if telefono not in SESIONES:
        _cargar_sesion_mica(telefono)

    sesion = SESIONES.get(telefono, {})
    ahora_ts = _time.time()
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""

    # Registrar en historial
    _agregar_historial(telefono, "Lead", texto)

    # Comando # → asesor inmediato
    if texto_lower == "#":
        _ir_asesor(telefono, sesion)
        return

    # Timeout de sesión (>30 min) → modo recuperación
    SESSION_TIMEOUT = 30 * 60
    ultimo_ts = sesion.get("_ultimo_ts", 0)
    step = sesion.get("step", "inicio")
    if ultimo_ts and step not in ("inicio",) and (ahora_ts - ultimo_ts) > SESSION_TIMEOUT:
        sesion["step"] = "recuperacion"
    if telefono in SESIONES:
        SESIONES[telefono]["_ultimo_ts"] = ahora_ts

    step = sesion.get("step", "inicio")

    # ── Steps deterministas: agendar_slots y confirmar_cita ──────────────────
    if step == "agendar_slots":
        slots = sesion.get("slots", [])
        if texto.strip() == "0":
            _enviar_texto(telefono,
                f"¡De acuerdo! *{NOMBRE_ASESOR}* te va a contactar a la brevedad. 🏡\n"
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
                    mx = dt.astimezone(timezone(timedelta(hours=-3)))
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
                _enviar_texto(telefono, "Ese horario ya no está disponible 😔 ¿Elegimos otro? Escribí *2* o *0* para cancelar.")
        elif texto_lower in ("no", "2", "otro", "cambiar"):
            slots = sesion.get("slots", [])
            SESIONES[telefono] = {**sesion, "step": "agendar_slots"}
            _enviar_texto(telefono, f"Sin problema 😊 Elegí otro horario:\n\n{_formatear_slots(slots)}")
        else:
            _enviar_texto(telefono, "Respondé *sí* para confirmar o *no* para elegir otro horario.")
        return

    # ── NÚCLEO LLM CONVERSACIONAL ─────────────────────────────────────────────
    system_prompt = _build_system_prompt(sesion, telefono)
    respuesta_llm = _llm(texto, system=system_prompt)

    if not respuesta_llm:
        _enviar_texto(telefono, "Disculpá, tuve un problema técnico. ¿Podés repetir tu mensaje? 🙏")
        return

    # Extraer acciones ocultas
    lineas = respuesta_llm.strip().split("\n")
    acciones = {}
    texto_visible = []
    for linea in lineas:
        l = linea.strip()
        if l.startswith("ACCION:"):
            acciones["accion"] = l.split(":", 1)[1].strip()
        elif l.startswith("EMAIL:"):
            acciones["email"] = l.split(":", 1)[1].strip()
        elif l.startswith("NOMBRE:"):
            acciones["nombre"] = l.split(":", 1)[1].strip().title()
        elif l.startswith("SUBNICHE:"):
            acciones["subniche"] = l.split(":", 1)[1].strip()
        elif l.startswith("CIUDAD:"):
            acciones["ciudad"] = l.split(":", 1)[1].strip().title()
        elif l.startswith("OBJETIVO:"):
            acciones["objetivo"] = l.split(":", 1)[1].strip().lower()
        elif l.startswith("TIPO:"):
            acciones["tipo"] = l.split(":", 1)[1].strip().lower()
        elif l.startswith("ZONA:"):
            acciones["zona"] = l.split(":", 1)[1].strip()
        elif l.startswith("PRESUPUESTO:"):
            acciones["presupuesto"] = l.split(":", 1)[1].strip()
        elif l.startswith("URGENCIA:"):
            acciones["urgencia"] = l.split(":", 1)[1].strip()
        else:
            texto_visible.append(linea)
    mensaje_final = "\n".join(texto_visible).strip()

    # Actualizar sesión con datos extraídos
    sesion_nueva = dict(sesion)
    sesion_nueva["_ultimo_ts"] = ahora_ts

    if "nombre" in acciones and not sesion_nueva.get("nombre"):
        sesion_nueva["nombre"] = acciones["nombre"]
        nombre = acciones["nombre"]
        nombre_corto = nombre.split()[0]

    if "email" in acciones and not sesion_nueva.get("email"):
        sesion_nueva["email"] = acciones["email"]
        threading.Thread(target=_at_guardar_email, args=(telefono, acciones["email"]), daemon=True).start()

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

    # Inferencia progresiva desde texto del usuario (backup si LLM no puso directive)
    if not sesion_nueva.get("resp_objetivo"):
        for kw, val in [("comprar","venta"),("alquilar","alquiler"),("invertir","venta"),("venta","venta")]:
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

    if not sesion_nueva.get("resp_presupuesto") and any(
        kw in texto_lower for kw in ["50", "100", "200", "presupuesto", "precio"]
    ):
        sesion_nueva["resp_presupuesto"] = texto
        for k, v in [("menos", "hasta_50k"), ("50", "50k_100k"), ("100", "100k_200k"), ("200", "mas_200k")]:
            if k in texto_lower:
                sesion_nueva["presupuesto_at"] = v
                break

    if not sesion_nueva.get("resp_urgencia") and any(
        kw in texto_lower for kw in ["ahora", "urgente", "ya", "meses", "año", "explorando"]
    ):
        sesion_nueva["resp_urgencia"] = texto

    # Verificar si datos completos → calificar
    datos_completos = all([
        sesion_nueva.get("nombre"),
        sesion_nueva.get("resp_objetivo") or sesion_nueva.get("operacion_at"),
        sesion_nueva.get("resp_tipo"),
        sesion_nueva.get("resp_presupuesto") or sesion_nueva.get("presupuesto_at"),
        sesion_nueva.get("resp_urgencia"),
    ])

    SESIONES[telefono] = sesion_nueva

    # ── Ejecutar ACCION ────────────────────────────────────────────────────────
    accion = acciones.get("accion", "")

    if accion == "ir_asesor":
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)
        _ir_asesor(telefono, sesion_nueva)
        return

    if accion == "cerrar_curioso":
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)
        threading.Thread(target=_at_registrar_lead, args=(
            telefono, nombre or "Sin nombre", "frio",
            sesion_nueva.get("resp_tipo",""), sesion_nueva.get("resp_zona",""),
            "Lead evasivo/curioso — filtrado por bot",
            sesion_nueva.get("presupuesto_at",""), sesion_nueva.get("operacion_at",""),
            sesion_nueva.get("ciudad_resp", CIUDAD), sesion_nueva.get("subniche",""),
        ), daemon=True).start()
        SESIONES.pop(telefono, None)
        return

    if accion == "calificar" or datos_completos:
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)

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

        threading.Thread(target=_at_registrar_lead, args=(
            telefono, nombre, score, tipo, zona, nota,
            sesion_nueva.get("presupuesto_at",""), sesion_nueva.get("operacion_at",""),
            sesion_nueva.get("ciudad_resp", CIUDAD), sesion_nueva.get("subniche",""),
        ), daemon=True).start()
        threading.Thread(target=_notificar_asesor, args=(telefono, sesion_nueva, calificacion), daemon=True).start()

        if derivar or score == "frio":
            web_line = f"🌐 *{SITIO_WEB}*\n\n" if SITIO_WEB else ""
            _enviar_texto(telefono, MSG_SITIO_WEB.format(
                nombre=nombre_corto or nombre, web_line=web_line, asesor=NOMBRE_ASESOR))
            SESIONES.pop(telefono, None)
            return

        props = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona,
                                       presupuesto=sesion_nueva.get("presupuesto_at",""))
        if not props:
            if _cal_disponible():
                slots = _cal_obtener_slots()
                if slots:
                    SESIONES[telefono] = {**sesion_nueva, "step": "agendar_slots", "slots": slots}
                    _enviar_texto(telefono,
                        f"No tenemos propiedades con esas características publicadas ahora, "
                        f"pero *{NOMBRE_ASESOR}* maneja opciones exclusivas. 🏡\n\n"
                        f"Te muestro sus horarios disponibles:\n\n"
                        f"{_formatear_slots(slots)}\n\nElegí un número o *0* para que te contactemos.")
                    return
            _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
                nombre=nombre_corto or nombre, asesor=NOMBRE_ASESOR, empresa=NOMBRE_EMPRESA))
            SESIONES.pop(telefono, None)
            return

        SESIONES[telefono] = {**sesion_nueva, "step": "lista", "props": props,
                              "tipo": tipo, "zona": zona, "operacion": operacion}
        _enviar_texto(telefono, f"Encontré propiedades que coinciden con lo que buscás 👇")
        _enviar_texto(telefono, _lista_titulos(props))
        return

    # Navegación lista/ficha
    if step == "lista":
        props = sesion.get("props", [])
        if texto.strip() == "+":
            _enviar_texto(telefono, _lista_titulos(props))
            return
        try:
            idx = int(texto) - 1
            if 0 <= idx < len(props):
                SESIONES[telefono] = {**sesion_nueva, "step": "ficha", "ficha_actual": idx}
                _enviar_ficha(telefono, props[idx])
                return
        except ValueError:
            pass
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
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
            _agregar_historial(telefono, "Bot", mensaje_final)
        return

    # Respuesta LLM estándar
    if mensaje_final:
        _enviar_texto(telefono, mensaje_final)
        _agregar_historial(telefono, "Bot", mensaje_final)


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
    SESIONES.pop(telefono, None)


# ─── ENDPOINT WEBHOOK ─────────────────────────────────────────────────────────
@router.post("/whatsapp")
async def webhook_whatsapp(request: Request):
    """Recibe mensajes directamente desde Evolution API."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error"}

    # Evolution manda "MESSAGES_UPSERT" (uppercase) o "messages.upsert"
    event = body.get("event", "").lower().replace("_", ".")
    if event and event != "messages.upsert":
        return {"status": "ignored", "event": event}

    data    = body.get("data", body)
    key     = data.get("key", {})
    message = data.get("message", {})

    # Ignorar mensajes propios del bot
    if key.get("fromMe"):
        return {"status": "ignored", "reason": "fromMe"}

    # Extraer teléfono — Evolution usa "549XXXX@s.whatsapp.net"
    remote_jid = key.get("remoteJid", "")
    telefono   = re.sub(r'@.*', '', remote_jid)

    # Extraer texto según tipo de mensaje
    texto = ""
    msg_type = list(message.keys())[0] if message else ""
    if msg_type == "conversation":
        texto = message.get("conversation", "")
    elif msg_type == "extendedTextMessage":
        texto = message.get("extendedTextMessage", {}).get("text", "")
    elif msg_type == "buttonsResponseMessage":
        texto = message.get("buttonsResponseMessage", {}).get("selectedDisplayText", "")
    elif msg_type == "listResponseMessage":
        texto = message.get("listResponseMessage", {}).get("title", "")
    elif msg_type in ("audioMessage", "pttMessage"):
        # Nota de voz → transcribir con Whisper y procesar como texto
        print(f"[MICA-EVO] Audio recibido de {telefono} — transcribiendo...")
        texto = _transcribir_audio(data, message)
        if not texto:
            # Sin transcripción → avisar al usuario
            threading.Thread(
                target=_enviar_texto,
                args=(telefono, "Recibí tu nota de voz, pero no pude entenderla bien. ¿Podés escribirme? 🙏"),
                daemon=True,
            ).start()
            return {"status": "audio_sin_transcripcion"}
    elif msg_type in ("imageMessage", "videoMessage", "documentMessage", "stickerMessage"):
        return {"status": "ignored", "reason": f"media: {msg_type}"}

    if not telefono or not texto:
        return {"status": "ignored", "reason": "sin telefono o texto"}

    # Capturar nombre del perfil si viene
    push_name = data.get("pushName", "")
    if push_name and telefono not in SESIONES:
        SESIONES[telefono] = {"nombre": push_name}
    elif push_name and not SESIONES.get(telefono, {}).get("nombre"):
        SESIONES.setdefault(telefono, {})["nombre"] = push_name

    threading.Thread(target=_procesar, args=(telefono, texto), daemon=True).start()
    return {"status": "processing", "telefono": telefono}


# ─── MÉTRICAS ────────────────────────────────────────────────────────────────
@router.get("/crm/metricas")
def crm_metricas():
    """Métricas del pipeline calculadas desde Airtable."""
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return {"error": "Airtable no configurado"}
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
        por_estado, con_cita, cerrados = {}, 0, 0
        scores = {"caliente": 0, "tibio": 0, "frio": 0}
        fuentes = {}
        for rec in records:
            f = rec.get("fields", {})
            e = f.get("Estado", "no_contactado")
            por_estado[e] = por_estado.get(e, 0) + 1
            if f.get("Fecha_Cita") or "CITA AGENDADA" in (f.get("Notas_Bot") or ""):
                con_cita += 1
            if e == "cerrado":
                cerrados += 1
            s = f.get("Score", 0) or 0
            if s >= 12:   scores["caliente"] += 1
            elif s >= 7:  scores["tibio"] += 1
            else:         scores["frio"] += 1
            fu = f.get("Fuente", "desconocido")
            fuentes[fu] = fuentes.get(fu, 0) + 1
        return {
            "total": total,
            "por_estado": por_estado,
            "scores": scores,
            "fuentes": fuentes,
            "con_cita": con_cita,
            "cerrados_ganados": cerrados,
            "tasa_citas":  round((con_cita / total) * 100, 1) if total else 0,
            "tasa_cierre": round((cerrados / total) * 100, 1) if total else 0,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── CRM ENDPOINTS ────────────────────────────────────────────────────────────
@router.get("/crm/clientes")
def crm_clientes():
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return {"records": [], "error": "Airtable no configurado"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset = data.get("offset")
        if not offset:
            break
    return {"total": len(records), "records": records}


@router.patch("/crm/clientes/{record_id}")
async def crm_actualizar_cliente(record_id: str, request: Request):
    from fastapi import HTTPException
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        return {"status": "error", "detalle": "Airtable no configurado"}
    body = await request.json()
    CAMPOS_VALIDOS = {
        "Nombre", "Apellido", "Telefono", "Email", "Operacion", "Tipo_Propiedad",
        "Presupuesto", "Zona", "Estado", "Notas_Bot", "Fuente", "Llego_WhatsApp",
    }
    ESTADOS_VALIDOS = {"no_contactado", "contactado", "en_negociacion", "cerrado", "descartado"}
    fields = body.get("fields", body)
    campos = {k: v for k, v in fields.items() if k in CAMPOS_VALIDOS and v is not None}
    if "Estado" in campos and campos["Estado"] not in ESTADOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Valores: {sorted(ESTADOS_VALIDOS)}")
    if not campos:
        return {"status": "error", "detalle": "Nada que actualizar"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
    if r.status_code in (200, 201):
        return {"status": "ok", "record_id": record_id, "campos": campos}
    raise HTTPException(status_code=r.status_code, detail=r.text[:200])


@router.post("/crm/clientes")
async def crm_crear_cliente(request: Request):
    from fastapi import HTTPException
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        raise HTTPException(status_code=500, detail="Airtable no configurado")
    data = await request.json()
    CAMPOS_VALIDOS = {
        "Nombre", "Apellido", "Telefono", "Email", "Operacion", "Tipo_Propiedad",
        "Presupuesto", "Zona", "Estado", "Notas_Bot", "Fuente", "Llego_WhatsApp",
    }
    campos = {k: v for k, v in data.items() if k in CAMPOS_VALIDOS and v is not None}
    campos.setdefault("Estado", "no_contactado")
    ESTADOS_VALIDOS = {"no_contactado", "contactado", "en_negociacion", "cerrado", "descartado"}
    if campos["Estado"] not in ESTADOS_VALIDOS:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {campos['Estado']}")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.get("/crm/propiedades")
def crm_propiedades():
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return {"records": [], "error": "Airtable no configurado"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset = data.get("offset")
        if not offset:
            break
    return {"total": len(records), "records": records}


@router.get("/crm/activos")
def crm_activos():
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        return {"records": [], "error": "Airtable no configurado"}
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset = data.get("offset")
        if not offset:
            break
    return {"total": len(records), "records": records}


@router.post("/crm/activos")
async def crm_crear_activo(request: Request):
    from fastapi import HTTPException
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        raise HTTPException(status_code=500, detail="Airtable no configurado")
    data = await request.json()
    fields = data.get("fields", data)
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.patch("/crm/activos/{record_id}")
async def crm_actualizar_activo(record_id: str, request: Request):
    from fastapi import HTTPException
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        raise HTTPException(status_code=500, detail="Airtable no configurado")
    data = await request.json()
    fields = data.get("fields", data)
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": fields}, timeout=8)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.delete("/crm/activos/{record_id}")
def crm_eliminar_activo(record_id: str):
    from fastapi import HTTPException
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_ACTIVOS:
        raise HTTPException(status_code=500, detail="Airtable no configurado")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}/{record_id}"
    r = requests.delete(url, headers=AT_HEADERS, timeout=8)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "deleted": record_id}
