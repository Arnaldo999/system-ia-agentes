"""
Worker — Mica / System IA — Inmobiliaria Demo (clonado de Robert)
==================================================================
Bot conversacional inmobiliario clonado 1:1 del worker productivo de Robert,
adaptado para Mica:
  - DB: Airtable (base Mica `appA8QxIhBYYAHw0F`) en vez de PostgreSQL
  - Provider WhatsApp: Evolution API default, Meta via Tech Provider Robert
    si WHATSAPP_PROVIDER=meta (modulo workers.shared.wa_provider)
  - LLM: GPT-4.1-mini con MICA_OPENAI_API_KEY (fallback OPENAI_API_KEY)
  - Sub-nicho: hardcoded "desarrollador_inmobiliario" (como Robert)
  - Nurturing: solo in-window 24hs (sin templates — Mica sin prioridad)

Dos routers expuestos (misma logica, distinto provider):
  /clientes/system_ia/demos/inmobiliaria/whatsapp      → webhook Evolution (Mica productivo, legacy)
  /clientes/system_ia/mica-demo-inmo/whatsapp          → webhook Meta (via Tech Provider Robert)

Variables de entorno:
  MICA_OPENAI_API_KEY            API key OpenAI Mica (fallback OPENAI_API_KEY)
  OPENAI_API_KEY                 Fallback compartido
  GEMINI_API_KEY                 Compartida (fallback LLM)
  AIRTABLE_TOKEN / AIRTABLE_API_KEY   Token Airtable
  MICA_AIRTABLE_BASE_ID              Base Airtable Mica (appA8QxIhBYYAHw0F)
  MICA_DEMO_AIRTABLE_TABLE_PROPS     ID tabla propiedades
  MICA_DEMO_AIRTABLE_TABLE_CLIENTES  ID tabla clientes/leads

  WHATSAPP_PROVIDER              meta | evolution | ycloud (def: evolution)
  EVOLUTION_API_URL / EVOLUTION_API_KEY / EVOLUTION_INSTANCE  (default Mica)
  META_ACCESS_TOKEN / META_PHONE_NUMBER_ID (si WHATSAPP_PROVIDER=meta)

  INMO_DEMO_NOMBRE         Nombre empresa (def: "Inmobiliaria Demo Mica")
  INMO_DEMO_CIUDAD         Ciudad (def: "Apóstoles")
  INMO_DEMO_ASESOR         Nombre asesor
  INMO_DEMO_NUMERO_ASESOR  Número asesor para notificaciones
  INMO_DEMO_ZONAS          Zonas separadas por coma
  INMO_DEMO_MONEDA         Moneda (def: USD)
  INMO_DEMO_SITIO_WEB      URL del sitio web (opcional)
  INMO_DEMO_CAL_API_KEY    API Key Cal.com (opcional)
  INMO_DEMO_CAL_EVENT_ID   Event Type ID Cal.com (opcional)
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
# OpenAI: MICA propia → fallback a OPENAI_API_KEY compartida (de Arnaldo)
OPENAI_API_KEY    = os.environ.get("MICA_OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_PHONE_ID     = os.environ.get("META_PHONE_NUMBER_ID", "")

# Chatwoot — usamos el de Arnaldo (Mica comparte instancia, no tiene una propia)
CHATWOOT_API_TOKEN  = os.environ.get("CHATWOOT_API_TOKEN", "")
CHATWOOT_URL        = os.environ.get("CHATWOOT_URL", "https://chatwoot.arnaldoayalaestratega.cloud")
CHATWOOT_ACCOUNT_ID = os.environ.get("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_INBOX_ID   = os.environ.get("MICA_CHATWOOT_INBOX_ID", "")

AIRTABLE_TOKEN         = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID       = os.environ.get("MICA_AIRTABLE_BASE_ID", "") or os.environ.get("MICA_DEMO_AIRTABLE_BASE", "")
AIRTABLE_TABLE_PROPS   = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_PROPS", "")
AIRTABLE_TABLE_LEADS   = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_CLIENTES", "")
AIRTABLE_TABLE_ACTIVOS = os.environ.get("MICA_DEMO_AIRTABLE_TABLE_ACTIVOS", "")

# Branding: prioridad MICA_DEMO_* (especifico Mica) → INMO_DEMO_* (legacy compartido)
# Asi Mica puede tener sus propias env vars sin pisar las de Arnaldo en el mismo backend.
NOMBRE_EMPRESA = os.environ.get("MICA_DEMO_NOMBRE")  or os.environ.get("INMO_DEMO_NOMBRE",  "Inmobiliaria Demo Mica")
CIUDAD         = os.environ.get("MICA_DEMO_CIUDAD")  or os.environ.get("INMO_DEMO_CIUDAD",  "Apóstoles")
NOMBRE_ASESOR  = os.environ.get("MICA_DEMO_ASESOR")  or os.environ.get("INMO_DEMO_ASESOR",  "el asesor")
NUMERO_ASESOR  = os.environ.get("MICA_DEMO_NUMERO_ASESOR") or os.environ.get("INMO_DEMO_NUMERO_ASESOR", "")
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

_zonas_raw = os.environ.get("INMO_DEMO_ZONAS", "Apóstoles,Gdor Roca,San Ignacio,Otra Zona")
ZONAS_LIST = [z.strip() for z in _zonas_raw.split(",") if z.strip()]

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ── DB: Airtable Mica (misma API publica que db_postgres de Robert) ──────────
try:
    from workers.clientes.system_ia.demos.inmobiliaria import db_airtable as db
    USE_POSTGRES = db._available()
    if USE_POSTGRES:
        print("[MICA] ✅ Airtable Mica disponible — usando DB directa")
    else:
        print("[MICA] ⚠️ Airtable Mica no configurado — modo sin persistencia")
except ImportError:
    USE_POSTGRES = False
    db = None
    print("[MICA] ⚠️ db_airtable no encontrado — modo sin persistencia")

# ── Provider WhatsApp: capa abstraccion para switch Meta/Evolution/YCloud ────
try:
    from workers.shared import wa_provider as _wa
    _WA_SHARED_OK = True
except Exception as _e:
    _wa = None
    _WA_SHARED_OK = False
    print(f"[MICA] wa_provider no disponible: {_e}")

# Dos routers: uno oficial (Evolution, productivo Mica) + uno v2 (Meta, tech-provider Robert)
router    = APIRouter(prefix="/clientes/system_ia/demos/inmobiliaria",    tags=["Mica — Inmobiliaria"])
router_v2 = APIRouter(prefix="/clientes/system_ia/mica-demo-inmo",        tags=["Mica — Inmobiliaria (Tech Provider)"])

# Multi-tenant slug para el historial/sesion (cada agencia su prefijo)
TENANT_SLUG = os.environ.get("MICA_TENANT_SLUG", "mica-demo")

# ─── SESIONES + HISTORIAL — cache en RAM + persistencia PostgreSQL ─────────────
# Estrategia: RAM es el cache primario (sin latencia por mensaje).
# PostgreSQL persiste en background → sobrevive reinicios y deploys.
# Multi-tenant: cada cliente de Robert tiene su propio LOVBOT_TENANT_SLUG.

HISTORIAL: dict[str, list[str]] = {}
MAX_HISTORIAL = 20


def _sanitizar_nombre(raw: str) -> str:
    """Limpia el nombre del perfil de WhatsApp.

    Trampa comun: usuarios usan '@' como ofuscacion del nombre real para evitar
    spam (ej: '@rn@ldo' = 'Arnaldo'). Antes el regex eliminaba el '@' dejando
    'rnldo' (sin la primera A). Ahora mapeamos '@' → 'a' y luego limpiamos
    el resto de caracteres especiales.

    Tambien normaliza otros leetspeak comunes:
      4 → a, 3 → e, 1 → i, 0 → o (cuando no hay otros digitos cerca)
    """
    if not raw:
        return ""
    s = raw.strip()
    # Mapear leetspeak basico ANTES de eliminar caracteres no-alfa
    s = s.replace("@", "a").replace("@", "a")  # @ unicode + ascii
    # Eliminar todo lo que no sea letra o espacio
    import re as _re
    s = _re.sub(r"[^A-Za-záéíóúüñÁÉÍÓÚÜÑ\s]", "", s).strip()
    # Title case
    return s.title() if s else ""


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
                # Mica puede no tener inbox configurado — permitir matchear cualquier inbox abierto
                inbox_match = (str(c.get("inbox_id", "")) == str(CHATWOOT_INBOX_ID)) if CHATWOOT_INBOX_ID else True
                if inbox_match and c.get("status") == "open":
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


# Provider activo: prioridad override-por-sesion (router v2) → env → default evolution.
# Esto permite que el MISMO bot responda por Evolution a clientes Mica y por
# Meta a los tests via Tech Provider Robert, sin mezclar conversaciones.
def _provider_activo(telefono: str = "") -> str:
    if telefono:
        tel_clean = re.sub(r'\D', '', telefono)
        sesion = SESIONES.get(tel_clean, {}) if tel_clean else {}
        override = sesion.get("_provider_forzado", "")
        if override:
            return override.lower().strip()
    return (os.environ.get("WHATSAPP_PROVIDER", "") or "evolution").lower().strip()


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    """Envia texto via wa_provider. Provider: override-sesion → env → evolution."""
    _agregar_historial(telefono, "Bot", mensaje)
    if not _WA_SHARED_OK:
        print(f"[MICA-SEND] wa_provider no disponible. Msg: {mensaje[:80]}")
        return False
    ok = _wa.send_text(telefono, mensaje, provider=_provider_activo(telefono))
    if ok:
        _cw_mirror_msg(telefono, mensaje, es_bot=True)
    return ok


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    """Envia imagen via wa_provider (switch automatico)."""
    if not _WA_SHARED_OK or not url_imagen:
        return False
    return _wa.send_image(telefono, url_imagen, caption, provider=_provider_activo(telefono))


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
    bot_ya_saludo = False  # Se calcula a partir del historial
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
        # Detectar si el bot ya saludó antes (cualquier turno previo del bot)
        bot_ya_saludo = any("Bot:" in h or "(bot)" in h for h in historial)

    # ── Zonas disponibles ──
    zonas_str = ", ".join(ZONAS_LIST) if ZONAS_LIST else "sin zonas definidas"

    # ── ¿Es un lead recurrente? (escribió antes, ya está en Airtable) ──
    es_recurrente = sesion.get("_lead_recurrente", False)
    estado_previo = sesion.get("_estado_previo", "")
    notas_previas = sesion.get("_notas_previas", "")
    prop_interes_previa = sesion.get("_prop_interes_previa", "")

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
    if not ciudad:      faltantes.append("ciudad (de dónde es el lead)")
    if not objetivo:    faltantes.append("qué busca (comprar/alquilar/invertir)")
    if not tipo:        faltantes.append("tipo de propiedad")
    if not presupuesto: faltantes.append("presupuesto aproximado")
    if not urgencia:    faltantes.append("urgencia / timing de compra")
    faltantes_txt = ", ".join(faltantes) if faltantes else "TODOS los datos ya obtenidos — proceder a calificar"

    # ── SIGUIENTE PREGUNTA DETERMINISTA (orden fijo BANT) ─────────────────
    # Python decide cuál es LA ÚNICA pregunta que el LLM puede hacer este turno.
    # Esto elimina la repetición: el LLM no puede "elegir" otra cosa.
    autoridad_actual = sesion.get("autoridad", "")
    forma_pago_actual = sesion.get("forma_pago", "")
    orden_bant = [
        ("nombre",      nombre,           "¿Con quién tengo el gusto de conversar?"),
        ("ciudad",      ciudad,           f"¿De qué ciudad nos escribís? (saber la distancia a {CIUDAD} nos ayuda a filtrar opciones accesibles)"),
        ("objetivo",    objetivo,         "¿La propiedad sería para vivir o más como inversión?"),
        ("tipo",        tipo,             "¿Qué tipo de propiedad tenés en mente: casa, terreno, departamento...?"),
        ("presupuesto", presupuesto,      f"¿Qué presupuesto aproximado manejás? (en {MONEDA}) ¿Contado o con crédito?"),
        ("autoridad",   autoridad_actual, "¿La decisión la tomás vos o lo definís con pareja/socio/familia?"),
        ("urgencia",    urgencia,         "¿Ya estás buscando activamente o todavía explorando?"),
    ]
    siguiente_campo = None
    siguiente_pregunta_ejemplo = ""
    for campo, valor, ejemplo in orden_bant:
        if not valor:
            siguiente_campo = campo
            siguiente_pregunta_ejemplo = ejemplo
            break
    bant_completo = siguiente_campo is None

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
        "nombre": "Obtener el nombre del cliente con calidez. Explicá que es para llamarle bien durante la conversación.",
        "email": "Pedir email de forma opcional. Explicá que es para tener un canal alternativo si no podés contactarlo por WhatsApp. NO prometas envíos por email — todo se gestiona por acá.",
        "ciudad": f"Preguntar de qué ciudad es. Explicá que es para entender qué tan cerca está de los proyectos en {CIUDAD} y si puede visitarlos. Ej: 'Saber desde dónde escribís nos ayuda a entender qué opciones son más accesibles para vos. ¿De qué ciudad sos?'",
        "objetivo": "Preguntar si es para vivir o invertir. Explicá que esto define qué tipo de propiedad tiene sentido mostrarle. Ej: 'Para filtrarte solo lo que encaja, ¿la propiedad sería para vivir vos, o la ves más como una inversión?'",
        "tipo": "Preguntar tipo de propiedad con contexto. Ej: 'Contame un poco más — ¿tenés en mente algún tipo en particular? ¿Casa, terreno, departamento...?'",
        "presupuesto": f"Preguntar presupuesto con empatía y razón clara. Ej: 'Para no hacerte perder el tiempo con opciones fuera de rango, ¿qué presupuesto aproximado manejás? ¿Sería al contado o con crédito?' — en {MONEDA}.",
        "urgencia": "Preguntar timing con contexto. Ej: 'Dependiendo de cuándo querés concretar, podemos priorizar distintas opciones. ¿Ya estás buscando activamente o todavía explorando?'",
        "calificado": "Datos completos. Mostrar propiedades encontradas o derivar al asesor según score.",
        "lista": "El cliente está viendo la lista de propiedades. Invitarlo a pedir más detalles de alguna. Si pregunta '#' o quiere hablar con alguien → ACCION: ir_asesor.",
        "ficha": "El cliente está viendo una ficha. Preguntarle si quiere agendar una visita o tiene preguntas.",
        "ofrecer_cita": f"El lead ya calificó. Tu ÚNICO objetivo es conseguir la cita. Ofrecé ver horarios con {NOMBRE_ASESOR}. Si el lead dice 'sí', 'dale', 'bueno', 'perfecto' → emitir ACCION: agendar. NO hacer más preguntas.",
        "agendar_slots": f"Mostrar horarios disponibles y pedir que elija. Slots: {slots_txt}",
        "confirmar_cita": "Confirmar la cita elegida. Pedir que confirme o cambie.",
        "recuperacion": f"El cliente volvió después de un tiempo. Saludarlo por nombre ({nombre}) y preguntar si quiere retomar donde estaban o empezar de nuevo.",
    }.get(step, "Continuar la conversación según el contexto.")

    # ── ORIGEN DEL LEAD (Caso A vs Caso B) ──
    saludo_nombre = nombre.split()[0] if nombre else ""
    saludo_pers = f", {saludo_nombre}" if saludo_nombre else ""
    zonas_breve = " · ".join(ZONAS_LIST[:4]) if ZONAS_LIST else ""

    # 🚨 Si el bot YA saludó en turnos anteriores, NO repetir el saludo.
    # Esto evita el bug de "bot saluda 2 veces" cuando el cliente manda audio
    # corto, audio mal transcrito, o un mensaje raro como "ok" / "ah".
    if bot_ya_saludo:
        bloque_origen = f"""## 🔄 CONVERSACIÓN EN CURSO — NO VUELVAS A SALUDAR

