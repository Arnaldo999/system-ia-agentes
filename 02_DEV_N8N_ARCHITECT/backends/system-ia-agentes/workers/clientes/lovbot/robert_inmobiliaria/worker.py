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

AIRTABLE_TOKEN        = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID      = os.environ.get("ROBERT_AIRTABLE_BASE", "")
AIRTABLE_TABLE_PROPS  = os.environ.get("ROBERT_TABLE_PROPS", "")
AIRTABLE_TABLE_LEADS  = os.environ.get("ROBERT_TABLE_CLIENTES", "")

NOMBRE_EMPRESA = os.environ.get("INMO_DEMO_NOMBRE",  "Lovbot — Inmobiliaria")
CIUDAD         = os.environ.get("INMO_DEMO_CIUDAD",  "México")
NOMBRE_ASESOR  = os.environ.get("INMO_DEMO_ASESOR",  "Roberto")
NUMERO_ASESOR  = os.environ.get("INMO_DEMO_NUMERO_ASESOR", "")
MONEDA         = os.environ.get("INMO_DEMO_MONEDA",  "USD")
SITIO_WEB      = os.environ.get("INMO_DEMO_SITIO_WEB", "")

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
def _at_registrar_lead(telefono: str, nombre: str, score: str = "",
                       tipo: str = "", zona: str = "", notas: str = "") -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_LEADS:
        print("[ROBERT-AT] Sin base/tabla configurada — skip registro lead")
        return
    from datetime import date
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_LEADS}"
    buscar = requests.get(url, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []

    campos = {"Telefono": telefono, "Llego_WhatsApp": True}
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
    if tipo:
        campos["Tipo_Propiedad"] = tipo
    if zona:
        campos["Zona"] = zona
    if notas:
        campos["Notas_Bot"] = notas

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


def _at_buscar_propiedades(tipo: str = None, operacion: str = None,
                           zona: str = None) -> list[dict]:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return []
    filtros = ["OR({Disponible}='✅ Disponible',{Disponible}='⏳ Reservado')"]
    if tipo:
        filtros.append(f"LOWER({{Tipo}})='{tipo.lower()}'")
    if operacion:
        filtros.append(f"LOWER({{Operacion}})='{operacion.lower()}'")
    if zona and zona.lower() not in ("otra zona", "otra", "no sé", "no se"):
        filtros.append(f"{{Zona}}='{zona}'")
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


def _pregunta_dinamica(paso: str, nombre: str = "") -> str:
    nombre_corto = nombre.split()[0] if nombre else ""
    nombre_txt = f", {nombre_corto}" if nombre_corto else ""
    zonas_opciones = "\n".join(f"{i+1}️⃣ {z}" for i, z in enumerate(ZONAS_LIST))

    prompts = {
        "objetivo": (
            f"Generá una pregunta cálida y breve para preguntarle{nombre_txt} qué está buscando: "
            f"¿quiere comprar o alquilar? y para qué lo necesita (vivir, invertir, negocio). "
            f"Español neutro. Máx 4 líneas."
        ),
        "tipo": (
            f"Generá una pregunta para preguntarle{nombre_txt} qué tipo de propiedad busca. "
            f"Opciones numeradas: 1. Casa, 2. Departamento, 3. Terreno, 4. Local comercial, 5. Oficina. "
            f"Español neutro. Máx 5 líneas."
        ),
        "zona": (
            f"Generá una pregunta para preguntarle{nombre_txt} en qué zona de {CIUDAD} busca. "
            f"Mostrá las opciones numeradas: {', '.join(f'{i+1}. {z}' for i,z in enumerate(ZONAS_LIST))}. "
            f"Agregá opción extra al final: 'Otra zona / No lo sé aún'. Español neutro. Máx 7 líneas."
        ),
        "presupuesto": (
            f"Generá una pregunta amable para preguntarle{nombre_txt} su rango de presupuesto en {MONEDA}. "
            f"Opciones: 1. Menos de 50K, 2. 50K-100K, 3. 100K-200K, 4. Más de 200K, 5. Prefiero hablarlo. "
            f"Español neutro. Máx 6 líneas."
        ),
        "urgencia": (
            f"Generá una pregunta para preguntarle{nombre_txt} cuándo planea concretar. "
            f"Opciones: 1. Lo antes posible (1-3 meses), 2. En los próximos 6 meses, "
            f"3. En el próximo año, 4. Estoy explorando opciones. Español neutro. Máx 5 líneas."
        ),
    }
    respuesta = _gemini(prompts[paso])
    if respuesta:
        return respuesta

    fallbacks = {
        "objetivo": (
            f"¿Qué está buscando{nombre_txt}? 🏠\n\n"
            "¿Desea *comprar* o *alquilar* una propiedad?\n"
            "También puede contarme para qué la necesita (vivir, invertir, negocio...) 😊"
        ),
        "tipo": (
            f"¿Qué tipo de propiedad busca{nombre_txt}? 🏡\n\n"
            "1️⃣ Casa\n2️⃣ Departamento\n3️⃣ Terreno\n4️⃣ Local comercial\n5️⃣ Oficina\n\n"
            "También puede escribirlo libremente."
        ),
        "zona": (
            f"¿En qué zona de {CIUDAD} busca{nombre_txt}? 📍\n\n"
            + zonas_opciones +
            f"\n{len(ZONAS_LIST) + 1}️⃣ Otra zona / No lo sé aún"
        ),
        "presupuesto": (
            f"¿Con qué presupuesto cuenta{nombre_txt}? 💰\n\n"
            f"1️⃣ Menos de 50K {MONEDA}\n2️⃣ 50K-100K\n3️⃣ 100K-200K\n"
            f"4️⃣ Más de 200K\n5️⃣ Prefiero hablarlo con el asesor"
        ),
        "urgencia": (
            f"¿En qué tiempo piensa concretar{nombre_txt}? 🗓️\n\n"
            "1️⃣ 🔥 Lo antes posible (1-3 meses)\n"
            "2️⃣ 📅 En los próximos 6 meses\n"
            "3️⃣ 🗓️ En el próximo año\n"
            "4️⃣ 🔍 Estoy explorando opciones"
        ),
    }
    return fallbacks[paso]


# ─── FORMATEO PROPIEDADES ─────────────────────────────────────────────────────
def _lista_titulos(props: list[dict]) -> str:
    lineas = ["✨ *PROPIEDADES DISPONIBLES*\n"]
    for i, p in enumerate(props, 1):
        precio = p.get("Precio", 0)
        moneda = p.get("Moneda", MONEDA)
        precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar precio"
        estado = p.get("Disponible", "")
        tag = " ⏳ _Reservado_" if "Reservado" in str(estado) else ""
        tipo = p.get("Tipo", "")
        tipo_tag = f" · {tipo}" if tipo else ""
        lineas.append(f"*{i}.* {p.get('Titulo', 'Propiedad')}{tipo_tag} — {precio_str}{tag}")
    lineas.append("\nRespondé con el *número* para ver la ficha completa.")
    lineas.append("*0* Volver al inicio | *#* Hablar con el asesor")
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
    lineas.append(f"\n¿Le interesa esta propiedad?\n*#* Hablar con {NOMBRE_ASESOR} | *0* Ver otras propiedades")
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
MSG_BIENVENIDA = (
    "¡Hola! 👋 Bienvenido/a a *{empresa}*.\n\n"
    "Estoy aquí para ayudarle a encontrar la propiedad ideal en {ciudad}. "
    "Le haré solo *5 preguntas rápidas* para mostrarle exactamente lo que busca. 😊\n\n"
    "¿Me podría decir su nombre?"
)

MSG_SITIO_WEB = (
    "¡Muchas gracias por su interés, {nombre}! 🙏\n\n"
    "Entendemos que aún está explorando opciones — eso está perfecto. "
    "Le invitamos a conocer todo nuestro portafolio de propiedades disponibles.\n\n"
    "{web_line}"
    "Cuando esté listo para dar el siguiente paso, escríbanos y con gusto "
    "lo asesoramos personalmente. ¡Estamos para ayudarle! 🏡"
)

MSG_ASESOR_CONTACTO = (
    "¡Excelente, {nombre}! 🎉\n\n"
    "Nuestro asesor *{asesor}* se pondrá en contacto con usted a la brevedad "
    "para mostrarle las mejores opciones disponibles.\n\n"
    "¡Gracias por confiar en *{empresa}*! 🏠"
)


# ─── FLUJO PRINCIPAL ──────────────────────────────────────────────────────────
def _procesar(telefono: str, texto: str) -> None:
    texto = texto.strip()
    texto_lower = texto.lower()
    sesion = SESIONES.get(telefono, {})
    step = sesion.get("step", "inicio")
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""

    # Comandos globales
    if texto_lower in ("0", "menú", "menu", "inicio", "hola", "hi", "buenas"):
        SESIONES.pop(telefono, None)
        step = "inicio"

    if texto_lower == "#":
        _ir_asesor(telefono, sesion)
        return

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
        _enviar_texto(telefono, _pregunta_dinamica("objetivo", nombre))
        return

    # ── OBJETIVO (comprar/alquilar + para qué) ────────────────────────────────
    if step == "objetivo":
        SESIONES[telefono] = {**sesion, "step": "tipo", "resp_objetivo": texto}
        _enviar_texto(telefono, _pregunta_dinamica("tipo", nombre_corto))
        return

    # ── TIPO DE PROPIEDAD ─────────────────────────────────────────────────────
    if step == "tipo":
        mapa_tipo = {
            "1": "casa", "2": "departamento", "3": "terreno",
            "4": "local", "5": "oficina",
        }
        tipo_detectado = mapa_tipo.get(texto, texto.lower())
        SESIONES[telefono] = {**sesion, "step": "zona", "resp_tipo": tipo_detectado}
        _enviar_texto(telefono, _pregunta_dinamica("zona", nombre_corto))
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
        _enviar_texto(telefono, _pregunta_dinamica("presupuesto", nombre_corto))
        return

    # ── PRESUPUESTO ───────────────────────────────────────────────────────────
    if step == "presupuesto":
        SESIONES[telefono] = {**sesion, "step": "urgencia", "resp_presupuesto": texto}
        _enviar_texto(telefono, _pregunta_dinamica("urgencia", nombre_corto))
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
            operacion = None

        # Registrar lead en Airtable (background)
        threading.Thread(
            target=_at_registrar_lead,
            args=(telefono, nombre, score, tipo, zona, nota), daemon=True
        ).start()

        # Lead frío → derivar a sitio web
        if derivar or score == "frio":
            web_line = f"🌐 *{SITIO_WEB}*\n\n" if SITIO_WEB else ""
            _enviar_texto(telefono, MSG_SITIO_WEB.format(
                nombre=nombre_corto or nombre, web_line=web_line))
            threading.Thread(
                target=_notificar_asesor,
                args=(telefono, sesion_act, calificacion), daemon=True
            ).start()
            return

        # Lead caliente/tibio → buscar propiedades en Airtable
        props = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona)

        if not props:
            _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
                nombre=nombre_corto or nombre,
                asesor=NOMBRE_ASESOR,
                empresa=NOMBRE_EMPRESA,
            ))
            threading.Thread(
                target=_notificar_asesor,
                args=(telefono, sesion_act, calificacion), daemon=True
            ).start()
            return

        # Mostrar lista de propiedades
        SESIONES[telefono] = {**sesion_act, "step": "lista", "props": props,
                              "tipo": tipo, "zona": zona, "operacion": operacion}
        _enviar_texto(telefono,
            f"¡Perfecto, {nombre_corto or nombre}! 🎉 Encontré *{len(props)} propiedad(es)* "
            f"que coinciden con lo que busca:\n")
        _enviar_texto(telefono, _lista_titulos(props))

        threading.Thread(
            target=_notificar_asesor,
            args=(telefono, sesion_act, calificacion), daemon=True
        ).start()
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

    # ── FICHA → ACCIONES ──────────────────────────────────────────────────────
    if step == "ficha":
        props = sesion.get("props", [])
        if texto == "0":
            SESIONES[telefono] = {**sesion, "step": "lista"}
            _enviar_texto(telefono, _lista_titulos(props))
            return
        _enviar_texto(telefono,
            f"*#* Hablar con {NOMBRE_ASESOR} | *0* Ver otras propiedades | *menú* para empezar de nuevo 😊")
        return

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    _enviar_texto(telefono,
        "Disculpe, no entendí su mensaje. 😊\n\n"
        "Escriba *hola* para comenzar una nueva consulta\n"
        "o *#* para hablar directamente con el asesor.")
    SESIONES.pop(telefono, None)


def _ir_asesor(telefono: str, sesion: dict) -> None:
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""
    _enviar_texto(telefono, MSG_ASESOR_CONTACTO.format(
        nombre=nombre_corto or nombre,
        asesor=NOMBRE_ASESOR,
        empresa=NOMBRE_EMPRESA,
    ))
    if NUMERO_ASESOR:
        numero_limpio = re.sub(r"[^0-9]", "", NUMERO_ASESOR)
        _enviar_texto(numero_limpio,
            f"🔔 *{NOMBRE_EMPRESA}*\n\n"
            f"Un cliente solicita hablar con vos:\n"
            f"👤 *{nombre or 'Sin nombre'}*\n"
            f"📱 +{re.sub(r'[^0-9]', '', telefono)}"
        )
    SESIONES[telefono] = {**sesion, "step": "calificado"}


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
