---
title: "Lau (Creaciones Lau)"
type: persona/cliente-propio
proyecto: arnaldo
tags: [lau, arnaldo, cliente-propio, familia, creaciones-lau]
---

# Lau — Creaciones Lau

## Descripción

Esposa de [[arnaldo-ayala]]. "Creaciones Lau" es el negocio propio de Lau (manualidades, decoraciones escolares, cumpleaños, eventos, diseños). Es un **proyecto personal de Arnaldo** — NO es cliente de [[micaela-colmenares]] / System IA, NO es cliente de [[robert-bazan]] / Lovbot.

## ⚠️ Advertencia de navegación

El worker de Lau vive en `workers/clientes/system_ia/lau/` **por razones históricas/legacy** — esa ruta NO implica que el proyecto sea de Mica. La nomenclatura del path puede confundir, pero el dueño del proyecto es Arnaldo. Cualquier cambio en el worker de Lau es responsabilidad directa de Arnaldo.

## Stack del bot "Creaciones Lau"

- **WhatsApp provider**: Evolution API (instancia "Lau Emprende")
- **Evolution host**: `sytem-ia-pruebas-evolution-api.6g0gdj.easypanel.host`
- **Base de datos**: Airtable base `app4WvGPank8QixTU`
  - Tabla Productos: `tblhCGfMLhaOZaXqe`
  - Tabla Leads: `tblJLwmnhfihzybFz`
  - Campo Categoría (singleSelect): `Escolar`, `Cumpleaños`, `Eventos`, `Diseños`
- **Imágenes**: Cloudinary carpeta `creaciones-lau/`
- **LLM**: Gemini (categorización automática de trabajos) + OpenAI cuenta Arnaldo
- **Deploy**: Coolify Hostinger (Arnaldo) — mismo monorepo FastAPI
- **Path del worker**: `workers/clientes/system_ia/lau/` (legacy — NO implica Mica)

## Números

- WhatsApp personal Lau: `+5493765389823`
- WhatsApp instancia bot: `+5493765005345` (ownerJid en Evolution)
- Env var asesor: `LAU_NUMERO_ASESOR`
- Admin PIN: env var `LAU_ADMIN_PIN` (default `1234`)

## Bugs resueltos

- **2026-04-13** — Categorías Airtable: el worker mandaba nombres que no existían como opciones del singleSelect (ej: "Fiestas y Eventos" vs "Eventos" real). Fix: alinear nombres con las 4 opciones reales.
- **2026-04-13** — Webhook lento/timeout: conexión Coolify Hostinger ↔ Evolution Easypanel tarda ~12s. Fix: responder inmediato con FastAPI `BackgroundTasks`, timeout subido de 10s a 20s.

## Aparece en

_Pendiente ingestar fuente oficial._

## Relaciones con otras entidades

- Esposa de → [[arnaldo-ayala]]
- Negocio propio → Creaciones Lau (manualidades / decoración)
- Worker path (legacy) → `workers/clientes/system_ia/lau/`
- **NO** relacionada con → [[micaela-colmenares]] ni System IA (marca)

## Notas

- Estado (2026-04-13): worker live, deployado, webhook async, 4 categorías alineadas, modo admin (CARGAR + PIN) y modo cliente funcionando.
- Pendiente: considerar migrar Evolution al VPS de Arnaldo (Hostinger) para bajar latencia de ~12s, o usar proxy.
