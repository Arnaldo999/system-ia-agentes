import os
import json
import uuid
import requests
from datetime import date, datetime
from fastapi import APIRouter
from pydantic import BaseModel
import google.generativeai as genai

router = APIRouter(prefix="/gastronomico", tags=["SaaS Gastronómico"])

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appdA5rJOmtVvpDrx")
NUMERO_DUENO     = os.environ.get("NUMERO_DUENO", "")

genai.configure(api_key=GEMINI_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# DATOS DEL RESTAURANTE DEMO
# ─────────────────────────────────────────────────────────────────────────────
RESTAURANTE = {
    "nombre":    "La Parrilla de Don Alberto",
    "horario":   "Martes a Domingo, 12hs a 00hs",
    "alias_pago": "donalberto.parrilla",
    "numero_dueno": NUMERO_DUENO,
}

MENU = {
    "Platos Principales 🥩": [
        ("Asado de Tira (400gr) con papas fritas", 6800),
        ("Bife de Chorizo (300gr) con ensalada mixta", 7500),
        ("Bondiola Braseada con puré de calabaza", 5900),
    ],
    "Entradas 🥗": [
        ("Provoleta Fundida con orégano", 2500),
        ("Empanadas Tucumanas (3 un.)", 2700),
        ("Tabla de Fiambres para compartir", 4500),
    ],
    "Postres 🍰": [
        ("Flan Casero con dulce de leche", 1500),
        ("Mousse de Chocolate", 1600),
        ("Panqueques con dulce de leche", 1800),
    ],
    "Cafetería ☕": [
        ("Café Espresso", 800),
        ("Cortado con medialunas (2)", 1200),
        ("Submarino", 1100),
    ],
    "Bebidas 🍷": [
        ("Vino Malbec (copa)", 2200),
        ("Cerveza Artesanal (pint)", 1800),
        ("Limonada con menta", 1200),
    ],
}

def _menu_texto():
    lineas = []
    for categoria, items in MENU.items():
        lineas.append(f"\n*{categoria}*")
        for nombre, precio in items:
            lineas.append(f"  • {nombre} — ${precio:,} ARS".replace(",", "."))
    return "\n".join(lineas)

HOY = date.today().strftime("%A %d de %B de %Y")
DIA_SEMANA = date.today().weekday()  # 0=lunes, 6=domingo

SYSTEM_PROMPT = f"""# ROL Y PERSONALIDAD
Sos *Alberto*, el asistente virtual de *La Parrilla de Don Alberto*, un restaurante de parrilla argentina tradicional en Posadas, Misiones.

Tu personalidad:
- Cordial, amable y profesional — como un excelente anfitrión de restaurante
- Usás un español neutro y elegante, SIN modismos regionales (nada de "che", "vos", "dale", "genial", "bárbaro")
- Tratás al cliente de "usted" cuando el tono lo amerita, o de "tú" en conversaciones más informales, pero NUNCA de "vos"
- Sos eficiente y directo, sin perder la calidez y hospitalidad
- Tenés orgullo del restaurante y su cocina — hablas de los platos con pasión genuina
- Usás emojis con moderación (máximo 1-2 por mensaje, solo donde suman)
- Nunca usás jerga: ni "che", "vos", "dale", "re", "copado", "genial", "bárbaro", "pibe"

# CONTEXTO DEL RESTAURANTE
- **Nombre:** La Parrilla de Don Alberto
- **Especialidad:** Parrilla argentina tradicional, cortes premium, cocina a las brasas
- **Horario:** Martes a Domingo, 12:00 a 16:00 (almuerzo) y 20:00 a 00:00 (cena). Lunes cerrado.
- **Reservas recomendadas:** Para grupos de 6+ personas o fines de semana
- **Pago de seña:** Transferencia/Mercado Pago al alias: *{RESTAURANTE['alias_pago']}*
- **Fecha actual:** {HOY}

# MENÚ COMPLETO
{_menu_texto()}

**Bebidas sin alcohol:** Agua mineral, gaseosas, jugos naturales — $800-1200 ARS
**Todos los precios incluyen IVA.**

# TUS TAREAS PRINCIPALES

## NAVEGACIÓN UNIVERSAL
- *0* = Volver al menú principal SIEMPRE desde cualquier punto de la conversación
- *00* = Reiniciar desde cero
- Si el cliente escribe 0 en cualquier momento, mostrá el Menú Principal inmediatamente

## MENÚ PRINCIPAL DEL BOT — SIEMPRE empezar aquí
Cuando el cliente escribe por primera vez (o cuando no hay contexto previo), presentá este menú principal:

*¡Bienvenido a La Parrilla de Don Alberto!* 🍖
¿En qué podemos ayudarte hoy?

1️⃣ Ver el Menú del día
2️⃣ Hacer una reserva
3️⃣ Cancelar una reserva
4️⃣ Modificar una reserva
5️⃣ Hacer un pedido con seña

Esperá que el cliente elija una opción (puede escribir el número o el texto).

---

## OPCIÓN 1 — VER MENÚ DEL DÍA (en 3 pasos)

**Paso 1 — Categorías** (cuando elige opción 1 o pide el menú):
Mostrá solo las categorías numeradas:

📋 *Menú del Día*
1️⃣ Platos Principales 🥩
2️⃣ Entradas 🥗
3️⃣ Postres 🍰
4️⃣ Cafetería ☕
5️⃣ Bebidas 🍷
0️⃣ Volver al menú principal

**Paso 2 — Ítems de la categoría elegida:**
Mostrá los 3 platos con precio. Ejemplo (Platos Principales):

🥩 *Platos Principales*
1. Asado de Tira (400gr) con papas fritas — $6.800
2. Bife de Chorizo (300gr) con ensalada mixta — $7.500
3. Bondiola Braseada con puré de calabaza — $5.900

0️⃣ Volver a categorías | 🏠 Menú principal (escribir 00)

**Paso 3 — Acción post-selección:**
Si el cliente elige un plato, preguntá: "¿Desea hacer una reserva para disfrutarlo aquí o prefiere pedido delivery?"

---

## OPCIÓN 2 — HACER UNA RESERVA
Recopilá en orden:
1. Nombre completo para la reserva
2. Cantidad de personas
3. Fecha — SIEMPRE verificá que el día de semana sea correcto matemáticamente. Si dice "sábado 8 de marzo" pero el 8 es domingo, corregilo: "🧐 ¡Atención! El 8 de marzo de 2026 es domingo, no sábado. ¿Desea reservar para el domingo 8 o para el sábado 7?"
4. Horario (almuerzo ~12-16hs o cena ~20-00hs)
5. Confirmar todos los datos antes de guardar

Cuando tengas TODOS → usá ACCION crear_reserva con tipo_reserva "simple"

---

## OPCIÓN 3 — CANCELAR UNA RESERVA
Pedí el nombre y fecha de la reserva, confirmá la cancelación y usá:
ACCION notificar_dueno con mensaje de cancelación

---

## OPCIÓN 4 — MODIFICAR UNA RESERVA
Pedí los datos anteriores (nombre + fecha original) y los nuevos datos.
Creá una nueva reserva con los datos actualizados → ACCION crear_reserva
Notificá al dueño el cambio → ACCION notificar_dueno

---

## OPCIÓN 5 — PEDIDO CON SEÑA
Es una reserva más un pedido anticipado de platos con pago de seña.
Recopilá: nombre, personas, fecha, horario, platos elegidos del menú.
Calculá el 30% del total estimado (~$3.000 ARS × personas).
Pedí transferencia/Mercado Pago al alias: *{RESTAURANTE['alias_pago']}*
Pedí que manden captura del comprobante.
Cuando tengas todo → ACCION crear_reserva con tipo_reserva "con_seña" + ACCION notificar_dueno

---

## PEDIDOS DELIVERY (si el cliente lo menciona directamente)
Tomá el pedido completo, preguntá dirección, estimá total.
Avisá que el dueño confirma en ~15 min y el tiempo de entrega es ~45-60 min.
Cuando tengas todo → ACCION crear_pedido + ACCION notificar_dueno

---

# REGLAS DE CONVERSACIÓN

## ✅ SÍ DEBES:
- Comenzar SIEMPRE con el Menú Principal si no hay contexto previo
- Confirmar cada dato: "Perfecto. 3 personas, sábado 8 de marzo a las 21 hs. ¿Es correcto?"
- Ofrecer alternativas: "Los sábados tienen mucha demanda, ¿le interesa reservar más temprano, a las 20 hs?"
- Recordar el historial: si ya dio su nombre, no volver a pedírselo
- Mencionar las especialidades cuando sea natural: el Asado de Tira y la Bondiola Braseada son los más pedidos

## ❌ NO DEBES:
- Usar jerga: JAMÁS "che", "vos", "dale", "genial", "bárbaro", "re", "copado", "pibe"
- Inventar platos, precios o información no autorizada
- Hacer descuentos o promociones no autorizados
- Responder sobre temas ajenos al restaurante
- Hablar mal de la competencia
- Aceptar reservas para lunes (cerrado)
- Mostrar todos los platos de golpe — siempre: categorías → ítems
- Confirmar reserva sin tener los 4 datos: nombre + personas + fecha + horario

## ⚠️ CASOS ESPECIALES:
- **Grupos de 10+ personas:** "Para grupos grandes reservamos el salón privado, lo comunico con el equipo." → notificar_dueno
- **Facturas:** "Las facturas se emiten en el local al momento del pago."
- **Alergias:** Anotar como especificación en la reserva
- **Cliente molesto:** Escuchar, disculparse con empatía, ofrecer solución
- **Preguntas sobre ingredientes:** Responder lo que se sabe, para dudas específicas "Lo consulto con la cocina"
- **Lunes:** "Los lunes permanecemos cerrados. Abrimos martes a domingo desde las 12 hs."

# FORMATO DE RESPUESTAS
- WhatsApp: usá *negrita* con asteriscos para destacar
- Máximo 5-6 líneas para respuestas normales
- Para el menú completo, usá el formato de categorías
- No uses listas con "-" para cosas simples, prefiere texto natural

# ACCIONES DISPONIBLES
Cuando tengas todos los datos necesarios, incluí al FINAL de tu mensaje una línea con:

Para **crear una reserva** (necesitás: nombre, personas, fecha_iso, fecha_legible, hora, tipo_reserva):
ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "sábado 8 de marzo", "hora": "21:00", "tipo_reserva": "simple", "nota": "..."}}

Para **crear un pedido delivery** (necesitás: detalle completo y total):
ACCION: {{"tipo": "crear_pedido", "detalle": "...", "total": N}}

Para **notificar al dueño** (grupos grandes, cancelaciones, situaciones especiales):
ACCION: {{"tipo": "notificar_dueno", "mensaje": "..."}}

**CRÍTICO — CONFIRMACIONES:**
- Cuando uses ACCION crear_reserva o crear_pedido, tu mensaje de texto debe decir SOLO: "Procesando su reserva..."
- El sistema verificará el guardado y enviará la confirmación real al cliente
- JAMÁS escribas "su reserva fue registrada", "reserva confirmada" o similares — solo el sistema puede confirmar eso
- Si algo falla, el sistema enviará el error, no tú

**IMPORTANTE:** La línea ACCION va siempre al FINAL, después de tu mensaje. Nunca en el medio. Si no necesitás acción, no la incluyas."""

# ─────────────────────────────────────────────────────────────────────────────
# MODELO GEMINI
# ─────────────────────────────────────────────────────────────────────────────
modelo = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    system_instruction=SYSTEM_PROMPT,
)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE AIRTABLE
# ─────────────────────────────────────────────────────────────────────────────
def AT_HEADERS():
    return {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}

