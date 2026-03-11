"""
workers/comercio/worker.py
──────────────────────────
Bot conversacional para comercios (electrónica, ropa, ferretería, etc.)
Usa Gemini 2.5 Flash Lite + Airtable + historial de conversación.

Endpoint: POST /comercio/mensaje
Workflow n8n: webhook → FastAPI → WhatsApp

Funcionalidades:
- Catálogo dinámico desde Airtable (productos con imagen, precio, descripción)
- Historial de conversación multi-turno
- Ruta admin (dueño gestiona catálogo por WhatsApp)
- Calificación de leads + notificación al dueño
- Guardrails anti prompt-injection
- Endpoint GET /comercio/catalogo para sitio web
"""

import os
import json
import re
import requests
import traceback
from datetime import date, datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

import google.generativeai as genai

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/comercio", tags=["Comercio WhatsApp"])

GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
AIRTABLE_API_KEY  = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID  = os.environ.get("AIRTABLE_BASE_COMERCIO",
                    os.environ.get("AIRTABLE_BASE_ID", ""))
NUMERO_DUENO      = os.environ.get("NUMERO_DUENO_COMERCIO",
                    os.environ.get("NUMERO_DUENO", ""))

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def AT_HEADERS():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

TIENDA = {
    "nombre":      "Casa Electrónica",
    "especialidad": "Electrónica, electrodomésticos y tecnología",
    "horario":     "Lunes a Sábado, 9:00 a 19:00hs",
    "alias_pago":  "",
    "numero_dueno": NUMERO_DUENO,
}

HOY = date.today().strftime("%A %d de %B de %Y")

# ─────────────────────────────────────────────────────────────────────────────
# GUARDRAILS
# ─────────────────────────────────────────────────────────────────────────────
try:
    from workers.shared.guardrails import detect_injection, sanitize_for_llm, validate_output, FALLBACK_SOCIAL as FALLBACK
except ImportError:
    def detect_injection(t, w="comercio"): return False
    def sanitize_for_llm(t, c="mensaje"): return t
    def validate_output(t, w="comercio"): return True
    FALLBACK = "¡Gracias por tu consulta! ¿En qué te puedo ayudar? 😊"

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""════════════════════════════════════════════════════════
ROL
════════════════════════════════════════════════════════
Sos el asistente virtual de *{TIENDA['nombre']}*.
Tu trabajo es atender clientes por WhatsApp: mostrar productos, responder consultas técnicas, comparar opciones y derivar al vendedor humano cuando el cliente está listo para comprar.

PERSONALIDAD:
- Amable, profesional y conocedor del rubro
- Respuestas cortas y directas para WhatsApp — máximo 8 líneas
- Emojis con moderación (máximo 2 por mensaje)
- Tratá al cliente de "vos" o "usted" según como escriba

════════════════════════════════════════════════════════
DATOS DE LA TIENDA
════════════════════════════════════════════════════════
- Nombre: {TIENDA['nombre']}
- Especialidad: {TIENDA['especialidad']}
- Horario: {TIENDA['horario']}
- Fecha de hoy: {HOY}

[El catálogo se inyecta dinámicamente al final de este prompt con datos reales de Airtable]

════════════════════════════════════════════════════════
MENÚ PRINCIPAL (punto de entrada)
════════════════════════════════════════════════════════
CUÁNDO mostrarlo: ante cualquier primer mensaje, saludo, o cuando escriba "0" o "menu".

TEXTO EXACTO a mostrar:
*¡Bienvenido a {TIENDA['nombre']}!* 🏪
¿En qué podemos ayudarte?

1️⃣ Ver productos disponibles
2️⃣ Buscar un producto específico
3️⃣ Comparar productos
4️⃣ Hablar con un vendedor

REGLA: Esperá que el cliente elija. No agregues texto extra.

════════════════════════════════════════════════════════
TAREA 1 — VER PRODUCTOS (opción 1)
════════════════════════════════════════════════════════
Mostrá las categorías disponibles del catálogo inyectado al final.
Cuando elija una categoría → mostrá los productos con nombre, precio y descripción corta.
Solo mostrá productos donde Disponible = true.

════════════════════════════════════════════════════════
TAREA 2 — BUSCAR PRODUCTO (opción 2)
════════════════════════════════════════════════════════
Preguntá: "¿Qué producto estás buscando?"
Buscá en el catálogo inyectado. Si hay coincidencia, mostrá:

