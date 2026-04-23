---
title: "Landing pública lovbot.ai"
type: producto
proyecto: robert
ownership: lovbot-ai
tags: [landing, marketing, lead-capture, lovbot, frontend]
status: parcial
---

# Landing pública lovbot.ai

## Qué es

Sitio público de marketing de la agencia [[lovbot-ai|Lovbot.ai]]. Punto de entrada principal para captar leads que terminan en el [[crm-agencia-lovbot|CRM Gestión Agencia]] (pendiente de implementar).

## URL en producción

`https://lovbot.ai/` — vivo (HTTP 200), responde "Próximamente".

## Estado actual (2026-04-22)

🟡 **Parcial**: la página existe y responde, pero el contenido es placeholder ("Próximamente"). El CTA WhatsApp está pendiente de conectar al bot agencia.

## Función esperada (cuando esté completa)

1. **Capturar atención** del visitante (potencial cliente inmobiliaria, agencia, desarrolladora).
2. **Educar** sobre los servicios de la agencia: bot WhatsApp + CRM v2 + integraciones.
3. **CTA WhatsApp** → redirige a `wa.me/<numero-bot-agencia>` con mensaje pre-poblado → bot atiende → lead entra al [[crm-agencia-lovbot|CRM Agencia]].
4. **Otros canales futuros**: formulario lead, links a casos de estudio, demos.

## Archivo físico

Pendiente de identificar — capaz vive en `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/landing-lovbot/` o repo separado en GitHub Lovbot. A confirmar.

## Ownership

- **Agencia**: [[lovbot-ai]] (Robert Bazán)
- **Mantenimiento técnico**: [[arnaldo-ayala]]
- **Captura leads para**: [[crm-agencia-lovbot]] (pendiente de implementar)

## Relaciones

- Vinculo principal → [[crm-agencia-lovbot]] (los leads de esta landing van al CRM agencia)
- Bot al que conecta CTA WhatsApp → bot agencia Lovbot (pendiente de crear, ver [[crm-agencia-lovbot]] sección "Origen de leads")
- Hosting → a confirmar (probablemente Vercel o Coolify)

## Pendientes

1. Identificar y documentar repo / archivo físico de la landing.
2. Diseño definitivo de la landing (hoy es placeholder).
3. Conectar CTA WhatsApp al bot agencia (cuando esté creado).
4. Sumar check al [[sistema-auditoria|monitor]] para que alerte si la landing cae.
5. Tracking de UTMs para saber qué fuente trae más leads.

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22]] — sesión donde Robert propuso conectar landing al bot agencia
