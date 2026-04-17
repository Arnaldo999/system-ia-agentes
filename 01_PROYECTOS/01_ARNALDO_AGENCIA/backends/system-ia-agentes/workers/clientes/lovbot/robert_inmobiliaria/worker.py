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
OPENAI_API_KEY    = os.environ.get("LOVBOT_OPENAI_API_KEY", "")
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


def _restaurar_lead_desde_db(telefono: str) -> bool:
    """Si el lead ya existe en PostgreSQL `leads` (escribió antes), restaura sus
    datos como 'lead recurrente' para que el bot lo salude por nombre y no pida
    datos otra vez.

    Robert usa PostgreSQL `robert_crm` (NO Airtable).
    Returns True si encontró y restauró el lead.
    """
    if not USE_POSTGRES:
        return False
    tel = re.sub(r'\D', '', telefono)
    if tel in SESIONES:
        return False  # ya tiene sesión activa
    try:
        lead = db.get_lead_by_telefono(telefono)
        if not lead:
            return False

        nombre_full = f"{lead.get('nombre','')} {lead.get('apellido','')}".strip() or "Cliente"

        sesion_recurrente = {
            "nombre": nombre_full,
            "_lead_recurrente": True,
            "_ultimo_ts": __import__("time").time(),
            "_lead_id": lead.get("id"),
        }
        # Restaurar campos BANT previos si existen
        if lead.get("email"):           sesion_recurrente["email"] = lead["email"]
        if lead.get("tipo_propiedad"):  sesion_recurrente["resp_tipo"] = lead["tipo_propiedad"]
        if lead.get("zona"):            sesion_recurrente["resp_zona"] = lead["zona"]
        if lead.get("operacion"):       sesion_recurrente["operacion_at"] = lead["operacion"]
        if lead.get("presupuesto"):     sesion_recurrente["resp_presupuesto"] = str(lead["presupuesto"])
        if lead.get("score"):           sesion_recurrente["score"] = str(lead["score"]).lower()
        if lead.get("ciudad"):          sesion_recurrente["ciudad_resp"] = lead["ciudad"]
        if lead.get("notas_bot"):       sesion_recurrente["_notas_previas"] = str(lead["notas_bot"])[:500]
        if lead.get("propiedad_interes"): sesion_recurrente["_prop_interes_previa"] = lead["propiedad_interes"]
        if lead.get("estado"):          sesion_recurrente["_estado_previo"] = lead["estado"]
        # Si tiene cita agendada previa
        if lead.get("fecha_cita"):      sesion_recurrente["_fecha_cita_previa"] = str(lead["fecha_cita"])

        SESIONES[telefono] = sesion_recurrente
        print(f"[ROBERT-RESTORE] Lead recurrente {tel[-4:]}*** restaurado desde PostgreSQL: "
              f"{nombre_full} | score={lead.get('score','?')} | tipo={lead.get('tipo_propiedad','?')} | "
              f"zona={lead.get('zona','?')} | estado_previo={lead.get('estado','?')}")
        return True
    except Exception as e:
        print(f"[ROBERT-RESTORE] Error: {e}")
        return False


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
def _transcribir_audio_meta(media_id: str) -> str:
    """Descarga audio de Meta Graph API y transcribe con Whisper (OpenAI Robert)."""
    import tempfile
    if not META_ACCESS_TOKEN or not OPENAI_API_KEY:
        print("[ROBERT-AUDIO] Faltan META_ACCESS_TOKEN o OPENAI_API_KEY")
        return ""
    try:
        # Paso 1: obtener URL del media
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{media_id}",
            headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}"},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"[ROBERT-AUDIO] Error obteniendo URL media: {r.status_code} {r.text[:200]}")
            return ""
        media_url = r.json().get("url", "")
        if not media_url:
            return ""
        # Paso 2: descargar audio
        r2 = requests.get(
            media_url,
            headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}"},
            timeout=30,
        )
        if r2.status_code != 200:
            print(f"[ROBERT-AUDIO] Error descargando audio: {r2.status_code}")
            return ""
        # Paso 3: Whisper
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(r2.content)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                resp = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    data={
                        "model": "whisper-1",
                        "language": "es",
                        # Hint para audios cortos donde el lead suele decir nombre,
                        # objetivo, presupuesto, zona, urgencia.
                        "prompt": (
                            "Conversación inmobiliaria en español rioplatense. "
                            "El usuario puede decir su nombre, presupuesto en USD/ARS, "
                            "tipo (lote, casa, departamento), zona "
                            "(San Ignacio, Apóstoles, Gdor Roca), urgencia."
                        ),
                        "temperature": "0",
                    },
                    files={"file": ("audio.ogg", f, "audio/ogg")},
                    timeout=30,
                )
            if resp.status_code == 200:
                texto = resp.json().get("text", "").strip()
                print(f"[ROBERT-AUDIO] Transcripción: '{texto[:100]}'")
                return texto
            print(f"[ROBERT-AUDIO] Whisper error: {resp.status_code} {resp.text[:200]}")
            return ""
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        print(f"[ROBERT-AUDIO] Excepción: {e}")
        return ""


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
    """Detecta tipo en string corto (match exacto) o dentro de oración larga."""
    if not tipo:
        return ""
    txt = tipo.lower().strip()
    # Match exacto primero
    direct = _TIPO_MAP.get(txt, "")
    if direct:
        return direct
    # Buscar palabras del map dentro del texto (oración larga)
    for kw, val in _TIPO_MAP.items():
        if re.search(rf'\b{re.escape(kw)}\b', txt):
            return val
    return ""


