---
title: "Maicol — Back Urbanizaciones"
type: cliente-externo
proyecto: arnaldo
tags: [maicol, arnaldo, cliente-externo, inmobiliaria, back-urbanizaciones, produccion-live]
---

# Maicol — Back Urbanizaciones

## Descripción

Cliente externo de [[arnaldo-ayala]], dueño de **Back Urbanizaciones** — empresa inmobiliaria que vende lotes en desarrollos urbanos de Misiones, Argentina (San Ignacio, Apóstoles, Gdor Roca, Alem, La Paulina, Altos San Ignacio, Altos Roca). Es uno de los dos proyectos de producción 100% propios de Arnaldo (junto con [[lau]]).

Atiende clientes reales desde **2026-04-06** (carga datos en el CRM LIVE) — bug en el bot o CRM afecta conversaciones reales. Ser cuidadoso.

## Stack del bot "Back Urbanizaciones"

Ver [[wiki/conceptos/matriz-infraestructura]] columna "Arnaldo".

- **WhatsApp provider**: YCloud (cuenta Arnaldo)
- **Base de datos**: Airtable (base de Arnaldo) — tablas: Propiedades, Clientes, Pipeline, Clientes Activos, Loteos
- **LLM**: Gemini (calificación de leads) + OpenAI cuenta Arnaldo (`OPENAI_API_KEY`)
- **Deploy**: Coolify Hostinger (Arnaldo) — `agentes.arnaldoayalaestratega.cloud`
- **Path del worker**: `workers/clientes/arnaldo/maicol/`
- **n8n**: `n8n.arnaldoayalaestratega.cloud` (alerta vencimientos 8am ARG via SMTP + WhatsApp asesor)

## CRM LIVE — `crm.backurbanizaciones.com`

7 paneles con Tailwind CSS: Inicio · Propiedades · Pipeline · Leads · Clientes Activos · Galería · Loteos.

- Panel Clientes Activos: CRUD completo, `Estado_Pago` automático, select Loteo dinámico, fetch fresco.
- Panel Loteos: **6 loteos** con mapas SVG interactivos.
  - San Ignacio: 163 pins calibrados
  - Apóstoles: 332 pins calibrados (331 lotes + 1 EV Mz17) ✅ 2026-04-08
- Fetch fresco al abrir → pins reflejan estado real (verde/amarillo/rojo), sincronizado con Airtable por `Numero_Lote`.

## Flujo del bot

1. Nombre → Objetivo → Zona → Presupuesto (cuota/mes) → Urgencia → Calificación Gemini
2. **Scoring**:
   - Caliente/tibio → muestra propiedades filtradas por zona+precio
   - Frío → sitio web
3. CTA email al final: guarda en Airtable tabla Clientes
4. Dedup YCloud: `MENSAJES_PROCESADOS` evita doble procesamiento en retries

## Zonas del bot

San Ignacio · Gdor Roca · Apóstoles · Leandro N. Alem · Lote Urbano · Otra zona

## Presupuesto (rangos por cuotas mensuales ARS)

`$150k` · `$150-200k` · `+$200k` — filtra Airtable por campo `Precio`.

## Aparece en

_Pendiente ingestar fuentes (brief inicial, reuniones, handoffs)._

## Relaciones con otras entidades

- Cliente de → [[arnaldo-ayala]]
- Marca comercial → Back Urbanizaciones (`backurbanizaciones.com`)
- Worker → `workers/clientes/arnaldo/maicol/`
- CRM → `crm.backurbanizaciones.com`
- NO relacionado con → [[micaela-colmenares]] ni [[robert-bazan]]

## Notas

- Estado (2026-04-17): producción estable, ya carga datos reales de clientes.
- Domain: `backurbanizaciones.com` (propio, gestionado por Arnaldo).
- Regla: NUNCA modificar el worker de Maicol directamente — primero probar en `workers/demos/inmobiliaria/`, después copiar.
