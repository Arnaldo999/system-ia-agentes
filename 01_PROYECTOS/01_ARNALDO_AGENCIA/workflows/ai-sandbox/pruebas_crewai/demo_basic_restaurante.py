"""
DEMO 1 — PLAN BASIC: Sistema de Reservas y Delivery con IA
============================================================
Simula el flujo de un cliente que escribe por WhatsApp al restaurante.
El Crew de CrewAI procesa la solicitud y devuelve:
  - La reserva capturada y formateada.
  - El CVU/Alias del local para confirmar el pedido de delivery.

ENTORNO: Pruebas locales — gemini/gemini-2.0-flash-lite
NO REQUIERE: WhatsApp real, n8n activo, ni MercadoPago.
SIGUIENTE PASO: Cuando este demo funcione, se convierte en el endpoint
                POST /reserva/basic en FastAPI.
"""

import os
import json
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
# 2. DATOS DE ENTRADA (Simulan lo que n8n recibiría de WhatsApp)
# ─────────────────────────────────────────────
DATOS_RESTAURANTE = {
    "nombre_local": "La Parrilla de Don Alberto",
    "cvú_alias": "donalberto.parrilla",
    "horario_atencion": "Martes a Domingo, 12hs a 00hs",
    "menu_hoy": "Bife de Chorizo, Entraña, Empanadas, Ensalada Mixta"
}

# Mensaje que llega desde el cliente final vía WhatsApp
MENSAJE_CLIENTE = "Hola! Quisiera reservar una mesa para 4 personas el sábado a las 21hs. Me llamo Rodrigo."

print("─" * 55)
print(f"🍽️  DEMO BASIC — {DATOS_RESTAURANTE['nombre_local']}")
print("─" * 55)
print(f"📱 Mensaje entrante: «{MENSAJE_CLIENTE}»")
print("─" * 55)

# ─────────────────────────────────────────────
# 3. AGENTES
# ─────────────────────────────────────────────

recepcionista = Agent(
    role="Recepcionista Virtual del Restaurante",
    goal=(
        "Extraer de forma precisa todos los datos de reserva de un cliente "
        "(nombre, cantidad de personas, fecha y horario) desde un mensaje de WhatsApp. "
        "Si falta algún dato, identificar cuál es y preparar la pregunta para solicitarlo cortésmente."
    ),
    backstory=(
        f"Eres el profesional asistente del restaurante '{DATOS_RESTAURANTE['nombre_local']}'. "
        "Tu trabajo es atender por WhatsApp de forma cálida y precisa. "
        f"El horario de atención del local es {DATOS_RESTAURANTE['horario_atencion']}. "
        "Hablas en español argentino, con tono amigable y profesional."
    ),
    llm=MODELO,
    verbose=True
)

confirmador = Agent(
    role="Confirmador de Reservas y Asistente de Delivery",
    goal=(
        "Redactar el mensaje final de confirmación de reserva con todos los datos del cliente, "
        "incluyendo el CVU/Alias del local para confirmar pagos de delivery si aplica. "
        "El mensaje debe ser claro, breve y listo para enviarse por WhatsApp."
    ),
    backstory=(
        "Eres el sistema de backend del restaurante que toma los datos estructurados de reserva "
        "y genera el mensaje de confirmación perfecto. Tus respuestas siempre deben terminar "
        "con el alias de pago en caso de delivery y una frase de bienvenida cálida."
    ),
    llm=MODELO,
    verbose=True
)

# ─────────────────────────────────────────────
# 4. TAREAS
# ─────────────────────────────────────────────

tarea_extraccion = Task(
    description=(
        f"El cliente envió este mensaje: '{MENSAJE_CLIENTE}'. "
        "Extrae los siguientes datos: nombre del cliente, número de personas, fecha y horario. "
        "Si todos los datos están, marca como 'completo'. Si falta alguno, indica cuál falta. "
        "Devuelve el resultado como un diccionario en texto plano."
    ),
    expected_output=(
        "Un diccionario con las claves: nombre, personas, fecha, horario, estado (completo/incompleto), "
        "y si está incompleto, el campo 'dato_faltante' con qué pregunta hacer."
    ),
    agent=recepcionista
)

tarea_confirmacion = Task(
    description=(
        "Con los datos de reserva extraídos en la tarea anterior, redacta el mensaje de confirmación "
        f"para enviar al cliente por WhatsApp. El local se llama {DATOS_RESTAURANTE['nombre_local']}. "
        f"Si el cliente menciona delivery, incluye el CVU/Alias: {DATOS_RESTAURANTE['cvú_alias']}. "
        f"El menú de hoy es: {DATOS_RESTAURANTE['menu_hoy']}. "
        "El mensaje debe ser en español, cálido, máximo 5 líneas."
    ),
    expected_output=(
        "El texto exacto del mensaje de WhatsApp a enviar al cliente, incluyendo emoji de confiración ✅, "
        "los datos de su reserva, y si aplica, el alias para el pago."
    ),
    agent=confirmador,
    context=[tarea_extraccion]
)

# ─────────────────────────────────────────────
# 5. CREW Y EJECUCIÓN
# ─────────────────────────────────────────────

crew_basic = Crew(
    agents=[recepcionista, confirmador],
    tasks=[tarea_extraccion, tarea_confirmacion],
    verbose=True
)

print("\n🧠 Los agentes están procesando la solicitud...\n")
resultado = crew_basic.kickoff()

# ─────────────────────────────────────────────
# 6. OUTPUT FINAL (Simula el JSON que FastAPI devolvería a n8n)
# ─────────────────────────────────────────────

output_simulado = {
    "plan": "BASIC",
    "restaurante": DATOS_RESTAURANTE["nombre_local"],
    "mensaje_cliente_original": MENSAJE_CLIENTE,
    "respuesta_bot_whatsapp": str(resultado),
    "estado": "reserva_procesada"
}

print("\n" + "═" * 55)
print("📦 OUTPUT FINAL (JSON que FastAPI devolvería a n8n):")
print("═" * 55)
print(json.dumps(output_simulado, ensure_ascii=False, indent=2))
print("═" * 55)
