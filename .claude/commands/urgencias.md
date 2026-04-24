---
description: Versión compacta de /apertura — solo reporta las urgencias 🔴 Críticos y 🟠 Altos del backlog, con la recomendación de qué atacar primero. Úsalo cuando querés un resumen rápido sin todo el contexto de la apertura.
---

# Urgencias

Reporte compacto: solo lo urgente, sin ceremonia.

---

## Proceso

### Fase 1 — Leer

1. `02_OPERACION_COMPARTIDA/standup/backlog.md`
2. `02_OPERACION_COMPARTIDA/standup/.ultimo-cierre.json` (solo para saber si está fresco)

### Fase 2 — Filtrar

Solo items con urgencia 🔴 Crítico o 🟠 Alto. Ignorar 🟡 y 🟢.

**Re-priorización dinámica** (igual que `/apertura`):
- Items 🟠 con >7 días sin mover → promover a 🔴
- Items con deadline en <48h → asegurar que estén en 🟠 como mínimo

### Fase 3 — Reportar

Formato ultra compacto:

```
## 🔥 Urgencias ahora

<Si hay 0 críticos y 0 altos>:
🟢 Nada urgente. Aprovechá para tareas 🟡 Medias del backlog o trabajo de fondo.

<Si hay items>:

### 🔴 Críticos (N)
1. **<tarea>** → <proyecto> — <razón en 1 línea>

### 🟠 Altos (N)
1. **<tarea>** → <proyecto> — <razón en 1 línea>
2. ...

---

### 🎯 Siguiente paso recomendado

**<Tarea que resolvería primero>** porque <justificación breve>.
Próxima acción concreta: <qué hacer>.

<Si backlog desactualizado>:
⚠️ Último cierre fue hace <X horas/días>. El backlog puede estar desactualizado.
```

---

## Reglas

1. **Corto y al grano**. Máximo 1 línea de razón por item.
2. **No incluir 🟡 Medios ni 🟢 Bajos** — eso es lo que diferencia `/urgencias` de `/apertura`.
3. **Si backlog vacío o desactualizado**, decirlo explícitamente, no inventar.
4. **Una sola recomendación final** — no lista de 5 cosas. El usuario quiere saber QUÉ HACER AHORA.
