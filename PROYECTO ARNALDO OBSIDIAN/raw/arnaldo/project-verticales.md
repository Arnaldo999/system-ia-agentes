---
name: Verticales de producto System IA
description: Verticales de negocio desarrolladas o en desarrollo — gastronomico, inmobiliario, membresias, redes sociales
type: project
---

## Verticales activas

| Vertical | Estado | Worker/Archivo | Notas |
|----------|--------|---------------|-------|
| Inmobiliaria (Maicol) | Produccion | `workers/clientes/arnaldo/maicol/worker.py` | Lotes y terrenos, YCloud |
| Inmobiliaria Demo v2 | Pack completo listo | `workers/demos/inmobiliaria/worker.py` | Gemini, 3 sub-nichos B2B + comprador, Cal.com, formulario + CRM dashboard |
| Gastronomico Demo | **ACTIVO — en desarrollo** | `workers/demos/gastronomico/worker.py` | Multi-subniche, Gemini, reservas+delivery+encargues+eventos |
| Redes Sociales | En desarrollo | `workers/social/worker.py` | Respuesta auto a comentarios IG/FB via FastAPI |
| Membresias (MembresIA) | Pausado | PWA HTML+Tailwind | Gimnasios, academias, coworkings |

## Demo Gastronómico — estado actual (2026-04-06)

Worker activo: `workers/demos/gastronomico/worker.py` (legacy en `workers/_legacy/gastronomico/`)
Frontend: `DEMOS/GASTRONOMIA/gastronomia.html` — sub-niche switcher en sidebar

### Sub-nichos soportados (6)
cafeteria | pizzeria | rotiseria | hamburgueseria | parrilla | restaurante (todo-en-uno)

### Funcionalidades implementadas
- **Selector subniche**: al inicio el cliente elige tipo de local → bot adopta personalidad/menú/horario
- **Menú por subniche desde Airtable**: `_at_leer_menu_subniche(sn)` filtra tabla Platos
- **Opciones menú dinámicas**: `_build_menu_opciones(sn)` — pizzería sin tortas, parrilla sin delivery, etc.
- **Navegación**: `0`/`menu` → menú principal subniche, `00` → selector de sub-nichos
- **7 opciones**: Menú del día, Delivery, Encargues, Reservas, Presupuesto evento, Cancelar/modificar reserva, Reseñas
- **Delivery**: no pide dirección ni calcula tiempo — deriva asesor directo (fix 2026-04-06)
- **Reservas**: Airtable + Cal.com en tiempo real, confirmación incluye recordatorio Cal.com
- **Cancelar reserva**: removido de menú (Cal.com lo maneja)
- **Reseñas**: guarda en AT Clientes, alerta dueño si negativa
- **derivar_asesor**: delivery/encargue/presupuesto → notifica dueño vía YCloud con datos del cliente
- **YCloud inbound**: parsea `whatsappInboundMessage` correctamente (fix 2026-04-06)

### Env vars (prefijo `GASTRO_DEMO_`)
`SUBNICHE`, `NOMBRE`, `HORARIO`, `ALIAS_PAGO`, `NUMERO_BOT`, `NUMERO_DUENO`, `YCLOUD_KEY`, `AIRTABLE_BASE`, `CAL_API_KEY`, `CAL_EVENT_ID` + compartidas `GEMINI_API_KEY`, `AIRTABLE_TOKEN`

### Origen
Micaela trajo a **Luciano** (dueño de cafetería en Misiones) — videollamada 2026-04-02. Casos de uso: encargues, delivery, presupuestos, reservas, menú del día, difusión.

### Airtable gastro
Base: `appdA5rJOmtVvpDrx` — tablas: Platos (con campo subniche), Reservas, Clientes, Pedidos

## Demo Inmobiliaria v2 — detalles técnicos
- **3 sub-nichos B2B**: desarrolladora / inmobiliaria / agente independiente
- **1 sub-nicho B2C**: comprador/inquilino
- **Gemini**: clasifica intención + detecta sub-nicho automáticamente
- **Precalificación**: 3 preguntas por sub-nicho → score caliente/tibio/frío
- **Cal.com**: agendamiento automático de citas
- **Endpoint `/lead`**: leads del formulario web → bot va directo a propiedades/agenda
- **Env vars**: prefijo `INMO_DEMO_`

## Demo Pack (Vercel) — LIVE `lovbot-demos.vercel.app`
- `DEMOS/INMOBILIARIA/demo-crm-mvp.html` → CRM dark mode
- `DEMOS/INMOBILIARIA/formulario-desarrolladora.html` → comprador de lotes
- `DEMOS/INMOBILIARIA/formulario-agencia.html` → comprador/inquilino via agencia
- `DEMOS/INMOBILIARIA/formulario-agente.html` → comprador/inquilino via agente
- `DEMOS/INMOBILIARIA/informe-mercado-inmobiliario.html` → scraping Reddit pain points
- `DEMOS/GASTRONOMIA/gastronomia.html` → demo gastronómico con subniche switcher
- **DEPLOYED** — auto-deploy desde GitHub push `master:main`

## Productos complementarios
- **Sitios web**: WordPress + Elementor (backurbanizaciones.com como caso)
- **Formularios leads**: HTML estatico → n8n webhook → Airtable → WhatsApp

**Why:** Cada vertical se construye como worker replicable. El gastronómico es el foco actual de desarrollo.
**How to apply:** Al crear nuevo cliente, identificar vertical y copiar el worker demo correspondiente.