⚠️ IMPORTANTE: Vos YA saludaste antes (mirá el historial). NO repitas el saludo
de bienvenida ("Hola, bienvenido a Lovbot..."). NO te presentes de nuevo.

Continuá la conversación natural desde donde quedó. Mirá el ÚLTIMO mensaje
del cliente y respondé lo que corresponda según el flujo BANT.

Si el último mensaje del cliente NO se entiende bien (audio mal transcrito,
texto raro, "ok" suelto, "gracias", "muchas gracias"):
- NO vuelvas a saludar
- Asumí que es respuesta a tu última pregunta y continuá el flujo BANT
- Si ya tenés el nombre del cliente → NUNCA lo vuelvas a pedir, independientemente del mensaje
- Solo pedí el nombre si todavía no lo tenés Y tu última pregunta fue específicamente sobre el nombre
- Si no es claro qué preguntaste, hacé la siguiente pregunta pendiente del BANT
"""
    elif tiene_ref:
        bloque_origen = f"""## 🎯 ORIGEN DEL LEAD: CASO A — VINO DESDE UN ANUNCIO ESPECÍFICO
Propiedad anunciada: '{ad_info}'

ACCIÓN INICIAL OBLIGATORIA (si es el primer mensaje):

📝 SALUDO PROFESIONAL Y CÁLIDO (en 2 mensajes cortos o uno mediano):
- Saludá por nombre si lo tenés.
- Confirmá la disponibilidad de ESA propiedad (precio, m², ubicación, highlight).
- Mencioná brevemente {NOMBRE_EMPRESA} ({CIUDAD}, desarrolladora propia).
- Hacé UNA pregunta abierta para abrir conversación
  (no listés opciones tipo menú).

Ejemplo de tono:
"¡Hola{saludo_pers}! 👋 Te confirmo que el {ad_info} sigue disponible.
Soy el asistente virtual de *{NOMBRE_EMPRESA}*, desarrolladora propia
en {CIUDAD}. ¿Lo estás viendo para vos / para tu familia, o como inversión?"

REGLAS:
- NO empieces preguntando datos personales en frío
- Anclá toda la conversación en LA propiedad anunciada
- Después calificá con BANT (Need → Budget → Authority → Timeline)
- Si pide más opciones → ahí sí abrís catálogo filtrado (2-4 máx)"""
    else:
        # Caso B: SIEMPRE pedimos el nombre al cliente. El nombre del perfil de
        # WhatsApp es poco confiable (puede ser apodo, nombre de empresa, etc.)
        # Si tenemos nombre del perfil, lo usamos como sugerencia para confirmar.
        if nombre:
            instruccion_nombre = (
                f"Tenés '{nombre}' del perfil de WhatsApp del cliente, pero IGUAL DEBÉS CONFIRMAR "
                f"su nombre preguntando: '¿Hablo con {nombre.split()[0]}, verdad? 😊' o "
                f"'¿Con quién tengo el gusto de conversar?' — el nombre del perfil puede ser "
                f"incorrecto o un apodo. Una vez que confirme, usalo en toda la conversación."
            )
            ejemplo_saludo = f"""Ejemplo de tono cálido (NO copiar literal, adaptá):
"¡Hola! 👋 Bienvenido/a a *{NOMBRE_EMPRESA}*, gracias por escribirnos.

Somos una desarrolladora inmobiliaria en {CIUDAD} con proyectos
en {zonas_breve or 'distintas zonas premium'}. Estoy acá para acompañarte
en lo que necesités 🏡

¿Hablo con {nombre.split()[0]}, correcto?"

→ Cuando confirme su nombre, saludalo por su nombre y preguntá Need:
"¡Perfecto, [nombre]! Contame, ¿la propiedad sería para vos / tu familia,
o buscás más una opción de inversión?"
"""
        else:
            instruccion_nombre = (
                "El cliente NO se identificó todavía. PEDÍ su nombre con cortesía SIEMPRE: "
                "'¿Con quién tengo el gusto de conversar?'"
            )
            ejemplo_saludo = f"""Ejemplo de tono cálido (NO copiar literal, adaptá):
"¡Hola! 👋 Bienvenido/a a *{NOMBRE_EMPRESA}*, gracias por escribirnos.

Somos una desarrolladora inmobiliaria en {CIUDAD} con proyectos
en {zonas_breve or 'distintas zonas premium'}. Estoy acá para ayudarte a
encontrar lo que estás buscando 🏡

Antes de seguir, *¿con quién tengo el gusto de conversar?* 😊"

→ Cuando responda con su nombre, saludalo por su nombre y preguntá Need:
"¡Genial [nombre]! Contame, ¿la propiedad sería para
vos / tu familia, o buscás más una opción de inversión?"
"""

        bloque_origen = f"""## 📨 ORIGEN DEL LEAD: CASO B — GENÉRICO (sin anuncio previo)

