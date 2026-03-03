import os
import json
import uuid
import requests
from datetime import date
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
3. Fecha — Aceptá la fecha que dé el cliente sin cuestionar el día de la semana. La ÚNICA verificación es si el día cae en lunes (cerrado): "Los lunes permanecemos cerrados, ¿le parece bien el martes o el domingo?" Solo si el cliente menciona explícitamente un nombre de día junto a una fecha y hay una contradicción obvia (ej: "el sábado 9" pero el 9 es lunes), corregilo con amabilidad.
4. Horario (almuerzo ~12-16hs o cena ~20-00hs)
5. Confirmar todos los datos antes de guardar

Cuando tengas TODOS → usá ACCION crear_reserva con tipo_reserva "simple"

---

## OPCIÓN 3 — CANCELAR UNA RESERVA
Preguntá:
1. Nombre de la reserva
2. Fecha y hora de la reserva que quiere cancelar

Luego confirmá: "¿Confirma la cancelación de la reserva de [Nombre] para el [Fecha] a las [Hora]?"
Cuando confirme → ACCION: {{"tipo": "cancelar_reserva", "nombre": "...", "fecha_legible": "...", "hora": "..."}}

---

## OPCIÓN 4 — MODIFICAR UNA RESERVA
Preguntá:
1. Nombre de la reserva original
2. Qué quiere cambiar (fecha, hora, cantidad de personas)
3. Los nuevos datos

Cuando tengas todo → ACCION: {{"tipo": "modificar_reserva", "nombre": "...", "fecha_iso": "YYYY-MM-DD", "fecha_legible": "...", "hora": "...", "personas": N, "nota": "Modificación de reserva anterior"}}

---

## OPCIÓN 5 — DELIVERY CON SEÑA
Es un pedido para llevar donde se cobra una seña del 10% para confirmar el pedido.
Recopilá en orden:
1. Nombre completo
2. Inmediatamente después de recibir el nombre, mostrá las categorías del menú Y aclará el 10% de seña en el MISMO mensaje. Ejemplo:
   "Perfecto, [Nombre]. Nuestro pedido con seña requiere un adelanto del *10% del total* para confirmar. 🛵
   ¿Qué le gustaría pedir? Nuestras categorías:
   1️⃣ Platos Principales 🥩
   2️⃣ Entradas 🥗
   3️⃣ Postres 🍰
   4️⃣ Cafetería ☕
   5️⃣ Bebidas 🍷"
3. Tomá su pedido (platos + cantidades). Cada vez que agregue un ítem confirmalo y preguntá "¿Desea agregar algo más?". NUNCA calculés el total hasta que el cliente diga explícitamente que terminó.
4. Cuando el cliente diga que terminó ("listo", "con eso", "nada más", "estamos", etc.), en ese MISMO mensaje usá EXACTAMENTE esta estructura (sin omitir ninguna línea):

   📦 *Su pedido:*
   • [ítem 1] — $[precio]
   • [ítem 2] — $[precio]
   *Total: $[TOTAL] ARS*
   💳 *Seña requerida (10%): $[SEÑA] ARS*

   Puede abonar la seña por transferencia o MercadoPago al alias: *{RESTAURANTE['alias_pago']}*

   📸 *Una vez realizada la transferencia, envíenos la captura del comprobante para confirmar su pedido.*

   (inmediatamente después de ese bloque, en el mismo mensaje:)
ACCION: {{"tipo": "solicitar_comprobante", "nombre": "[nombre del cliente]", "detalle": "[platos y cantidades]", "total": N}}

⚠️ OBLIGATORIO: el mensaje SIEMPRE debe terminar con "envíenos la captura del comprobante" — NUNCA omitir esa línea.
⚠️ En Opción 5, usa SIEMPRE ACCION solicitar_comprobante — NUNCA crear_pedido.
⚠️ NO preguntes la dirección en este paso — el sistema la solicita automáticamente DESPUÉS de verificar el pago.
⚠️ Después del ACCION solicitar_comprobante, NO agregues más preguntas ni instrucciones.

---

