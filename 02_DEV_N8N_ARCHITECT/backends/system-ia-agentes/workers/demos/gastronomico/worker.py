"""
Worker DEMO — Agente Gastronómico Multi-Subniche
================================================
Demo universal para el rubro gastronómico de LATAM.
Soporta sub-nichos configurables por env var:
  cafeteria | pizzeria | rotiseria | hamburgueseria | parrilla

Casos de uso soportados:
  - Encargues (tortas, pizzas, catering)
  - Deliverys con seña del 10%
  - Presupuestos para eventos
  - Reservas de mesa → Cal.com si configurado, Airtable si configurado
  - Consultas de menú del día
  - Comentarios / consultas generales por WhatsApp

Arquitectura:
  - Historial in-memory (no requiere Airtable para demo)
  - Airtable opcional: reservas + pedidos + clientes
  - Cal.com opcional: agendamiento de reservas / reuniones
  - YCloud para enviar mensajes

Variables de entorno (prefijo GASTRO_DEMO_):
  GASTRO_DEMO_SUBNICHE        Sub-nicho del local (def: "cafeteria")
                              Opciones: cafeteria | pizzeria | rotiseria | hamburgueseria | parrilla
  GASTRO_DEMO_NOMBRE          Nombre del local  (def: según subniche)
  GASTRO_DEMO_HORARIO         Horario legible   (def: según subniche)
  GASTRO_DEMO_ALIAS_PAGO      Alias transferencia (def: según subniche)
  GASTRO_DEMO_NUMERO_BOT      Número WhatsApp del bot
  GASTRO_DEMO_NUMERO_DUENO    Número del dueño/a
  GASTRO_DEMO_YCLOUD_KEY      API Key YCloud
  GASTRO_DEMO_AIRTABLE_BASE   Base ID Airtable (opcional)
  GASTRO_DEMO_CAL_API_KEY     API Key Cal.com  (opcional)
  GASTRO_DEMO_CAL_EVENT_ID    Event Type ID Cal.com (opcional)

  GEMINI_API_KEY              Compartida
  AIRTABLE_TOKEN              Compartida
"""

import os
import re
import json
import uuid
from datetime import date, datetime, timedelta

import requests
from google import genai
from fastapi import APIRouter, Request
from pydantic import BaseModel

# ─── SUBNICHE CONFIG ─────────────────────────────────────────────────────────
# Cada sub-niche define defaults para nombre, horario, alias_pago y personalidad.
# Todo puede sobreescribirse con env vars.

_SUBNICHE_DEFAULTS = {
    "cafeteria": {
        "nombre":      "Café del Centro",
        "horario":     "Lunes a Sábado de 7:30 a 21:00 hs",
        "alias_pago":  "cafedelcentro.pagos",
        "emoji":       "☕",
        "menu_label":  "☕ Menú del día",
        "personalidad": "Cordial y acogedora, como una cafetería de barrio. Tono cálido, informal pero respetuoso.",
        "tareas_extra": "También gestionás encargues de tortas y catering para reuniones de empresa.",
    },
    "pizzeria": {
        "nombre":      "Pizzería Demo",
        "horario":     "Martes a Domingo de 19:00 a 00:00 hs (Lunes cerrado)",
        "alias_pago":  "pizzeriademo.pagos",
        "emoji":       "🍕",
        "menu_label":  "🍕 Nuestra carta",
        "personalidad": "Dinámica y directa, como una pizzería familiar. Rápido en respuestas, eficiente.",
        "tareas_extra": "Manejás pedidos de delivery (mínimo 2 pizzas para delivery), takeaway y reservas de salón.",
    },
    "rotiseria": {
        "nombre":      "Rotisería Demo",
        "horario":     "Lunes a Sábado de 9:00 a 20:00 hs",
        "alias_pago":  "rotiseriademo.pagos",
        "emoji":       "🍗",
        "menu_label":  "🍗 Menú del día",
        "personalidad": "Práctica y eficiente. El cliente quiere comer rico y rápido. Mostrá opciones del día con claridad.",
        "tareas_extra": "Gestionás viandas en cantidad para empresas (encargues con 48hs de anticipación).",
    },
    "hamburgueseria": {
        "nombre":      "Burger Demo",
        "horario":     "Todos los días de 11:00 a 23:00 hs",
        "alias_pago":  "burgerdemo.pagos",
        "emoji":       "🍔",
        "menu_label":  "🍔 Nuestra carta",
        "personalidad": "Joven y energética. Podés usar un tono más casual (pero nunca maleducado). Emojis al máximo 2.",
        "tareas_extra": "Deliverys con tiempo estimado, combos personalizables, y eventos de cumpleaños.",
    },
    "parrilla": {
        "nombre":      "La Parrilla Demo",
        "horario":     "Martes a Domingo — Almuerzo 12-16hs, Cena 20-00hs. Lunes cerrado.",
        "alias_pago":  "laparillademo.pagos",
        "emoji":       "🥩",
        "menu_label":  "🥩 Nuestra carta",
        "personalidad": "Clásica y cálida, estilo parrilla argentina tradicional. Tono formal pero cercano.",
        "tareas_extra": "Reservas son el foco principal. También manejás encargues de asados para eventos.",
    },
}

# ─── CONFIG ──────────────────────────────────────────────────────────────────
SUBNICHE = os.environ.get("GASTRO_DEMO_SUBNICHE", "cafeteria").lower()
if SUBNICHE not in _SUBNICHE_DEFAULTS:
    SUBNICHE = "cafeteria"

_defaults = _SUBNICHE_DEFAULTS[SUBNICHE]

GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
AIRTABLE_TOKEN  = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
YCLOUD_API_KEY  = os.environ.get("GASTRO_DEMO_YCLOUD_KEY", "") or os.environ.get("YCLOUD_API_KEY", "")

NOMBRE_LOCAL    = os.environ.get("GASTRO_DEMO_NOMBRE",   _defaults["nombre"])
HORARIO         = os.environ.get("GASTRO_DEMO_HORARIO",  _defaults["horario"])
ALIAS_PAGO      = os.environ.get("GASTRO_DEMO_ALIAS_PAGO", _defaults["alias_pago"])
NUMERO_BOT      = os.environ.get("GASTRO_DEMO_NUMERO_BOT",  "")
NUMERO_DUENO    = os.environ.get("GASTRO_DEMO_NUMERO_DUENO","")

AIRTABLE_BASE_ID        = os.environ.get("GASTRO_DEMO_AIRTABLE_BASE", "") or os.environ.get("AIRTABLE_BASE_ID", "appdA5rJOmtVvpDrx")
CAL_API_KEY             = os.environ.get("GASTRO_DEMO_CAL_API_KEY",   "")
CAL_EVENT_ID            = os.environ.get("GASTRO_DEMO_CAL_EVENT_ID",  "")

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# ─── SESIONES IN-MEMORY ───────────────────────────────────────────────────────
# { telefono: [ {"role": "user"|"model", "parts": [{"text": "..."}]}, ... ] }
SESIONES: dict[str, list] = {}
# Subniche elegido por sesión (se asigna en el selector inicial)
# { telefono: "cafeteria"|"pizzeria"|... }
SESION_SUBNICHE: dict[str, str] = {}