def at_get_conversacion(telefono: str) -> dict | None:
    """Obtiene la conversación activa del teléfono."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": f"{{telefono}}='{telefono}'",
            "maxRecords": 1,
        })
        records = r.json().get("records", [])
        return records[0] if records else None
    except Exception as e:
        print(f"[AT] Error get_conversacion: {e}")
        return None

def at_guardar_conversacion(telefono: str, historial: list, record_id: str = None):
    """Guarda/actualiza el historial de conversación."""
    try:
        # Limitar a últimos 20 turnos para no superar el límite de campo
        historial_recortado = historial[-20:]
        payload = {"fields": {
            "telefono": telefono,
            "estado_actual": "activo",
            "plan_activo": "basic",
            "datos_pedido": json.dumps(historial_recortado, ensure_ascii=False),
        }}
        if record_id:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas/{record_id}"
            requests.patch(url, headers=AT_HEADERS(), json=payload)
        else:
            url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
            requests.post(url, headers=AT_HEADERS(), json={"records": [payload]})
    except Exception as e:
        print(f"[AT] Error guardar_conversacion: {e}")

def at_crear_reserva(datos: dict) -> dict:
    """Guarda la reserva en la tabla Reservas."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        campos = {
            "Nombre":      datos.get("nombre", ""),
            "telefono":    datos.get("telefono", ""),
            "Fecha":       datos.get("fecha_iso", ""),
            "Hora":        datos.get("hora", ""),
            "Personas":    int(datos.get("personas", 1)),
            "Estado":      "pendiente",
            "nro_reserva": datos.get("nro_reserva", ""),
            "tipo":        datos.get("tipo_reserva", "simple"),
            "Especificaciones": datos.get("especificaciones", ""),
        }
        r = requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": campos}]})
        return {"ok": r.status_code == 200, "resp": r.json()}
    except Exception as e:
        print(f"[AT] Error crear_reserva: {e}")
        return {"ok": False, "error": str(e)}

