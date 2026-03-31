"""
Worker DEMO — Agente Precalificador Inmobiliario
=================================================
Demo universal para cualquier país de LATAM.
Gemini detecta sub-nicho automáticamente y precalifica leads.

Sub-nichos soportados:
  A — Desarrolladora / proyecto inmobiliario
  B — Inmobiliaria mediana (agencia con equipo)
  C — Agente independiente

Flujo principal:
  Mensaje entra → Gemini clasifica intención + sub-nicho
  → Precalifica con preguntas clave (filtro de curiosos)
  → Score: CALIENTE / TIBIO / FRIO
  → CALIENTE → agenda cita Cal.com
  → TIBIO    → secuencia remarketing (flag para n8n)
  → FRIO     → cierre educado

Variables de entorno requeridas (prefijo INMO_DEMO_):
  INMO_DEMO_NOMBRE          Nombre de la empresa/proyecto
  INMO_DEMO_CIUDAD          Ciudad o región
  INMO_DEMO_ASESOR          Nombre del asesor senior
  INMO_DEMO_NUMERO_BOT      Número WhatsApp del bot
  INMO_DEMO_NUMERO_ASESOR   Número WhatsApp del asesor
  INMO_DEMO_YCLOUD_KEY      API Key YCloud (o usa la general)
  INMO_DEMO_AIRTABLE_BASE   Base ID Airtable
  INMO_DEMO_TABLE_PROPS     ID tabla propiedades
  INMO_DEMO_TABLE_CLIENTES  ID tabla clientes/leads
  INMO_DEMO_ZONAS           Zonas separadas por coma
  INMO_DEMO_MONEDA          Moneda principal (def: USD)
  INMO_DEMO_CAL_API_KEY     API Key Cal.com (opcional — habilita agendamiento)
  INMO_DEMO_CAL_EVENT_ID    Event Type ID Cal.com (opcional)

  GEMINI_API_KEY            Compartida
  AIRTABLE_TOKEN            Compartido
"""

import os
import re
import json
import requests
from google import genai
from fastapi import APIRouter, Request

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
AIRTABLE_TOKEN  = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
YCLOUD_API_KEY  = os.environ.get("INMO_DEMO_YCLOUD_KEY", "") or os.environ.get("YCLOUD_API_KEY", "")

NOMBRE_EMPRESA  = os.environ.get("INMO_DEMO_NOMBRE",       "System IA — Demo Inmobiliaria")
CIUDAD          = os.environ.get("INMO_DEMO_CIUDAD",        "tu ciudad")
NOMBRE_ASESOR   = os.environ.get("INMO_DEMO_ASESOR",        "el asesor")
NUMERO_BOT      = os.environ.get("INMO_DEMO_NUMERO_BOT",    "")
NUMERO_ASESOR   = os.environ.get("INMO_DEMO_NUMERO_ASESOR", "")
MONEDA          = os.environ.get("INMO_DEMO_MONEDA",        "USD")

AIRTABLE_BASE_ID        = os.environ.get("INMO_DEMO_AIRTABLE_BASE",   "")
AIRTABLE_TABLE_PROPS    = os.environ.get("INMO_DEMO_TABLE_PROPS",      "")
AIRTABLE_TABLE_CLIENTES = os.environ.get("INMO_DEMO_TABLE_CLIENTES",   "")

CAL_API_KEY   = os.environ.get("INMO_DEMO_CAL_API_KEY",  "")
CAL_EVENT_ID  = os.environ.get("INMO_DEMO_CAL_EVENT_ID", "")

_zonas_raw = os.environ.get("INMO_DEMO_ZONAS", "Zona Norte,Zona Sur,Zona Centro")
ZONAS_LIST = [z.strip() for z in _zonas_raw.split(",") if z.strip()]

EMPRESA = {
    "nombre":   NOMBRE_EMPRESA,
    "ciudad":   CIUDAD,
    "asesor":   NOMBRE_ASESOR,
    "whatsapp": ("+" + re.sub(r'\D', '', NUMERO_ASESOR)) if NUMERO_ASESOR and not NUMERO_ASESOR.startswith("+") else NUMERO_ASESOR,
}

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(prefix="/demos/inmobiliaria", tags=["Demo — Inmobiliaria"])

# ─── SESIONES (in-memory) ─────────────────────────────────────────────────────
# Estructura de sesión:
# {
#   "step": str,           — bienvenida | precalificacion | propiedades | lista | ficha | agendamiento
#   "subniche": str,       — desarrolladora | inmobiliaria | agente | comprador | None
#   "score": str,          — caliente | tibio | frio | None
#   "operacion": str,      — venta | alquiler
#   "tipo": str,
#   "zona": str,
#   "props": list,
#   "nombre": str,
#   "preguntas_hechas": int,
#   "respuestas_precal": list,
# }
SESIONES: dict[str, dict] = {}

# ─── CONSTANTES SUB-NICHO ─────────────────────────────────────────────────────
SUBNICHE_LABELS = {
    "desarrolladora": "Desarrolladora Inmobiliaria",
    "inmobiliaria":   "Inmobiliaria / Agencia",
    "agente":         "Agente Independiente",
    "comprador":      "Comprador / Inquilino",
}