_SELECTOR_SUBNICHOS = (
    "¡Hola! 👋 Soy el asistente virtual de *System IA Demo*.\n\n"
    "¿Con qué tipo de negocio podemos ayudarte hoy?\n\n"
    "1️⃣ ☕ Cafetería\n"
    "2️⃣ 🍕 Pizzería\n"
    "3️⃣ 🍗 Rotisería\n"
    "4️⃣ 🍔 Hamburguesería\n"
    "5️⃣ 🥩 Parrilla"
)
_SELECTOR_MAP = {
    "1": "cafeteria", "cafeteria": "cafeteria", "cafe": "cafeteria", "cafetería": "cafeteria",
    "2": "pizzeria",  "pizzeria":  "pizzeria",  "pizza": "pizzeria", "pizzería": "pizzeria",
    "3": "rotiseria", "rotiseria": "rotiseria", "rotis": "rotiseria", "rotisería": "rotiseria",
    "4": "hamburgueseria", "hamburgueseria": "hamburgueseria", "burger": "hamburgueseria",
          "hamburguesa": "hamburgueseria", "hamburguesería": "hamburgueseria",
    "5": "parrilla",  "parrilla": "parrilla", "asado": "parrilla",
}

# ─── MENÚ FALLBACK por sub-niche ─────────────────────────────────────────────
_MENUS_FALLBACK: dict[str, dict] = {
    "cafeteria": {
        "☕ Cafetería": [
            ("Café espresso", 800),
            ("Cortado + medialunas x2", 1_200),
            ("Submarino", 1_100),
            ("Menú desayuno completo", 2_800),
        ],
        "🥩 Salados": [
            ("Milanesa a la napolitana + guarnición", 4_500),
            ("Tallarines caseros con tuco", 3_800),
            ("Sándwich de miga x4", 2_600),
            ("Tarta del día (porción)", 1_800),
        ],
        "🍰 Dulces / Repostería": [
            ("Torta del día (porción)", 1_500),
            ("Medialunas de manteca x4", 1_200),
            ("Facturas surtidas x6", 2_000),
        ],
        "🍷 Bebidas": [
            ("Jugo natural exprimido", 1_100),
            ("Agua mineral 500ml", 500),
            ("Limonada con menta", 1_200),
        ],
    },
    "pizzeria": {
        "🍕 Pizzas (por metro)": [
            ("Mozzarella", 5_500),
            ("Napolitana", 6_000),
            ("Especial del día", 6_500),
            ("Fugazzeta rellena", 7_000),
        ],
        "🥗 Empanadas / Entradas": [
            ("Empanadas al horno x6", 3_200),
            ("Garlic bread (4 porciones)", 2_400),
            ("Tabla antipasto", 4_800),
        ],
        "🍰 Postres": [
            ("Tiramisú", 2_200),
            ("Panacotta", 2_000),
        ],
        "🍷 Bebidas": [
            ("Coca-Cola 1.5L", 1_200),
            ("Cerveza artesanal (pint)", 2_000),
            ("Vino tinto (copa)", 2_500),
        ],
    },
    "rotiseria": {
        "🍗 Platos del día": [
            ("Pollo asado entero", 6_500),
            ("Milanesa de ternera + guarnición", 4_800),
            ("Cazuela de lentejas (porción)", 3_200),
            ("Pastel de papa individual", 3_500),
        ],
        "🥗 Ensaladas / Guarniciones": [
            ("Ensalada rusa (200gr)", 1_800),
            ("Puré de papa (250gr)", 1_600),
            ("Ensalada mixta", 1_500),
        ],
        "📦 Viandas (pedido mínimo x5)": [
            ("Vianda ejecutiva (plato + postre)", 4_200),
            ("Vianda dietética", 4_000),
        ],
        "🍰 Postres": [
            ("Flan con crema", 1_400),
            ("Fruta del tiempo", 1_200),
        ],
    },
    "hamburgueseria": {
        "🍔 Hamburguesas": [
            ("Classic Burger 180gr", 4_500),
            ("Doble Cheese Bacon 200gr", 6_200),
            ("Veggie Burger", 5_000),
            ("BBQ Crispy 200gr", 6_500),
        ],
        "🍟 Acompañamientos": [
            ("Papas fritas (porción)", 1_800),
            ("Papas cheddar + bacon", 2_500),
            ("Aros de cebolla", 2_000),
        ],
        "🌮 Wraps / Extras": [
            ("Wrap de pollo grillado", 4_200),
            ("Hot Dog clásico", 3_500),
        ],
        "🥤 Bebidas": [
            ("Gaseosa 500ml", 900),
            ("Milkshake (vainilla/chocolate/frutilla)", 2_800),
            ("Agua mineral 500ml", 500),
        ],
    },
    "parrilla": {
        "🥩 Platos Principales": [
            ("Asado de Tira 400gr + papas", 6_800),
            ("Bife de Chorizo 300gr + ensalada", 7_500),
            ("Bondiola Braseada + puré de calabaza", 5_900),
            ("Vacío a la parrilla 350gr", 7_000),
        ],
        "🥗 Entradas": [
            ("Provoleta fundida", 2_500),
            ("Empanadas Tucumanas x3", 2_700),
            ("Tabla de Fiambres", 4_500),
        ],
        "🍰 Postres": [
            ("Flan Casero + dulce de leche", 1_500),
            ("Mousse de Chocolate", 1_600),
            ("Panqueques + dulce de leche", 1_800),
        ],
        "🍷 Bebidas": [
            ("Vino Malbec (copa)", 2_200),
            ("Cerveza Artesanal (pint)", 1_800),
            ("Limonada con menta", 1_200),
        ],
    },
}

MENU_FALLBACK = _MENUS_FALLBACK.get(SUBNICHE, _MENUS_FALLBACK["cafeteria"])


def _menu_texto(menu: dict | None = None) -> str:
    if not menu:
        menu = MENU_FALLBACK
    lineas = []
    for categoria, items in menu.items():
        lineas.append(f"\n*{categoria}*")
        for nombre, precio in items:
            lineas.append(f"  • {nombre} — ${precio:,.0f} ARS".replace(",", "."))
    return "\n".join(lineas)


HOY = date.today().strftime("%A %d de %B de %Y")
_EMOJI_LOCAL   = _defaults["emoji"]
_PERSONALIDAD  = _defaults["personalidad"]
_TAREAS_EXTRA  = _defaults["tareas_extra"]
_MENU_LABEL    = _defaults["menu_label"]

