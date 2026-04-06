"""
Worker — Bot WhatsApp Inmobiliaria Maicol v4
=============================================
Flujo estructurado por pasos + Gemini para texto libre.
Integrado como router en system-ia-agentes.
"""

import os
import re
import time
import requests
from google import genai
from fastapi import APIRouter, Request

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
CLOUDINARY_CLOUD_NAME   = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "")
YCLOUD_API_KEY        = os.environ.get("YCLOUD_API_KEY_MAICOL", "") or os.environ.get("YCLOUD_API_KEY", "")
AIRTABLE_TOKEN        = os.environ.get("AIRTABLE_TOKEN_MAICOL", "") or os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID      = os.environ.get("AIRTABLE_BASE_ID_MAICOL", "appaDT7uwHnimVZLM")
AIRTABLE_TABLE        = "tbly67z1oY8EFQoFj"
AIRTABLE_TABLE_CLIENTES = "tblonoyIMAM5kl2ue"
AIRTABLE_TABLE_ACTIVOS  = os.environ.get("AIRTABLE_TABLE_ACTIVOS_MAICOL", "tblDgQFXLzvbhNiyX")
NUMERO_BOT            = os.environ.get("NUMERO_BOT_MAICOL", "5493764815689")
NUMERO_ASESOR         = os.environ.get("NUMERO_ASESOR_MAICOL", "+5493765384843")

INMOBILIARIA = {
    "nombre":   "Back Urbanizaciones",
    "ciudad":   "San Ignacio, Misiones",
    "asesor":   "un asesor",
    "whatsapp": NUMERO_ASESOR if NUMERO_ASESOR.startswith("+") else f"+{NUMERO_ASESOR}",
    "whatsapp_link": f"https://wa.me/{re.sub(r'[^0-9]', '', NUMERO_ASESOR)}",
}

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

router = APIRouter(prefix="/clientes/arnaldo/maicol", tags=["Maicol — Back Urbanizaciones"])

# ─── SESIONES (in-memory) ─────────────────────────────────────────────────────
SESIONES: dict[str, dict] = {}

# ─── AIRTABLE ─────────────────────────────────────────────────────────────────
AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def _at_registrar_cliente(telefono: str, nombre: str, notas: str = "") -> None:
    from datetime import date
    hoy = date.today().isoformat()
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
    buscar = requests.get(url, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []

    # Campos reales en Airtable: Nombre, Telefono, Estado, Llego_WhatsApp, Notas_Bot, Fecha_WhatsApp
    # Estado valores: no_contactado | contactado | en_negociacion | cerrado | descartado
    campos = {"Telefono": telefono, "Llego_WhatsApp": True}
    if nombre:
        campos["Nombre"] = nombre.strip()
    if notas:
        campos["Notas_Bot"] = notas

    if records:
        rec_id = records[0]["id"]
        campos["Estado"] = "contactado"
        requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS, json={"fields": campos}, timeout=8)
    else:
        campos["Fecha_WhatsApp"] = hoy
        campos["Estado"] = "no_contactado"
        requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)


def _at_buscar_propiedades(tipo: str = None, operacion: str = None, zona: str = None) -> list[dict]:
    filtros = ["OR({Disponible}='✅ Disponible',{Disponible}='⏳ Reservado')"]
    if tipo:
        filtros.append(f"LOWER({{Tipo}})='{tipo.lower()}'")
    if operacion:
        filtros.append(f"LOWER({{Operacion}})='{operacion.lower()}'")
    if zona and zona != "Otra Zona":
        filtros.append(f"{{Zona}}='{zona}'")
    formula = "AND(" + ",".join(filtros) + ")" if len(filtros) > 1 else filtros[0]
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
    params = {"filterByFormula": formula, "maxRecords": 5,
              "sort[0][field]": "Precio", "sort[0][direction]": "asc"}
    try:
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=8)
        return [rec["fields"] for rec in r.json().get("records", [])]
    except Exception as e:
        print(f"[INMO-AT] Error: {e}")
        return []


# ─── YCLOUD ───────────────────────────────────────────────────────────────────
def _normalizar_telefono(tel: str) -> str:
    solo_digitos = re.sub(r'\D', '', tel)
    return f"+{solo_digitos}"


def _typing(msg_id: str) -> None:
    """Muestra 'escribiendo...' en WhatsApp antes de responder."""
    if not YCLOUD_API_KEY or not msg_id:
        return
    try:
        requests.post(
            f"https://api.ycloud.com/v2/whatsapp/inboundMessages/{msg_id}/typingIndicator",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            timeout=5,
        )
        time.sleep(1.2)  # pausa breve para que el usuario vea el indicador
    except Exception:
        pass


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not YCLOUD_API_KEY:
        print(f"[INMO-YCLOUD] Sin key:\n{mensaje}")
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
        print(f"[INMO-YCLOUD] Excepción: {e}")
        return False


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    if not YCLOUD_API_KEY or not url_imagen:
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            json={"from": NUMERO_BOT, "to": telefono, "type": "image",
                  "image": {"link": url_imagen, "caption": caption}},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[INMO-YCLOUD] Excepción imagen: {e}")
        return False


