---
title: "Migración Lovbot completa de Vercel a Coolify Hetzner"
date: 2026-04-23
query_origin: "quiero cambiar todo lo referente de Robert a su coolify, porque cada vez que mejoramos algo nos topamos siempre con los limites de vercel y nos frena todo"
tags: [migracion, coolify, vercel, lovbot, infraestructura, dns, autodeploy, hito]
fuentes_citadas: [sesion-2026-04-22]
proyecto: robert
hito: true
---

# Migración Lovbot completa de Vercel → Coolify Hetzner (2026-04-23)

## Pregunta de origen

Arnaldo: "quiero cambiar todo lo referente de Robert a su coolify, porque cada vez que mejoramos algo nos topamos siempre con los límites de vercel y nos frena todo"

## Resumen ejecutivo

En una sesión continuada del 22 al 23 de abril 2026 se migraron **los 2 dominios productivos de Lovbot** (`crm.lovbot.ai` y `admin.lovbot.ai`) desde Vercel hacia el VPS Hetzner de Robert (gestionado por [[coolify-robert|Coolify]]). Cero downtime, todo automatizado vía Coolify Traefik + Let's Encrypt + GitHub webhooks.

**Resultado**: Lovbot ya no depende de Vercel para nada productivo. Vercel queda solo como fallback temporal mientras se valida estabilidad.

## Contexto y problema

A lo largo del 21-22 de abril, el cupo Vercel Free Plan Hobby (100 deploys/día) se agotó múltiples veces por el ritmo intenso de refactor del CRM v3 Robert + CRM v3 Mica + CRM Agencia. Quedaron commits trabados en queue por horas, con tiempo perdido diagnosticando "¿deployó o no?".

Decisión tomada el 22-04 ([[wiki/conceptos/coolify-default-deploy|coolify-default-deploy]]) y ejecutada el 23-04: migrar todo Lovbot a Hetzner.

## Lo que se migró

### Antes (22-04 y previo)

| URL | Hosting | Sirve |
|-----|---------|-------|
| `crm.lovbot.ai` | Vercel | CRM v2 Lovbot (modelo cliente) |
| `admin.lovbot.ai` | Vercel | Admin tenants (`lovbot-demos.vercel.app/dev/admin`) |
| `agentes.lovbot.ai` | Coolify Hetzner | Backend FastAPI |
| `n8n.lovbot.ai` | Coolify Hetzner | n8n |
| `chatwoot.lovbot.ai` | Coolify Hetzner | Chatwoot |
| `coolify.lovbot.ai` | Coolify Hetzner | Orquestador |

### Después (23-04)

| URL | Hosting | Sirve |
|-----|---------|-------|
| `crm.lovbot.ai/dev/crm-v2` | 🆕 **Coolify Hetzner** (app `lovbot-crm-modelo`) | CRM v2 cliente (modelo multi-tenant) |
| `admin.lovbot.ai/clientes` | 🆕 **Coolify Hetzner** (app `lovbot-admin-internal`) | [[panel-gestion-robert]] (admin Supabase tenants) |
| `admin.lovbot.ai/agencia` | 🆕 **Coolify Hetzner** (misma app) | [[crm-agencia-lovbot]] (mockup, backend Postgres pendiente) |
| `agentes.lovbot.ai` | Coolify Hetzner | (sin cambios) |
| `n8n.lovbot.ai` | Coolify Hetzner | (sin cambios) |
| `chatwoot.lovbot.ai` | Coolify Hetzner | (sin cambios) |
| `coolify.lovbot.ai` | Coolify Hetzner | (sin cambios) |
| `lovbot.ai` (landing) | otro hosting (`192.185.131.188`) | NO migrado en esta sesión — fuera de scope |

## Pasos ejecutados (cronológico)

### 1. Crear app Coolify para admin (22-04 noche)

App `lovbot-admin-internal` UUID `v0k8480sw800o00og0oo04g8`. Source: "Public Repository" (no GitHub App oficial — error que se descubrió después). Stack: Dockerfile nginx alpine. Fix de healthcheck con 4 deploys hasta que arrancó (problema de generación inline de `nginx.conf` con `printf`).

### 2. Crear app Coolify para CRM (23-04 madrugada)

App `lovbot-crm-modelo` UUID `wcgg4kk0sw0g0wgw4swowog0`. Source: GitHub App oficial (autodeploy OK desde el primer push). Dockerfile + `nginx.crm.conf` separados.

### 3. Cambios DNS en cPanel (Arnaldo manual)

| Subdominio | Antes | Después |
|-----------|-------|---------|
| `crm.lovbot.ai` | CNAME → `dba1e5fd62bb0b29.vercel-dns-017.com` | A → `5.161.235.99` |
| `admin.lovbot.ai` | CNAME → `dba1e5fd62bb0b29.vercel-dns-017.com` | A → `5.161.235.99` |

TTL bajado de `14400` a `300` para propagación rápida (5-15 min).

### 4. Validación post-DNS

Verificación con `--resolve` directo al IP del VPS Hetzner pre-propagación + verificación con DNS Google (8.8.8.8) post-propagación. Arnaldo confirmó visualmente desde ventana incógnito que las 3 URLs sirven correctamente desde Coolify.

### 5. Bug fix navegación (commit `1851623`)

