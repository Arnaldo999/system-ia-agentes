"""
Worker DEMO — Bot WhatsApp Inmobiliaria
========================================
Template genérico para cualquier inmobiliaria.
NUNCA editar este archivo para un cliente real.
Para nuevo cliente: copiar carpeta, renombrar, configurar env vars propias.

Variables de entorno requeridas (prefijo INMO_DEMO_):
  INMO_DEMO_NOMBRE          Nombre de la inmobiliaria       (def: "System IA Inmobiliaria Demo")
  INMO_DEMO_CIUDAD          Ciudad/zona general             (def: "tu ciudad")
  INMO_DEMO_ASESOR          Nombre del asesor humano        (def: "el asesor")
  INMO_DEMO_NUMERO_BOT      Número WhatsApp del bot         (def: "")
  INMO_DEMO_NUMERO_ASESOR   Número WhatsApp del asesor      (def: "")
  INMO_DEMO_YCLOUD_KEY      API Key YCloud                  (def: YCLOUD_API_KEY general)
  INMO_DEMO_AIRTABLE_BASE   Base ID Airtable                (def: "")
  INMO_DEMO_TABLE_PROPS     ID tabla propiedades            (def: "")
  INMO_DEMO_TABLE_CLIENTES  ID tabla clientes               (def: "")
  INMO_DEMO_ZONAS           Zonas separadas por coma        (def: "Zona 1,Zona 2,Zona 3")

  GEMINI_API_KEY            API Key Gemini (compartida)
  AIRTABLE_TOKEN            Token Airtable (compartido)
"""

import os
import re
import requests
import google.generativeai as genai
from fastapi import APIRouter, Request

# ─── CONFIG — todo desde env vars ─────────────────────────────────────────────
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
AIRTABLE_TOKEN  = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
YCLOUD_API_KEY  = os.environ.get("INMO_DEMO_YCLOUD_KEY", "") or os.environ.get("YCLOUD_API_KEY", "")

NOMBRE_INMO     = os.environ.get("INMO_DEMO_NOMBRE",        "System IA Inmobiliaria Demo")
CIUDAD          = os.environ.get("INMO_DEMO_CIUDAD",         "tu ciudad")
NOMBRE_ASESOR   = os.environ.get("INMO_DEMO_ASESOR",         "el asesor")
NUMERO_BOT      = os.environ.get("INMO_DEMO_NUMERO_BOT",     "")
NUMERO_ASESOR   = os.environ.get("INMO_DEMO_NUMERO_ASESOR",  "")

AIRTABLE_BASE_ID        = os.environ.get("INMO_DEMO_AIRTABLE_BASE",    "")
AIRTABLE_TABLE_PROPS    = os.environ.get("INMO_DEMO_TABLE_PROPS",       "")
AIRTABLE_TABLE_CLIENTES = os.environ.get("INMO_DEMO_TABLE_CLIENTES",    "")

_zonas_raw = os.environ.get("INMO_DEMO_ZONAS", "Zona 1,Zona 2,Zona 3")
ZONAS_LIST = [z.strip() for z in _zonas_raw.split(",") if z.strip()]

INMO = {
    "nombre":   NOMBRE_INMO,
    "ciudad":   CIUDAD,
    "asesor":   NOMBRE_ASESOR,
    "whatsapp": NUMERO_ASESOR if NUMERO_ASESOR.startswith("+") else f"+{re.sub(r'D', '', NUMERO_ASESOR)}" if NUMERO_ASESOR else "",
}

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

router = APIRouter(prefix="/inmobiliaria-demo", tags=["Inmobiliaria Demo"])

# ─── SESIONES (in-memory) ─────────────────────────────────────────────────────
SESIONES: dict[str, dict] = {}

# ─── AIRTABLE ─────────────────────────────────────────────────────────────────
AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def _at_registrar_cliente(telefono: str, nombre: str, operacion: str = "", tipo: str = "", notas: str = "") -> None:
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_CLIENTES:
        return
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
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return []
    filtros = ["OR({Disponible}='✅ Disponible',{Disponible}='⏳ Reservado')"]
    if tipo:
        filtros.append(f"LOWER({{Tipo}})='{tipo.lower()}'")
    if operacion:
        filtros.append(f"LOWER({{Operacion}})='{operacion.lower()}'")
    if zona and zona != "Otra Zona":
        filtros.append(f"{{Zona}}='{zona}'")
    formula = "AND(" + ",".join(filtros) + ")" if len(filtros) > 1 else filtros[0]
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_PROPS}"
    params = {"filterByFormula": formula, "maxRecords": 5,
              "sort[0][field]": "Precio", "sort[0][direction]": "asc"}
    try:
        r = requests.get(url, headers=AT_HEADERS, params=params, timeout=8)
        return [rec["fields"] for rec in r.json().get("records", [])]
    except Exception as e:
        print(f"[DEMO-AT] Error: {e}")
        return []


