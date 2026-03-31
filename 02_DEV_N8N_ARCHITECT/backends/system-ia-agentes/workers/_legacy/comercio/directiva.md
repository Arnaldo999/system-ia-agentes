# DIRECTIVA: AGENCE_COMERCIO_WHATSAPP
> **ID:** 2026-02-21-COMERCIO-01
> **Script Asociado:** `workers/comercio/worker.py`
> **Última Actualización:** 2026-02-21
> **Estado:** ACTIVO

---

## 1. Objetivos y Alcance
- **Objetivo Principal:** Procesar mensajes de WhatsApp (audio/texto) para comerciantes. Permite dar de alta/baja productos (Gestión de Catálogo) y responder consultas de clientes finales actuando como un vendedor experto usando GPT-4o.
- **Criterio de Éxito:** 
  1. El comerciante puede crear o actualizar un producto indicando solo "Nombre, Precio, y Disponibilidad (Disponible / No Disponible)" mediante lenguaje natural.
  2. Los clientes reciben respuestas precisas, amables y orientadas a la venta basándose estrictamente en el catálogo proporcionado, sin inventar stock ni precios.

## 2. Especificaciones de Entrada/Salida (I/O)
### Entradas (Inputs)
- **Endpoint 1 (`/comercio/procesar-mensaje-admin`):** Para el dueño. Recibe `mensaje` (str).
- **Endpoint 2 (`/comercio/atender-cliente`):** Para el cliente final. Recibe `mensaje_cliente` (str) y `catalogo_actual` (list de dicts).
- **Variables de Entorno (.env):** `OPENAI_API_KEY`: API Key para usar gpt-4o.

### Salidas (Outputs)
- **Artefactos Generados:** JSON estructurado para que n8n interactúe con Airtable o envíe mensajes vía Evolution API.
- **Retorno de Consola/API:** 
  - Admin: `{"accion": "crear_producto|actualizar_disponibilidad|desconocida", "datos": {"nombre": "...", "precio": 100, "disponible": true}}`
  - Cliente: `{"respuesta": "Hola! Sí tenemos...", "requiere_accion": false}`

## 3. Flujo Lógico (Algoritmo)
1. **Inicialización:** Recibe el Request en FastAPI. Valida que exista `OPENAI_API_KEY`.
2. **Procesamiento Admin:** Usa GPT-4o con `response_format={"type": "json_object"}` para extraer los datos del producto del mensaje desordenado del dueño. Mapea la disponibilidad a un booleano o string binario.
3. **Procesamiento Cliente:** Inyecta el catálogo en el System Prompt de GPT-4o. Pide que actúe como vendedor. Genera la respuesta en texto plano lista para WhatsApp.
4. **Retorno:** Devuelve el payload a n8n.

## 4. Herramientas y Librerías permitidas
- **Librerías Python:** `fastapi`, `pydantic`, `openai` (o `litellm`), `os`, `json`.

## 5. Protocolo de Errores y Aprendizajes (Memoria Viva)
| Fecha | Error Detectado | Causa Raíz | Solución/Parche Aplicado |
|-------|-----------------|------------|--------------------------|
| 21/02 | N/A             | N/A        | Creación inicial del SOP |
