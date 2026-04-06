"""
Bot WhatsApp — Inmobiliaria Maicol v4
======================================
Flujo estructurado por pasos + Gemini para texto libre.
Gemini NO maneja el flujo principal — solo responde preguntas abiertas.
"""

import os
import re
import requests
import uvicorn
import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# ─── CONFIG ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
YCLOUD_API_KEY   = os.environ.get("YCLOUD_API_KEY", "")
AIRTABLE_TOKEN   = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appaDT7uwHnimVZLM")
AIRTABLE_TABLE         = "tbly67z1oY8EFQoFj"
AIRTABLE_TABLE_CLIENTES = "tblonoyIMAM5kl2ue"
NUMERO_BOT       = os.environ.get("NUMERO_BOT", "3764815689")   # Número YCloud (WhatsApp Business)
NUMERO_ASESOR    = os.environ.get("NUMERO_ASESOR", "+543764384843")  # Asesor humano

INMOBILIARIA = {
    "nombre":   "Inmobiliaria Maicol",
    "ciudad":   "San Ignacio, Misiones",
    "asesor":   "un asesor",
    "whatsapp": NUMERO_ASESOR if NUMERO_ASESOR.startswith("+") else f"+{NUMERO_ASESOR}",
}

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ─── APP ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="Bot Inmobiliaria Maicol", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── SESIONES ────────────────────────────────────────────────────────────────
# step: "bienvenida" | "tipo" | "lista"
# operacion: "venta" | "alquiler"
# props: lista de propiedades en caché
SESIONES: dict[str, dict] = {}

# ─── AIRTABLE ────────────────────────────────────────────────────────────────
AT_HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def _at_registrar_cliente(telefono: str, nombre: str, operacion: str = "", tipo: str = "", notas: str = "") -> None:
    """Crea o actualiza un cliente en Airtable."""
    from datetime import date
    hoy = date.today().isoformat()

    # Buscar si ya existe por teléfono
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}"
    buscar = requests.get(url, headers=AT_HEADERS,
        params={"filterByFormula": f"{{Telefono}}='{telefono}'", "maxRecords": 1}, timeout=8)
    records = buscar.json().get("records", []) if buscar.status_code == 200 else []

    campos = {
        "Telefono": telefono,
        "Llego_WhatsApp": True,
    }
    if nombre:
        partes = nombre.strip().split(" ", 1)
        campos["Nombre"] = partes[0]
        if len(partes) > 1:
            campos["Apellido"] = partes[1]
    if operacion:
        campos["Operacion"] = operacion.capitalize()
        campos["Estado"] = "calificado"  # eligió comprar/alquilar → calificado
    if tipo:
        campos["Tipo_Propiedad"] = tipo
    if notas:
        campos["Notas_Bot"] = notas

    if records:
        # Actualizar registro existente
        rec_id = records[0]["id"]
        r = requests.patch(f"{url}/{rec_id}", headers=AT_HEADERS,
                           json={"fields": campos}, timeout=8)
        print(f"[AT] Cliente actualizado: {telefono} → {r.status_code} {r.text[:200]}")
    else:
        # Crear nuevo — primer contacto
        campos["Fecha_WhatsApp"] = hoy
        if "Estado" not in campos:
            campos["Estado"] = "nuevo"
        r = requests.post(url, headers=AT_HEADERS, json={"fields": campos}, timeout=8)
        print(f"[AT] Cliente creado: {telefono} → {r.status_code} {r.text[:200]}")


def _at_buscar_propiedades(tipo: str = None, operacion: str = None, zona: str = None) -> list[dict]:
    # Solo mostrar disponibles Y reservadas (no disponible = ocultar)
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
        print(f"[AT] Error: {e}")
        return []


# ─── YCLOUD ──────────────────────────────────────────────────────────────────
def _normalizar_telefono(tel: str) -> str:
    return f"+{re.sub(r'\\D', '', tel)}"


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not YCLOUD_API_KEY:
        print(f"[YCLOUD] Sin key:\n{mensaje}")
        return False
    try:
        r = requests.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={"Content-Type": "application/json", "X-API-Key": YCLOUD_API_KEY},
            json={"from": NUMERO_BOT, "to": telefono, "type": "text", "text": {"body": mensaje}},
            timeout=10,
        )
        ok = r.status_code in (200, 201)
        print(f"[YCLOUD] Texto {'OK' if ok else 'ERROR ' + str(r.status_code)}")
        return ok
    except Exception as e:
        print(f"[YCLOUD] Excepción: {e}")
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
        ok = r.status_code in (200, 201)
        print(f"[YCLOUD] Imagen {'OK' if ok else 'ERROR ' + str(r.status_code)}")
        return ok
    except Exception as e:
        print(f"[YCLOUD] Excepción imagen: {e}")
        return False