ACCIÓN INICIAL OBLIGATORIA (si es el primer mensaje):

📝 SALUDO PROFESIONAL DE BIENVENIDA (NO seas seco ni directo):
1. Saludá cordialmente y agradecé el contacto.
2. Presentate como asistente virtual de *{NOMBRE_EMPRESA}*.
3. Mencioná brevemente qué es la empresa: una desarrolladora inmobiliaria
   en {CIUDAD}, con proyectos en {zonas_breve or 'distintas zonas'}.
4. Mostrá disponibilidad genuina ("estoy para ayudarte / acompañarte").
5. **SIEMPRE pedí o confirmá el nombre del cliente** — es OBLIGATORIO.

🔑 NOMBRE DEL CLIENTE (OBLIGATORIO ANTES DE CONTINUAR):
{instruccion_nombre}

{ejemplo_saludo}

REGLAS:
- NO arranques con "Hola, soy el asistente. ¿Vivir o invertir?" (es seco)
- SÍ presentá la empresa antes de calificar
- SÍ pedí o confirmá el nombre SIEMPRE — es el primer paso del BANT
- NO mostrés propiedades hasta tener al menos Need + Budget mínimo
- Una vez calificado → mostrar 2-4 opciones (no más)
- Después de que confirme su nombre → SALUDALO POR SU NOMBRE y seguí el flujo"""

    # ── Bloque LEAD RECURRENTE (si vuelve a escribir tras tiempo ausente) ──
    bloque_recurrente = ""
    if es_recurrente:
        nombre_corto_p = nombre.split()[0] if nombre else ""
        cita_previa = sesion.get('_fecha_cita_previa', '')
        info_previa = []
        if tipo:               info_previa.append(f"buscaba: {tipo}")
        if zona:               info_previa.append(f"zona: {zona}")
        if presupuesto:        info_previa.append(f"presupuesto: {presupuesto}")
        if score:              info_previa.append(f"clasificación previa: {score}")
        if estado_previo:      info_previa.append(f"estado previo: {estado_previo}")
        if prop_interes_previa: info_previa.append(f"se interesó por: {prop_interes_previa}")
        if cita_previa:        info_previa.append(f"cita previa: {cita_previa}")
        info_str = " · ".join(info_previa) if info_previa else "sin datos previos relevantes"
        notas_str = f"\nNotas previas del bot: {notas_previas[:300]}" if notas_previas else ""
        nombre_para_saludo = nombre_corto_p or nombre or "[nombre]"
        cita_linea = (f"Si el lead ya tenía cita agendada ({cita_previa}), "
                      "preguntá si está vinculado a esa visita."
                      if cita_previa else "")

        bloque_recurrente = f"""
## ⚡ LEAD RECURRENTE — YA TE ESCRIBIÓ ANTES

Este cliente ({nombre or 'sin nombre'}) ya está en la base de datos. Datos previos:
{info_str}{notas_str}

🔑 INSTRUCCIONES CRÍTICAS PARA LEAD RECURRENTE:
1. **Saludalo por su nombre** y reconocé que ya hablaron antes.
   Ej: "Hola {nombre_para_saludo}, ¡qué gusto verte de nuevo!"
2. **NO le pidas datos que ya diste** (nombre, tipo, zona, presupuesto, etc.)
3. **Hacé referencia a la búsqueda anterior** si tiene sentido.
   Ej: "La última vez estabas viendo {tipo or 'propiedades'} en {zona or 'la zona'}.
        ¿Querés retomar por ahí o cambió algo?"
4. {cita_linea}
5. Si era **caliente/tibio** previo y vuelve, asumí intención real → mostrá props
   actualizadas o ofrecé agendar directo.
6. Si era **frío** previo, dale otra chance pero estate alerta a señales de curiosidad.
"""

    # ── Bloque SIGUIENTE PREGUNTA — determinista, elimina repetición ──────
    if bant_completo:
        bloque_siguiente = """## 🎯 SIGUIENTE ACCIÓN (determinista)

✅ BANT COMPLETO — ya tenés todos los datos del lead.
→ NO hagas más preguntas BANT.
→ Emití `ACCION: agendar` para conseguir la cita, sin texto conversacional adicional.
"""
    else:
        bloque_siguiente = f"""## 🎯 SIGUIENTE PREGUNTA (única permitida este turno)

Campo a capturar: **{siguiente_campo}**
Ejemplo de cómo formularla (adaptá con tu tono, NO copies literal):
  "{siguiente_pregunta_ejemplo}"

🚫 REGLAS IRROMPIBLES DE ESTE TURNO:
1. SOLO podés preguntar por **{siguiente_campo}**. Cualquier otra pregunta está PROHIBIDA.
2. Si el lead ya respondió `{siguiente_campo}` en un turno anterior (ver DATOS YA CAPTURADOS),
   NO vuelvas a preguntarlo — avanzá al siguiente campo pendiente.
3. Si el lead te pregunta algo (precio, ubicación, horario), respondé brevemente Y DESPUÉS
   hacé la pregunta de **{siguiente_campo}** — una sola vez, sin reformular.
4. Si ya preguntaste **{siguiente_campo}** en el turno anterior del historial y el lead no
   respondió claramente, NO insistas — emití `ACCION: ir_asesor` o `ACCION: cerrar_curioso`.
"""

    system = f"""Sos el asistente virtual de *{NOMBRE_EMPRESA}*, una agencia inmobiliaria en {CIUDAD}.
El asesor humano se llama *{NOMBRE_ASESOR}*.

## TU MISIÓN — FILTRO PROFESIONAL BANT
Calificar leads inmobiliarios usando metodología BANT (Budget, Authority, Need, Timeline)
en menos de 2 minutos. NO sos un menú, sos un consultor que charla por WhatsApp.

OBJETIVO: identificar 3 tipos de leads:
🔥 CALIENTE → presupuesto claro + forma de pago definida + urgencia <3m → AGENDAR YA
🌡️ TIBIO   → presupuesto amplio o urgencia 3-6m → MOSTRAR 2-4 opciones + nurturing
❄️ FRÍO    → "solo viendo", sin presupuesto/urgencia → CERRAR amable + nurturing
{bloque_recurrente}
{bloque_origen}

{bloque_siguiente}

## METODOLOGÍA BANT (orden estricto, una pregunta por turno)

1. **NEED** (qué busca)
   - "¿De qué ciudad nos escribís?" ← importante para saber si puede visitar
   - "¿Es para vivir o invertir?"
   - "¿Qué tipo de propiedad? (casa, departamento, terreno…)"
   - ⚠️ NO preguntes por zona interna de los proyectos — el lead no conoce las zonas

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
- Cálido, empático, profesional. Como un asesor de confianza, no un formulario.
- Cada pregunta debe tener CONTEXTO y RAZÓN — el cliente tiene que entender POR QUÉ le preguntás.
  Ejemplos de cómo hacerlo natural:
  - "Para mostrarte opciones que encajen con tu búsqueda, ¿es para vivir o más como inversión?"
  - "El presupuesto nos ayuda a filtrarte solo lo que tiene sentido para vos, sin hacerte perder tiempo. ¿Qué rango manejás?"
  - "A veces estas decisiones se toman en familia o con socios — ¿hay alguien más en el proceso?"
  - "Saber desde dónde escribís nos ayuda a entender qué tan cerca estás de los proyectos. ¿De qué ciudad sos?"
- Después de cada respuesta del cliente, ACUSÁ RECIBO antes de preguntar lo siguiente.
  Ej: "Perfecto, terreno para invertir — buena elección en este mercado 💪" → luego la siguiente pregunta.
- Mensajes cortos: máximo 3-4 líneas. UNA sola pregunta por mensaje.
- *Negrita* solo para datos importantes (precios, fechas, nombres de proyectos).
- Emojis con moderación: máximo 1-2 por mensaje.
- Nunca uses "opción 1, 2, 3" para preguntas conversacionales (sí para slots o propiedades).
- Si el cliente dice "hola", "menú" o "0" → reconocer y continuar donde quedó la sesión.

## REGLAS CRÍTICAS

✅ HACER:
- Una pregunta por mensaje (NUNCA dos a la vez)
- Si Caso A: anclar conversación en LA propiedad anunciada
- Mostrar máximo 2-4 propiedades (NO 10) y SOLO si el lead las pide explícitamente
- Forma de pago es PREGUNTA OBLIGATORIA antes de agendar visita
- Después de agendar, ofrecer UNA sola cosa más (no agenda + info juntos)
- Cuando el lead confirma interés o dice "sí" → ir directo a ofrecer la cita, no hacer más preguntas

🚫 REGLA IRROMPIBLE — NUNCA REPETIR:
- Si ya preguntaste algo en este turno o en turnos anteriores → NO lo vuelvas a preguntar
- Si el lead dijo "sí" o confirmó algo → NO reformular la misma pregunta con otras palabras
- Revisá el HISTORIAL antes de cada respuesta — si ya preguntaste "¿querés agendar?" no lo vuelvas a preguntar
- Una confirmación ("sí", "dale", "perfecto") = avanzar al siguiente paso, nunca repetir

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

🚫 REGLA CRÍTICA — HORARIOS DE CITA:
- NUNCA inventes horarios de cita (ej: "tengo a las 16:00 o 18:00").
- Los horarios reales los maneja el sistema vía Cal.com automáticamente.
- Si el lead pregunta por horarios disponibles, respondé SOLO con:
  "Dejame chequear los horarios disponibles con {NOMBRE_ASESOR}"
  y NO listes horarios concretos — el sistema los envía después.
- Si el lead dice "sí quiero agendar" → emitir ACCION: agendar (nada más).

## DETECCIÓN DE CAÍDA
Si el lead deja de responder, da monosílabos repetidos, o evade calificación
→ cambiar a modo recuperación con UNA frase tipo:
- "¿Qué te faltó para decidirte?"
- "¿Te puedo enviar comparativo de otras opciones similares?"
- "Decime un buen día/hora y te llamo personalmente."

Si después de 2 intentos no hay engagement → ACCION: cerrar_curioso

## DATOS YA CONOCIDOS DEL CLIENTE
{datos_txt}

