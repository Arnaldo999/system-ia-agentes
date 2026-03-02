"""
Worker Gastronómico BASIC — Opción C: Gemini Directo + Airtable como Estado
=============================================================================
Single endpoint que maneja toda la conversación con máquina de estados.
Sin CrewAI → usa google-generativeai directamente → ~80MB RAM en Render.

Flujo n8n:
  Webhook (Evolution API) → POST /gastronomico/basico/mensaje → Evolution API (respuesta)

Variables de entorno requeridas en Render/Easypanel:
  GEMINI_API_KEY       → Google AI Studio
  AIRTABLE_API_KEY     → Token de Airtable
  AIRTABLE_BASE_ID     → appdA5rJOmtVpDrx (base Automatizacion-Restaurantes)
  NUMERO_DUENO         → +54911XXXXXXXX (para filtrar comandos admin)
"""

import os
import uuid
import json
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import google.generativeai as genai

router = APIRouter(prefix="/gastronomico", tags=["SaaS Gastronómico"])

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appdA5rJOmtVpDrx")
NUMERO_DUENO     = os.environ.get("NUMERO_DUENO", "")

genai.configure(api_key=GEMINI_API_KEY)
modelo = genai.GenerativeModel("gemini-2.5-flash-lite")

# ─────────────────────────────────────────────────────────────────────────────
# DATOS DEL RESTAURANTE DEMO (en producción vendrían de Airtable o Supabase)
# ─────────────────────────────────────────────────────────────────────────────
RESTAURANTE_DEMO = {
    "nombre":          "La Parrilla de Don Alberto",
    "cvu_alias":       "donalberto.parrilla",
    "horario":         "Martes a Domingo, 12hs a 00hs",
    "numero_dueno":    NUMERO_DUENO,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE AIRTABLE
# ─────────────────────────────────────────────────────────────────────────────
AT_HEADERS = lambda: {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type":  "application/json"
}

def at_buscar_conversacion(telefono: str) -> Optional[dict]:
    """Busca la conversación activa de un teléfono. Devuelve el record o None."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
    r = requests.get(url, headers=AT_HEADERS(), params={"filterByFormula": f"{{telefono}}='{telefono}'"})
    records = r.json().get("records", [])
    return records[0] if records else None

def at_crear_conversacion(telefono: str, estado: str, datos: dict = {}) -> str:
    """Crea un nuevo registro de conversación. Devuelve el record ID."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
    payload = {"records": [{"fields": {
        "telefono":            telefono,
        "estado_actual":       estado,
        "plan_activo":         "basic",
        "datos_pedido":        json.dumps(datos, ensure_ascii=False),
    }}]}
    r = requests.post(url, headers=AT_HEADERS(), json=payload)
    return r.json()["records"][0]["id"]

def at_actualizar_conversacion(record_id: str, estado: str, datos: dict = {}):
    """Actualiza el estado y datos de una conversación existente."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas/{record_id}"
    requests.patch(url, headers=AT_HEADERS(), json={"fields": {
        "estado_actual": estado,
        "datos_pedido":  json.dumps(datos, ensure_ascii=False),
    }})

def at_crear_reserva(datos: dict):
    """Guarda la reserva en la tabla Reservas."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
    requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": datos}]})

def at_crear_pedido(datos: dict):
    """Guarda el pedido en la tabla pedidos."""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
    requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": datos}]})


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE GEMINI
# ─────────────────────────────────────────────────────────────────────────────
def gemini(prompt: str) -> str:
    """Llama a Gemini y devuelve el texto de respuesta."""
    try:
        r = modelo.generate_content(prompt)
        return r.text.strip()
    except Exception as e:
        return f"Lo siento, tuve un problema técnico. Por favor intentá de nuevo. ({str(e)[:50]})"


# ─────────────────────────────────────────────────────────────────────────────
# MODELO DE DATOS
# ─────────────────────────────────────────────────────────────────────────────
class MensajeEntrante(BaseModel):
    telefono:       str
    mensaje:        str
    tiene_imagen:   bool = False
    es_admin:       bool = False   # n8n lo detecta comparando con NUMERO_DUENO


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT PRINCIPAL — MÁQUINA DE ESTADOS
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/basico/mensaje", summary="Plan BASIC: Maneja toda la conversación con máquina de estados")
async def manejar_mensaje(entrada: MensajeEntrante):
    """
    Recibe cada mensaje de WhatsApp desde n8n.
    Lee el estado actual de Airtable, procesa el mensaje con Gemini, y devuelve la respuesta.
    n8n se encarga SOLO de enviar esa respuesta por WhatsApp (Evolution API).
    """
    tel = entrada.telefono.strip()
    msg = entrada.mensaje.strip()
    res = RESTAURANTE_DEMO

    # ── Leer estado actual desde Airtable ───────────────────────────────────
    conv = at_buscar_conversacion(tel)
    estado    = conv["fields"].get("estado_actual", "nuevo") if conv else "nuevo"
    datos_raw = conv["fields"].get("datos_pedido", "{}") if conv else "{}"
    record_id = conv["id"] if conv else None

    try:
        datos = json.loads(datos_raw)
    except Exception:
        datos = {}

    # ────────────────────────────────────────────────────────────────────────
    # RUTA ADMIN: El dueño confirma el pago
    # ────────────────────────────────────────────────────────────────────────
    if entrada.es_admin and "pago confirmado" in msg.lower():
        # Buscar conversación con estado verificando_pago
        # (en producción se podría incluir el teléfono del cliente en el mensaje del dueño)
        nro = datos.get("nro_pedido", "N/A")
        tipo = datos.get("tipo", "pedido")

        if tipo == "delivery":
            ticket = gemini(f"""
Generá un ticket de entrega de delivery para WhatsApp del restaurante '{res['nombre']}'.
Datos del pedido:
- N° Pedido: {nro}
- Items: {datos.get('detalle', 'ver pedido')}
- Total: ${datos.get('total', 0)} ARS
- Estado: PAGADO Y CONFIRMADO ✅

El ticket debe tener emojis, ser claro y breve (máximo 8 líneas).
Incluí un mensaje de agradecimiento y el tiempo estimado de entrega (30-45 min).
Respondé SOLO el texto del mensaje de WhatsApp.
""")
        else:
            ticket = gemini(f"""
Generá un ticket de confirmación de RESERVA para WhatsApp del restaurante '{res['nombre']}'.
Datos:
- N° Reserva: {nro}
- Nombre: {datos.get('nombre_cliente', 'Cliente')}
- Personas: {datos.get('personas', '?')}
- Fecha: {datos.get('fecha', '?')}
- Hora: {datos.get('hora', '?')}
- Seña: CONFIRMADA ✅

Formato de ticket con emojis, breve y profesional (máximo 8 líneas).
Respondé SOLO el texto del mensaje de WhatsApp.
""")

        at_actualizar_conversacion(record_id, "completado", {})
        return {
            "respuesta": ticket,
            "estado_nuevo": "completado",
            "accion_extra": "notificar_cliente",
            "telefono_cliente": datos.get("telefono_cliente", tel)
        }

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: nuevo o desconocido → Bienvenida + menú de opciones
    # ────────────────────────────────────────────────────────────────────────
    if estado in ["nuevo", "completado", "cancelado"] or not conv:
        bienvenida = gemini(f"""
Sos el asistente virtual del restaurante '{res['nombre']}'.
Un cliente escribió: "{msg}"
Horario de atención: {res['horario']}.

Respondé con una BIENVENIDA CÁLIDA y corta, luego mostrá estas opciones numeradas:
1️⃣ Ver el Menú del día
2️⃣ Reservar / Modificar / Cancelar una reserva
3️⃣ Reservar con seña (asegurá tu lugar)
4️⃣ Pedir para llevar (Delivery)

Tono: amigable, español neutro, máximo 8 líneas. SOLO el texto del mensaje.
""")
        if conv:
            at_actualizar_conversacion(record_id, "esperando_opcion", {})
        else:
            at_crear_conversacion(tel, "esperando_opcion")

        return {"respuesta": bienvenida, "estado_nuevo": "esperando_opcion"}

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: esperando_opcion → Detectar opción elegida
    # ────────────────────────────────────────────────────────────────────────
    if estado == "esperando_opcion":
        intencion = gemini(f"""
El cliente respondió: "{msg}"
Las opciones disponibles eran:
1 = Ver menú, 2 = Reservar, 3 = Seña para reserva, 4 = Delivery

Respondé SOLO con el número de opción: 1, 2, 3 o 4.
Si no es claro, respondé 0.
""").strip()

        if "1" in intencion:
            menu_txt = gemini(f"""
Sos el asistente de '{res['nombre']}'. 
Generá un menú del día ficticio y apetitoso para un restaurante de parrilla argentina.
Incluí sección de entradas, platos principales y postres con precios en ARS.
Formato WhatsApp con emojis, máximo 12 líneas. SOLO el texto del mensaje.
Terminá ofreciendo: "¿Querés hacer un pedido o reservar? 🙌"
""")
            at_actualizar_conversacion(record_id, "esperando_opcion", datos)
            return {"respuesta": menu_txt, "estado_nuevo": "esperando_opcion"}

        elif "2" in intencion:
            resp = f"¡Perfecto! 📅 Para reservar tu mesa en *{res['nombre']}* necesito algunos datos:\n\n¿A nombre de quién va la reserva?"
            at_actualizar_conversacion(record_id, "datos_reserva", {"paso": "nombre", "tipo": "reserva_simple"})
            return {"respuesta": resp, "estado_nuevo": "datos_reserva"}

        elif "3" in intencion:
            resp = f"¡Genial! 🎯 Para asegurarte el lugar con seña en *{res['nombre']}*:\n\n¿A nombre de quién va la reserva?"
            at_actualizar_conversacion(record_id, "datos_reserva", {"paso": "nombre", "tipo": "reserva_con_seña"})
            return {"respuesta": resp, "estado_nuevo": "datos_reserva"}

        elif "4" in intencion:
            menu_delivery = gemini(f"""
Sos el asistente de '{res['nombre']}' para pedidos delivery.
Generá un menú del día ficticio para parrilla argentina con precios en ARS.
Formato WhatsApp con emojis. Máximo 10 líneas.
Terminá con: "¿Qué te gustaría pedir? 🛵"
SOLO el texto del mensaje.
""")
            at_actualizar_conversacion(record_id, "datos_delivery", {"tipo": "delivery"})
            return {"respuesta": menu_delivery, "estado_nuevo": "datos_delivery"}

        else:
            return {"respuesta": "¡Disculpá! No entendí tu respuesta. Por favor respondé con el número de opción: 1, 2, 3 o 4 👆", "estado_nuevo": "esperando_opcion"}

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: datos_reserva → Captura paso a paso de los datos
    # ────────────────────────────────────────────────────────────────────────
    if estado == "datos_reserva":
        paso = datos.get("paso", "nombre")

        if paso == "nombre":
            datos["nombre_cliente"] = msg
            datos["paso"] = "personas"
            at_actualizar_conversacion(record_id, "datos_reserva", datos)
            return {"respuesta": f"Perfecto *{msg}* 😊 ¿Para cuántas personas es la reserva?", "estado_nuevo": "datos_reserva"}

        elif paso == "personas":
            datos["personas"] = msg
            datos["paso"] = "fecha"
            at_actualizar_conversacion(record_id, "datos_reserva", datos)
            return {"respuesta": "¿Para qué fecha? 📅 (ej: sábado 8 de marzo)", "estado_nuevo": "datos_reserva"}

        elif paso == "fecha":
            datos["fecha"] = msg
            datos["paso"] = "hora"
            at_actualizar_conversacion(record_id, "datos_reserva", datos)
            return {"respuesta": "¿A qué horario? ⏰ (ej: 21hs)", "estado_nuevo": "datos_reserva"}

        elif paso == "hora":
            datos["hora"] = msg
            datos["paso"] = "completo"
            nro = f"RSV-{str(uuid.uuid4())[:5].upper()}"
            datos["nro_pedido"] = nro
            datos["telefono_cliente"] = tel

            # Guardar reserva en Airtable
            campos_reserva = {
                "Nombre":      datos["nombre_cliente"],
                "Fecha":       datos["fecha"],
                "Hora":        datos["hora"],
                "Personas":    int(datos.get("personas", 1)),
                "Estado":      "pendiente",
                "Nro_Reserva": nro,
                "Telefono":    tel,
                "Tipo":        datos.get("tipo", "reserva_simple"),
            }
            at_crear_reserva(campos_reserva)

            if datos.get("tipo") == "reserva_con_seña":
                msg_pago = gemini(f"""
El cliente {datos['nombre_cliente']} reservó una mesa para {datos['personas']} personas
el {datos['fecha']} a las {datos['hora']} en '{res['nombre']}'.
N° de Reserva: {nro}

Generá un mensaje de WhatsApp pidiendo la seña para confirmar el lugar.
La seña es del 30% del consumo estimado (aprox $3000 ARS por persona para {datos['personas']} personas).
Calculalo y pedí la transferencia al alias: {res['cvu_alias']}
Pedí que manden la captura del pago para confirmar.
Español amigable, máximo 8 líneas, con emojis. SOLO el texto.
""")
                at_actualizar_conversacion(record_id, "esperando_pago", datos)
                return {"respuesta": msg_pago, "estado_nuevo": "esperando_pago"}
            else:
                confirmacion = f"✅ *Reserva Confirmada* en {res['nombre']}!\n\n📋 N° *{nro}*\n👤 {datos['nombre_cliente']}\n👥 {datos['personas']} personas\n📅 {datos['fecha']} a las {datos['hora']}\n\n¡Te esperamos! Si necesitás modificarla, escribinos 😊"
                at_actualizar_conversacion(record_id, "completado", {})
                return {"respuesta": confirmacion, "estado_nuevo": "completado"}

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: datos_delivery → El cliente dice qué quiere pedir
    # ────────────────────────────────────────────────────────────────────────
    if estado == "datos_delivery":
        nro = f"PED-{str(uuid.uuid4())[:5].upper()}"
        total_estimado = gemini(f"""
El cliente pidió: "{msg}" para delivery de una parrilla argentina.
Calculá el total estimado basado en precios promedio argentinos (2025).
Respondé SOLO con el número del total en ARS, sin texto adicional. Solo el número.
""").strip().replace("$", "").replace(".", "").replace(",", "").split()[0]

        try:
            total = int(total_estimado)
        except Exception:
            total = 3500

        datos.update({"detalle": msg, "total": total, "nro_pedido": nro, "telefono_cliente": tel})

        # Guardar pedido en Airtable
        at_crear_pedido({
            "nro_pedido":      nro,
            "telefono_cliente": tel,
            "tipo":            "delivery",
            "detalle":         msg,
            "total_ars":       total,
            "estado_pago":     "pendiente",
        })

        msg_pago = gemini(f"""
El cliente pidió: "{msg}" para delivery.
Total estimado: ${total} ARS.
N° de pedido: {nro}

Generá el resumen del pedido y pedí la transferencia al alias: {res['cvu_alias']}
Aclará que deben mandar la captura del pago para que arranquemos a preparar.
Español amigable, máximo 8 líneas, emojis. SOLO el texto del mensaje de WhatsApp.
""")
        at_actualizar_conversacion(record_id, "esperando_pago", datos)
        return {"respuesta": msg_pago, "estado_nuevo": "esperando_pago"}

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: esperando_pago → Cliente envía imagen o sigue con texto
    # ────────────────────────────────────────────────────────────────────────
    if estado == "esperando_pago":
        if entrada.tiene_imagen:
            datos["tiene_comprobante"] = True
            at_actualizar_conversacion(record_id, "verificando_pago", datos)
            return {
                "respuesta":           "¡Recibimos tu comprobante! ⏳ El equipo lo está verificando. En breve te confirmamos.",
                "estado_nuevo":        "verificando_pago",
                "notificar_dueno":     True,
                "mensaje_para_dueno":  f"🔔 *Nuevo pago pendiente*\n• N°: {datos.get('nro_pedido','?')}\n• Pedido: {datos.get('detalle', datos.get('tipo','?'))}\n• Total: ${datos.get('total','?')} ARS\n• Cliente: {tel}\n\nVerificá la transferencia y respondé: *PAGO CONFIRMADO*",
            }
        else:
            return {"respuesta": f"Cuando hagas la transferencia al alias *{res['cvu_alias']}*, mandame la captura 📸 y confirmamos tu pedido!", "estado_nuevo": "esperando_pago"}

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: verificando_pago → Solo el dueño puede avanzar
    # ────────────────────────────────────────────────────────────────────────
    if estado == "verificando_pago":
        return {"respuesta": "Tu pago está siendo verificado ⏳. En breve te confirmamos. ¡Gracias por tu paciencia!", "estado_nuevo": "verificando_pago"}

    # Fallback
    return {"respuesta": "¡Hola! ¿En qué te puedo ayudar hoy? 😊", "estado_nuevo": "nuevo"}
