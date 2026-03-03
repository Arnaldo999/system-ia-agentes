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

SYSTEM_PROMPT = f"""Sos el asistente virtual de *{RESTAURANTE['nombre']}*, un restaurante de parrilla argentina.
Hoy es {HOY}.
Horario de atención: {RESTAURANTE['horario']}.

MENÚ COMPLETO:
{_menu_texto()}

TU ROL:
- Atendés clientes por WhatsApp de forma cálida, eficiente y profesional
- Respondés en español argentino (vos, che, etc.)
- Podés mostrar el menú, tomar reservas y pedidos delivery
- Corrección de fechas: SIEMPRE verificás que el día de la semana coincida con la fecha. Si el cliente dice "sábado 8 de marzo" pero el 8 es domingo, lo corregís amablemente.
- Cuando tomás una reserva, necesitás: nombre, cantidad de personas, fecha y horario
- Para reservas con seña: calculás el 30% del consumo estimado (~$3000 ARS/persona) y pedís transferencia al alias: {RESTAURANTE['alias_pago']}
- Para delivery: anotás el pedido y lo enviás al dueño para confirmación
- Sos conciso: máximo 5-6 líneas por mensaje salvo que muestres el menú completo

ACCIONES DISPONIBLES (cuando sea necesario, incluilas en tu respuesta en formato JSON al final):
Para crear una reserva cuando tengas TODOS los datos (nombre, personas, fecha, hora):
ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "HH:MM", "tipo_reserva": "simple|con_seña"}}

Para registrar un pedido delivery:
ACCION: {{"tipo": "crear_pedido", "detalle": "...", "total": N}}

Para notificar al dueño:
ACCION: {{"tipo": "notificar_dueno", "mensaje": "..."}}

IMPORTANTE: La línea ACCION va SIEMPRE al final del mensaje, nunca en el medio. Si no necesitás hacer ninguna acción, no incluyas la línea ACCION."""

# ─────────────────────────────────────────────────────────────────────────────
# MODELO GEMINI
# ─────────────────────────────────────────────────────────────────────────────
modelo = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite-preview-06-17",
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
def ejecutar_accion(accion: dict, tel: str) -> str | None:
    """Ejecuta la acción indicada por el agente y devuelve confirmación opcional."""
    tipo = accion.get("tipo")

    if tipo == "crear_reserva":
        nro = f"RSV-{str(uuid.uuid4())[:5].upper()}"
        resultado = at_crear_reserva({
            **accion,
            "telefono": tel,
            "nro_reserva": nro,
            "especificaciones": accion.get("nota", ""),
        })
        print(f"[Acción] Reserva creada: {resultado}")
        # Notificar al dueño
        notificar_dueno(
            f"🆕 *Nueva Reserva* #{nro}\n"
            f"👤 {accion.get('nombre')}\n"
            f"👥 {accion.get('personas')} personas\n"
            f"📅 {accion.get('fecha_legible')} a las {accion.get('hora')}\n"
            f"📞 {tel}"
        )
        return None  # El agente ya generó el mensaje de confirmación

    elif tipo == "crear_pedido":
        nro = f"PED-{str(uuid.uuid4())[:5].upper()}"
        resultado = at_crear_pedido({
            **accion,
            "telefono": tel,
            "nro_pedido": nro,
        })
        print(f"[Acción] Pedido creado: {resultado}")
        notificar_dueno(
            f"🛵 *Nuevo Pedido Delivery* #{nro}\n"
            f"📦 {accion.get('detalle')}\n"
            f"💰 ${accion.get('total')} ARS\n"
            f"📞 {tel}"
        )
        return None

    elif tipo == "notificar_dueno":
        notificar_dueno(accion.get("mensaje", ""))
        return None

    return None

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

        # Ejecutar acción si existe
        if accion:
            ejecutar_accion(accion, tel)

        # Actualizar historial
        historial.append({"role": "user", "content": msg})
        historial.append({"role": "model", "content": texto_respuesta})
        at_guardar_conversacion(tel, historial, record_id)

        return {
            "respuesta": texto_respuesta,
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

@router.delete("/debug/reset/{telefono}", summary="Debug: Borrar conversación")
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
