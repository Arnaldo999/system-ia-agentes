---
name: agentic-workflows
description: Guide for creating Agentic Workflows (Microservices) using Python, GitHub, and Coolify/Easypanel, replacing traditional n8n nodes with intelligent API endpoints.
---

# Agentic Workflows (Microservices) Builder

## Context
When a user requests a complex, AI-heavy, or long-running automation (e.g., advanced web scraping, audio/video processing, custom AI logic, robust data enrichment), DO NOT use traditional n8n nodes or pure n8n Code nodes. Instead, build an **Agentic Workflow** (Microservice/Worker).

An Agentic Workflow is a specialized script (usually Python) that handles the complex logic, packaged as a microservice (API endpoint) deployed to Easypanel/Coolify via a GitHub repository. n8n acts only as the Orchestrator, calling this microservice via a simple HTTP Request node.

## 1. Architecture: Orchestrator & Workers
- **n8n (Orchestrator)**: Triggers the execution, manages the state, and calls the microservices.
- **Workers (Microservices)**: Hosted externally (Coolify/Easypanel), they receive inputs from n8n, process the AI logic or heavy tasks using Python/Node.js, and return structured results.

## 2. Directives (SOPs)
Every new Worker must have an associated Directive file. These files act as the memory and strict guidelines for the agent to ensure determinism and prevent regression.

When creating a new worker:
1. Create a folder: `workers/[worker_name]/`
2. Create the directive file: `workers/[worker_name]/directiva.md` using the exact structure below.
3. Keep the code inside `workers/[worker_name]/`.

### Estructura de la Directiva (Obligatoria)

```md
# DIRECTIVA: [NOMBRE_CLAVE_DE_LA_TAREA_SOP]

> **ID:** [ID_UNICO_O_FECHA]
> **Script Asociado:** `scripts/[nombre_del_script].py`
> **Última Actualización:** [FECHA_ACTUAL]
> **Estado:** [BORRADOR / ACTIVO / DEPRECADO]

---

## 1. Objetivos y Alcance
- **Objetivo Principal:** [Descripción concisa de la meta final]
- **Criterio de Éxito:** [Condición exacta para considerar la tarea completada]

## 2. Especificaciones de Entrada/Salida (I/O)
### Entradas (Inputs)
- **Argumentos Requeridos:** `[nombre_arg]`: [Tipo de dato] - [Descripción].
- **Variables de Entorno (.env):** `[NOMBRE_VAR]`: [Descripción].

### Salidas (Outputs)
- **Artefactos Generados:** `[ruta_de_salida]`.
- **Retorno de Consola/API:** [Formato JSON esperado].

## 3. Flujo Lógico (Algoritmo)
1. **Inicialización:** ...
2. **Procesamiento:** ...
3. **Persistencia:** ...

## 4. Herramientas y Librerías permitidas
- **Librerías Python:** `[fastapi]`, `[requests]`, `[pydantic]`.

## 5. Protocolo de Errores y Aprendizajes (Memoria Viva)
| Fecha | Error Detectado | Causa Raíz | Solución/Parche Aplicado |
|-------|-----------------|------------|--------------------------|
| DD/MM | ...             | ...        | ...                      |
```

## 3. Code Generation Requirements
- The Worker code (e.g., `main.py`) MUST expose a robust HTTP endpoint (using FastAPI for Python, or Express for Node.js) to receive requests from n8n.
- Include a `Dockerfile` for easy deployment on Easypanel/Coolify.
- Include a `requirements.txt` or `package.json`.
- Implement robust error handling and ensure timeouts are managed gracefully (consider asynchronous architectures for jobs > 2 mins).

## 4. GitHub Deployment via MCP
As the Agent Engineer, you have access to the terminal to deploy these workflows:
1. After writing the code and the directive, use `run_command` to add, commit, and push the folder to the configured GitHub repository.
2. `git add workers/[worker_name]/`
3. `git commit -m "feat: add [worker_name] microservice"`
4. `git push origin main`
5. Inform the user that the code has been pushed and is ready for Easypanel deployment.
