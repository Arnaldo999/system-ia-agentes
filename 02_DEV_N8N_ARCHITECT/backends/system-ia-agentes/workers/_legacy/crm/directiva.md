# DIRECTIVA: WORKER_CRM

> **ID:** WK-CRM-001
> **Script Asociado:** `workers/crm/worker.py`
> **Última Actualización:** 2026-02-21
> **Estado:** ACTIVO

---

## 1. Objetivos y Alcance

- **Objetivo Principal:** Calificar leads automáticamente con score IA, enriquecer perfiles incompletos, y generar mensajes de seguimiento personalizados que no suenen a template de CRM.
- **Criterio de Éxito:** El score del lead refleja la realidad comercial (validado manualmente en las primeras semanas). Los mensajes de seguimiento tienen tasa de respuesta >30%.

---

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)

**`POST /crm/calificar-lead`**
- `nombre`: str
- `empresa`: str
- `industria`: str
- `mensaje_inicial`: str — Primer mensaje enviado por el lead
- `fuente`: str — Canal de origen (instagram, whatsapp, referido, web)
- `historial_interacciones`: list[str] — Resúmenes de interacciones previas
- `presupuesto_indicado`: str — Si el lead mencionó un presupuesto
- `cantidad_empleados`: str

**`POST /crm/enriquecer-lead`**
- `datos_actuales`: dict — Datos parciales del lead
- `contexto_conversacion`: str — Extracto de la conversación para inferir datos

**`POST /crm/generar-seguimiento`**
- `lead`: dict — Datos completos del lead
- `etapa_pipeline`: str — `nuevo|contactado|propuesta_enviada|negociacion|cerrado_perdido`
- `dias_sin_respuesta`: int
- `ultimo_contacto`: str — Descripción del último contacto
- `brandbook`: dict — `{nombre_agencia, tono}`

### Variables de Entorno
- `GEMINI_API_KEY`: requerida

### Salidas (Outputs)

**`/calificar-lead`:**
```json
{
  "status": "success",
  "temperatura": "tibio",
  "score": 6,
  "potencial_negocio": "alto",
  "urgencia_compra": "evaluando",
  "objeciones_probables": ["precio", "tiempo de implementación"],
  "siguiente_accion": "Enviar caso de éxito de un restaurante similar",
  "razonamiento": "Tiene necesidad clara pero no hay urgencia definida."
}
```

**`/enriquecer-lead`:**
```json
{
  "status": "success",
  "datos_enriquecidos": {
    "industria_inferida": "Gastronomía",
    "tamano_empresa": "pequena",
    "rol_contacto": "Dueño",
    "pain_points_probables": ["gestión manual de reservas", "respuesta lenta en WhatsApp"],
    "servicios_relevantes": ["agendamiento", "whatsapp"],
    "canal_preferido": "whatsapp",
    "nivel_madurez_digital": "basico",
    "confianza_inferencia": "alta"
  }
}
```

---

## 3. Flujo Lógico (Algoritmo)

### Flujo típico en n8n
```
Lead entra por WhatsApp/IG →
  [POST /crm/calificar-lead] →
  [POST /crm/enriquecer-lead] →
  Guardar en CRM (Airtable/Notion) →
  Si temperatura = "caliente" → Notificar vendedor
  Si temperatura = "tibio" → [POST /crm/generar-seguimiento] automático en 2 días
```

### `/calificar-lead`
1. Construir contexto completo del lead
2. Prompt especializado en ventas B2B LATAM de automatización
3. Gemini devuelve JSON con score + metadatos comerciales
4. Extraer y retornar

### `/enriquecer-lead`
1. Serializar datos actuales como JSON en el prompt
2. Gemini infiere solo lo deducible con alta confianza
3. Nunca inventar — si no se puede inferir, dejar vacío
4. Retornar datos enriquecidos separados de los originales

### `/generar-seguimiento`
1. Serializar datos del lead
2. Aplicar contexto según etapa del pipeline
3. Calcular `tono_recomendado` según `dias_sin_respuesta` (0-2: normal, 3-7: persistente_amable, 8+: ultimo_intento)
4. Gemini genera mensaje específico y personalizado

---

## 4. Herramientas y Librerías

- **FastAPI** + **Pydantic**: API endpoint
- **requests**: REST API de Gemini
- **Gemini 2.5 Flash**: Scoring, enriquecimiento, generación de mensajes
- **re, json**: Parseo

---

## 5. Restricciones y Casos Borde

- **Score subjetivo**: El score de Gemini es indicativo, no absoluto. Validar con el equipo de ventas las primeras semanas.
- **Enriquecimiento**: Si los datos actuales son muy escasos (solo nombre y teléfono), el enriquecimiento tendrá `confianza_inferencia: "baja"`. Usar con cautela.
- **Mensaje de seguimiento**: Para `cerrado_ganado`, no aplica seguimiento de ventas — usar para onboarding.
- **Privacidad**: No almacenar datos de leads en el Worker — solo procesar y retornar.

---

## 6. Protocolo de Errores y Aprendizajes (Memoria Viva)

| Fecha | Error Detectado | Causa Raíz | Solución/Parche Aplicado |
|-------|-----------------|------------|--------------------------|
| 21/02 | Gemini a veces devuelve score fuera de rango (0 o 11) | El modelo no siempre respeta rangos numéricos | Agregar validación: `max(1, min(10, parsed["score"]))` si es crítico |

---

## 7. Ejemplos de Uso desde n8n

```json
POST /crm/calificar-lead
{
  "nombre": "Carlos",
  "empresa": "Cafetería Don Carlos",
  "industria": "Gastronomía",
  "mensaje_inicial": "vi tu publicación sobre WhatsApp automático, me interesa",
  "fuente": "instagram",
  "historial_interacciones": ["Respondió rápido al primer mensaje", "Preguntó por precio"],
  "presupuesto_indicado": ""
}
```

```json
POST /crm/generar-seguimiento
{
  "lead": {"nombre": "Carlos", "empresa": "Cafetería Don Carlos", "industria": "Gastronomía"},
  "etapa_pipeline": "propuesta_enviada",
  "dias_sin_respuesta": 4,
  "brandbook": {"nombre_agencia": "System IA", "tono": "cercano y profesional"}
}
```

## 8. Checklist de Pre-Deploy
- [ ] `GEMINI_API_KEY` configurada en Easypanel
- [ ] Test con lead con datos mínimos (solo nombre + mensaje)
- [ ] Test con lead completo (verificar que score sea coherente)
- [ ] Test de seguimiento con 0 días y con 10 días (verificar diferencia de tono)
