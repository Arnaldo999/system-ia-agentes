---
description: Cierre de día — escanea todos los silos (ESTADO_ACTUAL, debug-log, planes en borrador, commits, handoffs), genera daily/YYYY-MM-DD.md con lo que quedó, actualiza backlog.md global, y reporta top 3 urgencias para mañana. Ejecutar al terminar el día de trabajo.
---

# Cierre del día

Consolidá todo lo que quedó pendiente del día en el sistema de standup, actualizá el backlog global, y reportá al usuario las urgencias para el próximo día.

## Sin argumento

Si el usuario pasó un argumento como `$ARGUMENTS`, usarlo como "nota del día" (ej: "día de onboarding Maicol social"). Si no, ignorarlo.

---

## Proceso — 5 fases

### Fase 1 — Escaneo de silos

Leer en paralelo (usar tool calls en el mismo mensaje):

1. `memory/ESTADO_ACTUAL.md` → estado operativo en curso
2. `memory/debug-log.md` → bugs a medias (buscar los de los últimos 7 días)
3. `ai.context.json` → agente activo + handoffs
4. `02_OPERACION_COMPARTIDA/planes/` → planes en Borrador/Listo (no Implementado)
5. `02_OPERACION_COMPARTIDA/handoff/*.md` → briefs activos
6. `02_OPERACION_COMPARTIDA/standup/backlog.md` → estado actual del backlog (si existe)
7. `git log --since="yesterday" --oneline` → commits del día para contexto de qué se trabajó
8. `git status -s` → cambios sin commitear (señal de trabajo a medias)

### Fase 2 — Clasificación de items

Para cada ítem detectado, asignar:

**Urgencia** (según tabla en `standup/README.md`):
- 🔴 Crítico — cliente LIVE roto, pérdida de datos, producción caída
- 🟠 Alto — deadline <48h, cliente pago esperando, plan "Listo" sin ejecutar
- 🟡 Medio — feature cliente nuevo, migración programada, bug documentado
- 🟢 Bajo — refactor, cleanup, idea futura

**Proyecto**: arnaldo | robert | mica | global/compartido

**Origen**: archivo o comando donde se detectó (trazabilidad)

**Detectado**: fecha ISO de cuando apareció por primera vez (si ya estaba en backlog, mantener fecha original)

### Fase 3 — Generar daily/YYYY-MM-DD.md

Crear archivo `02_OPERACION_COMPARTIDA/standup/daily/YYYY-MM-DD.md` con formato:

```markdown
# Cierre del día — YYYY-MM-DD

**Agencias tocadas**: <lista detectada de commits/archivos modificados>
**Sesiones Claude**: <si se puede detectar, cantidad aproximada>
**Nota del día** (si $ARGUMENTS): <la nota>

---

## ✅ Completado hoy

Items que se cerraron/resolvieron en este día:

- <tarea 1>
- <tarea 2>

_Fuente: commits del día + items que estaban en backlog y ya no aparecen_

---

## 🟡 Quedó pendiente

Items que están abiertos al cierre del día:

- <tarea 1> | urgencia: 🟠 Alto | origen: <archivo> | status: <en qué punto quedó>
- <tarea 2> | urgencia: 🟡 Medio | origen: ... | status: ...

---

## 💡 Descubierto nuevo

Patrones, gotchas, decisiones nuevas que emergieron hoy:

- <descubrimiento 1>
- <descubrimiento 2>

_Propuesta de dónde archivar cada uno:_
- `<descubrimiento>` → `wiki/playbooks/X` o `wiki/conceptos/Y` o `memory/debug-log.md`

---

## 🚫 Blockers

Cosas que bloquean otras tareas:

- <blocker 1> — bloquea: <qué tareas>

---

## 🏆 Top 3 urgencias para mañana

Ordenadas por criticidad + deadline:

1. **<tarea urgente 1>**
   - Urgencia: 🔴 / 🟠 / 🟡
   - Razón: <por qué es top>
   - Próximo paso: <acción concreta>

2. **<tarea urgente 2>**
   - ...

3. **<tarea urgente 3>**
   - ...

---

## Contexto que debo retomar mañana

Si abrís sesión mañana sin leer esto, ¿qué es crítico saber?

- <contexto 1>
- <contexto 2>
```

### Fase 4 — Actualizar backlog.md global

Leer `02_OPERACION_COMPARTIDA/standup/backlog.md` actual y reescribirlo consolidando:

