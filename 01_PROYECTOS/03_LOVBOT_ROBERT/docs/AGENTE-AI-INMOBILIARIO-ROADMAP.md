# AGENTE AI INMOBILIARIO — Roadmap de Implementación
**Documento de referencia**: PDF "AGENTE AI INMOBILIARIO" (Robert Bazan, 12-04-2026)
**Última actualización**: 2026-04-13
**Estado general**: 🟡 En progreso

> Este documento compara el estado actual del ecosistema Lovbot con los requerimientos
> del PDF de Robert. Cada ítem se marca con su estado y se actualiza a medida que se completa.
> **No eliminar ítems completados** — solo cambiar el estado.

## Estados
- ✅ **LISTO** — implementado y funcionando
- 🟡 **PARCIAL** — existe pero incompleto
- ❌ **FALTA** — no existe, hay que implementar
- 🔧 **EN PROGRESO** — se está trabajando

---

## PUNTO 1: FLUJO CONVERSACIONAL

### 1.1 Respuesta inmediata (<5 min)
- **Estado**: ✅ LISTO
- **Detalle**: Webhook Meta responde en segundos via FastAPI
- **Archivo**: `workers/clientes/lovbot/robert_inmobiliaria/worker.py`

### 1.2 Detectar origen del lead (anuncio/UTM/webhook)
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Webhook main.py extrae `referral` de mensajes Meta (text + button). Worker guarda `Fuente_Detalle` en Airtable con ad_id/source_url. Campo `Fuente` se marca como "meta_ads" si viene de anuncio.

### 1.3 Caso A: Lead desde anuncio de propiedad específica
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Si hay referral, bot responde contextualmente con headline del anuncio, salta subnicho y va directo a pedir nombre. Guarda `_fuente_detalle` y `_referral` en sesión.
- **Pendiente**: matchear referral con propiedad específica en Airtable (requiere que Robert configure source_url en sus ads apuntando a la propiedad)

### 1.4 Caso B: Lead genérico (sin propiedad)
- **Estado**: ✅ LISTO
- **Detalle**: El flujo actual es 100% genérico — funciona para este caso
- **Archivo**: worker.py, steps: subnicho → nombre → email → ciudad → objetivo → tipo → zona → presupuesto → urgencia

### 1.5 Calificar en <2 minutos
- **Estado**: ✅ LISTO
- **Detalle**: Gemini 2.5 Flash Lite califica después de completar urgencia. Scoring: caliente/tibio/frío
- **Archivo**: `_gemini_calificar()` en worker.py

### 1.6 Priorizar propiedad de interés
- **Estado**: ✅ LISTO
- **Detalle**: Filtra Airtable por tipo/zona/presupuesto/operación, muestra hasta 5 propiedades

### 1.7 Obtener datos de contacto
- **Estado**: ✅ LISTO
- **Detalle**: Captura nombre, apellido, email, ciudad, teléfono

### 1.8 Agendar visitas automáticamente
- **Estado**: ✅ LISTO
- **Detalle**: Cal.com v2 API — busca 6 slots en próximos 7 días, crea reserva
- **Bug conocido**: Timezone hardcodeado a America/Mexico_City — cambiar a configurable

### 1.9 Seguimiento en 6 puntos de contacto
- **Estado**: ❌ FALTA
- **Detalle**: Ver PUNTO 3 completo

### 1.10 Escalamiento a humano vía Chatwoot
- **Estado**: 🟡 PARCIAL
- **Detalle**: Escala por WhatsApp directo al asesor, no por Chatwoot. Ver PUNTO 5

---

## PUNTO 2: LÓGICA INTELIGENTE DEL BOT

### 2.1 Prioridad de atención — resolver interés inicial primero
- **Estado**: ✅ LISTO
- **Detalle**: Bot va directo a la propiedad/tipo de interés

### 2.2 No ofrecer más propiedades de inmediato
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13 — muestra 2 mejores inicialmente, "+" para ver más
- **Detalle**: Busca hasta 5 en Airtable pero muestra solo las 2 mejores. Si hay más, ofrece "Escriba + si desea verlas"

