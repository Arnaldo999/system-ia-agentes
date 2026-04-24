---
description: Crea un plan de implementación formal archivado en 02_OPERACION_COMPARTIDA/planes/YYYY-MM-DD-nombre.md. Úsalo antes de features grandes, refactors, migraciones o cuando arranque un cliente pago nuevo. NO usar para bugs, tareas cortas o trabajo que ya tiene playbook.
---

# Crear plan

Creá un plan de implementación detallado para un cambio grande en el ecosistema. Los planes son documentos formales que capturan contexto, justificación, decisiones arquitectónicas y tareas paso a paso.

## Argumento

$ARGUMENTS — descripción de qué querés planificar (ej: "migrar CRM de Vercel a Coolify", "onboardear cliente María con BD Postgres dedicada", "refactor worker social para soportar TikTok").

---

## Cuándo NO usar este comando (leer primero)

**STOP** si el pedido cae en alguno de estos casos — no hace falta plan formal:

| Caso | En vez de plan, usar |
|------|----------------------|
| Bug fix, error en producción | Corregir directo + actualizar `memory/debug-log.md` |
| Tarea de <30 min | Hacerla directo, TodoWrite si querés trackear |
| Pregunta / consulta | Responder directo |
| Trabajo que tiene playbook en `PROYECTO ARNALDO OBSIDIAN/wiki/playbooks/` | Leer el playbook y ejecutar — el playbook ES el plan |
| Deploy rutinario | Skill `/deploy` |
| Sync CRM dev→prod | Skill `/sync-crm-prod` |

Si el pedido cae acá, **decirle al usuario** "esto no necesita plan formal, puedo hacerlo directo" y proceder sin crear plan.

---

## Cuándo SÍ usar este comando

✅ Feature nueva que toca 3+ archivos o sistemas (bot + CRM + BD a la vez)
✅ Migración de infraestructura (Vercel→Coolify, Airtable→Postgres, provider→provider)
✅ Refactor arquitectónico (schema change, tenant model, multi-tenancy)
✅ Cliente pago nuevo con 3+h de trabajo coordinado
✅ Cambio con riesgo alto de romper producción
✅ Decisión que querés archivar para consultar en 3 meses por qué se hizo así

---

## Proceso — 4 fases

### Fase 0 — Identificar agencia (OBLIGATORIO)

Antes de escribir nada, aplicar REGLA #0 del router (CLAUDE.md raíz):

- ¿Es para **Arnaldo**, **Robert (Lovbot)** o **Mica (System IA)**?
- ¿Es **global / compartido** (afecta al Mission Control, hooks, skills)?

Si no está claro: PREGUNTAR al usuario antes de continuar. No asumir.

### Fase 1 — Investigación

**Leer siempre** (en este orden):

1. `CLAUDE.md` raíz — router de proyectos + regla silos
2. `PROYECTO ARNALDO OBSIDIAN/index.md` — índice wiki
3. Si existe playbook relacionado en `wiki/playbooks/` — leerlo entero (puede resolver el pedido sin plan)
4. `memory/ESTADO_ACTUAL.md` — qué está en curso hoy
5. `memory/debug-log.md` — bugs conocidos del área

**Leer según agencia identificada**:

- Arnaldo → `wiki/entidades/agencia-arnaldo-ayala.md`, `wiki/conceptos/matriz-infraestructura.md`
- Robert → `wiki/entidades/lovbot-ai.md`, `wiki/entidades/coolify-robert.md`, `wiki/entidades/lovbot-crm-modelo.md`
- Mica → `wiki/entidades/system-ia.md`, `wiki/entidades/easypanel-mica.md`
- Global → `.claude/hooks/`, `.claude/skills/`, `.claude/settings.json`

**Leer archivos afectados específicos** (según el pedido):

- Si toca workers: leer worker demo + worker cliente target
- Si toca CRM: leer HTML actual + endpoints FastAPI
- Si toca BD: leer schema actual (`\dt` en Postgres o base Airtable)

### Fase 2 — Construir el plan

Crear archivo en: `02_OPERACION_COMPARTIDA/planes/YYYY-MM-DD-{slug-descriptivo}.md`

- **Fecha**: hoy, formato ISO `2026-04-24-`
- **Slug**: kebab-case, español sin tildes, descriptivo pero corto
  - ✅ `2026-04-24-onboarding-cliente-maria.md`
  - ✅ `2026-04-24-migrar-maicol-system-user.md`
  - ❌ `plan1.md`, `cosas importantes.md`

Usar el formato exacto de más abajo. Llenar todas las secciones con contenido específico — sin placeholders genéricos.

### Fase 3 — Reportar y entregar

Después de crear el plan, dar al usuario:

1. **Resumen de 2-3 líneas** de qué cubre el plan
2. **Preguntas abiertas** que bloquean la ejecución (si las hay)
3. **Ruta completa** del archivo creado: `02_OPERACION_COMPARTIDA/planes/YYYY-MM-DD-{slug}.md`
4. **Próximo paso**: "Cuando revises y confirmes, ejecutá `/implementar 02_OPERACION_COMPARTIDA/planes/YYYY-MM-DD-{slug}.md`"

**NO implementar nada durante `/crear-plan`**. El comando solo escribe el plan. La ejecución es de `/implementar`.

---

## Formato exacto del plan