1. Items **resueltos hoy** → borrarlos del backlog
2. Items **nuevos detectados** → agregarlos en la sección de urgencia correcta
3. Items **existentes** cuya urgencia cambió → moverlos (ej: migración que subió de 🟡 a 🟠 por acercarse deadline)
4. Actualizar header con fecha/hora + total

Formato del backlog (mantener el que define `standup/README.md`).

**Secciones a generar**:
- 4 secciones por urgencia (🔴 🟠 🟡 🟢)
- 4 secciones por proyecto (Arnaldo / Robert / Mica / Global)

Cada item con formato:
```
- [ ] <descripción corta> | origen: `<archivo>` | detectado: YYYY-MM-DD
```

### Fase 4.5 — Notificar Telegram SI hay críticos o altos ≥3

Si el backlog final tiene:
- **1+ items 🔴 Críticos**, O
- **3+ items 🟠 Altos**

Entonces disparar notificación Telegram con resumen. Usar helper:

```bash
"/home/arna/PROYECTOS SYSTEM IA/SYSTEM_IA_MISSION_CONTROL/02_OPERACION_COMPARTIDA/scripts/notify_telegram.sh" \
  "📋 Cierre YYYY-MM-DD" \
  "Backlog al cierre: N críticos 🔴 + N altos 🟠.

Top urgencias mañana:
1. <tarea 1>
2. <tarea 2>
3. <tarea 3>

Ver detalle: 02_OPERACION_COMPARTIDA/standup/daily/YYYY-MM-DD.md"
```

Si el script falla (código != 0), NO bloquear el cierre — solo mencionarlo al usuario en el reporte final. El cierre es más importante que el aviso Telegram.

Si no hay críticos ni ≥3 altos → **NO enviar Telegram**. Evitar ruido. El usuario lo verá en la apertura de mañana si necesita.

### Fase 5 — Actualizar `.ultimo-cierre.json` + reportar al usuario

1. Escribir en `02_OPERACION_COMPARTIDA/standup/.ultimo-cierre.json`:
   ```json
   {
     "ultimo_cierre": "YYYY-MM-DDTHH:MM:SS-03:00",
     "total_items_backlog": N,
     "criticos": N,
     "altos": N,
     "dia_archivado": "daily/YYYY-MM-DD.md"
   }
   ```

2. **Reportar al usuario** en formato breve:

```
## Cierre del día YYYY-MM-DD listo ✅

### Resumen
- ✅ Completado: N items
- 🟡 Quedó pendiente: N items
- 💡 Descubrimientos: N
- 🚫 Blockers: N

### Top 3 urgencias mañana
1. **<tarea>** — <razón>
2. **<tarea>** — <razón>
3. **<tarea>** — <razón>

### Archivos generados
- `02_OPERACION_COMPARTIDA/standup/daily/YYYY-MM-DD.md` (nuevo)
- `02_OPERACION_COMPARTIDA/standup/backlog.md` (actualizado — N items totales)
- `02_OPERACION_COMPARTIDA/standup/.ultimo-cierre.json` (actualizado)

### Descubrimientos a propagar (opcional)
<si hay descubrimientos que deberían ir a playbook/wiki/memory, listarlos>
¿Querés que los archive ahora o mañana?
```

---

## Reglas irrompibles

1. **NO inventar tareas que no existen en los silos**. Solo capturar lo que ya está documentado en algún lado.
2. **NO duplicar info con memory/ESTADO_ACTUAL.md**. El backlog es el "qué queda por hacer"; ESTADO_ACTUAL es "qué está en curso ahora". Complementarios, no solapados.
3. **Respetar aislamiento de agencias** al clasificar por proyecto (ver CLAUDE.md REGLA #0).
4. **Los daily/ son inmutables** — nunca editar un daily de días pasados. Si hay que corregir algo, se corrige en el backlog o se escribe en el daily actual.
5. **El backlog se reescribe completo cada cierre** (no append). Es un snapshot del estado actual.

---

## Cuándo NO ejecutar cierre

- Si ya corriste `/cierre` hoy mismo (`.ultimo-cierre.json` tiene timestamp de hace <6h) → pregunta al usuario si quiere re-ejecutar
- Si no hay nada que cerrar (cero cambios, cero items) → reportar "día tranquilo, sin movimientos" y no generar daily/ vacío

---

## Notas

- Este comando es idempotente dentro del mismo día — correrlo 2 veces sobreescribe el daily del día.
- Si el usuario quiere cerrar con una nota específica, la pasa como argumento: `/cierre "día intenso de onboarding Maicol, quedó IG pendiente link cliente"`.
- Los dailies se mantienen para siempre. En un año vas a tener 365 archivos — es el registro histórico más valioso del ecosistema.