def _enviar_cta_asesor(telefono: str) -> bool:
    """Envía botón CTA interactivo con link directo al WhatsApp del equipo."""
    if not YCLOUD_API_KEY:
        return False
    try:
        wa_link = (
            f"{INMOBILIARIA['whatsapp_link']}"
            f"?text=Hola%2C+me+contacto+desde+el+bot+de+Back+Urbanizaciones+%F0%9F%8F%98%EF%B8%8F"
        )
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            json={
                "from": NUMERO_BOT,
                "to": telefono,
                "type": "interactive",
                "interactive": {
                    "type": "cta_url",
                    "body": {
                        "text": (
                            "¡Con gusto! 😊 Te ponemos en contacto "
                            "con nuestro equipo.\n\n"
                            "Tocá el botón para iniciar una conversación "
                            "directa 👇"
                        )
                    },
                    "action": {
                        "name": "cta_url",
                        "parameters": {
                            "display_text": "💬 Escribirle al equipo",
                            "url": wa_link
                        }
                    }
                }
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            return True
        print(f"[INMO-YCLOUD] CTA status {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[INMO-YCLOUD] CTA excepción: {e}")
        return False


# ─── GEMINI ───────────────────────────────────────────────────────────────────
def _gemini_respuesta(mensaje: str) -> str:
    if not GEMINI_API_KEY:
        return (f"Gracias por tu consulta. Para más información podés hablar con "
                f"nuestro asesor {INMOBILIARIA['asesor']} al {INMOBILIARIA['whatsapp']}. 🏠")
    try:
        prompt = f"""Sos el asistente virtual de {INMOBILIARIA['nombre']}, inmobiliaria en {INMOBILIARIA['ciudad']}, Argentina.
Tu asesor humano se llama {INMOBILIARIA['asesor']} ({INMOBILIARIA['whatsapp']}).

Respondé SOLO consultas sobre propiedades, compra, venta, alquiler o temas inmobiliarios.
Si la pregunta no es del rubro, decí amablemente que solo podés ayudar con temas inmobiliarios.
Sé breve, amigable y profesional. Respondé en español argentino.
Al finalizar, recordá al cliente que puede escribir *menú* para volver al inicio.

Consulta del cliente: {mensaje}"""
        resp = _gemini_client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"[INMO-GEMINI] Error: {e}")
        return (f"Gracias por tu consulta. Para más info escribile a nuestro asesor "
                f"{INMOBILIARIA['asesor']} al {INMOBILIARIA['whatsapp']}. 🏠")


def _gemini_calificar(sesion: dict) -> dict:
    """Usa Gemini para calificar el lead según sus respuestas y devolver score + zona + tipo."""
    if not GEMINI_API_KEY:
        return {"score": "potencial", "zona": None, "tipo": None, "presupuesto": None}
    try:
        respuestas = {
            "nombre": sesion.get("nombre", ""),
            "objetivo": sesion.get("resp_objetivo", ""),
            "zona": sesion.get("resp_zona", ""),
            "presupuesto": sesion.get("resp_presupuesto", ""),
            "urgencia": sesion.get("resp_urgencia", ""),
        }
        prompt = f"""Sos un analista comercial de Back Urbanizaciones, inmobiliaria de lotes en Misiones, Argentina.
Analizá las respuestas de este lead y devolvé un JSON con este formato exacto:
{{
  "score": "caliente|tibio|frio",
  "zona": "San Ignacio|Gdor. Roca|Apóstoles|Leandro N. Alem|null",
  "tipo": "lote|terreno|null",
  "presupuesto_detectado": "alto|medio|bajo|sin_info",
  "derivar_sitio_web": true|false,
  "nota_para_asesor": "texto breve"
}}

Reglas de scoring:
- caliente: tiene presupuesto claro + quiere comprar en menos de 6 meses
- tibio: interesado pero sin urgencia o presupuesto indefinido
- frio: solo curiosidad, sin presupuesto, o en etapa muy temprana → derivar_sitio_web: true

Respuestas del lead:
- Objetivo/para qué busca: "{respuestas['objetivo']}"
- Zona de interés: "{respuestas['zona']}"
- Presupuesto: "{respuestas['presupuesto']}"
- Urgencia / cuándo quiere comprar: "{respuestas['urgencia']}"

Devolvé SOLO el JSON, sin texto adicional."""
        resp = _gemini_client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        import json as _json
        texto = resp.text.strip()
        # Limpiar markdown si Gemini lo agrega
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return _json.loads(texto.strip())
    except Exception as e:
        print(f"[INMO-GEMINI-CALIF] Error: {e}")
        return {"score": "tibio", "zona": None, "tipo": None, "presupuesto_detectado": "sin_info",
                "derivar_sitio_web": False, "nota_para_asesor": "Error en calificación automática"}


def _gemini_texto_dinamico(paso: str, contexto: dict) -> str:
    """Genera mensajes conversacionales naturales según el paso del flujo."""
    if not GEMINI_API_KEY:
        fallbacks = {
            "pregunta_objetivo": "¿Para qué estás buscando el lote? ¿Para vivir, invertir o un emprendimiento? 🏡",
            "pregunta_zona": "¿Tenés alguna zona en mente dentro de Misiones? Por ejemplo San Ignacio, Apóstoles, Gdor. Roca... 📍",
            "pregunta_presupuesto": "¿Tenés pensado un rango de presupuesto? No hace falta que sea exacto, con una idea aproximada está bien 💰",
            "pregunta_urgencia": "¿En qué tiempo estás pensando concretar la compra? ¿Es algo urgente o estás explorando opciones? 🗓️",
        }
        return fallbacks.get(paso, "")
    nombre = contexto.get("nombre", "").split()[0] or ""
    nombre_txt = f", {nombre}" if nombre else ""
    prompts = {
        "pregunta_objetivo": f"Generá una pregunta corta y natural (máx 2 líneas) para preguntarle a {nombre or 'el cliente'} para qué está buscando un lote: ¿para vivir, invertir, construir un negocio? Usá español argentino, tono amigable y cercano, sin ser robótico.",
        "pregunta_zona": f"Generá una pregunta corta (máx 2 líneas) para preguntarle{nombre_txt} en qué zona de Misiones está buscando (mencionar que tenemos en San Ignacio, Apóstoles, Gdor. Roca, Leandro N. Alem). Español argentino, tono natural.",
        "pregunta_presupuesto": f"Generá una pregunta corta (máx 2 líneas) para preguntarle{nombre_txt} si tiene en mente un rango de presupuesto. Aclarar que no hace falta que sea exacto. Español argentino, empático y sin presión.",
        "pregunta_urgencia": f"Generá una pregunta corta (máx 2 líneas) para preguntarle{nombre_txt} en qué tiempo piensa concretar la compra — si es algo que quiere resolver pronto o está explorando. Español argentino, tono liviano.",
    }
    try:
        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite", contents=prompts[paso])
        return resp.text.strip()
    except Exception:
        fallbacks = {
            "pregunta_objetivo": f"¿Para qué estás buscando el lote{nombre_txt}? ¿Para vivir, invertir o un emprendimiento? 🏡",
            "pregunta_zona": f"¿Tenés alguna zona en mente{nombre_txt}? Tenemos opciones en San Ignacio, Apóstoles, Gdor. Roca y más 📍",
            "pregunta_presupuesto": f"¿Tenés en mente un rango de presupuesto{nombre_txt}? No hace falta que sea exacto 💰",
            "pregunta_urgencia": f"¿En qué tiempo estás pensando concretar{nombre_txt}? ¿Es algo que querés resolver pronto o estás explorando? 🗓️",
        }
        return fallbacks.get(paso, "")


