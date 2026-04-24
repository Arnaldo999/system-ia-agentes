---
description: Apertura del día — leé el backlog + último daily + detectá gaps de cierre, y reportá al usuario qué hay pendiente ordenado por urgencia (🔴 🟠 🟡 🟢). Propone qué atacar primero con justificación.
---

# Apertura del día

Resumí el estado operativo del ecosistema al usuario para que sepa qué pendiente tiene + qué es lo más urgente hoy.

---

## Proceso — 4 fases

### Fase 1 — Leer contexto

Leer en paralelo:

1. `02_OPERACION_COMPARTIDA/standup/backlog.md` → lista viva de TODOs
2. `02_OPERACION_COMPARTIDA/standup/.ultimo-cierre.json` → cuándo fue el último cierre
3. Último archivo de `02_OPERACION_COMPARTIDA/standup/daily/` (ordenar por fecha DESC, primero) → qué pasó el último día
4. `memory/ESTADO_ACTUAL.md` → contexto efímero del día actual
5. `ai.context.json` → agente activo

### Fase 2 — Detectar gaps y calidad del backlog

**Señales de alarma a reportar**:

- **Nunca se cerró** → `.ultimo-cierre.json.ultimo_cierre == null`: recomendar ejecutar `/cierre` al final del día de hoy para inicializar.
- **Última cierre hace >48h** → backlog puede estar desactualizado. Recomendar `/cierre` pronto.
- **Backlog vacío pero hay cambios recientes sin commit** (`git status -s`) → hay trabajo a medias sin capturar.
- **Item en backlog >30 días sin progreso** → posible tarea muerta, proponer archivar.
- **Items críticos 🔴 abiertos** → reportar SIEMPRE al principio, aunque el usuario no pregunte.

### Fase 3 — Re-priorizar dinámicamente

El backlog tiene urgencias estáticas (del último cierre). Ajustar dinámicamente:

- Migraciones/deadlines con fecha explícita (ej: *"migrar Maicol System User 2026-04-30"*) → sumar urgencia si la fecha está <7 días
- Items "Alto" que ya tienen >7 días en backlog sin moverse → **promover a "Crítico"** (están atorados)
- Items "Medio" con >14 días sin moverse → considerar 🟠 Alto

### Fase 4 — Reportar al usuario

Formato compacto pero informativo:

```
## Apertura del día — <día_semana> YYYY-MM-DD

### Estado del backlog

<Si nunca se cerró>:
⚠️ **Nunca ejecutaste `/cierre`.** El backlog está vacío. Te recomiendo correr `/cierre` al final del próximo día de trabajo para inicializarlo.

<Si último cierre >48h>:
⚠️ **Último cierre fue <hace cuánto>.** El backlog puede estar desactualizado — considerá correr `/cierre` pronto.

<Si todo OK>:
📊 Último cierre: <fecha>. Total items abiertos: N (<desglose: 🔴 X, 🟠 X, 🟡 X, 🟢 X>).

---

### 🔴 Críticos (N)

<Si hay críticos, listar TODOS con justificación — nunca ocultar>

1. **<tarea>**
   - Proyecto: arnaldo | robert | mica | global
   - Origen: <archivo donde se detectó>
   - Detectado: hace X días
   - Por qué es crítico: <razón>

<Si no hay críticos>:
_(Ninguno — buen estado)_

---

### 🟠 Altos (N)

<Listar los primeros 5 con mismo formato. Si hay más de 5: "+N más, ver backlog.md">

---

### 🎯 Mi recomendación para hoy

Dado el estado del backlog, deberías arrancar por:

1. **<tarea #1>** — razón: <por qué esta primero>
   - Próximo paso concreto: <acción>
   - Tiempo estimado: <corto / medio / largo>

2. **<tarea #2>** — razón: ...

<Si hay contexto del último daily relevante>:
### Retomá desde acá
Ayer <resumen breve del último daily>. Quedó pendiente: <lo más importante>.

---

### Atajos útiles

- `/urgencias` — solo las urgencias (versión compacta de esto)
- `/cierre` — cerrar día actual
- Ver backlog completo: `02_OPERACION_COMPARTIDA/standup/backlog.md`
- Ver daily anterior: `02_OPERACION_COMPARTIDA/standup/daily/<última_fecha>.md`
```

---

## Reglas

1. **Siempre reportar 🔴 Críticos**, aunque el usuario no pregunte. Son emergencias.
2. **Máximo 5 items por sección** en el reporte. Si hay más, decirlo pero no spamear.
3. **Proponer acción concreta**, no solo listar. "Hacer X" mejor que "revisar X".
4. **Honestidad con el estado**: si el backlog está vacío/desactualizado, decirlo. No inventar urgencias.
5. **No modificar archivos** — apertura es solo lectura + reporte.

---

## Cuándo NO ejecutar apertura

- Si el backlog no existe → decirle al usuario que inicialice con `/cierre` primero.
- Si ya corriste apertura hace <2h → preguntar si quiere refresh o solo ver el último reporte.
