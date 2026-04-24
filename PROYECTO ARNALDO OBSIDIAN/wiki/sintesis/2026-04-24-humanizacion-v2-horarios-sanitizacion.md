---
proyecto: compartido
tipo: sintesis
created: 2026-04-24
tags: [sesion, typing, splitter, horarios, sanitizacion-nombre, humanizacion]
---

# Sesión 2026-04-24 — Humanización v2: typing + splitter + horarios + sanitización

## Contexto

Continuación de la sesión nocturna del 2026-04-23 ([[wiki/sintesis/2026-04-23-humanizacion-workers-redis]]). Ayer quedamos con buffer debounce + image describer listos. Hoy faltaban las features #3 y #4:
- Typing indicator "escribiendo..." en todas las respuestas
- Partición de saludo en 2-3 chunks

Arnaldo empezó preguntando el estado y clarificó la diferencia entre los 2 timers:
- **Buffer debounce 8s** = tiempo desde el último mensaje del cliente (entrada, consolidación)
- **Typing + pausa 2s** = tiempo entre cada chunk del bot (salida, humanización)

Durante la implementación aparecieron 3 bugs nuevos + descubrimos que el ecosistema tiene **múltiples agentes Claude corriendo en paralelo** que a veces hacen fixes compitiendo.

## Decisiones clave

1. **Buffer 8s (sin cambio)** — confirmado, muchos usuarios LATAM escriben lento
2. **Pausa entre chunks 2s** — idéntica al typing indicator, sin sleep extra
3. **Typing SIEMPRE activo** — en todas las respuestas del bot, no solo particiones
4. **Splitter SOLO en primer turno** — BANT posterior mantiene mensaje consolidado
5. **Horarios de atención en el saludo** — "lunes a viernes de 9 a 18 hs" hardcoded (hasta que haya configuración por cliente)
6. **Sanitización de nombre obligatoria en Robert** — replicar patrón Mica (`@rn@ldo → Arnaldo`)

## Trabajo realizado

### Fase 1 — Módulos nuevos en `workers/shared/`

- `typing_indicator.py` — wrapper generico (Meta + Evolution + YCloud fallback)
- `message_splitter.py` — partición de saludos con GPT-4o-mini

Ver: [[wiki/conceptos/typing-indicator-pattern]] y [[wiki/conceptos/message-splitter-pattern]]

### Fase 2 — Integración en workers demo

- **Mica**: `_enviar_texto` wrappeado con `send_typing()` + splitter en primer turno
- **Robert**: idem + guardado de `ultimo_msg_id` entrante para Meta typing visual

### Fase 3 — Fixes derivados

- **Fix Robert**: agregar `_sanitizar_nombre()` (copiada de Mica) — saludaba "Rnldo" por no mapear `@` → `a`
- **Fix ambos workers**: agregar horarios de atención al `ejemplo_saludo`
- **Fix prompt conflicto**: regla de brevedad del BANT anulaba horarios — excepción explícita para primer turno

## Bugs descubiertos y fixeados

### Bug #1 — Python 3.11 f-string triple anidado (commit `5fd48de` → fix `570a473`)

Primera versión del fix del prompt Mica usó:
```python
{f"""1. En este PRIMER turno...""" if condicion else f"""1. SOLO..."""}
```

Python 3.11 no soporta f-strings triples anidados → `SyntaxError: f-string: expecting '}'`. Ambos backends quedaron caídos ~15 min.

Fix: variable intermedia `regla_1` fuera del f-string padre.

Regla durable documentada en [[auto-memory/feedback_REGLA_python311_fstring_triples]]. Ya hubo bug similar con `re.sub(r'\D',...)` dentro de f-string — esta es segunda iteración del mismo patrón.

### Bug #2 — Coolify cache no rebuild (commits `105e113` + `91b9924` no se deployaron automáticamente)

Hice commit de horarios a Robert. Pusheado a master. Auto-deploy ejecutó pero el container corriendo seguía con código viejo. Verificación con terminal Coolify confirmó que el código llegó al container file system pero el runtime usaba imagen cacheada.

Fix: forzar con `force=true` en API o botón "Redeploy" naranja (NO "Restart") en UI.

Regla documentada en [[auto-memory/feedback_REGLA_coolify_cache_force]].

### Bug #3 — Reglas del prompt BANT chocan entre sí (commit `5a99bb1`)

