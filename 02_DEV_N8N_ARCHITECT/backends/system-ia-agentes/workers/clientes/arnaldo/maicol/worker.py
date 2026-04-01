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
YCLOUD_API_KEY        = os.environ.get("YCLOUD_API_KEY_MAICOL", "") or os.environ.get("YCLOUD_API_KEY", "")
AIRTABLE_TOKEN        = os.environ.get("AIRTABLE_TOKEN_MAICOL", "") or os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID      = os.environ.get("AIRTABLE_BASE_ID_MAICOL", "appaDT7uwHnimVZLM")
AIRTABLE_TABLE        = "tbly67z1oY8EFQoFj"
AIRTABLE_TABLE_CLIENTES = "tblonoyIMAM5kl2ue"
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


def _at_registrar_cliente(telefono: str, nombre: str, operacion: str = "", tipo: str = "", notas: str = "") -> None:
    from datetime import date
    hoy = date.today().isoformat()
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
    if operacion:
        campos["Operacion"] = operacion.capitalize()
        campos["Estado"] = "calificado"
    if tipo:
        campos["Tipo_Propiedad"] = tipo
    if notas:
        campos["Notas_Bot"] = notas

    if records:
        rec_id = records[0]["id"]
        requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS, json={"fields": campos}, timeout=8)
    else:
        campos["Fecha_WhatsApp"] = hoy
        if "Estado" not in campos:
            campos["Estado"] = "nuevo"
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
Al finalizar, recordá al cliente que puede responder con un número para ver opciones o escribir *menú* para volver al inicio.

Consulta del cliente: {mensaje}"""
        resp = _gemini_client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"[INMO-GEMINI] Error: {e}")
        return (f"Gracias por tu consulta. Para más info escribile a nuestro asesor "
                f"{INMOBILIARIA['asesor']} al {INMOBILIARIA['whatsapp']}. 🏠")


# ─── MENSAJES FIJOS ───────────────────────────────────────────────────────────
MSG_BIENVENIDA = """👋 ¡Hola! Bienvenido a *{nombre}* 🏘️
Somos tu inmobiliaria de confianza en {ciudad}.

Nos especializamos en *Lotes y Terrenos* en venta en Misiones.

¿Qué querés hacer?

1️⃣ Ver *Lotes y Terrenos* disponibles
2️⃣ Hablar con un asesor

Respondé con el número de tu opción. 😊"""

MSG_ZONA = """📍 ¿En qué zona estás buscando?

1️⃣ *San Ignacio*
2️⃣ *Gdor. Roca*
3️⃣ *Apóstoles*
4️⃣ *Leandro N. Alem*
5️⃣ Otra zona / No sé
0️⃣ Volver al inicio

Respondé con el número. 😊"""

MSG_TIPO = """¿Qué tipo de propiedad te interesa?

1️⃣ *Lote*
2️⃣ *Terreno*
3️⃣ Ver todos (Lotes y Terrenos)
4️⃣ Hablar con un asesor
0️⃣ Volver al inicio

