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
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_PHONE_ID     = os.environ.get("META_PHONE_NUMBER_ID", "")

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

_zonas_raw = os.environ.get("INMO_DEMO_ZONAS", "Zona Norte,Zona Sur,Zona Centro")
ZONAS_LIST = [z.strip() for z in _zonas_raw.split(",") if z.strip()]

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(prefix="/clientes/lovbot/inmobiliaria", tags=["Robert — Inmobiliaria"])

# ─── SESIONES EN MEMORIA ──────────────────────────────────────────────────────
SESIONES: dict[str, dict] = {}

AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


# ─── META GRAPH API ───────────────────────────────────────────────────────────
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
            print(f"[ROBERT-META] Error {r.status_code}: {r.text[:300]}")
        return r.status_code in (200, 201)
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
                       ciudad: str = "", subniche: str = "") -> None:
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
    """Retorna hasta 6 slots disponibles en los próximos N días."""
    if not _cal_disponible():
        return []
    from datetime import datetime, timedelta
    start = datetime.utcnow().strftime("%Y-%m-%d")
    end   = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            "https://api.cal.com/v1/slots",
            params={"apiKey": CAL_API_KEY, "eventTypeId": CAL_EVENT_ID,
                    "startTime": start, "endTime": end},
            timeout=10,
        )
        if r.status_code == 200:
            slots_raw = r.json().get("slots", {})
            slots = []
            for fecha, lista in slots_raw.items():
                for slot in lista[:2]:
                    if slot.get("time"):
                        slots.append({"fecha": fecha, "time": slot["time"]})
            return slots[:6]
    except Exception as e:
        print(f"[ROBERT-CAL] Error slots: {e}")
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
                    "email": email or (re.sub(r'\D', '', telefono) + "@lovbot.ai"),
                    "phone": telefono,
                },
                "metadata": {"fuente": "WhatsApp Bot Lovbot", "notas": notas},
                "timeZone": "America/Mexico_City",
                "language": "es",
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {"ok": True, "uid": data.get("uid", ""), "start": data.get("startTime", slot_time)}
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
            mx = dt.astimezone(timezone(timedelta(hours=-6)))
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
                       json={"fields": {"Fecha_Cita": fecha_cita[:10], "Estado": "en_negociacion"}},
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


