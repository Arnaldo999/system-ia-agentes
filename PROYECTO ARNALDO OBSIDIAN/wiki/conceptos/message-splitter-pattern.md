---
proyecto: compartido
tipo: concepto
created: 2026-04-24
tags: [workers, whatsapp, humanizacion, saludo, gpt-4o-mini, splitter, bant]
---

# Message Splitter — partición del saludo en 2-3 chunks

## Qué es

Módulo compartido `workers/shared/message_splitter.py` que recibe un texto largo generado por el LLM y lo parte en 2-3 mensajes más cortos usando GPT-4o-mini como "editor". Solo se usa en el **primer turno** de la conversación (saludo inicial). El resto de los turnos BANT siguen con 1 solo mensaje consolidado.

## Por qué existe

Cuando el bot genera un saludo largo tipo:

> *"¡Hola! 👋 Bienvenido/a a Lovbot — Demo Inmobiliaria. Somos una desarrolladora inmobiliaria en México con proyectos en Zona Norte · Zona Sur · Zona Centro. Atendemos de lunes a viernes de 9 a 18 hs 🕐 ¿Hablo con Arnaldo, correcto?"*

Enviarlo como 1 solo mensaje gigante se siente robótico. Humanos mandan **partes** separadas por WhatsApp:

> 💬 *"¡Hola! 👋 Bienvenido/a a Lovbot — Demo Inmobiliaria."*
> *(pausa)*
> 💬 *"Somos una desarrolladora inmobiliaria con proyectos en Zona Norte · Zona Sur · Zona Centro. Atendemos de lunes a viernes de 9 a 18 hs 🕐"*
> *(pausa)*
> 💬 *"¿Hablo con Arnaldo, correcto?"*

## API pública

```python
from workers.shared.message_splitter import split_greeting

chunks = split_greeting(
    texto=mensaje_bot,
    max_chunks=3,
    api_key=None,  # opcional — si no viene, resuelve de env vars
)
# chunks: List[str] con 1-3 elementos
```

## Comportamiento

1. **Guard de longitud**: si `len(texto) < 120` → devuelve `[texto]` (1 solo chunk, no llama LLM)
2. **Resolución de API key**: si no se pasa `api_key`, intenta en orden: `OPENAI_API_KEY` → `LOVBOT_OPENAI_API_KEY` → `MICA_OPENAI_API_KEY`
3. **Llamada a GPT-4o-mini** con prompt JSON estricto pidiendo partición limpia
4. **Validaciones**:
   - Chunks no vacíos
   - No exceden `max_chunks`
   - Longitud total >= 70% del original (heurística: no se perdió contenido)
5. **Fallback graceful**: si algo falla → devuelve `[texto]` (1 chunk, comportamiento pre-feature)

## Costo

~$0.0001 por partición (GPT-4o-mini, 1 sola llamada por conversación). Solo se activa en primer turno.

## Cuándo usar (regla irrompible)

### ✅ Usar splitter SOLO en el primer turno (saludo inicial)

Detección de primer turno en el worker:
```python
_hist = HISTORIAL.get(tel_clean, [])
es_primer_turno_bot = not any("Bot:" in h for h in _hist)
```

### ❌ NO usar splitter en turnos BANT posteriores

Los turnos BANT (presupuesto, zona, tipo de propiedad, autoridad, timeline) tienen que ser **1 solo mensaje consolidado** porque:
- Son preguntas puntuales (no necesitan partición)
- Si los partís, el cliente siente que el bot habla entrecortado
- Rompe el ritmo conversacional

## Integración en worker

```python
if mensaje_final:
    _hist = HISTORIAL.get(re.sub(r'\D', '', telefono), [])
    es_primer_turno_bot = not any("Bot:" in h or "(bot)" in h for h in _hist)

    if es_primer_turno_bot:
        chunks = split_greeting(mensaje_final, max_chunks=3)
        for chunk in chunks:
            _enviar_texto(telefono, chunk)  # typing_indicator dentro
    else:
        _enviar_texto(telefono, mensaje_final)
```

Entre chunks no hace falta `sleep()` adicional — el `send_typing()` del siguiente chunk ya bloquea 2s, dando pausa natural.

## Relación con prompt BANT

Para que el splitter funcione bien, el prompt del worker debe **generar un saludo largo** (>120 chars) en primer turno. Si el prompt dice "mensajes cortos" sin excepción, el LLM genera un saludo breve y el splitter devuelve `[texto]` (1 chunk) porque no hay nada que partir.

**Regla derivada** (2026-04-24, lección aprendida): al prompt BANT agregar excepción explícita:
> *"Máximo 3-4 líneas en turnos BANT. EXCEPCIÓN: PRIMER turno DEBE incluir bienvenida + empresa + zonas + horarios + pregunta nombre. No recortar."*

Ver: [[auto-memory/feedback_REGLA_prompt_bant_conflictos]]

## Bugs históricos

### 1. Variable `OPENAI_API_KEY` hardcoded (fixed 2026-04-24)
El módulo original solo leía `OPENAI_API_KEY`. Robert usa `LOVBOT_OPENAI_API_KEY`. El splitter devolvía `[texto]` sin partir por falta de key.

**Fix** (commit `15eeda0`): agregar param `api_key` + fallback a 3 env vars.

### 2. Python 3.11 f-string triple anidado (fixed 2026-04-24)
Al implementar el fix de prompt para forzar saludo largo, introdujimos f-string triple anidado que crashea Python 3.11.

**Fix** (commit `570a473`): usar variable intermedia `regla_1` fuera del f-string padre.

Ver: [[auto-memory/feedback_REGLA_python311_fstring_triples]]

## Workers que lo usan

- `workers/clientes/system_ia/demos/inmobiliaria/worker.py` — Mica demo
- `workers/clientes/lovbot/robert_inmobiliaria/worker.py` — Robert demo

## Origen

- Patrón original: plantilla Nexum Academy (ManyChat + n8n) y curso Kevin Bellier
- Implementado en Python nativo (no ManyChat) — decisión 2026-04-23
- Commits: `6a2617e` (módulo inicial), `15eeda0` (fix api_key), `888a258` (Mica), `5b21e15` (Robert)

## Relacionado

- [[wiki/conceptos/typing-indicator-pattern]] — typing entre cada chunk
- [[wiki/conceptos/message-buffer-debounce]] — el buffer dispara el flush, después recién entra el splitter
- [[auto-memory/feedback_REGLA_prompt_bant_conflictos]] — evitar que reglas de brevedad aborten el saludo largo