*[Nombre del Producto]*
💰 Precio: $[precio] ARS
📋 [descripción]
✅ Disponible / ❌ Agotado

Si no hay coincidencia exacta, sugerí los más parecidos.

════════════════════════════════════════════════════════
TAREA 3 — COMPARAR PRODUCTOS (opción 3)
════════════════════════════════════════════════════════
Preguntá qué productos quiere comparar.
Mostrá una comparación lado a lado con precio y características principales.

════════════════════════════════════════════════════════
TAREA 4 — HABLAR CON VENDEDOR (opción 4)
════════════════════════════════════════════════════════
Cuando el cliente quiera comprar, pida información que no tengas, o pida hablar con alguien:
Respondé: "¡Perfecto! Ya le aviso a nuestro equipo para que te contacte. ¿Hay algo más que quieras saber mientras tanto?"
Ejecutá:
ACCION: {{"tipo": "notificar_vendedor", "producto_interes": "...", "consulta": "..."}}

════════════════════════════════════════════════════════
DETECCIÓN DE INTENCIÓN DE COMPRA
════════════════════════════════════════════════════════
Si el cliente dice cosas como: "lo quiero", "¿cómo pago?", "¿hacen envío?", "¿lo tienen?", "¿puedo pasar a buscarlo?" → es señal de compra.
Ejecutá:
ACCION: {{"tipo": "lead_calificado", "producto_interes": "...", "señal": "..."}}

════════════════════════════════════════════════════════
REGLAS CRÍTICAS
════════════════════════════════════════════════════════
1. SOLO ofrecé productos que estén en el catálogo inyectado
2. NUNCA inventes precios, specs o disponibilidad
3. Si no tenés la info → "Voy a consultar con nuestro equipo y te confirmo"
4. Siempre cerrá con una pregunta o sugerencia para mantener la conversación
5. Cuando el JSON de ACCION sea necesario, poné SOLO el JSON en una línea separada
"""

# ─────────────────────────────────────────────────────────────────────────────
# MODELO GEMINI
# ─────────────────────────────────────────────────────────────────────────────
modelo = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    system_instruction=SYSTEM_PROMPT,
) if GEMINI_API_KEY else None

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS AIRTABLE
# ─────────────────────────────────────────────────────────────────────────────
def at_get_catalogo() -> list:
    """Lee todos los productos desde Airtable."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Productos"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "sort[0][field]": "Nombre",
            "sort[0][direction]": "asc",
        })
        return r.json().get("records", [])
    except Exception as e:
        print(f"[AT-COMERCIO] Error get_catalogo: {e}")
        return []


def at_get_catalogo_texto(solo_disponibles: bool = True) -> str:
    """Devuelve el catálogo formateado como texto para el prompt."""
    records = at_get_catalogo()
    if not records:
        return "(Catálogo no disponible)"

    por_categoria = {}
    for rec in records:
        f = rec["fields"]
        if solo_disponibles and not f.get("Disponible", False):
            continue
        cat = f.get("Categoria", "Otros")
        if isinstance(cat, list):
            cat = cat[0] if cat else "Otros"
        if cat not in por_categoria:
            por_categoria[cat] = []
        por_categoria[cat].append({
            "nombre": f.get("Nombre", ""),
            "precio": f.get("Precio", 0),
            "descripcion": f.get("Descripcion", ""),
            "disponible": f.get("Disponible", False),
        })

    lineas = []
    for cat, productos in por_categoria.items():
        lineas.append(f"\n*{cat}*")
        for p in productos:
            precio = f"${p['precio']:,.0f}".replace(",", ".") if p['precio'] else "Consultar"
            desc = f" — {p['descripcion'][:80]}" if p['descripcion'] else ""
            estado = "✅" if p['disponible'] else "❌"
            lineas.append(f"  {estado} {p['nombre']} — {precio} ARS{desc}")
    return "\n".join(lineas) if lineas else "(Sin productos cargados)"


def at_get_conversacion(telefono: str):
    """Busca conversación activa por teléfono."""
    try:
        tel_limpio = telefono.replace("@s.whatsapp.net", "").replace("+", "")
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": f'{{telefono}}="{tel_limpio}"',
            "maxRecords": 1,
        })
        records = r.json().get("records", [])
        return records[0] if records else None
    except Exception as e:
        print(f"[AT-COMERCIO] Error get_conv: {e}")
        return None


