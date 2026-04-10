import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew

# 1. Cargamos las variables de entorno (como tu GEMINI_API_KEY)
load_dotenv()

# Verificamos si pusiste la API KEY en un archivo .env local
if not os.environ.get("GEMINI_API_KEY"):
    print("⚠️ ¡ATENCIÓN! No encontré tu GEMINI_API_KEY.")
    print("Por favor, crea un archivo llamado '.env' en esta carpeta y pon ahí tu llave.")
    exit()

# 2. DEFINIR EL MODELO LITE PARA PRUEBAS
# Usando la sintaxis de LiteLLM que recomienda el video (proveedor/modelo)
MODELO_PRUEBAS = "gemini/gemini-2.5-flash-lite"

print(f"🚀 Iniciando prueba con modelo: {MODELO_PRUEBAS}")

# 3. CREAMOS NUESTRO PRIMER AGENTE
# Este es un agente diseñado para ayudar a Micaela a buscar información
# antes de visitar a un cliente físico (ej: un gimnasio)
investigador_local = Agent(
    role='Investigador de Negocios Locales',
    goal='Analizar la presencia digital de un negocio local para encontrar fallas que la Agencia pueda solucionar.',
    backstory='Eres un estratega de marketing de la agencia "Crecimiento y Capital". '
              'Tu trabajo es investigar a fondo negocios locales antes de que Micaela (la vendedora de tu equipo) vaya a visitarlos en persona.',
    llm=MODELO_PRUEBAS,
    verbose=True # Para ver cómo piensa por consola
)

# 4. CREAMOS LA TAREA ASIGNADA AL AGENTE
tarea_analisis_gimnasio = Task(
    description='Analiza en base a tus conocimientos cómo un "Gimnasio local tradicional en Argentina" '
                'podría beneficiarse de la automatización de WhatsApp y la agenda de Cal.com. '
                'Identifica 3 puntos de dolor comunes de estos negocios que nuestra agencia resuelve.',
    expected_output='Un breve reporte con 3 puntos de dolor del gimnasio y un argumento de venta para que use Micaela.',
    agent=investigador_local
)

# 5. CREAMOS EL EQUIPO (CREW) Y LO PONEMOS A TRABAJAR
equipo_prueba = Crew(
    agents=[investigador_local],
    tasks=[tarea_analisis_gimnasio],
    # process=Process.sequential  (Por defecto es secuencial, como decía el video)
    verbose=True
)

# 6. ¡ACCIÓN!
print("🧠 El Agente está pensando...")
resultado = equipo_prueba.kickoff()

print("\n\n✅ RESULTADO FINAL DE LA TAREA:\n", resultado)
