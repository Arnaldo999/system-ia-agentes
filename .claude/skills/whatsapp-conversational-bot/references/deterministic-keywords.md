# Deterministic Keywords — Detección antes del LLM

Patrón crítico: cuando el LLM ignora reglas del prompt, hacer detección determinista en Python **antes** de llamar al LLM. Más confiable y barato.

## Por qué NO confiar solo en el LLM

El LLM de un prompt largo (>2000 tokens) empieza a ignorar reglas específicas. Casos vistos en producción:

| Regla del prompt | Lo que hacía el LLM |
|---|---|
| "Si el cliente pide opciones, muéstralas" | Seguía preguntando presupuesto |
| "NUNCA ofrezcas alquiler para lotes" | Ofrecía vivir/invertir/alquilar |
| "Si preguntan precio específico, escalá a asesor" | Daba precio estimado propio |
| "Un mensaje corto, máximo 2-3 oraciones" | Mandaba párrafos de 5 líneas |
| "No listes opciones numeradas" | Listaba "1. 2. 3." |

**Lección**: para reglas críticas, no confiar en el LLM. Detectar con keywords en Python.

## Orden correcto en `_procesar()`

```python
def _procesar(telefono: str, texto: str, referral: dict = None):
    # 1) Preparación (idempotente)
    texto_lower = texto.lower().strip()
    sesion = SESIONES.get(telefono, {})
    step = sesion.get("step", "inicio")

    # 2) Bot pausado (asesor humano activo)
    if bot_pausado(telefono):
        return

    # 3) Comandos especiales directos
    if texto_lower == "#":
        _ir_asesor(telefono, sesion)
        return

    # 4) Step handlers deterministas (SIN LLM)
    if step == "agendar_slots":
        _handle_agendar_slots(telefono, texto, sesion)
        return

    if step == "confirmar_cita":
        _handle_confirmar_cita(telefono, texto, sesion)
        return

    if step in ("explorando", "lista"):
        if _handle_explorando(telefono, texto, texto_lower, sesion):
            return  # Si se manejó por keywords, return

    # 5) Anti-friction: pedido explícito de opciones
    if _pide_opciones_directo(texto_lower) and step not in ("explorando", "lista", "ficha"):
        _mostrar_props_inmediato(telefono, sesion)
        return

    # 6) NÚCLEO LLM (ya pasaron todas las reglas deterministas)
    system_prompt = _build_system_prompt(sesion, referral, telefono)
    respuesta = _llm(texto, system=system_prompt)

    if not respuesta:
        _enviar_texto(telefono, "Disculpá, tuve un problema técnico.")
        return

    # 7) Parser tolerante
    mensaje, acciones = _parse_llm_response(respuesta)
    _enviar_texto(telefono, mensaje)

    # 8) Ejecutar ACCION del LLM
    accion = acciones.get("accion", "")
    if accion == "mostrar_props":
        _mostrar_props_inmediato(telefono, sesion, mensaje_ya_enviado=True)
        return

    if accion == "ir_asesor":
        _ir_asesor(telefono, sesion_nueva)
        return

    # ... etc
```

**Clave**: cada step handler determinista va ANTES del LLM y retorna si logró manejar el mensaje. El LLM solo se llama si ningún handler determinista pudo decidir.

## Catálogo de keywords que vale la pena detectar

### 🟢 Pedido explícito de opciones (anti-friction)

```python
_KEYWORDS_PEDIR_OPCIONES = [
    "que opciones", "qué opciones", "que tienen", "qué tienen",
    "mostrame", "muéstrame", "muestrame",
    "quiero ver", "quisiera ver", "mandame", "mandame opciones",
    "que hay disponible", "qué hay disponible", "que propiedades",
    "qué propiedades", "opciones para", "ver opciones", "ver propiedades",
    "quiero opciones", "tenés opciones", "tienen opciones",
    "algo disponible", "algo para mostrar", "mostrame lo que tienen",
]
```

### 🟢 Navegación "siguiente / no me interesa / otra"

```python
_KEYWORDS_SIGUIENTE = [
    "otra", "siguiente", "mas", "más", "no me interesa", "no es",
    "no se adapta", "no me adapta", "otra opción", "otra opcion",
    "ver otra", "siguiente opción", "siguiente opcion", "diferente",
    "no gracias", "no me convence", "que mas", "qué más",
    "que más tenes", "hay mas", "hay más", "algo mas", "algo más",
]
```

### 🟢 Pedido de detalle / interés

```python
_KEYWORDS_INTERES = [
    "me interesa", "quiero info", "más info", "mas info", "info",
    "detalle", "cuéntame", "cuentame", "saber más", "saber mas",
    "esta me gusta", "me gusta", "interesante", "quiero verla",
    "puedo verla", "visita", "agendar", "cuando puedo",
    "cuanto sale", "cuánto sale", "precio", "cuánto cuesta",
    "cuanto cuesta", "me la muestran", "quiero esa",
]
```

### 🟢 Pedir hablar con humano

```python
_KEYWORDS_HUMANO = [
    "hablar con", "pasame", "asesor", "humano", "persona real",
    "alguien más", "alguien mas", "ayuda", "no entiendo",
    "mejor hablo", "me atiende alguien", "comunicarme",
]
```

