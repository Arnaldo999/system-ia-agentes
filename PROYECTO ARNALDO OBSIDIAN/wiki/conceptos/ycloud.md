---
title: "YCloud (WhatsApp BSP)"
tags: [whatsapp-provider, ycloud, bsp, arnaldo]
source_count: 0
proyectos_aplicables: [arnaldo]
---

# YCloud

## Definición

Business Solution Provider (BSP) de WhatsApp — revendedor oficial con permisos de Meta. NO es Tech Provider directo (Arnaldo es cliente de YCloud, no Tech Provider). Permite enviar/recibir WhatsApp con plantillas aprobadas y API REST sin exponerse a la complejidad de ser Tech Provider.

## Quién la usa

- ✅ [[arnaldo-ayala]] / [[back-urbanizaciones]] — número `+54 9 3764 81-5689` (bot de Maicol).
- ❌ [[robert-bazan]] → usa [[meta-graph-api]] directo (él es Tech Provider).
- ❌ [[micaela-colmenares]] → usa [[evolution-api]].
- ❌ [[lau]] → usa [[evolution-api]] (instancia "Lau Emprende").

## Env vars

- `YCLOUD_API_KEY` — apikey global YCloud
- Número asesor para notificaciones: `INMO_DEMO_NUMERO_ASESOR` o similar por bot.

## Bugs conocidos

- **CTA (Call-To-Action) no funciona** — botones interactivos con URL no disparan como se espera. Documentado en `feedback_deploy_conventions.md` del Mission Control.
- **Dedup en retries**: YCloud reenvía el mismo mensaje si el webhook tarda. Mitigación: set `MENSAJES_PROCESADOS` en worker.

## Bridge YCloud ↔ Chatwoot

El único camino válido es **via FastAPI bridge** — no hay integración directa YCloud-Chatwoot. Worker responde y envía mensaje a Chatwoot inbox.

## 🚫 No usar en otros proyectos

- Robert NO usa YCloud.
- Mica/System IA NO usa YCloud.
- Lau NO usa YCloud (usa Evolution).

## Fuentes que lo mencionan

_Pendiente ingestar: `feedback_deploy_conventions.md`, `project_maicol.md` en memory del Mission Control._