# ─── MENSAJES FIJOS ───────────────────────────────────────────────────────────
MSG_BIENVENIDA = """👋 ¡Hola! Soy el asistente virtual de *Back Urbanizaciones* 🏘️

Nos especializamos en lotes y terrenos en *{ciudad}* y alrededores de Misiones.

Antes de mostrarte nuestras opciones, me gustaría hacerte unas preguntas rápidas para encontrar exactamente lo que buscás. ¡Son solo 4 preguntas! 😊

¿Cómo es tu nombre?"""

MSG_ASESOR = (
    "¡Con gusto! 😊 Te ponemos en contacto con nuestro equipo. 👤\n\n"
    "👇 Tocá el enlace para escribirle directamente:\n"
    "{whatsapp_link}\n\n"
    "O aguardá que se comunique con vos en breve.\n\n"
    "¡Gracias por confiar en *Back Urbanizaciones*! 🏠"
)

MSG_SITIO_WEB = (
    "¡Gracias por tu interés, {nombre}! 🙏\n\n"
    "Por ahora te recomendamos visitar nuestro sitio web donde vas a encontrar "
    "todas nuestras propiedades, novedades y financiamiento disponible:\n\n"
    "🌐 *www.backurbanizaciones.com*\n\n"
    "Cuando estés listo para dar el paso, escribinos acá y te asesoramos "
    "personalmente. ¡Siempre es un placer ayudarte! 🏡"
)


# ─── FORMATEO ─────────────────────────────────────────────────────────────────
def _lista_titulos(props: list[dict], label: str) -> str:
    lineas = [f"✨ *{label.upper()} DISPONIBLES*\n"]
    for i, p in enumerate(props, 1):
        precio = p.get("Precio", 0)
        moneda = p.get("Moneda", "USD")
        precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar precio"
        estado = p.get("Disponible", "")
        tag = " ⏳ _Reservado_" if "Reservado" in str(estado) else ""
        lineas.append(f"*{i}.* {p.get('Titulo', 'Propiedad')} — {precio_str}{tag}")
    lineas.append("\nRespondé con el *número* para ver la ficha completa.")
    lineas.append("*0* para volver al inicio | *4* para hablar con el asesor")
    return "\n".join(lineas)


def _ficha_propiedad(p: dict) -> str:
    precio = p.get("Precio", 0)
    moneda = p.get("Moneda", "USD")
    precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar precio"
    estado = p.get("Disponible", "✅ Disponible")
    es_reservado = "Reservado" in str(estado)
    titulo = p.get('Titulo', 'Propiedad')
    lineas = [f"🏠 *{titulo}*"]
    if es_reservado:
        lineas.append("⏳ *RESERVADO* — Podés anotarte por si se libera\n")
    else:
        lineas.append("")
    desc = p.get("Descripcion", "")
    if desc:
        lineas.append(f"{desc}\n")
    lineas.append(f"💰 *Precio:* {precio_str}")
    dorm = p.get("Dormitorios", "")
    if dorm:
        lineas.append(f"🛏 *Dormitorios:* {dorm}")
    metros_c = p.get("Metros_Cubiertos", "")
    metros_t = p.get("Metros_Terreno", "")
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
    lineas.append(f"\n¿Te interesa?\n*4* para hablar con {INMOBILIARIA['asesor']} | *0* para volver al menú")
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


def _mostrar_lista(telefono: str, tipo: str, label: str, operacion: str, zona: str = None) -> None:
    props = _at_buscar_propiedades(tipo=tipo, operacion=operacion, zona=zona)
    zona_label = f" en {zona}" if zona and zona != "Otra Zona" else ""
    if not props:
        SESIONES[telefono] = {**SESIONES.get(telefono, {}), "step": "zona",
                              "operacion": operacion}
        _enviar_texto(telefono,
            f"En este momento no tenemos {label.lower()} disponibles{zona_label}. 😔\n\n"
            f"¿Querés buscar en otra zona?\n\n{MSG_ZONA}")
        return
    SESIONES[telefono] = {"step": "lista", "props": props, "operacion": operacion, "tipo": tipo, "zona": zona}
    _enviar_texto(telefono, _lista_titulos(props, f"{label} en Venta{zona_label}"))