# Preguntas de precalificación por sub-nicho
PREGUNTAS_PRECAL = {
    "desarrolladora": [
        "¿Cuántas unidades tiene tu proyecto? (ej: 20 casas, 50 departamentos)",
        "¿Ya tenés leads interesados o recién vas a lanzar el proyecto?",
        "¿Cuál es el ticket promedio de tus unidades?",
    ],
    "inmobiliaria": [
        "¿Cuántos asesores tiene tu equipo de ventas?",
        "¿Cuántos leads o consultas recibís por mes aproximadamente?",
        "¿Actualmente usás algún CRM o sistema para gestionar tus leads?",
    ],
    "agente": [
        "¿Con qué portales o canales conseguís tus prospectos? (ej: Lamudi, Vivaanuncios, Instagram)",
        "¿Cuántos prospectos activos estás manejando ahora mismo?",
        "¿El mayor problema es conseguir prospectos o dar seguimiento a los que ya tenés?",
    ],
    "comprador": [],  # No precalifica — va directo a propiedades
}

# ─── AIRTABLE ─────────────────────────────────────────────────────────────────
AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def _at_registrar_lead(telefono: str, nombre: str, subniche: str = "", score: str = "",
                       operacion: str = "", tipo: str = "", notas: str = "") -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_CLIENTES:
        return
    from datetime import date
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
    buscar = requests.get(url, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []

    campos = {"Telefono": telefono, "Llego_WhatsApp": True}
    if nombre:
        partes = nombre.strip().split(" ", 1)
        campos["Nombre"] = partes[0]
        if len(partes) > 1:
            campos["Apellido"] = partes[1]
    if subniche:
        campos["Tipo_Cliente"] = SUBNICHE_LABELS.get(subniche, subniche)
    if score:
        campos["Score_Bot"] = score.upper()
        if score == "caliente":
            campos["Estado"] = "calificado"
        elif score == "tibio":
            campos["Estado"] = "seguimiento"
        else:
            campos["Estado"] = "frio"
    if operacion:
        campos["Operacion"] = operacion.capitalize()
    if tipo:
        campos["Tipo_Propiedad"] = tipo
    if notas:
        campos["Notas_Bot"] = notas

    if records:
        rec_id = records[0]["id"]
        requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS, json={"fields": campos}, timeout=8)
    else:
        campos["Fecha_WhatsApp"] = date.today().isoformat()
        if "Estado" not in campos:
            campos["Estado"] = "nuevo"
        requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)


def _at_buscar_propiedades(tipo: str = None, operacion: str = None, zona: str = None) -> list[dict]:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return []
    filtros = ["OR({Disponible}='✅ Disponible',{Disponible}='⏳ Reservado')"]
    if tipo:
        filtros.append(f"LOWER({{Tipo}})='{tipo.lower()}'")
    if operacion:
        filtros.append(f"LOWER({{Operacion}})='{operacion.lower()}'")
    if zona and zona != "otra":
        filtros.append(f"{{Zona}}='{zona}'")
    formula = "AND(" + ",".join(filtros) + ")" if len(filtros) > 1 else filtros[0]
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}"
    try:
        r = requests.get(url, headers=AT_HEADERS,
            params={"filterByFormula": formula, "maxRecords": 5,
                    "sort[0][field]": "Precio", "sort[0][direction]": "asc"}, timeout=8)
        return [rec["fields"] for rec in r.json().get("records", [])]
    except Exception as e:
        print(f"[DEMO-AT] Error: {e}")
        return []


# ─── YCLOUD ───────────────────────────────────────────────────────────────────
def _norm_tel(tel: str) -> str:
    return "+" + re.sub(r'\D', '', tel)


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not YCLOUD_API_KEY or not NUMERO_BOT:
        print(f"[DEMO] Sin key/número configurado. Mensaje:\n{mensaje}")
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            json={"from": NUMERO_BOT, "to": telefono, "type": "text", "text": {"body": mensaje}},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[DEMO-YCLOUD] Error: {e}")
        return False


def _enviar_imagen(telefono: str, url_img: str, caption: str = "") -> bool:
    if not YCLOUD_API_KEY or not NUMERO_BOT or not url_img:
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            json={"from": NUMERO_BOT, "to": telefono, "type": "image",
                  "image": {"link": url_img, "caption": caption}},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[DEMO-YCLOUD] Error imagen: {e}")
        return False


# ─── CAL.COM ──────────────────────────────────────────────────────────────────
def _cal_disponible() -> bool:
    return bool(CAL_API_KEY and CAL_EVENT_ID)


def _cal_obtener_slots(dias: int = 7) -> list[dict]:
    """Retorna slots disponibles en los próximos N días."""
    if not _cal_disponible():
        return []
    from datetime import datetime, timedelta
    start = datetime.utcnow().strftime("%Y-%m-%d")
    end   = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"https://api.cal.com/v1/slots",
            params={"apiKey": CAL_API_KEY, "eventTypeId": CAL_EVENT_ID,
                    "startTime": start, "endTime": end},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            slots_raw = data.get("slots", {})
            # Aplanar: {fecha: [{time: ...}]} → lista de strings legibles
            slots = []
            for fecha, lista in slots_raw.items():
                for slot in lista[:2]:  # máx 2 por día para no saturar WhatsApp
                    dt = slot.get("time", "")
                    if dt:
                        slots.append({"fecha": fecha, "time": dt})
            return slots[:6]  # máx 6 opciones totales
    except Exception as e:
        print(f"[DEMO-CAL] Error slots: {e}")
    return []


