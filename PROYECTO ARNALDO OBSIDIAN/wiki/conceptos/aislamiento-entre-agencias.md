---
title: "Aislamiento entre agencias"
tags: [regla-irrompible, aislamiento, router, arquitectura]
source_count: 0
proyectos_aplicables: [arnaldo, robert, mica]
---

# Aislamiento entre agencias

## Definición

[[arnaldo-ayala]] es el **hub** (centro operativo) de un ecosistema con **3 agencias independientes**. Arnaldo está asociado individualmente con cada uno de los otros dos dueños (Robert y Mica) a través de **dos sociedades separadas**, pero **las tres agencias nunca se cruzan entre sí**.

## Modelo topológico

```
              [[agencia-arnaldo-ayala]]
                    (Arnaldo)
                  dueño único
                  🟢 LIVE
                       |
         +----sociedad----+----sociedad----+
         |                                 |
         ↓                                 ↓
  [[lovbot-ai]]                    [[system-ia]]
    (Robert)                          (Mica)
   Arnaldo socio                  Arnaldo socio
     técnico                         técnico
   🟠 construcción                 🟡 sin LIVE
```

**Clave**: las 2 sociedades (Arnaldo↔Robert y Arnaldo↔Mica) son **independientes entre sí**. Robert no tiene nada que ver con Mica y viceversa — no se conocen comercialmente, no comparten clientes, no comparten datos, no comparten stack.

## Qué NO se cruza nunca

| Aspecto | Regla |
|---------|-------|
| **Clientes** | Un cliente de [[agencia-arnaldo-ayala]] NUNCA es cliente de Lovbot o System IA. Idem para los otros. |
| **Datos** | Datos de [[back-urbanizaciones]] jamás tocan [[postgresql]] `robert_crm` ni la base Airtable de Mica. |
| **Bases de datos** | [[airtable]] Arnaldo ↔ [[airtable]] Mica ↔ [[postgresql]] Robert son **3 silos**. Nunca migrar registros entre ellas. |
| **WhatsApp providers** | [[ycloud]] (Arnaldo), [[meta-graph-api]] (Robert), [[evolution-api]] (Mica + Lau) — 3 caminos paralelos. |
| **Env vars** | `OPENAI_API_KEY` (Arnaldo) ≠ `LOVBOT_OPENAI_API_KEY` (Robert). Prefijos obligatorios. |
| **Credenciales n8n** | 3 instancias n8n aisladas, con credenciales apuntando a su propio stack. |
| **Dominios** | `arnaldoayalaestratega.cloud`, `lovbot.ai`, `6g0gdj.easypanel.host` (Mica) — nunca mezclar DNS. |
| **Repos GitHub** | Un solo repo compartido (`system-ia-agentes`) pero **separados lógicamente** por `workers/clientes/[agencia]/*`. |

## Qué SÍ puede ser compartido (servicios neutros, prestados por Arnaldo)

Desde [[vps-hostinger-arnaldo]] Arnaldo ofrece como **proveedor de servicios** a las otras 2 agencias:

- **Cal.com** — agendador único para los 3 (Robert y Mica agendan con la cuenta de Arnaldo).
- **Supabase** — CRM SaaS multi-tenant (Robert y Mica guardan **solo sus tenants** acá, no datos del bot).
- **Cuenta OpenAI** (`OPENAI_API_KEY`) — compartida con Mica (porque Mica no tiene cuenta propia). ⚠️ NO se comparte con Robert (Robert tiene `LOVBOT_OPENAI_API_KEY`).
- **Cuenta Gemini** — compartida con las 2 como fallback.

Incluso estos recursos compartidos mantienen **datos segregados por tenant** — Robert no ve los tenants de Mica en Supabase, ni viceversa.

## Trampas detectadas en sesiones anteriores

1. **[[lau]]** — path `workers/clientes/system_ia/lau/` hizo asumir que era de System IA. Es de Arnaldo (familia).
2. **`AIRTABLE_TOKEN` en worker de Robert** — código legacy que no se usa. Robert NO debe tener referencias a Airtable.
3. **`OPENAI_API_KEY` en código de Robert** — debe ser `LOVBOT_OPENAI_API_KEY`.
4. **Base Airtable vieja de Mica** (`appXPpRAfb6GH0xzV`) — la correcta es `appA8QxIhBYYAHw0F`.
5. **Deploy a Coolify Arnaldo creyendo que es Robert** — Robert tiene Coolify Hetzner separado (`coolify.lovbot.ai`).

## Relación con la regla de atribución

Este aislamiento requiere aplicar siempre [[regla-de-atribucion]]: **preguntar primero a cuál agencia pertenece el trabajo**.

## Consecuencias prácticas para el agente (Claude)

Cuando trabajes en cualquier tarea:

1. Identificar la agencia (paso 0).
2. Cargar SOLO el contexto de esa agencia: su VPS, su orquestador, su DB, su provider WhatsApp, sus env vars.
3. **Bloquear mentalmente** los otros dos stacks como inexistentes para esa tarea.
4. Si hay que hacer algo que cruce 2 agencias (muy raro), **preguntar al usuario qué parte corresponde a cuál** y separar la operación en 2 invocaciones distintas.

## Fuentes que lo mencionan

- `feedback_REGLA_infraestructura_clientes.md` (memory Mission Control)
- `feedback_REGLA_CRITICA_proyecto_destino.md` (memory Mission Control)
- Sesión 2026-04-17 con Arnaldo (reestructuración wiki).
