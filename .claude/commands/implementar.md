---
description: Ejecuta un plan creado con /crear-plan. Lee el plan completo, ejecuta cada paso en orden, valida, y marca el plan como "Implementado" con notas de desviaciones.
---

# Implementar

Ejecutá un plan de implementación creado por `/crear-plan`. Leé el plan entero, ejecutá cada paso en orden, validá el trabajo y actualizá el estado del plan al terminar.

## Argumento

$ARGUMENTS — ruta al archivo del plan, ej: `02_OPERACION_COMPARTIDA/planes/2026-04-24-onboarding-cliente-maria.md`

---

## Proceso — 4 fases

### Fase 1 — Entender el plan

1. **Leer el archivo completo** (no hojearlo) — cada sección importa
2. **Verificar prerequisitos**:
   - ¿Hay preguntas abiertas marcadas con `[ ]` en la sección "Preguntas abiertas"? → si sí, PARAR y preguntarle al usuario antes de continuar
   - ¿Hay decisiones bloqueadas por input externo? → PARAR
3. **Verificar que el plan está listo**:
   - Estado debe ser "Borrador" o "Listo"
   - Si dice "Implementado" ya se ejecutó antes → preguntar al usuario si quiere re-ejecutar o si se olvidó actualizar
4. **Identificar el proyecto** según frontmatter del plan:
   - Si dice `Proyecto: arnaldo` → invocar consideraciones de stack Arnaldo
   - Si `robert` → consideraciones Lovbot
   - Si `mica` → System IA
   - Si `compartido` → múltiples proyectos
   - Si `global` → infraestructura Mission Control
5. **Leer playbook relacionado** (si el plan lo referencia) antes de ejecutar

---

### Fase 2 — Ejecutar paso a paso

1. **Seguir "Tareas paso a paso" en orden exacto**
   - Completar un paso antes de pasar al siguiente
   - Si un paso crea un archivo: escribirlo completo, NO en borrador
   - Si un paso modifica un archivo: leerlo primero, aplicar cambios con precisión
2. **Para cada paso**:
   - Leer archivos afectados
   - Aplicar cambios especificados
   - Correr la validación del paso (si está definida)
   - Reportar al usuario qué se hizo antes de pasar al siguiente (1 frase)
3. **Respetar reglas del ecosistema** (nunca romper estas, aunque el plan diga algo distinto):
   - **Silos**: info en UN solo silo, no duplicar entre auto-memory / wiki / memory / código
   - **Aislamiento agencias**: NO mezclar stacks (ej: no meter Airtable en código Robert)
   - **Demo primero**: cambios en `workers/clientes/*` o `demo-crm-mvp.html` SIEMPRE vía demo
   - **Playbooks vigentes**: si el paso contradice un playbook, PARAR y avisar
4. **Cuando aparezca un problema**:
   - Si el paso no puede ejecutarse como está escrito y la intención es clara → adaptar y documentar
   - Si no está claro cómo seguir → PREGUNTAR al usuario, no adivinar
   - Si descubrís algo que cambia las decisiones del plan → PARAR, avisar al usuario, no seguir ciegamente

---

### Fase 3 — Validar

1. **Correr "Lista de validación" del plan**:
   - Tildar cada ítem verificado
   - Marcar los que fallan con descripción del fallo
2. **Verificar "Criterios de éxito"**:
   - Confirmar cada criterio
   - Notar brechas
3. **Chequeos de consistencia del ecosistema**:
   - ¿CLAUDE.md necesita actualización por nueva estructura?
   - ¿`PROYECTO ARNALDO OBSIDIAN/index.md` necesita nuevas entradas (entidad, concepto, síntesis)?
   - ¿`memory/ESTADO_ACTUAL.md` refleja el cambio?
   - ¿Hay playbook que se deba actualizar con descubrimientos nuevos?
   - ¿Hay skill/hook afectado?

Si algo falla: reportarlo con detalle, sugerir fix, preguntar al usuario cómo seguir.

---

### Fase 4 — Cerrar el plan

1. **Actualizar el archivo del plan**:
   - Cambiar `**Estado**: Borrador` → `**Estado**: Implementado`
   - Completar la sección "Notas de implementación" con:
     - `**Implementado**: YYYY-MM-DD`
     - **Resumen**: qué se hizo (bullets)
     - **Desviaciones**: cambios respecto al plan original (o "Ninguna")
     - **Problemas encontrados**: bugs durante implementación + cómo se resolvieron
     - **Descubrimientos nuevos**: cosas que aprendimos que deben ir a:
       - Playbook (si es un patrón nuevo)
       - Wiki concepto (si es conocimiento estructural)
       - Auto-memory (si es preferencia del usuario)
       - `memory/debug-log.md` (si es un bug nuevo)
2. **Propagar descubrimientos** (si los hay):
   - Ofrecer al usuario actualizar el playbook / wiki / memory correspondiente
   - NO duplicar — decidir qué silo corresponde antes de escribir
3. **Actualizar memory operativo**:
   - Si el plan completó algo productivo → actualizar `memory/ESTADO_ACTUAL.md`
   - Si quedaron TODOs post-plan → apuntarlos explícitamente

---

## Estándares de calidad

- **Exhaustividad**: cada paso del plan se ejecuta, nada se saltea sin justificación documentada
- **Precisión**: los cambios coinciden con lo que especifica el plan
- **Completitud**: archivos escritos enteros, no en borrador
- **Trazabilidad**: desviaciones del plan quedan documentadas
- **No romper reglas del ecosistema**: aislamiento agencias + silos + demo primero + playbooks

---

## Formato de reporte final

Al terminar, reportar al usuario:

```
## Implementación completa

### Resumen
- <qué se hizo, bullet 1>
- <qué se hizo, bullet 2>

### Archivos modificados
**Creados**:
- `ruta/nuevo-archivo`

**Modificados**:
- `ruta/archivo-modificado`

**Eliminados**:
- (ninguno)

### Infraestructura externa tocada
- <BD: CREATE DATABASE maria_crm>
- <Coolify: env vars agregadas>
- <Airtable: nueva tabla Contratos>

### Validación
- [x] <verificación 1 pasa>
- [x] <verificación 2 pasa>
- [ ] <verificación 3 falla — descripción>

### Desviaciones del plan
<Ninguna, o listado>

### Descubrimientos propagados
- Playbook actualizado: <path>
- Wiki concepto nuevo: <path>
- Debug-log entry: <path>
- (o "Ninguno")

### Estado del plan
Actualizado `02_OPERACION_COMPARTIDA/planes/YYYY-MM-DD-{slug}.md` → Implementado

### Próximos pasos (si aplican)
- <follow-up pendiente>
```

---

## Cuándo NO ejecutar un plan

**PARAR y avisarle al usuario** si:

- El plan está marcado como "Implementado" (preguntar si quiere re-ejecutar)
- Hay preguntas abiertas sin resolver en la sección del plan
- El plan contradice un playbook vigente (puede que el playbook esté más actualizado)
- El plan toca producción (workers clientes, CRM prod) sin pasar por demo
- El plan menciona mezclar stacks entre agencias (señal de error)

En estos casos, pedir confirmación explícita antes de hacer cualquier cosa.

---

## Notas finales

- Implementar un plan bien hecho es un trabajo mecánico — el plan ya pensó por vos
- Si durante la ejecución sentís que "el plan está mal pensado" → PARAR, no improvisar, discutir con el usuario y actualizar el plan antes de seguir
- El plan es un contrato con el futuro: 3 meses después vas a consultar qué se hizo y por qué
