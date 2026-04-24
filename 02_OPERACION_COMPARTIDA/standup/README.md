# Daily Standup — Sistema de tareas pendientes y urgencias

> Sistema que escala cuando tengas 20+ proyectos simultáneos. Consolida todo lo que quedó abierto en UN solo lugar (`backlog.md`), con snapshots diarios en `daily/YYYY-MM-DD.md`.

## Filosofía

**Problema que resuelve**: hoy las tareas pendientes viven en 4 lugares distintos (`memory/ESTADO_ACTUAL.md`, `ai.context.json`, `memory/debug-log.md`, TodoWrite de sesión). Con pocos clientes la cabeza humana alcanza. Con 20+ proyectos, perdés cosas, no priorizás bien, nada tiene urgencia explícita.

**Solución**: una sola fuente de verdad para TODOs abiertos + un ritual de cierre diario + priorización automática.

## Estructura

```
standup/
├── README.md                    ← este archivo
├── backlog.md                   ← FUENTE ÚNICA de TODOs abiertos (se actualiza diario)
├── daily/
│   ├── 2026-04-24.md            ← snapshot cierre del día
│   ├── 2026-04-25.md
│   └── ...
└── .ultimo-cierre.json          ← marker automático para detectar días sin cerrar
```

## Los 3 comandos

### `/cierre` — Al final del día

1. Escaneo todos los silos (ESTADO_ACTUAL, debug-log, planes en borrador, commits recientes, TodoWrite activo)
2. Genero `daily/YYYY-MM-DD.md` con:
   - Lo que se cerró hoy (✅)
   - Lo que quedó pendiente (🟡)
   - Lo que se descubrió nuevo (💡)
   - Blockers detectados (🚫)
3. Actualizo `backlog.md` con el estado global
4. Te muestro **top 3 urgencias** para mañana
5. Actualizo `.ultimo-cierre.json`

### `/apertura` — Al arrancar el día

1. Leo `backlog.md` + el último `daily/`
2. Detecto días no cerrados (gap desde `.ultimo-cierre.json`)
3. Te reporto:
   - **🔴 Crítico** (pérdida de datos, cliente LIVE caído)
   - **🟠 Alto** (deadline <48h, cliente pago esperando)
   - **🟡 Medio** (features, migraciones programadas)
   - **🟢 Bajo** (refactor, cleanup, ideas futuras)
4. Propongo qué atacar primero con justificación

### `/urgencias` — En cualquier momento

Como `/apertura` pero solo la parte de urgencias. Útil si me preguntás a las 3pm "qué es lo más importante que debería hacer ahora".

## Hook automático SessionStart

Al abrir una sesión nueva de Claude Code, un hook silencioso:
1. Lee `.ultimo-cierre.json`
2. Si el último cierre fue hace +12h → inyecta mensaje en mi contexto tipo *"tenés backlog pendiente, corré `/apertura` para ver urgencias"*
3. Si fue <12h (mismo día) → no molesta

No ejecuto `/apertura` automático para no abrumarte — solo te recuerdo que existe si hace rato que no cerrás.

## Criterios de priorización (automáticos)

| Señal detectada | Urgencia asignada |
|-----------------|---------------------|
| Cliente productivo LIVE reportado roto (Maicol, Lau) | 🔴 Crítico |
| Pérdida/corrupción de datos posible | 🔴 Crítico |
| Deadline explícito en ≤48h | 🟠 Alto |
| Cliente pago esperando respuesta >24h | 🟠 Alto |
| Plan en estado "Listo" sin ejecutar | 🟠 Alto |
| Migración programada con fecha | 🟡 Medio (sube a 🟠 si fecha <7 días) |
| Cliente nuevo en onboarding | 🟡 Medio |
| Bug documentado en debug-log sin fix | 🟡 Medio |
| Plan en estado "Borrador" | 🟢 Bajo |
| Refactor, cleanup, tech debt | 🟢 Bajo |
| Idea futura, research | 🟢 Bajo |

## Relación con `/crear-plan`

Un plan en estado "Borrador" o "Listo" aparece **automáticamente** en el backlog. Cuando hago `/cierre`, escaneo `02_OPERACION_COMPARTIDA/planes/` y sumo los que no están "Implementado".

Flujo típico:
1. Lunes: `/crear-plan onboarding María` → queda en Borrador
2. Martes: `/cierre` lo detecta, lo pone en backlog como 🟡 Medio
3. Si pasa una semana sin ejecutarlo: sube a 🟠 Alto (stale)
4. Cuando hago `/implementar` y cierra → desaparece del backlog

## Formato del backlog.md

```markdown
# Backlog consolidado

**Última actualización**: YYYY-MM-DD HH:MM
**Total items abiertos**: N

## 🔴 Críticos (N)
- [ ] <descripción> | origen: <archivo> | detectado: <fecha>

## 🟠 Altos (N)
- [ ] <descripción> | origen: <archivo> | detectado: <fecha>

## 🟡 Medios (N)

## 🟢 Bajos (N)

---

## Por proyecto

### Arnaldo (N items)
...

### Robert (N items)
...

### Mica (N items)
...
```

## Formato del daily/YYYY-MM-DD.md

```markdown
# Cierre del día — YYYY-MM-DD

**Duración sesiones**: <tiempo estimado> | **Agencias tocadas**: <lista>

## ✅ Completado hoy
- <tarea cerrada 1>
- <tarea cerrada 2>

## 🟡 Quedó pendiente
- <tarea abierta 1> — status: <en qué quedó>
- <tarea abierta 2>

## 💡 Descubierto nuevo
- <patrón, gotcha, decisión>

## 🚫 Blockers
- <bloqueo 1> — bloquea: <qué>

## 🏆 Top 3 para mañana

1. **<tarea más urgente>** — razón: <por qué>
2. **<segunda prioridad>**
3. **<tercera>**
```

## Reglas irrompibles

1. **El backlog.md es la ÚNICA fuente de verdad**. Si una tarea pendiente no está ahí, no existe.
2. **No duplicar con memory/ESTADO_ACTUAL.md**. El standup lo reemplaza gradualmente — ESTADO_ACTUAL queda para contexto efímero del día, el backlog para TODOs abiertos multi-día.
3. **Los daily/ se mantienen indefinidamente**. Son el registro histórico de qué hiciste cada día.
4. **Cada item del backlog DEBE tener origen rastreable** (archivo o comando que lo generó).
5. **No crear tareas imaginarias**. Solo capturar lo que ya existe en los silos (ESTADO_ACTUAL, debug-log, planes, commits, handoffs).