SYSTEM_PROMPT = f"""════════════════════════════════════════════════════════
ROL
════════════════════════════════════════════════════════
Sos la asistente virtual de *{NOMBRE_LOCAL}* ({SUBNICHE}).
Tu trabajo es atender clientes por WhatsApp:
encargues, deliverys, presupuestos, reservas de mesa, difusión del menú del día y gestión de comentarios/reseñas.
{_TAREAS_EXTRA}

PERSONALIDAD:
- {_PERSONALIDAD}
- Español neutro: NUNCA usés "vos", "che", "dale", "genial", "bárbaro", "re", "copado", "pibe"
- Tratá al cliente de "usted" o "tú" (nunca "vos")
- Emojis con moderación: máximo 1-2 por mensaje
- Respuestas cortas y directas — máximo 6 líneas salvo que el menú lo requiera

════════════════════════════════════════════════════════
DATOS DEL LOCAL
════════════════════════════════════════════════════════
- Nombre: {NOMBRE_LOCAL}
- Horario: {HORARIO}
- Fecha de hoy: {HOY}
- Todos los precios incluyen IVA.

════════════════════════════════════════════════════════
MENÚ PRINCIPAL (punto de entrada)
════════════════════════════════════════════════════════
CUÁNDO mostrarlo: cuando el cliente ya eligió su tipo de negocio, ante cualquier saludo, o cuando escriba "0" o "menu".

TEXTO EXACTO:
*¡Bienvenido a {NOMBRE_LOCAL}!* {_EMOJI_LOCAL}
¿En qué puedo ayudarte?

1️⃣ {_MENU_LABEL} 🍽️
2️⃣ Hacer un pedido / delivery 🛵
3️⃣ Encargue especial (tortas, catering, salados) 📦
4️⃣ Reservar una mesa 📅
5️⃣ Pedir presupuesto para evento 💬
6️⃣ Cancelar o modificar una reserva ✏️
7️⃣ Dejar un comentario ⭐

REGLA: Esperá que el cliente elija. No agregues texto extra.

════════════════════════════════════════════════════════
TAREA 1 — MENÚ DEL DÍA (opción 1)
════════════════════════════════════════════════════════
Mostrá DIRECTAMENTE el menú agrupado por categoría usando la sección MENÚ al final de este prompt.

Formato:
🍽️ *Menú de hoy — {HOY}*
[categorías y platos con precios]
0️⃣ Volver al menú principal

════════════════════════════════════════════════════════
TAREA 2 — PEDIDO DELIVERY (opción 2)
════════════════════════════════════════════════════════
─── TURNO 1 ───
Pedí solo el nombre: "¡Con gusto! ¿Podría indicarme su nombre?"

─── TURNO 2 ───
Con el nombre: mostrá las categorías del menú numeradas.

─── TURNOS SIGUIENTES ───
Cuando elige categoría → mostrá ítems con precio.
Cuando elige ítem → confirmalo y preguntá "¿Desea agregar algo más?"
⛔ NO calcules total hasta que diga que terminó.

─── TURNO FINAL (cliente dice "listo", "nada más", "eso es todo") ───
Mostrá el resumen del pedido con total y ejecutá:
ACCION: {{"tipo": "derivar_asesor", "motivo": "delivery", "nombre": "[nombre]", "detalle": "[resumen del pedido]", "total": [número]}}

════════════════════════════════════════════════════════
TAREA 3 — ENCARGUE ESPECIAL (opción 3)
════════════════════════════════════════════════════════
Casos: tortas, catering, comidas saladas en cantidad, sándwiches para eventos, tapas para reuniones.
Recopilar en orden:
1. Nombre del cliente
2. Qué desea encargar
3. Para cuántas personas / especificaciones
4. Fecha y horario en que lo necesita

Cuando tenés los 4 datos → confirmá y ejecutá:
ACCION: {{"tipo": "derivar_asesor", "motivo": "encargue", "nombre": "...", "detalle": "[descripción completa incluyendo fecha]", "total": 0}}

════════════════════════════════════════════════════════
TAREA 4 — RESERVA DE MESA (opción 4)
════════════════════════════════════════════════════════
Datos a recopilar en orden:
1. Nombre completo
2. Cantidad de personas
3. Fecha
4. Horario

Cuando tenés los 4 → confirmá: "¿Confirma: reserva para [nombre], [N] personas, [fecha] a las [hora]?"
Cuando confirme → ejecutá:
ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "HH:MM", "nota": "..."}}

⚠️ NUNCA digas "reserva confirmada" vos mismo — el sistema lo confirma automáticamente.

════════════════════════════════════════════════════════
TAREA 5 — PRESUPUESTO PARA EVENTO (opción 5)
════════════════════════════════════════════════════════
Recopilar:
1. Nombre / empresa
2. Tipo de evento (cumpleaños, reunión, catering, brunch)
3. Cantidad de personas
4. Fecha y horario tentativo
5. Preferencias (salado, dulce, bebidas)

Con todos los datos → generá una cotización estimada usando el menú y ejecutá:
ACCION: {{"tipo": "derivar_asesor", "motivo": "presupuesto_evento", "nombre": "...", "detalle": "[tipo evento] — [N] personas — [fecha] — [preferencias]", "total": 0}}

════════════════════════════════════════════════════════
TAREA 6 — CANCELAR O MODIFICAR RESERVA (opción 6)
════════════════════════════════════════════════════════
Preguntá: "¿Desea *cancelar* o *modificar* su reserva?"

CANCELAR → recopilá nombre y ejecutá:
ACCION: {{"tipo": "cancelar_reserva", "nombre": "...", "fecha_legible": "...", "hora": "..."}}

MODIFICAR → recopilá qué cambia y ejecutá:
ACCION: {{"tipo": "modificar_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "HH:MM", "nota": "Modificación solicitada"}}

════════════════════════════════════════════════════════
TAREA 7 — COMENTARIOS / RESEÑAS (opción 7)
════════════════════════════════════════════════════════
Decí: "¡Nos alegra que nos contactes! ¿Nos dejás tu comentario?"
Cuando el cliente envíe el comentario → agradecé y ejecutá:
ACCION: {{"tipo": "registrar_resena", "nombre": "[nombre si lo conocés]", "comentario": "[texto]", "valoracion": "positiva|negativa|neutra"}}

════════════════════════════════════════════════════════
REGLA DE CONTEXTO
════════════════════════════════════════════════════════
SIEMPRE analizá el historial para saber en qué flujo estás.
ÚNICA forma de salir: cliente escribe "0" (menú principal) o "00" (reiniciar conversación).
⛔ NUNCA interpretes un número como opción del menú principal si estás dentro de un flujo activo.

════════════════════════════════════════════════════════
ACCIONES DISPONIBLES
════════════════════════════════════════════════════════
ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "HH:MM", "nota": "..."}}
ACCION: {{"tipo": "cancelar_reserva", "nombre": "...", "fecha_legible": "...", "hora": "..."}}
ACCION: {{"tipo": "modificar_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "HH:MM", "nota": "..."}}
ACCION: {{"tipo": "derivar_asesor", "motivo": "delivery|encargue|presupuesto_evento", "nombre": "...", "detalle": "...", "total": N}}
ACCION: {{"tipo": "notificar_dueno", "mensaje": "..."}}
ACCION: {{"tipo": "registrar_resena", "nombre": "...", "comentario": "...", "valoracion": "positiva|negativa|neutra"}}

⛔ CRÍTICO: Con ACCION crear_reserva tu mensaje visible dice SOLO "Procesando...".
"""

# ─── AIRTABLE HELPERS ─────────────────────────────────────────────────────────
def _at_headers() -> dict:
    return {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}


def _at_disponible() -> bool:
    return bool(AIRTABLE_BASE_ID and AIRTABLE_TOKEN)