El nav del sidebar en `clientes.html` y `agencia.html` tenía paths heredados de Vercel (`/dev/admin/clientes`). En Coolify Hetzner los archivos se sirven desde la raíz, así que daban 404. Cambio: `/dev/admin/clientes` → `/clientes`, `/dev/admin/agencia` → `/agencia`. Aplicado a ambos HTML.

### 6. Configurar autodeploy `lovbot-admin-internal`

Como esta app usa "Public Repository" (no GitHub App), no tenía autodeploy. Configurado webhook manual:

- **URL**: `https://coolify.lovbot.ai/webhooks/source/github/events/manual`
- **Secret**: `a8f3d2e1b9c7456082f1a3d4e5b6c7d8a9e0f1b2c3d4e5f6a7b8c9d0e1f2a3b4`
- **Events**: Just push
- Configurado en Coolify y en GitHub `Arnaldo999/system-ia-agentes` Settings → Webhooks
- Validado con ping ✅ exitoso

### 7. Sumar checks al monitor

[[sistema-auditoria|guardia_critica.py]] ahora tiene 18 checks activos (antes 14):
- `robert_crm_modelo_internal` → `https://crm.lovbot.ai/dev/crm-v2.html`
- `robert_crm_js_panel_loteos` → `https://crm.lovbot.ai/dev/js/panel-loteos.js`
- `robert_admin_clientes_internal` → `https://admin.lovbot.ai/clientes.html`
- `robert_admin_agencia_internal` → `https://admin.lovbot.ai/agencia.html`

## Commits relevantes

- `27367cf` — feat(robert/crm): app Coolify Hetzner para crm.lovbot.ai (Dockerfile + nginx.conf)
- `418751a` — docs(robert/crm): monitor + wiki + debug-log
- `1851623` — fix(robert/admin): nav links del sidebar (Coolify sirve desde raíz)
- (varios commits de fix en el Dockerfile.admin: `3ab0ce0`, `bb412f4`, `9640318`, `6403c32`, `d969e90`)

## Tokens y secrets configurados (referencia)

| Item | Valor |
|------|-------|
| LOVBOT_ADMIN_TOKEN | `lovbot-admin-2026` (default del código en `workers/shared/tenants.py`) |
| GitHub Webhook Secret (admin) | `a8f3d2e1...f2a3b4` |
| GitHub Webhook Secret (CRM) | (no necesario — usa GitHub App oficial) |

⚠️ **TODO seguridad** próxima sesión: rotar `LOVBOT_ADMIN_TOKEN` por algo random fuerte (`openssl rand -hex 32`) + override en Coolify env vars.

## Lecciones aprendidas

1. **GitHub App oficial > Public Repository** para crear apps Coolify nuevas. Si el subagente futuro crea una app, validá que esté usando GitHub App para no tener que configurar webhook manual después.

2. **El Dockerfile inline con `printf` rompe nginx**. Usar siempre `nginx.conf` como archivo separado en el repo y `COPY` desde el Dockerfile.

3. **Healthcheck con `wget 127.0.0.1` (no `localhost`)** — `localhost` puede fallar en algunas configuraciones nginx alpine.

4. **Cambio DNS A record (no CNAME)** cuando apuntás a un VPS con IP fija. CNAME funciona pero agrega latencia y complejidad.

5. **Múltiples Coolify pueden escuchar el mismo repo sin interferir**: cada uno recibe el push event en paralelo de GitHub. Por eso Coolify Arnaldo + Coolify Hetzner Robert + webhook manual Coolify Robert pueden coexistir sin pisarse.

6. **`watch_paths: null`** triggea redeploy de TODAS las apps con cualquier push, aunque solo cambien archivos no relacionados. Para optimizar: configurar `watch_paths` por app (TODO próxima sesión si los redeploys innecesarios molestan).

7. **DNS resolver local vs DNS pública**: cuando el usuario "no ve la migración", suele ser caché DNS de su compu. La realidad del servicio se valida con `--resolve` o `dig @8.8.8.8`.

## Pendientes

1. **Limpiar `vercel.json`** — sacar las reglas Lovbot cuando se valide 1-2 días que Coolify funciona estable. Hoy mantenido como fallback.
2. **Configurar `watch_paths`** en cada app Coolify para que solo redeploye cuando cambian sus archivos (optimización).
3. **Rotar `LOVBOT_ADMIN_TOKEN`** + override en Coolify (security).
4. **Migrar landing `lovbot.ai`** del hosting cPanel actual (`192.185.131.188`) a Coolify si Robert quiere unificar todo.
5. **Backend del CRM Agencia**: BD `lovbot_agencia_crm` Postgres + endpoints `/agencia/leads` (próxima sesión grande).
6. **Bot WhatsApp Agencia**: cuando Tech Provider Robert esté habilitado, crear nuevo número WABA y worker.

## Fuentes

- [[wiki/fuentes/sesion-2026-04-22]] — sesión donde nació la decisión de migrar
- [[wiki/conceptos/coolify-default-deploy]] — regla operativa que motivó este cambio
- [[wiki/entidades/crm-v2-modelo-robert]] — entidad actualizada con nueva URL/host
- [[wiki/entidades/panel-gestion-robert]] — entidad actualizada
- [[wiki/entidades/coolify-robert]] — actualizada con tabla de apps deployadas
- [[wiki/conceptos/crm-agencia-lovbot]] — referencia al producto que vive en `admin.lovbot.ai/agencia`