def _gemini_calificar(sesion: dict) -> dict:
    zonas_str = "|".join(ZONAS_LIST)
    prompt = f"""Sos un analista comercial inmobiliario de {NOMBRE_EMPRESA} en {CIUDAD}.
Analizá las respuestas del lead y devolvé SOLO un JSON:
{{
  "score": "caliente|tibio|frio",
  "tipo": "casa|departamento|terreno|local|oficina|null",
  "zona": "{zonas_str}|null",
  "operacion": "venta|alquiler|null",
  "presupuesto_detectado": "alto|medio|bajo|sin_info",
  "derivar_sitio_web": true|false,
  "nota_para_asesor": "texto breve"
}}

Reglas:
- caliente: presupuesto claro + compra/alquiler en menos de 6 meses
- tibio: interesado pero sin urgencia o presupuesto indefinido
- frio: solo curiosidad, explorando, más de 1 año → derivar_sitio_web: true
- Opciones 3 y 4 de urgencia ("próximo año", "explorando") → frio + derivar_sitio_web: true

Respuestas del lead:
- Objetivo/intención: "{sesion.get('resp_objetivo', '')}"
- Tipo de propiedad: "{sesion.get('resp_tipo', '')}"
- Zona: "{sesion.get('resp_zona', '')}"
- Presupuesto: "{sesion.get('resp_presupuesto', '')}"
- Urgencia: "{sesion.get('resp_urgencia', '')}"

Devolvé SOLO el JSON."""
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
    "Soy su asistente virtual y estoy aquí para ayudarle a encontrar "
    "la propiedad ideal en *{ciudad}* 🏙️\n\n"
    "Le haré solo *5 preguntas rápidas* para mostrarle opciones "
    "que se ajusten exactamente a lo que busca. ¡Son menos de 2 minutos! ⚡\n\n"
    "Para empezar — ¿me podría decir su nombre, por favor? 😊"
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
def _procesar(telefono: str, texto: str) -> None:
    texto = texto.strip()
    texto_lower = texto.lower()
    sesion = SESIONES.get(telefono, {})
    step = sesion.get("step", "inicio")
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""
    subniche = sesion.get("subniche", "")

    # Comandos globales
    if texto_lower in ("0", "menú", "menu", "inicio", "hola", "hi", "buenas"):
        SESIONES.pop(telefono, None)
        step = "inicio"

    if texto_lower == "#":
        _ir_asesor(telefono, sesion)
        return

    # ── INICIO → MENÚ SUBNICHO ────────────────────────────────────────────────
    if step == "inicio":
        SESIONES[telefono] = {"step": "subnicho"}
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

    # ── NOMBRE ────────────────────────────────────────────────────────────────
    if step == "nombre":
        nombre = texto.title()
        SESIONES[telefono] = {**sesion, "step": "email", "nombre": nombre}
        n = nombre.split()[0]
        _enviar_texto(telefono,
            f"¡Mucho gusto, *{n}*! 😊 Es un placer atenderle.\n\n"
            f"¿Me comparte su *correo electrónico*? 📬\n"
            f"_(Lo usamos para enviarle fichas de propiedades y novedades)_\n\n"
            f"_(Si prefiere no compartirlo, escriba *no*)_"
        )
        return

    # ── EMAIL ─────────────────────────────────────────────────────────────────
    if step == "email":
        rechazos = ("no", "no gracias", "nop", "nel", "paso", "no quiero", "omitir", "sin email")
        if texto_lower in rechazos:
            SESIONES[telefono] = {**sesion, "step": "ciudad", "email": ""}
            _enviar_texto(telefono,
                f"Sin problema 😊\n\n¿Desde qué *ciudad* nos escribe? 📍"
            )
        elif "@" in texto and "." in texto:
            email = texto.strip()
            threading.Thread(target=_at_guardar_email, args=(telefono, email), daemon=True).start()
            SESIONES[telefono] = {**sesion, "step": "ciudad", "email": email}
            _enviar_texto(telefono,
                f"¡Perfecto! 📬 Email registrado.\n\n¿Desde qué *ciudad* nos escribe? 📍"
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
            f"¡Gracias! 📍 *{ciudad_resp}*\n\n" + _pregunta("objetivo", nombre, subniche)
        )
        return

    # ── OBJETIVO (comprar/alquilar + para qué) ────────────────────────────────
    if step == "objetivo":
        mapa_op = {"1": "venta", "2": "alquiler", "3": "venta"}
        operacion = mapa_op.get(texto.strip(), "venta")
        SESIONES[telefono] = {**sesion, "step": "tipo", "resp_objetivo": texto,
                              "operacion_at": operacion}
        _enviar_texto(telefono, _pregunta("tipo", nombre_corto, subniche))
        return

    # ── TIPO DE PROPIEDAD ─────────────────────────────────────────────────────
    if step == "tipo":
        mapa_tipo = {
            "1": "casa", "2": "departamento", "3": "terreno",
            "4": "otro", "5": "otro",
        }
        tipo_detectado = mapa_tipo.get(texto.strip(), _normalizar_tipo(texto) or texto.lower())
        SESIONES[telefono] = {**sesion, "step": "zona", "resp_tipo": tipo_detectado}
        _enviar_texto(telefono, _pregunta("zona", nombre_corto, subniche))
        return

    # ── ZONA ──────────────────────────────────────────────────────────────────
    if step == "zona":
        zona_detectada = texto
        try:
            idx = int(texto) - 1
            if 0 <= idx < len(ZONAS_LIST):
                zona_detectada = ZONAS_LIST[idx]
            elif idx == len(ZONAS_LIST):
                zona_detectada = ""
        except ValueError:
            pass
        SESIONES[telefono] = {**sesion, "step": "presupuesto", "resp_zona": zona_detectada}
        _enviar_texto(telefono, _pregunta("presupuesto", nombre_corto, subniche))
        return

    # ── PRESUPUESTO ───────────────────────────────────────────────────────────
    if step == "presupuesto":
        # Opción 5 = hablar con asesor directo
        if texto.strip() == "5":
            _ir_asesor(telefono, sesion)
            return
        presupuesto_at = _PRESUPUESTO_MAP.get(texto.strip(), "")
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
        threading.Thread(
            target=_at_registrar_lead,
            args=(telefono, nombre, score, tipo, zona, nota, presupuesto_at,
                  operacion_at, ciudad_at, subniche_at), daemon=True
        ).start()

        # Lead frío → derivar a sitio web
        if derivar or score == "frio":
            web_line = f"🌐 *{SITIO_WEB}*\n\n" if SITIO_WEB else ""
            _enviar_texto(telefono, MSG_SITIO_WEB.format(
                nombre=nombre_corto or nombre, web_line=web_line,
                asesor=NOMBRE_ASESOR))
            threading.Thread(
                target=_notificar_asesor,
                args=(telefono, sesion_act, calificacion), daemon=True
            ).start()
            SESIONES.pop(telefono, None)
            return

        # Lead caliente/tibio → buscar propiedades en Airtable
        props = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona,
                                       presupuesto=presupuesto_at)

        threading.Thread(
            target=_notificar_asesor,
            args=(telefono, sesion_act, calificacion), daemon=True
        ).start()

        if not props:
            _enviar_texto(telefono,
                f"*{nombre_corto or nombre}*, no tenemos propiedades disponibles "
                f"con esas características en este momento, pero nuestro asesor "
                f"*{NOMBRE_ASESOR}* puede ayudarle a encontrar opciones personalizadas. 🏡"
            )
        else:
            # Mostrar lista de propiedades
            SESIONES[telefono] = {**sesion_act, "step": "lista", "props": props,
                                  "tipo": tipo, "zona": zona, "operacion": operacion}
            _enviar_texto(telefono,
                f"¡Excelente, *{nombre_corto or nombre}*! 🎉\n\n"
                f"Revisé nuestro portafolio y encontré *{len(props)} propiedad(es)* "
                f"que coinciden con lo que está buscando. Aquí están 👇"
            )
            _enviar_texto(telefono, _lista_titulos(props))
            return  # queda en step lista para que elija ficha

        # Ofrecer cita con Cal.com (ya tiene email y datos)
        if _cal_disponible():
            slots = _cal_obtener_slots()
            if slots:
                SESIONES[telefono] = {**sesion_act, "step": "agendar_slots",
                                      "slots": slots, "email": email}
                _enviar_texto(telefono,
                    f"¿Le gustaría agendar una cita con nuestro asesor *{NOMBRE_ASESOR}*? 📅\n\n"
                    f"{_formatear_slots(slots)}\n\n"
                    f"Responda con el *número* del horario que prefiere, o *0* para omitir."
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
        try:
            idx = int(texto) - 1
            if 0 <= idx < len(props):
                SESIONES[telefono] = {**sesion, "step": "ficha", "ficha_actual": idx}
                _enviar_ficha(telefono, props[idx])
            else:
                _enviar_texto(telefono,
                    f"Por favor elija un número del 1 al {len(props)}, "
                    f"*0* para volver o *#* para hablar con el asesor.")
        except ValueError:
            _enviar_texto(telefono,
                "Responda con el *número* de la propiedad que desea ver, "
                "*0* para volver o *#* para hablar con el asesor. 😊")
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

    # ── AGENDAMIENTO — SELECCIÓN DE SLOT ─────────────────────────────────────
    if step == "agendar_slots":
        slots = sesion.get("slots", [])
        email = sesion.get("email", "")
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
                notas = (f"Busca: {sesion.get('resp_tipo','')} en {sesion.get('resp_zona','')} "
                         f"— Presupuesto: {sesion.get('resp_presupuesto','')}")
                resultado = _cal_crear_reserva(nombre, email, telefono, slot["time"], notas)
                if resultado["ok"]:
                    threading.Thread(
                        target=_at_guardar_cita,
                        args=(telefono, slot["time"]), daemon=True
                    ).start()
                    from datetime import datetime, timezone, timedelta
                    try:
                        dt = datetime.fromisoformat(slot["time"].replace("Z", "+00:00"))
                        mx = dt.astimezone(timezone(timedelta(hours=-6)))
                        dia_es = _DIAS_ES.get(mx.strftime("%A"), mx.strftime("%A"))
                        fecha_str = f"{dia_es} {mx.strftime('%d/%m a las %H:%M hs')}"
                    except Exception:
                        fecha_str = slot["time"]
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
                        f"Por favor elija otro horario o escriba *0* para que el asesor lo contacte."
                    )
            else:
                _enviar_texto(telefono,
                    f"Por favor elija un número del 1 al {len(slots)}, o *0* para omitir. 😊")
        except ValueError:
            _enviar_texto(telefono,
                f"Responda con el *número* del horario (1-{len(slots)}) o *0* para omitir. 😊")
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

    # Ofrecer cita con Cal.com (ya tiene email desde el inicio)
    if _cal_disponible():
        slots = _cal_obtener_slots()
        if slots:
            SESIONES[telefono] = {**sesion, "step": "agendar_slots",
                                  "slots": slots, "email": email}
            _enviar_texto(telefono,
                f"¡Con gusto, {nombre_corto}! Estos son los horarios disponibles con *{NOMBRE_ASESOR}*: 📅\n\n"
                f"{_formatear_slots(slots)}\n\n"
                f"Responda con el *número* del horario que prefiere, o *0* para que lo contacten."
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
    """Recibe mensajes desde /meta/webhook (main.py lo redirige aquí)."""
    data = await request.json()
    telefono = data.get("from", "")
    texto    = data.get("text", "")
    if not telefono or not texto:
        return {"status": "ignored"}
    threading.Thread(target=_procesar, args=(telefono, texto), daemon=True).start()
    return {"status": "processing"}


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