Respondé con el número. 😊"""

MSG_ASESOR = (
    "¡Con gusto! 😊 Te ponemos en contacto con nuestro equipo. 👤\n\n"
    "👇 Tocá el enlace para escribirle directamente:\n"
    "{whatsapp_link}\n\n"
    "O aguardá que se comunique con vos en breve.\n\n"
    "¡Gracias por confiar en *Back Urbanizaciones*! 🏠"
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


# ─── PROCESADOR PRINCIPAL ──────────────────────────────────────────────────────
def _procesar_mensaje(telefono: str, texto: str) -> None:
    t = texto.lower().strip()
    sesion = SESIONES.get(telefono, {"step": "bienvenida", "props": [], "operacion": ""})
    step = sesion.get("step", "bienvenida")
    operacion = sesion.get("operacion", "")

    # ── Lead desde formulario web ────────────────────────────────────────────
    if "me registré en el formulario" in t or "me registre en el formulario" in t:
        nombre_match = re.search(r"nombre:\s*(.+)", texto, re.IGNORECASE)
        nombre = nombre_match.group(1).strip() if nombre_match else sesion.get("nombre", "")
        nombre_corto = nombre.split()[0] if nombre else ""
        operacion = "venta" if "comprar" in t else ("alquiler" if "alquil" in t else "")
        zona = None
        for z in ["San Ignacio", "Gdor Roca", "Apóstoles", "Otra Zona"]:
            if z.lower() in t or z.lower().replace("ó", "o") in t:
                zona = z
                break
        tipo_raw = None
        if re.search(r"\blote\b", t):
            tipo_raw = ("Lote", "Lotes")
        elif re.search(r"\bterreno\b", t):
            tipo_raw = ("Terreno", "Terrenos")

        SESIONES[telefono] = {"step": "lista", "props": [], "operacion": "venta",
                               "nombre": nombre, "zona": zona}
        saludo = f"¡Hola {nombre_corto}! " if nombre_corto else "¡Hola! "

        if zona and tipo_raw:
            intro = (f"{saludo}✅ Recibimos tu consulta de *Back Urbanizaciones*.\n\n"
                     f"Buscamos {tipo_raw[1].lower()} disponibles en *{zona}*... 🔍")
            _enviar_texto(telefono, intro)
            _mostrar_lista(telefono, tipo_raw[0], tipo_raw[1], "venta", zona)
        elif zona:
            SESIONES[telefono] = {**SESIONES[telefono], "step": "tipo"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *Back Urbanizaciones*.\n\n"
                f"Buscás en *{zona}*. ¿Qué te interesa?\n\n{MSG_TIPO}")
        else:
            SESIONES[telefono] = {**SESIONES[telefono], "step": "zona"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *Back Urbanizaciones*.\n\n"
                f"¿En qué zona estás buscando?\n\n{MSG_ZONA}")
        return

    # ── Lead viene del formulario web — ya tiene datos precargados ──────────
    if step == "mostrar_props":
        nombre_corto = sesion.get("nombre", "").split()[0] or "!"
        zona  = sesion.get("zona", "")
        tipo  = sesion.get("tipo", "")
        # Primer mensaje que llega: cualquier texto activa el flujo
        tipo_busqueda = tipo.split(",")[0].strip() if tipo else None
        props = _at_buscar_propiedades(tipo=tipo_busqueda, zona=zona if zona != "Otra zona" else None)
        if not props and tipo_busqueda:
            props = _at_buscar_propiedades(zona=zona if zona != "Otra zona" else None)
        SESIONES[telefono] = {**sesion, "step": "lista", "props": props}
        if props:
            _mostrar_lista(telefono, tipo_busqueda or "", "propiedades", "venta", zona)
        else:
            _enviar_texto(telefono,
                f"En este momento no tenemos propiedades disponibles con esos criterios. 😔\n\n"
                f"¿Querés que te avise cuando tengamos? Escribí *asesor* para hablar con {INMOBILIARIA['asesor']}.")
        return

    # ── 0 o saludo → bienvenida ──────────────────────────────────────────────
    if t in ("0", "menu", "menú", "inicio", "volver", "hola", "hi", "hey", "start") or \
       re.search(r"\b(buenos dias|buenas tardes|buenas noches|buen dia)\b", t):
        nombre = sesion.get("nombre", "")
        SESIONES[telefono] = {"step": "bienvenida", "props": [], "operacion": "", "nombre": nombre}
        _at_registrar_cliente(telefono, nombre, notas="Primer contacto por WhatsApp")
        _enviar_texto(telefono, MSG_BIENVENIDA.format(**INMOBILIARIA))
        return

    # ── Palabras de asesor ───────────────────────────────────────────────────
    if t in ("asesor", "humano", "agente", "vendedor", "maicol", "persona", "quiero hablar"):
        _ir_asesor(telefono)
        return

    # ── PASO: bienvenida ─────────────────────────────────────────────────────
    if step == "bienvenida":
        nombre = sesion.get("nombre", "")
        if t in ("1", "ver", "lotes", "terrenos", "terreno", "lote", "comprar", "venta", "quiero comprar"):
            SESIONES[telefono] = {"step": "zona", "props": [], "operacion": "venta", "nombre": nombre}
            _at_registrar_cliente(telefono, nombre, operacion="Venta", notas="Busca lotes/terrenos")
            _enviar_texto(telefono, MSG_ZONA)
        elif t == "2":
            _ir_asesor(telefono)
        else:
            _enviar_texto(telefono, _gemini_respuesta(texto))
        return

    # ── PASO: zona ───────────────────────────────────────────────────────────
    ZONAS = {
        "1": "San Ignacio", "san ignacio": "San Ignacio",
        "2": "Gdor Roca", "gdor roca": "Gdor Roca", "gobernador roca": "Gdor Roca", "roca": "Gdor Roca",
        "3": "Apóstoles", "apostoles": "Apóstoles", "apóstoles": "Apóstoles",
        "4": "Leandro N. Alem", "leandro": "Leandro N. Alem", "alem": "Leandro N. Alem", "l.n. alem": "Leandro N. Alem",
        "5": "Otra Zona", "otra": "Otra Zona", "no se": "Otra Zona", "no sé": "Otra Zona",
    }
    if step == "zona":
        nombre = sesion.get("nombre", "")
        operacion = sesion.get("operacion", "venta")
        zona = ZONAS.get(t, "")
        if zona:
            SESIONES[telefono] = {**sesion, "step": "tipo", "zona": zona}
            _at_registrar_cliente(telefono, nombre, notas=f"Zona: {zona}")
            _enviar_texto(telefono, MSG_TIPO)
        else:
            _enviar_texto(telefono, f"Por favor elegí una opción del 1 al 5.\n\n{MSG_ZONA}")
        return

    # ── PASO: tipo (lote / terreno / todos) ──────────────────────────────────
    if step == "tipo":
        nombre = sesion.get("nombre", "")
        zona = sesion.get("zona", None)
        operacion = sesion.get("operacion", "venta")
        if t in ("1", "terreno", "terrenos", "lote", "lotes"):
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="terreno",
                                  notas=f"Busca terreno en {zona or 'zona no especificada'}")
            _mostrar_lista(telefono, "terreno", "Terrenos", operacion, zona)
        elif t in ("2", "casa", "casas"):
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="casa",
                                  notas=f"Busca casa en {zona or 'zona no especificada'}")
            _mostrar_lista(telefono, "casa", "Casas", operacion, zona)
        elif t in ("3", "todos", "ver todos", "cualquiera", "departamento", "depto"):
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="cualquiera",
                                  notas=f"Busca cualquier tipo en {zona or 'zona no especificada'}")
            props = _at_buscar_propiedades(zona=zona)
            zona_label = f" en {zona}" if zona and zona != "Otra Zona" else ""
            if not props:
                SESIONES[telefono] = {**SESIONES.get(telefono, {}), "step": "zona", "operacion": operacion}
                _enviar_texto(telefono,
                    f"En este momento no tenemos propiedades disponibles{zona_label}. 😔\n\n"
                    f"¿Querés buscar en otra zona?\n\n{MSG_ZONA}")
            else:
                SESIONES[telefono] = {"step": "lista", "props": props, "operacion": operacion, "zona": zona}
                _enviar_texto(telefono, _lista_titulos(props, f"Propiedades Disponibles{zona_label}"))
        elif t == "4":
            _ir_asesor(telefono)
        else:
            _enviar_texto(telefono, _gemini_respuesta(texto))
        return

    # ── PASO: lista de propiedades ───────────────────────────────────────────
    if step == "lista":
        props = sesion.get("props", [])
        if t == "4":
            _ir_asesor(telefono)
        elif re.fullmatch(r"\d+", t):
            idx = int(t) - 1
            if 0 <= idx < len(props):
                _enviar_ficha(telefono, props[idx])
            else:
                _enviar_texto(telefono,
                    f"Elegí un número del 1 al {len(props)}.\n*0* para volver | *4* para hablar con el asesor")
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

    nombre_completo = f"{nombre} {apellido}".strip()
    score = "caliente" if urgencia in ("inmediata", "1-3 meses") else "tibio" if urgencia == "3-6 meses" else "frio"

    # Guardar en Airtable
    hoy = date.today().isoformat()
    url_at = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
    buscar = requests.get(url_at, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []

    # Solo campos que existen en la tabla Clientes de Maicol
    estado_at = "calificado" if score == "caliente" else "nuevo"
    nombre_completo_at = f"{nombre} {apellido}".strip()
    notas = f"Formulario web | Zona: {zona} | Tipo: {tipo} | Objetivo: {operacion} | Presupuesto: {presupuesto} | Plazo: {urgencia} | Score: {score}"
    if nota:
        notas += f" | Nota: {nota}"

    campos = {
        "Nombre": nombre_completo_at,
        "Telefono": telefono,
        "Estado": estado_at,
        "Notas_Bot": notas,
        "Llego_WhatsApp": False,
    }
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