def _at_get_or_create_cliente(telefono: str, nombre: str = "") -> str:
    """Busca cliente por Telefono o lo crea. Devuelve record ID."""
    if not _at_disponible():
        return ""
    try:
        tel_limpio = re.sub(r"\D", "", telefono)
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Clientes"
        # Airtable phoneNumber guarda sin formato — buscar por contains
        r = requests.get(url, headers=_at_headers(),
                         params={"filterByFormula": f"FIND('{tel_limpio}', SUBSTITUTE({{Telefono}},'+',''))",
                                 "maxRecords": 1}, timeout=8)
        records = r.json().get("records", [])
        if records:
            return records[0]["id"]
        payload = {"records": [{"fields": {"Telefono": telefono, "Nombre": nombre}}]}
        r2 = requests.post(url, headers=_at_headers(), json=payload, timeout=8)
        resp = r2.json()
        if "records" in resp and resp["records"]:
            return resp["records"][0]["id"]
    except Exception as e:
        print(f"[GASTRO-AT] get_or_create_cliente: {e}")
    return ""


def _at_crear_reserva(datos: dict) -> dict:
    if not _at_disponible():
        return {"ok": True, "simulated": True}
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        try:
            personas = int(str(datos.get("personas", 1)).strip())
        except Exception:
            personas = 1
        cliente_id = _at_get_or_create_cliente(datos.get("telefono", ""), datos.get("nombre", ""))
        fecha_str = str(datos.get("fecha_iso", ""))[:10]
        hora_str  = str(datos.get("hora", ""))
        campos = {
            "Cantidad de Personas": personas,
            "Estado":               "pendiente",
            "Especificaciones":     str(datos.get("nota", "")),
        }
        # Telefono es link a Clientes
        if cliente_id:
            campos["Telefono"] = [cliente_id]
        if fecha_str and hora_str:
            campos["Fecha y Hora"] = f"{fecha_str}T{hora_str}:00.000Z"
        r = requests.post(url, headers=_at_headers(), json={"records": [{"fields": campos}]}, timeout=8)
        return {"ok": r.status_code in (200, 201), "resp": r.json()}
    except Exception as e:
        print(f"[GASTRO-AT] crear_reserva: {e}")
        return {"ok": False, "error": str(e)}


def _at_crear_pedido(datos: dict) -> dict:
    if not _at_disponible():
        return {"ok": True, "simulated": True}
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        total = float(datos.get("total", 0))
        sena  = round(total * 0.10, 2)
        cliente_id = _at_get_or_create_cliente(datos.get("telefono", ""), datos.get("nombre", ""))
        # tipo: opciones reales en Airtable = "delivey" (typo), "reserva", "seña"
        tipo_raw = datos.get("tipo_pedido", "delivery")
        tipo_at  = "delivey" if "deliver" in tipo_raw.lower() else tipo_raw
        campos = {
            "detalle":        datos.get("detalle", ""),
            "total_ars":      total,
            "sena_ars":       sena,
            "estado_pago":    datos.get("estado_pago", "pendiente"),
            "estado_entrega": "pendiente",
            "tipo":           tipo_at,
            "Fecha":          date.today().isoformat(),
        }
        if cliente_id:
            campos["Clientes"] = [cliente_id]
        r = requests.post(url, headers=_at_headers(), json={"records": [{"fields": campos}]}, timeout=8)
        return {"ok": r.status_code in (200, 201), "resp": r.json()}
    except Exception as e:
        print(f"[GASTRO-AT] crear_pedido: {e}")
        return {"ok": False, "error": str(e)}


def _at_buscar_reserva_por_tel(telefono: str) -> dict | None:
    """Devuelve la reserva más reciente del cliente (no cancelada)."""
    if not _at_disponible():
        return None
    try:
        tel_limpio = re.sub(r"\D", "", telefono)
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        r = requests.get(url, headers=_at_headers(), params={
            "filterByFormula": f"AND(FIND('{tel_limpio}', SUBSTITUTE({{Telefono}}&'','+','')), {{Estado}}!='cancelada')",
            "sort[0][field]": "Fecha y Hora",
            "sort[0][direction]": "desc",
            "maxRecords": 1,
        }, timeout=8)
        records = r.json().get("records", [])
        return records[0] if records else None
    except Exception as e:
        print(f"[GASTRO-AT] buscar_reserva_por_tel: {e}")
        return None


def _at_actualizar_reserva(record_id: str, campos: dict) -> dict:
    """PATCH una reserva existente en Airtable."""
    if not _at_disponible():
        return {"ok": True, "simulated": True}
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas/{record_id}"
        r = requests.patch(url, headers=_at_headers(), json={"fields": campos}, timeout=8)
        return {"ok": r.status_code in (200, 201), "resp": r.json()}
    except Exception as e:
        print(f"[GASTRO-AT] actualizar_reserva: {e}")
        return {"ok": False, "error": str(e)}


def _at_registrar_resena(nombre: str, comentario: str, valoracion: str, telefono: str) -> dict:
    """Guarda la reseña en la tabla Clientes (campo Comentarios) y crea registro si no existe."""
    if not _at_disponible():
        return {"ok": True, "simulated": True}
    try:
        cliente_id = _at_get_or_create_cliente(telefono, nombre)
        if not cliente_id:
            return {"ok": False, "error": "No se pudo encontrar/crear cliente"}
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Clientes/{cliente_id}"
        r = requests.patch(url, headers=_at_headers(), json={"fields": {
            "Comentarios": f"[{valoracion.upper()}] {comentario}",
        }}, timeout=8)
        return {"ok": r.status_code in (200, 201)}
    except Exception as e:
        print(f"[GASTRO-AT] registrar_resena: {e}")
        return {"ok": False, "error": str(e)}


def _at_leer_menu_subniche(sn: str) -> dict | None:
    """Lee platos filtrados por subniche desde Airtable. Devuelve dict {categoria: [(nombre,precio)]} o None."""
    if not _at_disponible():
        return None
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Platos"
        r = requests.get(url, headers=_at_headers(), params={
            "filterByFormula": f"{{subniche}}='{sn}'",
            "maxRecords": 30,
        }, timeout=8)
        records = r.json().get("records", [])
        if not records:
            return None
        menu: dict = {}
        for rec in records:
            f = rec["fields"]
            nombre = f.get("Nombre", "")
            precio = float(f.get("Precio", 0))
            cats = f.get("Menús (from Categoría)", [f"🍽️ {sn.title()}"])
            cat = cats[0] if cats else f"🍽️ {sn.title()}"
            if cat not in menu:
                menu[cat] = []
            menu[cat].append((nombre, precio))
        return menu if menu else None
    except Exception as e:
        print(f"[GASTRO-AT] leer_menu_subniche({sn}): {e}")
        return None


def _at_leer_menu_dia() -> dict | None:
    """Lee platos con Menú del Dia=true desde Airtable. Devuelve dict por categoría o None."""
    if not _at_disponible():
        return None
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Platos"
        r = requests.get(url, headers=_at_headers(), params={
            "filterByFormula": "{Menú del Dia}=1",
            "maxRecords": 50,
        }, timeout=8)
        records = r.json().get("records", [])
        if not records:
            return None
        menu: dict = {}
        for rec in records:
            f = rec["fields"]
            nombre = f.get("Nombre", "")
            precio = float(f.get("Precio", 0))
            cats = f.get("Menús (from Categoría)", ["🍽️ Menú del día"])
            cat = cats[0] if cats else "🍽️ Menú del día"
            if cat not in menu:
                menu[cat] = []
            menu[cat].append((nombre, precio))
        return menu if menu else None
    except Exception as e:
        print(f"[GASTRO-AT] leer_menu_dia: {e}")
        return None


