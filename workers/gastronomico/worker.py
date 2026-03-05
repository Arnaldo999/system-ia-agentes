import os
import json
import uuid
import tempfile
import base64 as b64
import requests
from urllib.parse import quote
from datetime import date
from fastapi import APIRouter
from pydantic import BaseModel
import google.generativeai as genai
import openai

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

SYSTEM_PROMPT = f"""════════════════════════════════════════════════════════
ROL
════════════════════════════════════════════════════════
Sos *Alberto*, el asistente virtual de *La Parrilla de Don Alberto*.
Tu único trabajo es atender clientes por WhatsApp: mostrar el menú, tomar reservas y gestionar pedidos delivery.

PERSONALIDAD:
- Cordial y profesional, como un buen anfitrión de restaurante
- Español neutro: NUNCA usés "vos", "che", "dale", "genial", "bárbaro", "re", "copado", "pibe"
- Tratá al cliente de "usted" o "tú" (nunca "vos")
- Emojis con moderación: máximo 1-2 por mensaje
- Respuestas cortas y directas — máximo 6 líneas salvo que el menú lo requiera

════════════════════════════════════════════════════════
DATOS DEL RESTAURANTE
════════════════════════════════════════════════════════
- Nombre: La Parrilla de Don Alberto
- Especialidad: Parrilla argentina, cortes premium
- Horario: Martes a Domingo | Almuerzo 12:00-16:00 | Cena 20:00-00:00
- CERRADO los lunes — no aceptar reservas ni pedidos para ese día
- Alias de pago (seña): *{RESTAURANTE['alias_pago']}*
- Fecha de hoy: {HOY}

MENÚ COMPLETO:
{_menu_texto()}
Bebidas sin alcohol (agua, gaseosas, jugos): $800-1.200 ARS
Todos los precios incluyen IVA.

════════════════════════════════════════════════════════
MENÚ PRINCIPAL (punto de entrada)
════════════════════════════════════════════════════════
CUÁNDO mostrarlo: ante cualquier primer mensaje, saludo, o cuando el cliente escriba "0" o "menu".

TEXTO EXACTO a mostrar:
*¡Bienvenido a La Parrilla de Don Alberto!* 🍖
¿En qué podemos ayudarte hoy?

1️⃣ Ver el Menú del día
2️⃣ Hacer una reserva
3️⃣ Cancelar una reserva
4️⃣ Modificar una reserva
5️⃣ Delivery (hacer pedido)

REGLA: Esperá que el cliente elija. No agregues texto extra.

════════════════════════════════════════════════════════
TAREA 1 — VER MENÚ DEL DÍA (opción 1)
════════════════════════════════════════════════════════
PASO 1: El cliente elige "1" o "ver menú" → mostrá SOLO las categorías:

📋 *Menú del Día*
1️⃣ Platos Principales 🥩
2️⃣ Entradas 🥗
3️⃣ Postres 🍰
4️⃣ Cafetería ☕
5️⃣ Bebidas 🍷
0️⃣ Volver al menú principal

PASO 2: El cliente elige una categoría (número 1-5) → mostrá los ítems con precio.
Ejemplo para "1" (Platos Principales):
🥩 *Platos Principales*
1. Asado de Tira (400gr) con papas fritas — $6.800
2. Bife de Chorizo (300gr) con ensalada mixta — $7.500
3. Bondiola Braseada con puré de calabaza — $5.900
0️⃣ Volver a categorías | escribí *00* para el menú principal

PASO 3: Si el cliente elige un plato → preguntá: "¿Desea hacer una reserva para venir al restaurante o prefiere pedido delivery?"

════════════════════════════════════════════════════════
TAREA 2 — HACER RESERVA (opción 2)
════════════════════════════════════════════════════════
DATOS a recopilar en orden (uno por vez):
1. Nombre completo
2. Cantidad de personas
3. Fecha (solo rechazá si es lunes)
4. Horario (almuerzo 12-16hs o cena 20-00hs)

CUANDO tengas los 4 datos → confirmá: "¿Confirma: reserva para [nombre], [N] personas, [fecha] a las [hora] hs?"
CUANDO el cliente confirme → ejecutá:
ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "sábado 8 de marzo", "hora": "21:00", "tipo_reserva": "simple", "nota": "..."}}

⚠️ NO tenés información de disponibilidad en tiempo real. NUNCA digas "está completo" o "no hay lugar".
⚠️ NUNCA escribas "reserva confirmada" vos mismo — el sistema lo confirma automáticamente.

════════════════════════════════════════════════════════
TAREA 3 — CANCELAR RESERVA (opción 3)
════════════════════════════════════════════════════════
DATOS a recopilar:
1. Nombre de la reserva
2. Fecha y hora

Confirmá: "¿Confirma la cancelación de la reserva de [nombre] para el [fecha] a las [hora]?"
Cuando confirme → ejecutá:
ACCION: {{"tipo": "cancelar_reserva", "nombre": "...", "fecha_legible": "...", "hora": "..."}}

════════════════════════════════════════════════════════
TAREA 4 — MODIFICAR RESERVA (opción 4)
════════════════════════════════════════════════════════
DATOS a recopilar:
1. Nombre de la reserva original
2. Qué quiere cambiar (fecha / hora / cantidad de personas)
3. Los nuevos datos

Confirmá los cambios antes de guardar.
Cuando confirme → ejecutá:
ACCION: {{"tipo": "modificar_reserva", "nombre": "...", "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "...", "personas": N, "nota": "Modificación solicitada por el cliente"}}

⚠️ Igual que en reservas: NO tenés datos de disponibilidad. No inventes que algo "está ocupado".

════════════════════════════════════════════════════════
TAREA 5 — DELIVERY (opción 5)
════════════════════════════════════════════════════════
La seña del 10% es OBLIGATORIA para confirmar el pedido.
Seguí estos pasos EN ORDEN — no saltés pasos.

─── TURNO 1: Pedí el nombre ───
Respondé ÚNICAMENTE:
"¡Con gusto! Para registrar su pedido, ¿podría indicarme su nombre completo?"
⛔ NO muestres el menú todavía. Esperá el nombre.

─── TURNO 2: Mostrá categorías ───
Recién cuando el cliente te dé el nombre, respondé:
"Perfecto, [nombre]. Este pedido requiere una *seña del 10%* del total para confirmar. 🛵
¿Qué le gustaría pedir? Nuestras categorías:
1️⃣ Platos Principales 🥩
2️⃣ Entradas 🥗
3️⃣ Postres 🍰
4️⃣ Cafetería ☕
5️⃣ Bebidas 🍷"

─── TURNOS SIGUIENTES: Tomá el pedido ───
- Cuando el cliente elige una categoría → mostrá sus ítems con precio
- Cuando elige un ítem → confirmalo y preguntá "¿Desea agregar algo más?"
- ⛔ NO calcules el total hasta que el cliente diga explícitamente que terminó

─── TURNO FINAL: Cliente dice que terminó ───
Palabras que indican que terminó: "listo", "con eso", "nada más", "estamos", "eso es todo", "es todo"

En ese mismo mensaje, respondé con EXACTAMENTE este formato:
"📦 *Su pedido:*
• [ítem 1] — $[precio]
• [ítem 2] — $[precio]
*Total: $[TOTAL] ARS*
💳 *Seña requerida (10%): $[SEÑA] ARS*

Puede abonar por transferencia o MercadoPago al alias: *{RESTAURANTE['alias_pago']}*

📸 *Una vez realizada la transferencia, envíenos la captura del comprobante para confirmar su pedido.*"

Luego, EN EL MISMO MENSAJE, agregá la acción:
ACCION: {{"tipo": "solicitar_comprobante", "nombre": "[nombre del cliente]", "detalle": "[lista detallada de ítems]", "total": [número sin formato]}}

⛔ PROHIBIDO: No uses ACCION crear_pedido en este paso — SIEMPRE solicitar_comprobante
⛔ PROHIBIDO: No preguntes la dirección — el sistema la pide automáticamente después del pago
⛔ PROHIBIDO: No agregues texto después del ACCION

════════════════════════════════════════════════════════
REGLA DE CONTEXTO — LEÉ ESTO ANTES DE RESPONDER
════════════════════════════════════════════════════════
SIEMPRE analizá el historial para saber en qué flujo estás:

| Si el último mensaje del bot... | Entonces el próximo mensaje del cliente es... |
|---|---|
| Pedía el nombre para reserva | El nombre para la reserva |
| Pedía cantidad de personas | La cantidad de personas |
| Pedía la fecha | La fecha |
| Pedía el horario | El horario |
| Mostraba categorías (1-5) | El número de una categoría |
| Mostraba ítems de una categoría | El número de un ítem o "agregar algo más" |
| Preguntaba "¿algo más?" | Un ítem adicional o "listo/nada más/etc." |
| Pedía el nombre para delivery | El nombre del cliente |
| Pedía nombre para cancelar | El nombre de la reserva a cancelar |

⛔ NUNCA interpretes un número como opción del menú principal si estás dentro de un flujo activo.
⛔ NUNCA abandones el flujo actual por culpa de un número — interpretalo según el contexto.

ÚNICA forma de salir de un flujo: cliente escribe "0" (menú principal) o "00" (reiniciar).

════════════════════════════════════════════════════════
CASOS ESPECIALES
════════════════════════════════════════════════════════
- Grupos 10+ personas: "Para grupos grandes coordinamos el salón privado, lo gestiono con el equipo." → ACCION notificar_dueno
- Alergias: anotarlas en la nota de la reserva
- Lunes: "Los lunes permanecemos cerrados. Atendemos de martes a domingo desde las 12 hs."
- Facturas: "Las facturas se emiten en el local al momento del pago."
- Preguntas fuera del contexto del restaurante: respondé amablemente que solo podés ayudar con temas del restaurante

════════════════════════════════════════════════════════
FORMATO WhatsApp
════════════════════════════════════════════════════════
- Negrita: *texto*
- No uses markdown con # ni listas con guion
- Máximo 6 líneas por mensaje (excepto cuando mostrás el menú)

════════════════════════════════════════════════════════
ACCIONES DISPONIBLES (al final del mensaje)
════════════════════════════════════════════════════════
Reserva:
ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "sábado 8 de marzo", "hora": "21:00", "tipo_reserva": "simple", "nota": "..."}}

Cancelar reserva:
ACCION: {{"tipo": "cancelar_reserva", "nombre": "...", "fecha_legible": "...", "hora": "..."}}

Modificar reserva:
ACCION: {{"tipo": "modificar_reserva", "nombre": "...", "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "...", "personas": N, "nota": "..."}}

Solicitar comprobante de seña (delivery):
ACCION: {{"tipo": "solicitar_comprobante", "nombre": "...", "detalle": "...", "total": N}}

Notificar al dueño:
ACCION: {{"tipo": "notificar_dueno", "mensaje": "..."}}

⛔ CRÍTICO: Cuando uses ACCION crear_reserva o crear_pedido, tu mensaje visible debe decir SOLO "Procesando...".
El sistema envía la confirmación real al cliente. JAMÁS escribas "reserva confirmada" o "pedido registrado" vos mismo."""

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

