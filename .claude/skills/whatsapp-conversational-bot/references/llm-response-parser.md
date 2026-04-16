# LLM Response Parser — Tolerante

Parser tolerante de respuestas del LLM que separa el mensaje natural (para el cliente) de la extracción de datos estructurada (para Python). Tolera bullets, markdown, emojis, headers.

## El problema

El prompt pide al LLM algo como:
```
Parte 1 — mensaje natural al cliente
Parte 2 — EXTRACCIÓN DE DATOS al final:
NOMBRE: ...
EMAIL: ...
ACCION: ...
```

Pero el LLM a veces devuelve:
```
Hola Arnaldo! Gracias por escribir...

### EXTRACCIÓN DE DATOS:
- **NOMBRE**: Arnaldo
- **EMAIL**: null
• OBJETIVO: vivir
```

Si el parser es estricto (busca "NOMBRE: ..."), falla y la extracción leaks al cliente. El parser tolerante sacude todo el formato y extrae igual.

## Implementación

```python
KEYS_INTERNAS = {
    "ACCION", "EMAIL", "NOMBRE", "SUBNICHE", "CIUDAD", "OBJETIVO", "TIPO",
    "ZONA", "PRESUPUESTO", "URGENCIA", "FORMA_PAGO", "AUTORIDAD", "MOTIVO", "SCORE"
}

HEADERS_INTERNOS = {
    "EXTRACCIÓN DE DATOS", "EXTRACCION DE DATOS", "ACCIONES", "DATOS EXTRAÍDOS",
    "DATOS EXTRAIDOS", "---", "===",
}


def _normalizar_linea_extraccion(linea_raw: str):
    """Devuelve (key, value) si la línea es de extracción, sino None.

    Tolera:
    - Bullets: - * • · ▪ ► ◦ ● ◾ ▶ ➤ →
    - Markdown: **KEY**: value
    - Espacios al inicio
    - Case insensitive en keys
    """
    # Limpia bullets, *, espacios, emojis comunes al inicio
    cleaned = re.sub(r'^[\s\-•*·▪►◦●◾▶➤→\u2022\u2023]+', '', linea_raw).strip()
    # Quita ** ** alrededor de la KEY (markdown)
    cleaned = re.sub(r'^\*+\s*', '', cleaned)
    # Match KEY: VALUE (case-insensitive)
    m = re.match(r'^([A-ZÁÉÍÓÚÑ_]+)\s*:\s*(.*)$', cleaned)
    if not m:
        return None
    key_upper = m.group(1).upper().strip("*").strip()
    if key_upper in KEYS_INTERNAS:
        # Limpiar valor: quitar ** al final, "null" → ""
        value = m.group(2).strip()
        value = re.sub(r'\*+\s*$', '', value).strip()
        if value.lower() in ("null", "none", "n/a", "-"):
            value = ""
        return key_upper, value
    return None


def _es_header_interno(linea_raw: str) -> bool:
    """True si la línea es un header tipo 'EXTRACCIÓN DE DATOS' o separador."""
    cleaned = re.sub(r'^[\s\-•*·▪►◦●◾▶➤→#\u2022\u2023]+', '', linea_raw).strip()
    cleaned = re.sub(r'^\*+\s*|\*+\s*$', '', cleaned).strip()
    cleaned = re.sub(r':\s*$', '', cleaned)  # "EXTRACCIÓN DE DATOS:" → "EXTRACCIÓN DE DATOS"
    return cleaned.upper() in HEADERS_INTERNOS or cleaned in ("---", "===", "###")


def _parse_llm_response(respuesta: str) -> tuple[str, dict]:
    """Separa el mensaje natural de la extracción de datos.

    Returns:
        (mensaje_para_cliente, {"accion": ..., "nombre": ..., etc.})
    """
    lineas = respuesta.split("\n")
    mensaje_lineas = []
    acciones = {}

    for linea in lineas:
        linea_stripped = linea.strip()
        if not linea_stripped:
            # Línea vacía — la incluimos en el mensaje solo si ya no estamos en modo extracción
            if not acciones:  # todavía no empezó la extracción
                mensaje_lineas.append(linea)
            continue

        # ¿Es header "EXTRACCIÓN DE DATOS"?
        if _es_header_interno(linea_stripped):
            continue  # Skip, no lo mostramos al cliente ni lo parseamos

        # ¿Es línea de extracción KEY: VALUE?
        extraccion = _normalizar_linea_extraccion(linea_stripped)
        if extraccion:
            key, value = extraccion
            acciones[key.lower()] = value
            continue  # No incluir en mensaje

        # Línea normal del mensaje
        mensaje_lineas.append(linea)

    # Join y limpiar
    mensaje = "\n".join(mensaje_lineas).strip()

    # Remover líneas vacías dobles
    mensaje = re.sub(r'\n{3,}', '\n\n', mensaje)

    return mensaje, acciones
```

## Uso en `_procesar()`

```python
respuesta_llm = _llm(texto, system=system_prompt)
if not respuesta_llm:
    _enviar_texto(telefono, "Disculpá, tuve un problema técnico. 🙏")
    return

mensaje_final, acciones = _parse_llm_response(respuesta_llm)

# Guardar datos extraídos en la sesión
sesion_nueva = {**sesion}
if acciones.get("nombre"):       sesion_nueva["nombre"] = acciones["nombre"].title()
if acciones.get("email"):        sesion_nueva["email"] = acciones["email"].lower()
if acciones.get("objetivo"):     sesion_nueva["resp_objetivo"] = acciones["objetivo"]
if acciones.get("tipo"):         sesion_nueva["resp_tipo"] = acciones["tipo"]
if acciones.get("zona"):         sesion_nueva["resp_zona"] = acciones["zona"]
if acciones.get("presupuesto"):  sesion_nueva["resp_presupuesto"] = acciones["presupuesto"]
if acciones.get("urgencia"):     sesion_nueva["resp_urgencia"] = acciones["urgencia"]
if acciones.get("forma_pago"):   sesion_nueva["forma_pago"] = acciones["forma_pago"]
if acciones.get("autoridad"):    sesion_nueva["autoridad"] = acciones["autoridad"]
if acciones.get("motivo"):       sesion_nueva["motivo"] = acciones["motivo"]
if acciones.get("score"):        sesion_nueva["score"] = acciones["score"]

SESIONES[telefono] = sesion_nueva

# Ejecutar ACCION
accion = acciones.get("accion", "").lower()
```