def _cal_crear_reserva(nombre: str, email: str, telefono: str, slot_time: str, notas: str = "") -> dict:
    """Crea una reserva en Cal.com."""
    if not _cal_disponible():
        return {"ok": False, "error": "Cal.com no configurado"}
    try:
        r = requests.post(
            "https://api.cal.com/v1/bookings",
            params={"apiKey": CAL_API_KEY},
            json={
                "eventTypeId": int(CAL_EVENT_ID),
                "start": slot_time,
                "responses": {
                    "name": nombre,
                    "email": email or (re.sub(r'\D', '', telefono) + "@demo.com"),
                    "phone": telefono,
                },
                "metadata": {"fuente": "WhatsApp Bot", "notas": notas},
                "timeZone": "America/Mexico_City",
                "language": "es",
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {"ok": True, "uid": data.get("uid", ""), "start": data.get("startTime", slot_time)}
        return {"ok": False, "error": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── GEMINI — CLASIFICADOR PRINCIPAL ──────────────────────────────────────────
def _gemini_clasificar(texto: str, sesion: dict) -> dict:
    """
    Clasifica intención y extrae datos del mensaje.
    Retorna dict con:
      intencion: bienvenida | precalificacion | propiedades | asesor | agendar | respuesta_libre
      subniche:  desarrolladora | inmobiliaria | agente | comprador | None (mantener actual)
      operacion: venta | alquiler | None
      tipo:      casa | departamento | terreno | None
      zona:      str | None
      respuesta: str (mensaje a enviar al usuario)
    """
    if not _gemini_client:
        return {"intencion": "respuesta_libre", "subniche": None, "operacion": None,
                "tipo": None, "zona": None, "respuesta": ""}

    subniche_actual = sesion.get("subniche", "")
    step_actual     = sesion.get("step", "bienvenida")
    nombre          = sesion.get("nombre", "")
    historial       = sesion.get("historial", [])[-6:]  # últimas 6 interacciones

    historial_txt = "\n".join([f"  {h['rol']}: {h['msg']}" for h in historial]) if historial else "  (primera interacción)"

    prompt = f"""Sos el cerebro de un agente inmobiliario IA para {EMPRESA['nombre']} en {EMPRESA['ciudad']}.
Tu trabajo es analizar el mensaje del cliente y devolver un JSON con la clasificación.

CONTEXTO ACTUAL:
- Sub-nicho detectado: {subniche_actual or 'ninguno aún'}
- Paso actual: {step_actual}
- Nombre del cliente: {nombre or 'desconocido'}
- Historial reciente:
{historial_txt}

NUEVO MENSAJE DEL CLIENTE: "{texto}"

INSTRUCCIONES:
1. Detectá el sub-nicho si no está definido:
   - "desarrolladora": tiene un proyecto inmobiliario para vender (desarrollador, proyecto, unidades, preventa)
   - "inmobiliaria": agencia o inmobiliaria con cartera y equipo
   - "agente": asesor o agente independiente
   - "comprador": quiere comprar, alquilar, busca propiedad para vivir o invertir
   Si ya hay sub-nicho definido, devolvé null (mantener).

2. Detectá la intención:
   - "saludo": primeros mensajes, hola, inicio
   - "precalificacion": responde a una pregunta de precalificación
   - "ver_propiedades": quiere ver propiedades del catálogo
   - "agendar": quiere agendar una cita o visita
   - "asesor": pide hablar con un humano
   - "respuesta_libre": consulta general, pregunta, otro

3. Extraé si mencionó:
   - operacion: "venta" o "alquiler" (null si no menciona)
   - tipo: "casa", "departamento", "terreno" (null si no menciona)
   - zona: nombre de zona si menciona alguna (null si no)

4. Generá una respuesta natural, breve, en español LATAM (no Spain).
   - Tono: profesional pero cercano, como un asesor experto
   - Si es saludo → presentarte y preguntar en qué podés ayudar
   - Si detectás sub-nicho por primera vez → confirmarlo y arrancar precalificación
   - Si es comprador → ir directo a qué busca
   - Máximo 3 líneas de texto libre, podés usar emojis con moderación

Respondé SOLO con JSON válido, sin markdown, sin explicaciones:
{{
  "intencion": "...",
  "subniche": "...",
  "operacion": "...",
  "tipo": "...",
  "zona": "...",
  "respuesta": "..."
}}
Donde los campos sin valor van como null (no string vacío)."""

    try:
        result = _gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        raw = result.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[DEMO-GEMINI-CLAS] Error: {e}")
        return {"intencion": "respuesta_libre", "subniche": None, "operacion": None,
                "tipo": None, "zona": None, "respuesta": ""}


def _gemini_score_precal(subniche: str, respuestas: list[str]) -> dict:
    """
    Evalúa las respuestas de precalificación y devuelve score + razonamiento.
    Retorna: {score: caliente|tibio|frio, razon: str, respuesta: str}
    """
    if not _gemini_client or not respuestas:
        return {"score": "tibio", "razon": "Sin Gemini", "respuesta": ""}

    preguntas = PREGUNTAS_PRECAL.get(subniche, [])
    pares = []
    for i, r in enumerate(respuestas):
        pregunta = preguntas[i] if i < len(preguntas) else f"Pregunta {i+1}"
        pares.append(f"  P: {pregunta}\n  R: {r}")
    pares_txt = "\n".join(pares)

    prompt = f"""Sos un experto en ventas inmobiliarias B2B evaluando la calidad de un lead.

Sub-nicho: {SUBNICHE_LABELS.get(subniche, subniche)}
Empresa: {EMPRESA['nombre']}

Respuestas de precalificación:
{pares_txt}

Evaluá el lead y devolvé JSON:
{{
  "score": "caliente" | "tibio" | "frio",
  "razon": "explicación breve en 1 línea",
  "respuesta": "mensaje para enviar al lead ahora (máx 3 líneas, tono consultivo)"
}}

Criterios:
- CALIENTE: tiene necesidad real, urgencia, presupuesto o volumen claro → ofrecé agendar cita YA
- TIBIO: interés real pero no urgente, falta info → nutrir con seguimiento
- FRIO: sin presupuesto, sin proyecto, curiosidad sin intención real → cierre educado

Respondé SOLO JSON válido sin markdown."""

    try:
        result = _gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        raw = result.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[DEMO-GEMINI-SCORE] Error: {e}")
        return {"score": "tibio", "razon": str(e), "respuesta": ""}


def _gemini_libre(texto: str, sesion: dict) -> str:
    """Respuesta libre para preguntas generales."""
    if not _gemini_client:
        return f"Para más información hablá con {EMPRESA['asesor']} al {EMPRESA['whatsapp']} 🏠"
    subniche = sesion.get("subniche", "")
    contexto_subniche = f"El cliente es: {SUBNICHE_LABELS.get(subniche, 'visitante')}." if subniche else ""
    try:
        result = _gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=(f"Sos el asistente de {EMPRESA['nombre']} en {EMPRESA['ciudad']}. "
                      f"{contexto_subniche} Respondé en español LATAM, breve y profesional. "
                      f"Solo temas inmobiliarios. Pregunta: {texto}")
        )
        return result.text.strip()
    except Exception as e:
        print(f"[DEMO-GEMINI-LIBRE] Error: {e}")
        return f"Para más info escribile a {EMPRESA['asesor']} al {EMPRESA['whatsapp']} 🏠"


# ─── FORMATEO DE PROPIEDADES ───────────────────────────────────────────────────
def _lista_titulos(props: list[dict], label: str) -> str:
    lineas = [f"✨ *{label.upper()}*\n"]
    for i, p in enumerate(props, 1):
        precio = p.get("Precio", 0)
        moneda = p.get("Moneda", MONEDA)
        precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar"
        tag = " ⏳" if "Reservado" in str(p.get("Disponible", "")) else ""
        lineas.append(f"*{i}.* {p.get('Titulo', 'Propiedad')} — {precio_str}{tag}")
    lineas.append("\nRespondé con el *número* para ver la ficha.")
    lineas.append("*0* volver | *asesor* hablar con un humano")
    return "\n".join(lineas)


def _ficha_propiedad(p: dict) -> str:
    precio = p.get("Precio", 0)
    moneda = p.get("Moneda", MONEDA)
    precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar precio"
    es_reservado = "Reservado" in str(p.get("Disponible", ""))
    lineas = [f"🏠 *{p.get('Titulo', 'Propiedad')}*"]
    if es_reservado:
        lineas.append("⏳ *RESERVADO* — podés anotarte por si se libera\n")
    else:
        lineas.append("")
    if p.get("Descripcion"):
        lineas.append(f"{p['Descripcion']}\n")
    lineas.append(f"💰 *Precio:* {precio_str}")
    if p.get("Dormitorios"):
        lineas.append(f"🛏 *Dormitorios:* {p['Dormitorios']}")
    if p.get("Metros_Cubiertos"):
        lineas.append(f"📐 *Sup. cubierta:* {p['Metros_Cubiertos']}m²")
    if p.get("Metros_Terreno"):
        lineas.append(f"🌿 *Terreno:* {p['Metros_Terreno']}m²")
    if p.get("Zona"):
        lineas.append(f"📍 *Zona:* {p['Zona']}")
    if p.get("Google_Maps_URL"):
        lineas.append(f"\n🗺 *Ver en Maps:* {p['Google_Maps_URL']}")
    lineas.append(f"\n¿Te interesa?\n*1* agendar visita | *2* hablar con {EMPRESA['asesor']} | *0* volver")
    return "\n".join(lineas)


def _enviar_ficha(telefono: str, p: dict) -> None:
    img_field = p.get("Imagen_URL", "")
    img = ""
    if isinstance(img_field, list) and img_field:
        img = img_field[0].get("url", "")
    elif isinstance(img_field, str):
        img = img_field
    if img:
        _enviar_imagen(telefono, img, caption=p.get("Titulo", ""))
    _enviar_texto(telefono, _ficha_propiedad(p))


def _mostrar_propiedades(telefono: str, sesion: dict) -> None:
    operacion = sesion.get("operacion", "venta")
    tipo      = sesion.get("tipo")
    zona      = sesion.get("zona")
    props     = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona)
    op_label  = "en Venta" if operacion == "venta" else "en Alquiler"
    if not props:
        _enviar_texto(telefono,
            f"En este momento no tenemos propiedades disponibles con esos criterios. 😔\n\n"
            f"¿Querés que te avise cuando tengamos? Escribí *asesor* para hablar con {EMPRESA['asesor']}.")
        return
    SESIONES[telefono] = {**sesion, "step": "lista", "props": props}
    label = f"{tipo.capitalize() if tipo else 'Propiedades'} {op_label}"
    if zona:
        label += f" — {zona}"
    _enviar_texto(telefono, _lista_titulos(props, label))


# ─── AGENDAMIENTO CAL.COM ──────────────────────────────────────────────────────
def _iniciar_agendamiento(telefono: str, sesion: dict) -> None:
    if not _cal_disponible():
        # Cal.com no configurado → derivar a asesor
        _enviar_texto(telefono,
            f"¡Perfecto! Te conectamos con {EMPRESA['asesor']} para coordinar la visita. 📅\n\n"
            f"Escribile directamente al {EMPRESA['whatsapp']} o aguardá que te contacte pronto. 🏠")
        SESIONES[telefono] = {**sesion, "step": "bienvenida"}
        return

    slots = _cal_obtener_slots(dias=7)
    if not slots:
        _enviar_texto(telefono,
            f"En este momento no hay turnos disponibles en el calendario. 😔\n"
            f"Escribile a {EMPRESA['asesor']} al {EMPRESA['whatsapp']} para coordinar. 📱")
        return

    lineas = ["📅 *Turnos disponibles esta semana:*\n"]
    for i, s in enumerate(slots, 1):
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(s["time"].replace("Z", "+00:00"))
            legible = dt.strftime("%a %d/%m — %H:%M hs")
        except Exception:
            legible = s["time"]
        lineas.append(f"*{i}.* {legible}")
    lineas.append("\nRespondé con el *número* del turno que te queda mejor.")
    lineas.append("*0* para volver")

    SESIONES[telefono] = {**sesion, "step": "agendamiento", "slots": slots}
    _enviar_texto(telefono, "\n".join(lineas))


def _confirmar_reserva(telefono: str, sesion: dict, slot_idx: int) -> None:
    slots  = sesion.get("slots", [])
    nombre = sesion.get("nombre", "Cliente")
    if slot_idx < 0 or slot_idx >= len(slots):
        _enviar_texto(telefono, f"Elegí un número del 1 al {len(slots)}.")
        return
    slot  = slots[slot_idx]
    result = _cal_crear_reserva(nombre=nombre, email="", telefono=telefono,
                                 slot_time=slot["time"],
                                 notas=f"Agendado por WhatsApp Bot — {EMPRESA['nombre']}")
    if result.get("ok"):
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(slot["time"].replace("Z", "+00:00"))
            legible = dt.strftime("%A %d de %B a las %H:%M hs")
        except Exception:
            legible = slot["time"]
        _at_registrar_lead(telefono, nombre, subniche=sesion.get("subniche", ""),
                           score="caliente", notas=f"Cita agendada: {legible}")
        _enviar_texto(telefono,
            f"✅ *¡Cita confirmada!*\n\n"
            f"📅 {legible}\n"
            f"📍 {EMPRESA['ciudad']}\n\n"
            f"Vas a recibir un recordatorio. Si necesitás cambiarla escribí *asesor*. 🏠")
        SESIONES[telefono] = {**sesion, "step": "bienvenida", "score": "caliente"}
    else:
        _enviar_texto(telefono,
            f"Hubo un problema al confirmar la cita. 😔\n"
            f"Escribile directamente a {EMPRESA['asesor']} al {EMPRESA['whatsapp']}.")


# ─── FLUJO PRECALIFICACIÓN ─────────────────────────────────────────────────────
def _siguiente_pregunta_precal(telefono: str, sesion: dict) -> None:
    subniche  = sesion.get("subniche", "comprador")
    preguntas = PREGUNTAS_PRECAL.get(subniche, [])
    hechas    = sesion.get("preguntas_hechas", 0)

    if hechas >= len(preguntas):
        # Todas las preguntas hechas → evaluar score
        respuestas = sesion.get("respuestas_precal", [])
        eval_result = _gemini_score_precal(subniche, respuestas)
        score = eval_result.get("score", "tibio")
        respuesta_gemini = eval_result.get("respuesta", "")

        SESIONES[telefono] = {**sesion, "step": "post_precal", "score": score}
        _at_registrar_lead(telefono, sesion.get("nombre", ""), subniche=subniche,
                           score=score, notas=f"Score: {score} | {eval_result.get('razon', '')}")

        if respuesta_gemini:
            _enviar_texto(telefono, respuesta_gemini)

        if score == "caliente":
            _enviar_texto(telefono,
                f"\n¿Querés que agendemos una reunión para contarte más? 📅\n\n"
                f"*1* Sí, agendar cita\n*2* Prefiero que me llamen\n*3* Ver propiedades primero")
        elif score == "tibio":
            _enviar_texto(telefono,
                f"\nTe voy a compartir información de nuestras propiedades.\n"
                f"*1* Ver propiedades\n*2* Hablar con {EMPRESA['asesor']}")
        else:  # frio
            _enviar_texto(telefono,
                f"\nCuando estés listo para avanzar, acá estamos. 🏠\n"
                f"Escribí *hola* para volver al menú o *asesor* para hablar con nosotros.")
        return

    # Hacer la siguiente pregunta
    pregunta = preguntas[hechas]
    SESIONES[telefono] = {**sesion, "preguntas_hechas": hechas + 1, "step": "precalificacion"}
    _enviar_texto(telefono, f"*{hechas + 1}/{len(preguntas)}* {pregunta}")


# ─── PROCESADOR PRINCIPAL ──────────────────────────────────────────────────────
def _procesar_mensaje(telefono: str, texto: str) -> None:
    t       = texto.lower().strip()
    sesion  = SESIONES.get(telefono, {"step": "bienvenida", "props": [], "operacion": "",
                                       "preguntas_hechas": 0, "respuestas_precal": [],
                                       "historial": []})
    step    = sesion.get("step", "bienvenida")

    # ── Guardar en historial ─────────────────────────────────────────────────
    historial = sesion.get("historial", [])
    historial.append({"rol": "cliente", "msg": texto[:200]})
    sesion["historial"] = historial[-10:]  # ventana de 10 mensajes
    SESIONES[telefono]  = sesion

    # ── Comandos universales ─────────────────────────────────────────────────
    if t in ("0", "menu", "menú", "inicio", "volver", "restart"):
        nombre = sesion.get("nombre", "")
        SESIONES[telefono] = {"step": "bienvenida", "props": [], "operacion": "",
                               "preguntas_hechas": 0, "respuestas_precal": [],
                               "nombre": nombre, "historial": sesion.get("historial", [])}
        _at_registrar_lead(telefono, nombre, notas="Reinició conversación")
        _enviar_texto(telefono, _msg_bienvenida())
        return

    if t in ("asesor", "humano", "agente", "vendedor", "persona"):
        _ir_asesor(telefono)
        return

    # ── PASO: agendamiento ───────────────────────────────────────────────────
    if step == "agendamiento":
        if t == "0":
            SESIONES[telefono] = {**sesion, "step": "bienvenida"}
            _enviar_texto(telefono, _msg_bienvenida())
        elif re.fullmatch(r"\d+", t):
            _confirmar_reserva(telefono, sesion, int(t) - 1)
        else:
            _enviar_texto(telefono, "Elegí un número de la lista o *0* para volver.")
        return

    # ── PASO: lista de propiedades ───────────────────────────────────────────
    if step == "lista":
        props = sesion.get("props", [])
        if t == "0":
            SESIONES[telefono] = {**sesion, "step": "bienvenida"}
            _enviar_texto(telefono, _msg_bienvenida())
        elif t in ("1", "agendar", "visita"):
            _iniciar_agendamiento(telefono, sesion)
        elif t in ("2", "asesor"):
            _ir_asesor(telefono)
        elif re.fullmatch(r"\d+", t):
            idx = int(t) - 1
            if 0 <= idx < len(props):
                SESIONES[telefono] = {**sesion, "step": "ficha", "prop_actual": props[idx]}
                _enviar_ficha(telefono, props[idx])
            else:
                _enviar_texto(telefono,
                    f"Elegí un número del 1 al {len(props)}.\n*0* volver | *asesor* hablar con nosotros")
        else:
            _enviar_texto(telefono, _gemini_libre(texto, sesion))
        return

    # ── PASO: ficha individual ───────────────────────────────────────────────
    if step == "ficha":
        if t in ("1", "agendar", "visita", "quiero"):
            _iniciar_agendamiento(telefono, sesion)
        elif t == "2":
            _ir_asesor(telefono)
        elif t == "0":
            _mostrar_propiedades(telefono, sesion)
        else:
            _enviar_texto(telefono, _gemini_libre(texto, sesion))
        return

    # ── PASO: post-precalificación ───────────────────────────────────────────
    if step == "post_precal":
        score = sesion.get("score", "tibio")
        if t == "1":
            if score == "caliente":
                _iniciar_agendamiento(telefono, sesion)
            else:
                _mostrar_propiedades(telefono, sesion)
        elif t == "2":
            _ir_asesor(telefono)
        elif t == "3":
            _mostrar_propiedades(telefono, sesion)
        else:
            _enviar_texto(telefono, _gemini_libre(texto, sesion))
        return

    # ── PASO: precalificación en curso ────────────────────────────────────────
    if step == "precalificacion":
        # Guardar respuesta y hacer siguiente pregunta
        respuestas = sesion.get("respuestas_precal", [])
        respuestas.append(texto[:300])
        SESIONES[telefono] = {**sesion, "respuestas_precal": respuestas}
        _siguiente_pregunta_precal(telefono, SESIONES[telefono])
        return

    # ── PASO: bienvenida — opción numérica directa ────────────────────────────
    if step == "bienvenida" and re.fullmatch(r"[1-4]", t):
        mapa = {"1": "desarrolladora", "2": "inmobiliaria", "3": "agente", "4": "comprador"}
        subniche = mapa[t]
        sesion["subniche"] = subniche
        SESIONES[telefono] = sesion
        _at_registrar_lead(telefono, sesion.get("nombre", ""), subniche=subniche)
        if subniche == "comprador":
            _enviar_texto(telefono,
                f"Perfecto, te ayudo a encontrar tu propiedad ideal. 🏠\n\n"
                f"¿Qué estás buscando?\n\n"
                f"*1* Comprar\n*2* Alquilar\n*3* Hablar con {EMPRESA['asesor']}")
            SESIONES[telefono] = {**sesion, "step": "operacion_comprador", "subniche": "comprador"}
        else:
            label = SUBNICHE_LABELS[subniche]
            _enviar_texto(telefono,
                f"Excelente, trabajo mucho con *{label}*. 💼\n\n"
                f"Te hago {len(PREGUNTAS_PRECAL.get(subniche, []))} preguntas rápidas "
                f"para entender mejor tu situación y mostrarte cómo podemos ayudarte.\n\n"
                f"¿Arrancamos? 🚀")
            SESIONES[telefono] = {**sesion, "step": "precalificacion",
                                   "subniche": subniche, "preguntas_hechas": 0,
                                   "respuestas_precal": []}
            _siguiente_pregunta_precal(telefono, SESIONES[telefono])
        return

    # ── PASO: operacion comprador ─────────────────────────────────────────────
    if step == "operacion_comprador":
        if t in ("1", "comprar", "compra", "venta"):
            sesion["operacion"] = "venta"
            SESIONES[telefono] = {**sesion, "step": "bienvenida"}
            _mostrar_propiedades(telefono, {**sesion, "operacion": "venta"})
        elif t in ("2", "alquilar", "alquiler", "renta"):
            sesion["operacion"] = "alquiler"
            SESIONES[telefono] = {**sesion, "step": "bienvenida"}
            _mostrar_propiedades(telefono, {**sesion, "operacion": "alquiler"})
        elif t == "3":
            _ir_asesor(telefono)
        else:
            _enviar_texto(telefono, _gemini_libre(texto, sesion))
        return

    # ── PASO: bienvenida / fallback → Gemini decide ───────────────────────────
    # Shortcut: saludos simples en paso bienvenida siempre muestran el menú
    _saludos = {"hola", "hi", "hello", "buenas", "buen dia", "buen día", "buenos dias",
                "buenos días", "buenas tardes", "buenas noches", "ola", "hey", "start"}
    if step == "bienvenida" and t in _saludos:
        SESIONES[telefono] = {**sesion, "step": "bienvenida"}
        _at_registrar_lead(telefono, sesion.get("nombre", ""), notas="Primer contacto WhatsApp")
        _enviar_texto(telefono, _msg_bienvenida())
        return

    clas = _gemini_clasificar(texto, sesion)

    # Actualizar sub-nicho si Gemini detectó uno nuevo
    nuevo_subniche = clas.get("subniche")
    if nuevo_subniche and nuevo_subniche != sesion.get("subniche"):
        sesion["subniche"] = nuevo_subniche
        SESIONES[telefono] = sesion
        _at_registrar_lead(telefono, sesion.get("nombre", ""),
                           subniche=nuevo_subniche, notas=f"Sub-nicho detectado: {nuevo_subniche}")

    intencion = clas.get("intencion", "respuesta_libre")
    respuesta_gemini = clas.get("respuesta", "")

    if intencion == "saludo":
        nombre = sesion.get("nombre", "")
        SESIONES[telefono] = {**sesion, "step": "bienvenida"}
        _at_registrar_lead(telefono, nombre, notas="Primer contacto WhatsApp")
        _enviar_texto(telefono, respuesta_gemini or _msg_bienvenida())

    elif intencion == "ver_propiedades":
        if clas.get("operacion"):
            sesion["operacion"] = clas["operacion"]
        if clas.get("tipo"):
            sesion["tipo"] = clas["tipo"]
        if clas.get("zona"):
            sesion["zona"] = clas["zona"]
        SESIONES[telefono] = sesion
        if respuesta_gemini:
            _enviar_texto(telefono, respuesta_gemini)
        _mostrar_propiedades(telefono, sesion)

    elif intencion == "agendar":
        if respuesta_gemini:
            _enviar_texto(telefono, respuesta_gemini)
        _iniciar_agendamiento(telefono, sesion)

    elif intencion == "asesor":
        _ir_asesor(telefono)

    elif intencion == "precalificacion":
        subniche = sesion.get("subniche", "comprador")
        if subniche and subniche != "comprador":
            # Sub-nicho B2B → arrancar precalificación
            if respuesta_gemini:
                _enviar_texto(telefono, respuesta_gemini)
            SESIONES[telefono] = {**sesion, "step": "precalificacion",
                                   "preguntas_hechas": 0, "respuestas_precal": []}
            _siguiente_pregunta_precal(telefono, SESIONES[telefono])
        else:
            # Comprador → respuesta libre + propiedades
            _enviar_texto(telefono, respuesta_gemini or _gemini_libre(texto, sesion))

    else:
        # respuesta_libre
        subniche = sesion.get("subniche")
        if subniche and subniche != "comprador" and not sesion.get("preguntas_hechas"):
            # Detectó sub-nicho B2B pero aún no precalificó
            if respuesta_gemini:
                _enviar_texto(telefono, respuesta_gemini)
            _enviar_texto(telefono,
                f"Para entender mejor cómo podemos ayudarte, "
                f"¿te hago unas preguntas rápidas? Son solo {len(PREGUNTAS_PRECAL.get(subniche, []))}. 😊\n\n"
                f"*1* Sí, dale\n*2* Prefiero hablar con un asesor")
            SESIONES[telefono] = {**sesion, "step": "oferta_precal"}
        else:
            _enviar_texto(telefono, respuesta_gemini or _gemini_libre(texto, sesion))


# ─── MENSAJES FIJOS ───────────────────────────────────────────────────────────
def _msg_bienvenida() -> str:
    return (f"👋 ¡Hola! Soy un asistente IA especializado en el sector inmobiliario. 🏘️\n\n"
            f"Ayudo a empresas y profesionales a *automatizar su atención y agendar "
            f"más citas* con inteligencia artificial.\n\n"
            f"¿Con cuál de estas situaciones te identificás?\n\n"
            f"🏗️ *1.* Tengo un *proyecto / desarrollo* inmobiliario\n"
            f"🏢 *2.* Tengo una *inmobiliaria* con equipo de asesores\n"
            f"🧑‍💼 *3.* Soy *agente independiente* con mi propia cartera\n"
            f"🏠 *4.* Busco *comprar o alquilar* una propiedad\n\n"
            f"Respondé con el número o contame directamente. 😊")


def _ir_asesor(telefono: str) -> None:
    sesion = SESIONES.get(telefono, {})
    SESIONES[telefono] = {**sesion, "step": "bienvenida"}
    _enviar_texto(telefono,
        f"¡Perfecto! Te conecto con {EMPRESA['asesor']}. 👤\n\n"
        f"Podés escribirle al {EMPRESA['whatsapp']} o aguardá que te contacte en breve. 🏠")


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────
@router.post("/whatsapp")
async def procesar_whatsapp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detalle": "body no es JSON válido"}

    msg      = body.get("whatsappInboundMessage") or body
    telefono = str(msg.get("from") or body.get("from") or body.get("telefono") or "")
    if telefono:
        telefono = _norm_tel(telefono)

    msg_type = msg.get("type", "text")
    texto    = ""
    if msg_type == "text":
        text_obj = msg.get("text") or {}
        texto = text_obj.get("body", "") if isinstance(text_obj, dict) else str(text_obj)
    elif msg_type == "button":
        btn   = msg.get("button") or {}
        texto = btn.get("text", btn.get("payload", ""))
    elif msg_type == "interactive":
        inter      = msg.get("interactive") or {}
        tipo_inter = inter.get("type", "")
        if tipo_inter == "button_reply":
            texto = inter.get("button_reply", {}).get("title", "")
        elif tipo_inter == "list_reply":
            texto = inter.get("list_reply", {}).get("title", "")
    elif msg_type in ("image", "audio", "video", "document", "sticker"):
        return {"status": "ignorado", "razon": f"media: {msg_type}"}

    if not telefono or not texto:
        return {"status": "ignorado", "razon": "sin telefono o texto"}

    # Capturar nombre del perfil
    profile  = (msg.get("customerProfile") or msg.get("whatsappContact")
                or body.get("customerProfile") or {})
    raw_name = profile.get("name") or profile.get("displayName") or ""
    sesion   = SESIONES.get(telefono, {})
    if raw_name and not sesion.get("nombre"):
        sesion["nombre"] = raw_name
        SESIONES[telefono] = sesion

    _procesar_mensaje(telefono, texto)
    return {"status": "ok", "telefono": telefono, "texto": texto,
            "subniche": SESIONES.get(telefono, {}).get("subniche"),
            "step": SESIONES.get(telefono, {}).get("step")}


@router.get("/propiedades")
def ver_propiedades(tipo: str = None, operacion: str = None, zona: str = None):
    props = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona)
    return {"total": len(props), "propiedades": props}