### 🟢 Urgencia alta

```python
_KEYWORDS_URGENCIA_ALTA = [
    "ya", "ahora", "esta semana", "urgente", "rapido", "rápido",
    "cuanto antes", "cuánto antes", "necesito", "tengo que",
    "hoy", "mañana", "esta semana", "apuro",
]
```

### 🟢 Evasivo / curioso

```python
_KEYWORDS_CURIOSO = [
    "solo miraba", "solo miro", "por curiosidad", "estoy viendo",
    "curioso", "despues veo", "después veo", "cuando pueda",
    "cuando tenga la plata", "no estoy seguro", "no sé todavia",
    "no sé todavía", "tengo que ver", "pregunto nomás",
]
```

## Patrón helper para aplicar keywords

```python
def _match_any(texto_lower: str, keywords: list[str]) -> bool:
    """True si el texto contiene alguna keyword."""
    return any(kw in texto_lower for kw in keywords)


def _extract_budget(texto_lower: str) -> str | None:
    """Extrae presupuesto si el cliente menciona un número."""
    import re
    # Match: $100k, 100.000, 100 mil, USD 100, etc.
    m = re.search(r'\b(\d{1,4})[.,]?(\d{3})?\s*(k|mil|000)?\s*(usd|dolares|pesos|ars)?', texto_lower)
    if m:
        return m.group(0).strip()
    return None


def _extract_zona(texto_lower: str, zonas_list: list[str]) -> str | None:
    """Detecta si el cliente menciona alguna de las zonas disponibles."""
    import unicodedata
    def norm(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                      if unicodedata.category(c) != "Mn")
    texto_norm = norm(texto_lower)
    for zona in zonas_list:
        if norm(zona) in texto_norm:
            return zona
    return None
```

## Cuándo NO usar keywords deterministas

Las keywords son blunt tools. NO usarlas cuando:

1. **Comprensión semántica profunda** → "mi viejo me recomendó esta zona" vs "prefiero zona norte" (el LLM entiende mejor)
2. **Respuestas ambiguas** → "más o menos" / "depende" → dejar al LLM
3. **Primera interacción** → el LLM debe saludar y pedir contexto
4. **Preguntas complejas** → "qué ventajas tiene comprar acá vs alquiler?" → LLM

## Tests unitarios recomendados

```python
def test_keywords_pedir_opciones():
    casos_positivos = [
        "que opciones tienen",
        "QUÉ OPCIONES TIENEN PARA INVERSIÓN",
        "quiero ver algo",
        "mostrame lo que tienen",
        "que hay disponible",
    ]
    casos_negativos = [
        "hola",
        "cuanto sale esa casa",
        "me interesa la zona norte",
    ]
    for caso in casos_positivos:
        assert _match_any(caso.lower(), _KEYWORDS_PEDIR_OPCIONES), f"debería matchear: {caso}"
    for caso in casos_negativos:
        assert not _match_any(caso.lower(), _KEYWORDS_PEDIR_OPCIONES), f"no debería matchear: {caso}"
```

## Evitar duplicados con LLM

Si agregás una nueva regla determinista, **sacala del prompt del LLM** para no confundirlo. Ejemplo: si el Python maneja "quiero ver opciones", el prompt NO debe decir "si pide opciones, mostralas".

El prompt del LLM debe encargarse SOLO de lo que:
- Requiere comprensión semántica
- El Python determinista no puede capturar bien
- Genera texto natural al cliente

## Trampa común: keywords genéricas matchean PREGUNTAS del cliente

Bug histórico Sprint 1 Robert (commit `5dbb8c6`):

```python
# ❌ MAL — "precio" / "cuánto" / "presupuesto" matchea preguntas
if any(kw in texto_lower for kw in ["precio", "cuánto", "presupuesto"]):
    sesion["resp_presupuesto"] = texto  # ← guarda "qué precio tiene?"
```

Cuando el cliente pregunta "qué precio tiene?", el regex matcheaba "precio" y guardaba la pregunta como si fuera el presupuesto del cliente.

**Fix**: para datos numéricos como presupuesto/edad/cantidad, **requerir que el texto contenga un número + unidad**:

```python
# ✅ BIEN — solo matchea si hay número real
m_pres = re.search(r'\b(\d{1,4})\s*(k|mil|000|usd|ars|pesos|\$)', texto_lower)
if m_pres:
    sesion["resp_presupuesto"] = texto[:80]
    # ... extraer número real, mapear a rangos
```

Regla general: **si el dato es numérico, exigir un número en el texto del cliente**. Si solo hay verbos/adjetivos, dejar al LLM extraerlo (vía línea `PRESUPUESTO: X` en la respuesta).

## Debugging

Si sospechás que un caso debería matchear pero no lo hace:

```python
def debug_match(texto: str, keywords: list[str]):
    texto_lower = texto.lower()
    for kw in keywords:
        if kw in texto_lower:
            print(f"✅ MATCH: '{kw}' en '{texto}'")
    else:
        print(f"❌ NO MATCH: '{texto}'")
        print(f"   Texto normalized: '{texto_lower}'")
```
