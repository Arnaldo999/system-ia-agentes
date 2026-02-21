# DIRECTIVA: WORKER_WHATSAPP

> **ID:** WK-WA-001
> **Script Asociado:** `workers/whatsapp/worker.py`
> **Última Actualización:** 2026-02-21
> **Estado:** ACTIVO

---

## 1. Objetivos y Alcance

- **Objetivo Principal:** Automatizar conversaciones de WhatsApp con IA: clasificar mensajes entrantes, generar respuestas personalizadas con voz de marca, y transcribir notas de voz.
- **Criterio de Éxito:** El agente clasifica con ≥90% de precisión las intenciones comunes y genera respuestas que el cliente no puede distinguir de un humano real.

---

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)

**`POST /whatsapp/clasificar-mensaje`**
- `mensaje`: str — Texto del mensaje de WhatsApp a clasificar
- `historial`: list[dict] — Últimos mensajes `[{role: "user"|"agente", text: "..."}]`
- `brandbook`: dict — Contexto de la marca (opcional)

**`POST /whatsapp/generar-respuesta`**
- `mensaje`: str — Mensaje del cliente
- `intencion`: str — Intención detectada previamente (output de `/clasificar-mensaje`)
- `historial`: list[dict] — Historial de conversación
- `brandbook`: dict — `{nombre_agencia, tono, servicios, reglas}`
- `nombre_cliente`: str — Nombre del cliente para personalización

**`POST /whatsapp/transcribir-audio`**
- `audio_base64`: str — Audio en base64
- `mime_type`: str — Formato del audio (`audio/ogg`, `audio/mp4`, `audio/mpeg`, `audio/webm`)

### Variables de Entorno
- `GEMINI_API_KEY`: API Key de Google Gemini (requerida)

### Salidas (Outputs)

**`/clasificar-mensaje`:**
```json
{
  "status": "success",
  "intencion": "agendar_cita",
  "confianza": "alta",
  "urgencia": "normal",
  "sentimiento": "positivo",
  "datos_extraidos": {
    "nombre": "Juan",
    "telefono": "",
    "fecha_mencionada": "el jueves",
    "producto_servicio_interes": "CRM"
  }
}
```

**`/generar-respuesta`:**
```json
{"status": "success", "respuesta": "Hola Juan..."}
```

**`/transcribir-audio`:**
```json
{"status": "success", "transcripcion": "Quería consultar sobre..."}
```

---

## 3. Flujo Lógico (Algoritmo)

### Flujo típico en n8n (secuencia de llamadas)
```
Webhook WhatsApp → [POST /whatsapp/clasificar-mensaje]
                         ↓
                   [POST /whatsapp/generar-respuesta] (con intencion del paso anterior)
                         ↓
                   Evolution API → enviar respuesta al cliente
```

### `/clasificar-mensaje`
1. Construir contexto con historial (últimos 5 mensajes)
2. Prompt con intenciones válidas hardcodeadas
3. Gemini devuelve JSON — extraer con regex
4. Retornar intención + metadatos

### `/generar-respuesta`
1. Extraer brandbook del cliente
2. Seleccionar instrucción especial según intención (queja → empatía, cita → pedir disponibilidad)
3. Construir prompt con historial y contexto
4. Gemini genera respuesta en tono WhatsApp (sin markdown, corta, con acción al cierre)

### `/transcribir-audio`
1. Enviar audio en base64 como `inlineData` a Gemini multimodal
2. Gemini transcribe el contenido
3. Retornar texto limpio

---

## 4. Herramientas y Librerías

- **FastAPI** + **Pydantic**: API endpoint
- **requests**: REST API de Gemini
- **Gemini 2.5 Flash**: Clasificación, generación de respuesta y transcripción de audio
- **re, json**: Parseo de JSON en respuestas de Gemini

---

## 5. Restricciones y Casos Borde

- **Intenciones válidas**: Solo las 7 definidas en `INTENCIONES_VALIDAS`. Si Gemini devuelve otra, tratar como `otro`.
- **Historial largo**: Enviar solo los últimos 5-6 mensajes para no exceder el contexto ni el costo.
- **Audio WhatsApp**: Evolution API entrega audios en formato OGG/Opus — pasar `mime_type: "audio/ogg"`.
- **Respuestas largas**: Si Gemini genera respuesta >300 palabras, el mensaje es demasiado largo para WhatsApp. Reforzar en el prompt que sea corta.
- **Mensaje vacío**: Si `mensaje` es cadena vacía, retornar error antes de llamar a Gemini.

---

## 6. Protocolo de Errores y Aprendizajes (Memoria Viva)

| Fecha | Error Detectado | Causa Raíz | Solución/Parche Aplicado |
|-------|-----------------|------------|--------------------------|
| 21/02 | Gemini genera respuestas con asteriscos (markdown) | El modelo usa markdown por defecto | Instrucción explícita "Sin asteriscos ni markdown" en el prompt |

---

## 7. Ejemplos de Uso desde n8n

```json
POST /whatsapp/clasificar-mensaje
{
  "mensaje": "Hola! cuánto cobran por el CRM?",
  "historial": [],
  "brandbook": {"nombre_agencia": "System IA"}
}
```

```json
POST /whatsapp/generar-respuesta
{
  "mensaje": "Hola! cuánto cobran por el CRM?",
  "intencion": "consulta_precio",
  "nombre_cliente": "María",
  "brandbook": {
    "nombre_agencia": "System IA",
    "tono": "cercano y profesional",
    "servicios": "CRM, WhatsApp, agendamientos",
    "reglas": "No dar precio sin antes entender la necesidad"
  }
}
```

## 8. Checklist de Pre-Deploy
- [ ] `GEMINI_API_KEY` configurada en Easypanel
- [ ] Test con mensaje de queja (debe empatizar primero)
- [ ] Test con mensaje de agendamiento (debe pedir fecha)
- [ ] Test transcripción con audio OGG de prueba
