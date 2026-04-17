---
title: "Easypanel Mica (Hostinger)"
type: orquestador
proyecto: mica
tags: [easypanel, mica, system-ia, orquestador, paas]
---

# Easypanel Mica

## Descripción

Instancia de **Easypanel** (PaaS competidor de Coolify) instalada en [[vps-hostinger-mica]]. **NO es Coolify** — Mica eligió Easypanel en vez de Coolify para su stack. Cada vez que el agente opere en el proyecto de Mica, debe considerar que la API y convenciones son distintas a Coolify.

## Acceso

- URL: `http://72.61.222.107:3000/`
- Subdominio base para servicios: `*.6g0gdj.easypanel.host`

## Servicios que orquesta

- **n8n** `https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/` — workflows de Mica
- **Evolution API** `https://sytem-ia-pruebas-evolution-api.6g0gdj.easypanel.host/` — servicio self-hosted de WhatsApp, con instancia `Demos` para el bot de Mica (nro `+5493765005465`)

## 🚫 NO corre acá

- ❌ El backend FastAPI — está en [[coolify-arnaldo]] (Mica comparte el monorepo, separado por paths `/mica/*` y `/clientes/system-ia/*`).
- ❌ PostgreSQL de Robert (está en [[coolify-robert]]).
- ❌ YCloud (eso es de Arnaldo).

## Relaciones con otras entidades

- Corre sobre → [[vps-hostinger-mica]]
- Pertenece a → [[micaela-colmenares]]
- Hospeda → n8n de Mica, Evolution API de Mica

## Diferencia con Coolify

- Coolify usa convenciones PaaS GitHub App + git push webhook. Easypanel tiene su propio modelo.
- Los scripts `02_OPERACION_COMPARTIDA/execution/coolify_manager.py` **NO sirven para Easypanel**. Si se necesita automatizar deploys en Mica, hay que escribir un manager específico de Easypanel (pendiente).

## Notas

- Instancia Evolution puede actualizarse desde UI Easypanel. Verificar `N8N_ENCRYPTION_KEY` antes de actualizar n8n (bug histórico con clave desencriptada).
- Pendiente: backup periódico del workflow n8n de Mica al repo `N8N-REPOSITORIO-SYSTEM-IA-DEMO`.
