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
}

# Contexto de bienvenida por sub-nicho — simula el bot de ESA empresa
SUBNICHE_BIENVENIDA = {
    "desarrolladora": (
        "🏗️ Bienvenido a *{empresa}*.\n\n"
        "Somos una desarrolladora inmobiliaria en {ciudad}.\n"
        "Tenemos proyectos de casas y lotes disponibles.\n\n"
        "¿Qué estás buscando?\n\n"
        "*1* Ver proyectos disponibles\n"
        "*2* Hablar con un asesor"
    ),
    "inmobiliaria": (
        "🏢 Hola, bienvenido a *{empresa}*.\n\n"
        "Somos una inmobiliaria en {ciudad} con propiedades en venta y alquiler.\n\n"
        "¿Qué estás buscando?\n\n"
        "*1* Comprar una propiedad\n"
        "*2* Alquilar una propiedad\n"
        "*3* Hablar con un asesor"
    ),
    "agente": (
        "🧑‍💼 Hola, soy *{asesor}*, asesor inmobiliario independiente en {ciudad}.\n\n"
        "Te puedo ayudar a encontrar la propiedad ideal.\n\n"
        "¿Qué necesitás?\n\n"
        "*1* Comprar\n"
        "*2* Alquilar\n"
        "*3* Hablar conmigo directo"
    ),
}

# ─── AIRTABLE ─────────────────────────────────────────────────────────────────
AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def _at_registrar_lead(telefono: str, nombre: str, subniche: str = "", score: str = "",  # noqa: ARG001
                       operacion: str = "", tipo: str = "", notas: str = "",
                       email: str = "", ciudad: str = "", fecha_cita: str = "") -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_CLIENTES:
        print(f"[AT-SKIP] base={AIRTABLE_BASE_ID!r} tabla={AIRTABLE_TABLE_CLIENTES!r} — vars no configuradas")
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
    if email:
        campos["Email"] = email
    if ciudad:
        campos["Ciudad"] = ciudad
    if score:
        if score == "caliente":
            campos["Estado"] = "en_negociacion"
        elif score == "tibio":
            campos["Estado"] = "contactado"
        else:
            campos["Estado"] = "no_contactado"
    if operacion:
        campos["Operacion"] = operacion.lower()
    if tipo:
        campos["Tipo_Propiedad"] = tipo
    if fecha_cita:
        campos["Fecha_Cita"] = fecha_cita[:10]  # Airtable date solo acepta YYYY-MM-DD
    if notas:
        campos["Notas_Bot"] = notas

    if records:
        rec_id = records[0]["id"]
        r = requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        print(f"[AT-PATCH] tel={telefono} status={r.status_code} resp={r.text[:200]}")
    else:
        campos["Fecha_WhatsApp"] = date.today().isoformat()
        if "Estado" not in campos:
            campos["Estado"] = "nuevo"
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        print(f"[AT-POST] tel={telefono} status={r.status_code} resp={r.text[:200]}")


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
                "timeZone": "America/Argentina/Buenos_Aires",
                "language": "es",
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {"ok": True, "uid": data.get("uid", ""), "start": data.get("startTime", slot_time)}
        print(f"[CAL-ERROR] status={r.status_code} body={r.text[:500]}")
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
        result = _gemini_client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
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
        result = _gemini_client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
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
            model="gemini-2.5-flash-lite",
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
    lineas.append(f"\n¿Te interesa?\n*1* Agendar visita | *2* Hablar con {EMPRESA['asesor']} | *0* Volver")
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
def _mostrar_slots(telefono: str, sesion: dict) -> None:
    """Obtiene slots de Cal.com y los muestra al usuario."""
    slots = _cal_obtener_slots(dias=7)
    if not slots:
        _enviar_texto(telefono,
            f"En este momento no hay turnos disponibles en el calendario. 😔\n"
            f"Escribile a {EMPRESA['asesor']} al {EMPRESA['whatsapp']} para coordinar. 📱")
        return

    nombre = sesion.get("nombre", "")
    _enviar_texto(telefono,
        f"Perfecto{', ' + nombre.split()[0] if nombre else ''}! 😊 "
        f"Estos son los turnos disponibles esta semana para reunirte con {EMPRESA['asesor']}:")

    lineas = []
    for i, s in enumerate(slots, 1):
        from datetime import datetime, timezone, timedelta
        try:
            dt_utc = datetime.fromisoformat(s["time"].replace("Z", "+00:00"))
            tz_local = timezone(timedelta(hours=int(os.environ.get("INMO_DEMO_UTC_OFFSET", "-3"))))
            dt = dt_utc.astimezone(tz_local)
            _dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            dia_es = _dias_es[dt.weekday()]
            legible = f"{dia_es} {dt.strftime('%d/%m')} — {dt.strftime('%H:%M')} hs"
        except Exception:
            legible = s["time"]
        lineas.append(f"*{i}.* {legible}")
    lineas.append("\nRespondé con el *número* del turno que te queda mejor.")
    lineas.append("*0* para volver")

    SESIONES[telefono] = {**sesion, "step": "agendamiento", "slots": slots}
    _enviar_texto(telefono, "\n".join(lineas))


