---
title: "Decisión arquitectural — 1 tenant demo por agencia en Supabase"
date: 2026-04-18
query_origin: "Arnaldo preguntó si tenía sentido tener 2 tenants robert+demo cuando ambos apuntaban a datos simulados"
tags: [compartido, arquitectura, supabase, tenants, crm-saas, multi-tenant]
fuentes_citadas: []
proyecto: compartido
---

# Decisión: 1 tenant demo por agencia en Supabase

## Pregunta de origen

Arnaldo observó que el admin de Robert (`lovbot-demos.vercel.app/dev/admin`) mostraba **2 tenants** (`demo` + `robert`) pero el admin de Mica (`system-ia-agencia.vercel.app/system-ia/admin`) solo mostraba **1** (`mica-demo`). Al revisar, ambos tenants de Robert (`demo` y `robert`) estaban apuntando a **los mismos datos demo** — no había cliente real productivo detrás.

La pregunta: ¿tiene sentido mantener el duplicado?

## Síntesis

**No.** Son duplicados funcionales sin valor agregado.

### Arquitectura original (pre 2026-04-18)

```
Supabase tenants:
├── demo         (agencia=lovbot)     → Airtable demo compartido
├── robert       (agencia=lovbot)     → PostgreSQL robert_crm (con datos simulados)
└── mica-demo    (agencia=system-ia)  → Airtable demo compartido
```

**Razón histórica**: al principio se pensó `demo` como "demo técnica para presentar prospectos" y `robert` como "producción de Robert" para probar que el flow productivo funcionaba. Pero cuando el bot de Robert pasó a usar PostgreSQL y datos simulados, los 2 tenants se volvieron funcionalmente idénticos.

### Arquitectura nueva (post 2026-04-18)

```
Supabase tenants:
├── demo         (agencia=lovbot)     → Demo presentación Robert/Lovbot
└── mica-demo    (agencia=system-ia)  → Demo presentación Mica/System IA
```

**Regla**: 1 tenant demo por agencia. Los clientes reales se crean automáticamente via `/public/waba/onboarding` con su propio slug (ej: `inmobiliaria-garcia`).

## Qué se tocó y qué NO

### ✅ Eliminado
- `DELETE FROM tenants WHERE slug='robert'` en Supabase.

### ❌ Intacto (diferente al tenant Supabase)
- `waba_clients` en PostgreSQL `robert_crm` — registro del bot productivo del WhatsApp +52 998 743 4234 (db_id=1, slug `robert-inmobiliaria`). Esto es LA TABLA DEL BOT, no del CRM SaaS.
- Worker `workers/clientes/lovbot/robert_inmobiliaria/worker.py` activo en producción Coolify.
- Chatwoot agents (ninguno estaba asociado al tenant Supabase borrado).
- Proyectos Vercel (todos siguen en uso).
- Código Python que menciona "robert" (son imports y lógica del bot productivo, no del tenant CRM).

## Separación clave — 3 niveles de "robert"

Es crucial distinguir:

| Nivel | Ubicación | Qué es | Post-limpieza 2026-04-18 |
|-------|-----------|--------|--------------------------|
| 1. Tenant CRM SaaS | Supabase `tenants` | Registro de un cliente del producto "CRM SaaS Lovbot" | ❌ **Eliminado** |
| 2. Registro WABA | PG `waba_clients` (robert_crm) | Mapeo `phone_number_id → worker_url` del bot | ✅ Intacto (db_id=1) |
| 3. Código worker | `workers/clientes/lovbot/robert_inmobiliaria/` | Código Python del bot +52 998 | ✅ Intacto |

Los 3 niveles tenían nombres similares pero son conceptualmente independientes. Solo se tocó el nivel 1.

## Consecuencia en el admin

### Antes
```
Admin Robert (LOVBOT_ADMIN_TOKEN):
  Total: 2
  ├── demo   (Al día)
  └── robert (Al día, $99 USD)   ← CONFUSO: era demo también
```

### Después
```
Admin Robert (LOVBOT_ADMIN_TOKEN):
  Total: 1
  └── demo (Al día)
```

Queda **paridad** con el admin de Mica (también 1 solo demo).

## Cuándo volverá a haber clientes productivos

Cuando Meta apruebe el Advanced Access (solicitud de Robert del lunes 2026-04-21, 2-10 días de espera), el flow será:

1. Un cliente real (ej: Inmobiliaria García) entra a `https://lovbot-onboarding.vercel.app/?client=inmobiliaria-garcia`
2. Conecta su WhatsApp Business via Embedded Signup
3. El backend ejecuta `/public/waba/onboarding`:
   - Crea tenant Supabase `inmobiliaria-garcia` (agencia=lovbot)
   - Crea registro en PG `waba_clients` (db_id=2 o siguiente)
   - Crea inbox Chatwoot + agent con email del cliente
   - Envía email Resend + WhatsApp con credenciales
4. Robert ve en su admin: `demo` + `inmobiliaria-garcia` (2 tenants — el segundo ES cliente real)

## Fuentes

Esta decisión se tomó en sesión Claude del 2026-04-18 entre 09:00-10:40 UTC.
Commits relacionados: ver `git log --grep="tenant robert"` en el repo.

## Relaciones con otras páginas

- [[wiki/entidades/lovbot-ai]] — estado actualizado post-limpieza
- [[wiki/entidades/robert-bazan]] — estado actualizado post-limpieza
- [[wiki/conceptos/matriz-infraestructura]] — sigue válida, no tocada
- [[log]] — entrada `2026-04-18` con detalle