def _ir_asesor(telefono: str) -> None:
    SESIONES[telefono] = {"step": "bienvenida", "props": [], "operacion": ""}
    _enviar_texto(telefono, MSG_ASESOR.format(**INMOBILIARIA))
    # Notificar al asesor
    numero_limpio = re.sub(r"[^0-9]", "", NUMERO_ASESOR)
    _enviar_texto(
        numero_limpio,
        f"🔔 *Lead nuevo en Back Urbanizaciones*\n\nUn cliente quiere hablar con vos:\n*Número:* +{telefono}\n\n_Mensaje enviado automáticamente por el bot._",
    )


# ─── NOTIFICACIÓN ASESOR CON SCORE ────────────────────────────────────────────
def _notificar_asesor_lead(telefono: str, sesion: dict, calificacion: dict) -> None:
    """Notifica a Maicol con el score y datos del lead."""
    nombre = sesion.get("nombre", telefono)
    score = calificacion.get("score", "tibio")
    emoji_score = {"caliente": "🔥", "tibio": "🌡️", "frio": "🧊"}.get(score, "📋")
    nota = calificacion.get("nota_para_asesor", "")
    numero_limpio = re.sub(r"[^0-9]", "", NUMERO_ASESOR)
    msg = (
        f"{emoji_score} *Nuevo Lead — Back Urbanizaciones*\n\n"
        f"👤 *Nombre:* {nombre}\n"
        f"📞 *WhatsApp:* +{telefono}\n"
        f"📊 *Score:* {score.upper()}\n"
        f"🎯 *Objetivo:* {sesion.get('resp_objetivo', '—')}\n"
        f"📍 *Zona:* {sesion.get('resp_zona', '—')}\n"
        f"💰 *Presupuesto:* {sesion.get('resp_presupuesto', '—')}\n"
        f"🗓️ *Urgencia:* {sesion.get('resp_urgencia', '—')}\n"
        f"📝 *Nota:* {nota}"
    )
    _enviar_texto(numero_limpio, msg)