def _at_listar_reservas(limite: int = 30) -> list[dict]:
    if not _at_disponible():
        return _mock_reservas()
    try:
        hoy = date.today().isoformat()
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        r = requests.get(url, headers=_at_headers(), params={
            "filterByFormula": f"IS_AFTER({{Fecha y Hora}}, '{hoy}')",
            "sort[0][field]":      "Fecha y Hora",
            "sort[0][direction]":  "asc",
            "maxRecords":          limite,
        }, timeout=8)
        return [rec["fields"] | {"_id": rec["id"]} for rec in r.json().get("records", [])]
    except Exception as e:
        print(f"[GASTRO-AT] listar_reservas: {e}")
        return _mock_reservas()


def _at_listar_pedidos(limite: int = 50) -> list[dict]:
    if not _at_disponible():
        return _mock_pedidos()
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        r = requests.get(url, headers=_at_headers(), params={
            "sort[0][field]":     "ID Pedido",
            "sort[0][direction]": "desc",
            "maxRecords":         limite,
        }, timeout=8)
        return [rec["fields"] | {"_id": rec["id"]} for rec in r.json().get("records", [])]
    except Exception as e:
        print(f"[GASTRO-AT] listar_pedidos: {e}")
        return _mock_pedidos()


def _at_listar_clientes(limite: int = 50) -> list[dict]:
    if not _at_disponible():
        return _mock_clientes()
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Clientes"
        r = requests.get(url, headers=_at_headers(), params={
            "sort[0][field]":     "Fecha de ultima interaccion",
            "sort[0][direction]": "desc",
            "maxRecords":         limite,
        }, timeout=8)
        return [rec["fields"] | {"_id": rec["id"]} for rec in r.json().get("records", [])]
    except Exception as e:
        print(f"[GASTRO-AT] listar_clientes: {e}")
        return _mock_clientes()


# ─── MOCKS (sin Airtable) ─────────────────────────────────────────────────────
def _mock_reservas() -> list[dict]:
    hoy = date.today().isoformat()
    return [
        {"Nombre del Cliente": "Familia Martínez", "Fecha y Hora": f"{hoy}T12:00:00.000Z", "Cantidad de Personas": 4, "Estado": "confirmada"},
        {"Nombre del Cliente": "Pedro Sosa",        "Fecha y Hora": f"{hoy}T13:00:00.000Z", "Cantidad de Personas": 2, "Estado": "confirmada"},
        {"Nombre del Cliente": "Familia Ramírez",   "Fecha y Hora": f"{hoy}T19:00:00.000Z", "Cantidad de Personas": 4, "Estado": "pendiente"},
        {"Nombre del Cliente": "Laura Quintero",    "Fecha y Hora": f"{hoy}T20:30:00.000Z", "Cantidad de Personas": 6, "Estado": "pendiente"},
    ]


def _mock_pedidos() -> list[dict]:
    return [
        {"Detalle": "2 medialunas + café con leche", "Total ARS": 2400, "Estado Pago": "pendiente",  "Estado Entrega": "nuevo",          "Tipo": "delivery"},
        {"Detalle": "Torta cumpleaños 4 pers.",       "Total ARS": 8500, "Estado Pago": "pendiente",  "Estado Entrega": "pendiente",       "Tipo": "encargue"},
        {"Detalle": "Menú almuerzo completo + jugo",  "Total ARS": 4200, "Estado Pago": "confirmado", "Estado Entrega": "en preparación",  "Tipo": "delivery"},
        {"Detalle": "Sándwiches x3 + agua",           "Total ARS": 3200, "Estado Pago": "confirmado", "Estado Entrega": "en camino",       "Tipo": "delivery"},
        {"Detalle": "Catering reunión 20 pers.",      "Total ARS": 68000,"Estado Pago": "pendiente",  "Estado Entrega": "presupuesto",     "Tipo": "encargue"},
    ]


def _mock_clientes() -> list[dict]:
    return [
        {"Nombre": "María González",  "Teléfono": "+5493764001234", "Email": "", "Pedidos": 3,  "Origen": "WhatsApp IA"},
        {"Nombre": "Lucas Pérez",     "Teléfono": "+5493764005678", "Email": "", "Pedidos": 1,  "Origen": "WhatsApp IA"},
        {"Nombre": "Ana López",       "Teléfono": "+5493764009876", "Email": "", "Pedidos": 5,  "Origen": "WhatsApp IA"},
        {"Nombre": "Familia Ramírez", "Teléfono": "+5493764005555", "Email": "", "Pedidos": 2,  "Origen": "WhatsApp IA"},
        {"Nombre": "Empresa ABC",     "Teléfono": "+5493764001111", "Email": "", "Pedidos": 1,  "Origen": "WhatsApp IA"},
        {"Nombre": "Club Social",     "Teléfono": "+5493764002222", "Email": "", "Pedidos": 2,  "Origen": "WhatsApp IA"},
    ]


# ─── YCLOUD ───────────────────────────────────────────────────────────────────
def _norm_tel(tel: str) -> str:
    return "+" + re.sub(r"\D", "", tel)


def _enviar_texto(telefono: str, mensaje: str) -> bool:
    if not YCLOUD_API_KEY or not NUMERO_BOT:
        print(f"[GASTRO-DEMO] Sin key/número. Msg:\n{mensaje}")
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
        print(f"[GASTRO-YCLOUD] Error: {e}")
        return False


def _notificar_dueno(mensaje: str) -> None:
    if NUMERO_DUENO:
        _enviar_texto(NUMERO_DUENO, mensaje)


# ─── CAL.COM ──────────────────────────────────────────────────────────────────
def _cal_disponible() -> bool:
    return bool(CAL_API_KEY and CAL_EVENT_ID)


def _cal_slots(dias: int = 7) -> list[dict]:
    if not _cal_disponible():
        return []
    start = datetime.utcnow().strftime("%Y-%m-%d")
    end   = (datetime.utcnow() + timedelta(days=dias)).strftime("%Y-%m-%d")
    try:
        r = requests.get("https://api.cal.com/v1/slots",
                         params={"apiKey": CAL_API_KEY, "eventTypeId": CAL_EVENT_ID,
                                 "startTime": start, "endTime": end}, timeout=10)
        if r.status_code == 200:
            slots_raw = r.json().get("slots", {})
            slots = []
            for fecha, lista in slots_raw.items():
                for slot in lista[:2]:
                    dt = slot.get("time", "")
                    if dt:
                        slots.append({"fecha": fecha, "time": dt})
            return slots[:6]
    except Exception as e:
        print(f"[GASTRO-CAL] Error: {e}")
    return []


