"""
DEMO 2 — PLAN PROFESIONAL: Reservas con Seña Automática + API Meta Oficial
===========================================================================
Simula el flujo de un cliente que quiere hacer una reserva con seña vía
MercadoPago/Stripe y recibe la confirmación con N° de mesa/reserva.

ENTORNO: Pruebas locales — gemini/gemini-2.5-flash
NO REQUIERE: WhatsApp real, MercadoPago activo, API Meta real.
SIGUIENTE PASO: Cuando este demo funcione, se convierte en el endpoint
                POST /reserva/profesional en FastAPI.
"""

import os
import json
import uuid
from dotenv import load_dotenv
from crewai import Agent, Task, Crew

# ─────────────────────────────────────────────
# 1. ENTORNO
# ─────────────────────────────────────────────
load_dotenv()

if not os.environ.get("GEMINI_API_KEY"):
    print("⚠️ No encontré GEMINI_API_KEY en el archivo .env.")
    exit(1)

MODELO = "gemini/gemini-2.5-flash-lite"

# ─────────────────────────────────────────────
# 2. DATOS DE ENTRADA (Simulan el payload de n8n desde Meta/WhatsApp Cloud API)
# ─────────────────────────────────────────────
DATOS_RESTAURANTE = {
    "nombre_local": "Sento Sushi Bar",
    "alias_pago": "sushibar.sento",
    "pasarela": "MercadoPago",
    "monto_sena_porcentaje": 30,   # 30% del total como seña
    "precio_promedio_cubierto": 5000,  # ARS por persona
    "horario_atencion": "Miércoles a Domingo, 19hs a 00hs",
    "reservas_disponibles": ["Mesa 3", "Mesa 5", "Mesa 8", "Mesa 12"]
}

# Payload simulado de WhatsApp Cloud API (Meta) — lo que n8n recibiría via Webhook
MENSAJE_CLIENTE = {
    "nombre": "Valentina",
    "telefono": "+54911XXXXXXXX",
    "mensaje": "Buenas! Quiero reservar para 6 personas este viernes 7 de marzo a las 20:30hs. Tienen mesa disponible?"
}

print("─" * 60)
print(f"🍣  DEMO PROFESIONAL — {DATOS_RESTAURANTE['nombre_local']}")
print("─" * 60)
print(f"📱 Mensaje entrante de {MENSAJE_CLIENTE['nombre']}: «{MENSAJE_CLIENTE['mensaje']}»")
print("─" * 60)

# ─────────────────────────────────────────────
# 3. SIMULACIÓN DE PAGO (MercadoPago/Stripe — esto en producción llamaría a la API real)
# ─────────────────────────────────────────────
total_estimado = DATOS_RESTAURANTE["precio_promedio_cubierto"] * 6  # 6 personas
monto_sena = int(total_estimado * DATOS_RESTAURANTE["monto_sena_porcentaje"] / 100)
nro_reserva = f"RSV-{str(uuid.uuid4())[:6].upper()}"
mesa_asignada = DATOS_RESTAURANTE["reservas_disponibles"][0]
link_pago_simulado = f"https://mp.com/checkout/v1/redirect?pref_id={nro_reserva}"

# ─────────────────────────────────────────────
# 4. AGENTES
# ─────────────────────────────────────────────

recepcionista_pro = Agent(
    role="Recepcionista Digital Premium (API Meta)",
    goal=(
        "Verificar que el mensaje del cliente tenga todos los datos de reserva "
        "(nombre, personas, fecha, horario) y confirmar disponibilidad consultando la lista de mesas. "
        "Operar con el nivel de calidad de WhatsApp Business API Oficial."
    ),
    backstory=(
        f"Eres el asistente digital del restaurante '{DATOS_RESTAURANTE['nombre_local']}'. "
        f"Horario de atención: {DATOS_RESTAURANTE['horario_atencion']}. "
        f"Mesas disponibles hoy: {', '.join(DATOS_RESTAURANTE['reservas_disponibles'])}. "
        "Hablas de forma sofisticada, breve y profesional. Español neutro con elegancia."
    ),
    llm=MODELO,
    verbose=True
)

operador_pago = Agent(
    role="Operador de Cobro de Señas Automático",
    goal=(
        "Calcular el monto de la seña, generar la instrucción de pago clara para el cliente "
        "y preparar el mensaje con el link de pago y los datos de la reserva confirmada."
    ),
    backstory=(
        "Eres el sistema de backend de pagos del restaurante. "
        f"Tu trabajo es procesar señas via {DATOS_RESTAURANTE['pasarela']} por el {DATOS_RESTAURANTE['monto_sena_porcentaje']}% del total. "
        f"El precio por cubierto es ${DATOS_RESTAURANTE['precio_promedio_cubierto']} ARS. "
        "Una vez que el cliente paga, el sistema asigna automáticamente el N° de mesa confirmada."
    ),
    llm=MODELO,
    verbose=True
)

