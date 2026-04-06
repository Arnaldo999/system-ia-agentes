"""
Worker — Robert Bazán / Lovbot — Demo Inmobiliaria
===================================================
Copia del demo inmobiliaria adaptada para Meta Graph API (en lugar de YCloud).
Canal: WhatsApp Business API vía Meta Tech Provider.

Variables de entorno (cargadas en Coolify Robert):
  META_ACCESS_TOKEN     Token permanente del System User
  META_PHONE_NUMBER_ID  ID del número de WhatsApp
  GEMINI_API_KEY        Compartida
  AIRTABLE_API_KEY      Compartida (opcional)

  INMO_DEMO_NOMBRE      Nombre empresa (def: "Lovbot — Demo Inmobiliaria")
  INMO_DEMO_CIUDAD      Ciudad (def: "México")
  INMO_DEMO_ASESOR      Nombre asesor (def: "Roberto")
  INMO_DEMO_NUMERO_ASESOR  Número asesor para notificaciones
"""

import os
import re
import json
import requests
import threading
from google import genai
from fastapi import APIRouter, Request

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_PHONE_ID     = os.environ.get("META_PHONE_NUMBER_ID", "")
NUMERO_ASESOR     = os.environ.get("INMO_DEMO_NUMERO_ASESOR", os.environ.get("NUMERO_ASESOR_ROBERT", ""))

NOMBRE_EMPRESA = os.environ.get("INMO_DEMO_NOMBRE",  "Lovbot — Demo Inmobiliaria")
CIUDAD         = os.environ.get("INMO_DEMO_CIUDAD",  "México")
NOMBRE_ASESOR  = os.environ.get("INMO_DEMO_ASESOR",  "Roberto")
MONEDA         = os.environ.get("INMO_DEMO_MONEDA",  "USD")

_zonas_raw = os.environ.get("INMO_DEMO_ZONAS", "Zona Norte,Zona Sur,Zona Centro")
ZONAS_LIST = [z.strip() for z in _zonas_raw.split(",") if z.strip()]

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(prefix="/clientes/lovbot/inmobiliaria", tags=["Robert — Inmobiliaria"])

# ─── SESIONES EN MEMORIA ──────────────────────────────────────────────────────
SESIONES: dict[str, dict] = {}

# ─── META GRAPH API — ENVÍO ───────────────────────────────────────────────────
def _enviar_texto(telefono: str, mensaje: str) -> bool:
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
            print(f"[ROBERT-META] Error {r.status_code}: {r.text[:200]}")
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[ROBERT-META] Excepción: {e}")
        return False


def _notificar_asesor(telefono_lead: str, nombre: str, score: str, nota: str) -> None:
    if not NUMERO_ASESOR:
        return
    msg = (
        f"🔔 *Nuevo Lead — {NOMBRE_EMPRESA}*\n\n"
        f"👤 *Nombre:* {nombre}\n"
        f"📱 *WhatsApp:* +{re.sub(r'[^0-9]', '', telefono_lead)}\n"
        f"📊 *Score:* {score.upper()}\n"
        f"📝 *Nota:* {nota}"
    )
    _enviar_texto(NUMERO_ASESOR, msg)


# ─── GEMINI ───────────────────────────────────────────────────────────────────
def _gemini(prompt: str) -> str:
    if not _gemini_client:
        return ""
    try:
        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite", contents=prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"[ROBERT-GEMINI] Error: {e}")
        return ""


