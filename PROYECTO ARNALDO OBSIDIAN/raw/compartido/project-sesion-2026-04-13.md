---
name: Sesión épica 2026-04-13
description: Resumen completo de la sesión más larga — cotizador, auditores, roadmap Robert 92%, PostgreSQL, Chatwoot
type: project
originSessionId: 7accf720-af36-49d0-bc07-ba7e60eb27c2
---
## Sesión 2026-04-13 — Resumen completo

### Cotizador v2 (n8n workflow)
- Workflow completo: formulario → Cloudinary (logo) → LLM (Gemini/OpenAI) → Gotenberg (PDF) → cambios iterativos
- Gotenberg instalado en Coolify Arnaldo (PDF gratis ilimitado, UUID: fl3d98h92norx84xv88h0wek)
- Logo se sube como archivo, se procesa a Cloudinary automáticamente
- Backticks limpiados en HTML to File nodes
- Workflow ID: lSuj7CZLi3yW61eh

### Auditoría corregida
- 3 falsos positivos arreglados (YCloud phoneNumber, Evolution Instance, Meta token skip)
- Fase 2 migrada de 9 nodos complejos a 2 (Schedule → HTTP Request al endpoint /auditor/fase2)
- Endpoint envía Telegram directo (n8n sandbox bloquea $env)
- EVOLUTION_INSTANCE eliminada de Coolify
- Guardia crítica: agregados n8n Mica + n8n Lovbot (5 servicios cada 5 min)

### Roadmap Robert — 92% completado (59/64 items)
- Documento: 01_PROYECTOS/03_LOVBOT_ROBERT/docs/AGENTE-AI-INMOBILIARIO-ROADMAP.md
- GPT-4o principal + Gemini 2.5 Flash fallback
- Conversación natural (_interpretar_respuesta con GPT-4o)
- Caso A (Meta Ads referral) + Caso B (genérico)
- 2 propiedades iniciales ("+" para ver más)
- Pipeline CRM 9 estados
- Pausa/retoma bot con Chatwoot (labels automáticos)
- Seguimiento 5 puntos + nurturing 6 mensajes quincenales
- Detección caída (30 min timeout) + modo recuperación
- Historial conversación guardado en Airtable/PostgreSQL
- Endpoint métricas + filtros CRM + dashboard dinámico
- Cal.com timezone configurable
- Fix: Cal.com siempre para leads calientes sin propiedades

### Chatwoot integrado
- Token: vtZPAnRwKMhATa4k2A5kcGKL (guardado en .env + Coolify)
- Account ID: 2, Inbox WhatsApp ID: 4
- Labels automáticos: caliente/tibio/frio + atiende-humano + automatizacion
- Webhook configurado: conversation_status_changed + conversation_updated
- Bridge: _chatwoot_escalar() agrega labels + nota privada con historial

### PostgreSQL Lovbot CRM
- Servicio creado en Coolify Robert (Hetzner): UUID p8s8kcgckgoc484wwo4w8wck
- Container: lovbot-postgres-p8s8kcgckgoc484wwo4w8wck
- DB: lovbot_crm | User: lovbot | Pass: 9C7i82bFVoscycGCF6f7XPbZyNpWvEXa
- Tablas: leads, propiedades, clientes_activos (con índices + triggers updated_at)
- Multi-tenant via tenant_slug
- db_postgres.py: módulo completo con misma interfaz que Airtable
- Worker: USE_POSTGRES flag — PostgreSQL principal, Airtable fallback
- Endpoints CRM actualizados para usar PostgreSQL

### Workflows n8n — limpieza
- Eliminados: Keep-Alive Render, Monitor YCloud, Monitor Arnaldo (redundantes)
- Quedan 8 workflows limpios (7 + Onboarding)
- Workflow Onboarding creado: formulario → POST /admin/onboard
- Fix alerta cuotas Maicol: URL Render→Coolify, YCloud API key corregida

### Pendiente próxima sesión
1. Ejecutar migración datos Airtable → PostgreSQL: GET /admin/migrar-airtable (desde agentes.lovbot.ai)
2. CRUD editable en CRM HTML (crear/editar/eliminar leads y propiedades)
3. Upload imágenes propiedades via Cloudinary desde CRM
4. Probar bot completo con GPT-4o + PostgreSQL end-to-end
5. Verificar Cal.com ofrece slots cuando no hay propiedades
6. Items faltantes del roadmap: WhatsApp botones (7.2), Meta Ads Lead Forms (7.5), Landing (7.6)
7. Considerar migrar worker de Robert a su propio repo/FastAPI separado

### Deploy pendiente
- Coolify Robert: deploy en cola (UUID: v4c40s04goowo004wcok44kk)
- Después del deploy: ejecutar GET /admin/migrar-airtable para copiar datos
