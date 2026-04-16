# Conversational Property Display — Una a la vez sin menú numérico

Patrón de presentación anti-curiosos: mostrar UNA propiedad a la vez de forma conversacional, y el lead tiene que **escribir** para avanzar.

## Por qué este patrón

**Problema del menú numérico** (*1* *2* *3*):
- El lead hace scroll pasivo sin compromiso
- Leads curiosos que no tienen presupuesto real siguen "explorando" sin dar señales
- El bot se siente como un catálogo/website, no como una conversación

**Solución — Una prop a la vez**:
- El cliente ve UNA propiedad con descripción natural
- Al final del mensaje: pregunta anchor ("¿querés más info o te muestro otra?")
- Si el lead responde, muestra señal de interés
- Los curiosos se filtran solos — no van a escribir varios mensajes sin intención real

## Función principal

```python
def _presentar_prop_breve(p: dict, idx: int, total: int) -> str:
    """Presenta UNA propiedad de forma conversacional, sin menú numérico."""
    precio = p.get("Precio", 0)
    moneda = p.get("Moneda", MONEDA)
    precio_str = f"${precio:,.0f} {moneda}" if precio else "a consultar"
    estado = p.get("Disponible", "")
    reservado = "Reservado" in str(estado)
    titulo = p.get("Titulo", "Propiedad")
    tipo  = p.get("Tipo", "")
    zona  = p.get("Zona", "")
    metros_t = p.get("Metros_Terreno", "")
    metros_c = p.get("Metros_Cubiertos", "")
    desc  = p.get("Descripcion", "")

    lineas = []
    # Intro variable según si es la primera o no
    if idx == 0:
        lineas.append("Mirá, tengo esta opción que puede interesarte 👇\n")
    else:
        lineas.append("También tengo esta 👇\n")

    lineas.append(f"🏡 *{titulo}*")
    if reservado:
        lineas.append("⏳ _(Reservada — podés anotarte por si se libera)_")

    # Línea compacta: zona · tipo · m2
    partes = []
    if zona:  partes.append(f"📍 {zona}")
    if tipo:  partes.append(tipo)
    if metros_t: partes.append(f"{metros_t}m²")
    elif metros_c: partes.append(f"{metros_c}m² cubiertos")
    if partes:
        lineas.append(" · ".join(partes))

    lineas.append(f"💰 *{precio_str}*")

    # Primera oración de la descripción (máx 1 línea)
    if desc:
        primera = desc.split(".")[0].strip()
        if primera and len(primera) > 5:
            lineas.append(f"\n_{primera}._")

    # Pregunta anchor al final
    restantes = total - idx - 1
    if restantes > 0:
        lineas.append(f"\n¿Querés que te cuente más sobre esta, o te muestro otra opción?")
    else:
        lineas.append(f"\n¿Qué te parece esta opción?")
    return "\n".join(lineas)
```

## Step `explorando` — Navegación por keywords

En lugar de esperar números (1/2/0), detectamos intención por texto libre. **IMPORTANTE**: este handler va ANTES del LLM call.

```python
# ── Step explorando → navegación conversacional (UNA prop a la vez) ─────
if step in ("explorando", "lista"):  # "lista" legacy
    props = sesion.get("props", [])
    prop_idx = sesion.get("prop_idx", 0)

    _KEYWORDS_SIGUIENTE = [
        "otra", "siguiente", "mas", "más", "no me interesa", "no es",
        "no se adapta", "otra opción", "otra opcion", "ver otra",
        "diferente", "no gracias", "no me convence", "que mas", "qué más",
        "hay mas", "hay más", "no me adapta", "algo mas", "algo más",
    ]
    _KEYWORDS_INTERES = [
        "me interesa", "quiero info", "más info", "mas info", "info",
        "detalle", "cuéntame", "cuentame", "saber más", "saber mas",
        "esta me gusta", "me gusta", "interesante", "quiero verla",
        "puedo verla", "visita", "agendar", "cuando puedo", "cuanto sale",
        "cuánto sale", "precio", "cuánto cuesta", "cuanto cuesta",
    ]

    _pide_siguiente = any(kw in texto_lower for kw in _KEYWORDS_SIGUIENTE)
    _pide_detalle   = any(kw in texto_lower for kw in _KEYWORDS_INTERES)

    if _pide_siguiente:
        next_idx = prop_idx + 1
        if next_idx < len(props):
            SESIONES[telefono] = {**sesion, "step": "explorando",
                                  "prop_idx": next_idx, "_ultimo_ts": ahora_ts}
            _enviar_texto(telefono, _presentar_prop_breve(props[next_idx], next_idx, len(props)))
            # Enviar imagen si tiene
            img_field = props[next_idx].get("Imagen_URL", "")
            img = (img_field[0].get("url","") if isinstance(img_field, list) and img_field
                   else img_field if isinstance(img_field, str) else "")
            if img:
                _enviar_imagen(telefono, img, caption=props[next_idx].get("Titulo",""))
        else:
            _enviar_texto(telefono,
                f"Ya te mostré todas las opciones disponibles ahora. "
                f"Si querés, {NOMBRE_ASESOR} tiene proyectos que no están publicados todavía. "
                f"¿Te contactamos?")
        return

    if _pide_detalle:
        prop = props[prop_idx] if prop_idx < len(props) else (props[-1] if props else None)
        if prop:
            SESIONES[telefono] = {**sesion, "step": "ficha",
                                  "ficha_actual": prop_idx, "_ultimo_ts": ahora_ts}
            _enviar_ficha(telefono, prop)  # envía imagen + ficha completa
        return

    # Si es ambiguo → dejar que el LLM responda (pasa al bloque del LLM más abajo)
```