def _cal_crear_reserva(nombre: str, email: str, fecha_iso: str, hora: str) -> dict:
    if not _cal_disponible():
        return {"ok": False, "reason": "Cal.com no configurado"}
    try:
        dt_str = f"{fecha_iso}T{hora}:00.000Z"
        r = requests.post("https://api.cal.com/v1/bookings",
                          params={"apiKey": CAL_API_KEY},
                          json={"eventTypeId": int(CAL_EVENT_ID), "start": dt_str,
                                "responses": {"name": nombre, "email": email or "demo@systemai.ar",
                                              "location": {"value": "inPerson", "optionValue": ""}}},
                          timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            return {"ok": True, "uid": data.get("uid", ""), "data": data}
        return {"ok": False, "status": r.status_code, "resp": r.text[:200]}
    except Exception as e:
        print(f"[GASTRO-CAL] crear_reserva: {e}")
        return {"ok": False, "error": str(e)}


# ─── EJECUTAR ACCIONES DEL AGENTE ─────────────────────────────────────────────
def _ejecutar_accion(accion: dict, tel: str) -> dict:
    tipo = accion.get("tipo")

    if tipo == "crear_reserva":
        nombre = accion.get("nombre", "")
        # 1. Airtable (CRM en tiempo real)
        resultado_at = _at_crear_reserva({**accion, "telefono": tel})
        # 2. Cal.com (agenda en tiempo real)
        resultado_cal = _cal_crear_reserva(
            nombre=nombre,
            email="",
            fecha_iso=accion.get("fecha_iso", ""),
            hora=accion.get("hora", ""),
        )
        cal_ok = resultado_cal.get("ok", False)
        nro = "RSV-" + str(uuid.uuid4())[:5].upper()
        if resultado_at.get("ok"):
            _notificar_dueno(
                f"🆕 *Nueva Reserva* #{nro}\n"
                f"👤 {nombre}\n"
                f"👥 {accion.get('personas')} personas\n"
                f"📅 {accion.get('fecha_legible', accion.get('fecha_iso'))} a las {accion.get('hora')}\n"
                f"📞 {tel}\n"
                + (f"📆 Cal.com: ✅ agendado" if cal_ok else "📆 Cal.com: registrado en CRM")
            )
            return {
                "ok": True,
                "mensaje_confirmacion": (
                    f"✅ *Reserva confirmada*\n\n"
                    f"📋 N° *{nro}*\n"
                    f"👤 {nombre}\n"
                    f"👥 {accion.get('personas')} personas\n"
                    f"📅 {accion.get('fecha_legible', accion.get('fecha_iso'))} a las {accion.get('hora')} hs\n\n"
                    f"¡Los esperamos! {_EMOJI_LOCAL} Un asesor le confirmará los detalles."
                ),
            }
        return {
            "ok": False,
            "mensaje_error": (
                "⚠️ Ocurrió un inconveniente al registrar la reserva.\n"
                "Por favor contáctenos directamente para confirmar su lugar."
            ),
        }

    elif tipo == "crear_pedido":
        resultado = _at_crear_pedido({**accion, "telefono": tel})
        nro = "PED-" + str(uuid.uuid4())[:5].upper()
        tipo_pedido = accion.get("tipo_pedido", "delivery")
        if resultado.get("ok"):
            _notificar_dueno(
                f"📦 *Nuevo {tipo_pedido.title()}* #{nro}\n"
                f"👤 {accion.get('nombre', tel)}\n"
                f"📋 {accion.get('detalle', '')}\n"
                f"📞 {tel}"
            )
            return {
                "ok": True,
                "mensaje_confirmacion": (
                    f"✅ *{tipo_pedido.title()} registrado* N° *{nro}*\n\n"
                    "Nos comunicaremos para confirmar los detalles. ¡Gracias! 🙌"
                ),
            }
        return {"ok": False, "mensaje_error": "⚠️ No se pudo registrar el pedido. Contáctenos directamente."}

    elif tipo == "derivar_asesor":
        nombre  = accion.get("nombre", "")
        detalle = accion.get("detalle", "")
        total   = float(accion.get("total", 0))
        motivo  = accion.get("motivo", "pedido")
        nro     = "PED-" + str(uuid.uuid4())[:5].upper()
        # Guardar en Airtable
        _at_crear_pedido({**accion, "telefono": tel, "estado_pago": "pendiente",
                          "tipo_pedido": motivo})
        # Etiqueta legible según motivo
        etiquetas = {
            "delivery":          "🛵 Pedido Delivery",
            "encargue":          "📦 Encargue Especial",
            "presupuesto_evento": "💬 Presupuesto Evento",
        }
        etiqueta = etiquetas.get(motivo, "📋 Pedido")
        _notificar_dueno(
            f"🔔 *{etiqueta}* #{nro}\n"
            f"👤 {nombre or tel}\n"
            f"📋 {detalle}\n"
            + (f"💰 Total est.: ${total:,.0f} ARS\n" if total else "")
            + f"📞 {tel}\n\n"
            f"⚡ El cliente espera que lo contactes para coordinar."
        )
        mensajes = {
            "delivery":          f"¡Perfecto! Su pedido fue registrado. 🛵\nUn asesor se comunicará con usted a la brevedad para coordinar la entrega y el pago.",
            "encargue":          f"¡Encargue registrado! 📦\nUn asesor se comunicará con usted para confirmar los detalles y el precio final.",
            "presupuesto_evento": f"¡Consulta recibida! 💬\nUn asesor le enviará el presupuesto detallado a la brevedad. ¡Gracias por elegirnos!",
        }
        return {
            "ok": True,
            "mensaje_confirmacion": mensajes.get(motivo, "Un asesor se comunicará con usted en breve. ¡Gracias! 🙌"),
        }

    elif tipo == "cancelar_reserva":
        nombre = accion.get("nombre", "")
        fecha  = accion.get("fecha_legible", "")
        hora   = accion.get("hora", "")
        # Intentar cancelar en Airtable
        reserva = _at_buscar_reserva_por_tel(tel)
        if reserva:
            _at_actualizar_reserva(reserva["id"], {
                "Estado": "cancelada",
                "Especificaciones": f"CANCELADA el {date.today().strftime('%d/%m/%Y')} — {fecha} {hora}",
            })
        _notificar_dueno(
            f"❌ *Cancelación de Reserva*\n"
            f"👤 {nombre}\n"
            f"📅 {fecha} a las {hora}\n"
            f"📞 {tel}"
        )
        return {
            "ok": True,
            "mensaje_confirmacion": (
                f"✅ *Reserva cancelada*\n\n"
                f"La reserva de *{nombre}* para el *{fecha}* a las *{hora} hs* fue cancelada.\n\n"
                f"Si desea hacer una nueva reserva, con gusto lo atendemos. {_EMOJI_LOCAL}"
            ),
        }

    elif tipo == "modificar_reserva":
        nombre = accion.get("nombre", "")
        fecha  = accion.get("fecha_legible", accion.get("fecha_iso", ""))
        hora   = accion.get("hora", "")
        try:
            personas = int(str(accion.get("personas", 1)).strip())
        except Exception:
            personas = 1
        # Buscar y actualizar en Airtable
        reserva = _at_buscar_reserva_por_tel(tel)
        campos_nuevos: dict = {
            "Cantidad de Personas": personas,
            "Estado": "pendiente",
            "Especificaciones": accion.get("nota", "Modificación solicitada por el cliente"),
        }
        fecha_str = str(accion.get("fecha_iso", ""))[:10]
        if fecha_str and hora:
            campos_nuevos["Fecha y Hora"] = f"{fecha_str}T{hora}:00.000Z"
        if reserva:
            resultado = _at_actualizar_reserva(reserva["id"], campos_nuevos)
        else:
            resultado = {"ok": True, "simulated": True}
        _notificar_dueno(
            f"✏️ *Reserva MODIFICADA*\n"
            f"👤 {nombre}\n"
            f"👥 {personas} personas\n"
            f"📅 {fecha} a las {hora}\n"
            f"📞 {tel}"
        )
        return {
            "ok": True,
            "mensaje_confirmacion": (
                f"✅ *Reserva actualizada correctamente*\n\n"
                f"👤 {nombre}\n"
                f"👥 {personas} personas\n"
                f"📅 {fecha} a las {hora} hs\n\n"
                f"¡Lo esperamos en {NOMBRE_LOCAL}! {_EMOJI_LOCAL}"
            ),
        }

    elif tipo == "registrar_resena":
        nombre     = accion.get("nombre", "cliente")
        comentario = accion.get("comentario", "")
        valoracion = accion.get("valoracion", "neutra")
        _at_registrar_resena(nombre, comentario, valoracion, tel)
        # Notificar al dueño solo si es negativa
        if valoracion == "negativa":
            _notificar_dueno(
                f"⚠️ *Comentario negativo recibido*\n"
                f"👤 {nombre} ({tel})\n"
                f"💬 {comentario}"
            )
        return {
            "ok": True,
            "mensaje_confirmacion": (
                f"¡Muchas gracias por su comentario, {nombre}! 🙏\n\n"
                f"Su opinión es muy valiosa para nosotros y nos ayuda a mejorar cada día. "
                f"¡Esperamos verlo pronto en {NOMBRE_LOCAL}! {_EMOJI_LOCAL}"
            ),
        }

    elif tipo == "notificar_dueno":
        _notificar_dueno(accion.get("mensaje", ""))
        return {"ok": True, "mensaje_confirmacion": None}

    return {"ok": True, "mensaje_confirmacion": None}


# ─── GEMINI ───────────────────────────────────────────────────────────────────
def _build_system_prompt_for(sn: str) -> str:
    """Construye un SYSTEM_PROMPT dinámico para el subniche indicado (demo mode)."""
    if sn not in _SUBNICHE_DEFAULTS:
        return SYSTEM_PROMPT
    d = _SUBNICHE_DEFAULTS[sn]
    nombre  = os.environ.get("GASTRO_DEMO_NOMBRE") or d["nombre"]
    horario = os.environ.get("GASTRO_DEMO_HORARIO") or d["horario"]
    emoji   = d.get("emoji", "🍴")
    return f"""════════════════════════════════════════════════════════
ROL
════════════════════════════════════════════════════════
Sos la asistente virtual de *{nombre}* ({sn}).
Tu trabajo: encargues, deliverys, presupuestos, reservas y gestión de comentarios por WhatsApp.
{d['tareas_extra']}

PERSONALIDAD:
- {d['personalidad']}
- Español neutro: NUNCA usés "vos", "che", "dale", "genial", "bárbaro", "re", "copado", "pibe"
- Tratá al cliente de "usted" o "tú" (nunca "vos")
- Emojis con moderación: máximo 1-2 por mensaje
- Respuestas cortas y directas — máximo 6 líneas salvo que el menú lo requiera

════════════════════════════════════════════════════════
DATOS DEL LOCAL
════════════════════════════════════════════════════════
- Nombre: {nombre}
- Horario: {horario}
- Fecha de hoy: {HOY}
- Todos los precios incluyen IVA.

════════════════════════════════════════════════════════
MENÚ PRINCIPAL
════════════════════════════════════════════════════════
*¡Bienvenido a {nombre}!* {emoji}
¿En qué puedo ayudarte?

1️⃣ {d['menu_label']} 🍽️
2️⃣ Hacer un pedido / delivery 🛵
3️⃣ Encargue especial 📦
4️⃣ Reservar una mesa 📅
5️⃣ Pedir presupuesto para evento 💬
6️⃣ Cancelar o modificar una reserva ✏️
7️⃣ Dejar un comentario ⭐

Para delivery/encargue/presupuesto → al finalizar usar:
ACCION: {{"tipo": "derivar_asesor", "motivo": "delivery|encargue|presupuesto_evento", "nombre": "...", "detalle": "...", "total": N}}

Para reservas → ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "HH:MM", "nota": "..."}}
Para cancelar → ACCION: {{"tipo": "cancelar_reserva", "nombre": "...", "fecha_legible": "...", "hora": "..."}}
Para reseñas  → ACCION: {{"tipo": "registrar_resena", "nombre": "...", "comentario": "...", "valoracion": "positiva|negativa|neutra"}}
"""


def _llamar_gemini(historial: list, subniche_override: str = "") -> str:
    if not _gemini_client:
        return "⚠️ Sistema no disponible. Contáctenos directamente."
    try:
        # Determinar subniche activo
        sn = subniche_override if subniche_override in _SUBNICHE_DEFAULTS else SUBNICHE
        sn_prompt = _build_system_prompt_for(sn)
        # Leer menú desde Airtable filtrado por subniche, fallback a hardcodeado
        menu_live = _at_leer_menu_subniche(sn)
        sn_menu   = _menu_texto(menu_live) if menu_live else _menu_texto(_MENUS_FALLBACK.get(sn, {}))
        sys_instr = sn_prompt + "\n\n## MENÚ DEL LOCAL\n" + sn_menu
        resp = _gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=historial,
            config={"system_instruction": sys_instr},
        )
        return resp.text or ""
    except Exception as e:
        print(f"[GASTRO-GEMINI] Error: {e}")
        return "⚠️ No pude procesar su mensaje. Por favor intente nuevamente."


