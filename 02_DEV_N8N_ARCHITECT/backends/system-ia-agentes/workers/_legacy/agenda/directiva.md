# DIRECTIVA: WORKER_AGENDAMIENTO

> **ID:** WK-AGENDA-001
> **Script Asociado:** `workers/agenda/worker.py`
> **Última Actualización:** 2026-02-21
> **Estado:** ACTIVO

---

## 1. Objetivos y Alcance

- **Objetivo Principal:** Automatizar el ciclo completo de agendamiento: parsear fechas en lenguaje natural, verificar disponibilidad contra la agenda real, y generar mensajes de confirmación/recordatorio personalizados.
- **Criterio de Éxito:** Parseo de fechas con ≥95% de precisión en expresiones típicas de LATAM. Verificación de slots en <100ms (lógica pura Python, sin IA). Recordatorios que el cliente no percibe como automáticos.

---

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)

**`POST /agenda/parsear-fecha`**
- `texto`: str — Texto en lenguaje natural con la fecha ("el martes a las 3", "mañana temprano")
- `zona_horaria`: str — Zona horaria del cliente (default: `America/Argentina/Buenos_Aires`)
- `fecha_referencia`: str — YYYY-MM-DD de "hoy" (default: fecha actual del servidor)

**`POST /agenda/verificar-slot`**
- `fecha_solicitada`: str — YYYY-MM-DD
- `hora_solicitada`: str — HH:MM
- `duracion_minutos`: int — Duración de la cita (default: 60)
- `eventos_existentes`: list[dict] — `[{titulo, inicio: "ISO", fin: "ISO"}]`

**`POST /agenda/generar-recordatorio`**
- `cita`: dict — `{nombre_cliente, fecha, hora, servicio, lugar_o_link, duracion_minutos}`
- `tipo`: str — `confirmacion|recordatorio_24h|recordatorio_1h|reprogramacion`
- `brandbook`: dict — `{nombre_agencia, tono}`

### Variables de Entorno
- `GEMINI_API_KEY`: requerida para `/parsear-fecha` y `/generar-recordatorio`

### Salidas (Outputs)

**`/parsear-fecha`:**
```json
{
  "status": "success",
  "fecha": "2026-02-24",
  "hora": "15:00",
  "fecha_hora_iso": "2026-02-24T15:00:00",
  "es_aproximado": false,
  "confianza": "alta",
  "texto_interpretado": "El martes 24 de febrero a las 3 PM",
  "ambiguo": false,
  "razon_ambiguedad": ""
}
```

**`/verificar-slot`:**
```json
{
  "status": "success",
  "disponible": true,
  "slot_solicitado": {"inicio": "2026-02-24T15:00:00", "fin": "2026-02-24T16:00:00"},
  "conflictos": [],
  "mensaje": "Slot disponible ✓"
}
```

**`/generar-recordatorio`:**
```json
{
  "status": "success",
  "mensaje": "Hola María, te confirmo tu cita...",
  "tipo": "confirmacion"
}
```

---

## 3. Flujo Lógico (Algoritmo)

### Flujo típico en n8n (agendamiento completo)
```
Cliente envía fecha por WhatsApp →
  [POST /whatsapp/clasificar-mensaje] → intencion: "agendar_cita"
  [POST /agenda/parsear-fecha] con el texto del cliente →
  Leer eventos de Google Calendar (n8n nativo) →
  [POST /agenda/verificar-slot] con los eventos leídos →
  Si disponible:
    Crear evento en Google Calendar (n8n)
    [POST /agenda/generar-recordatorio] tipo: "confirmacion"
    Evolution API → enviar confirmación
  Si no disponible:
    [POST /whatsapp/generar-respuesta] → sugerir otros horarios
```

### `/parsear-fecha`
1. Determinar día de la semana actual para contexto
2. Prompt con ejemplos de expresiones típicas de LATAM
3. Gemini devuelve JSON con fecha ISO + metadatos de confianza
4. Si `ambiguo: true` → n8n debe pedir aclaración al cliente