# ─── YCLOUD ───────────────────────────────────────────────────────────────────
def _normalizar_telefono(tel: str) -> str:
    solo_digitos = re.sub(r'\D', '', tel)
    return f"+{solo_digitos}"


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not YCLOUD_API_KEY or not NUMERO_BOT:
        print(f"[DEMO-YCLOUD] Sin key/número. Mensaje:\n{mensaje}")
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
        print(f"[DEMO-YCLOUD] Excepción: {e}")
        return False


def _enviar_imagen(telefono: str, url_imagen: str, caption: str = "") -> bool:
    if not YCLOUD_API_KEY or not NUMERO_BOT or not url_imagen:
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
        print(f"[DEMO-YCLOUD] Excepción imagen: {e}")
        return False


# ─── GEMINI ───────────────────────────────────────────────────────────────────
def _gemini_respuesta(mensaje: str) -> str:
    if not GEMINI_API_KEY:
        return (f"Gracias por tu consulta. Para más información podés hablar con "
                f"nuestro asesor {INMO['asesor']} al {INMO['whatsapp']}. 🏠")
    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        prompt = f"""Sos el asistente virtual de {INMO['nombre']}, inmobiliaria en {INMO['ciudad']}.
Tu asesor humano se llama {INMO['asesor']} ({INMO['whatsapp']}).

Respondé SOLO consultas sobre propiedades, compra, venta, alquiler o temas inmobiliarios.
Si la pregunta no es del rubro, decí amablemente que solo podés ayudar con temas inmobiliarios.
Sé breve, amigable y profesional. Respondé en español.
Al finalizar, recordá al cliente que puede responder con un número para ver opciones o escribir *menú* para volver al inicio.

Consulta del cliente: {mensaje}"""
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"[DEMO-GEMINI] Error: {e}")
        return (f"Gracias por tu consulta. Para más info escribile a nuestro asesor "
                f"{INMO['asesor']} al {INMO['whatsapp']}. 🏠")


# ─── MENSAJES DINÁMICOS ────────────────────────────────────────────────────────
def _msg_bienvenida() -> str:
    return (f"👋 ¡Hola! Bienvenido a *{INMO['nombre']}* 🏘️\n"
            f"Somos tu inmobiliaria de confianza en {INMO['ciudad']}.\n\n"
            f"¿Qué estás buscando?\n\n"
            f"1️⃣ *Comprar* una propiedad\n"
            f"2️⃣ *Alquilar* una propiedad\n"
            f"3️⃣ Hablar con un asesor\n\n"
            f"Respondé con el número de tu opción. 😊")


def _msg_zona() -> str:
    lineas = ["📍 ¿En qué zona estás buscando?\n"]
    for i, zona in enumerate(ZONAS_LIST, 1):
        lineas.append(f"{i}️⃣ *{zona}*")
    lineas.append(f"{len(ZONAS_LIST)+1}️⃣ Otra zona / No sé")
    lineas.append("0️⃣ Volver al inicio\n")
    lineas.append("Respondé con el número. 😊")
    return "\n".join(lineas)


MSG_TIPO = """¿Qué tipo de propiedad te interesa?

1️⃣ *Casa*
2️⃣ *Departamento*
3️⃣ *Terreno*
4️⃣ Hablar con un asesor
0️⃣ Volver al inicio

Respondé con el número. 😊"""

MSG_ASESOR = ("¡Perfecto! Te conectamos con nuestro asesor. 👤\n\n"
              "Podés escribirle directamente al *{whatsapp}* "
              "o aguardá que te contacte en breve. ¡Gracias por elegirnos! 🏠")


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
    lineas.append("*0* para volver | *4* para hablar con el asesor")
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
    lineas.append(f"\n¿Te interesa?\n*4* para hablar con {INMO['asesor']} | *0* para volver al menú")
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
    op_label = "en Venta" if operacion == "venta" else "en Alquiler"
    zona_label = f" en {zona}" if zona and zona != "Otra Zona" else ""
    if not props:
        SESIONES[telefono] = {**SESIONES.get(telefono, {}), "step": "tipo",
                              "operacion": operacion, "zona": zona}
        _enviar_texto(telefono,
            f"En este momento no tenemos {label.lower()} {op_label.lower()}{zona_label}. 😔\n\n"
            f"¿Querés buscar otro tipo de propiedad?\n\n{MSG_TIPO}")
        return
    SESIONES[telefono] = {"step": "lista", "props": props, "operacion": operacion, "tipo": tipo, "zona": zona}
    _enviar_texto(telefono, _lista_titulos(props, f"{label} {op_label}{zona_label}"))