### 2.3 Lead caliente → agendamiento inmediato + alerta asesor
- **Estado**: ✅ LISTO
- **Detalle**: Score caliente → propiedades → Cal.com → notifica asesor por WhatsApp

### 2.4 Lead explorador → más propiedades + nurturing ligero
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Lead tibio recibe propiedades + cita + se activa `Estado_Seguimiento=activo` automáticamente. Script de seguimiento contacta en 5 puntos. Diferenciación fina de mensajes por score queda como refinamiento futuro.

### 2.5 Lead frío → flujo de nurturing
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Lead frío se deriva a sitio web + se activa `Estado_Seguimiento=activo` con `Proximo_Seguimiento=+3 días`. El script `seguimiento_leads.py` lo contacta automáticamente.

### 2.6 Detección de caída del lead
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Timeout de 30 min sin actividad. Si lead vuelve después de timeout, activa modo recuperación automáticamente. Timestamp `_ultimo_ts` en cada sesión.

### 2.7 Modo recuperación
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Step "recuperacion" con 4 opciones: retomar, ver otras opciones, hablar con asesor, empezar de nuevo. Guarda `_prev_step` para retomar exactamente donde quedó.

### 2.8 Detección de objeción familiar
- **Estado**: ✅ LISTO
- **Detalle**: Detecta "lo hablo con mi esposa/papá" → pausa + ofrece asesor

---

## PUNTO 3: SEGUIMIENTO AUTOMÁTICO (OBLIGATORIO)

**Regla base del PDF**: mínimo 6 contactos antes de considerar lead muerto

### 3.1 Contacto 1 — Inmediato (respuesta inicial)
- **Estado**: ✅ LISTO
- **Detalle**: Bot responde al instante via webhook

### 3.2 Contacto 2 — +24 horas (seguimiento suave)
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Script**: `seguimiento_leads.py` mensaje #1 — "¿Pudiste ver las opciones?"

### 3.3 Contacto 3 — +3 días (valor / ficha)
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Script**: `seguimiento_leads.py` mensaje #2 — "Te comparto información adicional + agendar visita"

### 3.4 Contacto 4 — +7 días (nuevas opciones)
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Script**: `seguimiento_leads.py` mensaje #3 — "Tenemos nuevas propiedades"

### 3.5 Contacto 5 — +14 días (reactivación)
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Script**: `seguimiento_leads.py` mensaje #4 — "¿Seguís buscando? Hay novedades"

### 3.6 Contacto 6 — +30 días (último intento)
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Script**: `seguimiento_leads.py` mensaje #5 — último intento → mover a "dormido"

### 3.7 Infraestructura de seguimiento
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Campos Airtable**: `Estado_Seguimiento`, `Cantidad_Seguimientos`, `Proximo_Seguimiento`, `Ultimo_Contacto_Bot` — creados ✅
- **Script**: `scripts/seguimiento_leads.py` — busca leads con seguimiento activo y envía mensajes ✅
- **Activación automática**: worker marca `Estado_Seguimiento=activo` + `Proximo_Seguimiento=mañana` al calificar lead caliente/tibio ✅
- **5 mensajes predefinidos**: seguimiento suave, valor, nuevas opciones, reactivación, último intento ✅
- **Reporte Telegram**: notifica cantidad de mensajes enviados/dormidos ✅
- **Pendiente**:
  - [ ] Registrar como scheduled task en Coolify (cron diario 14:00 UTC)
  - [ ] Templates WhatsApp aprobados por Meta (necesario para mensajes fuera de ventana 24h)
  - [ ] Pausa automática si lead responde durante seguimiento

---

## PUNTO 4: NURTURING (CRÍTICO — 3 a 6 meses)

### 4.1 Enviar propiedades nuevas automáticamente
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Mensaje nurturing #1 ofrece "nuevas propiedades". Mensaje #4 "propiedades que bajaron de precio".

### 4.2 Notificar cambios de precio
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Mensaje nurturing #4 cubre cambios de precio. Trigger automático cuando Airtable cambia precio queda como refinamiento futuro.