⚠️ REGLA CRÍTICA — NO REPETIR: Si un dato ya aparece en "DATOS YA CONOCIDOS", NUNCA vuelvas a preguntarlo.
Esto incluye nombre, ciudad, objetivo, tipo, presupuesto, urgencia, forma de pago y autoridad.
Si el cliente acaba de responder algo, ese dato ya está guardado — pasá al siguiente faltante.

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


def _procesar_safe(telefono: str, texto: str, referral: dict = None) -> None:
    """Wrapper que ejecuta _procesar y captura cualquier excepcion para que el
    background thread no muera silenciosamente. Critico para debug en produccion."""
    try:
        _procesar(telefono, texto, referral)
    except Exception as e:
        import traceback
        print(f"[MICA-CRASH] tel={telefono} exc={type(e).__name__}: {e}")
        print(f"[MICA-CRASH] traceback:\n{traceback.format_exc()}")
        # Intentar mandar mensaje de error al user para que sepa que algo paso
        try:
            _enviar_texto(telefono,
                "Disculpá, tuve un problema técnico procesando tu mensaje. "
                "Probá de nuevo en un momento o escribime '#' para hablar con un asesor.")
        except Exception:
            pass


def _procesar(telefono: str, texto: str, referral: dict = None) -> None:
    referral = referral or {}
    # Si el asesor tomó control, el bot NO responde
    if bot_pausado(telefono):
        print(f"[MICA] Bot pausado para {telefono} — asesor activo, ignorando mensaje")
        return

    # ── Restaurar sesión desde BotSessions si no está en RAM (post-deploy) ──
    # o si la sesión en RAM es solo el nombre precargado por el webhook.
    # El webhook pasa nombre_meta y provider_forzado via referral (keys con _ prefix)
    # para aplicarlos DESPUES de cargar la sesion persistida.
    _nombre_meta_from_hook = referral.pop("_nombre_meta", "") if isinstance(referral, dict) else ""
    _provider_forzado_from_hook = referral.pop("_provider_forzado", "") if isinstance(referral, dict) else ""

    sesion_actual = SESIONES.get(telefono, {})
    sesion_es_minima = (
        not sesion_actual or
        (set(sesion_actual.keys()) - {"nombre", "_ultimo_ts", "origen_lead"}) == set()
    )
    if sesion_es_minima:
        if telefono in SESIONES:
            super(_SessionStore, SESIONES).__delitem__(telefono)
        _cargar_sesion_db(telefono)

    # Aplicar nombre/provider del webhook si corresponde (SIN triggear save todavia —
    # se va a guardar al final cuando el flow asigne SESIONES[tel] = ...)
    _s_actual = SESIONES.get(telefono, {})
    if _s_actual:
        if _nombre_meta_from_hook and not _s_actual.get("nombre"):
            nombre_limpio = _sanitizar_nombre(_nombre_meta_from_hook)
            if nombre_limpio and len(nombre_limpio) >= 2:
                _s_actual["nombre"] = nombre_limpio
                print(f"[MICA] Nombre aplicado post-load: {_nombre_meta_from_hook} → {nombre_limpio}")
        if _provider_forzado_from_hook:
            _s_actual["_provider_forzado"] = _provider_forzado_from_hook

    # ── Detectar lead RECURRENTE en tabla `leads` (fallback si no hay BotSession) ──
    sesion_actual = SESIONES.get(telefono, {})
    sesion_es_minima = (
        not sesion_actual or
        (set(sesion_actual.keys()) - {"nombre", "_ultimo_ts", "origen_lead"}) == set()
    )
    no_es_recurrente_aun = not sesion_actual.get("_lead_recurrente", False)
    if sesion_es_minima and no_es_recurrente_aun:
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
        print(f"[MICA] Lead desde anuncio: {referral.get('headline') or referral.get('body','')}")

    # ── Crear sesion minima si NO existe (lead directo sin referral) ──────
    # Critico para Mica: la mayoria de leads llegan por Evolution sin venir de ad,
    # entonces necesitan una sesion inicial para que el flow BANT funcione.
    if telefono not in SESIONES:
        SESIONES[telefono] = {
            "step": "inicio",
            "subniche": "agencia_inmobiliaria",
            "_fuente_detalle": "whatsapp_directo",
            "_ultimo_ts": ahora_ts,
        }
        sesion = SESIONES[telefono]
        nombre_pre = sesion.get("nombre", "")
        tel_masked = re.sub(r"\D", "", telefono)[-4:]
        print(f"[MICA] Lead nuevo directo (sin referral): tel={tel_masked}*** nombre_pre={nombre_pre or '?'}")

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
                # Guardar cita en PostgreSQL (robert_crm) — Robert NO usa Airtable
                threading.Thread(target=db.guardar_cita, args=(telefono, slot.get("time","")), daemon=True).start()
                # Legacy Airtable — fallback por si el tenant tiene Airtable configurado
                if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
                    threading.Thread(target=_at_guardar_cita, args=(telefono, slot.get("time","")), daemon=True).start()
                # Notificar al asesor SOLO cuando la cita está confirmada
                # (antes se hacía en la calificación — ahora se espera a la confirmación real)
                _cal_guardada = sesion.get("_calificacion", {})
                _sesion_con_cita = {**sesion, "fecha_str": fecha_str, "fecha_cita": slot.get("time", "")}
                threading.Thread(target=_notificar_asesor, args=(telefono, _sesion_con_cita, _cal_guardada), daemon=True).start()
                _enviar_texto(telefono,
                    f"✅ *¡Cita confirmada{', ' + nombre_corto if nombre_corto else ''}!*\n\n"
                    f"📅 *{fecha_str}* con *{NOMBRE_ASESOR}*\n\n"
                    f"Te vamos a contactar por acá unos minutos antes para confirmar. "
                    f"Si necesitás reagendar, escribime. 😊\n"
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
    # Extraer ACCION tambien si aparece entre corchetes/parentesis (leak comun del LLM)
    # Ej: "[ACCION: mostrar_props]", "(ACCION: agendar)", "**ACCION**: cerrar_curioso"
    for _m in re.finditer(r"[\[\(]?\s*\*?\*?\s*ACCION\s*\*?\*?\s*:\s*([a-z_]+)\s*[\]\)]?", respuesta_llm, re.IGNORECASE):
        val = _m.group(1).strip().lower()
        if val and "accion" not in acciones:
            acciones["accion"] = val
    # Y limpiar esos patrones del texto visible (los corchetes/parentesis tambien)
    respuesta_llm_clean = re.sub(
        r"[\[\(]?\s*\*?\*?\s*ACCION\s*\*?\*?\s*:\s*[a-z_]+\s*[\]\)]?",
        "",
        respuesta_llm,
        flags=re.IGNORECASE,
    )
    lineas = respuesta_llm_clean.strip().split("\n")

    for linea in lineas:
        # Headers tipo "EXTRACCIÓN DE DATOS:" o "===" → ocultar
        if _es_header_interno(linea):
            continue
        # Líneas que empiezan con una KEY interna (leak del prompt) → ocultar
        linea_strip = linea.strip()
        # Quitar [ ( al inicio para detectar leak: "[ACCION: ..." "(NOMBRE: ..."
        linea_upper = re.sub(r"^[\[\(\*\s]+", "", linea_strip).upper()
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
                # Sanitiza nombre (mapea '@' → 'a' antes de limpiar simbolos)
                nombre_limpio = _sanitizar_nombre(value)
                acciones["nombre"] = nombre_limpio if nombre_limpio else value.title()
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
        _args_reg = (
            telefono, nombre or "Sin nombre", "frio",
            sesion_nueva.get("resp_tipo",""),
            sesion_nueva.get("resp_zona",""),
            "Lead no calificado — evasivo/curioso (filtrado por bot)",
            sesion_nueva.get("presupuesto_at",""),
            sesion_nueva.get("operacion_at",""),
            sesion_nueva.get("ciudad_resp", CIUDAD),
            sesion_nueva.get("subniche",""),
            sesion_nueva.get("_fuente_detalle",""),
        )
        # PostgreSQL (Robert usa PG, no Airtable)
        threading.Thread(target=db.registrar_lead, args=_args_reg, daemon=True).start()
        # Airtable fallback solo si está configurado
        if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
            threading.Thread(target=_at_registrar_lead, args=_args_reg, daemon=True).start()
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

        # Registrar lead (background) — PostgreSQL principal + Airtable fallback
        _args_reg = (
            telefono, nombre, score, tipo, zona, nota,
            sesion_nueva.get("presupuesto_at",""),
            sesion_nueva.get("operacion_at",""),
            sesion_nueva.get("ciudad_resp", CIUDAD),
            sesion_nueva.get("subniche",""),
            sesion_nueva.get("_fuente_detalle",""),
        )
        threading.Thread(target=db.registrar_lead, args=_args_reg, daemon=True).start()
        if AIRTABLE_BASE_ID and AIRTABLE_TABLE_LEADS:
            threading.Thread(target=_at_registrar_lead, args=_args_reg, daemon=True).start()

        # NOTA: _notificar_asesor se mueve al handler de confirmar_cita.
        # El asesor solo debe recibir el aviso "🔥 Nuevo Lead" cuando el lead CONFIRMA
        # la cita agendada, no cuando termina el BANT. Guardamos la calificación en
        # sesión para que el handler post-confirmación tenga los datos a mano.
        sesion_nueva["_calificacion"] = calificacion
        SESIONES[telefono] = sesion_nueva
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

    # ── Step calificado → si ya tenemos autoridad, disparar slots Cal.com ─────
    # Cubre el caso donde el BANT se completa con autoridad al último turno:
    # en el turno anterior ya se marcó _ya_calificado=True pero faltaba autoridad.
    # Ahora que el lead respondió autoridad, forzamos ofrecer slots.
    if step == "calificado" and sesion_nueva.get("autoridad") and sesion_nueva.get("score") in ("caliente", "tibio"):
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
        _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
            nombre=nombre_corto or nombre, asesor=NOMBRE_ASESOR, empresa=NOMBRE_EMPRESA))
        SESIONES.pop(telefono, None)
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


# ─── ENDPOINT WEBHOOK (2 routers, misma logica) ──────────────────────────────
META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "mica_webhook_2026")


