---
title: "Regla de atribución: ¿quién es quién?"
tags: [regla-irrompible, atribucion, router, disambiguation]
source_count: 0
proyectos_aplicables: [arnaldo, robert, mica]
---

# Regla de atribución — ¿quién es quién?

## Definición

**Antes de editar código, deployar, operar APIs, mandar curl, o modificar bases de datos**, el agente (humano o LLM) debe preguntar explícitamente:

> **"¿Este cliente / proyecto / recurso corresponde a cuál de las 3 agencias?"**
> - [[agencia-arnaldo-ayala|Arnaldo Ayala — Estratega en IA y Marketing]] (mía propia)
> - [[system-ia]] (de Micaela Colmenares, socia)
> - [[lovbot-ai]] (de Robert Bazán, socio)

Jamás asumir por contexto implícito.

## Las 3 agencias

| Agencia | Dueño | Arnaldo es… | Estado clientes |
|---------|-------|-------------|------------------|
| [[agencia-arnaldo-ayala]] | [[arnaldo-ayala]] | dueño | 🟢 LIVE: [[maicol]], [[lau]] |
| [[system-ia]] | [[micaela-colmenares]] | socio técnico | 🟡 sin producción propia aún |
| [[lovbot-ai]] | [[robert-bazan]] | socio técnico | 🟠 en construcción (sin clientes externos LIVE) |

## Por qué la regla existe

Se viola esta regla repetidamente con consecuencias concretas:
- Editar [[airtable]] creyendo que es Robert, cuando Robert usa [[postgresql]]
- Usar `OPENAI_API_KEY` (Arnaldo) en código de Robert (debe ser `LOVBOT_OPENAI_API_KEY`)
- Asumir Coolify Hostinger cuando el proyecto es Hetzner
- Tomar a [[lau]] como cliente de [[system-ia]] porque vive en `workers/clientes/system_ia/lau/` (path legacy)

El problema no es falta de información — la info está en [[matriz-infraestructura]]. El problema es **saltarse la pregunta**.

## Disparadores que deberían activar la regla

La regla se aplica **siempre**, pero hay disparadores inequívocos:

- Path de archivo contiene `clientes/[arnaldo|lovbot|system_ia]/`
- Usuario dice nombres de clientes: Maicol, Lau, nuevo cliente sin decir agencia
- Usuario pide deploy sin decir VPS
- Usuario menciona "bot" sin decir proyecto
- Operación externa: curl a Coolify/Airtable/Supabase/MCP
- Edición de `.env` o variables de entorno

## Protocolo de confirmación

Cuando hay ambigüedad, responder **primero** con:

> "Antes de avanzar, confirmame: ¿este [cliente / proyecto / recurso] corresponde a mi agencia (Arnaldo Ayala), a System IA (Mica), o a Lovbot.ai (Robert)?"

Solo después de la confirmación: proceder.

## Regla derivada — path engañoso

La ubicación de un archivo NO determina a qué agencia pertenece. Casos:

- `workers/clientes/system_ia/lau/` → **agencia Arnaldo** (Lau es esposa de Arnaldo, path legacy)
- `workers/clientes/lovbot/robert_inmobiliaria/` → **agencia Lovbot** ✅
- `workers/clientes/arnaldo/maicol/` → **agencia Arnaldo** ✅
- Fuera del repo, cualquier URL con `arnaldoayalaestratega.cloud` → puede ser de Arnaldo O un servicio compartido que usan los 3. Confirmar.

## Relación con subagentes de Claude Code

Esta regla está operacionalizada en 3 subagentes de `.claude/agents/`:
- `proyecto-arnaldo` → activa bajo paths de Arnaldo
- `proyecto-robert` → activa bajo paths de Robert
- `proyecto-mica` → activa bajo paths de Mica

Y en el hook `.claude/hooks/detect-project-context.sh` que warning cuando detecta mezcla de stacks.

## Fuentes que lo mencionan

- `feedback_REGLA_CRITICA_proyecto_destino.md` (memory Mission Control)
- `feedback_REGLA_infraestructura_clientes.md` (memory Mission Control)