### `/verificar-slot` (sin IA — lógica pura)
1. Parsear fecha/hora solicitada a `datetime`
2. Calcular fin del slot según `duracion_minutos`
3. Para cada evento: detectar overlap con `A.start < B.end AND A.end > B.start`
4. Retornar disponible + lista de conflictos si los hay

### `/generar-recordatorio`
1. Extraer brandbook y datos de la cita
2. Seleccionar propósito según `tipo`
3. Gemini genera mensaje personalizado en tono WhatsApp
4. Sin markdown, con saltos de línea, máximo 5 líneas

---

## 4. Herramientas y Librerías

- **FastAPI** + **Pydantic**: API endpoint
- **requests**: REST API de Gemini
- **datetime, timedelta** (stdlib): Cálculo de overlaps en `/verificar-slot`
- **Gemini 2.5 Flash**: Parseo de lenguaje natural y generación de mensajes
- **re, json**: Parseo de respuestas

---

## 5. Restricciones y Casos Borde

- **"A las 3"** sin AM/PM: Gemini asume tarde (15:00) si el contexto es laboral. Si el cliente especifica "de la mañana" → 09:00.
- **Zonas horarias**: `/verificar-slot` trabaja en tiempo local — los eventos de Google Calendar llegan en UTC con sufijo `Z`. El código hace `.replace("Z", "")` para evitar errores de parseo (asume misma zona horaria).
- **`ambiguo: true`**: n8n debe detectar este campo y enviar al cliente `generar-respuesta` solicitando aclaración en lugar de continuar con el agendamiento.
- **Eventos sin `fin`**: Si un evento de Google Calendar no tiene `fin`, se asume duración de 1 hora.
- **Fecha pasada**: Si Gemini parsea una fecha anterior a hoy, n8n debe validar y pedir nueva fecha.

---

## 6. Protocolo de Errores y Aprendizajes (Memoria Viva)

| Fecha | Error Detectado | Causa Raíz | Solución/Parche Aplicado |
|-------|-----------------|------------|--------------------------|
| 21/02 | `datetime.fromisoformat()` falla con fechas de Google Calendar en formato `2026-02-24T15:00:00Z` | Python <3.11 no soporta el sufijo `Z` | `.replace("Z", "")` antes de parsear |

---

## 7. Ejemplos de Uso desde n8n

```json
POST /agenda/parsear-fecha
{
  "texto": "el jueves a las 3 de la tarde",
  "zona_horaria": "America/Argentina/Buenos_Aires",
  "fecha_referencia": "2026-02-21"
}
```

```json
POST /agenda/verificar-slot
{
  "fecha_solicitada": "2026-02-26",
  "hora_solicitada": "15:00",
  "duracion_minutos": 60,
  "eventos_existentes": [
    {"titulo": "Reunión con cliente", "inicio": "2026-02-26T14:00:00", "fin": "2026-02-26T15:30:00"}
  ]
}
```

```json
POST /agenda/generar-recordatorio
{
  "cita": {
    "nombre_cliente": "María García",
    "fecha": "26 de febrero de 2026",
    "hora": "15:00",
    "servicio": "Consultoría de automatización",
    "lugar_o_link": "https://meet.google.com/abc-defg-hij"
  },
  "tipo": "recordatorio_24h",
  "brandbook": {"nombre_agencia": "System IA", "tono": "amable y profesional"}
}
```

## 8. Checklist de Pre-Deploy
- [ ] `GEMINI_API_KEY` configurada en Easypanel
- [ ] Test parsear-fecha con "mañana" (debe retornar fecha de mañana)
- [ ] Test parsear-fecha con "el jueves a las 3" (debe retornar próximo jueves 15:00)
- [ ] Test verificar-slot con conflicto real (debe retornar `disponible: false`)
- [ ] Test recordatorio tipo `recordatorio_1h` (tono más urgente)
