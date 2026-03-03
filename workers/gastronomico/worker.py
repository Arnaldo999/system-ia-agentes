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
2. Los platos que desea pedir (podés ir acumulando ítems turno a turno)
3. Cuando el cliente termina de pedir, en ese MISMO mensaje:
   a. Mostrá el desglose del pedido con precios
   b. Mostrá el total
   c. Calculá el 10% del total como seña
   d. Informá: "Para confirmar su pedido, le pedimos una seña de $[MONTO] ARS (10% del total de $[TOTAL])."
   e. Pedí transferencia al alias: *{RESTAURANTE['alias_pago']}* (MercadoPago/Transferencia)
   f. Pedí que manden la captura del comprobante
4. Cuando indiquen que enviaron el comprobante → pedí la dirección de entrega
5. Con dirección confirmada → ejecutá:
ACCION: {{"tipo": "crear_pedido", "detalle": "[platos y cantidades]", "total": N, "direccion": "...", "nota": "Delivery con seña - Pendiente verificación de comprobante"}}
ACCION: {{"tipo": "notificar_dueno", "mensaje": "🛵 Nuevo delivery con seña de [Nombre] — Total: $[TOTAL]. Seña: $[MONTO]. Dirección: [dir]. Verificar comprobante."}}

---

## DELIVERY 🛵
Si el cliente menciona delivery en cualquier momento:
1. Mostrá las categorías del menú y tomá su pedido (platos + cantidades). Podés ir acumulando ítems turno a turno.
2. En cuanto el cliente indique que terminó de pedir (dice "listo", "con eso", "eso es todo", "nada más", etc.), en ese MISMO mensaje hacé las tres cosas juntas sin esperar otro turno:
   a. Mostrá el desglose del pedido con precios unitarios
   b. Calculá y mostrá el TOTAL sumando todos los ítems
   c. Pedí la dirección de entrega
   Ejemplo: "📦 *Resumen de su pedido:*\n• Empanadas Tucumanas x12 — $32.400\n• Flan Casero — $1.500\n*Total: $33.900 ARS*\n\n¿Cuál es su dirección de entrega?"
3. Cuando el cliente dé la dirección → ejecutá ACCION inmediatamente:
ACCION: {{"tipo": "crear_pedido", "detalle": "[platos y cantidades]", "total": N, "direccion": "...", "nota": "Delivery"}}

⚠️ NUNCA digas "procederé a calcular" y dejes el cálculo para el próximo turno. Calculá y mostrá el total en el mismo mensaje en que el cliente termina de pedir.

---

# REGLAS DE CONVERSACIÓN

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
