---
title: "CRM v2 modelo (Robert / Lovbot) — frontend HTML"
type: producto
proyecto: robert
tags: [crm, frontend, html, lovbot, modelo, coolify-hetzner]
ownership: lovbot-ai
fecha_migracion: 2026-04-22
hosting_actual: coolify-hetzner-robert
hosting_anterior: vercel
fecha_migracion_coolify: 2026-04-23
---

# CRM v2 modelo — frontend HTML de Lovbot

## Qué es

Frontend HTML único y canónico del CRM de la agencia [[lovbot-ai|Lovbot.ai]] (dueño [[robert-bazan]]). Es el **modelo del que se replica** para cada cliente inmobiliario real de Robert. Reemplaza al CRM v1 a partir del **2026-04-22**.

Equivalente conceptual frontend de [[lovbot-crm-modelo]] (que es la BD Postgres modelo).

## Archivo físico

- **Path**: `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/crm-v2.html`
- **Servido por**: 🆕 **[[coolify-robert|Coolify Hetzner Robert]]** (desde 2026-04-23, app `lovbot-crm-modelo` UUID `wcgg4kk0sw0g0wgw4swowog0`). Antes vivía en Vercel.
- **Dockerfile**: `dev/Dockerfile` + `dev/nginx.crm.conf` (nginx alpine estático)
- **JS dependencias**: `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/js/*.js` (panel-loteos, panel-contratos, panel-contrato-unificado, panel-inquilinos, panel-propietarios, panel-pagos-alquiler, panel-liquidaciones, panel-inmuebles-renta, panel-visitas, panel-asesores, panel-reportes, _crm-helpers)
- **Autodeploy**: ✅ via GitHub App oficial Coolify Hetzner (push a `main` redespliega solo)

## URLs en producción

- **Modelo (canónico)**: `https://crm.lovbot.ai/dev/crm-v2` — sirve desde [[coolify-robert]]
- **Raíz dominio** (catch-all sirve el v2): `https://crm.lovbot.ai/`
- **Alias legacy** (sirven v2): `https://crm.lovbot.ai/dev/crm`
- **Panel Gestión** (admin de tenants): `https://admin.lovbot.ai/clientes` — ver [[panel-gestion-robert]]
- **Panel Agencia** (CRM interno): `https://admin.lovbot.ai/agencia` — ver [[crm-agencia-lovbot]]
- **Fallback Vercel temporal** (no usar — solo backup): `https://lovbot-demos.vercel.app/dev/crm-v2`

## Ownership

- **Agencia**: [[lovbot-ai]] (Robert Bazán)
- **Socio técnico**: [[arnaldo-ayala]] (mantenimiento + monorepo en GitHub `Arnaldo999/system-ia-agentes`)
- **Hosting**: 100% [[coolify-robert|Coolify Hetzner Robert]] desde 2026-04-23 (cero dependencia Vercel)
- **Gestión de clientes**: [[panel-gestion-robert]] (admin desde donde se onboardea/suspende/reactiva cada cliente que compra este CRM)
- **NO confundir con**: [[crm-v2-modelo-mica]] (frontend equivalente para System IA, ese SÍ sigue en Vercel)

## Backend al que pega

- **API**: `https://agentes.lovbot.ai/` (FastAPI en [[coolify-robert]])
- **DB**: [[lovbot-crm-modelo|lovbot_crm_modelo]] (PostgreSQL única, [[vps-hetzner-robert]])
- **WhatsApp**: [[meta-graph-api]] (Tech Provider Robert)
- **CORS Origin permitido**: `https://crm.lovbot.ai`

## Migración v1 → v2 (2026-04-22)

**Antes**:
- `dev/crm.html` (v1) en `crm.lovbot.ai/dev/crm`
- `demo-crm-mvp.html` (v0 legacy) en `crm.lovbot.ai/`

**Ahora**:
- `dev/crm-v2.html` (v2) en `crm.lovbot.ai/dev/crm-v2`
- Las URLs viejas (`/`, `/dev/crm`) sirven v2 vía nginx try_files (no rompe links pegados)

## Migración a Coolify Hetzner (2026-04-23)

**Razón**: salir del límite Vercel Hobby para no frenar deploys de clientes Lovbot reales.

**Cambios DNS** (hechos por Arnaldo en cPanel):
- `crm.lovbot.ai`: CNAME Vercel → A record `5.161.235.99` (Hetzner)

**App Coolify creada**:
- Nombre: `lovbot-crm-modelo`
- UUID: `wcgg4kk0sw0g0wgw4swowog0`
- Stack: Dockerfile nginx alpine + Let's Encrypt SSL automático via Traefik
- Autodeploy: ✅ GitHub App oficial Coolify Hetzner

**Validación post-migración**:
- Server header: `nginx/1.29.8` (Coolify, ya no Vercel)
- SSL: Let's Encrypt válido
- Cero downtime durante la migración (Vercel sirvió durante propagación DNS)

**Commit**: `83d24c8` — `feat(robert/crm): migración v2 definitiva`

**Validado por**: [[robert-bazan]] el 2026-04-22 (chat con Arnaldo: "el crm ya está optimizado")

## Replicación a clientes reales (futuro)

Cuando un cliente real de Robert se onboardea:
1. Endpoint admin clona [[lovbot-crm-modelo|lovbot_crm_modelo]] → `lovbot_crm_<cliente>`
2. Vercel sirve el mismo `crm-v2.html` con `?tenant=<cliente>` o subdominio dedicado
3. Bot worker apunta a la nueva DB

El **archivo HTML del frontend NO se duplica** — un solo `crm-v2.html` sirve a N clientes vía multi-tenancy.

## Monitoreo

- Check `robert_crm_modelo` en [[sistema-auditoria|guardia_critica.py]] pegando a `https://crm.lovbot.ai/dev/crm-v2` cada 5 min.
- Check `robert_crm_dominio` pegando a `https://crm.lovbot.ai/`.
- Check `robert_crm_cors` haciendo preflight OPTIONS al backend con Origin del dominio.
- Alerta Telegram consolidada si cae.

## Reglas

- ❌ NO crear archivos `crm.html` o `demo-crm-mvp.html` nuevos. Si aparecen son legacy.
- ❌ NO confundir con [[crm-v2-modelo-mica]] (mismo concepto pero para System IA).
- ✅ Modificar SOLO `dev/crm-v2.html` cuando se necesiten ajustes al modelo.
- ✅ Cuando un cliente real se onboardea, el HTML se reusa, no se duplica.

## Fuentes que lo mencionan

- `memory/debug-log.md` (entrada 2026-04-22 "migración v2 definitiva Robert")
- Sesión Claude 2026-04-22 con Arnaldo
- Chat WhatsApp Arnaldo↔Robert 2026-04-22