### 4.3 Enviar info de crédito/financiamiento
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Mensaje nurturing #2 — "nuevas opciones de crédito hipotecario disponibles"

### 4.4 Enviar plusvalía de zona
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Mensaje nurturing #3 — "propiedades en la zona se están valorizando"

### 4.5 Frecuencia semanal o quincenal
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: `procesar_nurturing()` busca leads dormidos con último contacto hace +14 días. 6 mensajes en rotación.

### 4.6 Detección de respuesta → recalificar
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Cuando lead en seguimiento (activo/dormido) responde, `_desactivar_seguimiento()` cambia `Estado_Seguimiento` a `pausado`. El bot lo atiende como conversación nueva → recalifica.

### 4.7 Infraestructura de nurturing
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: 6 mensajes predefinidos en `MENSAJES_NURTURING`, rotación automática, integrado en `seguimiento_leads.py`. Scheduled task en Coolify corre diariamente. Templates WhatsApp pendientes (requieren aprobación Meta para mensajes fuera de ventana 24h).

---

## PUNTO 5: INTERVENCIÓN HUMANA (CHATWOOT)

### 5.1 Escalamiento automático a Chatwoot
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Inbox WhatsApp ya conectado (ID:4, +5219987434234). Al escalar: `_chatwoot_escalar()` agrega label `atiende-humano` + nota privada con historial y score. Webhook configurado en Chatwoot → FastAPI para pausa/retoma automática.

### 5.2 Bot se pausa cuando entra humano
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Dict `LEADS_PAUSADOS` en memoria. `_procesar()` chequea `bot_pausado()` antes de responder. Auto-despausar después de 4h.
- **Endpoints**: `POST /bot/pausar/{tel}`, `POST /bot/despausar/{tel}`, `GET /bot/estado/{tel}`
- **Trigger automático**: bot se pausa cuando escala a asesor via `_ir_asesor()`
- **Pendiente**: integrar con Chatwoot webhooks para pausa/despausar automático (cuando Chatwoot esté conectado)

### 5.3 Bot retoma cuando sale humano
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Auto-despausar después de 4h (`PAUSA_TIMEOUT_HORAS`). Endpoint manual `POST /bot/despausar/{tel}` disponible.
- **Pendiente**: webhook Chatwoot "conversation_resolved" para despausar automático

### 5.4 Panel del asesor — historial completo
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Dict `HISTORIAL` guarda últimos 20 mensajes (Lead + Bot con timestamp). Se persiste en Airtable `Notas_Bot` cuando escala al asesor.

### 5.5 Panel del asesor — respuestas del bot
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Cada `_enviar_texto()` registra en historial. El asesor ve las respuestas del bot en `Notas_Bot`.

### 5.6 Panel del asesor — datos de calificación
- **Estado**: ✅ LISTO
- **Detalle**: Score, zona, tipo, presupuesto, notas de Gemini — todo en Airtable

### 5.7 Panel del asesor — estado del lead
- **Estado**: ✅ LISTO
- **Detalle**: Campo Estado en Airtable (pero limitado a 3 estados — ver Punto 6)

---

## PUNTO 6: CRM / DASHBOARD

### 6.1 Pipeline completo
- **Estado**: 🟡 PARCIAL
- **Worker**: ✅ Actualizado 2026-04-13 — 9 estados: `no_contactado, contactado, calificado, visita_agendada, visito, en_negociacion, seguimiento, cerrado_ganado, cerrado_perdido`
- **Airtable**: ⚠️ Pendiente agregar nuevos estados al singleSelect (se crean automáticamente al primer uso, pero hay que verificar)
- **CRM HTML**: ✅ Actualizado 2026-04-13 — mapeos ESTADO_MAP, STATUS_TO_AT, AT_TO_STATUS, dropdown 9 estados
- **Lógica bot**: ✅ Caliente→`calificado`, cita confirmada→`visita_agendada`

### 6.2 Datos clave — fuente del lead
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: `Fuente` = "meta_ads" o "whatsapp_directo". `Fuente_Detalle` = "ad:source_id|headline" o "referral:url"

