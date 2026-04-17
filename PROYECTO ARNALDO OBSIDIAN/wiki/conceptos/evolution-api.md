---
title: "Evolution API (WhatsApp self-hosted)"
tags: [whatsapp-provider, evolution, self-hosted, mica, lau]
source_count: 0
proyectos_aplicables: [mica, arnaldo]
---

# Evolution API

## Definición

Servicio open-source self-hosted que implementa una interfaz API sobre WhatsApp Web. **NO es oficial de Meta** — funciona escaneando QR como WhatsApp Web. Cada bot corre como **instancia** independiente dentro del servicio.

## Quién la usa

| Proyecto | Instancia | Host | Número |
|----------|-----------|------|--------|
| [[micaela-colmenares]] / [[system-ia]] | `Demos` | `sytem-ia-pruebas-evolution-api.6g0gdj.easypanel.host` ([[easypanel-mica]]) | `+54 9 3765 00-5465` |
| [[arnaldo-ayala]] / [[lau]] | `Lau Emprende` | (misma instancia Evolution en infra Mica — pendiente confirmar si migrará a infra propia Arnaldo) | `+54 9 3765 00-5345` |
| [[robert-bazan]] | ❌ No usa | — | Robert usa [[meta-graph-api]] |

## Env vars

- `EVOLUTION_API_URL` — URL base del servicio
- `EVOLUTION_API_KEY` — apikey global del servicio
- `EVOLUTION_INSTANCE` — nombre de la instancia (ej: `Demos`, `Lau Emprende`)

## Bugs conocidos

- `MESSAGES_UPSERT` viene en **UPPERCASE** — el worker debe normalizar antes de parsear (`bugs_calcom_evolution.md` en memory Mission Control).
- WhatsApp Web **no dispara webhook** — probar siempre desde WhatsApp oficial del user.
- Latencia **~12s desde Coolify Arnaldo a Evolution Easypanel** — webhook lento. Mitigación: responder inmediato con `BackgroundTasks` de FastAPI, timeout 20s.

## ⚠️ No usar en otros proyectos

- Robert NO usa Evolution — usa [[meta-graph-api]].
- Back Urbanizaciones (Maicol) NO usa Evolution — usa [[ycloud]].

## Fuentes que lo mencionan

_Pendiente ingestar: `bugs_calcom_evolution.md`, `project_lau.md`, `project_mica_demo_inmo.md` en memory del Mission Control._