def at_guardar_conversacion(telefono: str, historial: list, record_id: str = None, estado: str = "activo"):
    """Guarda/actualiza el historial de conversación."""
    try:
        # Limitar a últimos 20 turnos para no superar el límite de campo
        historial_recortado = historial[-20:]
        payload = {"fields": {
            "telefono": telefono,
            "estado_actual": estado,
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

def at_get_or_create_cliente(telefono: str, nombre: str = "") -> str:
    """Busca al cliente por teléfono o lo crea en la tabla Clientes."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Clientes"
        # 1. Buscar
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": f"{{Teléfono}}='{telefono}'",
            "maxRecords": 1,
        })
        records = r.json().get("records", [])
        if records:
            return records[0]["id"]
        
        # 2. Si no existe, crearlo
        payload = {"records": [{"fields": {
            "Teléfono": telefono,
            "Nombre": nombre
        }}]}
        r_post = requests.post(url, headers=AT_HEADERS(), json=payload)
        resp_post = r_post.json()
        if "records" in resp_post and resp_post["records"]:
            return resp_post["records"][0]["id"]
            
    except Exception as e:
        print(f"[AT] Error get_or_create_cliente: {e}")
    return ""

def at_crear_reserva(datos: dict) -> dict:
    """Guarda la reserva en la tabla Reservas."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        # Sanitizar personas — asegurar que sea int
        try:
            personas_num = int(str(datos.get("personas", 1)).strip().strip('"'))
        except Exception:
            personas_num = 1

        # Demo: solo existe reserva_simple (delivery con seña → tabla pedidos)
        tipo_at = "reserva_simple"

        cliente_id = at_get_or_create_cliente(str(datos.get("telefono", "")).strip(), str(datos.get("nombre", "")).strip())
        
        # Combinar en ISO para campo Date con time
        fecha_str = str(datos.get("fecha_iso", "")).strip()[:10]
        hora_str = str(datos.get("hora", "")).strip()
        fecha_y_hora = f"{fecha_str}T{hora_str}:00.000Z" if fecha_str and hora_str else None

        campos = {
            "Clientes":    [cliente_id] if cliente_id else [],
            "Cantidad de Personas": personas_num,
            "Estado":      "pendiente",
            "Especificaciones": str(datos.get("especificaciones", datos.get("nota", ""))).strip(),
        }
        if fecha_y_hora:
            campos["Fecha y Hora"] = fecha_y_hora


        print(f"[AT] Enviando reserva: {campos}")
        r = requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": campos}]})
        resp = r.json()
        print(f"[AT] Reserva status={r.status_code} resp={resp}")
        return {"ok": r.status_code == 200, "resp": resp}
    except Exception as e:
        print(f"[AT] Error crear_reserva: {e}")
        return {"ok": False, "error": str(e)}

def at_crear_pedido(datos: dict) -> dict:
    """Guarda el pedido en la tabla pedidos."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        total = float(datos.get("total", 0))
        sena  = round(total * 0.10, 2)
        saldo = round(total * 0.90, 2)
        cliente_id = at_get_or_create_cliente(str(datos.get("telefono", "")).strip(), str(datos.get("nombre", "")).strip())
        campos = {
            "Clientes":         [cliente_id] if cliente_id else [],
            "detalle":          datos.get("detalle", ""),
            "total_ars":        total,
            "sena_ars":         sena,
            "saldo_a_cobrar":   saldo,
            "estado_pago":      datos.get("estado_pago", "pendiente"),
            "estado_entrega":   "pendiente",
        }
        print(f"[AT] Enviando pedido: {campos}")
        r = requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": campos}]})
        resp = r.json()
        print(f"[AT] Pedido status={r.status_code} resp={resp}")
        return {"ok": r.status_code == 200, "resp": resp}
    except Exception as e:
        print(f"[AT] Error crear_pedido: {e}")
        return {"ok": False, "error": str(e)}

def at_actualizar_pedido(record_id: str, datos: dict) -> dict:
    """Actualiza campos de un pedido existente en Airtable (PATCH)."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos/{record_id}"
        campos = {}
        if "detalle" in datos:
            campos["detalle"] = datos["detalle"]
        if "estado_pago" in datos:
            campos["estado_pago"] = datos["estado_pago"]
        r = requests.patch(url, headers=AT_HEADERS(), json={"fields": campos})
        resp = r.json()
        print(f"[AT] Actualizar pedido {record_id} status={r.status_code} resp={resp}")
        return {"ok": r.status_code == 200, "resp": resp}
    except Exception as e:
        print(f"[AT] Error actualizar_pedido: {e}")
        return {"ok": False, "error": str(e)}

def at_get_reservas_futuras() -> str:
    """
    Devuelve un resumen de las reservas activas (no canceladas) desde hoy.
    Se inyecta en el system prompt para que Gemini conozca la disponibilidad real.
    """
    try:
        hoy = date.today().isoformat()
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": f"AND({{Fecha y Hora}}>='{hoy}', {{Estado}}!='cancelada')",
            "sort[0][field]": "Fecha y Hora",
            "sort[0][direction]": "asc",
            "maxRecords": 50,
        })
        records = r.json().get("records", [])
        if not records:
            return "No hay reservas activas próximas."
        lineas = []
        for rec in records:
            f = rec["fields"]
            lineas.append(
                f"- {f.get('Fecha y Hora','')} | {f.get('Nombre del Cliente',[''])[0] if type(f.get('Nombre del Cliente'))==list else f.get('Nombre del Cliente','')} | {f.get('Cantidad de Personas','')} pax | Estado: {f.get('Estado','')}"
            )
        return "\n".join(lineas)
    except Exception as e:
        print(f"[AT] Error get_reservas_futuras: {e}")
        return "(no disponible)"