## Ficha completa (cuando el lead pide detalle)

```python
def _ficha_propiedad(p: dict) -> str:
    precio = p.get("Precio", 0)
    moneda = p.get("Moneda", MONEDA)
    precio_str = f"${precio:,.0f} {moneda}" if precio else "Consultar precio"
    estado = p.get("Disponible", "✅ Disponible")
    es_reservado = "Reservado" in str(estado)
    titulo = p.get("Titulo", "Propiedad")

    lineas = [f"🏠 *{titulo}*"]
    if es_reservado:
        lineas.append("⏳ *RESERVADO* — Puede anotarse por si se libera\n")
    else:
        lineas.append("")

    desc = p.get("Descripcion", "")
    if desc:
        lineas.append(f"{desc}\n")

    lineas.append(f"💰 *Precio:* {precio_str}")
    if p.get("Operacion"):        lineas.append(f"📋 *Operación:* {p['Operacion'].capitalize()}")
    if p.get("Tipo"):             lineas.append(f"🏡 *Tipo:* {p['Tipo']}")
    if p.get("Dormitorios"):      lineas.append(f"🛏 *Dormitorios:* {p['Dormitorios']}")
    if p.get("Banos"):            lineas.append(f"🚿 *Baños:* {p['Banos']}")
    if p.get("Metros_Cubiertos"): lineas.append(f"📐 *Sup. cubierta:* {p['Metros_Cubiertos']}m²")
    if p.get("Metros_Terreno"):   lineas.append(f"🌿 *Terreno:* {p['Metros_Terreno']}m²")
    if p.get("Zona"):             lineas.append(f"📍 *Zona:* {p['Zona']}")
    if p.get("Google_Maps_URL"):  lineas.append(f"\n🗺 *Ver en Maps:* {p['Google_Maps_URL']}")

    # Pregunta anchor al final — SIN shortcuts numéricos
    lineas.append(f"\n¿Qué te parece? Si te interesa te puedo gestionar una visita con {NOMBRE_ASESOR}. 😊")
    return "\n".join(lineas)


def _enviar_ficha(telefono: str, p: dict) -> None:
    """Envía imagen + ficha completa."""
    img_field = p.get("Imagen_URL", "")
    if isinstance(img_field, list) and img_field:
        img = img_field[0].get("url", "")
    elif isinstance(img_field, str):
        img = img_field
    else:
        img = ""
    if img:
        _enviar_imagen(telefono, img, caption=p.get("Titulo", ""))
    _enviar_texto(telefono, _ficha_propiedad(p))
```

## Reglas del sistema conversacional

### ✅ SÍ hacer
- Una prop a la vez
- Pregunta anchor al final de cada mensaje
- Imagen adjunta (cuando hay) JUNTO con el texto
- Variar intros ("Mirá, tengo esta..." vs "También tengo esta...")
- Cerrar con CTA de visita con el asesor cuando muestran interés

### ❌ NO hacer
- Listar varias props en un mismo mensaje
- Mostrar footer con `*0* Ver otras opciones | *#* Hablar con asesor`
- Pedir número de prop al lead
- Mostrar toda la info de la prop antes de que pida detalle
- Ofrecer props al principio de la conversación (antes de calificar BANT)

## Cuándo mostrar props

1. **Anti-friction explícito**: el cliente pide "ver opciones" literalmente → mostrar SIN pedir presupuesto
2. **Calificado (caliente/tibio)**: tiene los 4 datos BANT y el score ameritar propiedades
3. **Acción `mostrar_props` del LLM**: el LLM decidió que es momento

## Bug que evita este patrón

**No se puede empezar a mostrar props directamente para leads cualquiera** — primero hay que calificar mínimamente (objetivo + tipo) para filtrar curiosos. La excepción es cuando piden explícitamente "qué opciones tienen" (anti-friction).

## Step `ficha` — después de mostrar el detalle

Cuando el bot muestra la ficha completa, el step pasa a `"ficha"`. A partir de ahí, el LLM maneja la conversación (preguntas específicas sobre la propiedad, agendar visita, etc.):

```python
if step == "ficha":
    # Cualquier respuesta → LLM decide (ofrecer cita, responder pregunta, etc.)
    if mensaje_final:
        _enviar_texto(telefono, mensaje_final)
        _agregar_historial(telefono, "Bot", mensaje_final)
    return
```

## Ejemplo de conversación completa

```
Cliente: que opciones tienen
Bot:     Mirá, tengo esta opción que puede interesarte 👇
         🏡 *Lote en loteo privado - Apóstoles*
         📍 Apóstoles · terreno · 360m²
         💰 *$7,000 USD*
         _Lote en loteo privado con escritura inmediata._
         ¿Querés que te cuente más sobre esta, o te muestro otra opción?
         [📷 imagen]

Cliente: no me interesa mostrá otra
Bot:     También tengo esta 👇
         🏡 *Terreno céntrico en Gdor. Roca*
         📍 Gdor Roca · terreno · 300m²
         💰 *$9,500 USD*
         ¿Querés que te cuente más sobre esta, o te muestro otra opción?
         [📷 imagen]

Cliente: esta me gusta, cuanto sale?
Bot:     🏠 *Terreno céntrico en Gdor. Roca - 10x30*
         Terreno de 300m² con todos los servicios: luz, agua y cloacas...
         💰 *Precio:* $9,500 USD
         📋 *Operación:* Venta
         🏡 *Tipo:* terreno
         🌿 *Terreno:* 300m²
         📍 *Zona:* Gdor Roca
         ¿Qué te parece? Si te interesa te puedo gestionar una visita con Roberto. 😊
```

El cliente avanzó en 3 mensajes y demostró compromiso real. Un curioso hubiese abandonado tras la primera prop.
