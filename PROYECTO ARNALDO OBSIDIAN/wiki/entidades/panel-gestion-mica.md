---
title: "Panel Gestión Mica (System IA Admin)"
type: producto
proyecto: mica
ownership: system-ia
tags: [admin, panel-gestion, system-ia, vercel, frontend]
---

# Panel Gestión Mica — System IA Admin

## Qué es

Panel HTML de administración de tenants (clientes) de la agencia [[system-ia|System IA]] (dueña [[micaela-colmenares]], socio técnico [[arnaldo-ayala]]). Desde acá se puede:

- Listar todos los tenants (clientes inmobiliarias futuros) onboardeados.
- Suspender / reactivar / renovar suscripción de un cliente.
- Abrir directamente el CRM v2 de cada cliente con su `tenant=<slug>` precargado.

## URL en producción

- `https://system-ia-agencia.vercel.app/system-ia/admin` (canónica, no cambió)
- `https://system-ia-agencia.vercel.app/system-ia/admin/clientes` (alias agregado 2026-04-22)

> Hoy bajo dominio Vercel. Cuando System IA defina dominio propio (ej: `admin.systemia.com` o similar), actualizar esta página y el [[sistema-auditoria|monitor]].

## Archivo físico

- **Path**: `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/admin/clientes.html`
  - Movido de `SYSTEM-IA/admin.html` a `SYSTEM-IA/admin/clientes.html` el 2026-04-22 por simetría con la reorganización de Robert (ver [[crm-agencia-lovbot]]).
  - **El contenido HTML/UI NO cambió**. Mica solo gestiona Clientes CRM y no necesita un nav adicional (a diferencia de [[panel-gestion-robert]] que sí lo tiene porque comparte espacio con `agencia.html`).
- **Servido por**: Vercel ([[wiki/conceptos/coolify-default-deploy|considerar migración a Coolify]] cuando Mica tenga dominio prop)

## A qué backend pega — y por qué

`https://agentes.arnaldoayalaestratega.cloud/admin/tenants` (backend FastAPI [[arnaldo-ayala|Arnaldo]] en [[coolify-arnaldo]])

**Doble motivo correcto** (no viola [[aislamiento-entre-agencias]]):

1. **System IA usa el backend FastAPI Arnaldo** según la [[matriz-infraestructura]] — Mica no tiene backend propio.
2. **El catálogo de tenants vive en [[supabase-tenants|Supabase]]** (cuenta Arnaldo, compartida con Lovbot). El backend Arnaldo es el único con credenciales para escribir/leer ahí.

### Capas de datos

| Capa | Dónde vive | Quién la lee |
|------|-----------|--------------|
| Catálogo de tenants (qué clientes compraron CRM, su estado) | [[supabase-tenants\|Supabase]] (cuenta Arnaldo, compartida) | Backend Arnaldo |
| Datos del CRM Mica (leads, propiedades, contratos) | [[inmobiliaria-demo-mica-airtable\|Airtable `appA8QxIhBYYAHw0F`]] | Backend Arnaldo (mismo) |

El admin solo gestiona la **capa 1** (Supabase). Para entrar al CRM real de un cliente, el botón "🔗 CRM" abre el frontend [[crm-v2-modelo-mica]] que pega al mismo backend Arnaldo pero leyendo Airtable.

## Vínculo con el CRM modelo

El botón "🔗 CRM" de cada tenant abre `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=<slug>` → ver [[crm-v2-modelo-mica]].

> **Bug arreglado 2026-04-22**: el botón apuntaba a `lovbot-demos.vercel.app/system-ia/crm?tenant=<slug>` — URL **completamente rota** (dominio incorrecto: `lovbot-demos` es de Robert, NO de Mica + ruta `/system-ia/crm` que se eliminó hoy en la migración v2). Cambiado al dominio + ruta correctos.
> Es un caso real de violación de [[aislamiento-entre-agencias]] que pasó desapercibido por mucho tiempo.

## Hermano por agencia

[[panel-gestion-robert]] — equivalente para [[lovbot-ai|Lovbot.ai]]. Son archivos físicos casi idénticos (5 líneas de diferencia: título, branding, emoji, URL del CRM destino).

**No hay sincronización automática** entre ambos. Si se modifica uno y el otro debería tener la misma feature, hay que copiar manualmente.

## Monitoreo

Hoy NO hay check específico para este panel en [[sistema-auditoria|guardia_critica.py]]. Cuando Mica tenga dominio prod, agregar check `mica_panel_gestion` análogo al de Robert.

Pendiente de hacer junto con la activación de los checks `mica_crm` y `mica_crm_cors` que ya están preparados en el script (deshabilitados via env var `MICA_CRM_ENABLED=0`).

## Reglas

- ❌ NO confundir con [[panel-gestion-robert]] (mismo concepto, otro dueño y otra URL).
- ❌ NO usar dominios `lovbot-demos.vercel.app` ni `crm.lovbot.ai` en este panel — esos son de Robert.
- ❌ NO usar la ruta `/system-ia/crm` (eliminada en migración 2026-04-22). Usar `/system-ia/dev/crm-v2`.
- ✅ Modificar SOLO `SYSTEM-IA/admin.html`.
- ✅ Si se agrega feature acá que también beneficia a Robert, replicarla manualmente en `INMOBILIARIA/dev/admin.html`.

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22|Sesión 2026-04-22]] — fix bug crítico del botón CRM apuntando a dominio Robert
- `memory/debug-log.md` (entrada 2026-04-22)
