# Protocolo init/ — Apertura de Sesión

Ejecutar al inicio de cada sesión, en este orden:

1. Leer `ai.context.json` — agente activo, proyectos, infraestructura
2. Leer `memory/ESTADO_ACTUAL.md` — estado del ecosistema
3. Leer `02_OPERACION_COMPARTIDA/handoff/ULTIMA_SESION.md` — qué se hizo, qué quedó pendiente
4. Si la tarea involucra un proyecto concreto → leer `01_PROYECTOS/<PROYECTO>/docs/ESTADO_ACTUAL.md`

No leer documentación adicional salvo que la tarea lo requiera.

## Criterio de bloqueo al abrir

Si al leer ULTIMA_SESION hay un riesgo marcado con producción → reportarlo antes de ejecutar cualquier tarea.
