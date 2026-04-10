# DIRECTIVA: DEMO_BASIC_RESTAURANTE — SaaS Gastronómico

> **ID:** BASIC-001
> **Script Asociado:** `demo_basic_restaurante.py`
> **Última Actualización:** 2026-03-02
> **Estado:** BORRADOR (Pruebas locales)

---

## 1. Objetivos y Alcance
- **Objetivo Principal:** Demostrar el flujo completo del Plan BASIC: recibir el mensaje crudo de un cliente por WhatsApp → extraer datos de reserva → generar mensaje de confirmación con CVU para delivery.
- **Criterio de Éxito:** El script corre sin errores, el Crew genera un mensaje de WhatsApp coherente en español argentino con los datos de reserva del cliente, y la salida JSON está bien formateada.

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)
- **`MENSAJE_CLIENTE`**: `str` — El texto crudo del cliente que llega por WhatsApp (ej:"Quiero mesa para 4 el sábado").
- **`DATOS_RESTAURANTE`**: `dict` — Nombre del local, CVU/Alias, horario de atención, menú del día.
- **Variables de Entorno (`.env`):** `GEMINI_API_KEY`: Llave de Google AI Studio.

### Salidas (Outputs)
- **Salida por consola:** `output_simulado` (JSON con 5 campos: `plan`, `restaurante`, `mensaje_cliente_original`, `respuesta_bot_whatsapp`, `estado`).
- **Cuando pase a FastAPI:** Este JSON será el `return` del endpoint `POST /reserva/basic`.

## 3. Flujo Lógico (Algoritmo)
1. **Carga de Variables:** `load_dotenv()` carga la `GEMINI_API_KEY`.
2. **Configuración de Datos:** Se definen las variables del restaurante y el mensaje entrante del cliente.
3. **Agente 1 - Recepcionista Virtual:** Extrae los datos de reserva del mensaje de texto (nombre, personas, fecha, horario). Detecta si falta algún dato.
4. **Agente 2 - Confirmador:** Toma los datos extraídos y redacta el mensaje de confirmación para WhatsApp.
5. **Crew Kickoff:** Se ejecutan las dos tareas en secuencia.
6. **Output JSON:** Se imprime el resultado final como simulación del endpoint de FastAPI.

## 4. Herramientas y Librerías Permitidas
- `crewai` — Orquestación de Agentes.
- `python-dotenv` — Gestión de variables de entorno.
- `json` — Serialización del output final.
- **LLM:** `gemini/gemini-2.0-flash-lite` (obligatorio en fase de pruebas).

## 5. Protocolo de Errores y Aprendizajes (Memoria Viva)
| Fecha | Error Detectado | Causa Raíz | Solución/Parche Aplicado |
|-------|-----------------|------------|--------------------------|
| - | - | - | - |

## 6. Camino a Producción (FastAPI)
Cuando este demo sea aprobado por el usuario, el script se refactorizará:
1. Mover `DATOS_RESTAURANTE` y `MENSAJE_CLIENTE` a los parámetros del cuerpo HTTP (Body de la request).
2. Envolver el Crew en una función `async` de FastAPI.
3. Retornar `output_simulado` como `JSONResponse`.
4. Endpoint resultante: `POST /api/v1/gastronomico/basic/reserva`