async def _webhook_handler(request: Request, provider_forzado: str = ""):
    """Handler unificado para ambos routers (Evolution + Meta via Tech Provider).

    Usa wa_provider.parse_incoming() que auto-detecta el formato:
    - Evolution API (MESSAGES_UPSERT / messages.upsert)
    - Meta Graph (whatsapp_business_account)
    - bridge interno (from/text directo — cuando el forwarder Robert llama)
    - YCloud (por si en algun momento Mica migra)

    `provider_forzado`: si esta seteado (ej: "meta" en el router v2), sobreescribe
    la env var WHATSAPP_PROVIDER solo para los sends de esta conversacion.
    """
    data = await request.json()
    if not _WA_SHARED_OK:
        return {"status": "error", "reason": "wa_provider no disponible"}

    parsed = _wa.parse_incoming(data)
    if not parsed:
        return {"status": "ignored", "reason": "payload no reconocido"}

    telefono = parsed.get("telefono", "")
    texto    = parsed.get("texto", "")
    referral = parsed.get("referral", {}) or {}
    nombre_meta = parsed.get("nombre", "")
    tipo_msg = parsed.get("tipo", "text")

    # Audio: intentar transcribir (solo si viene por Meta — tenemos media_id)
    if tipo_msg == "audio" and not texto:
        raw_msg = parsed.get("raw", {})
        media_id = raw_msg.get("audio", {}).get("id", "") if isinstance(raw_msg, dict) else ""
        if media_id:
            texto = _transcribir_audio_meta(media_id)
            if not texto:
                tel_tmp = re.sub(r'\D', '', telefono)
                if tel_tmp:
                    _enviar_texto(tel_tmp,
                        "No pude escuchar bien el audio 😔. ¿Me lo escribís o lo grabás de nuevo?")
                return {"status": "ignored", "reason": "audio-no-transcrito"}

    if not telefono or not texto:
        return {"status": "ignored"}

    tel_clean = re.sub(r'\D', '', telefono)

    # Pre-cargar nombre desde perfil WhatsApp (Meta trae "contacts.profile.name",
    # Evolution trae "pushName") — ambos normalizados por wa_provider
    # IMPORTANTE: si la sesion no esta en RAM, NO la pisamos con solo {nombre}.
    # Dejamos que _procesar la cargue desde Airtable BotSessions primero.
    if nombre_meta and tel_clean in SESIONES:
        sesion_pre = SESIONES.get(tel_clean, {})
        if not sesion_pre.get("nombre"):
            nombre_limpio = _sanitizar_nombre(nombre_meta)
            if nombre_limpio and len(nombre_limpio) >= 2:
                sesion_pre["nombre"] = nombre_limpio
                SESIONES[tel_clean] = sesion_pre
                print(f"[MICA-WEBHOOK] Nombre precargado: {nombre_meta} → {nombre_limpio} → {tel_clean}")

    if referral and (referral.get("headline") or referral.get("source_url")):
        print(f"[MICA-WEBHOOK] Lead vino de ad: {referral.get('headline', '')[:60]}")

    # Si se fuerza un provider (router v2 → meta), setear para esta sesion
    # provider_forzado: mismo cuidado que con nombre_meta — no pisar sesion completa
    # con sesion minima si el tel no esta en RAM.
    if provider_forzado and tel_clean in SESIONES:
        sesion_pre = SESIONES.get(tel_clean, {})
        sesion_pre["_provider_forzado"] = provider_forzado
        SESIONES[tel_clean] = sesion_pre

    # Pasar nombre_meta y provider_forzado a _procesar para que los use despues
    # de cargar la sesion persistida.
    if nombre_meta:
        referral = {**referral, "_nombre_meta": nombre_meta}
    if provider_forzado:
        referral = {**referral, "_provider_forzado": provider_forzado}

    threading.Thread(target=_procesar_safe, args=(tel_clean, texto, referral), daemon=True).start()
    return {"status": "processing", "provider_detectado": parsed.get("provider", "?")}


# ── Router oficial (Evolution default — productivo Mica) ─────────────────────

@router.get("/whatsapp")
async def verificar_webhook_mica(request: Request):
    """Handshake Meta (solo si WHATSAPP_PROVIDER=meta). Evolution no usa GET."""
    from fastapi.responses import PlainTextResponse, Response
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=200)
    return Response(status_code=403)


@router.post("/whatsapp")
async def webhook_whatsapp_oficial(request: Request):
    """Webhook oficial Mica — recibe Evolution API (default) o Meta si override."""
    return await _webhook_handler(request)


# ── Router v2 (Tech Provider Robert → Meta forzado) ──────────────────────────

@router_v2.get("/whatsapp")
async def verificar_webhook_v2(request: Request):
    """Handshake Meta para router v2 (Tech Provider Robert)."""
    from fastapi.responses import PlainTextResponse, Response
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=200)
    return Response(status_code=403)


@router_v2.post("/whatsapp")
async def webhook_whatsapp_v2(request: Request):
    """Webhook v2 Mica — recibe payload desde Tech Provider Robert (Meta)."""
    return await _webhook_handler(request, provider_forzado="meta")


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
            nombre_ads_limpio = _sanitizar_nombre(nombre_ads)
            if nombre_ads_limpio and len(nombre_ads_limpio) >= 2:
                sesion_pre["nombre"] = nombre_ads_limpio
        if email_ads:
            sesion_pre["email"] = email_ads
        sesion_pre["origen_lead"] = "meta_ads_form"
        SESIONES[tel] = sesion_pre

    primer_mensaje = body.get("mensaje", "Hola, me interesa la propiedad que vi en el anuncio")
    threading.Thread(target=_procesar_safe, args=(tel, primer_mensaje, referral), daemon=True).start()
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


# ── NURTURING 24H ─────────────────────────────────────────────────────────────

@router.post("/admin/setup-nurturing")
def setup_nurturing():
    """Agrega las columnas nurturing_24h_enviado / nurturing_24h_fecha a la tabla leads.
    Idempotente — llamar una sola vez después del deploy, o volver a llamar sin riesgo.
    """
    _check_pg()
    return db.setup_nurturing_columns()