# ─── ROUTER ───────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/demos/gastronomico", tags=["Demo — Gastronómico"])


class _MsgIn(BaseModel):
    telefono: str
    mensaje: str
    nombre: str = ""
    subniche: str = ""  # opcional — para demo multi-subniche desde el CRM HTML


def _procesar_mensaje(tel: str, texto: str, subniche_override: str = "") -> str:
    """Lógica central: selector subniche → Gemini → acciones → respuesta final."""

    # ── SELECTOR DE SUBNICHE (solo si aún no eligió) ──────────────────────────
    if tel not in SESION_SUBNICHE:
        msg_lower = texto.strip().lower().rstrip(".,!?")
        sn = _SELECTOR_MAP.get(msg_lower)
        if sn:
            # Cliente eligió subniche
            SESION_SUBNICHE[tel] = sn
            SESIONES[tel] = []  # sesión limpia para el nuevo subniche
            d = _SUBNICHE_DEFAULTS[sn]
            bienvenida = (
                f"*¡Bienvenido a {d['nombre']}!* {d['emoji']}\n"
                f"¿En qué puedo ayudarte?\n\n"
                f"1️⃣ {d['menu_label']} 🍽️\n"
                f"2️⃣ Hacer un pedido / delivery 🛵\n"
                f"3️⃣ Encargue especial (tortas, catering, salados) 📦\n"
                f"4️⃣ Reservar una mesa 📅\n"
                f"5️⃣ Pedir presupuesto para evento 💬\n"
                f"6️⃣ Cancelar o modificar una reserva ✏️\n"
                f"7️⃣ Dejar un comentario ⭐\n\n"
                f"_(Escribí *0* o *Menú* para ver esto de nuevo | *00* para cambiar negocio)_"
            )
            SESIONES[tel] = [
                {"role": "user",  "parts": [{"text": texto}]},
                {"role": "model", "parts": [{"text": bienvenida}]},
            ]
            return bienvenida
        else:
            # Todavía no eligió — mostrar selector
            SESIONES.setdefault(tel, [])
            return _SELECTOR_SUBNICHOS

    # "00" → volver al selector de sub-nichos
    if texto.strip() == "00":
        SESION_SUBNICHE.pop(tel, None)
        SESIONES[tel] = []
        return _SELECTOR_SUBNICHOS + "\n\n_(Escribí 00 en cualquier momento para volver aquí)_"

    # "0" o "menu"/"menú" → mostrar menú principal del subniche activo
    if texto.strip() in ("0", "menu", "menú", "Menu", "Menú", "MENU"):
        sn = SESION_SUBNICHE.get(tel, SUBNICHE)
        d  = _SUBNICHE_DEFAULTS[sn]
        menu_principal = (
            f"*¡Hola de nuevo!* {d['emoji']}\n"
            f"¿En qué puedo ayudarte?\n\n"
            f"1️⃣ {d['menu_label']} 🍽️\n"
            f"2️⃣ Hacer un pedido / delivery 🛵\n"
            f"3️⃣ Encargue especial 📦\n"
            f"4️⃣ Reservar una mesa 📅\n"
            f"5️⃣ Presupuesto para evento 💬\n"
            f"6️⃣ Cancelar / modificar reserva ✏️\n"
            f"7️⃣ Dejar un comentario ⭐\n\n"
            f"_(Escribí 00 para cambiar de tipo de negocio)_"
        )
        return menu_principal

    # ── SUBNICHE YA ELEGIDO → GEMINI ──────────────────────────────────────────
    sn_activo = subniche_override or SESION_SUBNICHE.get(tel, SUBNICHE)

    if tel not in SESIONES:
        SESIONES[tel] = []
    SESIONES[tel].append({"role": "user", "parts": [{"text": texto}]})
    SESIONES[tel] = SESIONES[tel][-20:]

    respuesta_raw = _llamar_gemini(SESIONES[tel], subniche_override=sn_activo)

    accion_match  = re.search(r"ACCION:\s*(\{.*\})", respuesta_raw, re.DOTALL)
    texto_visible = re.sub(r"ACCION:\s*\{.*\}", "", respuesta_raw, flags=re.DOTALL).strip()
    msg_final = texto_visible

    if accion_match:
        try:
            accion    = json.loads(accion_match.group(1))
            resultado = _ejecutar_accion(accion, tel)
            if resultado.get("mensaje_confirmacion"):
                msg_final = resultado["mensaje_confirmacion"]
            elif resultado.get("mensaje_error"):
                msg_final = resultado["mensaje_error"]
        except json.JSONDecodeError as e:
            print(f"[GASTRO] ACCION JSON inválido: {e} — raw: {accion_match.group(1)[:200]}")

    SESIONES[tel].append({"role": "model", "parts": [{"text": msg_final}]})
    return msg_final


