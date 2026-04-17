---
name: LOVBOT CRM + SYSTEM IA CRM — SaaS Multi-agencia
description: CRM white-label multi-tenant para Lovbot (Robert) y System IA (Mica) — arquitectura multi-agencia en una sola infra
type: project
---

## Estado — LIVE (2026-04-09)

### Lovbot (Robert)
- Admin: `admin.lovbot.ai` — token: `LOVBOT_ADMIN_TOKEN` (Coolify Robert)
- CRM demo: `lovbot-demos.vercel.app/dev/crm?tenant=demo` (PIN: 1234)
- CRM producción: `crm.lovbot.ai?tenant=SLUG`
- Tenants activos: `robert` (PIN: 1234), `demo` (PIN: 1234)

### System IA (Mica)
- Admin: `system-ia-agencia.vercel.app/system-ia/admin` — token: `system-ia-admin-2026`
- CRM demo: `system-ia-agencia.vercel.app/system-ia/crm?tenant=mica-demo` (PIN: 1234)
- CRM producción: `system-ia-agencia.vercel.app/system-ia/crm?tenant=SLUG`
- Tenant demo: `mica-demo` → Airtable `appXPpRAfb6GH0xzV` (base demo Mica)
- Vercel project: `system-ia-agencia` (repo: system-ia-agentes)

### Arnaldo (Maicol y propios)
- CRM: `crm.backurbanizaciones.com` — dominio propio, 100% personalizado
- NO usa sistema de tenants/Supabase — es proyecto independiente
- Worker propio YCloud + Airtable específico, mapas SVG, loteos calibrados

---

## REGLAS DE ARQUITECTURA — RESPETAR SIEMPRE

### 1. Supabase es el único componente compartido
- Una sola instancia Supabase para Lovbot + System IA
- Separación por columna `agencia`: `lovbot` | `system-ia`
- Filtro server-side — datos NUNCA se cruzan entre agencias
- Si Mica crece y quiere su propio Supabase: solo cambiar env vars `SUPABASE_URL` + `SUPABASE_KEY`

### 2. Los 4 HTMLs son archivos físicamente separados
```
DEMOS/INMOBILIARIA/dev/crm.html      → lovbot-demos.vercel.app/dev/crm        (Lovbot dev)
DEMOS/INMOBILIARIA/demo-crm-mvp.html → crm.lovbot.ai                           (Lovbot prod)
DEMOS/SYSTEM-IA/crm.html             → system-ia-agencia.vercel.app/system-ia/crm (Mica dev+prod)
DEMOS/SYSTEM-IA/admin.html           → system-ia-agencia.vercel.app/system-ia/admin
```
- Editar uno NO afecta a los demás
- Si Mica quiere cambio: editar solo `DEMOS/SYSTEM-IA/crm.html`
- Si Robert quiere cambio: editar solo `DEMOS/INMOBILIARIA/dev/crm.html`

### 3. Flujo de actualización (dev → prod)
```
DEMOS/INMOBILIARIA/dev/crm.html  (laboratorio, iterar aquí)
    ↓ probado con Robert → bump CRM_VERSION
DEMOS/SYSTEM-IA/crm.html        (copiar cuando Mica quiera actualizarse)
    ↓ probado con Mica → bump CRM_VERSION
DEMOS/INMOBILIARIA/demo-crm-mvp.html (producción Lovbot)
```
- Producción se entera de actualización por el banner "🔔 Nueva versión" (sistema CRM_VERSION)
- Cliente NO sabe que hay actualización hasta que aparece el banner — no hay deploy forzado

### 4. Airtable siempre separado por cliente
- Cada tenant tiene su propio `airtable_base_id` en Supabase
- Robert y Mica nunca comparten bases Airtable
- El CRM lee las credenciales dinámicamente desde Supabase por slug

### 5. Los proyectos de Arnaldo son independientes
- Maicol y otros proyectos propios: CRM personalizado, NO white-label
- No pasan por Supabase tenants
- Tienen dominio propio, worker propio, todo a medida

---

## Arquitectura técnica

### Backend `workers/shared/tenants.py`
- `_ADMIN_TOKENS`: mapa token → agencia
  - `LOVBOT_ADMIN_TOKEN` (env) → `lovbot`
  - `SYSTEM_IA_ADMIN_TOKEN` (env) → `system-ia`
- `_get_agencia(request)`: valida token y retorna agencia, 403 si inválido
- `POST /admin/tenants`: asigna `agencia` automáticamente al crear
- `GET /admin/tenants`: filtra `WHERE agencia = agencia_del_token`

### Columnas Supabase `tenants`
- Base: id, slug, nombre, subniche, api_prefix, pin_hash, plan, estado_pago, fecha_alta, fecha_vence
- Branding: logo_url, color_primario, color_acento, ciudad, moneda
- Admin: email_admin, telefono_admin, monto_mensual, moneda_pago, notas, activo
- Credenciales: airtable_base_id, airtable_leads_table, airtable_props_table, airtable_api_key
- Cal.com: calcom_api_key, calcom_event_type
- WhatsApp: whatsapp_number, whatsapp_bot_name, ycloud_api_key, ycloud_webhook_secret
- Evolution: evolution_instance, evolution_api_key
- Multi-agencia: agencia (DEFAULT 'lovbot')

### Seguridad
- PIN almacenado como SHA-256, nunca en texto plano
- estado_pago calculado server-side desde fecha_vence (sin cron)
- Tenant suspendido/vencido → pantalla bloqueante en CRM
- Solo admin puede reactivar — cliente no puede saltarse el bloqueo

### Env vars en Coolify Arnaldo
- `LOVBOT_ADMIN_TOKEN` — token admin Lovbot
- `SYSTEM_IA_ADMIN_TOKEN=system-ia-admin-2026` — token admin System IA

---

## Pendiente Mica
- YCloud: número + webhook secret (pendiente que lo consiga)
- Cal.com: cuenta + evento (pendiente que lo cree)
- Primer cliente real → crear tenant desde admin con credenciales reales
- HTML prod separado: cuando Mica tenga prod, crear `DEMOS/SYSTEM-IA/crm-prod.html`
