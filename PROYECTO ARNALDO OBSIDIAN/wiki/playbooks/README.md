---
name: Playbooks — índice y reglas de uso
description: Playbooks vivos del ecosistema System IA Mission Control. Cada uno es un patrón repetible destilado de experiencias reales. Leer ANTES de arrancar trabajo del tipo correspondiente para no repetir errores ya resueltos.
type: index
proyecto: global
tags: [playbooks, patrones, indice]
ultima_actualizacion: 2026-04-24
---

# Playbooks del ecosistema

> **Qué es un playbook**: un patrón repetible destilado de **experiencia real** (no teoría). Cada vez que completás un trabajo del tipo X y aprendés algo, se **actualiza** el playbook correspondiente. Así el conocimiento se acumula en vez de perderse.

## Los 6 playbooks activos

| # | Playbook | Qué construye | Versión | Última iteración |
|---|----------|---------------|---------|------------------|
| 1 | [worker-whatsapp-bot](worker-whatsapp-bot.md) | Bot WhatsApp conversacional (BANT, 1-a-1, LLM parsing) | v1 | 2026-04-24 |
| 2 | [worker-social-automation](worker-social-automation.md) | Publicación auto FB+IG + bot comentarios + bot DMs | v1 | 2026-04-24 |
| 3 | [crm-html-tailwind](crm-html-tailwind.md) | CRM/panel admin con HTML+Tailwind CDN+JS vanilla | v1 | 2026-04-24 |
| 4 | [postgres-multi-tenant](postgres-multi-tenant.md) | BD Postgres aislada por cliente (workspaces) | v1 | 2026-04-24 |
| 5 | [airtable-schema-setup](airtable-schema-setup.md) | Base Airtable con schema estándar para brandbook/CRM | v1 | 2026-04-24 |
| 6 | [propuesta-cliente-coolify](propuesta-cliente-coolify.md) | Landing/propuesta pública en `clientes-publicos/{slug}/` | v1 | 2026-04-24 |

## Regla de uso

**ANTES de empezar cualquier trabajo que caiga en una de estas categorías**: leer el playbook correspondiente. Es 5 minutos que te ahorran horas de re-descubrimiento.

**DESPUÉS de completar un trabajo** que te hizo aprender algo nuevo (bug raro, solución elegante, gotcha de provider): abrir el playbook y agregar la lección en la sección "Histórico de descubrimientos". Si es un gotcha reutilizable, promoverlo a la sección "Gotchas conocidos".

## Orden sugerido de activación

Cuando arranca una sesión sobre un cliente nuevo (ej: Cesar Posada turismo):

1. Leer `wiki/conceptos/onboarding-cliente-nuevo-arnaldo.md`
2. Leer el playbook que corresponda al entregable (ej: `worker-whatsapp-bot.md` si es bot)
3. Si hay CRM: leer `crm-html-tailwind.md`
4. Si hay propuesta/landing: leer `propuesta-cliente-coolify.md`
5. Si requiere multi-tenant Postgres: leer `postgres-multi-tenant.md`

## Relación con otras piezas de la wiki

- **Conceptos** (`wiki/conceptos/`): definen qué es X (ej: "qué es BANT"). Los playbooks definen **cómo aplicarlo** paso a paso.
- **Runbooks** (dentro de conceptos): son playbooks de un caso muy específico (ej: `runbook-meta-social-automation.md`). Los playbooks generalizan ese conocimiento a todos los tipos del mismo trabajo.
- **Síntesis** (`wiki/sintesis/`): registro cronológico de cada iteración importante. Los playbooks son la versión **destilada y estable** de esas síntesis.

## Cómo evoluciona un playbook

1. **v1 (hoy)** — Captura el estado actual con los gotchas conocidos
2. **vN+1** — Cada cliente nuevo que pasa por el playbook puede detectar:
   - Un nuevo gotcha que no estaba → se agrega
   - Un paso que ya no hace falta → se marca como legacy y se elimina
   - Una automatización posible → se promueve a script en `02_OPERACION_COMPARTIDA/execution/`
3. **vFinal (objetivo)** — Todo el playbook automatizado con 1 comando. Ahí dejó de ser playbook y se volvió **tool**.

## Anti-patrones a evitar

- ❌ Playbook aspiracional (*"lo que debería hacerse"*). Cada paso debe haberse ejecutado al menos una vez.
- ❌ Playbook abstracto sin archivos/URLs/comandos concretos. Debe poder seguirse copiando y pegando.
- ❌ Duplicación de info que ya existe en `conceptos/`. Los playbooks LINKEAN a conceptos, no los reescriben.
- ❌ Actualizar playbooks solo cuando hay bugs. También hay que capturar **qué funcionó bien** para replicarlo.