@router.post("/whatsapp")
async def whatsapp(req: Request):
    """Endpoint principal — recibe mensaje de WhatsApp (YCloud / n8n)."""
    body = await req.json()

    wim     = body.get("whatsappInboundMessage", {})
    tel_raw = (wim.get("from") or body.get("from") or body.get("telefono") or
               body.get("data", {}).get("from") or "")
    texto   = (wim.get("text", {}).get("body") or
               body.get("text", {}).get("body") or body.get("mensaje") or
               body.get("data", {}).get("text", {}).get("body") or "")

    if not tel_raw or not texto:
        return {"status": "ignored", "reason": "sin telefono o texto"}

    tel = _norm_tel(tel_raw)
    msg_final = _procesar_mensaje(tel, texto)
    _enviar_texto(tel, msg_final)
    return {"status": "ok", "respuesta": msg_final}


@router.post("/mensaje")
async def mensaje(data: _MsgIn):
    """Endpoint alternativo tipo POST JSON (para tests / CRM simulador)."""
    tel = _norm_tel(data.telefono)
    # Si viene subniche desde el CRM HTML, forzarlo en la sesión
    if data.subniche and data.subniche in _SUBNICHE_DEFAULTS:
        SESION_SUBNICHE[tel] = data.subniche
    msg_final = _procesar_mensaje(tel, data.mensaje, subniche_override=data.subniche)
    _enviar_texto(tel, msg_final)
    return {"status": "ok", "respuesta": msg_final}


# ─── ENDPOINTS CRM ────────────────────────────────────────────────────────────
@router.get("/crm/reservas")
def crm_reservas():
    return {"status": "ok", "data": _at_listar_reservas()}


@router.get("/crm/pedidos")
def crm_pedidos():
    return {"status": "ok", "data": _at_listar_pedidos()}


@router.get("/crm/clientes")
def crm_clientes():
    return {"status": "ok", "data": _at_listar_clientes()}


@router.get("/config")
def config():
    return {
        "nombre":        NOMBRE_LOCAL,
        "subniche":      SUBNICHE,
        "emoji":         _EMOJI_LOCAL,
        "horario":       HORARIO,
        "alias_pago":    ALIAS_PAGO,
        "airtable_ok":   _at_disponible(),
        "cal_ok":        _cal_disponible(),
        "ycloud_ok":     bool(YCLOUD_API_KEY),
        "gemini_ok":     bool(GEMINI_API_KEY),
        "menu_fallback": MENU_FALLBACK,
        "subnichos_disponibles": list(_SUBNICHE_DEFAULTS.keys()),
    }


@router.post("/difusion")
async def difusion(req: Request):
    """Envía un mensaje masivo a la lista de teléfonos proporcionada."""
    body = await req.json()
    mensaje   = body.get("mensaje", "")
    telefonos = body.get("telefonos", [])   # lista de strings
    if not mensaje or not telefonos:
        return {"status": "error", "reason": "faltan mensaje o telefonos"}
    enviados, fallidos = 0, 0
    for tel_raw in telefonos:
        tel = _norm_tel(str(tel_raw))
        ok  = _enviar_texto(tel, mensaje)
        if ok:
            enviados += 1
        else:
            fallidos += 1
    return {"status": "ok", "enviados": enviados, "fallidos": fallidos, "total": len(telefonos)}


@router.get("/debug/reset/{telefono}")
def reset_sesion(telefono: str):
    tel = _norm_tel(telefono)
    if tel in SESIONES:
        del SESIONES[tel]
        return {"status": "ok", "msg": f"Sesión {tel} eliminada"}
    return {"status": "not_found"}


@router.get("/debug/config")
def debug_config():
    return config()