## DELIVERY 🛵 (sin seña — distinto a Opción 5)
Este flujo aplica cuando el cliente menciona "delivery" espontáneamente o al ver el menú. NO tiene seña.
⚠️ Si el cliente ya eligió uno o más platos antes de decir "delivery", NO volvás a mostrar las categorías — ya tenés esos platos, preguntá si quiere agregar algo más.

1. Si ya tiene platos elegidos: "Anotado, [plato/s]. ¿Desea agregar algo más a su pedido?"
   Si no tiene nada elegido aún: mostrá las categorías y tomá el pedido (podés acumular ítems turno a turno)
2. Pedí el nombre completo si no lo tenés todavía
3. Cada vez que el cliente agregue un ítem, confirmalo y SIEMPRE preguntá "¿Desea agregar algo más?" — NUNCA calculés el total ni la seña solo porque agregó un plato. Esperá confirmación explícita de que terminó.
4. SOLO cuando el cliente diga que terminó (dice "listo", "con eso", "eso es todo", "nada más", "no gracias", "estamos", etc.), en ese MISMO mensaje hacé todo junto:
   a. Mostrá el desglose del pedido con precios unitarios
   b. Calculá y mostrá el TOTAL
   c. Calculá el 10% del total como seña y mostralo
   d. Pedí la dirección de entrega
   Ejemplo:
   "📦 *Su pedido:*
   • Bondiola Braseada — $5.900
   • Vino Malbec (copa) — $2.200
   *Total: $8.100 ARS*
   💳 Seña requerida (10%): *$810 ARS* al alias *donalberto.parrilla*

   ¿Cuál es su dirección de entrega?"
4. Cuando el cliente dé la dirección → en ese MISMO mensaje ejecutá ACCION SIN pedir confirmación adicional:
ACCION: {{"tipo": "crear_pedido", "nombre": "[nombre del cliente]", "detalle": "[platos y cantidades]", "total": N, "direccion": "...", "nota": "Delivery"}}

⚠️ NUNCA digas "procederé a calcular" ni "tu pedido está siendo procesado" sin incluir el ACCION en el mismo mensaje.
⚠️ El ACCION debe ir en el MISMO mensaje en que recibís la dirección — nunca en un turno posterior.

---

# REGLAS DE CONVERSACIÓN

## 🔒 REGLA CRÍTICA — CONTEXTO DE FLUJO ACTIVO
Esta es la regla más importante. Debes leerla ANTES de interpretar cualquier mensaje del cliente.

**Analiza el historial de conversación para determinar en qué flujo estás:**

- Si en el historial reciente mostraste el menú de CATEGORÍAS (1=Platos Principales, 2=Entradas, 3=Postres, 4=Cafetería, 5=Bebidas) → estás en flujo de MENÚ/DELIVERY. Un número del cliente es una CATEGORÍA, NO una opción del menú principal.
- Si en el historial reciente pediste nombre/personas/fecha/hora → estás en flujo de RESERVA. Interpreta el mensaje en ese contexto.
- Si en el historial reciente pediste una dirección de entrega → estás en flujo de DELIVERY. Interpreta el mensaje como dirección.
- Si en el historial reciente pediste nombre del titular de una reserva para cancelar → estás en flujo de CANCELACIÓN.

**REGLA ABSOLUTA:** Cuando estás dentro de un flujo activo (delivery, reserva, cancelación, modificación), los números que escribe el cliente se refieren al SUB-MENÚ ACTUAL, NUNCA al menú principal (1=Ver menú, 2=Reserva, etc.).

**Solo se sale de un flujo activo cuando el cliente escribe:**
- `0` → volver al menú principal (interrumpe el flujo actual)
- `00` → reiniciar desde el principio

Si el cliente escribe cualquier otro número dentro de un flujo activo → interpretar según el contexto del flujo, NO como opción del menú principal.

Ejemplo CORRECTO:
- Contexto: mostraste las 5 categorías en flujo de delivery
- Cliente escribe: "2"
- Respuesta CORRECTA: mostrar los ítems de "Entradas" (2=Entradas)
- Respuesta INCORRECTA: ❌ "Perfecto, ¿para qué nombre hago la reserva?" (esto sería error grave)

