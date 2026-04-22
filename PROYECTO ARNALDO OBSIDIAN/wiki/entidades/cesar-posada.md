---
title: Cesar Posada — cliente nuevo agencia turismo
type: cliente
proyecto: arnaldo
tags: [proyecto-arnaldo, cliente, turismo, agencia-turismo, prospecto-caliente]
estado: propuesta-enviada
fecha_contacto: 2026-04-22
---

# Cesar Posada

Contacto nuevo de Arnaldo interesado en automatizar su agencia de turismo con bot WhatsApp + CRM. Propuesta enviada 22 de abril de 2026, esperando que complete el formulario de brief para arrancar desarrollo.

## Estado actual

**Pre-onboarding** — propuesta enviada, pendiente de recibir brief + pago de implementación.

## Contacto

- **Nombre**: Cesar Posada (persona)
- **Marca de la agencia**: _pendiente — se confirma en el brief_
- **Tipo de negocio**: Agencia de turismo / viajes
- **Relación**: cliente directo de Arnaldo (NO de Mica ni de Robert)

## Proyecto solicitado

**Bot WhatsApp IA + CRM web** para filtrar consultas de viajes entrantes y gestionar leads.

El cliente quiere algo similar a lo que se implementó para [[maicol]] (bot inmobiliario LIVE), pero adaptado al vertical de turismo:
- Bot atiende consultas entrantes por WhatsApp
- Filtra leads con preguntas calificadoras (destino, fechas, cantidad de personas, presupuesto)
- Respuestas con info real de paquetes turísticos
- Escalamiento a asesor humano cuando corresponde
- CRM web para ver el pipeline completo

## Stack asignado (clientes de Arnaldo)

Sigue la matriz estándar de [[agencia-arnaldo-ayala]]:

| Componente | Servicio |
|------------|----------|
| Base de datos | [[airtable]] (base propia nueva a crear) |
| WhatsApp provider | [[ycloud]] |
| LLM | Google Gemini / GPT-4 (OpenAI Arnaldo) |
| Orquestador | [[coolify-arnaldo]] (Hostinger) |
| Worker | FastAPI en monorepo `workers/clientes/arnaldo/cesar-posada/` |
| Agenda | Cal.com Arnaldo (compartido) |
| CRM web | HTML + Tailwind + FastAPI endpoints — mismo patrón que Maicol/Mica |

## Propuesta comercial enviada

- **Implementación única**: USD 300
  - Configuración bot WhatsApp oficial
  - Desarrollo CRM web a medida
  - Registro WhatsApp Business
  - Carga inicial de paquetes
  - Capacitación
  - 15 días soporte post-lanzamiento
- **Mantenimiento mensual**: USD 80/mes
  - Hosting + conectividad 24/7
  - Actualizaciones técnicas
  - Ajustes según feedback
  - Soporte priorizado
  - Reportes mensuales
  - Costos IA + servidores incluidos

## Entregables ya producidos

### Formulario de brief
**URL**: `https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/brief.html`

7 secciones: Agencia / Equipo / Servicios / Paquetes / Proceso de venta / Tono del bot / Extras.

Al completar genera un `.md` descargable + abre WhatsApp con Arnaldo pre-llenado con mensaje corto, y Cesar adjunta el archivo manualmente. Sin backend server-side para el envío — 100% client-side.

### Propuesta comercial
**URL**: `https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/propuesta.html`

Página HTML única con scope + stack técnico + precios + cronograma + CTA de contacto vía WhatsApp.

Ambos archivos residen en:
`01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/cesar-posada/brief.html` y `propuesta.html`

Servidos por el backend `system-ia-agentes` bajo ruta `/propuestas/cesar-posada/` via mount `StaticFiles`.

## Cronograma estimado

| Día | Acción |
|-----|--------|
| 1 | Brief completado por Cesar |
| 2-5 | Desarrollo bot + CRM |
| 6-8 | Testing + ajustes de tono |
| 9-10 | Lanzamiento + capacitación |
| 11-25 | 15 días soporte |

## Próximos pasos (cuando llegue el brief)

1. **Leer el brief.md** que Cesar va a enviar por WhatsApp
2. **Crear base Airtable nueva** con estructura para agencia de turismo:
   - `Leads` — consultas entrantes del bot
   - `Clientes_Activos` — personas que compraron
   - `Paquetes` — catálogo editable por el dueño
   - `Asesores` — equipo de la agencia
   - `Conversaciones` — historial del bot
   - `Destinos` — catálogo de destinos disponibles
3. **Scaffold del worker** en `workers/clientes/arnaldo/cesar-posada/worker.py`
4. **Scaffold del CRM web** en `demos/turismo/dev/crm-v2.html` (template para nicho turismo)
5. **Onboarding WhatsApp oficial** — registrar el número con YCloud
6. **Deploy Coolify Hostinger** como servicio del monorepo
7. **Prompt del bot** adaptado a turismo (criterios de calificación, tono, respuestas tipo)

## Notas

- Es el **primer cliente de Arnaldo en vertical turismo** — sirve como template para próximos clientes del rubro.
- El brief que complete Cesar define qué tan complejo es el bot (paquetes estándar vs cotizaciones custom, cantidad de destinos, etc.)
- Precio alineado con la escala de Maicol (similar complejidad). Si al ver el brief resulta más complejo (ej: integración con PAX, Amadeus, o GDS), renegociar antes de firmar.

## Relaciones con otras entidades

- [[arnaldo-ayala]] — dueño de la agencia que atiende a Cesar
- [[agencia-arnaldo-ayala]] — la agencia de Arnaldo
- [[maicol]] — cliente modelo (bot similar en vertical inmobiliario)
- [[ycloud]] — provider WhatsApp
- [[airtable]] — base de datos
- [[coolify-arnaldo]] — orquestador donde se va a deployar

## Fuentes

- [[sesion-2026-04-22-brief-cesar-posada]] — ingesta de la sesión donde se armó propuesta + formulario