def _calificar(sesion: dict) -> dict:
    prompt = f"""Sos un analista comercial inmobiliario de {NOMBRE_EMPRESA} en {CIUDAD}.
Analizá las respuestas y devolvé SOLO un JSON:
{{
  "score": "caliente|tibio|frio",
  "tipo": "casa|departamento|terreno|local|oficina|null",
  "zona": "{"|".join(ZONAS_LIST)}|null",
  "presupuesto_detectado": "alto|medio|bajo|sin_info",
  "derivar_sitio_web": true|false,
  "nota_para_asesor": "texto breve"
}}

Reglas:
- caliente: presupuesto claro + compra en menos de 6 meses
- tibio: interesado pero sin urgencia
- frio: solo curiosidad → derivar_sitio_web: true
- Si urgencia es "próximo año" o "explorando" → frio, derivar_sitio_web: true

Respuestas del lead:
- Objetivo: "{sesion.get('resp_objetivo','')}"
- Zona: "{sesion.get('resp_zona','')}"
- Presupuesto: "{sesion.get('resp_presupuesto','')}"
- Urgencia: "{sesion.get('resp_urgencia','')}"

Devolvé SOLO el JSON."""
    try:
        texto = _gemini(prompt)
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return json.loads(texto.strip())
    except Exception:
        return {"score": "tibio", "tipo": None, "zona": None,
                "presupuesto_detectado": "sin_info", "derivar_sitio_web": False,
                "nota_para_asesor": "Error en calificación"}


def _pregunta_dinamica(paso: str, nombre: str) -> str:
    nombre_txt = f" {nombre.split()[0]}" if nombre else ""
    prompts = {
        "objetivo": f"Generá una pregunta cálida y breve para preguntarle{nombre_txt} qué tipo de propiedad busca en {CIUDAD} (casa, depto, terreno, local, etc.) y para qué la quiere (vivir, invertir, negocio). Máx 4 líneas. Español neutro.",
        "zona": f"Generá una pregunta para preguntarle{nombre_txt} en qué zona de {CIUDAD} busca. Mostrá las opciones numeradas: {', '.join(f'{i+1}. {z}' for i,z in enumerate(ZONAS_LIST))}. Máx 6 líneas.",
        "presupuesto": f"Generá una pregunta amable para preguntarle{nombre_txt} su rango de presupuesto en {MONEDA}. Opciones: 1. Menos de 50K, 2. 50K-100K, 3. 100K-200K, 4. Más de 200K, 5. Prefiero hablarlo. Máx 6 líneas.",
        "urgencia": f"Generá una pregunta para preguntarle{nombre_txt} cuándo planea concretar. Opciones: 1. Lo antes posible (1-3 meses), 2. En los próximos 6 meses, 3. En el próximo año, 4. Estoy explorando. Máx 5 líneas.",
    }
    respuesta = _gemini(prompts[paso])
    if respuesta:
        return respuesta
    # Fallbacks
    fallbacks = {
        "objetivo": f"¿Qué tipo de propiedad está buscando{nombre_txt}? 🏠\n\nPuede escribirme libremente.",
        "zona": f"¿En qué zona de {CIUDAD} le interesa buscar{nombre_txt}? 📍\n\n" + "\n".join(f"{i+1}️⃣ {z}" for i,z in enumerate(ZONAS_LIST)),
        "presupuesto": f"¿Con qué presupuesto cuenta{nombre_txt}? 💰\n\n1️⃣ Menos de 50K {MONEDA}\n2️⃣ 50K-100K\n3️⃣ 100K-200K\n4️⃣ Más de 200K\n5️⃣ Prefiero hablarlo",
        "urgencia": f"¿En qué tiempo piensa concretar{nombre_txt}? 🗓️\n\n1️⃣ Lo antes posible\n2️⃣ En 6 meses\n3️⃣ En el próximo año\n4️⃣ Explorando opciones",
    }
    return fallbacks[paso]


# ─── FLUJO PRINCIPAL ──────────────────────────────────────────────────────────
MSG_BIENVENIDA = (
    "¡Hola! 👋 Soy el asistente virtual de *{empresa}*.\n\n"
    "Estoy aquí para ayudarle a encontrar la propiedad ideal en {ciudad}. "
    "¿Me permite conocer su nombre para poder asistirle mejor? 😊"
)

MSG_SITIO_WEB = (
    "¡Muchas gracias por su interés, {nombre}! 🙏\n\n"
    "Entendemos que aún está explorando opciones — eso está perfecto. "
    "Le invitamos a visitar nuestra web donde encontrará todas nuestras "
    "propiedades disponibles y opciones de financiamiento.\n\n"
    "Cuando esté listo para dar el siguiente paso, escríbanos y con gusto "
    "lo asesoramos personalmente. ¡Estamos para ayudarle! 🏡"
)