## ✅ SÍ DEBES:
- Comenzar SIEMPRE con el Menú Principal si no hay contexto previo
- Confirmar cada dato antes de ejecutar: "¿Confirma: reserva para [nombre], [N] personas, [fecha] a las [hora]?"
- Ofrecer alternativas: "Los sábados tienen mucha demanda, ¿le interesa a las 20 hs?"
- Recordar el historial — si ya dio su nombre, no volver a pedírselo
- Mencionar las especialidades: el Asado de Tira y la Bondiola Braseada son los más pedidos

## ❌ NO DEBES:
- Usar jerga: JAMÁS "che", "vos", "dale", "genial", "bárbaro", "re", "copado"
- Inventar platos, precios o información no autorizada
- Confirmar reserva sin tener los 4 datos: nombre + personas + fecha + horario
- Aceptar reservas para lunes (cerrado)
- Mostrar todos los platos de una sola vez — siempre: categorías primero, luego ítems
- **Abandonar un flujo activo** porque el cliente escribió un número — siempre verificar el contexto primero

## ⚠️ CASOS ESPECIALES:
- **Grupos 10+ personas:** "Para grupos grandes reservamos el salón privado, lo coordino con el equipo." → notificar_dueno
- **Alergias:** Anotarlo como especificación en la reserva
- **Lunes:** "Los lunes permanecemos cerrados. Atendemos martes a domingo desde las 12 hs."
- **Facturas:** "Las facturas se emiten en el local al momento del pago."

# FORMATO DE RESPUESTAS
- WhatsApp: usá *negrita* con asteriscos
- Máximo 5-6 líneas para respuestas normales
- El menú siempre en 2 pasos: categorías → ítems al elegir

# ACCIONES DISPONIBLES
Incluir AL FINAL del mensaje. Formatos exactos:

Reserva nueva/modificación:
ACCION: {{"tipo": "crear_reserva", "nombre": "...", "personas": N, "fecha_iso": "YYYY-MM-DD", "fecha_legible": "sábado 8 de marzo", "hora": "21:00", "tipo_reserva": "simple", "nota": "..."}}

Cancelación:
ACCION: {{"tipo": "cancelar_reserva", "nombre": "...", "fecha_legible": "...", "hora": "..."}}

Pedido delivery:
ACCION: {{"tipo": "crear_pedido", "detalle": "...", "total": N, "direccion": "...", "nota": "Delivery"}}

Notificar al dueño:
ACCION: {{"tipo": "notificar_dueno", "mensaje": "..."}}

**CRÍTICO:** Cuando uses ACCION crear_reserva o crear_pedido, tu mensaje debe decir SOLO "Procesando...". El sistema confirma el resultado real al cliente. JAMÁS escribas "reserva confirmada" o "pedido registrado" vos mismo."""

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

def at_crear_reserva(datos: dict) -> dict:
    """Guarda la reserva en la tabla Reservas."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        # Sanitizar personas — asegurar que sea int
        try:
            personas_num = int(str(datos.get("personas", 1)).strip().strip('"'))
        except Exception:
            personas_num = 1

        campos = {
            "Nombre":      str(datos.get("nombre", "")).strip(),
            "telefono":    str(datos.get("telefono", "")).strip(),
            "Fecha":       str(datos.get("fecha_iso", "")).strip()[:10],
            "Hora":        str(datos.get("hora", "")).strip(),
            "Personas":    personas_num,
            "nro_reserva": str(datos.get("nro_reserva", "")).strip(),
            "Especificaciones": str(datos.get("especificaciones", datos.get("nota", ""))).strip(),
        }
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
        campos = {
            "nombre_cliente":   datos.get("nombre", ""),
            "telefono_cliente": datos.get("telefono", ""),
            "detalle":          datos.get("detalle", ""),
            "total_ars":        float(datos.get("total", 0)),
            "nro_pedido":       datos.get("nro_pedido", ""),
            "estado_pago":      "pendiente",
        }
        print(f"[AT] Enviando pedido: {campos}")
        r = requests.post(url, headers=AT_HEADERS(), json={"records": [{"fields": campos}]})
        resp = r.json()
        print(f"[AT] Pedido status={r.status_code} resp={resp}")
        return {"ok": r.status_code == 200, "resp": resp}
    except Exception as e:
        print(f"[AT] Error crear_pedido: {e}")
        return {"ok": False, "error": str(e)}