notificador_pro = Agent(
    role="Redactor de Mensajes de Confirmación Premium",
    goal=(
        "Redactar el mensaje final de WhatsApp de confirmación de reserva, incluyendo: "
        "nombre del cliente, fecha/hora/personas, N° de reserva, mesa asignada, monto de seña, "
        "y link de pago. El tono debe ser cálido pero muy profesional."
    ),
    backstory=(
        "Eres el cerebro de comunicación del restaurante. Cada mensaje que redactas hace "
        "que el cliente sienta que está en manos de un establecimiento de primera categoría. "
        "Usas emojis con moderación y siempre incluyes el número de reserva para seguridad del cliente."
    ),
    llm=MODELO,
    verbose=True
)

# ─────────────────────────────────────────────
# 5. TAREAS
# ─────────────────────────────────────────────

tarea_verificacion = Task(
    description=(
        f"El cliente {MENSAJE_CLIENTE['nombre']} envió este mensaje: '{MENSAJE_CLIENTE['mensaje']}'. "
        "Verifica que tenga: nombre, cantidad de personas, fecha y horario. "
        f"Confirma si el horario solicitado está dentro del horario de atención del local. "
        f"Responde con un resumen estructurado de los datos de la reserva."
    ),
    expected_output=(
        "Resumen estructurado: nombre, personas, fecha, horario solicitado, "
        "estado (dentro/fuera de horario), mesa sugerida a asignar."
    ),
    agent=recepcionista_pro
)

tarea_pago = Task(
    description=(
        f"Con los datos de la reserva ya verificados, calcula la seña para {6} personas "
        f"a ${DATOS_RESTAURANTE['precio_promedio_cubierto']} ARS por cubierto. "
        f"El porcentaje de seña es del {DATOS_RESTAURANTE['monto_sena_porcentaje']}%. "
        f"El N° de reserva generado es: {nro_reserva}. "
        f"La mesa asignada es: {mesa_asignada}. "
        f"El link de pago simulado es: {link_pago_simulado}. "
        "Prepara el resumen de pago para que el notificador redacte el mensaje final."
    ),
    expected_output=(
        f"Total calculado, monto de seña en ARS, N° de reserva, mesa asignada, link de pago, "
        f"alias de MercadoPago ({DATOS_RESTAURANTE['alias_pago']})."
    ),
    agent=operador_pago,
    context=[tarea_verificacion]
)

tarea_notificacion = Task(
    description=(
        f"Con la verificación de reserva y los datos de pago, redacta el mensaje de WhatsApp "
        f"de confirmación para {MENSAJE_CLIENTE['nombre']}. "
        "Debe incluir: todos los datos de reserva, N° de reserva, mesa, monto de seña a pagar, "
        "link de pago y alias de MercadoPago. Máximo 8 líneas. Tono profesional y cálido."
    ),
    expected_output=(
        "El texto exacto del mensaje de WhatsApp listo para enviar al cliente, "
        "con todos los datos de reserva y pago incluidos."
    ),
    agent=notificador_pro,
    context=[tarea_verificacion, tarea_pago]
)

# ─────────────────────────────────────────────
# 6. CREW Y EJECUCIÓN
# ─────────────────────────────────────────────

crew_pro = Crew(
    agents=[recepcionista_pro, operador_pago, notificador_pro],
    tasks=[tarea_verificacion, tarea_pago, tarea_notificacion],
    verbose=True
)

print(f"\n🧠 Procesando reserva para {MENSAJE_CLIENTE['nombre']} — 3 agentes activos...\n")
resultado = crew_pro.kickoff()

# ─────────────────────────────────────────────
# 7. OUTPUT FINAL (Simula el JSON que FastAPI devolvería a n8n)
# ─────────────────────────────────────────────

output_simulado = {
    "plan": "PROFESIONAL",
    "restaurante": DATOS_RESTAURANTE["nombre_local"],
    "cliente": MENSAJE_CLIENTE["nombre"],
    "telefono": MENSAJE_CLIENTE["telefono"],
    "nro_reserva": nro_reserva,
    "mesa_asignada": mesa_asignada,
    "monto_sena_ars": monto_sena,
    "link_pago_generado": link_pago_simulado,
    "respuesta_bot_whatsapp": str(resultado),
    "estado": "seña_pendiente_de_pago"
}

print("\n" + "═" * 60)
print("📦 OUTPUT FINAL (JSON que FastAPI devolvería a n8n):")
print("═" * 60)
print(json.dumps(output_simulado, ensure_ascii=False, indent=2))
print("═" * 60)
