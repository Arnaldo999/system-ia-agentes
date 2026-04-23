---
title: "Supabase como registro de tenants (clientes que adquieren CRM)"
tags: [supabase, tenants, crm, registro-clientes, multi-tenancy, base-compartida]
source_count: 1
proyectos_aplicables: [robert, mica]
---

# Supabase — registro de tenants (clientes que adquieren CRM)

## Definición

Base Supabase **compartida entre las dos agencias que venden CRM como servicio** ([[lovbot-ai|Lovbot]] y [[system-ia|System IA]]). Vive en la cuenta Supabase de [[arnaldo-ayala|Arnaldo]] y guarda la tabla `tenants`: el registro maestro de qué cliente compró qué CRM, su estado de suscripción (activo/suspendido), su slug, fecha de renovación, etc.

**No guarda los datos del CRM en sí** (esos viven cada uno en su BD propia: [[lovbot-crm-modelo|Postgres Lovbot]] o [[inmobiliaria-demo-mica-airtable|Airtable Mica]]). Supabase solo es el **catálogo de quién es cliente y cómo está su cuenta**.

**Tampoco guarda los leads de las agencias** (gente que aún NO compró el CRM). Los leads de la agencia Lovbot van a Postgres Hetzner — ver [[crm-agencia-lovbot]] (decisión arquitectural 2026-04-22). Esto es para mantener separación clara: Supabase = catálogo público de clientes activos; Postgres por agencia = leads privados de funnel propio.

## Por qué es compartido

A pesar de la regla de [[aislamiento-entre-agencias|aislamiento entre agencias]], Supabase se comparte porque:

- Es **infraestructura de Arnaldo** que ambas agencias usan como socio técnico.
- La tabla `tenants` distingue clientes de Robert vs clientes de Mica vía un campo (`agencia` o similar).
- Cada agencia ve solo sus tenants en su panel de gestión (filtrado por agencia/ownership).

> **Ver memoria persistente**: `feedback_supabase_tenants_lovbot.md` (Silo 1) — regla específica sobre qué tenants existen y cómo se crean nuevos clientes.

## Flujo de uso

```
[Operador (Arnaldo o Mica)] 
  → abre [[panel-gestion-robert]] o [[panel-gestion-mica]]
  → frontend HTML hace fetch a https://agentes.arnaldoayalaestratega.cloud/admin/tenants
  → backend FastAPI Arnaldo consulta tabla tenants en Supabase
  → backend devuelve la lista filtrada según la agencia
  → operador ve lista, puede suspender/reactivar/renovar
  → al hacer click en "🔗 CRM" se abre el CRM v2 de la agencia con ?tenant=<slug>
```

## Por qué los 2 paneles pegan al mismo backend

Ambos [[panel-gestion-robert|admin Robert]] y [[panel-gestion-mica|admin Mica]] hacen fetch a `https://agentes.arnaldoayalaestratega.cloud/admin/tenants` (backend Arnaldo en [[coolify-arnaldo]]).

Esto es **correcto**, no viola aislamiento, porque:

1. **Supabase es infra Arnaldo** (no de Robert ni de Mica).
2. El backend Arnaldo es el único con credenciales Supabase.
3. Los datos del CRM en sí (leads, propiedades, contratos) viven separados por agencia (Postgres para Robert, Airtable para Mica) — eso sí está aislado.

## Servicio actual (2026-04-22)

Por ahora **el único servicio que se vende es el CRM**. Los admins listan, suspenden, reactivan y renuevan suscripciones del CRM.

A futuro, si las agencias venden otros servicios (bot WhatsApp standalone, integraciones específicas, n8n workflows, etc.), la tabla `tenants` se puede extender con campos por servicio (`crm_activo`, `bot_activo`, `n8n_activo`) o evolucionar a un modelo de "subscription" multi-producto.

## Reglas operativas

- ❌ NO crear tenants directamente desde Supabase Studio. Usar siempre `/public/waba/onboarding` o el endpoint admin `/admin/tenants` (POST).
- ❌ NO compartir credenciales Supabase con clientes — solo el operador (Arnaldo o Mica con auth) debe acceder.
- ❌ NO mezclar la tabla `tenants` con el contenido del CRM — son dos capas distintas.
- ✅ Cada cliente nuevo entra como un row en `tenants` con `agencia=lovbot` o `agencia=system_ia`.
- ✅ El campo `slug` es el identificador que se usa en URL (`?tenant=<slug>`).
- ✅ El campo `estado` controla si el botón "🔗 CRM" funciona o muestra suspendido.

## Ownership

- **Cuenta Supabase**: Arnaldo (compartida entre agencias hermanas).
- **Backend que lee/escribe**: backend FastAPI Arnaldo en [[coolify-arnaldo]].
- **Frontends que consumen**: [[panel-gestion-robert]] y [[panel-gestion-mica]].

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22]] — sesión donde Arnaldo aclaró la conexión Admin→Supabase
- `feedback_supabase_tenants_lovbot.md` (Silo 1)
