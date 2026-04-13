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
- **Estado**: ❌ FALTA
- **Detalle**: Hoy todos los leads entran como "whatsapp_directo". No se detecta si viene de Meta Ads, portal, orgánico, etc.
- **Requerimiento PDF**: "Detecta origen del lead (ID anuncio / UTM / webhook)"
- **Implementación necesaria**:
  - [ ] Leer `referral` del webhook de Meta (contiene ad_id, source_url)
  - [ ] Guardar en Airtable campo `Fuente_Detalle` (ad_id, campaign_name, source_url)
  - [ ] Adaptar respuesta inicial según origen (Caso A vs Caso B)

### 1.3 Caso A: Lead desde anuncio de propiedad específica
- **Estado**: ❌ FALTA
- **Detalle**: Hoy no diferencia entre lead de anuncio y lead genérico. Todos pasan por el mismo flujo.
- **Requerimiento PDF**: "Responde con info DIRECTA de esa propiedad: precio, ubicación, highlights, disponibilidad"
- **Implementación necesaria**:
  - [ ] Detectar `referral.body` o `referral.source_url` del webhook Meta
  - [ ] Matchear con propiedad en Airtable (por ID, nombre o URL)
  - [ ] Responder directamente con ficha de esa propiedad
  - [ ] Saltar pasos de tipo/zona y ir directo a calificación + cita

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
- **Estado**: 🟡 PARCIAL
- **Detalle**: Score tibio recibe propiedades + cita (igual que caliente) pero sin nurturing posterior
- **Implementación necesaria**:
  - [ ] Diferenciar flujo tibio: propiedades + cita + entrada a nurturing si no agenda

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
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Trigger cuando se carga propiedad nueva en Airtable
  - [ ] Matchear con leads dormidos por zona/tipo/presupuesto
  - [ ] Enviar notificación personalizada

### 4.2 Notificar cambios de precio
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Detectar cambio de precio en Airtable (campo `Precio` modificado)
  - [ ] Notificar a leads que vieron esa propiedad

### 4.3 Enviar info de crédito/financiamiento
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Contenido predefinido sobre opciones de crédito hipotecario
  - [ ] Envío quincenal a leads en nurturing

### 4.4 Enviar plusvalía de zona
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Contenido predefinido sobre valorización por zona
  - [ ] Envío quincenal alternado con crédito

### 4.5 Frecuencia semanal o quincenal
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Scheduler semanal/quincenal para leads en nurturing
  - [ ] Rotación de contenido (no repetir mensajes)

### 4.6 Detección de respuesta → recalificar
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Si lead en nurturing responde → sacar de nurturing → volver a bot → recalificar
  - [ ] Campo Airtable: `Flujo_Nurturing` (activo/completado/cancelado)

### 4.7 Infraestructura de nurturing
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Campos Airtable: `Flujo_Nurturing`, `Nurturing_Inicio`, `Nurturing_Ultimo_Envio`, `Nurturing_Mensaje_Numero`
  - [ ] 8-12 mensajes de nurturing predefinidos para vertical inmobiliaria
  - [ ] Templates WhatsApp aprobados por Meta
  - [ ] Script/workflow quincenal

---

## PUNTO 5: INTERVENCIÓN HUMANA (CHATWOOT)

### 5.1 Escalamiento automático a Chatwoot
- **Estado**: 🟡 PARCIAL
- **Detalle actual**: Escala por WhatsApp directo al número del asesor
- **Requerimiento PDF**: Usar Chatwoot como canal — asesor ve toda la conversación
- **Implementación necesaria**:
  - [ ] Configurar bridge Meta WhatsApp ↔ Chatwoot para Robert (Coolify Hetzner o Arnaldo)
  - [ ] Webhook Chatwoot → FastAPI para sincronizar estados
  - [ ] Crear inbox en Chatwoot para el número de Robert

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
- **Estado**: 🟡 PARCIAL
- **Detalle**: Airtable tiene datos del lead pero no historial de la conversación
- **Implementación necesaria**:
  - [ ] Guardar mensajes del bot y del cliente en campo Airtable `Historial_Conversacion` (long text)
  - [ ] O mejor: visible directamente en Chatwoot (tiene historial nativo)

### 5.5 Panel del asesor — respuestas del bot
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Incluido en 5.4 — si se usa Chatwoot, el asesor ve todo

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
- **Estado**: 🟡 PARCIAL
- **Actual**: Hardcodeado "whatsapp_directo"
- **Implementación necesaria**:
  - [ ] Campo `Fuente_Detalle` en Airtable (ad_id, campaign, orgánico, portal)
  - [ ] Leer referral del webhook Meta

### 6.3 Datos clave — propiedad de interés
- **Estado**: 🟡 PARCIAL
- **Actual**: Se guarda tipo/zona pero no la propiedad específica
- **Implementación necesaria**:
  - [ ] Campo `Propiedad_Interes` en Airtable (nombre o record ID de la propiedad elegida)
  - [ ] Guardar cuando el lead selecciona una ficha

### 6.4 Datos clave — última interacción
- **Estado**: ✅ LISTO
- **Completado**: 2026-04-13
- **Detalle**: `fecha_ultimo_contacto` se actualiza automáticamente cada vez que el lead escribe (async thread)

### 6.5 Métricas — tiempo de respuesta
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Registrar timestamp de mensaje entrante y respuesta del bot
  - [ ] Campo `Tiempo_Respuesta_Seg` en Airtable
  - [ ] Endpoint `GET /crm/metricas` que calcule promedio

### 6.6 Métricas — tasa de citas
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Calcular: leads con `Fecha_Cita` / total leads

### 6.7 Métricas — tasa de cierre
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Calcular: leads `cerrado_ganado` / total leads calificados
  - [ ] Requiere primero implementar estados completos (6.1)

### 6.8 CRM visual — filtros
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Filtros en CRM HTML por score, zona, tipo, estado, fecha

### 6.9 CRM visual — dashboard métricas
- **Estado**: ❌ FALTA
- **Implementación necesaria**:
  - [ ] Panel con KPIs: leads hoy, tasa citas, tasa cierre, tiempo respuesta
  - [ ] Gráficos simples (Chart.js o similar)

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
- **Estado**: 🟡 PARCIAL
- **Detalle**: Usa menús numéricos "1/2/3" para la mayoría de pasos
- **Implementación necesaria**:
  - [ ] Usar Gemini para interpretar respuestas abiertas en vez de forzar opciones numéricas
  - [ ] Mantener opciones numéricas como fallback si Gemini no entiende
  - [ ] Usar botones interactivos de WhatsApp (mejor UX que texto "1/2/3")

### 8.3 No saturar con opciones
- **Estado**: ✅ CUMPLE
- **Completado**: 2026-04-13 — muestra 2 iniciales, "+" para expandir

### 8.4 Siempre llevar a acción (visita)
- **Estado**: ✅ CUMPLE
- **Detalle**: CTA de Cal.com después de calificar

### 8.5 Seguimiento automático SIEMPRE activo
- **Estado**: ❌ NO CUMPLE
- **Detalle**: No existe seguimiento — ver Punto 3

### 8.6 Datos del lead obligatorios
- **Estado**: ✅ CUMPLE

### 8.7 No responder genérico sin contexto
- **Estado**: 🟡 PARCIAL
- **Detalle**: Leads genéricos reciben misma bienvenida. Con Caso A implementado, se contextualiza

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