MSG_ASESOR = (
    "¡Excelente, {nombre}! 🎉\n\n"
    "Con base en lo que me indicó, nuestro asesor *{asesor}* se pondrá en contacto "
    "con usted a la brevedad para mostrarle las mejores opciones disponibles.\n\n"
    "¡Gracias por confiar en *{empresa}*! 🏠"
)


def _procesar(telefono: str, texto: str) -> None:
    texto = texto.strip()
    sesion = SESIONES.get(telefono, {})
    step = sesion.get("step", "inicio")
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""

    # ── INICIO ────────────────────────────────────────────────────────────────
    if step == "inicio":
        SESIONES[telefono] = {"step": "nombre"}
        _enviar_texto(telefono, MSG_BIENVENIDA.format(
            empresa=NOMBRE_EMPRESA, ciudad=CIUDAD))
        return

    # ── NOMBRE ────────────────────────────────────────────────────────────────
    if step == "nombre":
        nombre = texto.title()
        SESIONES[telefono] = {**sesion, "step": "objetivo", "nombre": nombre}
        pregunta = _pregunta_dinamica("objetivo", nombre)
        _enviar_texto(telefono, pregunta)
        return

    # ── OBJETIVO ──────────────────────────────────────────────────────────────
    if step == "objetivo":
        SESIONES[telefono] = {**sesion, "step": "zona", "resp_objetivo": texto}
        pregunta = _pregunta_dinamica("zona", nombre_corto)
        _enviar_texto(telefono, pregunta)
        return

    # ── ZONA ──────────────────────────────────────────────────────────────────
    if step == "zona":
        SESIONES[telefono] = {**sesion, "step": "presupuesto", "resp_zona": texto}
        pregunta = _pregunta_dinamica("presupuesto", nombre_corto)
        _enviar_texto(telefono, pregunta)
        return

    # ── PRESUPUESTO ───────────────────────────────────────────────────────────
    if step == "presupuesto":
        SESIONES[telefono] = {**sesion, "step": "urgencia", "resp_presupuesto": texto}
        pregunta = _pregunta_dinamica("urgencia", nombre_corto)
        _enviar_texto(telefono, pregunta)
        return

    # ── URGENCIA → CALIFICAR ──────────────────────────────────────────────────
    if step == "urgencia":
        sesion_actualizada = {**sesion, "step": "calificado", "resp_urgencia": texto}
        SESIONES[telefono] = sesion_actualizada
        calificacion = _calificar(sesion_actualizada)
        score = calificacion.get("score", "tibio")
        derivar = calificacion.get("derivar_sitio_web", False)
        nota = calificacion.get("nota_para_asesor", "")

        # Normalizar nulls de Gemini
        zona = calificacion.get("zona")
        if zona in (None, "null", ""):
            zona = None

        if derivar or score == "frio":
            _enviar_texto(telefono, MSG_SITIO_WEB.format(nombre=nombre_corto or nombre))
            threading.Thread(
                target=_notificar_asesor,
                args=(telefono, nombre, score, nota), daemon=True
            ).start()
            return

        # Lead caliente o tibio → conectar con asesor
        _enviar_texto(telefono, MSG_ASESOR.format(
            nombre=nombre_corto or nombre,
            asesor=NOMBRE_ASESOR,
            empresa=NOMBRE_EMPRESA,
        ))
        threading.Thread(
            target=_notificar_asesor,
            args=(telefono, nombre, score, nota), daemon=True
        ).start()
        return

    # ── FALLBACK (mensaje fuera de flujo) ─────────────────────────────────────
    _enviar_texto(telefono,
        f"Disculpe, no entendí su mensaje. ¿Desea iniciar una nueva consulta? "
        f"Escriba *hola* para comenzar. 😊")
    SESIONES.pop(telefono, None)


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
