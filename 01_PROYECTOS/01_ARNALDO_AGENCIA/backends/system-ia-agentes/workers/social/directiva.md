# DIRECTIVA: WORKER_SOCIAL_MEDIA

> **ID:** WK-SOCIAL-001
> **Script Asociado:** `workers/social/worker.py`
> **Última Actualización:** 2026-02-21
> **Estado:** ACTIVO

---

## 1. Objetivos y Alcance

- **Objetivo Principal:** Generar contenido de redes sociales (IG, LinkedIn, Facebook), imágenes con Gemini, y selección inteligente de temas — todo adaptado al brandbook de cada cliente.
- **Criterio de Éxito:** El endpoint devuelve `{"status": "success"}` con contenido diferenciado por plataforma, correctamente formateado y alineado al tono de la marca.

---

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)

**`POST /social/crear-post`**
- `cliente_id`: str — ID del cliente a buscar en Airtable
- `datos_marca`: list — Array de items enviados por n8n desde Airtable
  - Cada item: `{"json": {"ID Cliente": "...", "Industria": "...", "Tono de Voz": "...", ...}}`

**`POST /social/generar-imagen`**
- `prompt`: str — Descripción visual del contenido a generar
- `estilo`: str — Estilo visual (default: "fotografico, profesional, moderno, sin texto")
- `max_intentos`: int — Reintentos internos (default: 4)
- `espera_segundos`: int — Espera entre reintentos (default: 25)

**`POST /social/seleccionar-tema`**
- `historial_temas`: list[str] — Últimos temas publicados (para evitar repetir)
- `industria`: str — Industria del cliente
- `objetivo_mes`: str — Objetivo de contenido del mes

### Variables de Entorno
- `GEMINI_API_KEY`: API Key de Google Gemini (requerida)

### Salidas (Outputs)

**`/crear-post`:**
```json
{
  "status": "success",
  "resultados": {
    "instagram": "...",
    "linkedin": "...",
    "facebook": "..."
  }
}
```

**`/generar-imagen`:**
```json
{
  "status": "success",
  "base64Image": "...",
  "mimeType": "image/png",
  "intentos": 2
}
```

**`/seleccionar-tema`:**
```json
{
  "status": "success",
  "tema": "...",
  "angulo": "...",
  "idea_central": "...",
  "prompt_imagen": "...",
  "razonamiento": "..."
}
```

---

## 3. Flujo Lógico (Algoritmo)

### `/crear-post`
1. Buscar cliente en el array `datos_marca` por `ID Cliente`
2. Extraer brandbook: industria, servicio, público, tono, reglas, tema, ángulo
3. Construir mega-prompt con instrucciones por red social
4. Llamar Gemini 2.5 Flash — parsear resultado separado por `|||`
5. Retornar objeto con los 3 textos limpios

### `/generar-imagen` (loop interno — resuelve limitación de n8n)
1. Construir prompt completo (descripción + estilo)
2. Loop hasta `max_intentos`:
   - Llamar Gemini 2.0 Flash Image Generation con `responseModalities: ["image", "text"]`
   - Si respuesta contiene `inlineData` → retornar base64 + mimeType + intentos
   - Si no hay imagen → esperar `espera_segundos` y reintentar
3. Si se agotan intentos → retornar error descriptivo

### `/seleccionar-tema`
1. Construir contexto con historial de temas y objetivo del mes
2. Llamar Gemini solicitando JSON con tema + ángulo + prompt de imagen
3. Extraer JSON con regex, parsear y retornar

---

## 4. Herramientas y Librerías

- **FastAPI** + **Pydantic**: Servidor HTTP y validación de inputs
- **requests**: Llamadas a la REST API de Gemini (sin SDK — más control)
- **Gemini 2.5 Flash**: Generación de texto (`gemini-2.5-flash`)
- **Gemini 2.0 Flash Image**: Generación de imágenes (`gemini-2.0-flash-preview-image-generation`)
- **re, json**: Parseo de respuestas JSON de Gemini

---

## 5. Restricciones y Casos Borde

- **Separador `|||`**: Gemini a veces añade texto antes del primer `|||`. El índice `partes[0]` puede tener texto introductorio — hacer `.strip()` siempre.
- **Imagen no generada**: Gemini image generation a veces devuelve solo texto sin `inlineData`. El loop de reintentos cubre este caso.
- **Cliente no encontrado**: Si `cliente_id` no existe en `datos_marca`, retornar error 200 con `status: error` (no lanzar 4xx para que n8n lo maneje).
- **Timeout**: Generación de imagen puede tardar hasta 90s — configurar cliente HTTP con timeout generoso.

---

## 6. Protocolo de Errores y Aprendizajes (Memoria Viva)

| Fecha | Error Detectado | Causa Raíz | Solución/Parche Aplicado |
|-------|-----------------|------------|--------------------------|
| 21/02 | `google-generativeai` SDK no soporta image generation bien en v0.3.2 | SDK desactualizado | Migrado a REST API directa con `requests` |
| 21/02 | n8n no soporta ciclos (loop de imagen) | Arquitectura de n8n | Loop movido al Worker — n8n solo llama 1 vez y espera |

---

## 7. Ejemplos de Uso desde n8n

```json
POST https://tu-worker.easypanel.host/social/crear-post
{
  "cliente_id": "CLI-001",
  "datos_marca": [
    {"json": {"ID Cliente": "CLI-001", "Industria": "Restaurantes", "Tono de Voz": "Cálido y familiar"}}
  ]
}
```

```json
POST https://tu-worker.easypanel.host/social/generar-imagen
{
  "prompt": "Restaurante familiar latinoamericano lleno de vida",
  "estilo": "fotografia profesional, colores cálidos",
  "max_intentos": 4,
  "espera_segundos": 25
}
```

## 8. Checklist de Pre-Deploy
- [ ] `GEMINI_API_KEY` configurada en Easypanel como variable de entorno
- [ ] Endpoint `/health` retorna `gemini_api: configured`
- [ ] Test `/social/seleccionar-tema` con historial vacío
- [ ] Test `/social/generar-imagen` con prompt simple
