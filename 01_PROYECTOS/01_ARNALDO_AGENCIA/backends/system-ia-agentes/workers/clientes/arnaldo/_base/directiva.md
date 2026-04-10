# DIRECTIVA: WORKER BASE ARNALDO (YCloud)

> **ID:** arnaldo-base-2026-04-06
> **Script Asociado:** `workers/clientes/arnaldo/_base/worker_base.py`
> **Última Actualización:** 2026-04-06
> **Estado:** ACTIVO

---

## 1. Objetivos y Alcance
- **Objetivo Principal:** Template reutilizable para todos los clientes del proyecto Arnaldo
- **Criterio de Éxito:** Al copiar y personalizar, un nuevo cliente queda operativo en <30 min

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)
- **Webhook YCloud:** POST con `whatsappInboundMessage` (from, text, customerProfile, id)
- **Webhook Chatwoot:** POST con `message_created` (content, conversation.contact.phone_number)

### Salidas (Outputs)
- **WhatsApp:** Mensajes vía YCloud API (`api.ycloud.com/v2/whatsapp/messages`)
- **Chatwoot:** Sync bidireccional (incoming + outgoing) en `chatwoot.arnaldoayalaestratega.cloud`

### Variables de Entorno
| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini (compartida) |
| `YCLOUD_API_KEY_{SLUG}` | API key YCloud por cliente |
| `NUMERO_BOT_{SLUG}` | Número WhatsApp del bot |
| `NUMERO_ASESOR_{SLUG}` | Número del asesor humano |
| `CHATWOOT_API_TOKEN_{SLUG}` | Token Chatwoot por cliente |
| `CHATWOOT_INBOX_ID_{SLUG}` | Inbox Chatwoot por cliente |

## 3. Flujo Lógico
1. YCloud envía mensaje al webhook
2. Se parsea (from, text, nombre, msg_id)
3. Se muestra typing indicator
4. `_procesar_mensaje()` genera respuesta
5. Se envía respuesta vía YCloud
6. Se sincroniza con Chatwoot (incoming + outgoing)

## 4. Herramientas y Librerías
- `fastapi`, `requests`, `google-genai`, `re`, `logging`

## 5. Para crear nuevo cliente
1. `cp -r _base/ ../nombre-cliente/`
2. Editar `CLIENTE_SLUG`, `CLIENTE_TAG`, `CONFIG_NEGOCIO`
3. Personalizar `MSG_BIENVENIDA`, `PROMPT_GEMINI`, `_procesar_mensaje()`
4. Agregar env vars en Coolify/Render
5. Registrar router en `main.py`

## 6. Protocolo de Errores
| Fecha | Error | Causa | Solución |
|-------|-------|-------|----------|
| — | — | — | — |