def at_guardar_conversacion(telefono: str, historial: list, record_id: str = None):
    """Guarda o actualiza historial de conversación."""
    tel_limpio = telefono.replace("@s.whatsapp.net", "").replace("+", "")
    historial_json = json.dumps(historial[-30:], ensure_ascii=False)
    fields = {
        "telefono": tel_limpio,
        "historial": historial_json,
        "ultima_interaccion": datetime.now().isoformat(),
    }
    try:
        if record_id:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas/{record_id}"
            requests.patch(url, headers=AT_HEADERS(), json={"fields": fields})
        else:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
            requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": fields}]})
    except Exception as e:
        print(f"[AT-COMERCIO] Error guardar_conv: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICACIONES AL DUEÑO
# ─────────────────────────────────────────────────────────────────────────────
def notificar_dueno(texto: str):
    """Envía notificación al dueño vía Evolution API."""
    evo_url = os.environ.get("EVOLUTION_API_URL", "")
    evo_instance = os.environ.get("EVOLUTION_INSTANCE", "")
    evo_key = os.environ.get("EVOLUTION_API_KEY", "")
    if not all([evo_url, evo_instance, evo_key, NUMERO_DUENO]):
        print(f"[NOTIF-COMERCIO] Faltan vars. Mensaje: {texto[:100]}")
        return False
    try:
        from urllib.parse import quote
        url = f"{evo_url}/message/sendText/{quote(evo_instance)}"
        requests.post(url, json={"number": NUMERO_DUENO, "text": texto},
                      headers={"apikey": evo_key}, timeout=10)
        return True
    except Exception as e:
        print(f"[NOTIF-COMERCIO] Error: {e}")
        return False


def ejecutar_accion(accion_data: dict, telefono: str, nombre_contacto: str = "") -> str:
    """Ejecuta acciones detectadas en la respuesta del bot."""
    tipo = accion_data.get("tipo", "")
    producto = accion_data.get("producto_interes", "desconocido")

    if tipo == "lead_calificado":
        señal = accion_data.get("señal", "")
        msg = (
            f"🔥 *LEAD CALIFICADO — {TIENDA['nombre']}*\n\n"
            f"📱 Cliente: {nombre_contacto or telefono}\n"
            f"📞 Tel: {telefono}\n"
            f"🛒 Producto de interés: {producto}\n"
            f"💡 Señal: {señal}\n"
            f"⏰ {datetime.now().strftime('%d/%m %H:%M')}"
        )
        notificar_dueno(msg)
        return "lead_notificado"

    elif tipo == "notificar_vendedor":
        consulta = accion_data.get("consulta", "")
        msg = (
            f"📞 *CLIENTE PIDE VENDEDOR — {TIENDA['nombre']}*\n\n"
            f"📱 {nombre_contacto or telefono}\n"
            f"📞 Tel: {telefono}\n"
            f"🛒 Interés: {producto}\n"
            f"💬 Consulta: {consulta}\n"
            f"⏰ {datetime.now().strftime('%d/%m %H:%M')}"
        )
        notificar_dueno(msg)
        return "vendedor_notificado"

    return "sin_accion"


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS PYDANTIC
# ─────────────────────────────────────────────────────────────────────────────
class MensajeComercio(BaseModel):
    mensaje: str
    telefono: str
    nombre_contacto: Optional[str] = ""
    es_admin: Optional[bool] = False


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT PRINCIPAL: POST /comercio/mensaje
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/mensaje", summary="Procesar mensaje WhatsApp — Comercio")
async def manejar_mensaje(entrada: MensajeComercio):
    """
    Recibe mensaje de n8n, procesa con Gemini + catálogo Airtable,
    devuelve respuesta para WhatsApp.
    """
    if not GEMINI_API_KEY:
        return {"respuesta": "⚠️ GEMINI_API_KEY no configurada.", "status": "error"}

    tel = entrada.telefono
    msg = entrada.mensaje.strip()
    nombre = entrada.nombre_contacto or ""

    if not msg:
        return {"respuesta": "No recibí ningún mensaje.", "status": "error"}

    # ── Guardrails ────────────────────────────────────────────────────────
    if detect_injection(msg, worker="comercio"):
        return {"respuesta": FALLBACK, "tipo_mensaje": "texto", "accion_ejecutada": None}

    msg_sanitizado = sanitize_for_llm(msg, context="consulta_cliente")

    # ── Historial ─────────────────────────────────────────────────────────
    conv = at_get_conversacion(tel)
    record_id = conv["id"] if conv else None
    historial = []
    if conv:
        try:
            historial = json.loads(conv["fields"].get("historial", "[]"))
        except:
            historial = []

    # ── Bienvenida ────────────────────────────────────────────────────────
    SALUDOS = {"hola", "buenas", "buen día", "buenos días", "buenas tardes",
               "buenas noches", "hey", "hi", "holis", "buenas!", "hola!", "ola"}
    msg_lower = msg.lower().strip().rstrip(".,!?")
    if not historial or msg_lower in SALUDOS:
        bienvenida = (
            f"*¡Bienvenido a {TIENDA['nombre']}!* 🏪\n"
            f"¿En qué podemos ayudarte?\n\n"
            f"1️⃣ Ver productos disponibles\n"
            f"2️⃣ Buscar un producto específico\n"
            f"3️⃣ Comparar productos\n"
            f"4️⃣ Hablar con un vendedor"
        )
        historial.append({"role": "user",  "content": msg})
        historial.append({"role": "model", "content": bienvenida})
        at_guardar_conversacion(tel, historial, record_id)
        return {"respuesta": bienvenida, "tipo_mensaje": "texto", "accion_ejecutada": None}

    # ── Catálogo dinámico ─────────────────────────────────────────────────
    catalogo_texto = at_get_catalogo_texto(solo_disponibles=False)

    # ── Modelo con contexto ──────────────────────────────────────────────
    modelo_con_ctx = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=(
            SYSTEM_PROMPT
            + "\n\n---\n## CATÁLOGO ACTUAL (datos reales de Airtable)\n"
            + catalogo_texto
        ),
    )

    # ── Historial para Gemini ─────────────────────────────────────────────
    history_gemini = []
    for turno in historial:
        if turno.get("role") in ["user", "model"]:
            history_gemini.append({
                "role": turno["role"],
                "parts": [{"text": turno["content"]}],
            })

    # ── Generar respuesta ────────────────────────────────────────────────
    try:
        chat = modelo_con_ctx.start_chat(history=history_gemini)
        response = chat.send_message(msg_sanitizado)
        respuesta = response.text.strip()
    except Exception as e:
        print(f"[COMERCIO] Error Gemini: {traceback.format_exc()}")
        return {
            "respuesta": "Disculpá, tuve un problema técnico. ¿Podés repetir tu consulta?",
            "tipo_mensaje": "texto",
            "accion_ejecutada": None,
            "_error": str(e),
        }

    # ── Validar output ────────────────────────────────────────────────────
    if not validate_output(respuesta, worker="comercio"):
        respuesta = FALLBACK

    # ── Detectar y ejecutar acciones ──────────────────────────────────────
    accion_ejecutada = None
    accion_match = re.search(r'ACCION:\s*(\{[^}]+\})', respuesta)
    if accion_match:
        try:
            accion_data = json.loads(accion_match.group(1))
            accion_ejecutada = ejecutar_accion(accion_data, tel, nombre)
            # Limpiar el JSON de la respuesta al cliente
            respuesta = respuesta[:accion_match.start()].strip()
            if not respuesta:
                if accion_data.get("tipo") == "lead_calificado":
                    respuesta = "¡Excelente elección! Ya le avisé a nuestro equipo. Te van a contactar a la brevedad. 🙌"
                else:
                    respuesta = "¡Perfecto! Ya le avisé a un vendedor. Te va a contactar en breve. 📞"
        except json.JSONDecodeError:
            pass

    # ── Guardar historial ─────────────────────────────────────────────────
    historial.append({"role": "user",  "content": msg})
    historial.append({"role": "model", "content": respuesta})
    at_guardar_conversacion(tel, historial, record_id)

    return {
        "respuesta": respuesta,
        "tipo_mensaje": "texto",
        "accion_ejecutada": accion_ejecutada,
        "notificar_dueno": accion_ejecutada in ["lead_notificado", "vendedor_notificado"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT ADMIN: POST /comercio/admin (dueño gestiona catálogo por WhatsApp)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/admin", summary="Gestión de catálogo por WhatsApp (admin)")
async def admin_catalogo(entrada: MensajeComercio):
    """El dueño puede agregar/actualizar productos enviando mensajes."""
    if not GEMINI_API_KEY:
        return {"respuesta": "⚠️ GEMINI_API_KEY no configurada.", "status": "error"}

    prompt = f"""El dueño de la tienda envía este mensaje para gestionar su catálogo.
La disponibilidad es un checkbox booleano (true/false).

MENSAJE: "{entrada.mensaje}"

Extrae la información en JSON estricto:
{{
  "accion": "crear_producto" | "actualizar_disponibilidad" | "actualizar_precio" | "desconocida",
  "datos": {{
    "Nombre": "Nombre del producto",
    "Categoria": "Categoría",
    "Precio": 0,
    "Descripcion": "Descripción breve",
    "Disponible": true
  }}
}}"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        resp = model.generate_content(prompt)
        texto = resp.text.strip()

        match = re.search(r'\{[\s\S]*\}', texto)
        if not match:
            return {"respuesta": "🤖 No entendí qué querés hacer con el catálogo."}

        data = json.loads(match.group(0))
        accion = data.get("accion")
        datos = data.get("datos", {})
        nombre_prod = datos.get("Nombre", "").lower()

        if accion == "crear_producto":
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Productos"
            requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": datos}]})
            return {"respuesta": f"✅ Producto '{datos.get('Nombre')}' guardado en el catálogo."}

        elif accion in ("actualizar_disponibilidad", "actualizar_precio"):
            records = at_get_catalogo()
            found = None
            for rec in records:
                if nombre_prod in rec["fields"].get("Nombre", "").lower():
                    found = rec["id"]
                    break
            if found:
                update_fields = {}
                if "Disponible" in datos:
                    update_fields["Disponible"] = datos["Disponible"]
                if "Precio" in datos and datos["Precio"]:
                    update_fields["Precio"] = datos["Precio"]
                url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Productos/{found}"
                requests.patch(url, headers=AT_HEADERS(), json={"fields": update_fields})
                return {"respuesta": f"✅ Producto '{datos.get('Nombre')}' actualizado."}
            else:
                return {"respuesta": f"❌ No encontré '{datos.get('Nombre')}' en el catálogo."}

        return {"respuesta": "🤖 No entendí qué querés hacer. Probá: 'Agregar TV Samsung 55 a $450.000'"}

    except Exception as e:
        return {"respuesta": f"Error interno: {str(e)}"}


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT WEB: GET /comercio/catalogo (para sitio web)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/catalogo", summary="Catálogo JSON para sitio web")
def get_catalogo_web():
    """Devuelve el catálogo completo en JSON para consumir desde el sitio web."""
    records = at_get_catalogo()
    productos = []
    for rec in records:
        f = rec["fields"]
        if not f.get("Disponible", False):
            continue
        imgs = f.get("Imagen", [])
        productos.append({
            "id": f.get("ID_Producto", rec["id"]),
            "nombre": f.get("Nombre", ""),
            "precio": f.get("Precio", 0),
            "descripcion": f.get("Descripcion", ""),
            "categoria": f.get("Categoria", ""),
            "imagen": imgs[0].get("url", "") if imgs else "",
            "imagen_thumb": imgs[0].get("thumbnails", {}).get("large", {}).get("url", "") if imgs else "",
        })
    return {
        "tienda": TIENDA["nombre"],
        "total": len(productos),
        "productos": productos,
    }


# ─────────────────────────────────────────────────────────────────────────────
# DEBUG ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/debug/config", summary="Debug: Ver configuración")
def debug_config():
    return {
        "GEMINI_API_KEY": f"✅ ({len(GEMINI_API_KEY)} chars)" if GEMINI_API_KEY else "❌",
        "AIRTABLE_API_KEY": f"✅ ({len(AIRTABLE_API_KEY)} chars)" if AIRTABLE_API_KEY else "❌",
        "AIRTABLE_BASE_ID": AIRTABLE_BASE_ID or "❌",
        "NUMERO_DUENO": NUMERO_DUENO[:6] + "..." if NUMERO_DUENO else "❌",
        "tienda": TIENDA["nombre"],
    }


@router.get("/debug/test", summary="Debug: Test rápido del catálogo")
def debug_test():
    return {
        "catalogo_texto": at_get_catalogo_texto(),
        "total_productos": len(at_get_catalogo()),
    }