def at_buscar_reserva(nombre: str, telefono: str) -> dict | None:
    """Busca la reserva más reciente por nombre y teléfono."""
    try:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
        formula = f"AND({{Nombre}}='{nombre}', {{telefono}}='{telefono}')"
        r = requests.get(url, headers=AT_HEADERS(), params={
            "filterByFormula": formula,
            "sort[0][field]": "Fecha",
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

    elif tipo == "cancelar_reserva":
        nombre = accion.get("nombre", "")
        fecha  = accion.get("fecha_legible", accion.get("fecha_iso", ""))
        hora   = accion.get("hora", "")

        # Buscar la reserva existente solo por teléfono (evita problemas de case-sensitivity en nombre)
        try:
            url_buscar = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Reservas"
            r_buscar = requests.get(url_buscar, headers=AT_HEADERS(), params={
                "filterByFormula": f"{{telefono}}='{tel}'",
                "sort[0][field]": "Fecha",
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
            resultado_cancel = at_actualizar_reserva(record_id, {"Especificaciones": nota_cancel})
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
            "Fecha":  str(accion.get("fecha_iso", "")).strip()[:10],
            "Hora":   str(accion.get("hora", "")).strip(),
            "Personas": personas_num,
            "Especificaciones": accion.get("nota", "Reserva modificada por el cliente"),
        }
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

        pedido_data = {
            "nombre":    nombre,
            "telefono":  tel,
            "detalle":   detalle,
            "total":     total,
            "nro_pedido": nro,
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

        # Cargar conversación desde Airtable
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

        # ── MÁQUINA DE ESTADOS ────────────────────────────────────────────────
        # Interceptar mensajes cuando hay un pago pendiente en proceso

        if estado_actual == "esperando_comprobante":
            # El cliente acaba de enviar su comprobante (imagen o texto)
            nuevo_estado = json.dumps({"estado": "esperando_confirmacion", "pedido": pedido_pendiente})
            respuesta = "✅ *Comprobante recibido.* Estamos verificando el pago y le confirmaremos en breve. 🙏"
            historial.append({"role": "user",  "content": msg})
            historial.append({"role": "model", "content": respuesta})
            at_guardar_conversacion(tel, historial, record_id, estado=nuevo_estado)

            # Notificar al dueño con link de confirmación
            base_url = os.environ.get("BASE_URL", "https://system-ia-agentes.onrender.com")
            link = f"{base_url}/gastronomico/confirmar-pago/{tel}"
            nombre_cliente = pedido_pendiente.get("nombre", tel)
            notificar_dueno(
                f"🧾 *Comprobante recibido*\n"
                f"👤 Cliente: {nombre_cliente}\n"
                f"📋 Pedido: {pedido_pendiente.get('detalle', '')}\n"
                f"💰 Total: ${pedido_pendiente.get('total', 0):,.0f} ARS\n"
                f"💳 Seña: ${pedido_pendiente.get('total', 0) * 0.1:,.0f} ARS\n"
                f"📞 Tel: {tel}\n\n"
                f"✅ Para confirmar el pago:\n{link}"
            )
            return {"respuesta": respuesta, "tipo_mensaje": "texto", "accion_ejecutada": "comprobante_recibido"}

        elif estado_actual == "esperando_confirmacion":
            # El dueño aún no confirmó, el cliente manda otro mensaje
            return {
                "respuesta": "⏳ Su comprobante está siendo verificado. En breve le confirmamos y procesamos su pedido.",
                "tipo_mensaje": "texto",
                "accion_ejecutada": None,
            }

        elif estado_actual == "esperando_direccion":
            # El dueño confirmó el pago — el cliente acaba de mandar su dirección
            direccion = msg
            pedido = pedido_pendiente
            nro = pedido.get("nro_pedido", f"PED-{str(uuid.uuid4())[:5].upper()}")
            sena = pedido.get("total", 0) * 0.10

            resultado = at_crear_pedido({
                "nombre":    pedido.get("nombre", ""),
                "telefono":  tel,
                "detalle":   pedido.get("detalle", ""),
                "total":     pedido.get("total", 0),
                "nro_pedido": nro,
            })

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
