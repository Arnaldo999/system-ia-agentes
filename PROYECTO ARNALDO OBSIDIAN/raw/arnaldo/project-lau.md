---
name: Lau Creaciones — cliente de Arnaldo
description: Bot WhatsApp de Lau (esposa de Arnaldo), proyecto propio de Arnaldo. Usa Evolution API. Worker en workers/clientes/system_ia/lau/ (ubicacion legacy, es de Arnaldo)
type: project
originSessionId: 5fb785f5-f620-4cab-8c91-4431d03e392f
---
**Lau es cliente directo de Arnaldo** — NO es cliente de Mica/System IA.
El worker esta en `workers/clientes/system_ia/lau/` por razones historicas pero el proyecto es propiedad de Arnaldo.

**Why:** Lau es la esposa de Arnaldo. El negocio "Creaciones Lau" es de manualidades y decoraciones.
**How to apply:** Cualquier cambio en el worker de Lau es responsabilidad de Arnaldo, no de Mica. No confundir la carpeta `system_ia` con propiedad del proyecto.

## Stack

- WhatsApp: **Evolution API** (no YCloud) — instancia "Lau Emprende"
- Evolution host: `sytem-ia-pruebas-evolution-api.6g0gdj.easypanel.host`
- Airtable base: `app4WvGPank8QixTU` (tablas: Productos `tblhCGfMLhaOZaXqe`, Leads `tblJLwmnhfihzybFz`)
- Airtable campo Categoria: singleSelect con opciones exactas: `Escolar`, `Cumpleaños`, `Eventos`, `Diseños`
- Cloudinary: carpeta `creaciones-lau/`
- Gemini: categorizacion automatica de trabajos
- Deploy: Coolify Arnaldo (Hostinger) — mismo backend monorepo

## Numero de Lau

- WhatsApp personal: `+5493765389823`
- WhatsApp instancia (bot): `+5493765005345` (ownerJid de Evolution)
- Env var: `LAU_NUMERO_ASESOR`
- Admin PIN: env var `LAU_ADMIN_PIN` (default "1234")

## Bugs resueltos (2026-04-13)

1. **Categorias Airtable**: el worker mandaba nombres que no existian como opciones del singleSelect (ej: "Fiestas y Eventos" cuando Airtable tenia "Eventos"). Fix: alinear nombres del worker con las 4 opciones reales de Airtable.
2. **Webhook lento/timeout**: conexion Coolify (Hostinger) -> Evolution API (Easypanel) tarda ~12s. Fix: webhook responde inmediato con BackgroundTasks de FastAPI, timeout subido de 10s a 20s.

## Estado (2026-04-13)

- Worker live y deployado
- Webhook async (BackgroundTasks) — responde inmediato
- 4 categorias alineadas: Escolar, Eventos, Cumpleaños, Diseños
- Modo admin (CARGAR + PIN) y modo cliente funcionando
- Latencia Evolution API desde Coolify: ~12s (considerar migrar Evolution a mismo VPS o usar proxy)
