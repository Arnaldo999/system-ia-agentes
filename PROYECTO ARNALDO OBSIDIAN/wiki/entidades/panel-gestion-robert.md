---
title: "Panel Gestión Robert (Lovbot Admin)"
type: producto
proyecto: robert
ownership: lovbot-ai
tags: [admin, panel-gestion, lovbot, coolify, hetzner, frontend]
---

# Panel Gestión Robert — Lovbot Admin

## Qué es

Panel HTML de administración de tenants (clientes) de la agencia [[lovbot-ai|Lovbot.ai]]. Desde acá Robert (o Arnaldo como socio técnico) puede:

- Listar todos los tenants (clientes inmobiliarias) onboardeados.
- Suspender / reactivar / renovar suscripción de un cliente.
- Abrir directamente el CRM v2 de cada cliente con su `tenant=<slug>` precargado.

## URL canónica (Coolify Hetzner — desde 2026-04-22)

- `https://admin.lovbot.ai/clientes.html` (canónica definitiva — Coolify Hetzner)
- `https://admin.lovbot.ai/agencia.html` (CRM agencia Lovbot — mismo host)
- `https://admin.lovbot.ai/` (redirect → `clientes.html`)

## URL Vercel (fallback temporal — mientras DNS propaga)

- `https://lovbot-demos.vercel.app/dev/admin/clientes` (fallback — no tocar)
- `https://lovbot-demos.vercel.app/dev/admin` (alias retro-compatible)

## Archivo físico

- **Path**: `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/admin/clientes.html`
  - Movido de `dev/admin.html` a `dev/admin/clientes.html` el 2026-04-22 (git mv — historial preservado)
- **Hermano en la misma carpeta**: `dev/admin/agencia.html` — CRM agencia Lovbot ([[crm-agencia-lovbot]])
- **Dockerfile**: `dev/admin/Dockerfile` — nginx:alpine, sirve ambos HTMLs, agrega redirects `/clientes` → `/clientes.html` y `/agencia` → `/agencia.html`
- **Servido por**: [[coolify-robert|Coolify Hetzner]] — app `lovbot-admin-internal` (UUID `v0k8480sw800o00og0oo04g8`)
- **Fallback**: Vercel `lovbot-demos.vercel.app/dev/admin/*` (no tocar — sigue activo)

## A qué backend pega — y por qué

`https://agentes.arnaldoayalaestratega.cloud/admin/tenants` (backend FastAPI [[arnaldo-ayala|Arnaldo]] en [[coolify-arnaldo]])

Esto es **CORRECTO y NO viola [[aislamiento-entre-agencias]]** porque el backend Arnaldo es el único con credenciales para [[supabase-tenants|Supabase]] — la base compartida donde vive el catálogo de tenants (clientes que compraron CRM). Aclarado por Arnaldo el 2026-04-22.

### Capas de datos

| Capa | Dónde vive | Quién la lee |
|------|-----------|--------------|
| Catálogo de tenants (qué clientes compraron CRM, su estado) | [[supabase-tenants\|Supabase]] (cuenta Arnaldo, compartida) | Backend Arnaldo |
| Datos del CRM Robert (leads, propiedades, contratos) | [[lovbot-crm-modelo\|Postgres `lovbot_crm_modelo`]] (Hetzner) | Backend Robert (`agentes.lovbot.ai`) |

El admin solo gestiona la **capa 1** (Supabase). Para entrar al CRM real de un cliente, el botón "🔗 CRM" abre el frontend [[crm-v2-modelo-robert]] que sí pega al backend Robert.

## Vínculo con el CRM modelo

El botón "🔗 CRM" de cada tenant abre `https://crm.lovbot.ai/dev/crm-v2?tenant=<slug>` → ver [[crm-v2-modelo-robert]].

> **Bug arreglado 2026-04-22**: el botón apuntaba a `crm.lovbot.ai/?tenant=<slug>` (URL del v1 viejo, que por catch-all servía v2 pero no era explícito). Cambiado al path explícito `/dev/crm-v2`.

## Hermano por agencia

[[panel-gestion-mica]] — equivalente para [[system-ia|System IA]]. Son archivos físicos casi idénticos (5 líneas de diferencia: título, branding, emoji, URL del CRM destino).

**No hay sincronización automática** entre ambos. Si se modifica uno y el otro debería tener la misma feature, hay que copiar manualmente.

## NO confundir con el futuro CRM agencia

Este panel gestiona **clientes que YA compraron el CRM** (catálogo `tenants` en [[supabase-tenants|Supabase]]).

El futuro [[crm-agencia-lovbot]] (pendiente de implementar) gestiona **leads de la agencia que AÚN NO compraron** (Postgres Hetzner, captura desde [[landing-lovbot-ai]] + bot agencia).

Son productos complementarios: leads → conversión → cliente. Cuando un lead del CRM agencia se convierte, se inserta un row en `tenants` y aparece en este panel.

## Despliegue en Coolify Hetzner (migración 2026-04-22)

- **App Coolify**: `lovbot-admin-internal`, UUID `v0k8480sw800o00og0oo04g8`
- **Project**: `Agentes` (UUID `ck0kccsws4occ88488kw0g80`)
- **Env**: `production`
- **Repo/branch**: `Arnaldo999/system-ia-agentes` / `main`
- **base_directory**: `/01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/admin`
- **Dockerfile**: en `base_directory/Dockerfile` — imagen `nginx:alpine`
- **FQDN**: `https://admin.lovbot.ai`
- **DNS**: A record `admin` → `5.161.235.99` (VPS Hetzner Robert) — cambio manual por Arnaldo
- **SSL**: Let's Encrypt via Traefik (Coolify proxy automático)

## Monitoreo

Checks en [[sistema-auditoria|guardia_critica.py]]:
- `robert_admin_clientes_internal` → pega a `https://admin.lovbot.ai/clientes.html`
- `robert_admin_agencia_internal` → pega a `https://admin.lovbot.ai/agencia.html`

## Reglas

- ❌ NO confundir con [[panel-gestion-mica]] (mismo concepto, otro dueño y otra URL).
- ❌ NO mezclar lógica con el admin de Mica — son archivos separados a propósito.
- ✅ Modificar SOLO `INMOBILIARIA/dev/admin/clientes.html` (no hay admin.html raíz — fue movido).
- ✅ Si se agrega feature al panel Robert que también beneficia al de Mica, replicarla manualmente en `SYSTEM-IA/admin/clientes.html`.

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22|Sesión 2026-04-22]] — sincronización ambos admins + fix botón CRM
- `memory/debug-log.md` (entrada 2026-04-22)