def at_buscar_pendiente_confirmacion() -> list:
    """Busca conversaciones en estado esperando_confirmacion (pago pendiente de aprobar)."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": "SEARCH('esperando_confirmacion', {estado_actual})",
            "sort[0][field]": "telefono",
            "maxRecords": 10,
        })
        return r.json().get("records", [])
    except Exception as e:
        print(f"[AT] Error buscar_pendiente_confirmacion: {e}")
        return []


def at_confirmar_pago_pedido(nro_pedido: str):
    """Actualiza estado_pago del pedido a 'confirmado' en la tabla pedidos."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": f"{{nro_pedido}}='{nro_pedido}'",
            "maxRecords": 1,
        })
        records = r.json().get("records", [])
        if records:
            rec_id = records[0]["id"]
            requests.patch(
                f"{url}/{rec_id}",
                headers=AT_HEADERS(),
                json={"fields": {"estado_pago": "confirmado"}},
            )
            print(f"[AT] Pedido {nro_pedido} → estado_pago=confirmado")
    except Exception as e:
        print(f"[AT] Error confirmar_pago_pedido: {e}")


def at_marcar_entregado(nro_pedido: str) -> dict:
    """Marca el pedido como entregado y el saldo cobrado."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": f"{{nro_pedido}}='{nro_pedido}'",
            "maxRecords": 1,
        })
        records = r.json().get("records", [])
        if not records:
            return {"ok": False, "error": f"No se encontró el pedido {nro_pedido}"}
        rec_id = records[0]["id"]
        requests.patch(
            f"{url}/{rec_id}",
            headers=AT_HEADERS(),
            json={"fields": {"estado_entrega": "entregado"}},
        )
        print(f"[AT] Pedido {nro_pedido} → estado_entrega=entregado")
        return {"ok": True, "nro_pedido": nro_pedido}
    except Exception as e:
        print(f"[AT] Error marcar_entregado: {e}")
        return {"ok": False, "error": str(e)}


def at_buscar_pedido_pendiente_tel(telefono: str) -> dict | None:
    """Busca el pedido más reciente en estado 'pendiente' para un teléfono dado."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": f"AND(FIND('{telefono}', {{Clientes}}&'')>0, {{estado_pago}}='pendiente')",
            "sort[0][field]": "ID Pedido",
            "sort[0][direction]": "desc",
            "maxRecords": 1,
        })
        records = r.json().get("records", [])
        return records[0] if records else None
    except Exception as e:
        print(f"[AT] Error buscar_pedido_pendiente_tel: {e}")
        return None


def at_buscar_reserva(nombre: str, telefono: str) -> dict | None:
    """Busca la reserva más reciente por nombre y teléfono."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        formula = f"FIND('{telefono}', {{Clientes}}&'')>0"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": formula,
            "sort[0][field]": "Fecha y Hora",
            "sort[0][direction]": "desc",
            "maxRecords": 1,
        })
        records = r.json().get("records", [])
        return records[0] if records else None
    except Exception as e:
        print(f"[AT] Error buscar_reserva: {e}")
        return None

def at_actualizar_reserva(record_id: str, campos: dict) -> dict:
    """Actualiza (PATCH) una reserva existente en Airtable."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas/{record_id}"
        r = requests.patch(url, headers=AT_HEADERS(), json={"fields": campos})
        resp = r.json()
        print(f"[AT] Actualizar reserva {record_id} → status={r.status_code} resp={resp}")
        return {"ok": r.status_code == 200, "resp": resp}
    except Exception as e:
        print(f"[AT] Error actualizar_reserva: {e}")
        return {"ok": False, "error": str(e)}