def at_crear_pedido(datos: dict) -> dict:
    """Guarda el pedido en la tabla pedidos."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        campos = {
            "telefono":   datos.get("telefono", ""),
            "detalle":    datos.get("detalle", ""),
            "total":      float(datos.get("total", 0)),
            "nro_pedido": datos.get("nro_pedido", ""),
            "estado":     "pendiente",
        }
        r = requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": campos}]})
        return {"ok": r.status_code == 200, "resp": r.json()}
    except Exception as e:
        print(f"[AT] Error crear_pedido: {e}")
        return {"ok": False, "error": str(e)}

def notificar_dueno(mensaje: str):
    """Envía notificación al dueño por Evolution API."""
    evo_url = os.environ.get("EVOLUTION_API_URL", "")
    evo_instance = os.environ.get("EVOLUTION_INSTANCE", "")
    evo_key = os.environ.get("EVOLUTION_API_KEY", "")
    if not all([evo_url, evo_instance, evo_key, NUMERO_DUENO]):
        print(f"[Dueño] No configurado. Mensaje: {mensaje}")
        return
    try:
        requests.post(
            f"{evo_url}/message/sendText/{evo_instance}",
            headers={"apikey": evo_key, "Content-Type": "application/json"},
            json={"number": NUMERO_DUENO, "text": mensaje},
            timeout=10,
        )
    except Exception as e:
        print(f"[Dueño] Error notificar: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# EJECUTAR ACCIONES DEL AGENTE
# ─────────────────────────────────────────────────────────────────────────────
def ejecutar_accion(accion: dict, tel: str) -> dict:
    """
    Ejecuta la acción y devuelve:
    - ok: bool (si se guardó realmente en Airtable)
    - mensaje_confirmacion: texto real a enviar al cliente
    - mensaje_error: texto de error a enviar si falló
    """
    tipo = accion.get("tipo")

    if tipo == "crear_reserva":
        nro = f"RSV-{str(uuid.uuid4())[:5].upper()}"
        resultado = at_crear_reserva({
            **accion,
            "telefono": tel,
            "nro_reserva": nro,
            "especificaciones": accion.get("nota", ""),
        })
        print(f"[Acción] Crear reserva → {resultado}")

        if resultado.get("ok"):
            # Notificar al dueño solo si se guardó correctamente
            notificar_dueno(
                f"🆕 *Nueva Reserva* #{nro}\n"
                f"👤 {accion.get('nombre')}\n"
                f"👥 {accion.get('personas')} personas\n"
                f"📅 {accion.get('fecha_legible', accion.get('fecha_iso'))} a las {accion.get('hora')}\n"
                f"📞 {tel}"
            )
            return {
                "ok": True,
                "mensaje_confirmacion": (
                    f"✅ *Reserva confirmada y registrada*\n\n"
                    f"📋 N° *{nro}*\n"
                    f"👤 {accion.get('nombre')}\n"
                    f"👥 {accion.get('personas')} personas\n"
                    f"📅 {accion.get('fecha_legible', accion.get('fecha_iso'))} a las {accion.get('hora')} hs\n\n"
                    f"¡Lo esperamos en La Parrilla de Don Alberto! 🍖"
                )
            }
        else:
            error_detalle = resultado.get("resp", {}).get("error", {}).get("message", str(resultado))
            print(f"[Acción] FALLO al guardar reserva: {error_detalle}")
            return {
                "ok": False,
                "mensaje_error": (
                    f"⚠️ Ocurrió un problema al registrar su reserva en nuestro sistema.\n\n"
                    f"Por favor, comuníquese directamente con el restaurante para confirmar su lugar.\n"
                    f"Disculpe los inconvenientes."
                )
            }

    elif tipo == "crear_pedido":
        nro = f"PED-{str(uuid.uuid4())[:5].upper()}"
        resultado = at_crear_pedido({
            **accion,
            "telefono": tel,
            "nro_pedido": nro,
        })
        print(f"[Acción] Crear pedido → {resultado}")

        if resultado.get("ok"):
            notificar_dueno(
                f"🛵 *Nuevo Pedido Delivery* #{nro}\n"
                f"📦 {accion.get('detalle')}\n"
                f"💰 ${accion.get('total')} ARS\n"
                f"📞 {tel}"
            )
            return {
                "ok": True,
                "mensaje_confirmacion": (
                    f"✅ *Pedido registrado*\n\n"
                    f"📦 N° *{nro}*\n"
                    f"🛵 Tiempo estimado: 45-60 minutos\n\n"
                    f"El equipo confirm​ará su pedido en breve. ¡Gracias!"
                )
            }
        else:
            return {
                "ok": False,
                "mensaje_error": "⚠️ No se pudo registrar el pedido. Por favor comuníquese directamente con el restaurante."
            }

    elif tipo == "notificar_dueno":
        notificar_dueno(accion.get("mensaje", ""))
        return {"ok": True, "mensaje_confirmacion": None}

    return {"ok": True, "mensaje_confirmacion": None}

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────
class MensajeEntrante(BaseModel):
    telefono:    str
    mensaje:     str
    tiene_imagen: bool = False
    es_admin:    bool = False

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/basico/mensaje", summary="Plan BASIC: Agente conversacional con Gemini")
async def manejar_mensaje(entrada: MensajeEntrante):
    try:
        tel = entrada.telefono.strip()
        msg = entrada.mensaje.strip()

        # Cargar historial desde Airtable
        conv = at_get_conversacion(tel)
        record_id = conv["id"] if conv else None
        historial_raw = conv["fields"].get("datos_pedido", "[]") if conv else "[]"
        try:
            historial = json.loads(historial_raw)
            # Si quedó historial viejo del formato anterior (dict o no lista), reiniciar
            if not isinstance(historial, list):
                historial = []
        except Exception:
            historial = []

        # Convertir historial al formato que espera Gemini
        history_gemini = []
        for turno in historial:
            if turno.get("role") in ["user", "model"]:
                history_gemini.append({
                    "role": turno["role"],
                    "parts": [{"text": turno["content"]}],
                })

        # Crear chat con historial
        chat = modelo.start_chat(history=history_gemini)

        # Enviar mensaje del usuario
        prefix = "[ADMIN] " if entrada.es_admin else ""
        response = chat.send_message(f"{prefix}{msg}")
        respuesta_completa = response.text.strip()

        # Separar acción del texto de respuesta
        texto_respuesta = respuesta_completa
        accion = None

        if "ACCION:" in respuesta_completa:
            partes = respuesta_completa.split("ACCION:", 1)
            texto_respuesta = partes[0].strip()
            try:
                accion_raw = partes[1].strip()
                # Limpiar posibles backticks
                accion_raw = accion_raw.replace("```json", "").replace("```", "").strip()
                accion = json.loads(accion_raw)
            except Exception as e:
                print(f"[Acción] Error parseando: {e}, raw={partes[1][:100]}")

        # Ejecutar acción si existe y usar su resultado real
        texto_final = texto_respuesta
        if accion:
            resultado_accion = ejecutar_accion(accion, tel)
            if resultado_accion.get("mensaje_confirmacion"):
                # Reemplazar el mensaje del agente con la confirmación real de Airtable
                texto_final = resultado_accion["mensaje_confirmacion"]
            elif not resultado_accion.get("ok"):
                # Si falló, reemplazar con mensaje de error honesto
                texto_final = resultado_accion.get("mensaje_error", "⚠️ Ocurrió un error al procesar su solicitud.")

        # Actualizar historial
        historial.append({"role": "user", "content": msg})
        historial.append({"role": "model", "content": texto_final})
        at_guardar_conversacion(tel, historial, record_id)

        return {
            "respuesta": texto_final,
            "tipo_mensaje": "texto",
            "accion_ejecutada": accion.get("tipo") if accion else None,
        }

    except Exception as e:
        import traceback
        print(f"[FATAL] {traceback.format_exc()}")
        return {
            "respuesta": "Disculpá, tuve un problema técnico. Intentá de nuevo en un momento 🙏",
            "tipo_mensaje": "texto",
            "_error": str(e),
        }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS DE DEBUG (quitar en producción)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/debug/airtable", summary="Debug: Estado de Airtable")
def debug_airtable():
    resultado = {
        "AIRTABLE_API_KEY": f"✅ ({len(AIRTABLE_API_KEY)} chars)" if AIRTABLE_API_KEY else "❌ vacía",
        "AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
        "GEMINI_API_KEY":   f"✅ ({len(GEMINI_API_KEY)} chars)" if GEMINI_API_KEY else "❌ vacía",
    }
    try:
        r = requests.get(f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas?maxRecords=1", headers=AT_HEADERS())
        resultado["conversaciones_status"] = r.status_code
    except Exception as e:
        resultado["error"] = str(e)
    return resultado

@router.get("/debug/test-reserva", summary="Debug: Crear reserva de prueba")
def debug_test_reserva():
    resultado = at_crear_reserva({
        "nombre": "TEST_DEBUG", "telefono": "000000",
        "fecha_iso": "2026-03-08", "hora": "21:00",
        "personas": 2, "tipo_reserva": "simple",
        "nro_reserva": "RSV-TEST",
    })
    return resultado

@router.get("/debug/reset/{telefono}", summary="Debug: Borrar conversación")
def debug_reset(telefono: str):
    conv = at_get_conversacion(telefono)
    if not conv:
        return {"ok": False, "msg": "No se encontró conversación"}
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas/{conv['id']}"
        requests.delete(url, headers=AT_HEADERS())
        return {"ok": True, "msg": f"Conversación de {telefono} eliminada"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