def _iniciar_agendamiento(telefono: str, sesion: dict) -> None:
    if not _cal_disponible():
        _enviar_texto(telefono,
            f"¡Perfecto! {EMPRESA['asesor']} se va a poner en contacto con vos para coordinar. 📅\n\n"
            f"También podés escribirle directamente al {EMPRESA['whatsapp']}. 🏠")
        SESIONES[telefono] = {**sesion, "step": "bienvenida"}
        return

    # Iniciar captura de datos del lead antes de mostrar turnos
    SESIONES[telefono] = {**sesion, "step": "captura_datos", "captura_campo": "nombre"}
    _enviar_texto(telefono,
        f"¡Genial! Para coordinar la reunión con {EMPRESA['asesor']}, necesito algunos datos. 📋\n\n"
        f"¿Cuál es tu *nombre y apellido*?")


def _confirmar_reserva(telefono: str, sesion: dict, slot_idx: int) -> None:
    slots  = sesion.get("slots", [])
    nombre = sesion.get("nombre", "Cliente")
    if slot_idx < 0 or slot_idx >= len(slots):
        _enviar_texto(telefono, f"Elegí un número del 1 al {len(slots)}.")
        return
    slot  = slots[slot_idx]
    result = _cal_crear_reserva(nombre=nombre, email=sesion.get("email_lead", ""), telefono=telefono,
                                 slot_time=slot["time"],
                                 notas=f"Agendado por WhatsApp Bot — {EMPRESA['nombre']}")
    if result.get("ok"):
        from datetime import datetime, timezone, timedelta
        try:
            dt_utc = datetime.fromisoformat(slot["time"].replace("Z", "+00:00"))
            tz_local = timezone(timedelta(hours=int(os.environ.get("INMO_DEMO_UTC_OFFSET", "-3"))))
            dt = dt_utc.astimezone(tz_local)
            _dias_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
            _meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            legible = f"{_dias_es[dt.weekday()]} {dt.day} de {_meses_es[dt.month - 1]} a las {dt.strftime('%H:%M')} hs"
        except Exception:
            legible = slot["time"]
        _at_registrar_lead(telefono, nombre,
                           subniche=sesion.get("subniche", ""),
                           email=sesion.get("email_lead", ""),
                           ciudad=sesion.get("ciudad_lead", ""),
                           score="caliente",
                           fecha_cita=slot["time"],
                           notas=f"Cita agendada: {legible}")
        _enviar_texto(telefono,
            f"✅ *¡Cita confirmada!*\n\n"
            f"📅 {legible}\n"
            f"📍 {EMPRESA['ciudad']}\n\n"
            f"Vas a recibir un recordatorio. Si necesitás cambiarla escribí *asesor*. 🏠")
        SESIONES[telefono] = {**sesion, "step": "bienvenida", "score": "caliente"}
    else:
        err = result.get("error", "")
        print(f"[CAL-BOOKING-FAIL] tel={telefono} error={err}")
        # Si el slot ya no está disponible, mostrar nuevos slots
        if "no longer available" in err.lower() or "slot" in err.lower() or "available" in err.lower():
            _enviar_texto(telefono,
                "Ese turno ya no está disponible. 😔 Te muestro los turnos actualizados:")
            _mostrar_slots(telefono, sesion)
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

        es_b2b = subniche in ("desarrolladora", "inmobiliaria", "agente")

        if respuesta_gemini:
            _enviar_texto(telefono, respuesta_gemini)

        if score == "caliente":
            if es_b2b:
                _enviar_texto(telefono,
                    f"🔥 ¡Perfecto! Esto tiene mucho potencial.\n\n"
                    f"¿Agendamos una llamada de 20 min para mostrarte exactamente cómo funciona el sistema? 📅\n\n"
                    f"*1* Sí, agendar reunión ahora\n*2* Prefiero que me contacten")
            else:
                _enviar_texto(telefono,
                    f"¿Querés que agendemos una visita? 📅\n\n"
                    f"*1* Sí, agendar visita\n*2* Ver propiedades primero\n*3* Hablar con {EMPRESA['asesor']}")
        elif score == "tibio":
            if es_b2b:
                _enviar_texto(telefono,
                    f"💡 Entiendo tu situación. Te cuento brevemente cómo podemos ayudarte:\n\n"
                    f"✅ Bot WhatsApp que responde leads 24/7\n"
                    f"✅ Precalificación automática — filtra curiosos vs compradores reales\n"
                    f"✅ Agenda citas sin intervención humana\n"
                    f"✅ CRM integrado con todo el historial\n\n"
                    f"*1* Agendar demo de 20 min\n*2* Hablar con {EMPRESA['asesor']}")
            else:
                _enviar_texto(telefono,
                    f"Te muestro lo que tenemos disponible 🏠\n"
                    f"*1* Ver propiedades\n*2* Hablar con {EMPRESA['asesor']}")
        else:  # frio
            if es_b2b:
                _enviar_texto(telefono,
                    f"Entendido. Cuando el proyecto tome forma, acá estamos. 🤝\n\n"
                    f"Escribí *hola* cuando quieras retomar o *asesor* para hablar con nosotros.")
            else:
                _enviar_texto(telefono,
                    f"Cuando estés listo para buscar, acá estamos. 🏠\n"
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
    # "0" solo resetea al menú principal desde bienvenida o palabras clave explícitas.
    # En cualquier otro paso, "0" es manejado por el handler del paso (volver atrás).
    if t in ("menu", "menú", "inicio", "restart") or (t == "0" and step == "bienvenida"):
        nombre = sesion.get("nombre", "")
        SESIONES[telefono] = {"step": "bienvenida", "props": [], "operacion": "",
                               "preguntas_hechas": 0, "respuestas_precal": [],
                               "nombre": nombre, "historial": sesion.get("historial", [])}
        _at_registrar_lead(telefono, nombre, notas="Reinició conversación")
        _enviar_texto(telefono, _msg_bienvenida())
        return

    if t in ("asesor", "humano", "vendedor", "persona"):
        _ir_asesor(telefono)
        return

    # ── PASO: captura de datos del lead (nombre, email, ciudad) ─────────────
    # Si el lead viene del formulario, ya tiene todos los datos — saltar directo a slots
    if step == "captura_datos" and sesion.get("captura_completa"):
        _mostrar_slots(telefono, sesion)
        return

    if step == "captura_datos":
        campo = sesion.get("captura_campo", "nombre")
        valor = texto.strip()

        if campo == "nombre":
            sesion["nombre"] = valor
            SESIONES[telefono] = {**sesion, "captura_campo": "email"}
            _enviar_texto(telefono, f"Gracias, *{valor.split()[0]}*! 😊\n\n¿Cuál es tu *email*?")

        elif campo == "email":
            sesion["email_lead"] = valor
            SESIONES[telefono] = {**sesion, "captura_campo": "telefono_lead"}
            _enviar_texto(telefono, "¿Cuál es tu *número de teléfono* (con código de área)?")

        elif campo == "telefono_lead":
            sesion["telefono_lead"] = valor
            SESIONES[telefono] = {**sesion, "captura_campo": "ciudad"}
            _enviar_texto(telefono, "¿Desde qué *ciudad o zona* nos escribís?")

        elif campo == "ciudad":
            sesion["ciudad_lead"] = valor
            nombre        = sesion.get("nombre", "")
            email         = sesion.get("email_lead", "")
            tel_alt       = sesion.get("telefono_lead", "")
            notas_extra   = f" | Tel alternativo: {tel_alt}" if tel_alt else ""
            _at_registrar_lead(telefono, nombre, email=email, ciudad=valor,
                               notas="Datos capturados — pendiente agendar cita" + notas_extra)
            SESIONES[telefono] = {**sesion}
            _mostrar_slots(telefono, SESIONES[telefono])
        return

    # ── PASO: agendamiento ───────────────────────────────────────────────────
    if step == "agendamiento":
        if t == "0":
            # Volver a la ficha o lista según contexto
            _mostrar_propiedades(telefono, sesion)
        elif re.fullmatch(r"\d+", t):
            _confirmar_reserva(telefono, sesion, int(t) - 1)
        else:
            _enviar_texto(telefono, "Elegí un número de la lista o *0* para volver.")
        return

    # ── PASO: lista de propiedades ───────────────────────────────────────────
    if step == "lista":
        props = sesion.get("props", [])
        if t == "0":
            subniche = sesion.get("subniche")
            if subniche:
                SESIONES[telefono] = {**sesion, "step": "demo_subniche"}
                _enviar_texto(telefono, _msg_subniche(subniche))
            else:
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
            # Volver a la lista de propiedades (que a su vez permite volver al sub-nicho)
            _mostrar_propiedades(telefono, sesion)
        else:
            _enviar_texto(telefono, _gemini_libre(texto, sesion))
        return

    # ── PASO: post-precalificación ───────────────────────────────────────────
    if step == "post_precal":
        score    = sesion.get("score", "tibio")
        es_b2b   = sesion.get("subniche", "") in ("desarrolladora", "inmobiliaria", "agente")
        if t == "1":
            # B2B siempre agenda. B2C caliente agenda, tibio ve propiedades
            if es_b2b or score == "caliente":
                _iniciar_agendamiento(telefono, sesion)
            else:
                _mostrar_propiedades(telefono, sesion)
        elif t == "2":
            if es_b2b and score == "caliente":
                _ir_asesor(telefono)
            elif es_b2b:
                _ir_asesor(telefono)
            else:
                _ir_asesor(telefono)
        elif t == "3":
            _mostrar_propiedades(telefono, sesion)
        else:
            _enviar_texto(telefono, _gemini_libre(texto, sesion))
        return

    # ── PASO: demo_subniche — el prospecto experimenta el bot como lead ──────
    if step == "demo_subniche":
        subniche = sesion.get("subniche", "inmobiliaria")
        if subniche == "desarrolladora":
            # Solo venta de proyectos propios
            if t in ("1", "ver", "proyectos"):
                _mostrar_propiedades(telefono, {**sesion, "operacion": "venta"})
            elif t in ("2", "asesor"):
                _iniciar_agendamiento(telefono, sesion)
            else:
                _enviar_texto(telefono, _gemini_libre(texto, sesion))
        else:
            # Inmobiliaria y agente: compra o alquiler
            if t in ("1", "comprar"):
                _mostrar_propiedades(telefono, {**sesion, "operacion": "venta"})
            elif t in ("2", "alquilar"):
                _mostrar_propiedades(telefono, {**sesion, "operacion": "alquiler"})
            elif t in ("3", "asesor"):
                _iniciar_agendamiento(telefono, sesion)
            else:
                _enviar_texto(telefono, _gemini_libre(texto, sesion))
        return

    # ── PASO: bienvenida — opción numérica directa ────────────────────────────
    if step == "bienvenida" and re.fullmatch(r"[1-3]", t):
        mapa = {"1": "desarrolladora", "2": "inmobiliaria", "3": "agente"}
        subniche = mapa[t]
        SESIONES[telefono] = {**sesion, "subniche": subniche, "step": "demo_subniche"}
        _at_registrar_lead(telefono, sesion.get("nombre", ""), subniche=subniche)
        _enviar_texto(telefono, _msg_subniche(subniche))
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
    return ("👋 ¡Hola! Bienvenido a esta *demo de agente inmobiliario IA*. 🏘️\n\n"
            "Seleccioná el tipo de negocio que querés ver en acción:\n\n"
            "🏗️ *1.* Desarrolladora inmobiliaria\n"
            "🏢 *2.* Inmobiliaria / Agencia\n"
            "🧑‍💼 *3.* Agente independiente\n\n"
            "Vas a experimentar exactamente cómo el bot atiende a los leads de cada negocio. 🤖")


def _msg_subniche(subniche: str) -> str:
    """Primer mensaje del bot simulando ser el negocio del sub-nicho."""
    tpl = SUBNICHE_BIENVENIDA.get(subniche, "")
    return tpl.format(empresa=EMPRESA["nombre"], ciudad=EMPRESA["ciudad"], asesor=EMPRESA["asesor"])


def _ir_asesor(telefono: str) -> None:
    sesion = SESIONES.get(telefono, {})
    SESIONES[telefono] = {**sesion, "step": "bienvenida"}
    _enviar_texto(telefono,
        f"¡Perfecto! Te conecto con {EMPRESA['asesor']}. 👤\n\n"
        f"Podés escribirle al {EMPRESA['whatsapp']} o aguardá que te contacte en breve. 🏠")


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@router.post("/lead")
async def recibir_lead_formulario(request: Request):
    """
    Endpoint para leads que vienen del formulario web.
    El lead ya viene con todos sus datos precargados (nombre, apellido, email,
    teléfono, operación, tipo de propiedad, zona, presupuesto).

    Acción:
      1. Registrar el lead en Airtable directamente (sin pedir más datos).
      2. Enviar mensaje de WhatsApp de bienvenida personalizado.
      3. Cargar sesión con los datos ya precargados y mostrar propiedades
         (o slots de agenda si urgencia es inmediata).

    El bot NO vuelve a pedir nombre/email/ciudad — ya los tiene.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detalle": "body no es JSON válido"}

    # ── Extraer campos del formulario ──────────────────────────────────────────
    nombre    = (body.get("Nombre") or body.get("nombre") or "").strip()
    apellido  = (body.get("Apellido") or body.get("apellido") or "").strip()
    nombre_completo = (nombre + " " + apellido).strip()
    telefono_raw = str(body.get("Telefono") or body.get("telefono") or "")
    email     = (body.get("Email") or body.get("email") or "").strip()
    operacion = (body.get("Operacion") or body.get("operacion") or "venta").lower()
    tipo      = (body.get("Tipo_Propiedad") or body.get("tipo_propiedad") or "").lower()
    zona      = (body.get("Zona") or body.get("zona") or "").strip()
    presupuesto = (body.get("Presupuesto") or body.get("presupuesto") or "A consultar")
    urgencia  = (body.get("urgencia") or "").strip()
    notas_raw = (body.get("Notas_Bot") or body.get("notas") or "").strip()
    sub_nicho = (body.get("Sub_nicho") or body.get("subnicho") or "").strip()
    fuente    = (body.get("Fuente") or body.get("fuente") or "formulario").strip()
    score_num = body.get("Score") or body.get("score_num")

    if not telefono_raw:
        return {"status": "error", "detalle": "Telefono requerido"}

    telefono = _norm_tel(telefono_raw)
    nombre_corto = nombre or "allí"

    # ── Determinar score basado en urgencia ────────────────────────────────────
    score = "caliente" if urgencia in ("inmediata", "1-3 meses") else "tibio"

    # ── Registrar en Airtable inmediatamente con todos los datos ──────────────
    notas_at = f"Lead formulario web | Urgencia: {urgencia or '-'} | {notas_raw}".strip(" |")
    _at_registrar_lead(
        telefono, nombre_completo,
        score=score, operacion=operacion, tipo=tipo,
        email=email, ciudad=zona,
        notas=notas_at,
    )

    # ── Guardar Sub_nicho, Fuente y Score numérico en Airtable ────────────────
    if sub_nicho or fuente or score_num is not None:
        if AIRTABLE_BASE_ID and AIRTABLE_TABLE_CLIENTES:
            _url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
            _buscar = requests.get(_url, headers=AT_HEADERS,
                params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
            _recs = _buscar.json().get("records", []) if _buscar.status_code == 200 else []
            if _recs:
                _extra: dict = {}
                if sub_nicho:
                    _extra["Sub_nicho"] = sub_nicho
                if fuente:
                    _extra["Fuente"] = fuente
                if score_num is not None:
                    try:
                        _extra["Score"] = int(score_num)
                    except (ValueError, TypeError):
                        pass
                if _extra:
                    requests.patch(f"{_url}/{_recs[0]['id']}", headers=AT_HEADERS,
                                   json={"fields": _extra}, timeout=8)

    # ── Precargar sesión con datos del formulario ─────────────────────────────
    sesion_nueva = {
        "step":               "lista",
        "subniche":           "inmobiliaria",
        "score":              score,
        "operacion":          operacion,
        "tipo":               tipo,
        "zona":               zona,
        "nombre":             nombre_completo,
        "email_lead":         email,
        "telefono_lead":      telefono,
        "ciudad_lead":        zona,
        "presupuesto":        str(presupuesto),
        "urgencia":           urgencia,
        "captura_completa":   True,   # flag: no volver a pedir datos
        "props":              [],
        "historial":          [],
        "preguntas_hechas":   0,
        "respuestas_precal":  [],
        "origen":             "formulario",
    }
    SESIONES[telefono] = sesion_nueva

    # ── Enviar bienvenida personalizada via WhatsApp ───────────────────────────
    if not YCLOUD_API_KEY or not NUMERO_BOT:
        print(f"[LEAD-FORM] tel={telefono} — YCloud no configurado, solo Airtable registrado")
        return {"status": "ok_airtable_only", "telefono": telefono, "score": score}

    # Saludo personalizado
    saludo_tipo = {
        "venta": "propiedades en venta",
        "alquiler": "propiedades en alquiler",
    }.get(operacion, "propiedades")

    msg_bienvenida = (
        f"¡Hola {nombre_corto}! 👋 Recibimos tu consulta desde el formulario web.\n\n"
        f"Buscamos las *{saludo_tipo}*"
        + (f" en *{zona}*" if zona else "")
        + (f" — tipo: _{tipo}_" if tipo else "")
        + ".\n\n"
        f"Te muestro las opciones disponibles ahora mismo 🏠"
    )
    _enviar_texto(telefono, msg_bienvenida)

    # ── Notificar al asesor que llegó un lead nuevo ───────────────────────────
    if NUMERO_ASESOR:
        score_emoji = {"caliente": "🔥", "tibio": "🌡️"}.get(score, "❄️")
        asesor_tel = re.sub(r'\D', '', NUMERO_ASESOR)
        _enviar_texto(asesor_tel,
            f"🏠 *Nuevo lead desde el formulario web*\n\n"
            f"👤 *Nombre:* {nombre_completo}\n"
            f"📱 *Teléfono:* {telefono}\n"
            f"📍 *Zona:* {zona or '-'}\n"
            f"🏷 *Tipo:* {tipo or '-'} · {operacion or '-'}\n"
            f"💰 *Presupuesto:* {presupuesto}\n"
            f"⏱ *Urgencia:* {urgencia or '-'}\n"
            f"{score_emoji} *Score:* {score}\n\n"
            f"_El bot ya le escribió y le está mostrando propiedades._"
        )

    # ── Mostrar propiedades o agendar según urgencia ──────────────────────────
    if score == "caliente" and _cal_disponible():
        # Lead urgente → ir directo a agenda
        sesion_nueva["step"] = "agendamiento"
        SESIONES[telefono] = sesion_nueva
        _mostrar_slots(telefono, sesion_nueva)
    else:
        # Mostrar propiedades filtradas por sus preferencias
        _mostrar_propiedades(telefono, sesion_nueva)

    return {
        "status": "ok",
        "telefono": telefono,
        "nombre": nombre_completo,
        "score": score,
        "step": SESIONES.get(telefono, {}).get("step"),
    }


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


@router.patch("/crm/clientes/{record_id}")
async def actualizar_estado_cliente(record_id: str, request: Request):
    """Actualiza el Estado (y opcionalmente Notas_Bot) de un lead en Airtable."""
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_CLIENTES:
        return {"status": "error", "detalle": "Airtable no configurado"}
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detalle": "body no es JSON válido"}

    ESTADOS_VALIDOS = {"no_contactado", "contactado", "en_negociacion", "cerrado", "descartado"}
    nuevo_estado = body.get("Estado", "").strip()
    if nuevo_estado and nuevo_estado not in ESTADOS_VALIDOS:
        return {"status": "error", "detalle": f"Estado inválido. Valores: {sorted(ESTADOS_VALIDOS)}"}

    campos: dict = {}
    if nuevo_estado:
        campos["Estado"] = nuevo_estado
    notas = body.get("Notas_Bot", "").strip()
    if notas:
        campos["Notas_Bot"] = notas

    if not campos:
        return {"status": "error", "detalle": "Nada que actualizar"}

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
    if r.status_code == 200:
        return {"status": "ok", "record_id": record_id, "campos": campos}
    return {"status": "error", "detalle": r.text[:200]}


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
        "airtable":           "✅" if AIRTABLE_TOKEN else "❌",
        "airtable_base":      AIRTABLE_BASE_ID or "❌",
        "airtable_clientes":  AIRTABLE_TABLE_CLIENTES or "❌ INMO_DEMO_TABLE_CLIENTES no seteada",
        "airtable_props":     AIRTABLE_TABLE_PROPS or "❌ INMO_DEMO_TABLE_PROPS no seteada",
        "gemini":        "✅" if GEMINI_API_KEY else "❌",
        "cal_com":       "✅ activo" if _cal_disponible() else "⚠️ no configurado (derivación a asesor)",
        "subnichos":     list(SUBNICHE_LABELS.keys()),
    }