Agregué horarios al `ejemplo_saludo` del worker Robert. Código deployado correctamente. Pero el LLM seguía respondiendo sin horarios.

Causa: línea 1745 del prompt decía *"Mensajes cortos: máximo 3-4 líneas"*. Esa regla compite contra "incluir saludo + empresa + zonas + horarios + pregunta nombre". El LLM elige la restricción y descarta contenido.

Fix: excepción explícita:
> *"máximo 3-4 líneas **en turnos BANT (después del saludo)**. EXCEPCIÓN: PRIMER turno DEBE incluir bienvenida + empresa + zonas + HORARIOS + pregunta. No recortes."*

Regla documentada en [[auto-memory/feedback_REGLA_prompt_bant_conflictos]].

## Fenómeno observado — múltiples agentes Claude paralelos

Durante la sesión detecté varios commits que **NO hice yo** pero aparecieron en master:
- `570a473` — fix Python 3.11 f-string (hecho por otro agente)
- `91b9924` — refactor horarios a variable `HORARIO_ATENCION` (otro agente)
- `b450ac0`, `8be66c7` — fixes al worker social (otro agente)

Arnaldo tiene sesiones Claude paralelas corriendo. No hubo conflictos reales de merge porque los 2 agentes tocaron líneas distintas del mismo archivo (línea 1751 fix Python / línea 1566 horarios). Pero queda claro que hay que ser conservador con cambios grandes y chequear `git log --oneline` antes de pushear.

## Commits de la sesión (en orden cronológico)

1. `6a2617e` — feat(shared): typing_indicator + message_splitter
2. `15eeda0` — fix(message_splitter): accept api_key param + LOVBOT/MICA fallback
3. `888a258` — feat(mica-demo): integrar typing + splitter
4. `5b21e15` — feat(robert-demo): integrar typing + splitter
5. `5fd48de` — fix(mica-demo): saludo completo en primer turno (**rompió Python 3.11**)
6. `570a473` — fix(mica-demo): Python 3.11 compat (**otro agente, recuperó el deploy**)
7. `017badb` — feat(mica-demo): agregar horarios
8. `105e113` — feat(robert-demo): _sanitizar_nombre + horarios
9. `91b9924` — fix(robert-demo): horarios con variable HORARIO_ATENCION (**otro agente**)
10. `5a99bb1` — fix(ambos): regla brevedad no aplica al primer turno

## Validación end-to-end

Ambos bots probados con 3 mensajes fragmentados ("Hola / como / estas"):

### Mica demo ✅
- Msg 1: Bienvenida
- Msg 2: Presentación + zonas San Ignacio/Gdor Roca/Apóstoles + **horarios** + 🕐
- Msg 3: *"¿Hablo con Arnaldo?"* (nombre sanitizado)
- Typing "escribiendo..." visible entre cada mensaje ✅

### Robert demo ✅
- Msg 1: Bienvenida "Hola, Arnaldo"
- Msg 2: Presentación + zonas Norte/Sur/Centro + **"Atendemos de lunes a viernes de 9 a 18 hs 🕐"** ✅
- Msg 3: Pregunta BANT siguiente
- Typing visible ✅
- Nombre limpio (antes aparecía "Rnldo") ✅

## Pendientes para próxima sesión

1. **Deuda técnica `waba_clients`** (viene de ayer) — incluir schema en seed SQL de `lovbot_crm_modelo` para auto-clone a clientes nuevos
2. **Rotación de secrets expuestos en sesión de ayer** (no urgente):
   - `LOVBOT_OPENAI_API_KEY`
   - `OPENAI_API_KEY` compartida
   - Password Redis Hetzner
3. **Configuración de horarios por cliente** — hoy hardcoded `"lunes a viernes de 9 a 18 hs"`. A futuro leer de `INMO_DEMO_HORARIO` env var o campo Airtable/Postgres por tenant
4. **Replicar humanización (buffer + describer + typing + splitter) a workers reales de clientes** — hoy solo en demos. Cuando haya cliente real LIVE de Mica o Robert, copiar los 4 patrones

## Relacionado

- [[wiki/conceptos/message-buffer-debounce]]
- [[wiki/conceptos/image-describer]]
- [[wiki/conceptos/typing-indicator-pattern]]
- [[wiki/conceptos/message-splitter-pattern]]
- [[wiki/sintesis/2026-04-23-humanizacion-workers-redis]]