# ─── GEMINI (solo texto libre) ────────────────────────────────────────────────
def _gemini_respuesta(mensaje: str) -> str:
    if not GEMINI_API_KEY:
        return (f"Gracias por tu consulta. Para más información podés hablar con "
                f"nuestro asesor {INMOBILIARIA['asesor']} al {INMOBILIARIA['whatsapp']}. 🏠")
    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        prompt = f"""Sos el asistente virtual de {INMOBILIARIA['nombre']}, inmobiliaria en {INMOBILIARIA['ciudad']}, Argentina.
Tu asesor humano se llama {INMOBILIARIA['asesor']} ({INMOBILIARIA['whatsapp']}).

Respondé SOLO consultas sobre propiedades, compra, venta, alquiler o temas inmobiliarios.
Si la pregunta no es del rubro, decí amablemente que solo podés ayudar con temas inmobiliarios.
Sé breve, amigable y profesional. Respondé en español argentino.
Al finalizar, recordá al cliente que puede responder con un número para ver opciones o escribir *menú* para volver al inicio.

Consulta del cliente: {mensaje}"""
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except Exception as e:
        print(f"[GEMINI] Error: {e}")
        return (f"Gracias por tu consulta. Para más info escribile a nuestro asesor "
                f"{INMOBILIARIA['asesor']} al {INMOBILIARIA['whatsapp']}. 🏠")


# ─── MENSAJES FIJOS ──────────────────────────────────────────────────────────
MSG_BIENVENIDA = """👋 ¡Hola! Bienvenido a *{nombre}* 🏘️
Somos especialistas en *lotes y terrenos* en {ciudad} y la región.

¿En qué te podemos ayudar?

1️⃣ Ver *lotes y terrenos* disponibles
2️⃣ Hablar con un asesor

Respondé con el número de tu opción. 😊"""

MSG_ZONA = """📍 ¿En qué zona estás buscando?

1️⃣ *San Ignacio*
2️⃣ *Gdor Roca*
3️⃣ *Apóstoles*
4️⃣ Otra zona / No sé
0️⃣ Volver al inicio

Respondé con el número. 😊"""