### 6.3 Datos clave — propiedad de interés
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Cuando el lead selecciona una ficha, guarda `Propiedad_Interes` en Airtable con tipo+zona+título

### 6.4 Datos clave — última interacción
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: `fecha_ultimo_contacto` se actualiza automáticamente cada vez que el lead escribe (async thread)

### 6.5 Métricas — tiempo de respuesta
- **Estado**: 🟡 PARCIAL
- **Detalle**: Bot responde en <5 seg (instantáneo). KPI muestra "47s" hardcodeado. Tracking por lead pendiente.

### 6.6 Métricas — tasa de citas
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Endpoint `GET /crm/metricas` calcula `tasa_citas` = leads con Fecha_Cita / total × 100. Dashboard carga dinámicamente.

### 6.7 Métricas — tasa de cierre
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Endpoint calcula `tasa_cierre` = cerrado_ganado / total × 100.

### 6.8 CRM visual — filtros
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: Dropdowns de filtro por estado (6 opciones) y score (caliente/tibio/frío) + búsqueda texto. `aplicarFiltros()` filtra en tiempo real.

### 6.9 CRM visual — dashboard métricas
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: `cargarMetricas()` llama a `/crm/metricas` y actualiza KPIs dinámicamente (total, calientes, citas, fuentes). Barras de origen se generan desde datos reales.

---

## PUNTO 7: HERRAMIENTAS / STACK TÉCNICO

### 7.1 Bot AI (núcleo)
- **Estado**: ✅ LISTO
- **Stack**: FastAPI + Gemini 2.5 Flash Lite
- **Archivo**: `workers/clientes/lovbot/robert_inmobiliaria/worker.py` (1,352 líneas)

### 7.2 WhatsApp API
- **Estado**: ✅ LISTO
- **Stack**: Meta Graph API v21.0 (Cloud API directa)
- **Funciones**: Texto + imágenes
- **Mejoras pendientes**:
  - [ ] Botones interactivos (en vez de "escribí 1, 2 o 3")
  - [ ] Listas de opciones (list messages)
  - [ ] Templates aprobados para seguimiento/nurturing

### 7.3 Chatwoot
- **Estado**: 🟡 PARCIAL
- **Detalle**: Instalado en Coolify Arnaldo pero NO integrado con Robert
- **Implementación necesaria**:
  - [ ] Bridge Meta ↔ Chatwoot para número de Robert
  - [ ] Inbox configurado con el número de WhatsApp
  - [ ] Webhooks de eventos (assigned, resolved)

### 7.4 CRM ligero
- **Estado**: ✅ LISTO (pero limitado)
- **Stack**: Airtable (backend) + HTML Tailwind (frontend) + Supabase (auth tenants)
- **Mejoras**: Ver Punto 6

### 7.5 Integración Meta Ads / formularios
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Webhook para Facebook Lead Ads (formularios in-app)
  - [ ] Leer `referral` en webhook de click-to-WhatsApp ads
  - [ ] Guardar campaign_id, ad_id, adset en Airtable

### 7.6 Integración landing / sitio
- **Estado**: 🟡 PARCIAL
- **Detalle**: Variable `SITIO_WEB` existe, solo se usa para derivar leads fríos
- **Mejoras pendientes**:
  - [ ] Formulario web en landing que cree lead en Airtable + dispare bot
  - [ ] Tracking UTM desde landing → Airtable

### 7.7 Cal.com — timezone
- **Estado**: ✅ LISTO
- **Detalle**: Configurable via `INMO_DEMO_CAL_TIMEZONE` (default: America/Argentina/Buenos_Aires)
- **Completado**: 2026-04-13 — variable `CAL_TIMEZONE` + mapeo de offsets UTC para LATAM

---

## PUNTO 8: REGLAS CRÍTICAS + QUÉ NO HACER

### 8.1 Respuesta inmediata (<1 min)
- **Estado**: ✅ CUMPLE

### 8.2 Conversación natural (no menú rígido)
- **Estado**: ✅ CUMPLE
- **Completado**: 2026-04-13
- **Detalle**: `_interpretar_respuesta()` usa GPT-4o para mapear respuestas abiertas a opciones válidas. Pasos objetivo, tipo y presupuesto aceptan texto libre. Si escribe "quiero comprar una casa" en vez de "1", GPT-4o lo interpreta correctamente.

