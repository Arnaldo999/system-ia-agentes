# Regla Operativa — Continuidad entre Sesiones

## Al CERRAR una sesión

1. Si hubo cambios reales → hacer commit cuando corresponda
2. Actualizar `memory/ESTADO_ACTUAL.md` si el cambio afecta al ecosistema
3. Actualizar `02_OPERACION_COMPARTIDA/handoff/ULTIMA_SESION.md` **siempre**
4. Si el cambio afecta un proyecto concreto → actualizar `01_PROYECTOS/<PROYECTO>/docs/ESTADO_ACTUAL.md`
5. Si afecta producción → dejarlo explícito en "Riesgos / advertencias" y "No tocar sin validar"

## Al ABRIR una nueva sesión

1. Leer `ai.context.json`
2. Leer `memory/ESTADO_ACTUAL.md`
3. Leer `02_OPERACION_COMPARTIDA/handoff/ULTIMA_SESION.md`
4. Si aplica → leer `01_PROYECTOS/<PROYECTO>/docs/ESTADO_ACTUAL.md`

No leer documentación larga salvo que haga falta para ejecutar la tarea.
