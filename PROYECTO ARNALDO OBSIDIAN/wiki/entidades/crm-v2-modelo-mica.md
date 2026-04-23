---
title: "CRM v2 modelo (Mica / System IA) — frontend HTML"
type: producto
proyecto: mica
tags: [crm, frontend, html, system-ia, modelo, vercel]
ownership: system-ia
fecha_migracion: 2026-04-22
---

# CRM v2 modelo — frontend HTML de System IA

## Qué es

Frontend HTML único y canónico del CRM de la agencia [[system-ia|System IA]] (dueña [[micaela-colmenares]], socio técnico [[arnaldo-ayala]]). Es el **modelo del que se replica** para cada cliente inmobiliario real futuro de la agencia. Reemplaza al CRM v1 a partir del **2026-04-22**.

Equivalente conceptual frontend de [[inmobiliaria-demo-mica-airtable]] (la base Airtable modelo).

Mismo concepto que [[crm-v2-modelo-robert]] pero para System IA, **con stack distinto** (ver matriz abajo).

## Archivo físico

- **Path**: `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/crm-v2.html`
- **Servido por**: Vercel
- **JS dependencias**: `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/js/*.js`

## URLs en producción

- **Modelo (con tenant demo)**: `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo`
- **Modelo (sin tenant)**: `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2`
- **Alias legacy** (sirven v2 vía rewrite): `https://system-ia-agencia.vercel.app/system-ia/dev/crm` y `/system-ia/crm`
- **Admin Mica**: `https://system-ia-agencia.vercel.app/system-ia/admin`

> **Pendiente**: Mica todavía no tiene dominio propio (`crm.systemia.com` o similar). Hoy vive bajo `vercel.app`. Cuando se defina, actualizar esta página y activar el monitoreo (ver sección "Monitoreo" abajo).

## Ownership

- **Agencia**: [[system-ia]] (Micaela Colmenares — dueña; Arnaldo socio técnico)
- **Mantenimiento técnico**: [[arnaldo-ayala]] (monorepo Vercel + backend FastAPI compartido)
- **Gestión de clientes**: [[panel-gestion-mica]] (admin desde donde se onboardea/suspende/reactiva cada cliente que compra este CRM)
- **NO confundir con**: [[crm-v2-modelo-robert]] (frontend equivalente para Lovbot)

## Backend al que pega (DIFERENTE a Robert)

- **API**: `https://agentes.arnaldoayalaestratega.cloud/` (FastAPI compartido en [[coolify-arnaldo]], NO el de Robert)
- **DB**: [[inmobiliaria-demo-mica-airtable|Airtable base appA8QxIhBYYAHw0F]] (NO PostgreSQL — System IA usa Airtable)
- **WhatsApp**: [[evolution-api]] vía [[easypanel-mica]]
- **OpenAI**: cuenta Arnaldo compartida (NO `LOVBOT_OPENAI_API_KEY` que es de Robert)

Ver [[matriz-infraestructura]] para el cuadro completo.

## Migración v1 → v2 (2026-04-22)

**Antes**:
- `SYSTEM-IA/dev/crm.html` (v1) en `/system-ia/dev/crm`
- `SYSTEM-IA/crm.html` (v0 legacy raíz) en `/system-ia/crm`

**Ahora**:
- `SYSTEM-IA/dev/crm-v2.html` (v2) en `/system-ia/dev/crm-v2?tenant=mica-demo`
- Las URLs viejas (`/system-ia/dev/crm`, `/system-ia/crm`) sirven v2 vía rewrite Vercel (no rompe links pegados)

**Commits**:
- `a674c3d` — `feat(mica/crm): migración v2 definitiva`
- `ab879fb` — debug-log con registro

**Patrón aplicado**: idéntico al de [[crm-v2-modelo-robert]] (commit `83d24c8`) — primero Robert, después Mica el mismo día.

## Diferencias visuales con Robert

- **Paleta**: ámbar `#f59e0b` (NO purple). Ver feedback persistente `feedback_crm_v3_mica_persona_unica.md`.
- **IDs de records**: strings tipo `rec...` (Airtable), NO ints (a diferencia del Postgres de Robert).
- **Polimorfismo de items**: 3 linkedRecord (`Lote_Asignado`/`Propiedad_Asignada`/`Inmueble_Asignado`) + serializer (vs Postgres polimórfico de Robert).
- **Roles**: `multipleSelects` en Airtable (vs `TEXT[]` Postgres).
- **Sin transacciones** (limitación Airtable).

## Replicación a clientes reales (futuro)

Cuando un cliente real de Mica se onboardea:
1. Duplicar la base Airtable [[inmobiliaria-demo-mica-airtable|appA8QxIhBYYAHw0F]] → nueva base con `appXXXXXXXXX` propio del cliente.
2. Vercel sirve el mismo `crm-v2.html` con `?tenant=<cliente-slug>`.
3. Bot worker (en el backend Arnaldo) lee `tenant_slug` y apunta a la base Airtable correcta.

El **archivo HTML del frontend NO se duplica** — un solo `crm-v2.html` sirve a N clientes vía multi-tenancy y URL param `tenant`.

## Monitoreo

Hoy DESHABILITADO en [[sistema-auditoria|guardia_critica.py]] (checks `mica_crm` y `mica_crm_cors` retornan `None`).

**Para activar** cuando Mica tenga dominio prod definitivo:
- En Coolify → app `system-ia-agentes` → env vars: agregar `MICA_CRM_URL=https://<dominio-prod>` y `MICA_CRM_ENABLED=1`
- Próximo ciclo del cron picks up sin redeploy de código.

## Reglas

- ❌ NO crear archivos `crm.html` nuevos. Si aparecen son legacy.
- ❌ NO confundir con [[crm-v2-modelo-robert]] (mismo concepto, distinto stack y dueño).
- ❌ NO mezclar el stack: System IA es Airtable + Evolution + Easypanel; Lovbot es Postgres + Meta Graph + Hetzner.
- ✅ Modificar SOLO `SYSTEM-IA/dev/crm-v2.html`.
- ✅ Cuando un cliente real se onboardea, el HTML se reusa, no se duplica.

## Fuentes que lo mencionan

- `memory/debug-log.md` (entradas 2026-04-22 "migración v2 Mica" + commits `a674c3d` `ab879fb`)
- Sesión Claude 2026-04-22 con Arnaldo
- Memoria persistente `feedback_crm_v3_mica_persona_unica.md`
