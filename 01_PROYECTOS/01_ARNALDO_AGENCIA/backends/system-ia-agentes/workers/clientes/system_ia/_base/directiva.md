# DIRECTIVA: WORKER BASE SYSTEM IA / MICA (Evolution API)

> **ID:** system-ia-base-2026-04-06
> **Script Asociado:** `workers/clientes/system-ia/_base/worker_base.py`
> **Última Actualización:** 2026-04-06
> **Estado:** ACTIVO (Evolution API — futuro migración a Meta Tech Provider)

---

## 1. Objetivos y Alcance
- **Objetivo Principal:** Template reutilizable para clientes de System IA (Arnaldo + Micaela)
- **Criterio de Éxito:** Al copiar y personalizar, un nuevo cliente queda operativo en <30 min

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)
- **Webhook Evolution API:** POST con estructura:
  `{data: {key: {remoteJid}, message: {conversation}, pushName}}`
- **Webhook Chatwoot:** POST con `message_created` (futuro)

### Salidas (Outputs)
- **WhatsApp:** Mensajes vía Evolution API (`/message/sendText/{instance}`)
- **Chatwoot:** Por definir (instancia propia de System IA)

### Variables de Entorno
| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini (compartida) |
| `EVOLUTION_API_URL` | URL base de Evolution API |
| `EVOLUTION_API_KEY_{SLUG}` | API key por instancia/cliente |
| `EVOLUTION_INSTANCE_{SLUG}` | Nombre de instancia Evolution |
| `NUMERO_ASESOR_{SLUG}` | Número del asesor humano |
| `CHATWOOT_URL_SYSTEMIA` | URL Chatwoot System IA (por definir) |
| `CHATWOOT_API_TOKEN_{SLUG}` | Token Chatwoot por cliente |
| `CHATWOOT_INBOX_ID_{SLUG}` | Inbox Chatwoot por cliente |

## 3. Flujo Lógico
1. Evolution API envía evento al webhook
2. Se parsea (remoteJid → teléfono, conversation → texto, pushName → nombre)
3. `_procesar_mensaje()` genera respuesta
4. Se envía respuesta vía Evolution API
5. Se sincroniza con Chatwoot (cuando esté configurado)

## 4. Funciones de Evolution API
- `_enviar_texto()` — `/message/sendText/{instance}`
- `_enviar_imagen()` — `/message/sendMedia/{instance}`

## 5. Herramientas y Librerías
- `fastapi`, `requests`, `google-genai`, `re`, `logging`

## 6. Nota sobre migración futura
Mica está en camino a ser Meta Tech Provider propia. Cuando eso ocurra:
- Cambiar `_enviar_texto()` y `_enviar_imagen()` a Meta Graph API (igual que Lovbot)
- Actualizar variables de entorno
- El resto del worker (Gemini, Chatwoot, procesador) no cambia

## 7. Para crear nuevo cliente
1. `cp -r _base/ ../nombre-cliente/`
2. Editar `CLIENTE_SLUG`, `CLIENTE_TAG`, `CONFIG_NEGOCIO`
3. Personalizar `MSG_BIENVENIDA`, `PROMPT_GEMINI`, `_procesar_mensaje()`
4. Crear instancia en Evolution API
5. Agregar env vars
6. Registrar router en `main.py`

## 8. Protocolo de Errores
| Fecha | Error | Causa | Solución |
|-------|-------|-------|----------|
| — | — | — | — |