def _normalizar_zona(zona: str) -> str:
    """Detecta zona en string corto (match exacto) o dentro de oración larga."""
    if not zona:
        return ""
    txt = zona.lower().strip()
    direct = _ZONA_MAP.get(txt, "")
    if direct:
        return direct
    # Buscar palabras del map dentro del texto (acepta tildes/no-tildes)
    import unicodedata
    def _norm(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    txt_norm = _norm(txt)
    for kw, val in _ZONA_MAP.items():
        if _norm(kw) in txt_norm:
            return val
    return ""


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
    """Llama a GPT-5-mini (principal con retry) → Gemini fallback (2.0 → 2.5)."""
    # ── OpenAI (principal) con retry ──
    if OPENAI_API_KEY:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        for attempt in range(2):  # 1 intento + 1 retry
            try:
                r = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                    json={"model": "gpt-4.1-mini", "messages": messages, "max_tokens": 1200, "temperature": 0.7},
                    timeout=20,
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                print(f"[ROBERT-LLM] OpenAI error {r.status_code} (attempt {attempt+1}): {r.text[:200]}")
                if r.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    import time as _t; _t.sleep(1.5)
                    continue
                break
            except requests.exceptions.Timeout:
                print(f"[ROBERT-LLM] OpenAI timeout (attempt {attempt+1})")
                if attempt == 0:
                    continue
            except Exception as e:
                print(f"[ROBERT-LLM] OpenAI excepción (attempt {attempt+1}): {e}")
                break

    # ── Gemini (fallback) — probar 2.0 (más estable) → 2.5 ──
    if _gemini_client:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        for model in ("gemini-2.0-flash", "gemini-2.5-flash"):
            try:
                resp = _gemini_client.models.generate_content(model=model, contents=full_prompt)
                return resp.text.strip()
            except Exception as e:
                print(f"[ROBERT-LLM] Gemini {model} error: {str(e)[:200]}")
                continue

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
def _presentar_prop_breve(p: dict, idx: int, total: int) -> str:
    """Presenta UNA propiedad de forma conversacional, sin menú numérico."""
    precio = p.get("Precio", 0)
    moneda = p.get("Moneda", MONEDA)
    precio_str = f"${precio:,.0f} {moneda}" if precio else "a consultar"
    estado = p.get("Disponible", "")
    reservado = "Reservado" in str(estado)
    titulo = p.get("Titulo", "Propiedad")
    tipo  = p.get("Tipo", "")
    zona  = p.get("Zona", "")
    metros_t = p.get("Metros_Terreno", "")
    metros_c = p.get("Metros_Cubiertos", "")
    desc  = p.get("Descripcion", "")

    lineas = []
    if idx == 0:
        lineas.append("Mirá, tengo esta opción que puede interesarte 👇\n")
    else:
        lineas.append("También tengo esta 👇\n")

    lineas.append(f"🏡 *{titulo}*")
    if reservado:
        lineas.append("⏳ _(Reservada — podés anotarte por si se libera)_")
    partes = []
    if zona:  partes.append(f"📍 {zona}")
    if tipo:  partes.append(tipo)
    if metros_t: partes.append(f"{metros_t}m²")
    elif metros_c: partes.append(f"{metros_c}m² cubiertos")
    if partes:
        lineas.append(" · ".join(partes))
    lineas.append(f"💰 *{precio_str}*")
    if desc:
        # Primera oración del desc, máx 80 chars
        primera = desc.split(".")[0].strip()
        if primera and len(primera) > 5:
            lineas.append(f"\n_{primera}._")

    restantes = total - idx - 1
    if restantes > 0:
        lineas.append(f"\n¿Querés que te cuente más sobre esta, o te muestro otra opción?")
    else:
        lineas.append(f"\n¿Qué te parece esta opción?")
    return "\n".join(lineas)


def _lista_titulos(props: list[dict]) -> str:
    """Compatibilidad legacy — usa presentación conversacional en serie."""
    if not props:
        return "No hay propiedades disponibles en este momento."
    return _presentar_prop_breve(props[0], 0, len(props))


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
        f"\n¿Qué te parece? Si te interesa te puedo gestionar una visita con {NOMBRE_ASESOR}. 😊"
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


def _enviar_ficha_sin_imagen(telefono: str, p: dict) -> None:
    """Envía solo el texto de la ficha, sin imagen — para cuando ya se mostró antes."""
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
    """
    System prompt minimalista con arquitectura FSM (Finite State Machine).
    - Secciones fijas: IDENTIDAD, ESTILO, DATOS, ESTADO ACTUAL, TAREA, REGLAS, FORMATO
    - Solo se inyecta el prompt del ESTADO ACTUAL (no los 10 estados a la vez)
    - Contrato binario: texto conversacional XOR directiva ACCION:
    """
    import time as _t

    # ── Extraer datos de sesión ──
    nombre      = sesion.get("nombre", "")
    ciudad      = sesion.get("ciudad_resp", "")
    objetivo    = sesion.get("resp_objetivo", "")
    tipo        = sesion.get("resp_tipo", "")
    presupuesto = sesion.get("resp_presupuesto", "") or sesion.get("presupuesto_at", "")
    urgencia    = sesion.get("resp_urgencia", "")
    autoridad   = sesion.get("autoridad", "")
    forma_pago  = sesion.get("forma_pago", "")
    email       = sesion.get("email", "")
    step        = sesion.get("step", "inicio")
    props       = sesion.get("props", [])
    slots       = sesion.get("slots", [])
    tiene_ref   = bool(referral and (referral.get("source_url") or referral.get("body") or referral.get("headline")))
    ad_info     = (referral.get("headline") or referral.get("body") or referral.get("source_url") or "") if referral else ""
    nombre_corto = nombre.split()[0] if nombre else ""

    # ── Historial (últimos 8 turnos) ──
    historial = HISTORIAL.get(re.sub(r'\D', '', telefono), [])
    hist_txt = "\n".join(historial[-8:]) if historial else "(primer mensaje)"
    bot_ya_saludo = any(("] bot:" in (h.lower() if isinstance(h, str) else "")) for h in historial[-8:])

    # ── DATOS YA CAPTURADOS (bloque inyectado como contexto) ──
    datos_lines = []
    if nombre:       datos_lines.append(f"- nombre: {nombre}")
    if ciudad:       datos_lines.append(f"- ciudad: {ciudad}")
    if objetivo:     datos_lines.append(f"- objetivo: {objetivo}")
    if tipo:         datos_lines.append(f"- tipo_propiedad: {tipo}")
    if presupuesto:  datos_lines.append(f"- presupuesto: {presupuesto}")
    if forma_pago:   datos_lines.append(f"- forma_pago: {forma_pago}")
    if autoridad:    datos_lines.append(f"- autoridad: {autoridad}")
    if urgencia:     datos_lines.append(f"- urgencia: {urgencia}")
    datos_txt = "\n".join(datos_lines) if datos_lines else "(ninguno todavía)"

    # ── SIGUIENTE PREGUNTA DETERMINISTA (FSM) ──
    # Orden fijo BANT. Python decide qué falta. El LLM solo verbaliza UNA.
    orden_bant = [
        ("nombre",      nombre,      "¿Con quién tengo el gusto de conversar?"),
        ("ciudad",      ciudad,      f"¿De qué ciudad nos escribís? (nos ayuda a medir distancia a {CIUDAD})"),
        ("objetivo",    objetivo,    "¿La propiedad sería para vivir o más como inversión?"),
        ("tipo",        tipo,        "¿Qué tipo de propiedad tenés en mente? (casa / departamento / terreno)"),
        ("presupuesto", presupuesto, f"¿Qué presupuesto aproximado manejás? (en {MONEDA})"),
        ("forma_pago",  forma_pago,  "¿Sería al contado o con crédito?"),
        ("autoridad",   autoridad,   "¿La decisión la tomás vos solo/a o con pareja, socios o familia?"),
        ("urgencia",    urgencia,    "¿Para cuándo querés concretar? (ahora / 1-3 meses / explorando)"),
    ]
    siguiente_campo = None
    siguiente_ejemplo = ""
    for campo, valor, ejemplo in orden_bant:
        if not valor:
            siguiente_campo = campo
            siguiente_ejemplo = ejemplo
            break
    bant_completo = siguiente_campo is None

    # ── TAREA DEL ESTADO ACTUAL (inyección dinámica — solo UNO) ──
    # Estados post-BANT (ficha, agendar, ofrecer_cita, confirmar_cita) NO pasan por LLM:
    # los handlers Python los manejan. El LLM solo interviene en estados BANT.
    if step == "recuperacion":
        tarea = (
            f"El lead volvió después de un rato. Saludalo por nombre ({nombre_corto or 'amigo/a'}) "
            f"y preguntá si quiere retomar donde quedó o arrancar de nuevo. UNA sola pregunta."
        )
    elif bant_completo:
        tarea = (
            "BANT COMPLETO. Ya tenés todos los datos del lead. "
            "NO hagas más preguntas. Emití SOLO la directiva `ACCION: agendar` "
            "sin NINGÚN texto conversacional adicional. El sistema se encarga de ofrecer los slots."
        )
    elif tiene_ref and step == "inicio":
        tarea = f"""PRIMER CONTACTO desde anuncio: '{ad_info}'.

ACCIÓN OBLIGATORIA — saludo cálido en 2-3 líneas:
1. Saludá {'por nombre (' + nombre_corto + ')' if nombre_corto else 'con calidez'}.
2. Confirmá que la propiedad del anuncio sigue disponible + 1 dato clave (precio/ubicación).
3. Mencioná brevemente que sos el asistente de *{NOMBRE_EMPRESA}* en {CIUDAD}.
4. Hacé UNA sola pregunta abierta de calificación: **{siguiente_ejemplo}**

Ejemplo de tono (NO copiar literal, adaptá):
"¡Hola{', ' + nombre_corto if nombre_corto else ''}! 👋 Te confirmo que el {ad_info[:50]} sigue disponible.
Soy el asistente de *{NOMBRE_EMPRESA}*, desarrolladora en {CIUDAD}.
{siguiente_ejemplo}"
"""
    elif step == "inicio":
        zonas_breve = " · ".join(ZONAS_LIST[:3]) if ZONAS_LIST else "distintas zonas premium"
        tarea = f"""PRIMER CONTACTO genérico (sin anuncio previo).

ACCIÓN OBLIGATORIA — saludo cálido de bienvenida en 3-4 líneas:
1. "¡Hola! 👋 Bienvenido/a a *{NOMBRE_EMPRESA}*, gracias por escribirnos."
2. Presentarte: "Somos una desarrolladora inmobiliaria en {CIUDAD} con proyectos en {zonas_breve}."
3. Línea de cercanía: "Estoy acá para ayudarte a encontrar lo que estás buscando 🏡"
4. UNA sola pregunta: **{siguiente_ejemplo}**

Ejemplo de tono (adaptá, no copies literal):
"¡Hola! 👋 Bienvenido/a a *{NOMBRE_EMPRESA}*, gracias por escribirnos.

Somos una desarrolladora inmobiliaria en {CIUDAD} con proyectos en {zonas_breve}.
Estoy acá para ayudarte a encontrar lo que estás buscando 🏡

{siguiente_ejemplo}"
"""
    else:
        tarea = (
            f"El lead ya está en conversación. Tu única tarea este turno es: "
            f"**preguntar por `{siguiente_campo}`** (si no respondió ya) "
            f"con tono empático y una razón corta del porqué. Ejemplo: '{siguiente_ejemplo}'. "
            f"Si el lead te pregunta algo, respondé en 1 línea y DESPUÉS preguntás por `{siguiente_campo}`."
        )

    # ── Contexto de propiedades/slots (solo si aplica) ──
    contexto_extra = ""
    if props and step in ("explorando", "ficha"):
        contexto_extra += "\n\nPropiedades ya mostradas al lead:\n"
        for i, p in enumerate(props[:3], 1):
            titulo = p.get("Titulo") or p.get("Nombre", "Propiedad")
            contexto_extra += f"  {i}. {titulo}\n"
    if slots and step == "agendar_slots":
        contexto_extra += f"\n\nSlots Cal.com YA enviados al lead — no los vuelvas a listar.\n"

    # ── Bloque saludo — evitar repetir saludo ──
    bloque_saludo = ""
    if bot_ya_saludo and step != "inicio":
        bloque_saludo = "⚠️ Ya saludaste al lead antes. NO vuelvas a decir 'hola' ni a presentarte."

    # ── SYSTEM PROMPT FINAL (6 secciones fijas) ──
    system = f"""# IDENTIDAD
Sos el asistente virtual de *{NOMBRE_EMPRESA}*, una desarrolladora inmobiliaria en {CIUDAD}.
El asesor humano se llama *{NOMBRE_ASESOR}*.
Tu rol: filtrar leads con metodología BANT en menos de 2 minutos y llevarlos a agendar cita.

# ESTILO
- Tono cálido, empático, rioplatense (vos/ché). Como un consultor amigo, no un formulario.
- Mensajes cortos: máximo 2-3 líneas. UNA sola pregunta por turno.
- Después de cada respuesta del lead, acusá recibo brevemente antes de la siguiente pregunta.
  Ej: "Perfecto, inversión entonces 💪" → y recién ahí preguntás lo siguiente.
- Emojis con moderación (máx 1 por mensaje). *Negrita* solo para datos clave.
- NUNCA uses frases genéricas tipo "¿en qué puedo ayudarte?".

# DATOS YA CAPTURADOS
{datos_txt}

⚠️ Cualquier dato que figure acá ARRIBA ya fue respondido por el lead. NUNCA vuelvas a preguntarlo.

# ESTADO ACTUAL
step: {step}
siguiente_campo_pendiente: {siguiente_campo if siguiente_campo else "(BANT completo)"}
{bloque_saludo}
{contexto_extra}

# TU TAREA ESTE TURNO
{tarea}

# REGLAS IRROMPIBLES
1. SOLO podés hacer UNA pregunta por turno, y esa pregunta DEBE ser sobre `{siguiente_campo or "(ninguna — BANT completo)"}`.
2. NUNCA preguntes algo que ya figura en DATOS YA CAPTURADOS.
3. NUNCA inventes horarios de cita. Los slots los provee Cal.com — el sistema los envía aparte.
4. NUNCA muestres propiedades si el lead no las pidió explícitamente (palabras como "qué tenés", "mostrame", "opciones").
5. Si el lead pide ver propiedades → emitir `ACCION: mostrar_props` (sin listar tú).
6. Si el lead dice "sí quiero agendar / dale / perfecto" después de BANT → emitir `ACCION: agendar`.
7. Si el lead pide hablar con humano → emitir `ACCION: ir_asesor`.
8. Si el lead es evasivo 2+ turnos → emitir `ACCION: cerrar_curioso`.

# HISTORIAL DE LA CONVERSACIÓN
{hist_txt}

# FORMATO DE SALIDA (ESTRICTO)
Tu respuesta debe ser UNA de estas dos cosas, nunca ambas:

(A) Texto conversacional para el lead (2-3 líneas máx). En ese caso, al final agregás las directivas
    de extracción en líneas sueltas (el cliente NO las ve, las filtra el sistema):

    Texto conversacional acá.
    NOMBRE: Juan
    CIUDAD: Posadas
    OBJETIVO: invertir

(B) Solo una directiva ACCION: (sin texto conversacional), cuando corresponde derivar al
    handler determinista del sistema:

    ACCION: agendar

🚫 PROHIBIDO:
- Mezclar headers tipo "EXTRACCIÓN:", "ACCIONES:", "===" — van solo las líneas KEY: valor
- Emitir ACCION: junto con texto conversacional. Es una o la otra.
- Inventar horarios, fechas concretas, precios no confirmados, o propiedades no mostradas.

KEYS válidas:
NOMBRE, EMAIL, CIUDAD, OBJETIVO (vivir/invertir/alquilar), TIPO (casa/departamento/terreno/lote/local/oficina),
PRESUPUESTO, FORMA_PAGO (contado/credito_aprobado/credito_sin_aprobar),
AUTORIDAD (solo/pareja/socios/familia), URGENCIA (inmediata/1_3_meses/3_6_meses/explorando),
SCORE (caliente/tibio/frio), ACCION (continuar/mostrar_props/agendar/ir_asesor/cerrar_curioso)
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

    # ── Detectar lead RECURRENTE en tabla `leads` PostgreSQL ─────────────────
    # IMPORTANTE: el webhook puede haber creado una sesión "vacía" con solo el
    # nombre del Meta profile. En ese caso TAMBIÉN buscamos en leads, porque
    # la sesión efectiva está vacía pero el lead ya existe.
    sesion_actual = SESIONES.get(telefono, {})
    sesion_es_minima = (
        not sesion_actual or
        # Sesión solo con nombre (precargado del webhook) sin datos BANT
        (set(sesion_actual.keys()) - {"nombre", "_ultimo_ts", "origen_lead"}) == set()
    )
    no_es_recurrente_aun = not sesion_actual.get("_lead_recurrente", False)
    if sesion_es_minima and no_es_recurrente_aun:
        # Borrar sesión mínima si existe, para que _restaurar pueda crear la full
        if telefono in SESIONES and sesion_es_minima:
            super(_SessionStore, SESIONES).__delitem__(telefono)
        _restaurar_lead_desde_db(telefono)

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

    # ── Pedido natural de hablar con humano (anti-bot frustration) ────────
    _KEYWORDS_HUMANO = [
        "hablar con un asesor", "hablar con asesor", "hablar con humano",
        "hablar con una persona", "hablar con alguien", "atiende alguien",
        "atiende una persona", "me pasa con", "me deriva", "quiero un humano",
        "necesito hablar con", "comunicarme con un asesor", "asesor humano",
        "persona real", "pasame con", "que me llame", "que me llamen",
    ]
    if any(kw in texto_lower for kw in _KEYWORDS_HUMANO):
        _enviar_texto(telefono,
            f"Por supuesto. Te paso con *{NOMBRE_ASESOR}* ahora mismo. 🙋‍♂️\n"
            f"En unos minutos te va a contactar.")
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

    # ── Step explorando → navegación conversacional (UNA prop a la vez) ─────
    # DEBE estar ANTES del LLM para no depender de que el LLM responda.
    if step in ("explorando", "lista"):
        props = sesion.get("props", [])
        prop_idx = sesion.get("prop_idx", 0)

        _KEYWORDS_SIGUIENTE = [
            "otra", "siguiente", "mas", "más", "no me interesa", "no es",
            "no se adapta", "otra opción", "otra opcion", "ver otra",
            "siguiente opción", "siguiente opcion", "diferente", "no gracias",
            "no me convence", "que mas", "qué más", "hay mas", "hay más",
            "no me adapta", "algo mas", "algo más",
        ]
        _KEYWORDS_INTERES = [
            "me interesa", "quiero info", "más info", "mas info", "info",
            "detalle", "cuéntame", "cuentame", "saber más", "saber mas",
            "esta me gusta", "me gusta", "interesante", "quiero verla",
            "puedo verla", "visita", "agendar", "cuando puedo", "cuanto sale",
            "cuánto sale", "precio", "cuánto cuesta", "cuanto cuesta",
        ]

        _pide_siguiente = any(kw in texto_lower for kw in _KEYWORDS_SIGUIENTE)
        _pide_detalle   = any(kw in texto_lower for kw in _KEYWORDS_INTERES)

        if _pide_siguiente:
            next_idx = prop_idx + 1
            if next_idx < len(props):
                SESIONES[telefono] = {**sesion, "step": "explorando",
                                      "prop_idx": next_idx, "_ultimo_ts": ahora_ts}
                _enviar_texto(telefono, _presentar_prop_breve(props[next_idx], next_idx, len(props)))
                img_field = props[next_idx].get("Imagen_URL", "")
                img = (img_field[0].get("url","") if isinstance(img_field, list) and img_field
                       else img_field if isinstance(img_field, str) else "")
                if img:
                    _enviar_imagen(telefono, img, caption=props[next_idx].get("Titulo",""))
            else:
                _enviar_texto(telefono,
                    f"Ya te mostré todas las opciones disponibles ahora. "
                    f"Si querés, {NOMBRE_ASESOR} tiene proyectos que no están publicados todavía. "
                    f"¿Te contactamos?")
            return

        if _pide_detalle:
            prop = props[prop_idx] if prop_idx < len(props) else (props[-1] if props else None)
            if prop:
                # Si la prop ya fue mostrada con breve+imagen, no repetir la imagen — ir a ficha solo texto
                SESIONES[telefono] = {**sesion, "step": "ficha",
                                      "ficha_actual": prop_idx, "_ultimo_ts": ahora_ts}
                _enviar_ficha_sin_imagen(telefono, prop)
                prop_nombre = f"{prop.get('Tipo','')} {prop.get('Zona','')} - {prop.get('Titulo', prop.get('Nombre',''))}".strip()
                def _guardar_interes_exp():
                    if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
                        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
                        r = requests.get(url, headers=AT_HEADERS,
                            params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
                        recs = r.json().get("records", []) if r.status_code == 200 else []
                        if recs:
                            requests.patch(f"{url}/{recs[0]['id']}", headers=AT_HEADERS,
                                json={"fields": {"Propiedad_Interes": prop_nombre[:200]}}, timeout=8)
                threading.Thread(target=_guardar_interes_exp, daemon=True).start()
            return

        # Respuesta ambigua en explorando → LLM responde (pasa al bloque de abajo)
        # No retornamos, dejamos fluir al LLM

    # ── ANTI-FRICTION: pedido explícito de opciones → saltear BANT ─────────
    # Si el cliente pide ver opciones/propiedades explícitamente, mostramos
    # inmediatamente sin esperar presupuesto (ancla posterior).
    _KEYWORDS_PEDIR_OPCIONES = [
        "que opciones", "qué opciones", "que tienen", "qué tienen",
        "mostrame", "muéstrame", "muéstrame", "muestrame",
        "quiero ver", "quisiera ver", "mandame", "mandame opciones",
        "que hay disponible", "qué hay disponible", "que propiedades",
        "qué propiedades", "opciones para", "ver opciones", "ver propiedades",
        "quiero opciones", "tenés opciones", "tienen opciones",
    ]
    _pide_opciones_directo = any(kw in texto_lower for kw in _KEYWORDS_PEDIR_OPCIONES)

    if _pide_opciones_directo and step not in ("explorando", "lista", "ficha", "agendar_slots", "confirmar_cita"):
        tipo_busq   = sesion.get("resp_tipo", "") or sesion.get("_tipo_ref", "")
        zona_busq   = sesion.get("resp_zona", "")
        operac_busq = sesion.get("operacion_at", "venta")
        presp_busq  = sesion.get("presupuesto_at", "")
        props_d = _at_buscar_propiedades(tipo=tipo_busq, operacion=operac_busq,
                                          zona=zona_busq, presupuesto=presp_busq)
        if props_d:
            sesion_nueva = {**sesion, "step": "explorando",
                            "props": props_d, "prop_idx": 0,
                            "tipo": tipo_busq, "zona": zona_busq,
                            "operacion": operac_busq, "_ultimo_ts": ahora_ts}
            SESIONES[telefono] = sesion_nueva
            _enviar_texto(telefono, _presentar_prop_breve(props_d[0], 0, len(props_d)))
            img_field = props_d[0].get("Imagen_URL", "")
            img = (img_field[0].get("url","") if isinstance(img_field, list) and img_field
                   else img_field if isinstance(img_field, str) else "")
            if img:
                _enviar_imagen(telefono, img, caption=props_d[0].get("Titulo",""))
        else:
            _enviar_texto(telefono,
                f"En este momento no tenemos propiedades publicadas que coincidan. "
                f"Si querés, {NOMBRE_ASESOR} puede mostrarte opciones exclusivas — ¿te contactamos?")
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
    # Patrón para detectar leak de keys internas del prompt (ej: "CIUDAD ya lo tengo: X")
    _LEAK_KEYS = ("NOMBRE", "CIUDAD", "OBJETIVO", "TIPO", "ZONA", "PRESUPUESTO",
                  "URGENCIA", "AUTORIDAD", "FORMA_PAGO", "ACCION", "SCORE",
                  "MOTIVO", "SUBNICHE", "EMAIL")
    for linea in lineas:
        # Headers tipo "EXTRACCIÓN DE DATOS:" o "===" → ocultar
        if _es_header_interno(linea):
            continue
        # Líneas que empiezan con una KEY interna (leak del prompt) → ocultar
        linea_strip = linea.strip()
        linea_upper = linea_strip.upper()
        if any(linea_upper.startswith(k) for k in _LEAK_KEYS):
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
                # Limpiar caracteres especiales (@, números, símbolos) del nombre
                nombre_limpio = re.sub(r'[^A-Za-záéíóúüñÁÉÍÓÚÜÑ\s]', '', value).strip()
                acciones["nombre"] = nombre_limpio.title() if nombre_limpio else value.title()
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

    # Inferir nombre desde frases tipo "soy X / me llamo X / mi nombre es X"
    # Solo si el bot le acaba de preguntar el nombre (último msg del bot tiene
    # frase "con quién tengo el gusto" o equivalente) Y todavía no hay nombre.
    if not sesion_nueva.get("nombre"):
        m_nombre = re.match(
            r'^(?:soy|me\s+llamo|mi\s+nombre\s+es|llamame|llamame\s+)\s+([A-ZÁÉÍÓÚÑa-záéíóúñ]{2,20}(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]{2,20})?)',
            texto.strip(), re.IGNORECASE
        )
        if m_nombre:
            nombre_det = m_nombre.group(1).strip().title()
            sesion_nueva["nombre"] = nombre_det

        # Backup 2: nombre solo (1-2 palabras capitalizadas) cuando el bot preguntó el nombre
        # FIX: HISTORIAL guarda formato "[HH:MM] Bot: ..." — startswith('Bot:') no matcheaba
        if not sesion_nueva.get("nombre"):
            ultimo_msg_bot = ""
            _hist_local = HISTORIAL.get(re.sub(r'\D', '', telefono), [])
            for h in reversed(_hist_local):
                h_lower = h.lower() if isinstance(h, str) else ""
                if "] bot:" in h_lower or h_lower.startswith("bot:"):
                    ultimo_msg_bot = h_lower
                    break
            if any(p in ultimo_msg_bot for p in ["con quién", "con quien", "tu nombre", "cómo te llamás", "como te llamas", "el gusto"]):
                m_nombre_solo = re.match(
                    r'^([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,19}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,19})?)[\s\.,!?]*$',
                    texto.strip()
                )
                if m_nombre_solo:
                    sesion_nueva["nombre"] = m_nombre_solo.group(1).strip().title()

    # Sanitizar nombre inválido capturado por cualquier vía (ej: "@Rn@Ldo" → "Rnldo" sería raro)
    # Si el nombre actual tiene vocales muy escasas o longitud <3, descartarlo y volver a pedir
    if sesion_nueva.get("nombre"):
        n_val = sesion_nueva["nombre"]
        vocales = sum(1 for c in n_val.lower() if c in "aeiouáéíóú")
        if len(n_val) < 3 or vocales == 0:
            # Nombre inválido (probablemente del perfil de WhatsApp con símbolos)
            # Lo descartamos para que el bot vuelva a preguntarlo
            sesion_nueva.pop("nombre", None)

    # Backup ciudad: si el bot preguntó ciudad y el LLM no emitió CIUDAD:,
    # capturar el texto completo del mensaje como ciudad (respuestas simples tipo "San Ignacio")
    # FIX: HISTORIAL guarda formato "[HH:MM] Bot: ..." — startswith('Bot:') no matcheaba
    if not sesion_nueva.get("ciudad_resp"):
        _hist_local = HISTORIAL.get(re.sub(r'\D', '', telefono), [])
        ultimo_msg_bot = ""
        for h in reversed(_hist_local):
            h_lower = h.lower() if isinstance(h, str) else ""
            if "] bot:" in h_lower or h_lower.startswith("bot:"):
                ultimo_msg_bot = h_lower
                break
        _FRASES_PREGUNTA_CIUDAD = [
            "qué ciudad", "que ciudad", "desde dónde", "desde donde",
            "ciudad nos escribís", "ciudad sos", "de dónde sos", "de donde sos",
            "de dónde escribís", "de donde escribis", "dónde vivís", "donde vivis",
            "en qué ciudad", "en que ciudad",
        ]
        if any(p in ultimo_msg_bot for p in _FRASES_PREGUNTA_CIUDAD):
            ciudad_candidata = texto.strip().title()
            if 2 <= len(ciudad_candidata) <= 50 and not any(c.isdigit() for c in ciudad_candidata):
                sesion_nueva["ciudad_resp"] = ciudad_candidata

    # ── Backups deterministas por palabras clave en el texto del lead ─────
    # Si el LLM no emitió la directiva, Python captura la respuesta por regex simple
    texto_low = texto.lower().strip()

    # OBJETIVO: "vivir", "invertir", "alquilar"
    if not sesion_nueva.get("resp_objetivo"):
        if any(kw in texto_low for kw in ["invertir", "inversión", "inversion"]):
            sesion_nueva["resp_objetivo"] = "invertir"
            sesion_nueva["operacion_at"] = "venta"
        elif any(kw in texto_low for kw in ["vivir", "para mí", "para mi", "para la familia", "para mudarme"]):
            sesion_nueva["resp_objetivo"] = "vivir"
            sesion_nueva["operacion_at"] = "venta"
        elif "alquilar" in texto_low or "renta" in texto_low:
            sesion_nueva["resp_objetivo"] = "alquilar"
            sesion_nueva["operacion_at"] = "alquiler"

    # TIPO: casa / departamento / terreno / lote / local / oficina
    if not sesion_nueva.get("resp_tipo"):
        _tipos = {
            "casa": ["casa"],
            "departamento": ["departamento", "depto", "depa", "apartamento"],
            "terreno": ["terreno", "lote"],
            "local": ["local", "local comercial"],
            "oficina": ["oficina"],
        }
        for tipo_key, kws in _tipos.items():
            if any(f" {kw} " in f" {texto_low} " or texto_low == kw for kw in kws):
                sesion_nueva["resp_tipo"] = tipo_key
                break

    # PRESUPUESTO: números + unidad
    if not sesion_nueva.get("resp_presupuesto"):
        m_pres = re.search(r'\b(\d{1,4}(?:[.,]\d{3})?)\s*(k|mil|000|usd|dólares|dolares|\$|ars|pesos)\b', texto_low)
        if m_pres:
            sesion_nueva["resp_presupuesto"] = m_pres.group(0).upper().strip()

    # URGENCIA: palabras clave temporales
    if not sesion_nueva.get("resp_urgencia"):
        if any(kw in texto_low for kw in ["ahora", "ya", "inmediato", "urgente", "este mes", "esta semana"]):
            sesion_nueva["resp_urgencia"] = "inmediata"
        elif any(kw in texto_low for kw in ["1 mes", "2 meses", "3 meses", "próximo mes", "proximo mes", "corto plazo"]):
            sesion_nueva["resp_urgencia"] = "1_3_meses"
        elif any(kw in texto_low for kw in ["6 meses", "medio año", "medio ano", "mediano plazo"]):
            sesion_nueva["resp_urgencia"] = "3_6_meses"
        elif any(kw in texto_low for kw in ["explorando", "viendo", "mirando", "sin apuro", "sin prisa"]):
            sesion_nueva["resp_urgencia"] = "explorando"

    # AUTORIDAD: quién decide
    if not sesion_nueva.get("autoridad"):
        if any(kw in texto_low for kw in ["yo solo", "yo sola", "yo nomás", "yo nomas", "soy yo", "decido yo"]):
            sesion_nueva["autoridad"] = "solo"
        elif any(kw in texto_low for kw in ["mi pareja", "con mi esposa", "con mi esposo", "con mi marido", "con mi mujer"]):
            sesion_nueva["autoridad"] = "pareja"
        elif any(kw in texto_low for kw in ["mi socio", "mis socios", "con socios"]):
            sesion_nueva["autoridad"] = "socios"
        elif any(kw in texto_low for kw in ["familia", "mis padres", "mis hijos"]):
            sesion_nueva["autoridad"] = "familia"

    # FORMA DE PAGO
    if not sesion_nueva.get("forma_pago"):
        if "contado" in texto_low:
            sesion_nueva["forma_pago"] = "contado"
        elif any(kw in texto_low for kw in ["crédito aprobado", "credito aprobado", "con aprobación", "pre-aprobado", "preaprobado"]):
            sesion_nueva["forma_pago"] = "credito_aprobado"
        elif any(kw in texto_low for kw in ["crédito", "credito", "hipotecario", "préstamo", "prestamo"]):
            sesion_nueva["forma_pago"] = "credito_sin_aprobar"

    # NOMBRE: si quedó igual a la ciudad, descartarlo (bug detectado: "nombre=San Ignacio")
    if sesion_nueva.get("nombre") and sesion_nueva.get("ciudad_resp"):
        if sesion_nueva["nombre"].lower() == sesion_nueva["ciudad_resp"].lower():
            sesion_nueva.pop("nombre", None)

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

    if accion == "mostrar_props":
        # LLM decidió mostrar propiedades (anti-friction o calificación suficiente)
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
        tipo_mp   = sesion_nueva.get("resp_tipo", "") or sesion_nueva.get("_tipo_ref", "")
        zona_mp   = sesion_nueva.get("resp_zona", "")
        oper_mp   = sesion_nueva.get("operacion_at", "venta")
        presp_mp  = sesion_nueva.get("presupuesto_at", "")
        props_mp  = _at_buscar_propiedades(tipo=tipo_mp, operacion=oper_mp,
                                            zona=zona_mp, presupuesto=presp_mp)
        if props_mp:
            SESIONES[telefono] = {**sesion_nueva, "step": "explorando",
                                   "props": props_mp, "prop_idx": 0,
                                   "tipo": tipo_mp, "zona": zona_mp, "operacion": oper_mp}
            _enviar_texto(telefono, _presentar_prop_breve(props_mp[0], 0, len(props_mp)))
            img_field = props_mp[0].get("Imagen_URL", "")
            img = (img_field[0].get("url","") if isinstance(img_field, list) and img_field
                   else img_field if isinstance(img_field, str) else "")
            if img:
                _enviar_imagen(telefono, img, caption=props_mp[0].get("Titulo",""))
        else:
            _enviar_texto(telefono,
                f"Por ahora no hay propiedades publicadas con esas características. "
                f"Escribí *#* para hablar con *{NOMBRE_ASESOR}* directamente.")
        return

    if accion == "ir_asesor":
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
        _ir_asesor(telefono, sesion_nueva)
        return

    if accion == "cerrar_curioso":
        # Lead no interesado / evasivo — cerramos sin escalar al asesor.
        # Se registra como frío en Airtable para métrica, pero no notifica al asesor.
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
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

    if (accion == "calificar" or datos_completos) and not sesion_nueva.get("_ya_calificado"):
        # NO enviar mensaje_final del LLM acá — el handler de calificado/ofrecer_cita
        # envía los slots reales de Cal.com. Si mandamos el LLM, duplicamos/contradecimos
        # (el LLM suele inventar horarios como "16:00 o 18:00" que no existen).

        # Marcar como calificado ANTES de disparar threads, para evitar re-ejecución
        sesion_nueva["_ya_calificado"] = True

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

        # Caliente/tibio → mostrar propiedades solo si ya se preguntó Authority (quién decide)
        # Si no tenemos autoridad aún, el LLM debe preguntar antes de mostrar opciones
        autoridad = sesion_nueva.get("autoridad", "")
        if not autoridad:
            SESIONES[telefono] = {**sesion_nueva, "step": "calificado"}
            if mensaje_final:
                _enviar_texto(telefono, mensaje_final)
            return

        # Caliente/tibio → objetivo es conseguir la CITA, no mostrar catálogo
        # Las propiedades solo se muestran si el lead las pide explícitamente
        # Ofrecer cita directamente
        if _cal_disponible():
            slots = _cal_obtener_slots()
            if slots:
                SESIONES[telefono] = {**sesion_nueva, "step": "agendar_slots", "slots": slots}
                _enviar_texto(telefono,
                    f"Perfecto, {nombre_corto or nombre}. Con lo que me contaste, "
                    f"*{NOMBRE_ASESOR}* puede mostrarte opciones que encajan justo con lo que buscás. 🏡\n\n"
                    f"¿Cuándo te viene bien una charla rápida? Estos son los horarios disponibles:\n\n"
                    f"{_formatear_slots(slots)}\n\nElegí un número o escribí *0* para que te contactemos.")
                return
        # Sin Cal.com → derivar al asesor
        SESIONES[telefono] = {**sesion_nueva, "step": "ofrecer_cita"}
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
        return

    # ── Step ofrecer_cita → si confirma o pregunta por horarios, mostrar slots ─
    if step == "ofrecer_cita":
        _KEYWORDS_CONFIRMA = ["si", "sí", "dale", "bueno", "ok", "perfecto", "claro", "quiero", "adelante", "genial", "va"]
        _KEYWORDS_HORARIO = ["hora", "horario", "cuando", "cuándo", "disponib", "agenda", "visita", "cita", "dia", "día", "turno"]
        confirma = any(kw == texto_lower.strip().rstrip(".,!?") or texto_lower.startswith(kw) for kw in _KEYWORDS_CONFIRMA)
        pregunta_horario = any(kw in texto_lower for kw in _KEYWORDS_HORARIO)
        if confirma or pregunta_horario:
            if _cal_disponible():
                slots = _cal_obtener_slots()
                if slots:
                    SESIONES[telefono] = {**sesion_nueva, "step": "agendar_slots", "slots": slots}
                    _enviar_texto(telefono,
                        f"Perfecto. Estos son los horarios disponibles con *{NOMBRE_ASESOR}*:\n\n"
                        f"{_formatear_slots(slots)}\n\nElegí un número.")
                    return
            _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
                nombre=nombre_corto or nombre, asesor=NOMBRE_ASESOR, empresa=NOMBRE_EMPRESA))
            SESIONES.pop(telefono, None)
            return
        # Otra respuesta → LLM maneja, pero SIN inventar horarios
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
        return

    if step == "ficha":
        # Si el lead expresa interés → ir a ofrecer_cita directamente (no re-enviar ficha)
        _KEYWORDS_INTERES_FICHA = [
            "me interesa", "me gusta", "quiero verla", "quiero visitarla",
            "agendar", "visita", "cuando puedo", "cómo la veo", "como la veo",
            "me interesa ese", "quiero ese", "ese me gusta", "perfecto",
        ]
        if any(kw in texto_lower for kw in _KEYWORDS_INTERES_FICHA):
            SESIONES[telefono] = {**sesion_nueva, "step": "ofrecer_cita", "_ultimo_ts": ahora_ts}
            if mensaje_final:
                _enviar_texto(telefono, mensaje_final)
            return
        # Cualquier otra respuesta en ficha → LLM decide
        if mensaje_final:
            _enviar_texto(telefono, mensaje_final)
        return

    # ── Respuesta LLM estándar ─────────────────────────────────────────────
    if mensaje_final:
        _enviar_texto(telefono, mensaje_final)

    # Actualizar step si el LLM extrajo datos suficientes para avanzar
    # Inferencia de presupuesto: requiere NÚMERO + (k|mil|usd|ars|pesos|$)
    # No matchear "precio"/"cuánto" solos (eso es PREGUNTA del cliente, no su presupuesto)
    if not sesion_nueva.get("resp_presupuesto"):
        m_pres = re.search(r'\b(\d{1,4})\s*(k|mil|000|usd|ars|pesos|dolares|\$)', texto_lower)
        if m_pres:
            sesion_nueva["resp_presupuesto"] = m_pres.group(0).upper().strip()
            num = int(m_pres.group(1))
            unidad = m_pres.group(2)
            if unidad in ("mil", "000"):
                num_real = num * 1000
            elif unidad == "k":
                num_real = num * 1000
            else:
                num_real = num
            if num_real < 50000:
                sesion_nueva["presupuesto_at"] = "hasta_50k"
            elif num_real < 100000:
                sesion_nueva["presupuesto_at"] = "50k_100k"
            elif num_real < 200000:
                sesion_nueva["presupuesto_at"] = "100k_200k"
            else:
                sesion_nueva["presupuesto_at"] = "mas_200k"
            SESIONES[telefono] = sesion_nueva

    if not sesion_nueva.get("resp_urgencia") and any(
        kw in texto_lower for kw in ["ahora mismo", "urgente", "ya tengo", "este mes", "esta semana", "explorando", "tranquilo"]
    ):
        sesion_nueva["resp_urgencia"] = texto[:80]
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
                elif msg_type == "audio":
                    media_id = msg.get("audio", {}).get("id", "")
                    if media_id:
                        texto = _transcribir_audio_meta(media_id)
                        if not texto:
                            tel_tmp = re.sub(r'\D', '', msg.get("from", ""))
                            if tel_tmp:
                                _enviar_texto(tel_tmp,
                                    "No pude escuchar bien el audio 😔. ¿Me lo escribís o lo grabás de nuevo?")
                            return {"status": "ignored", "reason": "audio-no-transcrito"}
                elif msg_type == "image":
                    texto = msg.get("image", {}).get("caption", "") or "[imagen recibida]"

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
            nombre_limpio = re.sub(r'[^A-Za-záéíóúüñÁÉÍÓÚÜÑ\s]', '', nombre_meta).strip()
            if nombre_limpio and len(nombre_limpio) >= 2:
                sesion_pre["nombre"] = nombre_limpio.title()
                SESIONES[tel_clean] = sesion_pre
                print(f"[WEBHOOK] Nombre precargado desde Meta: {nombre_meta} → {nombre_limpio} → {tel_clean}")
            else:
                print(f"[WEBHOOK] Nombre Meta descartado por caracteres inválidos: {nombre_meta}")

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
            nombre_ads_limpio = re.sub(r'[^A-Za-záéíóúüñÁÉÍÓÚÜÑ\s]', '', nombre_ads).strip()
            if nombre_ads_limpio and len(nombre_ads_limpio) >= 2:
                sesion_pre["nombre"] = nombre_ads_limpio.title()
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


@router.get("/admin/ver-sesion/{telefono}")
def ver_sesion_bot(telefono: str):
    """Devuelve el estado actual de la sesión en RAM (útil para testing)."""
    tel = re.sub(r'\D', '', telefono)
    sesion = SESIONES.get(tel, {})
    historial = HISTORIAL.get(tel, [])
    return {
        "telefono": tel,
        "sesion": sesion,
        "historial_ultimos_10": historial[-10:] if historial else [],
        "en_memoria": tel in SESIONES,
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