def _ir_asesor(telefono: str) -> None:
    SESIONES[telefono] = {"step": "bienvenida", "props": [], "operacion": ""}
    _enviar_texto(telefono, MSG_ASESOR.format(**INMO))


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
        for z in ZONAS_LIST:
            if z.lower() in t:
                zona = z
                break
        tipo_raw = None
        if re.search(r"\bcasa\b", t):
            tipo_raw = ("Casa", "Casas")
        elif re.search(r"\bdep(to|artamento)\b", t):
            tipo_raw = ("Departamento", "Departamentos")
        elif re.search(r"\bterreno\b", t):
            tipo_raw = ("Terreno", "Terrenos")

        SESIONES[telefono] = {"step": "lista", "props": [], "operacion": operacion,
                               "nombre": nombre, "zona": zona}
        saludo = f"¡Hola {nombre_corto}! " if nombre_corto else "¡Hola! "
        op_str = "comprar" if operacion == "venta" else ("alquilar" if operacion == "alquiler" else "buscar")

        if operacion and zona and tipo_raw:
            intro = (f"{saludo}✅ Recibimos tu consulta de *{INMO['nombre']}*.\n\n"
                     f"Buscamos {tipo_raw[1].lower()} para *{op_str}* en *{zona}*... 🔍")
            _enviar_texto(telefono, intro)
            _mostrar_lista(telefono, tipo_raw[0], tipo_raw[1], operacion, zona)
        elif operacion and zona:
            SESIONES[telefono] = {**SESIONES[telefono], "step": "tipo"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *{INMO['nombre']}*.\n\n"
                f"Buscás *{op_str}* en *{zona}*. ¿Qué tipo de propiedad te interesa?\n\n{MSG_TIPO}")
        elif operacion:
            SESIONES[telefono] = {**SESIONES[telefono], "step": "zona"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *{INMO['nombre']}*.\n\n"
                f"Veo que querés *{op_str}*. ¿En qué zona?\n\n{_msg_zona()}")
        else:
            SESIONES[telefono] = {**SESIONES[telefono], "step": "bienvenida"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *{INMO['nombre']}*.\n\n{_msg_bienvenida()}")
        return

    # ── 0 o saludo → bienvenida ──────────────────────────────────────────────
    if t in ("0", "menu", "menú", "inicio", "volver", "hola", "hi", "hey", "start") or \
       re.search(r"\b(buenos dias|buenas tardes|buenas noches|buen dia)\b", t):
        nombre = sesion.get("nombre", "")
        SESIONES[telefono] = {"step": "bienvenida", "props": [], "operacion": "", "nombre": nombre}
        _at_registrar_cliente(telefono, nombre, notas="Primer contacto por WhatsApp")
        _enviar_texto(telefono, _msg_bienvenida())
        return

    # ── Palabras de asesor ───────────────────────────────────────────────────
    if t in ("asesor", "humano", "agente", "vendedor", "persona", "quiero hablar"):
        _ir_asesor(telefono)
        return

    # ── PASO: bienvenida ─────────────────────────────────────────────────────
    if step == "bienvenida":
        nombre = sesion.get("nombre", "")
        if t in ("1", "comprar", "compra", "venta", "quiero comprar"):
            SESIONES[telefono] = {"step": "zona", "props": [], "operacion": "venta", "nombre": nombre}
            _at_registrar_cliente(telefono, nombre, operacion="Venta", notas="Busca comprar")
            _enviar_texto(telefono, _msg_zona())
        elif t in ("2", "alquilar", "alquiler", "renta", "quiero alquilar"):
            SESIONES[telefono] = {"step": "zona", "props": [], "operacion": "alquiler", "nombre": nombre}
            _at_registrar_cliente(telefono, nombre, operacion="Alquiler", notas="Busca alquilar")
            _enviar_texto(telefono, _msg_zona())
        elif t == "3":
            _ir_asesor(telefono)
        else:
            _enviar_texto(telefono, _gemini_respuesta(texto))
        return

    # ── PASO: zona ───────────────────────────────────────────────────────────
    if step == "zona":
        nombre = sesion.get("nombre", "")
        # Mapear número a zona
        zona = None
        if t.isdigit():
            idx = int(t) - 1
            if 0 <= idx < len(ZONAS_LIST):
                zona = ZONAS_LIST[idx]
            elif int(t) == len(ZONAS_LIST) + 1:
                zona = "Otra Zona"
        else:
            # Buscar por nombre parcial
            for z in ZONAS_LIST:
                if z.lower() in t or t in z.lower():
                    zona = z
                    break
            if not zona and t in ("otra", "no se", "no sé"):
                zona = "Otra Zona"

        if zona == "Otra Zona":
            SESIONES[telefono] = {**sesion, "step": "tipo", "zona": "Otra Zona"}
            _at_registrar_cliente(telefono, nombre, notas="Zona: Otra Zona")
            _enviar_texto(telefono, MSG_TIPO)
        elif zona:
            SESIONES[telefono] = {**sesion, "step": "tipo", "zona": zona}
            _at_registrar_cliente(telefono, nombre, notas=f"Zona: {zona}")
            _enviar_texto(telefono, MSG_TIPO)
        else:
            _enviar_texto(telefono, f"Por favor elegí una opción válida.\n\n{_msg_zona()}")
        return

    # ── PASO: tipo de propiedad ──────────────────────────────────────────────
    if step == "tipo":
        nombre = sesion.get("nombre", "")
        zona = sesion.get("zona", None)
        if t in ("1", "casa", "casas"):
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="Casa",
                                  notas=f"Busca casa en {operacion}")
            _mostrar_lista(telefono, "Casa", "Casas", operacion, zona)
        elif t in ("2", "depto", "deptos", "departamento", "departamentos", "dpto"):
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="Departamento",
                                  notas=f"Busca departamento en {operacion}")
            _mostrar_lista(telefono, "Departamento", "Departamentos", operacion, zona)
        elif t in ("3", "terreno", "terrenos", "lote", "lotes"):
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="Terreno",
                                  notas=f"Busca terreno en {operacion}")
            _mostrar_lista(telefono, "Terreno", "Terrenos", operacion, zona)
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
        telefono = _normalizar_telefono(telefono)

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

    customer_profile = (msg.get("customerProfile") or msg.get("whatsappContact")
                        or body.get("customerProfile") or {})
    raw_name = customer_profile.get("name") or customer_profile.get("displayName") or ""
    sesion = SESIONES.get(telefono, {})
    if raw_name and not sesion.get("nombre"):
        sesion["nombre"] = raw_name
        SESIONES[telefono] = sesion

    _procesar_mensaje(telefono, texto)
    return {"status": "ok", "telefono": telefono, "texto": texto}