## Tests del parser

```python
def test_parser_tolerante():
    """Casos que el parser DEBE manejar."""

    # Caso 1: Formato estricto (ideal)
    resp1 = """Hola! Gracias por escribir.

EXTRACCIÓN DE DATOS
NOMBRE: Arnaldo
EMAIL: arnaldo@test.com
ACCION: continuar"""
    msg, acc = _parse_llm_response(resp1)
    assert "Hola! Gracias" in msg
    assert "EXTRACCIÓN" not in msg
    assert acc["nombre"] == "Arnaldo"
    assert acc["email"] == "arnaldo@test.com"
    assert acc["accion"] == "continuar"

    # Caso 2: Bullets
    resp2 = """Hola Arnaldo!

• NOMBRE: Arnaldo
• EMAIL: arnaldo@test.com
• ACCION: continuar"""
    msg, acc = _parse_llm_response(resp2)
    assert acc["nombre"] == "Arnaldo"

    # Caso 3: Markdown
    resp3 = """Hola!

**NOMBRE**: Arnaldo
**ACCION**: mostrar_props"""
    msg, acc = _parse_llm_response(resp3)
    assert acc["nombre"] == "Arnaldo"
    assert acc["accion"] == "mostrar_props"

    # Caso 4: Header con ### y :
    resp4 = """Hola!

### EXTRACCIÓN DE DATOS:
- NOMBRE: Arnaldo
- ACCION: continuar"""
    msg, acc = _parse_llm_response(resp4)
    assert "EXTRACCIÓN" not in msg
    assert acc["nombre"] == "Arnaldo"

    # Caso 5: "null" debe convertir a ""
    resp5 = """Hola!

EMAIL: null
NOMBRE: Arnaldo"""
    msg, acc = _parse_llm_response(resp5)
    assert acc["email"] == ""
    assert acc["nombre"] == "Arnaldo"

    # Caso 6: Separadores ---
    resp6 = """Hola!

---
NOMBRE: Arnaldo"""
    msg, acc = _parse_llm_response(resp6)
    assert "---" not in msg
    assert acc["nombre"] == "Arnaldo"
```

## Mensajes residuales

A veces el parser remueve todo y el mensaje queda vacío. Protección:

```python
if not mensaje_final or len(mensaje_final) < 3:
    mensaje_final = f"Perfecto{', ' + nombre_corto if nombre_corto else ''}. Contame un poco más para ayudarte mejor. 😊"
```

## Scoring desde el LLM

El LLM puede asignar score directamente, pero ES MÁS CONFIABLE tener una función Python que lo calcule desde los datos BANT:

```python
def _calcular_score_bant(sesion: dict) -> str:
    """Calcula score caliente/tibio/frio desde datos BANT."""
    presupuesto = (sesion.get("resp_presupuesto") or "").lower()
    urgencia = (sesion.get("resp_urgencia") or "").lower()
    autoridad = (sesion.get("autoridad") or "").lower()
    forma_pago = (sesion.get("forma_pago") or "").lower()

    puntos = 0
    # Budget: si hay número concreto
    if any(c.isdigit() for c in presupuesto):
        puntos += 3
    elif presupuesto in ("alto", "definido"):
        puntos += 2
    elif presupuesto:
        puntos += 1

    # Timeline
    if any(kw in urgencia for kw in ["ya", "ahora", "este mes", "urgente"]):
        puntos += 3
    elif any(kw in urgencia for kw in ["3m", "3 meses", "pronto"]):
        puntos += 2
    elif urgencia:
        puntos += 1

    # Authority
    if autoridad in ("solo", "si", "yo decido"):
        puntos += 2
    elif autoridad:
        puntos += 1

    # Forma pago concreta (contado/credito aprobado) = +2
    if forma_pago in ("contado", "credito aprobado", "credito aprobado"):
        puntos += 2
    elif forma_pago:
        puntos += 1

    # Clasificar
    if puntos >= 8:
        return "caliente"
    elif puntos >= 4:
        return "tibio"
    else:
        return "frio"
```

Entonces en el flujo:
```python
# Preferir la lógica determinista sobre lo que diga el LLM
score_calculado = _calcular_score_bant(sesion_nueva)
sesion_nueva["score"] = score_calculado
```

## Bug histórico — Extracción fugando al cliente

Síntoma: el cliente recibe texto como:
```
Hola Arnaldo!

EXTRACCIÓN DE DATOS
• NOMBRE: Arnaldo
• ACCION: continuar
```

Causas y fix:

| Causa | Fix |
|---|---|
| Parser estricto no matchea bullets `•` | Usar `_normalizar_linea_extraccion()` con regex tolerante |
| Header `### EXTRACCIÓN` no se detecta | Agregar `###` al filtro de headers |
| LLM usa `**NOMBRE**:` con markdown | Regex strip `\*+` |
| LLM usa `— NOMBRE: valor` (em dash) | Agregar `—` al set de bullets |

Ante la duda, **agregar más caracteres al regex de limpieza** y hacer test unitario con el caso real.