MSG_ASESOR = (
    "¡Perfecto! Te conectamos con nuestro asesor. 👤\n\n"
    "Podés escribirle directamente al *{whatsapp}* "
    "o aguardá que te contacte en breve. ¡Gracias por elegirnos! 🏠"
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
    video = p.get("Video_URL", "")
    if video:
        lineas.append(f"🎥 *Tour virtual:* Hacé clic en el siguiente enlace si querés verlo en video:\n{video}")
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
    op_label = "en Venta" if operacion == "venta" else "en Alquiler"
    zona_label = f" en {zona}" if zona and zona != "Otra Zona" else ""
    if not props:
        # Mantener sesión en "tipo" para que pueda elegir otra categoría
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
    _enviar_texto(telefono, MSG_ASESOR.format(**INMOBILIARIA))


# ─── PROCESADOR PRINCIPAL ─────────────────────────────────────────────────────
def _procesar_mensaje(telefono: str, texto: str) -> None:
    t = texto.lower().strip()
    sesion = SESIONES.get(telefono, {"step": "bienvenida", "props": [], "operacion": ""})
    step = sesion.get("step", "bienvenida")
    operacion = sesion.get("operacion", "")

    # ── Siempre: lead que viene del formulario web ───────────────────────────
    if "me registré en el formulario" in t or "me registre en el formulario" in t:
        # Extraer nombre
        nombre_match = re.search(r"nombre:\s*(.+)", texto, re.IGNORECASE)
        nombre = nombre_match.group(1).strip() if nombre_match else sesion.get("nombre", "")
        nombre_corto = nombre.split()[0] if nombre else ""

        # Detectar operación
        operacion = "venta" if "comprar" in t else ("alquiler" if "alquil" in t else "")

        # Detectar zona del mensaje del formulario
        zona = None
        for z in ["San Ignacio", "Gdor Roca", "Apóstoles", "Otra Zona"]:
            if z.lower() in t or z.lower().replace("ó", "o") in t:
                zona = z
                break

        # Detectar tipo del mensaje del formulario
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
            # Tenemos todo — ir directo a mostrar propiedades
            intro = (f"{saludo}✅ Recibimos tu consulta de *Inmobiliaria Maicol*.\n\n"
                     f"Buscamos {tipo_raw[1].lower()} *{op_str}* en *{zona}*... 🔍")
            _enviar_texto(telefono, intro)
            _mostrar_lista(telefono, tipo_raw[0], tipo_raw[1], operacion, zona)
        elif operacion and zona:
            # Sabemos operación y zona, falta tipo
            SESIONES[telefono] = {**SESIONES[telefono], "step": "tipo"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *Inmobiliaria Maicol*.\n\n"
                f"Buscás *{op_str}* en *{zona}*. ¿Qué tipo de propiedad te interesa?\n\n"
                f"{MSG_TIPO}")
        elif operacion:
            # Solo sabemos operación, falta zona
            SESIONES[telefono] = {**SESIONES[telefono], "step": "zona"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *Inmobiliaria Maicol*.\n\n"
                f"Veo que querés *{op_str}*. ¿En qué zona?\n\n{MSG_ZONA}")
        else:
            SESIONES[telefono] = {**SESIONES[telefono], "step": "bienvenida"}
            _enviar_texto(telefono,
                f"{saludo}✅ Recibimos tu consulta de *Inmobiliaria Maicol*.\n\n{MSG_BIENVENIDA.format(**INMOBILIARIA)}")
        return

    # ── Siempre: 0 o saludo → bienvenida ────────────────────────────────────
    if t in ("0", "menu", "menú", "inicio", "volver", "hola", "hi", "hey", "start") or \
       re.search(r"\b(buenos dias|buenas tardes|buenas noches|buen dia)\b", t):
        nombre = sesion.get("nombre", "")
        SESIONES[telefono] = {"step": "bienvenida", "props": [], "operacion": "", "nombre": nombre}
        # Registrar primer contacto en Airtable
        _at_registrar_cliente(telefono, nombre, notas="Primer contacto por WhatsApp")
        _enviar_texto(telefono, MSG_BIENVENIDA.format(**INMOBILIARIA))
        return

    # ── Siempre: palabras de asesor ──────────────────────────────────────────
    if t in ("asesor", "humano", "agente", "vendedor", "maicol", "persona", "quiero hablar"):
        _ir_asesor(telefono)
        return

    # ── PASO: bienvenida ─────────────────────────────────────────────────────
    if step == "bienvenida":
        nombre = sesion.get("nombre", "")
        if t in ("1", "lote", "lotes", "terreno", "terrenos", "comprar", "venta", "ver lotes"):
            SESIONES[telefono] = {"step": "zona", "props": [], "operacion": "venta", "nombre": nombre}
            _at_registrar_cliente(telefono, nombre, operacion="Venta", notas="Busca lote/terreno")
            _enviar_texto(telefono, MSG_ZONA)
        elif t in ("2", "asesor", "hablar", "humano", "agente"):
            _ir_asesor(telefono)
        else:
            # Texto libre → Gemini
            _enviar_texto(telefono, _gemini_respuesta(texto))
        return

    # ── PASO: zona ───────────────────────────────────────────────────────────
    ZONAS = {
        "1": "San Ignacio", "san ignacio": "San Ignacio",
        "2": "Gdor Roca", "gdor roca": "Gdor Roca", "gobernador roca": "Gdor Roca", "roca": "Gdor Roca",
        "3": "Apóstoles", "apostoles": "Apóstoles", "apóstoles": "Apóstoles",
        "4": "Otra Zona", "otra": "Otra Zona", "no se": "Otra Zona", "no sé": "Otra Zona",
    }
    if step == "zona":
        nombre = sesion.get("nombre", "")
        operacion = sesion.get("operacion", "venta")
        zona = ZONAS.get(t, "")
        if t == "4" or zona == "Otra Zona":
            SESIONES[telefono] = {**sesion, "step": "lista", "zona": "Otra Zona"}
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="Terreno", notas="Zona: Otra Zona")
            _mostrar_lista(telefono, "Terreno", "Lotes y Terrenos", operacion, None)
        elif zona:
            SESIONES[telefono] = {**sesion, "step": "lista", "zona": zona}
            _at_registrar_cliente(telefono, nombre, operacion=operacion, tipo="Terreno", notas=f"Zona: {zona}")
            _mostrar_lista(telefono, "Terreno", "Lotes y Terrenos", operacion, zona)
        elif t == "0":
            pass  # ya manejado arriba con el 0 global
        else:
            _enviar_texto(telefono, f"Por favor elegí una opción del 1 al 4.\n\n{MSG_ZONA}")
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