# ─── PROCESADOR PRINCIPAL ──────────────────────────────────────────────────────
def _procesar_mensaje(telefono: str, texto: str) -> None:
    t = texto.lower().strip()
    sesion = SESIONES.get(telefono, {"step": "bienvenida"})
    step = sesion.get("step", "bienvenida")
    nombre = sesion.get("nombre", "")
    nombre_corto = nombre.split()[0] if nombre else ""

    # ── Reset / saludo ───────────────────────────────────────────────────────
    es_saludo = t in ("0", "menu", "menú", "inicio", "volver", "hola", "hi", "hey", "start") or \
        re.search(r"\b(buenos dias|buenas tardes|buenas noches|buen dia)\b", t)
    if es_saludo:
        SESIONES[telefono] = {"step": "pedir_nombre"}
        _at_registrar_cliente(telefono, nombre, notas="Primer contacto por WhatsApp")
        _enviar_texto(telefono, MSG_BIENVENIDA.format(**INMOBILIARIA))
        return

    # ── Pedir asesor en cualquier momento ────────────────────────────────────
    if t in ("asesor", "humano", "agente", "vendedor", "maicol", "persona", "quiero hablar", "hablar con alguien"):
        _ir_asesor(telefono)
        return

    # ── PASO 1: capturar nombre ──────────────────────────────────────────────
    if step == "bienvenida" or step == "pedir_nombre":
        if not texto.strip():
            _enviar_texto(telefono, MSG_BIENVENIDA.format(**INMOBILIARIA))
            return
        # Cualquier texto en este paso = nombre
        nombre = texto.strip().title()
        nombre_corto = nombre.split()[0]
        SESIONES[telefono] = {"step": "objetivo", "nombre": nombre}
        _at_registrar_cliente(telefono, nombre, notas="Primer contacto por WhatsApp")
        pregunta = _gemini_texto_dinamico("pregunta_objetivo", {"nombre": nombre_corto})
        _enviar_texto(telefono, f"¡Hola {nombre_corto}! Qué bueno tenerte por acá 😊\n\n{pregunta}")
        return

    # ── PASO 2: objetivo ────────────────────────────────────────────────────
    if step == "objetivo":
        SESIONES[telefono] = {**sesion, "step": "zona", "resp_objetivo": texto.strip()}
        _at_registrar_cliente(telefono, nombre, notas=f"Objetivo: {texto.strip()}")
        pregunta = _gemini_texto_dinamico("pregunta_zona", {"nombre": nombre_corto})
        _enviar_texto(telefono, pregunta)
        return

    # ── PASO 3: zona ────────────────────────────────────────────────────────
    if step == "zona":
        SESIONES[telefono] = {**sesion, "step": "presupuesto", "resp_zona": texto.strip()}
        _at_registrar_cliente(telefono, nombre, notas=f"Zona: {texto.strip()}")
        pregunta = _gemini_texto_dinamico("pregunta_presupuesto", {"nombre": nombre_corto})
        _enviar_texto(telefono, pregunta)
        return

    # ── PASO 4: presupuesto ─────────────────────────────────────────────────
    if step == "presupuesto":
        SESIONES[telefono] = {**sesion, "step": "urgencia", "resp_presupuesto": texto.strip()}
        pregunta = _gemini_texto_dinamico("pregunta_urgencia", {"nombre": nombre_corto})
        _enviar_texto(telefono, pregunta)
        return

    # ── PASO 5: urgencia → calificar ────────────────────────────────────────
    if step == "urgencia":
        sesion_actualizada = {**sesion, "step": "calificando", "resp_urgencia": texto.strip()}
        SESIONES[telefono] = sesion_actualizada
        _at_registrar_cliente(telefono, nombre,
            notas=f"Urgencia: {texto.strip()} | Pres: {sesion.get('resp_presupuesto','')}")

        _enviar_texto(telefono, f"Perfecto, {nombre_corto}! Dame un segundo que busco las mejores opciones para vos... 🔍")

        # Calificar con Gemini
        calificacion = _gemini_calificar(sesion_actualizada)
        score = calificacion.get("score", "tibio")
        derivar = calificacion.get("derivar_sitio_web", False)

        # Notificar a Maicol siempre
        _notificar_asesor_lead(telefono, sesion_actualizada, calificacion)

        # Registrar score en Airtable
        nota_completa = (
            f"Score: {score} | Obj: {sesion_actualizada.get('resp_objetivo','')} | "
            f"Zona: {sesion_actualizada.get('resp_zona','')} | "
            f"Pres: {sesion_actualizada.get('resp_presupuesto','')} | "
            f"Urgencia: {sesion_actualizada.get('resp_urgencia','')}"
        )
        _at_registrar_cliente(telefono, nombre, notas=nota_completa)

        if derivar or score == "frio":
            # Lead frío → derivar al sitio web amablemente
            SESIONES[telefono] = {**sesion_actualizada, "step": "derivado"}
            _enviar_texto(telefono, MSG_SITIO_WEB.format(nombre=nombre_corto))
            return

        # Lead caliente o tibio → mostrar propiedades
        zona_detectada = calificacion.get("zona")
        tipo_detectado = calificacion.get("tipo")

        # Detectar zona desde la respuesta libre si Gemini no la extrajo
        if not zona_detectada:
            resp_zona = sesion_actualizada.get("resp_zona", "").lower()
            for z in ["San Ignacio", "Gdor. Roca", "Apóstoles", "Leandro N. Alem"]:
                if z.lower().replace(".", "") in resp_zona or z.lower().split()[0] in resp_zona:
                    zona_detectada = z
                    break

        props = _at_buscar_propiedades(tipo=tipo_detectado, zona=zona_detectada)
        if not props:
            props = _at_buscar_propiedades()  # fallback: mostrar todo

        if not props:
            SESIONES[telefono] = {**sesion_actualizada, "step": "sin_stock"}
            _enviar_texto(telefono,
                f"En este momento no tenemos stock disponible con esas características, {nombre_corto}. 😔\n\n"
                f"Pero no te preocupes — le aviso a nuestro asesor para que te contacte personalmente "
                f"con las opciones que mejor se adapten a vos. ¡Ya te escribimos! 🙌")
            return

        zona_label = f" en {zona_detectada}" if zona_detectada else ""
        intro = (
            f"¡Encontré algunas opciones{zona_label} que pueden interesarte, {nombre_corto}! 🎉\n\n"
            if score == "caliente"
            else f"Te muestro algunas opciones disponibles{zona_label}, {nombre_corto} 🏘️\n\n"
        )
        SESIONES[telefono] = {**sesion_actualizada, "step": "lista", "props": props,
                              "operacion": "venta", "zona": zona_detectada}
        _enviar_texto(telefono, intro + _lista_titulos(props, f"Lotes y Terrenos{zona_label}"))
        return

    # ── PASO: lista de propiedades ───────────────────────────────────────────
    if step == "lista":
        props = sesion.get("props", [])
        if re.fullmatch(r"\d+", t) and t != "0":
            idx = int(t) - 1
            if 0 <= idx < len(props):
                _enviar_ficha(telefono, props[idx])
                SESIONES[telefono] = {**sesion, "step": "ficha"}
            else:
                _enviar_texto(telefono, f"Elegí un número del 1 al {len(props)} para ver la ficha.")
        elif t in ("asesor", "hablar", "quiero", "me interesa", "info"):
            _ir_asesor(telefono)
        else:
            _enviar_texto(telefono, _gemini_respuesta(texto))
        return

    # ── PASO: ficha (después de ver una propiedad) ───────────────────────────
    if step == "ficha":
        if t in ("si", "sí", "me interesa", "quiero", "más info", "mas info", "interesa"):
            _ir_asesor(telefono)
        elif t == "0" or t in ("volver", "lista", "ver más", "ver mas"):
            props = sesion.get("props", [])
            zona = sesion.get("zona")
            zona_label = f" en {zona}" if zona else ""
            SESIONES[telefono] = {**sesion, "step": "lista"}
            _enviar_texto(telefono, _lista_titulos(props, f"Lotes y Terrenos{zona_label}"))
        else:
            _enviar_texto(telefono, _gemini_respuesta(texto))
        return

    # ── Fallback ─────────────────────────────────────────────────────────────
    _enviar_texto(telefono, _gemini_respuesta(texto))


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────
@router.post("/whatsapp")
async def procesar_whatsapp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detalle": "body no es JSON válido"}

    msg = body.get("whatsappInboundMessage") or body
    telefono = str(msg.get("from") or body.get("from") or body.get("telefono") or "")
    if telefono:
        digitos = re.sub(r"\D", "", telefono)
        telefono = f"+{digitos}"

    msg_type = msg.get("type", "text")
    texto = ""
    if msg_type == "text":
        text_obj = msg.get("text") or {}
        texto = text_obj.get("body", "") if isinstance(text_obj, dict) else str(text_obj)
    elif msg_type == "button":
        btn = msg.get("button") or {}
        texto = btn.get("text", btn.get("payload", ""))
    elif msg_type == "interactive":
        inter = msg.get("interactive") or {}
        tipo_inter = inter.get("type", "")
        if tipo_inter == "button_reply":
            texto = inter.get("button_reply", {}).get("title", "")
        elif tipo_inter == "list_reply":
            texto = inter.get("list_reply", {}).get("title", "")
    elif msg_type in ("image", "audio", "video", "document", "sticker"):
        return {"status": "ignorado", "razon": f"media type: {msg_type}"}

    if not telefono or not texto:
        return {"status": "ignorado", "razon": "sin telefono o texto"}

    # Capturar nombre del cliente desde YCloud
    customer_profile = msg.get("customerProfile") or msg.get("whatsappContact") or body.get("customerProfile") or {}
    raw_name = customer_profile.get("name") or customer_profile.get("displayName") or ""
    sesion = SESIONES.get(telefono, {})
    if raw_name and not sesion.get("nombre"):
        sesion["nombre"] = raw_name
        SESIONES[telefono] = sesion

    # Mostrar "escribiendo..." antes de procesar
    msg_id = msg.get("id") or body.get("id") or ""
    _typing(msg_id)

    _procesar_mensaje(telefono, texto)
    return {"status": "ok", "telefono": telefono, "texto": texto}