def at_actualizar_estado(record_id: str, estado: str):
    """Actualiza solo el campo estado_actual de una conversación."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas/{record_id}"
        requests.patch(url, headers=AT_HEADERS(), json={"fields": {"estado_actual": estado}})
    except Exception as e:
        print(f"[AT] Error actualizar_estado: {e}")

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

def enviar_cliente(telefono: str, mensaje: str):
    """Envía mensaje proactivo al cliente via Evolution API."""
    evo_url = os.environ.get("EVOLUTION_API_URL", "")
    evo_instance = os.environ.get("EVOLUTION_INSTANCE", "")
    evo_key = os.environ.get("EVOLUTION_API_KEY", "")
    if not all([evo_url, evo_instance, evo_key]):
        print(f"[Cliente] Evolution no configurado. Msg: {mensaje}")
        return
    try:
        requests.post(
            f"{evo_url}/message/sendText/{evo_instance}",
            headers={"apikey": evo_key, "Content-Type": "application/json"},
            json={"number": telefono, "text": mensaje},
            timeout=10,
        )
    except Exception as e:
        print(f"[Cliente] Error enviar: {e}")

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
        resultado = at_crear_reserva({
            **accion,
            "telefono": tel,
            "especificaciones": accion.get("nota", ""),
        })
        print(f"[Acción] Crear reserva → {resultado}")
        
        # Obtenemos id real si es posible
        nro = ""
        try:
            if resultado.get("ok"):
                nro = str(resultado["resp"]["records"][0]["fields"].get("ID Reserva", "N/A"))
        except:
            nro = "N/A"


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
        resultado = at_crear_pedido({
            **accion,
            "telefono": tel,
        })
        print(f"[Acción] Crear pedido → {resultado}")
        nro = ""
        try:
            if resultado.get("ok"):
                nro = str(resultado["resp"]["records"][0]["fields"].get("ID Pedido", "N/A"))
        except:
            nro = "N/A"

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

    elif tipo == "cancelar_reserva":
        nombre = accion.get("nombre", "")
        fecha  = accion.get("fecha_legible", accion.get("fecha_iso", ""))
        hora   = accion.get("hora", "")

        # Buscar la reserva existente solo por teléfono (evita problemas de case-sensitivity en nombre)
        try:
            url_buscar = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
            r_buscar = requests.get(url_buscar, headers=AT_HEADERS(), params={
                "filterByFormula": f"FIND('{tel}', {{Clientes}}&'')>0",
                "sort[0][field]": "Fecha y Hora",
                "sort[0][direction]": "desc",
                "maxRecords": 1,
            })
            registros = r_buscar.json().get("records", [])
            reserva_existente = registros[0] if registros else None
            print(f"[Acción] cancelar_reserva: búsqueda por tel={tel} → {len(registros)} registro(s)")
        except Exception as e:
            print(f"[Acción] cancelar_reserva: error en búsqueda → {e}")
            reserva_existente = None

        if reserva_existente:
            record_id = reserva_existente["id"]
            nota_cancel = f"CANCELADA el {date.today().strftime('%d/%m/%Y')} — {fecha} {hora}"
            resultado_cancel = at_actualizar_reserva(record_id, {
                "Estado": "cancelada",
                "Especificaciones": nota_cancel,
            })
            print(f"[Acción] Cancelar reserva PATCH → {resultado_cancel}")
        else:
            print(f"[Acción] cancelar_reserva: no se encontró fila para '{nombre}' / {tel}")

        notificar_dueno(
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
                f"Si desea hacer una nueva reserva, con gusto lo atendemos. 🍖"
            )
        }

    elif tipo == "modificar_reserva":
        # Buscar la reserva existente por nombre + teléfono
        reserva_existente = at_buscar_reserva(accion.get("nombre", ""), tel)
        if not reserva_existente:
            return {
                "ok": False,
                "mensaje_error": (
                    f"⚠️ No encontré una reserva a nombre de *{accion.get('nombre')}* en nuestro sistema.\n\n"
                    f"Si desea hacer una nueva reserva, elija la opción 2 del menú."
                )
            }
        record_id = reserva_existente["id"]
        try:
            personas_num = int(str(accion.get("personas", reserva_existente["fields"].get("Personas", 1))).strip().strip('"'))
        except Exception:
            personas_num = reserva_existente["fields"].get("Personas", 1)

        campos_nuevos = {
            "Cantidad de Personas": personas_num,
            "Estado": "confirmada",
            "Especificaciones": accion.get("nota", "Reserva modificada por el cliente"),
        }
        
        fecha_str = str(accion.get("fecha_iso", "")).strip()[:10]
        hora_str = str(accion.get("hora", "")).strip()
        if fecha_str and hora_str:
            campos_nuevos["Fecha y Hora"] = f"{fecha_str}T{hora_str}:00.000Z"

        resultado = at_actualizar_reserva(record_id, campos_nuevos)
        print(f"[Acción] Modificar reserva PATCH → {resultado}")
        if resultado.get("ok"):
            notificar_dueno(
                f"✏️ *Reserva MODIFICADA*\n"
                f"👤 {accion.get('nombre')}\n"
                f"👥 {personas_num} personas\n"
                f"📅 {accion.get('fecha_legible', accion.get('fecha_iso'))} a las {accion.get('hora')}\n"
                f"📞 {tel}"
            )
            return {
                "ok": True,
                "mensaje_confirmacion": (
                    f"✅ *Reserva actualizada correctamente*\n\n"
                    f"👤 {accion.get('nombre')}\n"
                    f"👥 {personas_num} personas\n"
                    f"📅 {accion.get('fecha_legible', accion.get('fecha_iso'))} a las {accion.get('hora')} hs\n\n"
                    f"¡Lo esperamos en La Parrilla de Don Alberto! 🍖"
                )
            }
        else:
            return {
                "ok": False,
                "mensaje_error": "⚠️ No se pudo actualizar la reserva. Comuníquese directamente con el restaurante."
            }

    elif tipo == "solicitar_comprobante":
        nombre = accion.get("nombre", "")
        detalle = accion.get("detalle", "")
        total   = float(accion.get("total", 0))
        sena    = total * 0.10
        nro     = f"PED-{str(uuid.uuid4())[:5].upper()}"

        # Crear el registro en Airtable inmediatamente con estado_pago = "pendiente"
        resultado_at = at_crear_pedido({
            "nombre":      nombre,
            "telefono":    tel,
            "detalle":     detalle,
            "total":       total,
            "estado_pago": "pendiente",
        })
        record_id = None
        nro = "N/A"
        if resultado_at.get("ok"):
            records = resultado_at.get("resp", {}).get("records", [])
            if records:
                record_id = records[0].get("id")
                nro = str(records[0]["fields"].get("ID Pedido", "N/A"))

        pedido_data = {
            "nombre":     nombre,
            "telefono":   tel,
            "detalle":    detalle,
            "total":      total,
            "nro_pedido": nro,
            "record_id":  record_id,  # para PATCH posterior
        }
        nuevo_estado = json.dumps({"estado": "esperando_comprobante", "pedido": pedido_data})

        notificar_dueno(
            f"🛒 *Nuevo pedido pendiente de pago*\n"
            f"👤 {nombre or tel}\n"
            f"📋 {detalle}\n"
            f"💰 Total: ${total:,.0f} ARS\n"
            f"💳 Seña: ${sena:,.0f} ARS\n"
            f"📞 {tel}\n\n"
            f"⏳ Esperando comprobante del cliente..."
        )
        return {
            "ok": True,
            "mensaje_confirmacion": None,   # Usar el texto que generó Gemini
            "nuevo_estado": nuevo_estado,
        }

    elif tipo == "notificar_dueno":
        notificar_dueno(accion.get("mensaje", ""))
        return {"ok": True, "mensaje_confirmacion": None}

    return {"ok": True, "mensaje_confirmacion": None}

# ─────────────────────────────────────────────────────────────────────────────
# WHISPER — TRANSCRIPCIÓN DE AUDIO
# ─────────────────────────────────────────────────────────────────────────────
def transcribir_audio(audio_url: str = "", audio_base64: str = "", audio_msg_raw: str = "{}") -> str:
    """
    Intenta obtener el audio por 4 métodos en cascada:
      0. Evolution API getBase64FromMediaMessage (audio_msg_raw con key+message)
      1. Base64 embebido directamente
      2. URL descargable directamente
      3. URL con header apikey (Evolution API autenticado)
    Luego transcribe con Whisper y devuelve el texto.
    """
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    if not OPENAI_API_KEY:
        print("[Whisper] Sin OPENAI_API_KEY — omitiendo transcripción")
        return ""

    audio_bytes  = None
    metodo_usado = ""
    content_type = ""

    # Mapa Content-Type → extensión (Whisper detecta el formato por extensión)
    MIME_EXT = {
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mpga": ".mp3",
        "audio/ogg":  ".ogg", "audio/opus": ".ogg",
        "audio/wav":  ".wav", "audio/x-wav": ".wav",
        "audio/mp4":  ".m4a", "audio/m4a": ".m4a",
        "audio/webm": ".webm",
        "audio/flac": ".flac",
    }

    def _ext_from(ct: str, url: str) -> str:
        """Detecta extensión desde Content-Type o URL."""
        for mime, ext in MIME_EXT.items():
            if mime in ct.lower():
                return ext
        for ext in [".mp3", ".ogg", ".wav", ".m4a", ".webm", ".flac", ".oga", ".mpga"]:
            if url.lower().endswith(ext):
                return ext
        return ".ogg"   # WhatsApp PTT siempre es OGG/Opus

    # ── Método 0: Evolution API getBase64FromMediaMessage ─────────────────
    if audio_msg_raw and audio_msg_raw not in ("{}", "") and not audio_bytes:
        evo_url      = os.environ.get("EVOLUTION_API_URL", "")
        evo_instance = os.environ.get("EVOLUTION_INSTANCE", "")
        evo_key      = os.environ.get("EVOLUTION_API_KEY", "")
        try:
            msg_data = json.loads(audio_msg_raw)
            resp = requests.post(
                f"{evo_url}/chat/getBase64FromMediaMessage/{quote(evo_instance)}",
                json={"message": msg_data, "convertToMp4": False},
                headers={"apikey": evo_key, "Content-Type": "application/json"},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                result    = resp.json()
                b64_data  = result.get("base64", "")
                if b64_data:
                    audio_bytes  = b64.b64decode(b64_data)
                    # Obtener mimetype desde el audioMessage
                    audio_msg_obj = msg_data.get("message", {})
                    audio_info    = audio_msg_obj.get("audioMessage", audio_msg_obj.get("pttMessage", {}))
                    content_type  = audio_info.get("mimetype", "audio/ogg")
                    # audio_url para detectar extensión si es necesario
                    audio_url = audio_url or audio_info.get("url", "")
                    metodo_usado  = "evolution_getBase64"
                    print(f"[Whisper] Método 0 (Evolution getBase64) OK — {len(audio_bytes)} bytes — CT: {content_type}")
                else:
                    print(f"[Whisper] Método 0 (Evolution getBase64) respuesta sin base64")
            else:
                print(f"[Whisper] Método 0 (Evolution getBase64) status={resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[Whisper] Método 0 (Evolution getBase64) FALLÓ: {e}")

    # ── Método 1: base64 embebido ──────────────────────────────────────────
    if audio_base64 and not audio_bytes:
        try:
            header, data = (audio_base64.split(",", 1) if "," in audio_base64
                            else ("", audio_base64))
            content_type = header   # p.ej. "data:audio/ogg;base64"
            audio_bytes  = b64.b64decode(data)
            metodo_usado = "base64"
            print(f"[Whisper] Método 1 (base64) OK — {len(audio_bytes)} bytes")
        except Exception as e:
            print(f"[Whisper] Método 1 (base64) FALLÓ: {e}")

    # ── Método 2: URL directa sin auth ────────────────────────────────────
    if audio_url and not audio_bytes:
        try:
            r = requests.get(audio_url, timeout=15)
            if r.status_code == 200 and len(r.content) > 100:
                audio_bytes  = r.content
                content_type = r.headers.get("Content-Type", "")
                metodo_usado = "url_directa"
                print(f"[Whisper] Método 2 (URL directa) OK — {len(audio_bytes)} bytes — CT: {content_type}")
            else:
                print(f"[Whisper] Método 2 (URL directa) status={r.status_code}")
        except Exception as e:
            print(f"[Whisper] Método 2 (URL directa) FALLÓ: {e}")

    # ── Método 3: URL con apikey de Evolution API ─────────────────────────
    if audio_url and not audio_bytes:
        evo_key = os.environ.get("EVOLUTION_API_KEY", "")
        try:
            r = requests.get(audio_url, headers={"apikey": evo_key}, timeout=15)
            if r.status_code == 200 and len(r.content) > 100:
                audio_bytes  = r.content
                content_type = r.headers.get("Content-Type", "")
                metodo_usado = "url_con_auth"
                print(f"[Whisper] Método 3 (URL+auth) OK — {len(audio_bytes)} bytes — CT: {content_type}")
            else:
                print(f"[Whisper] Método 3 (URL+auth) status={r.status_code}")
        except Exception as e:
            print(f"[Whisper] Método 3 (URL+auth) FALLÓ: {e}")

    if not audio_bytes:
        print("[Whisper] Ningún método logró obtener el audio")
        return ""

    # ── Transcribir con Whisper ───────────────────────────────────────────
    ext = _ext_from(content_type, audio_url)
    try:
        cliente_openai = openai.OpenAI(api_key=OPENAI_API_KEY)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            transcripcion = cliente_openai.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="es",
            )
        os.unlink(tmp_path)
        texto = transcripcion.text.strip()
        print(f"[Whisper] Transcripción ({metodo_usado}, {ext}): '{texto}'")
        return texto
    except Exception as e:
        print(f"[Whisper] Error al transcribir: {e}")
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────
class MensajeEntrante(BaseModel):
    telefono:      str
    mensaje:       str = ""
    tiene_imagen:  bool = False
    es_admin:      bool = False
    audio_url:     str = ""    # URL del audio (WhatsApp CDN)
    audio_base64:  str = ""    # Base64 embebido (si Evolution lo envía)
    audio_msg_raw: str = "{}"  # JSON con {key, message} para getBase64FromMediaMessage

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/basico/mensaje", summary="Plan BASIC: Agente conversacional con Gemini")
async def manejar_mensaje(entrada: MensajeEntrante):
    try:
        tel = entrada.telefono.strip()
        msg = entrada.mensaje.strip()
        # DEBUG — ver exactamente qué manda n8n (borrar después de confirmar)
        print(f"[DEBUG] tel={tel} | mensaje={repr(msg)} | tiene_imagen={entrada.tiene_imagen} | audio_url={bool(entrada.audio_url)}")

        # ── Transcripción de audio (Whisper) — PRIMERO que todo ───────────
        # Si tiene_imagen=True, NO intentar transcribir: audio_msg_raw puede
        # traer el JSON de la imagen de Evolution y Whisper rechazaría el PNG.
        tiene_audio = (not entrada.tiene_imagen) and (
            entrada.audio_url or entrada.audio_base64
            or entrada.audio_msg_raw not in ("{}", "")
        )
        if tiene_audio:
            transcripcion = transcribir_audio(
                entrada.audio_url, entrada.audio_base64, entrada.audio_msg_raw
            )
            if transcripcion:
                msg = transcripcion   # Reemplazar mensaje con el texto transcripto
            else:
                return {
                    "respuesta": "",
                    "tipo_mensaje": "audio_no_procesado",
                    "accion_ejecutada": None,
                }

        # ── Normalizar mensaje de imagen ──────────────────────────────────
        # Si tiene_imagen=True, SIEMPRE marcar como imagen (override cualquier texto)
        if entrada.tiene_imagen:
            msg = "[imagen enviada]"
        # ─────────────────────────────────────────────────────────────────

        # Cargar conversación desde Airtable (ANTES del early return para imagen)
        conv = at_get_conversacion(tel)
        record_id = conv["id"] if conv else None

        # Leer estado actual (puede ser JSON de estado de espera o simple "activo")
        estado_raw = conv["fields"].get("estado_actual", "activo") if conv else "activo"
        try:
            estado_data = json.loads(estado_raw)
            estado_actual = estado_data.get("estado", "activo")
            pedido_pendiente = estado_data.get("pedido", {})
        except Exception:
            estado_actual = estado_raw  # "activo" simple
            pedido_pendiente = {}

        # Cargar historial
        historial_raw = conv["fields"].get("datos_pedido", "[]") if conv else "[]"
        try:
            historial = json.loads(historial_raw)
            if not isinstance(historial, list):
                historial = []
        except Exception:
            historial = []

        # Si mensaje vacío: solo ignorar si NO estamos esperando un comprobante
        # (n8n envía tiene_imagen=False para imágenes, este es el fix principal)
        if not msg:
            if estado_actual == "esperando_comprobante":
                msg = "[imagen enviada]"  # Tratar como comprobante
            else:
                return {"respuesta": "", "tipo_mensaje": "ignorado", "accion_ejecutada": None}

        # ── CONFIRMACIÓN DE PAGO POR WHATSAPP (solo el dueño) ─────────────────
        dueno_tel = NUMERO_DUENO.lstrip("+").replace(" ", "")
        es_dueno  = tel == dueno_tel or tel.endswith(dueno_tel[-9:])
        if es_dueno and "pago confirmado" in msg.lower():
            pendientes = at_buscar_pendiente_confirmacion()
            if not pendientes:
                return {
                    "respuesta": "No hay pagos pendientes de confirmación en este momento.",
                    "tipo_mensaje": "texto",
                    "accion_ejecutada": None,
                }
            # Tomar el más reciente
            conv_cliente  = pendientes[0]
            tel_cliente   = conv_cliente["fields"].get("telefono", "")
            estado_data_c = json.loads(conv_cliente["fields"].get("estado_actual", "{}"))
            pedido_c      = estado_data_c.get("pedido", {})
            nombre_c      = pedido_c.get("nombre", tel_cliente)

            # 1. Actualizar estado del cliente → esperando_direccion
            nuevo_estado_c = json.dumps({"estado": "esperando_direccion", "pedido": pedido_c})
            at_actualizar_estado(conv_cliente["id"], nuevo_estado_c)

            # 2. Actualizar pedido en Airtable → estado_pago = confirmado
            if pedido_c.get("nro_pedido"):
                at_confirmar_pago_pedido(pedido_c["nro_pedido"])

            # 3. Notificar al cliente
            total_c     = pedido_c.get("total", 0)
            sena_c      = pedido_c.get("sena_ars", round(total_c * 0.10, 2))
            saldo_c     = pedido_c.get("saldo_a_cobrar", round(total_c * 0.90, 2))
            detalle_c   = pedido_c.get("detalle", "")
            nro_c       = pedido_c.get("nro_pedido", "")
            msg_cliente = (
                f"✅ *¡Pago confirmado, {nombre_c}!*\n\n"
                f"📦 *Resumen de su pedido {nro_c}:*\n"
                f"{detalle_c}\n\n"
                f"💰 Total: ${total_c:,.0f} ARS\n"
                f"💳 Seña abonada: ${sena_c:,.0f} ARS\n"
                f"🏷️ Saldo a pagar en la entrega: ${saldo_c:,.0f} ARS\n\n"
                f"🏠 Por favor, indíquenos su *dirección de entrega completa* para coordinar el envío."
            )
            enviar_cliente(tel_cliente, msg_cliente)

            # 4. Ticket resumen para el dueño
            sena = pedido_c.get("total", 0) * 0.10
            return {
                "respuesta": (
                    f"✅ *Pago confirmado*\n\n"
                    f"👤 {nombre_c} ({tel_cliente})\n"
                    f"📋 {pedido_c.get('detalle', '')}\n"
                    f"💰 Total: ${pedido_c.get('total', 0):,.0f} ARS\n"
                    f"💳 Seña cobrada: ${sena:,.0f} ARS\n\n"
                    f"Se le solicitó la dirección al cliente. 🛵"
                ),
                "tipo_mensaje": "texto",
                "accion_ejecutada": "pago_confirmado_dueno",
            }
        # ── CONFIRMACIÓN DE ENTREGA POR WHATSAPP (solo el dueño) ──────────────
        if es_dueno and "entrega confirmada" in msg.lower():
            # Extraer número de pedido del mensaje: "entrega confirmada PED-XXXXX"
            partes = msg.upper().split()
            nro_pedido_entrega = next((p for p in partes if p.startswith("PED-")), None)
            if not nro_pedido_entrega:
                return {
                    "respuesta": "Indicá el número de pedido. Ej: *entrega confirmada PED-XXXXX*",
                    "tipo_mensaje": "texto",
                    "accion_ejecutada": None,
                }
            resultado_e = at_marcar_entregado(nro_pedido_entrega)
            if resultado_e.get("ok"):
                return {
                    "respuesta": f"✅ Pedido *{nro_pedido_entrega}* marcado como entregado. Saldo cobrado. 🛵",
                    "tipo_mensaje": "texto",
                    "accion_ejecutada": "entrega_confirmada",
                }
            else:
                return {
                    "respuesta": f"⚠️ No encontré el pedido {nro_pedido_entrega}. Verificá el número.",
                    "tipo_mensaje": "texto",
                    "accion_ejecutada": None,
                }
        # ── FIN CONFIRMACIÓN ──────────────────────────────────────────────────

        # ── MÁQUINA DE ESTADOS ────────────────────────────────────────────────
        # Interceptar mensajes cuando hay un pago pendiente en proceso

        if estado_actual == "esperando_comprobante":
            # El cliente envió el comprobante — acusar recibo y esperar que el dueño confirme
            pedido = pedido_pendiente
            nombre_cliente = pedido.get("nombre", tel)
            total_pedido   = pedido.get("total", 0)
            sena_monto     = total_pedido * 0.1
            detalle_pedido = pedido.get("detalle", "")
            nro            = pedido.get("nro_pedido", "")

            respuesta = "🧾 Hemos recibido su comprobante, espere un momento mientras confirmamos el pago..."
            nuevo_estado = json.dumps({"estado": "esperando_confirmacion", "pedido": pedido})
            historial.append({"role": "user",  "content": msg})
            historial.append({"role": "model", "content": respuesta})
            at_guardar_conversacion(tel, historial, record_id, estado=nuevo_estado)

            notificar_dueno(
                f"🧾 *Comprobante recibido*\n"
                f"👤 {nombre_cliente} ({tel})\n"
                f"📋 {detalle_pedido}\n"
                f"💰 Total: ${total_pedido:,.0f} ARS | Seña: ${sena_monto:,.0f} ARS\n\n"
                f"✅ Respondé *pago confirmado* para aprobar."
            )
            return {"respuesta": respuesta, "tipo_mensaje": "texto", "accion_ejecutada": "comprobante_recibido"}

        elif estado_actual == "esperando_confirmacion":
            # El dueño aún no confirmó, el cliente manda otro mensaje
            return {
                "respuesta": "⏳ Su comprobante está siendo verificado. En breve le confirmamos.",
                "tipo_mensaje": "texto",
                "accion_ejecutada": None,
            }

        elif estado_actual == "esperando_direccion":
            # El dueño confirmó el pago — el cliente acaba de mandar su dirección
            direccion = msg
            pedido = pedido_pendiente
            nro = pedido.get("nro_pedido", f"PED-{str(uuid.uuid4())[:5].upper()}")
            sena = pedido.get("total", 0) * 0.10

            detalle_con_dir = pedido.get("detalle", "") + f"\n🏠 Dirección: {direccion}"
            record_id = pedido.get("record_id")

            # Si tenemos el record_id, actualizar el registro existente (PATCH)
            if record_id:
                resultado = at_actualizar_pedido(record_id, {
                    "detalle":     detalle_con_dir,
                    "estado_pago": "confirmado",
                })
            else:
                resultado = at_crear_pedido({
                    "nombre":      pedido.get("nombre", ""),
                    "telefono":    tel,
                    "detalle":     detalle_con_dir,
                    "total":       pedido.get("total", 0),
                    "estado_pago": "confirmado",
                })
            
            try:
                if not record_id and resultado.get("ok"):
                    nro_nuevo = str(resultado["resp"]["records"][0]["fields"].get("ID Pedido", "N/A"))
                    nro = nro_nuevo
            except:
                pass


            if resultado.get("ok"):
                notificar_dueno(
                    f"🛵 *Pedido listo para preparar* #{nro}\n"
                    f"👤 {pedido.get('nombre', tel)}\n"
                    f"📋 {pedido.get('detalle', '')}\n"
                    f"💰 Total: ${pedido.get('total', 0):,.0f} ARS (seña cobrada: ${sena:,.0f})\n"
                    f"🏠 Dirección: {direccion}\n"
                    f"📞 {tel}"
                )
                ticket = (
                    f"✅ *¡Pedido confirmado y registrado!*\n\n"
                    f"🧾 N° *{nro}*\n"
                    f"📦 {pedido.get('detalle', '')}\n"
                    f"💰 Total: ${pedido.get('total', 0):,.0f} ARS\n"
                    f"💳 Seña abonada: ${sena:,.0f} ARS\n"
                    f"🏠 Entrega en: {direccion}\n"
                    f"⏰ Tiempo estimado: 45-60 minutos\n\n"
                    f"¡Muchas gracias por su pedido! Le avisamos cuando esté en camino. 🛵"
                )
                historial.append({"role": "user",  "content": msg})
                historial.append({"role": "model", "content": ticket})
                at_guardar_conversacion(tel, historial, record_id, estado="activo")
                return {"respuesta": ticket, "tipo_mensaje": "texto", "accion_ejecutada": "crear_pedido"}
            else:
                return {
                    "respuesta": "⚠️ No se pudo registrar su pedido. Por favor, contáctenos directamente.",
                    "tipo_mensaje": "texto",
                    "accion_ejecutada": None,
                }
        # ── FIN MÁQUINA DE ESTADOS ────────────────────────────────────────────

        # ── FALLBACK: comprobante recibido pero estado no sincronizado ────────
        # Activar si: (1) llegó una imagen, O (2) el último mensaje del bot pedía
        # el comprobante. Cubre desincronización de estado en Airtable.
        ultimo_bot_msg = next(
            (t["content"] for t in reversed(historial) if t.get("role") == "model"), ""
        )
        estado_pedia_comprobante = "comprobante" in ultimo_bot_msg.lower()
        es_imagen = msg == "[imagen enviada]"
        if (es_imagen or estado_pedia_comprobante) and estado_actual not in ("esperando_confirmacion", "esperando_direccion"):
            pedido_fallback = at_buscar_pedido_pendiente_tel(tel)
            if pedido_fallback:
                fields     = pedido_fallback.get("fields", {})
                nombre_fb  = fields.get("nombre_cliente", tel)
                total_fb   = fields.get("total_ars", 0)
                sena_fb    = fields.get("sena_ars", 0)
                detalle_fb = fields.get("detalle", "")
                nro_fb     = fields.get("nro_pedido", "")

                respuesta_fb = "🧾 Hemos recibido su comprobante, espere un momento mientras confirmamos el pago..."
                pedido_data_fb = {
                    "nombre":     nombre_fb,
                    "telefono":   tel,
                    "detalle":    detalle_fb,
                    "total":      total_fb,
                    "sena_ars":   sena_fb,
                    "nro_pedido": pedido_fallback["id"], # usar Record ID de AT
                    "record_id":  pedido_fallback["id"],
                }
                nuevo_estado_fb = json.dumps({"estado": "esperando_confirmacion", "pedido": pedido_data_fb})
                historial.append({"role": "user",  "content": msg})
                historial.append({"role": "model", "content": respuesta_fb})
                at_guardar_conversacion(tel, historial, record_id, estado=nuevo_estado_fb)
                notificar_dueno(
                    f"🧾 *Comprobante recibido*\n"
                    f"👤 {nombre_fb} ({tel})\n"
                    f"📋 {detalle_fb}\n"
                    f"💰 Total: ${total_fb:,.0f} ARS | Seña: ${sena_fb:,.0f} ARS\n\n"
                    f"✅ Respondé *pago confirmado* para aprobar."
                )
                return {"respuesta": respuesta_fb, "tipo_mensaje": "texto", "accion_ejecutada": "comprobante_recibido"}
        # ─────────────────────────────────────────────────────────────────────

        # ── IMAGEN SIN ESTADO RESUELTO ────────────────────────────────────────
        # Si llegamos aquí con una imagen (msg == "[imagen enviada]") es porque:
        # - Estado no era esperando_comprobante
        # - Fallback tampoco encontró pedido pendiente
        # Respuesta genérica para no dejar al cliente sin respuesta.
        if msg == "[imagen enviada]":
            return {
                "respuesta": "🧾 Recibimos tu imagen, pero no encontramos un pedido pendiente asociado a tu número. ¿Podés contarnos qué querés hacer?",
                "tipo_mensaje": "texto",
                "accion_ejecutada": None,
            }
        # ─────────────────────────────────────────────────────────────────────

        # ── BIENVENIDA HARDCODEADA (primer mensaje o historial vacío) ─────────
        SALUDOS = {"hola", "buenas", "buen día", "buenos días", "buenas tardes",
                   "buenas noches", "hey", "hi", "holis", "buenas!", "hola!", "ola"}
        msg_lower = msg.lower().strip().rstrip(".,!?")
        if not historial or msg_lower in SALUDOS:
            bienvenida = (
                f"*¡Bienvenido a {RESTAURANTE['nombre']}!* 🍖\n"
                f"¿En qué podemos ayudarte hoy?\n\n"
                f"1️⃣ Ver el Menú del día\n"
                f"2️⃣ Hacer una reserva\n"
                f"3️⃣ Cancelar una reserva\n"
                f"4️⃣ Modificar una reserva\n"
                f"5️⃣ Delivery (hacer pedido)"
            )
            historial.append({"role": "user",  "content": msg})
            historial.append({"role": "model", "content": bienvenida})
            at_guardar_conversacion(tel, historial, record_id)
            return {"respuesta": bienvenida, "tipo_mensaje": "texto", "accion_ejecutada": None}
        # ─────────────────────────────────────────────────────────────────────

        # Convertir historial al formato que espera Gemini
        history_gemini = []
        for turno in historial:
            if turno.get("role") in ["user", "model"]:
                history_gemini.append({
                    "role": turno["role"],
                    "parts": [{"text": turno["content"]}],
                })

        # Inyectar reservas actuales en el system prompt (contexto real de disponibilidad)
        reservas_ctx = at_get_reservas_futuras()
        modelo_con_ctx = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            system_instruction=(
                SYSTEM_PROMPT
                + "\n\n---\n## RESERVAS ACTUALES EN EL SISTEMA (datos reales de Airtable)\n"
                + reservas_ctx
                + """

