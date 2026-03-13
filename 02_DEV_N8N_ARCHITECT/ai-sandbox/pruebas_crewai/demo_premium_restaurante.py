"""
DEMO 3 — PLAN PREMIUM: Motor de Cumpleaños y Fidelización con IA
=================================================================
Simula el flujo automático de un trigger de cumpleaños que se dispara
diariamente (CRON Job en n8n) para detectar clientes que cumplen años
y ejecutar la cadena de fidelización premium del restaurante.

ENTORNO: Pruebas locales — gemini/gemini-2.5-flash
NO REQUIERE: WhatsApp real, Airtable, Looker Studio activos.
SIGUIENTE PASO: Cuando este demo funcione, se convierte en el endpoint
                POST /fidelizacion/cumpleanios en FastAPI.
"""

import os
import json
from datetime import date
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
# 2. DATOS DE ENTRADA
# (Simulan lo que n8n leería de Airtable vía el Trigger de CRON Job diario)
# ─────────────────────────────────────────────
DATOS_RESTAURANTE = {
    "nombre_local": "Il Forno Trattoria",
    "tipo_cocina": "Italiana",
    "obsequio_cumpleanios": "Tiramisú de la casa para toda la mesa",
    "descuento_especial": "15% en toda la carta",
    "link_reserva": "https://ilforno.com/reservar",
    "instagram": "@ilfornotrattoria",
    "evento_proximo": {
        "nombre": "Noche de Jazz en vivo",
        "fecha": "Sábado 15 de Marzo",
        "descripcion": "Cóctel de bienvenida incluido para reservas anticipadas"
    }
}

# Perfil del cliente extraído de Airtable CRM (simulado)
PERFIL_CLIENTE = {
    "nombre": "Mariana López",
    "fecha_cumpleanios": "02 de Marzo",
    "visitas_totales": 7,
    "ultima_visita": "Diciembre 2024",
    "plato_favorito": "Risotto ai Funghi",
    "dias_para_cumpleanios": 0,  # 0 = hoy es su cumpleaños
    "tiene_reserva_activa": False,
    "canal_preferido": "WhatsApp"
}

hoy = date.today().strftime("%d de %B")

print("─" * 60)
print(f"🎂  DEMO PREMIUM — Motor de Cumpleaños")
print(f"    Restaurante: {DATOS_RESTAURANTE['nombre_local']}")
print("─" * 60)
print(f"👤 Cliente detectado: {PERFIL_CLIENTE['nombre']} — Cumpleaños: HOY ({hoy})")
print(f"📊 Visitas totales: {PERFIL_CLIENTE['visitas_totales']} | Plato favorito: {PERFIL_CLIENTE['plato_favorito']}")
print("─" * 60)

# ─────────────────────────────────────────────
# 3. AGENTES
# ─────────────────────────────────────────────

analista_fidelizacion = Agent(
    role="Analista de Perfil de Fidelización",
    goal=(
        "Analizar el perfil del cliente (visitas, preferencias, historial) "
        "y determinar el nivel de importancia y el tipo de mensaje personalizado que merece. "
        "Un cliente con más de 5 visitas es un 'Cliente VIP' y merece trato diferencial."
    ),
    backstory=(
        f"Eres el sistema de análisis CRM de '{DATOS_RESTAURANTE['nombre_local']}'. "
        "Conoces a cada cliente por su nombre y su historia con el restaurante. "
        "Tu misión es convertir datos fríos (número de visitas, plato favorito) "
        "en insights cálidos que guíen la estrategia de comunicación y retención."
    ),
    llm=MODELO,
    verbose=True
)

copywriter_cumpleanios = Agent(
    role="Copywriter de Felicitaciones y Ofertas Especiales",
    goal=(
        "Redactar un mensaje de felicitación de cumpleaños altamente personalizado "
        "para WhatsApp que incluya: el obsequio del restaurante, el descuento especial, "
        "y una mención al plato favorito del cliente. El mensaje debe generar una reserva inmediata."
    ),
    backstory=(
        f"Eres el escritor estrella de '{DATOS_RESTAURANTE['nombre_local']}'. "
        "Dominas el arte de hacer que las personas se sientan especiales y queridas. "
        "Cada mensaje que escribes combina calidez humana con una oferta irresistible. "
        "Escribes en español argentino con tono elegante, nunca exagerado. "
        "Siempre incluyes un llamado a la acción claro al final del mensaje."
    ),
    llm=MODELO,
    verbose=True
)

coordinador_eventos = Agent(
    role="Coordinador de Eventos y Experiencias Premium",
    goal=(
        "Si el restaurante tiene un evento próximo, evaluar si vale la pena mencionárselo al cliente "
        "en la secuencia de cumpleaños para maximizar la probabilidad de reserva."
    ),
    backstory=(
        "Eres el estratega de experiencias del restaurante. Sabes que los clientes de cumpleaños "
        "son los más propensos a reservar eventos especiales. Si hay un show, cata o noche temática "
        "próxima, lo integras sutilmente en la comunicación de felicitación para duplicar el impacto."
    ),
    llm=MODELO,
    verbose=True
)