@router.get("/propiedades")
def ver_propiedades(tipo: str = None):
    props = _at_buscar_propiedades(tipo=tipo)
    return {"total": len(props), "propiedades": props}


@router.get("/crm/propiedades")
def crm_propiedades():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
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
    return {"records": records}


@router.post("/crm/propiedades")
async def crm_crear_propiedad(request: Request):
    """Crea una nueva propiedad en Airtable."""
    data = await request.json()
    fields = data.get("fields", None) or data
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        from fastapi import HTTPException
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.patch("/crm/propiedades/{record_id}")
async def crm_editar_propiedad(record_id: str, request: Request):
    """Actualiza una propiedad existente en Airtable."""
    data = await request.json()
    fields = data.get("fields", None) or data
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        from fastapi import HTTPException
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.get("/crm/clientes")
def crm_clientes():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
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
    return {"records": records}


@router.post("/crm/clientes")
async def crm_crear_cliente(request: Request):
    """Crea un nuevo cliente en Airtable desde el CRM."""
    from fastapi import HTTPException
    data = await request.json()
    campos_validos = {
        "Nombre", "Apellido", "Telefono", "Email", "Operacion", "Tipo_Propiedad",
        "Presupuesto", "Zona", "Estado", "Llego_WhatsApp", "Notas_Bot", "Fuente",
    }
    campos = {k: v for k, v in data.items() if k in campos_validos and v is not None}
    estados_validos = {"no_contactado", "contactado", "en_negociacion", "cerrado", "descartado"}
    campos.setdefault("Estado", "no_contactado")
    if campos["Estado"] not in estados_validos:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {campos['Estado']}")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.patch("/crm/clientes/{record_id}")
async def crm_editar_cliente(record_id: str, request: Request):
    """Actualiza un cliente en Airtable desde el CRM."""
    from fastapi import HTTPException
    data = await request.json()
    # Aceptar campos directamente o bajo 'fields'
    fields = data.get("fields", data)
    # Validar Estado si viene
    estados_validos = {"no_contactado", "contactado", "en_negociacion", "cerrado", "descartado"}
    if "Estado" in fields and fields["Estado"] not in estados_validos:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {fields['Estado']}")
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok", "record": r.json()}


@router.post("/crm/upload-imagen")
async def crm_upload_imagen(request: Request):
    """Recibe imagen multipart, la sube a Cloudinary y devuelve la URL."""
    from fastapi import HTTPException
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_UPLOAD_PRESET:
        raise HTTPException(status_code=500, detail="Cloudinary no configurado")
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="No se recibió ningún archivo")
    content = await file.read()
    resp = requests.post(
        f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
        files={"file": (file.filename, content, file.content_type)},
        data={"upload_preset": CLOUDINARY_UPLOAD_PRESET, "folder": "clientes/maicol"},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
    return {"url": resp.json().get("secure_url")}


# ─── EMAIL ALERTAS (llamado por n8n workflow de vencimientos) ─────────────────

@router.post("/send-email-alerta")
async def send_email_alerta(request: Request):
    """Envía email de alerta de vencimiento al cliente via SMTP de backurbanizaciones.com."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from fastapi import HTTPException

    SMTP_HOST     = os.environ.get("SMTP_HOST_MAICOL", "mail.backurbanizaciones.com")
    SMTP_PORT     = int(os.environ.get("SMTP_PORT_MAICOL", "465"))
    SMTP_USER     = os.environ.get("SMTP_USER_MAICOL", "info@backurbanizaciones.com")
    SMTP_PASS     = os.environ.get("SMTP_PASS_MAICOL", "")

    data = await request.json()
    to      = data.get("to", "")
    nombre  = data.get("nombre", "Cliente")
    lote    = data.get("lote", "")
    venc    = data.get("venc", "")
    monto   = data.get("monto", "")
    cuotas  = data.get("cuotas", "")
    dias    = data.get("dias_restantes", 3)

    if not to:
        raise HTTPException(status_code=400, detail="Email destino requerido")
    if not SMTP_PASS:
        raise HTTPException(status_code=500, detail="SMTP no configurado")

    alerta_txt = "vence HOY" if dias == 0 else (f"venció hace {abs(dias)} día(s)" if dias < 0 else f"vence en {dias} día(s)")

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;background:#f8f9fa;padding:24px;border-radius:12px;">
      <div style="background:#0A261A;padding:20px 24px;border-radius:8px 8px 0 0;text-align:center;">
        <h2 style="color:#E5B239;margin:0;font-size:1.3rem;">⚠️ Recordatorio de Pago</h2>
        <p style="color:#A6C2B4;margin:4px 0 0;font-size:0.85rem;">Back Urbanizaciones</p>
      </div>
      <div style="background:#fff;padding:28px 24px;border-radius:0 0 8px 8px;border:1px solid #e5e7eb;">
        <p style="color:#374151;font-size:1rem;">Hola <strong>{nombre}</strong>,</p>
        <p style="color:#374151;">Te recordamos que tu cuota <strong>{cuotas}</strong> de <strong>{monto}</strong> <strong>{alerta_txt}</strong>.</p>
        <div style="background:#FEF3C7;border:1px solid #FCD34D;border-radius:8px;padding:16px;margin:20px 0;">
          <p style="margin:0;color:#92400E;font-size:0.95rem;">
            📋 <strong>Lote:</strong> {lote}<br/>
            💰 <strong>Monto:</strong> {monto}<br/>
            📅 <strong>Fecha de vencimiento:</strong> {venc}
          </p>
        </div>
        <p style="color:#374151;">Para realizar el pago o consultar, comunicate con nosotros:</p>
        <p style="color:#374151;">📞 WhatsApp: <a href="https://wa.me/5493765384843" style="color:#0A261A;">+54 9 376 538-4843</a></p>
        <p style="color:#6b7280;font-size:0.8rem;margin-top:24px;border-top:1px solid #e5e7eb;padding-top:12px;">
          Back Urbanizaciones — San Ignacio, Misiones<br/>
          Este es un mensaje automático, por favor no respondas a este correo.
        </p>
      </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⚠️ Recordatorio: tu cuota {alerta_txt} — Back Urbanizaciones"
    msg["From"]    = f"Back Urbanizaciones <{SMTP_USER}>"
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to, msg.as_string())
        return {"status": "ok", "to": to}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMTP error: {str(e)}")


# ─── CLIENTES ACTIVOS (compradores con cuotas) ────────────────────────────────

def _calcular_estado_pago(fields: dict) -> str:
    """Calcula el estado de pago automáticamente según la fecha de vencimiento."""
    from datetime import date, timedelta
    # Si ya pagó todo → Cancelado
    total = fields.get("Cuotas_Total")
    pagadas = fields.get("Cuotas_Pagadas")
    if total and pagadas is not None and int(pagadas) >= int(total):
        return "Cancelado"
    venc_str = fields.get("Proximo_Vencimiento")
    if not venc_str:
        return fields.get("Estado_Pago", "Al día")
    try:
        venc = date.fromisoformat(venc_str)
        hoy = date.today()
        if venc >= hoy:
            return "Al día"
        dias_vencido = (hoy - venc).days
        if dias_vencido <= 90:
            return "Atrasado"
        return "En mora"
    except Exception:
        return fields.get("Estado_Pago", "Al día")


@router.get("/crm/activos")
def crm_activos():
    """Lista todos los clientes activos con sus cuotas. Estado_Pago calculado automáticamente."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}"
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=10)
        data = r.json()
        for rec in data.get("records", []):
            fields = rec["fields"]
            # Sobreescribir Estado_Pago con el calculado automáticamente
            fields["Estado_Pago"] = _calcular_estado_pago(fields)
            records.append({"id": rec["id"], **fields})
        offset = data.get("offset")
        if not offset:
            break
    return {"records": records}