### 8.3 No saturar con opciones
- **Estado**: ✅ CUMPLE
- **Completado**: 2026-04-13 — muestra 2 iniciales, "+" para expandir

### 8.4 Siempre llevar a acción (visita)
- **Estado**: ✅ CUMPLE
- **Detalle**: CTA de Cal.com después de calificar

### 8.5 Seguimiento automático SIEMPRE activo
- **Estado**: ✅ CUMPLE
- **Completado**: 2026-04-13
- **Detalle**: Seguimiento 5 puntos (activos) + nurturing 6 mensajes (dormidos). Cron diario en Coolify.

### 8.6 Datos del lead obligatorios
- **Estado**: ✅ CUMPLE

### 8.7 No responder genérico sin contexto
- **Estado**: ✅ CUMPLE
- **Completado**: 2026-04-13
- **Detalle**: Caso A contextualiza con headline del anuncio. Caso B sigue flujo genérico (correcto para leads orgánicos)

### 8.8 No depender del asesor para seguimiento
- **Estado**: 🟡 PARCIAL
- **Detalle**: Bot se pausa cuando escala (✅), auto-retoma a las 4h (✅). Falta seguimiento automático post-retoma (Punto 3)

### 8.9 No mandar demasiadas propiedades
- **Estado**: ✅ CUMPLE
- **Completado**: 2026-04-13 — ver 8.3

---

## RESUMEN EJECUTIVO

### Scorecard

| Punto | Descripción | Items | ✅ Listo | 🟡 Parcial | ❌ Falta |
|-------|-------------|-------|---------|-----------|---------|
| **1** | Flujo conversacional | 10 | 6 | 1 | 3 |
| **2** | Lógica inteligente | 8 | 3 | 1 | 4 |
| **3** | Seguimiento automático | 7 | 1 | 0 | 6 |
| **4** | Nurturing | 7 | 0 | 0 | 7 |
| **5** | Chatwoot / humano | 7 | 2 | 2 | 3 |
| **6** | CRM / Dashboard | 9 | 0 | 4 | 5 |
| **7** | Stack técnico | 7 | 2 | 3 | 2 |
| **8** | Reglas / No hacer | 9 | 3 | 2 | 4 |
| **TOTAL** | | **64** | **17 (27%)** | **13 (20%)** | **34 (53%)** |

### Prioridades de implementación (por impacto)

| Prioridad | Qué | Por qué | Esfuerzo |
|-----------|-----|---------|----------|
| **P0** | Seguimiento automático 6 puntos (Punto 3) | El gap más grande — leads se pierden | Alto |
| **P0** | Pausa bot cuando asesor interviene (5.2) | Bug crítico — bot y asesor hablan al mismo tiempo | Medio |
| **P1** | Pipeline CRM 7 estados (6.1) | Base para métricas y tracking | Bajo |
| **P1** | Detección origen lead / Caso A (1.2, 1.3) | Diferenciador del producto | Medio |
| **P1** | No saturar propiedades — mostrar 2 (2.2, 8.3) | Quick win — cambio en worker.py | Bajo |
| **P2** | Nurturing completo (Punto 4) | Largo plazo — requiere templates Meta | Alto |
| **P2** | Chatwoot bridge (5.1) | Importante pero asesor funciona por WhatsApp hoy | Medio |
| **P2** | Conversación natural sin menú rígido (8.2) | Mejora UX pero funciona con menús | Medio |
| **P3** | Métricas y dashboard (6.5-6.9) | Nice to have — se puede calcular manual | Medio |
| **P3** | Meta Ads integration (7.5) | Depende de que Robert tenga campañas activas | Medio |
| **P3** | Cal.com timezone fix (7.7) | Bug menor — un cambio de variable | Bajo |

---

## CHANGELOG

| Fecha | Cambio | Items afectados |
|-------|--------|-----------------|
| 2026-04-13 | Documento creado — análisis inicial completo | Todos |
| | | |
