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
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appdA5rJOmtVvpDrx")
NUMERO_DUENO     = os.environ.get("NUMERO_DUENO", "")

genai.configure(api_key=GEMINI_API_KEY)
modelo = genai.GenerativeModel("gemini-2.5-flash-lite")


@router.get("/debug/airtable", summary="Debug: Verifica conexión con Airtable")
def debug_airtable():
    """Prueba la conexión con Airtable y devuelve el resultado."""
    resultado = {
        "AIRTABLE_API_KEY": f"✅ ({len(AIRTABLE_API_KEY)} chars)" if AIRTABLE_API_KEY else "❌ vacía",
        "AIRTABLE_API_KEY_inicio": AIRTABLE_API_KEY[:10] + "..." if AIRTABLE_API_KEY else "N/A",
        "AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    }
    # Test 1: Listar bases disponibles con este token
    try:
        r1 = requests.get("https://api.airtable.com/v0/meta/bases", headers=AT_HEADERS())
        resultado["bases_status"] = r1.status_code
        if r1.status_code == 200:
            bases = r1.json().get("bases", [])
            resultado["bases_disponibles"] = [{"id": b["id"], "name": b["name"]} for b in bases]
        else:
            resultado["bases_error"] = r1.json()
    except Exception as e:
        resultado["bases_error"] = str(e)
    # Test 2: Ver campos reales de la tabla
    try:
        schema_url = f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables"
        r_schema = requests.get(schema_url, headers=AT_HEADERS())
        if r_schema.status_code == 200:
            for t in r_schema.json().get("tables", []):
                if t["name"] == "conversaciones_activas":
                    resultado["campos_reales"] = [f["name"] for f in t.get("fields", [])]
                    break
        else:
            resultado["schema_error"] = r_schema.json()
    except Exception as e:
        resultado["schema_error"] = str(e)
    # Test 3: Intentar escribir un registro de prueba
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
        test_payload = {"records": [{"fields": {
            "telefono": "TEST_DEBUG",
            "estado_actual": "test",
            "plan_activo": "basic",
            "datos_pedido": "{}"
        }}]}
        r_write = requests.post(url, headers=AT_HEADERS(), json=test_payload)
        resultado["test_escritura_status"] = r_write.status_code
        resultado["test_escritura_resp"] = r_write.json()
    except Exception as e:
        resultado["test_escritura_error"] = str(e)
    return resultado


@router.get("/debug/test-reserva", summary="Debug: Crea una reserva de prueba")
def debug_test_reserva():
    """Intenta crear una reserva de prueba para ver errores de Airtable."""
    campos = {
        "Nombre": "TEST_DEBUG",
        "telefono": "000000",
        "Fecha": "2026-03-08",
        "Hora": "21:00",
        "Personas": 3,
        "Estado": "pendiente",
        "nro_reserva": "RSV-TEST1",
        "tipo": "reserva_simple",
    }
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        r = requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": campos}]})
        return {"status": r.status_code, "respuesta": r.json(), "campos_enviados": campos}
    except Exception as e:
        return {"error": str(e)}

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
# MENÚ DEMO — Categorías con 3 ítems cada una
# ─────────────────────────────────────────────────────────────────────────────
MENU_DEMO = {
    "principales": {
        "emoji": "🥩",
        "nombre": "Platos Principales",
        "descripcion": "Carnes y platos fuertes",
        "items": [
            {"nombre": "Asado de Tira (400gr) con papas fritas", "precio": 6800},
            {"nombre": "Bife de Chorizo (300gr) con ensalada mixta", "precio": 7500},
            {"nombre": "Bondiola Braseada con puré de calabaza", "precio": 5900},
        ]
    },
    "entradas": {
        "emoji": "🥗",
        "nombre": "Entradas",
        "descripcion": "Picadas y starters",
        "items": [
            {"nombre": "Provoleta Fundida con orégano", "precio": 2500},
            {"nombre": "Empanadas Tucumanas (3 un.)", "precio": 2700},
            {"nombre": "Tabla de Fiambres para compartir", "precio": 4500},
        ]
    },
    "postres": {
        "emoji": "🍰",
        "nombre": "Postres",
        "descripcion": "Dulces caseros",
        "items": [
            {"nombre": "Flan Casero con dulce de leche", "precio": 1500},
            {"nombre": "Mousse de Chocolate", "precio": 1600},
            {"nombre": "Panqueques con dulce de leche", "precio": 1800},
        ]
    },
    "cafeteria": {
        "emoji": "☕",
        "nombre": "Cafetería",
        "descripcion": "Cafés e infusiones",
        "items": [
            {"nombre": "Café Espresso", "precio": 800},
            {"nombre": "Cortado con medialunas (2)", "precio": 1200},
            {"nombre": "Submarino", "precio": 1100},
        ]
    },
    "bebidas": {
        "emoji": "🍷",
        "nombre": "Bebidas",
        "descripcion": "Vinos, cervezas y más",
        "items": [
            {"nombre": "Vino Malbec (copa)", "precio": 2200},
            {"nombre": "Cerveza Artesanal (pint)", "precio": 1800},
            {"nombre": "Limonada con menta", "precio": 1200},
        ]
    },
}


def _respuesta_lista_categorias():
    """Genera la respuesta interactiva con la lista de categorías del menú."""
    return {
        "title": "📋 Menú del Día",
        "description": f"Elegí la categoría que quieras ver 👇",
        "buttonText": "Ver Categorías",
        "footerText": RESTAURANTE_DEMO["nombre"],
        "sections": [{
            "title": "Categorías",
            "rows": [
                {"title": f"{cat['emoji']} {cat['nombre']}", "description": cat["descripcion"], "rowId": key}
                for key, cat in MENU_DEMO.items()
            ]
        }]
    }


def _respuesta_lista_items(categoria_key: str):
    """Genera la respuesta interactiva con los ítems de una categoría."""
    cat = MENU_DEMO[categoria_key]
    return {
        "title": f"{cat['emoji']} {cat['nombre']}",
        "description": f"Elegí lo que más te guste 😋",
        "buttonText": "Ver Opciones",
        "footerText": RESTAURANTE_DEMO["nombre"],
        "sections": [{
            "title": cat["nombre"],
            "rows": [
                {"title": item["nombre"], "description": f"${item['precio']:,} ARS".replace(',','.'), "rowId": f"{categoria_key}_{i}"}
                for i, item in enumerate(cat["items"])
            ]
        }]
    }


def _respuesta_botones_accion(item_nombre: str, item_precio: int):
    """Genera botones de acción después de elegir un ítem."""
    return {
        "title": "¿Qué querés hacer?",
        "description": f"Elegiste: *{item_nombre}* — ${item_precio:,} ARS\n\n¿Cómo seguimos?".replace(',','.'),
        "footerText": RESTAURANTE_DEMO["nombre"],
        "buttons": [
            {"buttonId": "reservar", "buttonText": {"displayText": "📅 Reservar mesa"}},
            {"buttonId": "delivery", "buttonText": {"displayText": "🛵 Pedir Delivery"}},
            {"buttonId": "volver", "buttonText": {"displayText": "↩️ Volver al menú"}},
        ]
    }


def _texto_categorias():
    """Texto fallback con las categorías numeradas."""
    lineas = ["📋 *Menú del Día* — Elegí una categoría:\n"]
    for i, (key, cat) in enumerate(MENU_DEMO.items(), 1):
        lineas.append(f"{i}️⃣ {cat['emoji']} *{cat['nombre']}* — {cat['descripcion']}")
    lineas.append("\nRespondé con el *número* de la categoría 👆")
    return "\n".join(lineas)


def _texto_items(categoria_key: str):
    """Texto fallback con los ítems de una categoría numerados."""
    cat = MENU_DEMO[categoria_key]
    lineas = [f"{cat['emoji']} *{cat['nombre']}*\n"]
    for i, item in enumerate(cat["items"], 1):
        lineas.append(f"{i}️⃣ {item['nombre']} — *${item['precio']:,} ARS*".replace(',','.'))
    lineas.append("\nRespondé con el *número* del plato 😋")
    return "\n".join(lineas)


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
    """Crea un nuevo registro de conversación. Devuelve el record ID o '' si falla."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
        payload = {"records": [{"fields": {
            "telefono":            telefono,
            "estado_actual":       estado,
            "plan_activo":         "basic",
            "datos_pedido":        json.dumps(datos, ensure_ascii=False),
        }}]}
        r = requests.post(url, headers=AT_HEADERS(), json=payload)
        data = r.json()
        return data["records"][0]["id"]
    except Exception as e:
        print(f"[Airtable] Error al crear conversación: {e}")
        return ""

def at_actualizar_conversacion(record_id: str, estado: str, datos: dict = {}):
    """Actualiza el estado y datos de una conversación existente."""
    if not record_id:
        return
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas/{record_id}"
        requests.patch(url, headers=AT_HEADERS(), json={"fields": {
            "estado_actual": estado,
            "datos_pedido":  json.dumps(datos, ensure_ascii=False),
        }})
    except Exception as e:
        print(f"[Airtable] Error al actualizar conversación: {e}")

def at_crear_reserva(datos: dict) -> dict:
    """Guarda la reserva en la tabla Reservas. Devuelve la respuesta de Airtable."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        r = requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": datos}]})
        resp = r.json()
        print(f"[Airtable] Crear reserva status={r.status_code} resp={resp}")
        return {"ok": r.status_code == 200, "status": r.status_code, "respuesta": resp}
    except Exception as e:
        print(f"[Airtable] Error al crear reserva: {e}")
        return {"ok": False, "error": str(e)}

