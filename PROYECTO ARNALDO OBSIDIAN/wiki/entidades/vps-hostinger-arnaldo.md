---
title: "VPS Hostinger — Arnaldo"
type: vps
proyecto: arnaldo
tags: [vps, hostinger, arnaldo, infraestructura]
---

# VPS Hostinger — Arnaldo

## Descripción

Servidor virtual privado de Hostinger propiedad de [[arnaldo-ayala]]. Es la infraestructura base de toda la producción propia de Arnaldo ([[maicol]] y [[lau]]) y también la sede de servicios compartidos que usan [[robert-bazan]] y [[micaela-colmenares]] (Cal.com, Supabase).

## Qué corre en este VPS

- **Orquestador**: [[coolify-arnaldo]] → `https://coolify.arnaldoayalaestratega.cloud/`
- **Backend FastAPI**: `agentes.arnaldoayalaestratega.cloud` (monorepo con workers de Maicol, Lau, demos)
- **n8n**: `https://n8n.arnaldoayalaestratega.cloud/` (workflows de automatización de Arnaldo)
- **Chatwoot**: `https://chatwoot.arnaldoayalaestratega.cloud/` (inbox WhatsApp para Arnaldo + compartido con Mica)
- **Cal.com**: agenda compartida — la usan Arnaldo, Robert y Mica para agendar citas.
- **Supabase**: CRM SaaS multi-tenant — Robert y Mica guardan sus tenants acá.

## Relaciones con otras entidades

- Pertenece a → [[arnaldo-ayala]]
- Corre → [[coolify-arnaldo]]
- Hospeda bots de → [[maicol]], [[lau]]
- Hospeda servicios compartidos usados por → [[robert-bazan]], [[micaela-colmenares]]

## Notas

- Dominio raíz: `arnaldoayalaestratega.cloud` (y `backurbanizaciones.com` para el CRM de Maicol).
- Tokens/env vars: `COOLIFY_TOKEN`, `COOLIFY_PROJECT_UUID`, `COOLIFY_ENVIRONMENT_UUID` (prefijo por defecto, sin `_ROBERT`).