@router.get("/crm/propiedades")
def crm_propiedades():
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return {"records": [], "error": "INMO_DEMO_AIRTABLE_BASE no configurado"}
    url     = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r    = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset   = data.get("offset")
        if not offset:
            break
    return {"total": len(records), "records": records}


@router.get("/crm/clientes")
def crm_clientes():
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_CLIENTES:
        return {"records": [], "error": "INMO_DEMO_AIRTABLE_BASE no configurado"}
    url     = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r    = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        records += [{"id": rec["id"], **rec["fields"]} for rec in data.get("records", [])]
        offset   = data.get("offset")
        if not offset:
            break
    return {"total": len(records), "records": records}


@router.get("/config")
def ver_config():
    return {
        "nombre":        NOMBRE_EMPRESA,
        "ciudad":        CIUDAD,
        "asesor":        NOMBRE_ASESOR,
        "numero_bot":    NUMERO_BOT[:6] + "..." if NUMERO_BOT else "❌ no configurado",
        "numero_asesor": NUMERO_ASESOR[:6] + "..." if NUMERO_ASESOR else "❌ no configurado",
        "moneda":        MONEDA,
        "zonas":         ZONAS_LIST,
        "ycloud":        "✅" if YCLOUD_API_KEY else "❌",
        "airtable":      "✅" if AIRTABLE_TOKEN else "❌",
        "airtable_base": AIRTABLE_BASE_ID or "❌",
        "gemini":        "✅" if GEMINI_API_KEY else "❌",
        "cal_com":       "✅ activo" if _cal_disponible() else "⚠️ no configurado (derivación a asesor)",
        "subnichos":     list(SUBNICHE_LABELS.keys()),
    }