@router.post("/crm/activos")
async def crm_crear_activo(request: Request):
    """Crea un nuevo cliente activo en Airtable."""
    from fastapi import HTTPException
    data = await request.json()
    fields = data.get("fields", data)
    # Limpiar campos None/vacíos
    fields = {k: v for k, v in fields.items() if v is not None and v != ""}
    # Calcular Estado_Pago automáticamente
    fields["Estado_Pago"] = _calcular_estado_pago(fields)
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}"
    r = requests.post(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.patch("/crm/activos/{record_id}")
async def crm_editar_activo(record_id: str, request: Request):
    """Actualiza un cliente activo en Airtable. Estado_Pago recalculado automáticamente."""
    from fastapi import HTTPException
    data = await request.json()
    fields = data.get("fields", data)
    fields = {k: v for k, v in fields.items() if v is not None and v != ""}
    # Recalcular Estado_Pago automáticamente — ignorar el que manda el frontend
    fields["Estado_Pago"] = _calcular_estado_pago(fields)
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}/{record_id}"
    r = requests.patch(url, headers=AT_HEADERS, json={"fields": fields}, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@router.delete("/crm/activos/{record_id}")
async def crm_eliminar_activo(record_id: str):
    """Elimina un cliente activo de Airtable."""
    from fastapi import HTTPException
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ACTIVOS}/{record_id}"
    r = requests.delete(url, headers=AT_HEADERS, timeout=10)
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"status": "ok"}


@router.get("/config")
def ver_config():
    """Diagnóstico: muestra qué variables de entorno están cargadas (sin exponer valores)."""
    token_ok = bool(AIRTABLE_TOKEN)
    token_len = len(AIRTABLE_TOKEN) if AIRTABLE_TOKEN else 0
    return {
        "airtable_token_ok": token_ok,
        "airtable_token_length": token_len,
        "airtable_token_prefix": AIRTABLE_TOKEN[:8] if token_ok else None,
        "airtable_base_id": AIRTABLE_BASE_ID,
        "airtable_table_clientes": AIRTABLE_TABLE_CLIENTES,
        "ycloud_key_ok": bool(YCLOUD_API_KEY),
        "numero_bot": NUMERO_BOT,
        "numero_asesor": NUMERO_ASESOR,
        "tabla_clientes": AIRTABLE_TABLE_CLIENTES,
    }


