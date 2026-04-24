# Planes de implementación

> Carpeta para planes formales de features grandes, refactors, migraciones y cambios estructurales del ecosistema.

## Cuándo usar esta carpeta

Un **plan formal** se justifica cuando:

- El cambio involucra ≥3 archivos o múltiples sistemas (ej: bot + CRM + BD)
- Hay decisiones arquitectónicas que impactan a futuro (ej: migración de provider, refactor schema)
- Tiene riesgo de romper cosas en producción (ej: downgrade de paquetes, cambio de tenant model)
- Arrancás con un cliente pago nuevo (3+h de trabajo coordinado)
- Querés archivar la decisión para consultar en 3 meses por qué se hizo así

**No usar para**:
- Bug fixes simples (van a `memory/debug-log.md`)
- Tareas de <30 min (TodoWrite alcanza)
- Consultas/preguntas (no generan plan)
- Trabajo que ya tiene playbook (ejecutar directo, el playbook ES el plan)

## Cómo funciona

1. Usás `/crear-plan <descripción>` → creo un doc `YYYY-MM-DD-nombre.md` acá
2. Revisás el plan, aclarás preguntas abiertas
3. Usás `/implementar planes/YYYY-MM-DD-nombre.md` → ejecuto paso a paso
4. Al terminar, marco el plan como "Implementado" con notas de desviaciones

## Estructura del archivo

Cada plan sigue el formato definido en `.claude/commands/crear-plan.md`:

```
# Plan: <título>
**Estado**: Borrador | Listo | Implementado | Archivado
**Creado**: YYYY-MM-DD
**Proyecto**: arnaldo | robert | mica | compartido | global

## Descripción general
## Estado actual (qué existe hoy)
## Cambios propuestos (archivos nuevos/modificados/eliminados)
## Decisiones de diseño + alternativas consideradas
## Preguntas abiertas (bloqueos antes de ejecutar)
## Tareas paso a paso
## Conexiones y dependencias
## Lista de validación
## Criterios de éxito
## Notas de implementación (se llena al terminar)
```

## Convenciones de nombres

- **Fecha**: formato ISO `2026-04-24-` al principio
- **Nombre**: kebab-case, español sin tildes, descriptivo pero corto
  - ✅ `2026-04-24-migrar-lovbot-coolify.md`
  - ✅ `2026-04-24-crm-v3-persona-unica.md`
  - ❌ `plan1.md`, `migración importante.md`

## Estados del plan

| Estado | Qué significa |
|--------|----------------|
| **Borrador** | Recién creado, puede tener preguntas abiertas |
| **Listo** | Revisado y aprobado, preguntas abiertas resueltas, listo para ejecutar |
| **Implementado** | Ejecutado completo con notas de cierre |
| **Archivado** | Plan que se abandonó o se reemplazó por otro |

## Relación con el resto del ecosistema

| Herramienta | Para qué sirve | Cuándo usar planes vs esto |
|-------------|----------------|----------------------------|
| **Este playbooks/** | Patrón repetible destilado | Si ya existe playbook → ejecutar, no hacer plan |
| **TodoWrite** | Tareas de la sesión actual | Bugs, fixes chicos, tareas cortas |
| **Taskmaster MCP** | Dividir feature grande | Alternativa/complemento a planes para tareas muy técnicas |
| **memory/ESTADO_ACTUAL** | Snapshot del día | Qué está en curso hoy |
| **wiki/sintesis/** | Historial de sesiones | Después de implementar, archivar retro acá si aporta conocimiento |
| **planes/ (esto)** | Planificación formal archivada | Features grandes + decisiones arquitectónicas |

## Histórico

Los planes "Implementados" y "Archivados" se mantienen acá indefinidamente para consulta futura. No borrarlos — son el registro de decisiones del ecosistema.

Si querés mover un plan muy viejo: `mv planes/YYYY-* 99_ARCHIVO/planes/` (mantener fuera del working set pero no perderlo).