⚠️ REGLAS CRÍTICAS PARA INTERPRETAR ESTAS RESERVAS:
1. Cada línea es una franja horaria OCUPADA. Todas las demás franjas dentro del horario de atención están LIBRES.
2. El restaurante acepta reservas de almuerzo (12:00 a 16:00) y cena (20:00 a 23:00). Si un horario no aparece en la lista, está disponible.
3. Ver "21:00 ocupado" NO significa que 22:00 o 23:00 estén ocupados — son franjas independientes.
4. NUNCA inventes que un horario está completo si no aparece en esta lista.
5. Si la lista dice "No hay reservas activas próximas", entonces TODOS los horarios están disponibles.
"""
            ),
        )

        # Crear chat con historial
        chat = modelo_con_ctx.start_chat(history=history_gemini)

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
                accion_raw = accion_raw.replace("```json", "").replace("```", "").strip()
                accion = json.loads(accion_raw)
            except Exception as e:
                print(f"[Acción] Error parseando: {e}, raw={partes[1][:100]}")

        # Ejecutar acción si existe y usar su resultado real
        texto_final = texto_respuesta
        nuevo_estado_accion = "activo"
        if accion:
            resultado_accion = ejecutar_accion(accion, tel)
            nuevo_estado_accion = resultado_accion.get("nuevo_estado", "activo")
            if resultado_accion.get("mensaje_confirmacion"):
                texto_final = resultado_accion["mensaje_confirmacion"]
            elif not resultado_accion.get("ok"):
                texto_final = resultado_accion.get("mensaje_error", "⚠️ Ocurrió un error al procesar su solicitud.")

        # Actualizar historial conservando el estado correcto
        historial.append({"role": "user",  "content": msg})
        historial.append({"role": "model", "content": texto_final})
        at_guardar_conversacion(tel, historial, record_id, estado=nuevo_estado_accion)

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
# ENDPOINT DE CONFIRMACIÓN DE PAGO (dueño)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/confirmar-pago/{telefono}", summary="Dueño: Confirmar pago del cliente y solicitar dirección")
async def confirmar_pago(telefono: str):
    conv = at_get_conversacion(telefono)
    if not conv:
        return {"ok": False, "error": f"No se encontró conversación para {telefono}"}

    estado_raw = conv["fields"].get("estado_actual", "activo")
    try:
        estado_data = json.loads(estado_raw)
    except Exception:
        return {"ok": False, "error": f"Estado actual: '{estado_raw}' — no hay comprobante pendiente"}

    if estado_data.get("estado") != "esperando_confirmacion":
        return {"ok": False, "error": f"Estado actual: '{estado_data.get('estado')}' — no hay comprobante esperando confirmación"}

    pedido_pendiente = estado_data.get("pedido", {})
    nombre = pedido_pendiente.get("nombre", "")

    # Actualizar estado a esperando_direccion
    nuevo_estado = json.dumps({"estado": "esperando_direccion", "pedido": pedido_pendiente})
    at_actualizar_estado(conv["id"], nuevo_estado)

    # Enviar mensaje al cliente solicitando la dirección
    saludo = f"¡Hola, {nombre}! " if nombre else ""
    msg_cliente = (
        f"✅ *¡Pago verificado!* {saludo}\n\n"
        f"Su seña fue confirmada exitosamente. 🎉\n\n"
        f"Por favor, indíquenos su *dirección de entrega completa* para procesar su pedido. 🏠"
    )
    enviar_cliente(telefono, msg_cliente)

    return {
        "ok": True,
        "mensaje": f"✅ Pago confirmado para {telefono}. Mensaje enviado al cliente solicitando dirección.",
        "pedido": pedido_pendiente,
    }

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS DE DEBUG (quitar en producción)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/debug/test-whisper", summary="Debug: Probar transcripción de audio")
async def debug_test_whisper(payload: dict):
    """
    Diagnóstico paso a paso de la transcripción.
    Mandá: {"audio_url": "https://..."} o {"audio_base64": "data:audio/..."}
    """
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    audio_url    = payload.get("audio_url", "")
    audio_base64 = payload.get("audio_base64", "")
    pasos = {}

    # Paso 0: verificar API key
    pasos["openai_api_key"] = f"✅ ({len(OPENAI_API_KEY)} chars)" if OPENAI_API_KEY else "❌ NO configurada en Render"
    if not OPENAI_API_KEY:
        return {"ok": False, "pasos": pasos, "error": "Falta OPENAI_API_KEY en las variables de entorno de Render"}

    MIME_EXT = {
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mpga": ".mp3",
        "audio/ogg": ".ogg",  "audio/opus": ".ogg",
        "audio/wav": ".wav",  "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",  "audio/m4a": ".m4a",
        "audio/webm": ".webm", "audio/flac": ".flac",
    }
    def _ext(ct: str, url: str) -> str:
        for mime, ext in MIME_EXT.items():
            if mime in ct.lower():
                return ext
        for ext in [".mp3", ".ogg", ".wav", ".m4a", ".webm", ".flac"]:
            if url.lower().endswith(ext):
                return ext
        return ".ogg"

    audio_bytes  = None
    content_type = ""

    # Paso 1: base64
    if audio_base64:
        try:
            header, data = (audio_base64.split(",", 1) if "," in audio_base64 else ("", audio_base64))
            content_type = header
            audio_bytes  = b64.b64decode(data)
            pasos["metodo_1_base64"] = f"✅ {len(audio_bytes)} bytes"
        except Exception as e:
            pasos["metodo_1_base64"] = f"❌ {e}"

    # Paso 2: URL directa
    if audio_url and not audio_bytes:
        try:
            r = requests.get(audio_url, timeout=15)
            ct = r.headers.get("Content-Type", "")
            pasos["metodo_2_url_directa"] = f"HTTP {r.status_code} — {len(r.content)} bytes — CT: {ct}"
            if r.status_code == 200 and len(r.content) > 100:
                audio_bytes  = r.content
                content_type = ct
                pasos["metodo_2_url_directa"] += " ✅"
            else:
                pasos["metodo_2_url_directa"] += " ❌"
        except Exception as e:
            pasos["metodo_2_url_directa"] = f"❌ {e}"

    # Paso 3: URL con auth
    if audio_url and not audio_bytes:
        evo_key = os.environ.get("EVOLUTION_API_KEY", "")
        try:
            r = requests.get(audio_url, headers={"apikey": evo_key}, timeout=15)
            ct = r.headers.get("Content-Type", "")
            pasos["metodo_3_url_auth"] = f"HTTP {r.status_code} — {len(r.content)} bytes — CT: {ct}"
            if r.status_code == 200 and len(r.content) > 100:
                audio_bytes  = r.content
                content_type = ct
                pasos["metodo_3_url_auth"] += " ✅"
            else:
                pasos["metodo_3_url_auth"] += " ❌"
        except Exception as e:
            pasos["metodo_3_url_auth"] = f"❌ {e}"

    if not audio_bytes:
        return {"ok": False, "pasos": pasos, "error": "Ningún método obtuvo el audio"}

    # Paso 4: Whisper (con extensión correcta)
    ext = _ext(content_type, audio_url)
    pasos["extension_detectada"] = ext
    try:
        cliente_openai = openai.OpenAI(api_key=OPENAI_API_KEY)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as f:
            result = cliente_openai.audio.transcriptions.create(model="whisper-1", file=f, language="es")
        os.unlink(tmp_path)
        pasos["whisper"] = "✅ OK"
        return {"ok": True, "transcripcion": result.text.strip(), "pasos": pasos}
    except Exception as e:
        pasos["whisper"] = f"❌ {e}"
        return {"ok": False, "pasos": pasos, "error": str(e)}

@router.get("/debug/airtable", summary="Debug: Estado de Airtable")
def debug_airtable():
    evo_url      = os.environ.get("EVOLUTION_API_URL", "")
    evo_instance = os.environ.get("EVOLUTION_INSTANCE", "")
    evo_key      = os.environ.get("EVOLUTION_API_KEY", "")
    openai_key   = os.environ.get("OPENAI_API_KEY", "")
    resultado = {
        "AIRTABLE_API_KEY":  f"✅ ({len(AIRTABLE_API_KEY)} chars)" if AIRTABLE_API_KEY else "❌ vacía",
        "AIRTABLE_BASE_ID":  AIRTABLE_BASE_ID,
        "GEMINI_API_KEY":    f"✅ ({len(GEMINI_API_KEY)} chars)" if GEMINI_API_KEY else "❌ vacía",
        "OPENAI_API_KEY":    f"✅ ({len(openai_key)} chars)" if openai_key else "❌ NO configurada",
        "EVOLUTION_API_URL": evo_url if evo_url else "❌ NO configurada",
        "EVOLUTION_INSTANCE": evo_instance if evo_instance else "❌ NO configurada",
        "EVOLUTION_API_KEY": f"✅ ({len(evo_key)} chars)" if evo_key else "❌ NO configurada",
    }
    try:
        r = requests.get(f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/conversaciones_activas?maxRecords=1", headers=AT_HEADERS())
        resultado["conversaciones_status"] = r.status_code
    except Exception as e:
        resultado["error"] = str(e)
    return resultado

@router.get("/debug/schema", summary="Debug: Ver esquema real de AT Airtable")
def debug_schema():
    try:
        r1 = requests.get(f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas?maxRecords=1", headers=AT_HEADERS())
        r2 = requests.get(f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/pedidos?maxRecords=1", headers=AT_HEADERS())
        r3 = requests.get(f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Clientes?maxRecords=1", headers=AT_HEADERS())
        return {
            "Reservas": r1.json(),
            "Pedidos": r2.json(),
            "Clientes": r3.json()
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/test-reserva", summary="Debug: Crear reserva de prueba")
def debug_test_reserva():
    resultado = at_crear_reserva({
        "nombre": "TEST_DEBUG", "telefono": "+5491100000000",
        "fecha_iso": "2026-03-08", "hora": "21:00",
        "personas": 2, "tipo_reserva": "simple",
    })
    return resultado

@router.get("/debug/test-pedido", summary="Debug: Crear pedido de prueba en Airtable")
def debug_test_pedido():
    """Intenta crear un pedido de prueba para verificar los campos de Airtable."""
    resultado = at_crear_pedido({
        "nombre":      "TEST_DEBUG",
        "telefono":    "+5491100000000",
        "detalle":     "Prueba de pedido — Asado de Tira: 1\n🏠 Dirección: Calle Test 123",
        "total":       6800,
        "estado_pago": "pendiente",
    })
    return resultado

@router.get("/debug/estado/{telefono}", summary="Debug: Ver estado de pago pendiente")
def debug_estado(telefono: str):
    conv = at_get_conversacion(telefono)
    if not conv:
        return {"estado": "sin_conversacion"}
    estado_raw = conv["fields"].get("estado_actual", "activo")
    try:
        estado_data = json.loads(estado_raw)
        return {"estado": estado_data.get("estado"), "pedido": estado_data.get("pedido")}
    except Exception:
        return {"estado": estado_raw}

@router.post("/debug/test-evo-getbase64", summary="Debug: Probar Evolution API getBase64FromMediaMessage")
def debug_evo_getbase64(payload: dict):
    """Manda audio_msg_raw directo a Evolution API y devuelve respuesta cruda."""
    evo_url      = os.environ.get("EVOLUTION_API_URL", "")
    evo_instance = os.environ.get("EVOLUTION_INSTANCE", "")
    evo_key      = os.environ.get("EVOLUTION_API_KEY", "")

    if not all([evo_url, evo_instance, evo_key]):
        return {"ok": False, "error": "Faltan EVOLUTION_* vars", "evo_url": evo_url, "evo_instance": evo_instance}

    audio_msg_raw = payload.get("audio_msg_raw", "")
    try:
        msg_data = json.loads(audio_msg_raw)
    except Exception as e:
        return {"ok": False, "error": f"JSON inválido: {e}"}

    instance_encoded = quote(evo_instance)
    url = f"{evo_url}/chat/getBase64FromMediaMessage/{instance_encoded}"
    body = {"message": msg_data, "convertToMp4": False}

    try:
        resp = requests.post(url, json=body, headers={"apikey": evo_key, "Content-Type": "application/json"}, timeout=30)
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = resp.text[:500]
        return {
            "ok": resp.status_code == 200,
            "status": resp.status_code,
            "url_llamado": url,
            "respuesta": resp_json,
            "tiene_base64": isinstance(resp_json, dict) and bool(resp_json.get("base64")),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "url_llamado": url}


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