@router.post("/lead")
async def recibir_lead(request: Request):
    """Recibe lead del formulario web — guarda en Airtable, activa bot y notifica asesor."""
    from datetime import date
    data = await request.json()

    nombre    = data.get("nombre", "").strip()
    apellido  = data.get("apellido", "").strip()
    telefono  = _normalizar_telefono(data.get("telefono", ""))
    zona      = data.get("zona", "")
    tipo      = data.get("tipo", "")
    operacion = data.get("operacion", "")
    presupuesto = data.get("presupuesto", "")
    urgencia  = data.get("urgencia", "")
    nota      = data.get("nota", "")
    email     = data.get("email", "").strip()

    nombre_completo = f"{nombre} {apellido}".strip()
    score = "caliente" if urgencia in ("inmediata", "1-3 meses") else "tibio" if urgencia == "3-6 meses" else "frio"

    # Guardar en Airtable
    hoy = date.today().isoformat()
    url_at = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
    buscar = requests.get(url_at, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []

    # Mapear valores del formulario a los valores reales de Airtable
    # Operacion: formulario manda construir-vivienda/inversion/etc → Airtable: Todo|venta|alquiler
    op_map = {"venta": "venta", "compra": "venta", "alquiler": "alquiler",
              "construir-vivienda": "Todo", "inversion": "Todo",
              "emprendimiento": "Todo", "segunda-residencia": "Todo"}
    operacion_at = op_map.get(operacion.lower(), "Todo") if operacion else None

    # Tipo_Propiedad: formulario puede mandar lista — tomar primero
    tipo_limpio = tipo.split(",")[0].strip() if isinstance(tipo, str) else (tipo[0] if isinstance(tipo, list) and tipo else "")
    # Mapear a valores exactos del singleSelect de Airtable
    tipo_map = {
        "lote residencial": "Lote residencial",
        "lote comercial":   "Lote comercial",
        "lote en esquina":  "Lote en esquina",
        "terreno rural":    "Terreno rural",
        "terreno":          "Terreno rural",
        "casa":             "Casa",
        "departamento":     "Departamento",
        "lote":             "Lote residencial",
    }
    tipo_at = tipo_map.get(tipo_limpio.lower()) if tipo_limpio else None

    # Presupuesto: el formulario ya manda string legible — mapear a singleSelect Airtable
    pres_map = {
        "hasta usd 20.000":   "hata_50k",
        "hasta usd 50.000":   "hata_50k",
        "hasta usd 80.000":   "50k_100k",
        "hasta usd 120.000":  "100k_200k",
        "hasta usd 200.000":  "100k_200k",
        "más de usd 200.000": "mas_200k",
        "mas de usd 200.000": "mas_200k",
        # también acepta valores crudos por si acaso
        "hata_50k": "hata_50k", "50k_100k": "50k_100k",
        "100k_200k": "100k_200k", "mas_200k": "mas_200k",
    }
    presupuesto_at = pres_map.get((presupuesto or "").lower().strip()) or None

    # Zona: verificar que sea un valor válido
    zonas_validas = {"San Ignacio", "Gdor Roca", "Apóstoles", "Leandro N. Alem"}
    zona_at = zona if zona in zonas_validas else None

    estado_at = "contactado"
    notas = f"Formulario web | Zona: {zona} | Tipo: {tipo} | Objetivo: {operacion} | Presupuesto: {presupuesto} | Plazo: {urgencia} | Score: {score}"
    if nota:
        notas += f" | Nota: {nota}"

    campos = {
        "Nombre": nombre.strip() or nombre_completo,
        "Telefono": telefono,
        "Estado": estado_at,
        "Notas_Bot": notas,
        "Llego_WhatsApp": False,
    }
    if apellido:
        campos["Apellido"] = apellido.strip()
    if operacion_at:
        campos["Operacion"] = operacion_at
    if tipo_at:
        campos["Tipo_Propiedad"] = tipo_at
    if presupuesto_at:
        campos["Presupuesto"] = presupuesto_at
    if zona_at:
        campos["Zona"] = zona_at
    if email:
        campos["Email"] = email
    if records:
        r_at = requests.patch(f"{url_at}/{records[0]['id']}", headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        print(f"[MAICOL-LEAD] PATCH Airtable {r_at.status_code}: {r_at.text[:200]}")
    else:
        campos["Fecha_WhatsApp"] = hoy
        r_at = requests.post(url_at, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        print(f"[MAICOL-LEAD] POST Airtable {r_at.status_code}: {r_at.text[:200]}")

    # Pre-cargar sesión para que el bot no repita preguntas
    SESIONES[telefono] = {
        "step": "mostrar_props",
        "nombre": nombre_completo,
        "operacion": operacion or "Compra",
        "tipo": tipo,
        "zona": zona,
        "presupuesto": presupuesto,
        "urgencia": urgencia,
        "score": score,
        "ts": time.time(),
    }

    # Mensaje de bienvenida al lead
    msg_bienvenida = (
        f"¡Hola {nombre}! 👋 Gracias por completar el formulario de *Back Urbanizaciones*.\n\n"
        f"Vi que buscás un *{tipo or 'lote'}* en *{zona or 'Misiones'}*"
        f"{f' — objetivo: {operacion}' if operacion else ''}.\n\n"
        f"💰 Presupuesto: {presupuesto or 'a consultar'}\n"
        f"⏱ Plazo: {urgencia or '-'}\n\n"
        f"Enseguida te muestro las opciones disponibles 🌿"
    )
    _enviar_texto(telefono, msg_bienvenida)

    # Mostrar propiedades — si el tipo tiene comas (multi-select), tomar solo el primero
    tipo_busqueda = tipo.split(",")[0].strip() if tipo else None
    props = _at_buscar_propiedades(tipo=tipo_busqueda, zona=zona if zona != "Otra zona" else None)
    # Fallback: buscar sin filtro de tipo si no hay resultados
    if not props and tipo_busqueda:
        props = _at_buscar_propiedades(zona=zona if zona != "Otra zona" else None)
    if props:
        _mostrar_lista(telefono, tipo_busqueda or "lote", "lotes disponibles", "Venta", zona)
    else:
        _enviar_texto(telefono, "📋 Estamos actualizando nuestro inventario. Un asesor te contacta en breve con las opciones disponibles.")

    # Notificar al asesor
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
            f"_El bot ya le escribió y le está mostrando lotes._"
        )

    return {"status": "ok", "score": score, "telefono": telefono}
