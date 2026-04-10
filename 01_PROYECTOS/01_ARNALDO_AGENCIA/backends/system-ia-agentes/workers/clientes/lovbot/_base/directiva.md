# DIRECTIVA: WORKER BASE LOVBOT / ROBERT (Meta Graph API)

> **ID:** lovbot-base-2026-04-06
> **Script Asociado:** `workers/clientes/lovbot/_base/worker_base.py`
> **Última Actualización:** 2026-04-06
> **Estado:** ACTIVO

---

## 1. Objetivos y Alcance
- **Objetivo Principal:** Template reutilizable para todos los clientes del proyecto Lovbot (alianza Arnaldo + Robert)
- **Criterio de Éxito:** Al copiar y personalizar, un nuevo cliente queda operativo en <30 min

## 2. Especificaciones de Entrada/Salida (I/O)

### Entradas (Inputs)
- **Webhook n8n:** POST desde WF4 "Eventos de mensajes" con JSON normalizado:
  `{from, text, phone_number_id, message_type, message_id, client_name}`
- **Webhook Chatwoot:** POST con `message_created` desde `chatwoot.lovbot.ai`

### Salidas (Outputs)
- **WhatsApp:** Mensajes vía Meta Graph API (`graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages`)
- **Chatwoot:** Sync bidireccional en `chatwoot.lovbot.ai`

### Variables de Entorno
| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini (compartida) |
| `META_PHONE_ID_{SLUG}` | Phone Number ID de Meta por cliente |
| `META_TOKEN_{SLUG}` | Access token permanente (generado por WF2) |
| `NUMERO_ASESOR_{SLUG}` | Número del asesor humano |
| `CHATWOOT_URL_LOVBOT` | URL Chatwoot Lovbot (chatwoot.lovbot.ai) |
| `CHATWOOT_API_TOKEN_{SLUG}` | Token Chatwoot por cliente |
| `CHATWOOT_ACCOUNT_ID_LOVBOT` | Account ID en Chatwoot Lovbot |
| `CHATWOOT_INBOX_ID_{SLUG}` | Inbox Chatwoot por cliente |

## 3. Flujo Lógico
1. Meta envía evento a n8n WF4
2. WF4 parsea y rutea al worker según `phone_number_id`
3. Worker recibe JSON normalizado
4. Marca mensaje como leído (check azul) vía Meta API
5. `_procesar_mensaje()` genera respuesta
6. Se envía respuesta vía Meta Graph API
7. Se sincroniza con Chatwoot lovbot.ai

## 4. Funciones exclusivas de Meta Graph API
- `_enviar_texto()` — Mensaje de texto
- `_enviar_imagen()` — Imagen con caption
- `_enviar_template()` — Plantillas de marketing/recordatorios
- `_marcar_leido()` — Double check azul

## 5. Herramientas y Librerías
- `fastapi`, `requests`, `google-genai`, `re`, `logging`

## 6. Arquitectura de clientes
- **Cliente chico:** misma VPS, WF4 rutea por phone_number_id al worker
- **Cliente grande:** VPS dedicada, WF5 Override redirige a su instancia n8n propia

## 7. Para crear nuevo cliente
1. `cp -r _base/ ../nombre-cliente/`
2. Editar `CLIENTE_SLUG`, `CLIENTE_TAG`, `CONFIG_NEGOCIO`
3. Personalizar `MSG_BIENVENIDA`, `PROMPT_GEMINI`, `_procesar_mensaje()`
4. Agregar env vars en Coolify de Robert
5. Registrar router en `main.py`
6. Agregar entry en tabla CLIENTES del nodo "Router por Cliente" en WF4

## 8. Protocolo de Errores
| Fecha | Error | Causa | Solución |
|-------|-------|-------|----------|
| — | — | — | — |
