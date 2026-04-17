---
title: "VPS Hostinger — Mica"
type: vps
proyecto: mica
tags: [vps, hostinger, mica, system-ia, infraestructura]
---

# VPS Hostinger — Mica

## Descripción

Servidor virtual privado de Hostinger propiedad de [[micaela-colmenares]] — **NO es el mismo que el de Arnaldo** aunque ambos sean Hostinger. Es la infraestructura base de la marca [[system-ia]] (proyectos de Mica). Usa **Easypanel** como orquestador (no Coolify).

## Qué corre en este VPS

- **Orquestador**: [[easypanel-mica]] → `http://72.61.222.107:3000/`
- **n8n**: `https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host/` (workflows de automatización de Mica)
- **Evolution API**: `https://sytem-ia-pruebas-evolution-api.6g0gdj.easypanel.host/` (servicio self-hosted WhatsApp para bots de Mica — instancia `Demos`)

## 🚫 NO corre acá

- ❌ El backend FastAPI — está en [[vps-hostinger-arnaldo]] (compartido vía paths `/mica/*` y `/clientes/system-ia/*`).
- ❌ PostgreSQL del bot de Robert (eso está en [[vps-hetzner-robert]]).
- ❌ Cal.com, Supabase, Chatwoot → corren en [[vps-hostinger-arnaldo]] y son compartidos.

## Relaciones con otras entidades

- Pertenece a → [[micaela-colmenares]]
- Corre → [[easypanel-mica]]
- Hospeda servicios usados por → bots de Mica (incluido el demo inmobiliaria en `+5493765005465`)
- Depende del backend FastAPI en → [[vps-hostinger-arnaldo]]

## Notas

- IP: `72.61.222.107`
- Subdominio base de Easypanel: `6g0gdj.easypanel.host`
- Evolution API acá es distinta a la que usa Lau (que también es Evolution pero en la misma instancia "Lau Emprende" — verificar al trabajar con cada bot).