# ─── ENDPOINT ────────────────────────────────────────────────────────────────
@app.post("/inmobiliaria/whatsapp")
async def procesar_whatsapp(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detalle": "body no es JSON válido"}

    print(f"[BOT] Payload: {str(body)[:600]}")
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
        # Ignorar multimedia — no disparar bienvenida
        return {"status": "ignorado", "razon": f"media type: {msg_type}"}
    else:
        texto = ""

    if not telefono or not texto:
        return {"status": "ignorado", "razon": "sin telefono o texto"}

    # Guardar nombre del cliente si viene en el payload — ANTES de procesar
    nombre_cliente = ""
    # YCloud puede enviar el nombre en customerProfile o en whatsappContact
    customer_profile = msg.get("customerProfile") or msg.get("whatsappContact") or body.get("customerProfile") or {}
    raw_name = customer_profile.get("name") or customer_profile.get("displayName") or ""
    if raw_name:
        nombre_cliente = raw_name
    print(f"[BOT] De: {telefono} ({nombre_cliente!r}) | Tipo: {msg_type} | Texto: {texto!r}")

    # Actualizar sesión con nombre antes de procesar
    sesion = SESIONES.get(telefono, {})
    if nombre_cliente and not sesion.get("nombre"):
        sesion["nombre"] = nombre_cliente
        SESIONES[telefono] = sesion

    _procesar_mensaje(telefono, texto)
    return {"status": "ok", "telefono": telefono, "texto": texto}


@app.get("/inmobiliaria/propiedades")
def ver_propiedades(tipo: str = None):
    return {"total": len(props := _at_buscar_propiedades(tipo=tipo)), "propiedades": props}


@app.get("/crm/propiedades")
def crm_propiedades():
    """Proxy para el dashboard CRM — evita CORS desde file://"""
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


@app.get("/crm/clientes")
def crm_clientes():
    """Proxy para el dashboard CRM — evita CORS desde file://"""
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


@app.patch("/crm/propiedades/{record_id}")
async def crm_patch_propiedad(record_id: str, req: Request):
    """Actualizar campos de una propiedad en Airtable"""
    body = await req.json()
    # Airtable Attachment fields requieren array de objetos, no string
    if "Imagen_URL" in body and isinstance(body["Imagen_URL"], str) and body["Imagen_URL"]:
        body["Imagen_URL"] = [{"url": body["Imagen_URL"]}]
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}/{record_id}"
    r = requests.patch(url, headers={**AT_HEADERS, "Content-Type": "application/json"},
                       json={"fields": body}, timeout=10)
    print(f"[PATCH] status={r.status_code} resp={r.text[:300]}")
    return r.json()


@app.post("/crm/propiedades")
async def crm_post_propiedad(req: Request):
    """Crear una nueva propiedad en Airtable"""
    body = await req.json()
    if "Imagen_URL" in body and isinstance(body["Imagen_URL"], str) and body["Imagen_URL"]:
        body["Imagen_URL"] = [{"url": body["Imagen_URL"]}]
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
    r = requests.post(url, headers={**AT_HEADERS, "Content-Type": "application/json"},
                      json={"fields": body}, timeout=10)
    return r.json()


@app.patch("/crm/clientes/{record_id}")
async def crm_patch_cliente(record_id: str, req: Request):
    """Actualizar campos de un lead/cliente en Airtable"""
    body = await req.json()
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_CLIENTES}/{record_id}"
    print(f"[PATCH cliente] record_id={record_id} body={body}")
    r = requests.patch(url, headers={**AT_HEADERS, "Content-Type": "application/json"},
                       json={"fields": body}, timeout=10)
    print(f"[PATCH cliente] status={r.status_code} resp={r.text[:400]}")
    return r.json()


@app.get("/crm")
def crm_dashboard():
    """Sirve el dashboard CRM desde HTTP (evita restricciones file://)"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "PRESENTACION", "dashboard-crm.html")
    return FileResponse(os.path.abspath(html_path), media_type="text/html")


@app.get("/formulario")
def formulario_leads():
    """Sirve el formulario de leads desde HTTP (evita restricciones file://)"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "PRESENTACION", "formulario-leads.html")
    return FileResponse(os.path.abspath(html_path), media_type="text/html")


@app.post("/formulario/submit")
async def formulario_submit(req: Request):
    """Recibe el formulario y reenvía a n8n internamente (evita CORS)"""
    body = await req.json()
    r = requests.post(
        "http://localhost:5678/webhook/inmobiliaria-formulario",
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    return {"status": "ok", "n8n": r.status_code}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "inmobiliaria": INMOBILIARIA["nombre"],
        "gemini": "configurado" if GEMINI_API_KEY else "sin API key",
        "ycloud": "configurado" if YCLOUD_API_KEY else "sin API key",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
