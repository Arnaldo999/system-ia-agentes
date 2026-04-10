---
name: Entorno de Pruebas AI (CrewAI)
description: Guía y protocolos para desarrollar, probar y ejecutar agentes de inteligencia artificial (CrewAI) en un entorno local y segregado, utilizando modelos eficientes de Google Gemini.
---
# Entorno de Pruebas para Agentes (CrewAI)

## 📌 Propósito y Arquitectura
Este proyecto mantiene una estricta separación entre el entorno de **Laboratorio de Pruebas** y el entorno de **Producción** (donde conviven FastAPI, n8n, Render y Easypanel).

*   **Carpeta de Laboratorio Local:** `/home/arna/PROYECTOS SYSTEM IA/INGENIERO N8N/pruebas_crewai`
*   **Motivo:** Evitar que los desarrollos experimentales con orquestación de Agentes (CrewAI, LangChain, etc.) rompan la API principal o incrementen de forma descontrolada los costos de tokens en los flujos activos.

Cualquier LLM o Agente (Gemini, Claude, GPT, etc.) que asista en este repositorio **DEBE OBLIGATORIAMENTE** seguir este estándar al momento de crear, depurar o diseñar scripts relacionados con agentes IA, antes de sugerir integrarlos a la API en producción.

---

## ⚙️ Estándar de Modelos (LiteLLM)

El proyecto utiliza la sintaxis nativa de LiteLLM (proveedor/modelo) integrada en versiones modernas de CrewAI. Para optimizar el presupuesto del proyecto, el estándar de uso es estricto:

### 1. Entorno Local / Pruebas (Carpeta `pruebas_crewai`)
*   **Modelo Obligatorio:** `gemini/gemini-2.5-flash-lite`
*   **Justificación:** Altamente económico, extremadamente rápido para iterar la lógica de los Agentes, probar prompts (YAML o Python) y evaluar la comunicación entre ellos sin quemar saldo. Se debe utilizar la llave de Google AI Studio gratuita.

### 2. Entorno Producción / Despliegue (FastAPI + n8n)
*   **Modelo Sugerido:** `gemini/gemini-2.5-flash-lite` (Versión estable y optimizada) o el modelo superior definido por el requerimiento del cliente.
*   **Implementación:** Solo se pasa el código a Producción transformándolo en endpoints HTTP manejables por n8n.

---

## 🏗️ Flujo de Trabajo (Workflow de Pruebas)

Cuando el usuario requiera asistencia con CrewAI o nuevos Agentes:

1.  **NO alteres** `main.py` de FastAPI.
2.  **Dirígete** a la carpeta `/ home/arna/PROYECTOS SYSTEM IA/INGENIERO N8N/pruebas_crewai`.
3.  **Crea scripts atómicos** para probar el Agente o la Tarea de manera aislada (ej. `agente_ventas_micaela.py`).
4.  **Usa configuración robusta:**
    *   Lee variables desde archivo `.env` mediante `dotenv`.
    *   Nunca hardcodees la API Key (`GEMINI_API_KEY`) en el código fuente.
5.  **Aprobación requerida:** Únicamente cuando la prueba local compile, se ejecute correctamente y el output estratégico del agente sea validado por el usuario, el LLM podrá sugerir el *refactoring* del script para integrarlo como un endpoint en la carpeta de la API local.

---

## 📝 Ejemplo de Plantilla de Agente para Pruebas

```python
import os
from dotenv import load_dotenv
from crewai import Agent

# 1. Cargar Entorno
load_dotenv()

# 2. Definir Estándar de Pruebas
MODELO_PRUEBAS = "gemini/gemini-2.0-flash-lite"

# 3. Creación del Agente (Aislado)
agente = Agent(
    role='Nombre del Rol',
    goal='Objetivo atómico y claro a lograr',
    backstory='Contexto profundo que guía la personalidad del Agente en beneficio de la Agencia o el Cliente',
    llm=MODELO_PRUEBAS,
    verbose=True
)
```

## 🚨 Regla de Oro
Ningún modelo asistente debe sugerir usar modelos pesados (ej. `gpt-4o` o `claude-3-opus`) durante la fase de creación de scripts en esta carpeta de pruebas. El diseño ágil del prompt debe validarse primero con la serie `gemini-*-flash-lite`.