def at_crear_pedido(datos: dict):
    """Guarda el pedido en la tabla pedidos."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": datos}]})
    except Exception as e:
        print(f"[Airtable] Error al crear pedido: {e}")


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
    try:
        return await _procesar_mensaje(entrada)
    except Exception as e:
        import traceback
        print(f"[FATAL] Error en manejar_mensaje: {traceback.format_exc()}")
        return {"respuesta": "Disculpá, tuve un problema técnico. Intentá de nuevo en un momento 🙏", "estado_nuevo": "nuevo", "_error": str(e)}


async def _procesar_mensaje(entrada: MensajeEntrante):
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
2️⃣ Reservar mesa
3️⃣ Reservar con seña (asegurá tu lugar)
4️⃣ Pedir Delivery 🛵

Tono: amigable, español neutro, máximo 6 líneas. SOLO el texto del mensaje.
""")
        if conv:
            at_actualizar_conversacion(record_id, "esperando_opcion", {})
        else:
            at_crear_conversacion(tel, "esperando_opcion")

        return {"respuesta": bienvenida, "estado_nuevo": "esperando_opcion", "tipo_mensaje": "texto"}

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
            # Mostrar categorías del menú como lista interactiva
            at_actualizar_conversacion(record_id, "menu_categorias", {})
            return {
                "respuesta": _texto_categorias(),
                "estado_nuevo": "menu_categorias",
                "tipo_mensaje": "lista",
                "lista": _respuesta_lista_categorias()
            }

        elif "2" in intencion:
            resp = f"¡Perfecto! 📅 Para reservar tu mesa en *{res['nombre']}* necesito algunos datos:\n\n¿A nombre de quién va la reserva?"
            at_actualizar_conversacion(record_id, "datos_reserva", {"paso": "nombre", "tipo": "reserva_simple"})
            return {"respuesta": resp, "estado_nuevo": "datos_reserva", "tipo_mensaje": "texto"}

        elif "3" in intencion:
            resp = f"¡Genial! 🎯 Para asegurarte el lugar con seña en *{res['nombre']}*:\n\n¿A nombre de quién va la reserva?"
            at_actualizar_conversacion(record_id, "datos_reserva", {"paso": "nombre", "tipo": "reserva_con_seña"})
            return {"respuesta": resp, "estado_nuevo": "datos_reserva", "tipo_mensaje": "texto"}

        elif "4" in intencion:
            # Mostrar menú para delivery como lista interactiva
            at_actualizar_conversacion(record_id, "menu_categorias", {"tipo": "delivery"})
            return {
                "respuesta": "🛵 ¡Genial! ¿Qué querés pedir?\n\n" + _texto_categorias(),
                "estado_nuevo": "menu_categorias",
                "tipo_mensaje": "lista",
                "lista": _respuesta_lista_categorias()
            }

        else:
            return {"respuesta": "¡Disculpá! No entendí tu respuesta. Por favor respondé con el número de opción: 1, 2, 3 o 4 👆", "estado_nuevo": "esperando_opcion", "tipo_mensaje": "texto"}

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: menu_categorias → El cliente elige una categoría del menú
    # ────────────────────────────────────────────────────────────────────────
    if estado == "menu_categorias":
        # Detectar categoría (por rowId de lista interactiva o texto libre)
        msg_lower = msg.lower().strip()
        categoria_key = None
        for key in MENU_DEMO:
            if key in msg_lower or MENU_DEMO[key]["nombre"].lower() in msg_lower:
                categoria_key = key
                break
        # También permitir selección por número
        categorias_ordenadas = list(MENU_DEMO.keys())
        if not categoria_key and msg_lower in ["1", "2", "3", "4", "5"]:
            idx = int(msg_lower) - 1
            if 0 <= idx < len(categorias_ordenadas):
                categoria_key = categorias_ordenadas[idx]

        if categoria_key:
            datos["categoria_actual"] = categoria_key
            at_actualizar_conversacion(record_id, "menu_items", datos)
            return {
                "respuesta": _texto_items(categoria_key),
                "estado_nuevo": "menu_items",
                "tipo_mensaje": "lista",
                "lista": _respuesta_lista_items(categoria_key)
            }
        else:
            return {
                "respuesta": "No encontré esa categoría 🤔\n\n" + _texto_categorias(),
                "estado_nuevo": "menu_categorias",
                "tipo_mensaje": "lista",
                "lista": _respuesta_lista_categorias()
            }

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: menu_items → El cliente elige un ítem del menú
    # ────────────────────────────────────────────────────────────────────────
    if estado == "menu_items":
        cat_key = datos.get("categoria_actual", "principales")
        cat = MENU_DEMO.get(cat_key, MENU_DEMO["principales"])
        msg_lower = msg.lower().strip()

        # Detectar ítem elegido por rowId, número o texto
        item_elegido = None
        item_idx = None
        # Por rowId (ej: "principales_0")
        if "_" in msg_lower:
            parts = msg_lower.split("_")
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1])
                if 0 <= idx < len(cat["items"]):
                    item_elegido = cat["items"][idx]
                    item_idx = idx
        # Por número (1, 2, 3)
        if not item_elegido and msg_lower in ["1", "2", "3"]:
            idx = int(msg_lower) - 1
            if 0 <= idx < len(cat["items"]):
                item_elegido = cat["items"][idx]
                item_idx = idx
        # Por texto parcial
        if not item_elegido:
            for i, item in enumerate(cat["items"]):
                if msg_lower in item["nombre"].lower():
                    item_elegido = item
                    item_idx = i
                    break

        if item_elegido:
            datos["item_elegido"] = item_elegido["nombre"]
            datos["item_precio"] = item_elegido["precio"]
            at_actualizar_conversacion(record_id, "menu_elegido", datos)

            # Texto fallback + botones interactivos
            txt = f"Elegiste: *{item_elegido['nombre']}* — ${item_elegido['precio']:,} ARS\n\n¿Qué querés hacer?\n\n1️⃣ 📅 Reservar mesa\n2️⃣ 🛵 Pedir Delivery\n3️⃣ ↩️ Volver al menú".replace(',','.')
            return {
                "respuesta": txt,
                "estado_nuevo": "menu_elegido",
                "tipo_mensaje": "botones",
                "botones": _respuesta_botones_accion(item_elegido["nombre"], item_elegido["precio"])
            }
        else:
            return {
                "respuesta": "No encontré ese plato 🤔\n\n" + _texto_items(cat_key),
                "estado_nuevo": "menu_items",
                "tipo_mensaje": "lista",
                "lista": _respuesta_lista_items(cat_key)
            }

    # ────────────────────────────────────────────────────────────────────────
    # ESTADO: menu_elegido → Reservar / Delivery / Volver
    # ────────────────────────────────────────────────────────────────────────
    if estado == "menu_elegido":
        msg_lower = msg.lower().strip()
        if msg_lower in ["1", "reservar", "reservar mesa", "📅"]:
            resp = f"¡Perfecto! 📅 Para reservar tu mesa en *{res['nombre']}* necesito algunos datos:\n\n¿A nombre de quién va la reserva?"
            datos["tipo"] = "reserva_simple"
            datos["paso"] = "nombre"
            at_actualizar_conversacion(record_id, "datos_reserva", datos)
            return {"respuesta": resp, "estado_nuevo": "datos_reserva", "tipo_mensaje": "texto"}

        elif msg_lower in ["2", "delivery", "pedir delivery", "🛵"]:
            datos["tipo"] = "delivery"
            at_actualizar_conversacion(record_id, "datos_delivery", datos)
            return {
                "respuesta": f"🛵 ¡Genial! Ya elegiste *{datos.get('item_elegido','')}*.\n\n¿Querés agregar algo más o confirmamos el pedido?\n\nDecime qué más querés o escribí *confirmar* para finalizar.",
                "estado_nuevo": "datos_delivery",
                "tipo_mensaje": "texto"
            }

        elif msg_lower in ["3", "volver", "volver al menú", "menu", "↩️", "volver al menu"]:
            at_actualizar_conversacion(record_id, "menu_categorias", {})
            return {
                "respuesta": _texto_categorias(),
                "estado_nuevo": "menu_categorias",
                "tipo_mensaje": "lista",
                "lista": _respuesta_lista_categorias()
            }

        else:
            return {
                "respuesta": "No entendí 🤔 Respondé:\n1️⃣ Reservar mesa\n2️⃣ Pedir Delivery\n3️⃣ Volver al menú",
                "estado_nuevo": "menu_elegido",
                "tipo_mensaje": "texto"
            }

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
            # Usar Gemini para parsear la fecha + Python para VALIDAR el día
            from datetime import date, datetime
            hoy = date.today().isoformat()
            DIAS_ES = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes", 5: "sábado", 6: "domingo"}
            MESES_ES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio", 7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}

            fecha_parsed = gemini(f"""
Hoy es {hoy}. El cliente dijo: "{msg}" como fecha para una reserva.
Extraé la fecha y respondé SOLO en formato YYYY-MM-DD. Nada más.
Si dice un día relativo ("mañana", "el viernes"), calculá la fecha real.
SOLO la fecha en formato YYYY-MM-DD.
""").strip()
            
            try:
                # Limpiar y parsear
                fecha_iso = fecha_parsed.replace('"','').replace("'","").strip()[:10]
                dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
                dia_real = DIAS_ES[dt.weekday()]
                mes_nombre = MESES_ES[dt.month]
                fecha_legible = f"{dia_real} {dt.day} de {mes_nombre}"
                
                # Verificar si el usuario dijo un día incorrecto
                msg_lower = msg.lower()
                dia_cliente = None
                for dia in DIAS_ES.values():
                    if dia in msg_lower:
                        dia_cliente = dia
                        break
                
                if dia_cliente and dia_cliente != dia_real:
                    msg_correccion = f"⚠️ *Ojo:* el {dt.day} de {mes_nombre} es *{dia_real}*, no {dia_cliente}\n\n"
                else:
                    msg_correccion = ""
                
                datos["fecha"] = fecha_iso
                datos["fecha_legible"] = fecha_legible
                datos["paso"] = "hora"
                at_actualizar_conversacion(record_id, "datos_reserva", datos)
                return {"respuesta": f"{msg_correccion}📅 Perfecto, reserva para el *{fecha_legible}*.\n\n¿A qué horario? ⏰ (ej: 21hs)", "estado_nuevo": "datos_reserva", "tipo_mensaje": "texto"}
            except Exception as e:
                print(f"[Fecha] Error parseando: {e}, raw={fecha_parsed}")
                datos["fecha"] = msg
                datos["fecha_legible"] = msg
                datos["paso"] = "hora"
                at_actualizar_conversacion(record_id, "datos_reserva", datos)
                return {"respuesta": "¿A qué horario? ⏰ (ej: 21hs)", "estado_nuevo": "datos_reserva", "tipo_mensaje": "texto"}

        elif paso == "hora":
            # Parsear hora a formato legible
            hora_parsed = gemini(f"""
El cliente dijo: "{msg}" como horario. Convertí a formato "HH:MM". 
Respondé SOLO el horario en formato HH:MM (ej: 21:00). Nada más.
""").strip()
            datos["hora"] = hora_parsed if ":" in hora_parsed else msg
            datos["paso"] = "completo"
            nro = f"RSV-{str(uuid.uuid4())[:5].upper()}"
            datos["nro_pedido"] = nro
            datos["telefono_cliente"] = tel

            # Parsear personas a número
            try:
                personas_num = int(''.join(c for c in str(datos.get("personas", "1")) if c.isdigit()) or "1")
            except:
                personas_num = 1

            # Guardar reserva en Airtable
            campos_reserva = {
                "Nombre":       datos["nombre_cliente"],
                "telefono":     tel,
                "Fecha":        datos.get("fecha", ""),
                "Hora":         datos["hora"],
                "Personas":     personas_num,
                "Estado":       "pendiente",
                "nro_reserva":  nro,
                "tipo":         datos.get("tipo", "reserva_simple"),
            }
            resultado_at = at_crear_reserva(campos_reserva)
            if not resultado_at.get("ok"):
                print(f"[RESERVA] Fallo al guardar: {resultado_at}")

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
                fecha_display = datos.get("fecha_legible", datos.get("fecha", ""))
                confirmacion = f"✅ *Reserva Confirmada* en {res['nombre']}!\n\n📋 N° *{nro}*\n👤 {datos['nombre_cliente']}\n👥 {datos['personas']} personas\n📅 {fecha_display} a las {datos['hora']}\n\n¡Te esperamos! Si necesitás modificarla, escribinos 😊"
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