```markdown
# Plan: <título descriptivo>

**Creado**: YYYY-MM-DD
**Estado**: Borrador
**Proyecto**: arnaldo | robert | mica | compartido | global
**Pedido**: <resumen de 1 línea de lo que se solicitó>

---

## Descripción general

### Qué logra este plan

<2-3 oraciones describiendo el resultado final y por qué importa>

### Por qué importa ahora

<Conectá con los objetivos. ¿Qué desbloquea? ¿Qué problema resuelve? ¿Qué cliente depende?>

---

## Estado actual

### Estructura existente relevante

<Listar archivos, BDs, endpoints, configs que existen y se relacionan con este cambio. Ser específico con paths y nombres.>

### Brechas o problemas que se abordan

<Qué falta, qué está roto, qué es subóptimo — lo que este plan soluciona>

### Playbook/concepto relacionado (si aplica)

<Link al playbook de `wiki/playbooks/` o concepto de `wiki/conceptos/` que aplica. Si no hay playbook y este plan va a crear uno nuevo → notarlo.>

---

## Cambios propuestos

### Resumen de cambios

- <Cambio alto nivel 1>
- <Cambio alto nivel 2>

### Archivos nuevos a crear

| Ruta | Propósito |
|------|-----------|
| `ruta/archivo.ext` | <descripción> |

### Archivos a modificar

| Ruta | Cambios |
|------|---------|
| `ruta/archivo.ext` | <qué se modifica> |

### Archivos a eliminar (si aplica)

| Ruta | Razón |
|------|-------|
| `ruta/archivo.ext` | <por qué eliminarlo> |

### Cambios en infraestructura externa

<Listar cambios en: BDs (CREATE/ALTER), Coolify env vars, Airtable schema, Supabase tablas, webhooks Meta, n8n workflows, etc. Cada uno con el comando o acción exacta.>

---

## Decisiones de diseño

### Decisiones clave tomadas

1. **<Decisión>**: <justificación>
2. **<Decisión>**: <justificación>

### Alternativas consideradas

<Qué otros enfoques se evaluaron y por qué se rechazaron. Importante para consultar en 3 meses por qué NO se hizo X.>

### Preguntas abiertas (bloquean la ejecución)

<Listar decisiones que requieren input del usuario ANTES de implementar. Si hay preguntas abiertas, el plan va a quedar en "Borrador" hasta resolverlas.>

- [ ] <Pregunta 1>
- [ ] <Pregunta 2>

---

## Tareas paso a paso

Ejecutar en este orden durante `/implementar`.

### Paso 1 — <Título>

<Descripción detallada>

**Acciones**:
- <acción específica>
- <acción específica>

**Archivos afectados**:
- `ruta/archivo.ext`

**Validación**:
- <cómo verificar que este paso quedó bien>

---

### Paso 2 — <Título>

<Continuar con todos los pasos...>

---

## Conexiones y dependencias

### Qué referencia esta área

<Archivos/sistemas que consumen lo que vamos a modificar. Si rompemos algo, ¿quién se entera?>

### Actualizaciones necesarias para consistencia

<Docs, wiki, memory, CLAUDE.md que necesitan actualización al terminar>

### Impacto en flujos existentes

<Qué workflows n8n, bots, CRMs, hooks se ven afectados>

### Riesgos

<Qué podría salir mal. Plan de rollback si aplica.>

---

## Lista de validación

Cómo verificar que la implementación quedó completa:

- [ ] <Verificación 1 — ej: "Worker nuevo responde OK a POST /whatsapp">
- [ ] <Verificación 2 — ej: "BD maria_crm tiene 15 tablas del modelo">
- [ ] <Verificación 3 — ej: "Webhook Meta suscrito y retorna success=true">
- [ ] Wiki actualizada (nueva entidad cliente / concepto / playbook si aplica)
- [ ] Memory `ESTADO_ACTUAL.md` refleja el cambio
- [ ] CLAUDE.md actualizado si cambió la estructura del workspace
- [ ] Playbook correspondiente actualizado si se descubrió algo nuevo

---

## Criterios de éxito

El plan está completo cuando:

1. <Criterio específico y medible>
2. <Criterio específico y medible>
3. <Criterio específico y medible>

---

## Notas

<Contexto adicional, consideraciones futuras, trabajos follow-up que quedan para después>

---

## Notas de implementación

_Esta sección se completa al final de `/implementar`._

**Implementado**: <YYYY-MM-DD>

### Resumen

<Qué se hizo>

### Desviaciones del plan

<Cambios respecto al plan original, o "Ninguna">

### Problemas encontrados

<Bugs durante implementación y cómo se resolvieron, o "Ninguno">

### Descubrimientos nuevos

<Si aprendimos algo que debe ir a: playbook / concepto wiki / auto-memory / memory debug-log>
```

---

## Estándares de calidad

- **Completitud**: cada sección llenada con contenido específico (no placeholders)
- **Accionabilidad**: los pasos son ejecutables por `/implementar` sin preguntar
- **Consistencia**: respeta convenciones existentes (paths, naming, silos)
- **Claridad**: alguien en 3 meses entiende por qué se hizo así
- **Alineación con silos**: plan NO duplica info que vive en wiki/memory/auto-memory

---

## Notas finales

- Un plan bien hecho ahorra horas en implementación
- Mejor invertir 15 min en un plan claro que 2h revirtiendo algo mal planeado
- Si durante la investigación descubrís que hay un playbook que resuelve esto sin plan formal → detenerse, avisarle al usuario y ejecutar vía playbook
