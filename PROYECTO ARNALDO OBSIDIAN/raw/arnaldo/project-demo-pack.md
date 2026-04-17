---
name: Demo Pack Inmobiliaria
description: Pack completo de demo inmobiliaria LIVE en Vercel — CRM + 3 formularios por sub-nicho + informe mercado
type: project
---

Creado: 2026-04-01. Deployado en Vercel: 2026-04-01.

## URLs Live (Vercel)

| URL | Archivo |
|-----|---------|
| `lovbot-demos.vercel.app/crm` | `DEMOS/demo-crm-mvp.html` |
| `lovbot-demos.vercel.app/formulario-desarrolladora` | `DEMOS/formulario-desarrolladora.html` |
| `lovbot-demos.vercel.app/formulario-agencia` | `DEMOS/formulario-agencia.html` |
| `lovbot-demos.vercel.app/formulario-agente` | `DEMOS/formulario-agente.html` |
| `lovbot-demos.vercel.app/informe` | `DEMOS/informe-mercado-inmobiliario.html` |

Routing: `vercel.json` en raíz del repo con rewrites.

## Archivos en DEMOS/

| Archivo | Función |
|---------|---------|
| `demo-crm-mvp.html` | CRM dark mode: Inicio/Pipeline/Leads/Resúmenes IA/Propiedades/Agenda/Formularios |
| `formulario-desarrolladora.html` | Lead capture comprador de lotes (purple, 4 pasos, scoring) |
| `formulario-agencia.html` | Lead capture comprador/inquilino de propiedades via agencia (blue, 4 pasos, scoring) |
| `formulario-agente.html` | Lead capture comprador/inquilino via agente individual (green, 4 pasos, scoring) |
| `informe-mercado-inmobiliario.html` | Informe scraping Reddit — pain points por sub-nicho |
| `formulario-leads.html` | Formulario original (legacy, conectado a n8n webhook) |
| `_archivo_dashboard-crm.html` | CRM v1 archivado |

## Concepto clave: quién habla a quién

Los formularios son **herramientas demo para mostrar al prospecto** (desarrolladora/agencia/agente) cómo captarían SUS leads:

- **Form Desarrolladora** → habla al comprador de lotes/terrenos
- **Form Agencia** → habla al comprador/inquilino que busca via agencia
- **Form Agente** → habla al comprador/inquilino que contacta al agente

El CRM es una herramienta para el cliente (el inmobiliario lo usa a diario). Un solo CRM genérico para todos los sub-nichos.

## CRM — secciones

| Panel | Contenido |
|-------|-----------|
| Inicio | 6 KPIs, 2 bar charts, activity feed "Lo que hizo tu bot hoy" |
| Mi Pipeline | Kanban 6 cols: Nuevo→Contactado→Calificado→Cita Agendada→Cerrado→Perdido |
| Mis Leads | Tabla con search, badges, status pills, detalle modal |
| Resúmenes IA | Cards con data extraída por el bot (presupuesto, zona, urgencia, resumen) |
| Propiedades | Fetch async desde Airtable (`/crm/propiedades`), fallback a datos demo |
| Mi Agenda | Citas con estado pills, "Ver lead" + cambiar estado |
| Formularios | 4 cards sub-nicho + flow diagram 7 pasos |

## Scoring formularios

Cada formulario calcula score en tiempo real:
- **Caliente** (>=10pts): respuesta prioritaria
- **Tibio** (5-9pts): contacto normal
- **Frío** (<5pts): explorando

Submit: `POST /demos/inmobiliaria/lead` → backend + bot WhatsApp. Fallback: siempre muestra success (demo funciona offline).

## Endpoint `/lead` — lógica

- Bot NO pregunta nombre/email — ya los tiene del formulario
- `caliente` + Cal.com disponible → directo a agendamiento
- `tibio` → muestra propiedades filtradas

**Why:** Pack demo completo para mostrar a Robert y prospectos. Ciclo: formulario → bot WhatsApp → CRM con cita.