@router.get("/propiedades")
def ver_propiedades(tipo: str = None):
    props = _at_buscar_propiedades(tipo=tipo)
    return {"total": len(props), "propiedades": props}


@router.get("/crm/propiedades")
def crm_propiedades():
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_PROPS:
        return {"records": [], "error": "INMO_DEMO_AIRTABLE_BASE o INMO_DEMO_TABLE_PROPS no configurados"}
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
    return {"records": records}


@router.get("/crm/clientes")
def crm_clientes():
    if not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_CLIENTES:
        return {"records": [], "error": "INMO_DEMO_AIRTABLE_BASE o INMO_DEMO_TABLE_CLIENTES no configurados"}
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


@router.get("/config")
def ver_config():
    """Endpoint de diagnóstico — muestra config activa (sin secrets)."""
    return {
        "nombre": NOMBRE_INMO,
        "ciudad": CIUDAD,
        "asesor": NOMBRE_ASESOR,
        "numero_bot": NUMERO_BOT[:6] + "..." if NUMERO_BOT else "❌ no configurado",
        "numero_asesor": NUMERO_ASESOR[:6] + "..." if NUMERO_ASESOR else "❌ no configurado",
        "ycloud_key": "✅ configurado" if YCLOUD_API_KEY else "❌ no configurado",
        "airtable_token": "✅ configurado" if AIRTABLE_TOKEN else "❌ no configurado",
        "airtable_base": AIRTABLE_BASE_ID or "❌ no configurado",
        "table_props": AIRTABLE_TABLE_PROPS or "❌ no configurado",
        "table_clientes": AIRTABLE_TABLE_CLIENTES or "❌ no configurado",
        "zonas": ZONAS_LIST,
        "gemini": "✅ configurado" if GEMINI_API_KEY else "❌ no configurado",
    }