# ─────────────────────────────────────────────
# 4. TAREAS
# ─────────────────────────────────────────────

tarea_analisis = Task(
    description=(
        f"Analiza el perfil del cliente: {json.dumps(PERFIL_CLIENTE, ensure_ascii=False)}. "
        "Determina: ¿Es cliente VIP (>5 visitas)? ¿Tiene reserva activa? "
        "¿Cuántos días faltan para su cumpleaños? "
        "Define el tono y la urgencia del mensaje: si es hoy, máxima prioridad; "
        "si faltan días, comunicación de anticipación. "
        "Entrega un resumen estratégico del perfil."
    ),
    expected_output=(
        "Resumen: nivel del cliente (VIP/Regular), si es su cumpleaños hoy o cuánto falta, "
        "tono recomendado del mensaje, y si se recomienda incluir link de reserva."
    ),
    agent=analista_fidelizacion
)

tarea_felicitacion = Task(
    description=(
        f"Usando el perfil analizado, redacta el mensaje de WhatsApp de felicitación de cumpleaños "
        f"para {PERFIL_CLIENTE['nombre']}. "
        f"El restaurante se llama {DATOS_RESTAURANTE['nombre_local']} ({DATOS_RESTAURANTE['tipo_cocina']}). "
        f"Su plato favorito es el {PERFIL_CLIENTE['plato_favorito']}. "
        f"El obsequio de la casa es: {DATOS_RESTAURANTE['obsequio_cumpleanios']}. "
        f"El descuento especial es: {DATOS_RESTAURANTE['descuento_especial']} (en su próxima visita este mes). "
        f"El link para reservar es: {DATOS_RESTAURANTE['link_reserva']}. "
        "Máximo 7 líneas. Use emojis con mesura (máximo 3). Tono cálido, sincero y elegante."
    ),
    expected_output=(
        "El texto exacto del mensaje de WhatsApp de felicitación con el obsequio, descuento, "
        "mención al plato favorito y el link de reserva."
    ),
    agent=copywriter_cumpleanios,
    context=[tarea_analisis]
)

tarea_evento = Task(
    description=(
        f"Evalúa si el próximo evento del restaurante es relevante para añadir al final del mensaje de cumpleaños: "
        f"Evento: '{DATOS_RESTAURANTE['evento_proximo']['nombre']}' el {DATOS_RESTAURANTE['evento_proximo']['fecha']}. "
        f"Descripción: {DATOS_RESTAURANTE['evento_proximo']['descripcion']}. "
        "Si el cliente es VIP y no tiene reserva activa, agrega un párrafo final (máximo 2 líneas) "
        "invitando al evento. Si el cliente ya tiene reserva, omite el evento para no saturar el mensaje. "
        "Entrega el mensaje final completo con o sin la sección del evento."
    ),
    expected_output=(
        "El mensaje final de WhatsApp COMPLETO (felicitación + evento si aplica), "
        "listo para enviarse directamente por la API de WhatsApp."
    ),
    agent=coordinador_eventos,
    context=[tarea_analisis, tarea_felicitacion]
)

# ─────────────────────────────────────────────
# 5. CREW Y EJECUCIÓN
# ─────────────────────────────────────────────

crew_premium = Crew(
    agents=[analista_fidelizacion, copywriter_cumpleanios, coordinador_eventos],
    tasks=[tarea_analisis, tarea_felicitacion, tarea_evento],
    verbose=True
)

print(f"\n🧠 Motor de Fidelización activado para {PERFIL_CLIENTE['nombre']} — 3 agentes activos...\n")
resultado = crew_premium.kickoff()

# ─────────────────────────────────────────────
# 6. OUTPUT FINAL (Simula el JSON que FastAPI devolvería a n8n)
# ─────────────────────────────────────────────

output_simulado = {
    "plan": "PREMIUM",
    "tipo_disparo": "cumpleanios",
    "restaurante": DATOS_RESTAURANTE["nombre_local"],
    "cliente": PERFIL_CLIENTE["nombre"],
    "canal": PERFIL_CLIENTE["canal_preferido"],
    "mensaje_generado": str(resultado),
    "obsequio_incluido": DATOS_RESTAURANTE["obsequio_cumpleanios"],
    "descuento_incluido": DATOS_RESTAURANTE["descuento_especial"],
    "evento_promovido": DATOS_RESTAURANTE["evento_proximo"]["nombre"],
    "estado": "listo_para_envio"
}

print("\n" + "═" * 60)
print("📦 OUTPUT FINAL (JSON que FastAPI devolvería a n8n):")
print("═" * 60)
print(json.dumps(output_simulado, ensure_ascii=False, indent=2))
print("═" * 60)