@router.post("/admin/nurturing/24h")
def nurturing_24h():
    """Envía mensajes de seguimiento a leads calificados que NO agendaron cita
    en las últimas 24 horas.

    Comportamiento:
    - Consulta PostgreSQL: estado IN ('calificado','contactado') + fecha_cita IS NULL
      + fecha_ultimo_contacto < NOW() - 24h + nurturing_24h_enviado = FALSE
    - Para cada lead: arma mensaje personalizado y lo envía via Meta Graph API
    - Marca nurturing_24h_enviado = TRUE (idempotente — no reenvía en llamadas siguientes)
    - Retorna resumen con contadores de enviados / fallidos / elegibles

    Uso desde n8n: Schedule node cada hora → HTTP POST a este endpoint.
    Header recomendado: Authorization: Bearer {LOVBOT_ADMIN_TOKEN}
    """
    _check_pg()

    leads = db.obtener_leads_sin_cita_24h()
    if not leads:
        return {"status": "ok", "elegibles": 0, "enviados": 0, "fallidos": 0, "detalle": []}

    enviados = []
    fallidos = []

    for lead in leads:
        lead_id  = lead["id"]
        telefono = lead.get("telefono", "")
        if not telefono:
            fallidos.append({"lead_id": lead_id, "razon": "sin telefono"})
            continue

        nombre   = lead.get("nombre") or "amigo"
        ciudad   = lead.get("ciudad") or CIUDAD
        tipo     = lead.get("tipo_propiedad") or "propiedad"
        operacion = lead.get("operacion") or ""

        # Construir descripción de búsqueda ("comprar una casa", "invertir en un lote", etc.)
        if operacion and operacion.lower() not in ("", "no sé", "no se"):
            descripcion_busqueda = f"{operacion} {tipo}".strip().lower()
        else:
            descripcion_busqueda = tipo.lower() if tipo else "una propiedad"

        mensaje = (
            f"Hola {nombre.title()} 👋 Soy el asistente de {NOMBRE_EMPRESA}.\n\n"
            f"Vi que estuviste consultando sobre {descripcion_busqueda} en {ciudad}. "
            f"Quería saber si pudiste charlarlo y si hay algo que te falta para dar el siguiente paso 🏡\n\n"
            f"Cuando quieras, puedo mostrarte algunas opciones o coordinar una reunión rápida con nuestro asesor {NOMBRE_ASESOR}."
        )

        ok = _enviar_texto(telefono, mensaje)
        if ok:
            db.marcar_nurturing_enviado(lead_id)
            enviados.append({
                "lead_id": lead_id,
                "telefono": telefono,
                "nombre": nombre,
            })
            print(f"[NURTURING-24H] Enviado → tel={telefono} nombre={nombre}")
        else:
            fallidos.append({
                "lead_id": lead_id,
                "telefono": telefono,
                "razon": "error Meta Graph API",
            })
            print(f"[NURTURING-24H] Fallo envío → tel={telefono}")

    return {
        "status": "ok",
        "elegibles": len(leads),
        "enviados": len(enviados),
        "fallidos": len(fallidos),
        "detalle_enviados": enviados,
        "detalle_fallidos": fallidos,
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
    """Lista resúmenes con filtros: limit, score_min, desde (YYYY-MM-DD), search (texto libre).
    Mica usa Airtable — listar_resumenes() retorna [] hasta que se implemente tabla."""
    try:
        rows = db.listar_resumenes(limit=limit, score_min=score_min, desde=desde, search=search)
    except TypeError:
        # Retrocompat: versión vieja sin parámetros
        rows = db.listar_resumenes()
    for r in rows:
        for k in ("fecha_conversacion", "created_at"):
            if r.get(k) and hasattr(r[k], "isoformat"):
                r[k] = r[k].isoformat()
    return {"total": len(rows), "records": rows}


# ═══════════════════════════════════════════════════════════════════════════
# CRM COMPLETO MULTI-SUBNICHO — Endpoints Sprints 3-8
# Asesores / Propietarios / Loteos / Lotes_Mapa / Contratos / Visitas / Reportes
# ═══════════════════════════════════════════════════════════════════════════

def _check_pg():
    """Mica usa Airtable como backend — esta función es no-op (siempre pasa).
    El guard real ocurre dentro de db_airtable cuando TOKEN/BASE_ID no están configurados.
    Se mantiene el nombre _check_pg para que los endpoints que ya lo llaman no rompan.
    """
    pass  # Airtable siempre disponible si env vars configuradas


def _check_at():
    """Verifica que Airtable esté configurado. Lanza 503 si no."""
    from fastapi import HTTPException
    if not db._available():
        raise HTTPException(status_code=503, detail="Airtable no configurado (TOKEN/BASE_ID faltantes)")


# ── Asesores (Sprint 3) ─────────────────────────────────────────────────────
@router.get("/crm/asesores")
def crm_asesores_list():
    _check_at()
    return db.get_all_asesores()

@router.post("/crm/asesores")
async def crm_asesor_create(request: Request):
    _check_at()
    return db.create_asesor(await request.json())

@router.patch("/crm/asesores/{record_id}")
async def crm_asesor_update(record_id: str, request: Request):
    _check_at()
    return db.update_asesor(record_id, await request.json())

@router.delete("/crm/asesores/{record_id}")
def crm_asesor_delete(record_id: str):
    _check_at()
    return db.delete_asesor(record_id)


# ── Propietarios (Sprint 4) ─────────────────────────────────────────────────
@router.get("/crm/propietarios")
def crm_propietarios_list():
    _check_at()
    return db.get_all_propietarios()

@router.post("/crm/propietarios")
async def crm_propietario_create(request: Request):
    _check_at()
    return db.create_propietario(await request.json())

@router.patch("/crm/propietarios/{record_id}")
async def crm_propietario_update(record_id: str, request: Request):
    _check_at()
    return db.update_propietario(record_id, await request.json())

@router.delete("/crm/propietarios/{record_id}")
def crm_propietario_delete(record_id: str):
    _check_at()
    return db.delete_propietario(record_id)


# ── Loteos (Sprint 5) ───────────────────────────────────────────────────────
@router.get("/crm/loteos")
def crm_loteos_list():
    _check_at()
    return db.get_all_loteos()

@router.post("/crm/loteos")
async def crm_loteo_create(request: Request):
    _check_at()
    return db.create_loteo(await request.json())

@router.patch("/crm/loteos/{record_id}")
async def crm_loteo_update(record_id: str, request: Request):
    _check_at()
    return db.update_loteo(record_id, await request.json())

@router.delete("/crm/loteos/{record_id}")
def crm_loteo_delete(record_id: str):
    _check_at()
    return db.delete_loteo(record_id)


# ── Lotes Mapa (Sprint 5) ───────────────────────────────────────────────────
@router.get("/crm/lotes-mapa")
def crm_lotes_mapa_list(loteo_id: str = None):
    _check_at()
    return db.get_lotes_mapa(loteo_id)

@router.post("/crm/lotes-mapa")
async def crm_lote_mapa_create(request: Request):
    _check_at()
    return db.create_lote_mapa(await request.json())

@router.patch("/crm/lotes-mapa/{record_id}")
async def crm_lote_mapa_update(record_id: str, request: Request):
    _check_at()
    return db.update_lote_mapa(record_id, await request.json())

@router.delete("/crm/lotes-mapa/{record_id}")
def crm_lote_mapa_delete(record_id: str):
    _check_at()
    return db.delete_lote_mapa(record_id)


# ── Contratos (Sprint 6) ────────────────────────────────────────────────────
@router.get("/crm/contratos")
def crm_contratos_list():
    _check_at()
    return db.get_all_contratos()

@router.post("/crm/contratos")
async def crm_contrato_create(request: Request):
    """Contrato unificado v3 (3 ramas) o legacy passthrough.
    v3: payload con cliente_activo_id | convertir_lead_id | cliente_nuevo.
    Legacy: cualquier otro payload → create_contrato directo.
    """
    from fastapi import HTTPException
    _check_at()
    data = await request.json()
    es_v3 = any(k in data for k in ("cliente_activo_id", "convertir_lead_id", "cliente_nuevo"))
    if es_v3:
        resultado = db.crear_contrato_unificado(data)
        if "error" in resultado and not resultado.get("log"):
            raise HTTPException(status_code=400, detail=resultado["error"])
        return resultado
    return db.create_contrato(data)

@router.patch("/crm/contratos/{record_id}")
async def crm_contrato_update(record_id: str, request: Request):
    _check_at()
    return db.update_contrato(record_id, await request.json())

@router.delete("/crm/contratos/{record_id}")
def crm_contrato_delete(record_id: str):
    _check_at()
    return db.delete_contrato(record_id)


@router.get("/crm/clientes-activos/{cliente_id}/contratos")
def crm_contratos_by_cliente(cliente_id: str):
    """Lista todos los contratos de un cliente activo."""
    _check_at()
    return db.get_contratos_by_cliente(cliente_id)


# ── Visitas / Agenda (Sprint 8) ─────────────────────────────────────────────
@router.get("/crm/visitas")
def crm_visitas_list():
    _check_at()
    return db.get_all_visitas()

@router.post("/crm/visitas")
async def crm_visita_create(request: Request):
    _check_at()
    return db.create_visita(await request.json())

@router.patch("/crm/visitas/{record_id}")
async def crm_visita_update(record_id: str, request: Request):
    _check_at()
    return db.update_visita(record_id, await request.json())

@router.delete("/crm/visitas/{record_id}")
def crm_visita_delete(record_id: str):
    _check_at()
    return db.delete_visita(record_id)


# ── InmueblesRenta (Agencia) ─────────────────────────────────────────────────
@router.get("/crm/inmuebles-renta")
def crm_inmuebles_renta_list():
    _check_at()
    return db.get_all_inmuebles_renta()

@router.post("/crm/inmuebles-renta")
async def crm_inmueble_renta_create(request: Request):
    _check_at()
    return db.create_inmueble_renta(await request.json())

@router.patch("/crm/inmuebles-renta/{record_id}")
async def crm_inmueble_renta_update(record_id: str, request: Request):
    _check_at()
    return db.update_inmueble_renta(record_id, await request.json())

@router.delete("/crm/inmuebles-renta/{record_id}")
def crm_inmueble_renta_delete(record_id: str):
    _check_at()
    return db.delete_inmueble_renta(record_id)


# ── Inquilinos (legacy + compatibilidad) ────────────────────────────────────
@router.get("/crm/inquilinos")
def crm_inquilinos_list(inmueble_renta_id: str = None):
    _check_at()
    return db.get_all_inquilinos(inmueble_renta_id)

@router.post("/crm/inquilinos")
async def crm_inquilino_create(request: Request):
    _check_at()
    return db.create_inquilino(await request.json())

@router.patch("/crm/inquilinos/{record_id}")
async def crm_inquilino_update(record_id: str, request: Request):
    _check_at()
    return db.update_inquilino(record_id, await request.json())

@router.delete("/crm/inquilinos/{record_id}")
def crm_inquilino_delete(record_id: str):
    _check_at()
    return db.delete_inquilino(record_id)


# ── PagosAlquiler ────────────────────────────────────────────────────────────
@router.get("/crm/pagos-alquiler")
def crm_pagos_alquiler_list(inquilino_id: str = None, mes_anio: str = None):
    _check_at()
    return db.get_all_pagos_alquiler(inquilino_id, mes_anio)

@router.post("/crm/pagos-alquiler")
async def crm_pago_alquiler_create(request: Request):
    _check_at()
    return db.create_pago_alquiler(await request.json())

@router.patch("/crm/pagos-alquiler/{record_id}")
async def crm_pago_alquiler_update(record_id: str, request: Request):
    _check_at()
    return db.update_pago_alquiler(record_id, await request.json())

@router.delete("/crm/pagos-alquiler/{record_id}")
def crm_pago_alquiler_delete(record_id: str):
    _check_at()
    return db.delete_pago_alquiler(record_id)


# ── Liquidaciones ────────────────────────────────────────────────────────────
@router.get("/crm/liquidaciones")
def crm_liquidaciones_list(propietario_id: str = None, mes_anio: str = None):
    _check_at()
    return db.get_all_liquidaciones(propietario_id, mes_anio)

@router.post("/crm/liquidaciones")
async def crm_liquidacion_create(request: Request):
    _check_at()
    return db.create_liquidacion(await request.json())

@router.patch("/crm/liquidaciones/{record_id}")
async def crm_liquidacion_update(record_id: str, request: Request):
    _check_at()
    return db.update_liquidacion(record_id, await request.json())

@router.delete("/crm/liquidaciones/{record_id}")
def crm_liquidacion_delete(record_id: str):
    _check_at()
    return db.delete_liquidacion(record_id)


# ═══════════════════════════════════════════════════════════════════════════
# CRM — Persona única v3 (espejo de Robert)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/crm/personas/buscar")
def crm_buscar_personas(q: str = ""):
    """Autocomplete de CLIENTES_ACTIVOS por nombre, apellido, teléfono, email, documento."""
    _check_at()
    if not q or len(q.strip()) < 1:
        return {"items": []}
    return db.buscar_personas(q.strip(), limit=20)


@router.get("/crm/personas/{cliente_id}")
def crm_get_ficha_persona(cliente_id: str):
    """Ficha 360: datos base + lead origen + contratos + alquileres + inmuebles propios."""
    from fastapi import HTTPException
    _check_at()
    result = db.get_ficha_persona(cliente_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/crm/personas/agregar-rol")
async def crm_agregar_rol_persona(request: Request):
    """Agrega un rol (comprador | inquilino | propietario) a un cliente.
    Body: {"cliente_id": "recXXX", "rol": "propietario"}
    Idempotente.
    """
    from fastapi import HTTPException
    _check_at()
    body = await request.json()
    cliente_id = body.get("cliente_id")
    rol = (body.get("rol") or "").strip()
    if not cliente_id or not rol:
        raise HTTPException(400, "Faltan cliente_id o rol")
    result = db.agregar_rol_persona(str(cliente_id), rol)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/crm/contratos/alquiler")
async def crm_crear_contrato_alquiler(request: Request):
    """Crea contrato tipo alquiler + ContratosAlquiler + actualiza inmueble + rol inquilino.
    Body: {cliente_activo_id, item_id, fecha_firma, moneda, notas?,
           alquiler: {fecha_inicio, fecha_fin, monto_mensual, ...}}
    """
    from fastapi import HTTPException
    _check_at()
    campos = await request.json()
    result = db.crear_contrato_alquiler(campos)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/crm/alquileres")
def crm_get_alquileres():
    """Lista todos los ContratosAlquiler activos con datos de inmueble y cliente."""
    _check_at()
    return db.get_all_alquileres()


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


# ═══════════════════════════════════════════════════════════════════════════
# TECH PROVIDER — WABA ONBOARDING (Fase 1)
# Endpoints admin para onboarding de clientes externos de Robert via
# Meta Embedded Signup. Requieren header X-Admin-Token.
# ═══════════════════════════════════════════════════════════════════════════

LOVBOT_ADMIN_TOKEN = os.environ.get("LOVBOT_ADMIN_TOKEN", "") or os.environ.get("ADMIN_TOKEN", "")
LOVBOT_META_APP_ID = os.environ.get("LOVBOT_META_APP_ID", "") or os.environ.get("META_APP_ID", "")
LOVBOT_META_APP_SECRET = os.environ.get("LOVBOT_META_APP_SECRET", "") or os.environ.get("META_APP_SECRET", "")


def _check_admin_token(request: Request):
    """Valida X-Admin-Token. Lanza 401 si es invalido o no esta configurado."""
    from fastapi import HTTPException
    token = request.headers.get("X-Admin-Token", "")
    if not LOVBOT_ADMIN_TOKEN:
        raise HTTPException(status_code=500, detail="LOVBOT_ADMIN_TOKEN no configurado en servidor")
    if token != LOVBOT_ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="X-Admin-Token invalido")


@router.post("/admin/waba/setup-table")
def waba_setup_table(request: Request):
    """Crea la tabla waba_clients en PostgreSQL. Idempotente.
    Requiere header X-Admin-Token.
    """
    _check_admin_token(request)
    _check_pg()
    return db.setup_waba_clients_table()


@router.post("/public/waba/onboarding")
@router.post("/admin/waba/onboarding")
async def waba_onboarding(request: Request):
    """Procesa el onboarding de un cliente nuevo via Meta Embedded Signup.

    Body JSON:
        client_name     (str) nombre del cliente
        client_slug     (str) slug unico (se normaliza a lowercase-dashes)
        waba_id         (str) WABA ID devuelto por Meta
        phone_number_id (str) Phone Number ID devuelto por Meta
        code            (str) code devuelto por FB.login
        display_phone   (str, opcional) numero legible ej "+52 998 123 4567"

    Flujo:
        1. Intercambia code -> access_token permanente (GET graph.facebook.com)
        2. Suscribe la app a esa WABA (POST subscribed_apps)
        3. Guarda en PostgreSQL waba_clients
        4. Marca webhook_subscrito si (2) fue OK

    Dual-route:
        - /public/waba/onboarding  → sin token, usado por HTML Vercel (cliente real).
          La seguridad viene del code OAuth: solo Meta lo emite y el intercambio
          requiere APP_SECRET (server-side). Un atacante no puede forjarlo.
        - /admin/waba/onboarding   → requiere X-Admin-Token (uso interno/testing).
    """
    from fastapi import HTTPException
    import re as _re

    # Admin token solo se valida en la ruta /admin/...
    if request.url.path.startswith("/clientes/lovbot/inmobiliaria/admin/"):
        _check_admin_token(request)
    _check_pg()

    body = await request.json()
    client_name     = (body.get("client_name") or "").strip()
    client_slug_raw = (body.get("client_slug") or "").strip()
    waba_id         = (body.get("waba_id") or "").strip()
    phone_number_id = (body.get("phone_number_id") or "").strip()
    code            = (body.get("code") or "").strip()
    display_phone   = (body.get("display_phone") or "").strip() or None

    # Validaciones
    if not client_name:
        raise HTTPException(status_code=400, detail="Falta client_name")
    if not waba_id:
        raise HTTPException(status_code=400, detail="Falta waba_id")
    if not phone_number_id:
        raise HTTPException(status_code=400, detail="Falta phone_number_id")
    if not code:
        raise HTTPException(status_code=400, detail="Falta code (del FB.login)")
    if not LOVBOT_META_APP_ID or not LOVBOT_META_APP_SECRET:
        raise HTTPException(status_code=500,
                            detail="LOVBOT_META_APP_ID / LOVBOT_META_APP_SECRET no configurados")

    # Normalizar slug: lowercase, espacios -> guiones, sin chars especiales
    client_slug = _re.sub(r'[^a-z0-9-]', '',
                          client_slug_raw.lower().replace(" ", "-"))
    if not client_slug:
        client_slug = _re.sub(r'[^a-z0-9-]', '',
                               client_name.lower().replace(" ", "-"))

    # 0. Validar que el worker del cliente EXISTA antes de proceder.
    # Evita registrar clientes cuyos mensajes caerian al vacio por falta de worker.
    # Flow correcto: agencia clona el worker ANTES de mandar la URL al cliente.
    # Excepcion: permitir "robert-inmobiliaria" (tenant inicial/testing).
    if client_slug != "robert-inmobiliaria":
        worker_path = (
            f"/app/workers/clientes/lovbot/{client_slug.replace('-', '_')}/worker.py"
        )
        # Fallback: buscar tambien con guiones en el path (por si la carpeta usa guiones)
        worker_path_alt = f"/app/workers/clientes/lovbot/{client_slug}/worker.py"
        if not (os.path.exists(worker_path) or os.path.exists(worker_path_alt)):
            print(f"[WABA] Worker no existe para slug={client_slug}")
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El bot para '{client_name}' todavia no esta listo. "
                    "Contactanos por WhatsApp y te enviaremos un nuevo link "
                    "cuando este configurado."
                )
            )
        print(f"[WABA] Worker encontrado para slug={client_slug}")

    # 1. Intercambiar code -> access_token permanente
    print(f"[WABA] Intercambiando code -> access_token para {client_name} ({client_slug})")
    try:
        token_resp = requests.get(
            "https://graph.facebook.com/v21.0/oauth/access_token",
            params={
                "client_id": LOVBOT_META_APP_ID,
                "client_secret": LOVBOT_META_APP_SECRET,
                "code": code,
            },
            timeout=15,
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Meta rechazo el code: {token_resp.text[:300]}"
            )
        token_data = token_resp.json()
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise HTTPException(
                status_code=502,
                detail=f"Meta no devolvio access_token: {token_data}"
            )
        print(f"[WABA] access_token obtenido para {client_slug}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error llamando a Meta OAuth: {e}")

    # 2. Suscribir la app a esa WABA (webhooks del cliente)
    webhook_ok = False
    webhook_detail = ""
    try:
        sub_resp = requests.post(
            f"https://graph.facebook.com/v21.0/{waba_id}/subscribed_apps",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if sub_resp.status_code == 200:
            webhook_ok = True
            print(f"[WABA] Webhook suscrito para waba_id={waba_id}")
        else:
            webhook_detail = sub_resp.text[:300]
            print(f"[WABA] Advertencia — webhook no suscrito: {webhook_detail}")
    except Exception as e:
        webhook_detail = str(e)
        print(f"[WABA] Advertencia — excepcion al suscribir webhook: {e}")

    # 3. Guardar en PostgreSQL.
    # worker_url: cada cliente tiene su propio worker dedicado siguiendo el slug.
    # IMPORTANTE: el worker debe existir en el monorepo ANTES de mandar la URL
    # de onboarding al cliente. Flow correcto:
    #   1. Cliente paga / decide contratar
    #   2. Agencia clona workers/clientes/lovbot/{otro-cliente}/ -> .../{nuevo-slug}/
    #   3. Ajusta prompt/config, deploy a Coolify
    #   4. Recién ahí manda la URL de onboarding al cliente con ?client=NuevoSlug
    # Si hace falta corregir el worker_url despues del registro, usar el endpoint
    # POST /admin/waba/client/{phone_id}/update-worker-url
    worker_url = f"https://agentes.lovbot.ai/clientes/lovbot/{client_slug}/whatsapp"
    reg = db.registrar_waba_client(
        client_name=client_name,
        client_slug=client_slug,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        access_token=access_token,
        worker_url=worker_url,
        display_phone=display_phone,
    )
    if "error" in reg:
        raise HTTPException(status_code=500, detail=f"Error guardando en DB: {reg['error']}")

    # 4. Marcar webhook_subscrito si la suscripcion fue exitosa
    if webhook_ok:
        db.marcar_webhook_subscrito(phone_number_id)

    # 5. Provisión asíncrona Chatwoot + CRM (en background, no bloquea el response)
    # Solo se dispara si vienen los datos opcionales del brief del cliente.
    nombre_asesor = (body.get("nombre_asesor") or "").strip() or client_name
    email_asesor  = (body.get("email_asesor") or "").strip()
    if email_asesor:  # solo si tenemos email
        def _bg_provisionar():
            try:
                import sys
                sys.path.insert(0, "/app")
                from scripts.onboard_inmobiliaria import onboard as _onboard_full
                resultado = _onboard_full(
                    nombre_empresa=client_name,
                    nombre_asesor=nombre_asesor,
                    email_asesor=email_asesor,
                    telefono_whatsapp=display_phone or phone_number_id,
                    waba_id=waba_id,
                    phone_number_id=phone_number_id,
                    access_token=access_token,
                    enviar_bienvenida=True,
                )
                print(f"[WABA-PROVISION] {client_slug}: {resultado.get('resumen')}")
            except Exception as e:
                print(f"[WABA-PROVISION] Error provisionando {client_slug}: {e}")

        threading.Thread(target=_bg_provisionar, daemon=True).start()

    return {
        "status": "ok",
        "client_slug": client_slug,
        "phone_number_id": phone_number_id,
        "waba_id": waba_id,
        "worker_url": worker_url,
        "webhook_subscrito": webhook_ok,
        "webhook_detail": webhook_detail if not webhook_ok else None,
        "db_id": reg.get("id"),
        "provision_started": bool(email_asesor),
    }


@router.post("/admin/waba/register-existing")
async def waba_register_existing(request: Request):
    """Registra un cliente WABA con access_token YA obtenido (no via FB.login).
    Caso de uso: bot propio de la agencia (Robert) o clientes migrados desde
    otro proveedor que ya tienen token permanente.

    Body JSON:
        client_name, client_slug, waba_id, phone_number_id,
        access_token, worker_url (opcional), display_phone (opcional)

    Requiere header X-Admin-Token.
    """
    from fastapi import HTTPException
    import re as _re

    _check_admin_token(request)
    _check_pg()

    body = await request.json()
    client_name     = (body.get("client_name") or "").strip()
    client_slug_raw = (body.get("client_slug") or "").strip()
    waba_id         = (body.get("waba_id") or "").strip()
    phone_number_id = (body.get("phone_number_id") or "").strip()
    access_token    = (body.get("access_token") or "").strip()
    worker_url      = (body.get("worker_url") or "").strip() or None
    display_phone   = (body.get("display_phone") or "").strip() or None

    if not client_name:       raise HTTPException(400, "Falta client_name")
    if not waba_id:           raise HTTPException(400, "Falta waba_id")
    if not phone_number_id:   raise HTTPException(400, "Falta phone_number_id")
    if not access_token:      raise HTTPException(400, "Falta access_token")

    client_slug = _re.sub(r'[^a-z0-9-]', '',
                          client_slug_raw.lower().replace(" ", "-"))
    if not client_slug:
        client_slug = _re.sub(r'[^a-z0-9-]', '',
                               client_name.lower().replace(" ", "-"))

    if not worker_url:
        worker_url = f"https://agentes.lovbot.ai/clientes/lovbot/{client_slug}/whatsapp"

    reg = db.registrar_waba_client(
        client_name=client_name,
        client_slug=client_slug,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        access_token=access_token,
        worker_url=worker_url,
        display_phone=display_phone,
    )
    if "error" in reg:
        raise HTTPException(500, f"Error guardando en DB: {reg['error']}")

    db.marcar_webhook_subscrito(phone_number_id)

    return {
        "status": "ok",
        "client_slug": client_slug,
        "phone_number_id": phone_number_id,
        "waba_id": waba_id,
        "worker_url": worker_url,
        "db_id": reg.get("id"),
    }


@router.get("/admin/waba/clients")
def waba_list_clients(request: Request):
    """Lista todos los clientes WABA onboarded. Omite access_token.
    Requiere header X-Admin-Token.
    """
    _check_admin_token(request)
    _check_pg()
    clients = db.listar_waba_clients()
    for c in clients:
        c.pop("access_token", None)
    return {"total": len(clients), "clients": clients}


@router.get("/admin/waba/client/{phone_number_id}")
def waba_get_client(phone_number_id: str, request: Request):
    """Detalle de un cliente WABA por phone_number_id.
    Usado por el router Meta para obtener worker_url y routear mensajes.
    Omite access_token. Requiere header X-Admin-Token.
    """
    from fastapi import HTTPException
    _check_admin_token(request)
    _check_pg()
    client = db.obtener_waba_client_por_phone(phone_number_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"phone_number_id={phone_number_id} no encontrado"
        )
    client.pop("access_token", None)
    return client


@router.post("/admin/waba/client/{phone_number_id}/update-worker-url")
async def waba_update_worker_url(phone_number_id: str, request: Request):
    """Actualiza el worker_url de un tenant WABA ya registrado.

    Caso de uso: el cliente completo el onboarding antes de que clonaramos
    su worker dedicado, o hay que mover un cliente a otro worker.

    Body JSON: {"worker_url": "https://agentes.lovbot.ai/clientes/lovbot/X/whatsapp"}

    Requiere header X-Admin-Token.
    """
    from fastapi import HTTPException
    _check_admin_token(request)
    _check_pg()

    body = await request.json()
    nuevo_url = (body.get("worker_url") or "").strip()
    if not nuevo_url.startswith("https://"):
        raise HTTPException(400, "worker_url debe empezar con https://")

    client = db.obtener_waba_client_por_phone(phone_number_id)
    if not client:
        raise HTTPException(404, f"phone_number_id={phone_number_id} no encontrado")

    ok = db.actualizar_waba_worker_url(phone_number_id, nuevo_url)
    if not ok:
        raise HTTPException(500, "Error actualizando worker_url en DB")

    return {
        "status": "ok",
        "phone_number_id": phone_number_id,
        "client_slug": client.get("client_slug"),
        "worker_url_anterior": client.get("worker_url"),
        "worker_url_nuevo": nuevo_url,
    }


# ── ADMIN: Templates Meta (helper para no exponer access_token) ──────────────

@router.get("/admin/meta/templates")
def list_meta_templates(request: Request):
    """Lista templates Meta de la WABA propia (Robert).
    Usa META_ACCESS_TOKEN del backend (que esta vigente) sin exponerlo.
    Requiere X-Admin-Token.
    """
    from fastapi import HTTPException
    _check_admin_token(request)

    waba_id = os.getenv("LOVBOT_META_WABA_ID") or os.getenv("META_WABA_ID")
    token = os.getenv("LOVBOT_META_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
    if not waba_id or not token:
        raise HTTPException(500, "Faltan META_WABA_ID o META_ACCESS_TOKEN en env")

    try:
        r = requests.get(
            f"https://graph.facebook.com/v22.0/{waba_id}/message_templates",
            params={"fields": "name,status,language,category,components"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code != 200:
            raise HTTPException(502, f"Meta error: {r.status_code} {r.text[:300]}")
        data = r.json()
        # Resumir para no inundar response
        templates = data.get("data", [])
        summary = [
            {
                "name": t.get("name"),
                "status": t.get("status"),
                "language": t.get("language"),
                "category": t.get("category"),
            }
            for t in templates
        ]
        return {
            "total": len(summary),
            "waba_id": waba_id,
            "templates": summary,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Error consultando Meta: {e}")


@router.post("/admin/meta/test-send-template")
async def test_send_template(request: Request):
    """Envia un template a un destinatario para hacer pruebas.
    Solo para verificar que el token + WABA + templates funcionan.

    Body JSON:
      to       (str) numero destino formato Meta (ej: "12268996991")
      template (str, opcional) nombre template (default: "hello_world")
      lang     (str, opcional) codigo idioma (default: "en_US")

    Requiere X-Admin-Token.
    """
    from fastapi import HTTPException
    _check_admin_token(request)

    body = await request.json()
    to = (body.get("to") or "").strip()
    if not to:
        raise HTTPException(400, "Falta 'to'")

    template = body.get("template", "hello_world")
    lang = body.get("lang", "en_US")

    phone_id = os.getenv("LOVBOT_META_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID")
    token = os.getenv("LOVBOT_META_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
    if not phone_id or not token:
        raise HTTPException(500, "Faltan PHONE_NUMBER_ID o ACCESS_TOKEN en env")

    try:
        r = requests.post(
            f"https://graph.facebook.com/v22.0/{phone_id}/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": template,
                    "language": {"code": lang},
                },
            },
            timeout=15,
        )
        return {
            "status_code": r.status_code,
            "ok": r.status_code == 200,
            "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:300],
            "phone_number_id_used": phone_id,
            "to": to,
            "template": template,
            "lang": lang,
        }
    except Exception as e:
        raise HTTPException(502, f"Error enviando: {e}")


@router.post("/admin/meta/templates/create")
async def create_meta_template(request: Request):
    """Crea un template de WhatsApp en la WABA propia (Robert).
    Body JSON:
      name: nombre snake_case (ej: "nurturing_3_dias")
      category: "MARKETING" | "UTILITY" | "AUTHENTICATION"
      language: codigo (default "es_MX")
      body_text: texto del cuerpo, con {{1}} {{2}} para variables
      example_vars: lista opcional de valores ejemplo para las variables
    Requiere X-Admin-Token.
    """
    from fastapi import HTTPException
    _check_admin_token(request)

    body = await request.json()
    name = (body.get("name") or "").strip()
    category = (body.get("category") or "MARKETING").strip().upper()
    language = (body.get("language") or "es_MX").strip()
    body_text = (body.get("body_text") or "").strip()
    example_vars = body.get("example_vars") or []

    if not name or not body_text:
        raise HTTPException(400, "Faltan name o body_text")

    waba_id = os.getenv("LOVBOT_META_WABA_ID") or os.getenv("META_WABA_ID")
    token = os.getenv("LOVBOT_META_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
    if not waba_id or not token:
        raise HTTPException(500, "Faltan WABA_ID o ACCESS_TOKEN")

    components = [{"type": "BODY", "text": body_text}]
    if example_vars:
        components[0]["example"] = {"body_text": [example_vars]}

    payload = {"name": name, "category": category, "language": language, "components": components}

    try:
        r = requests.post(
            f"https://graph.facebook.com/v22.0/{waba_id}/message_templates",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        return {
            "status_code": r.status_code,
            "ok": r.status_code in (200, 201),
            "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:300],
            "template_name": name,
        }
    except Exception as e:
        raise HTTPException(502, f"Error creando template: {e}")


@router.delete("/admin/waba/client/{phone_number_id}")
def waba_delete_client(phone_number_id: str, request: Request):
    """Elimina un cliente WABA por phone_number_id (solo limpieza/testing).
    Requiere X-Admin-Token.
    """
    from fastapi import HTTPException
    _check_admin_token(request)
    _check_pg()
    ok = db.eliminar_waba_client(phone_number_id)
    if not ok:
        raise HTTPException(404, f"phone_number_id={phone_number_id} no encontrado o no se pudo eliminar")
    return {"status": "ok", "deleted": phone_number_id}


@router.post("/admin/onboard/test-completo")
async def test_onboard_completo(request: Request):
    """Ejecuta el orquestador onboard() completo desde el backend (donde sí están
    las env vars como LOVBOT_SMTP_PASSWORD).
    Útil para testear el flow end-to-end sin que llegue un cliente real.

    Body JSON:
      nombre_empresa, nombre_asesor, email_asesor, telefono_whatsapp,
      ciudad, zonas, moneda

    Requiere X-Admin-Token.
    """
    from fastapi import HTTPException
    _check_admin_token(request)

    body = await request.json()
    try:
        # Import diferido para no fallar si hay error en script
        import sys as _sys
        _sys.path.insert(0, "/app")
        from scripts.onboard_inmobiliaria import onboard as _onboard

        resultado = _onboard(
            nombre_empresa=body.get("nombre_empresa", "Test"),
            nombre_asesor=body.get("nombre_asesor", "Test"),
            email_asesor=body.get("email_asesor", ""),
            telefono_whatsapp=body.get("telefono_whatsapp", ""),
            ciudad=body.get("ciudad", ""),
            zonas=body.get("zonas", ""),
            moneda=body.get("moneda", "USD"),
            waba_id=body.get("waba_id", ""),
            phone_number_id=body.get("phone_number_id", ""),
            access_token=body.get("access_token", ""),
            enviar_bienvenida=body.get("enviar_bienvenida", False),
        )
        return resultado
    except Exception as e:
        raise HTTPException(500, f"Error orquestando: {e}")
