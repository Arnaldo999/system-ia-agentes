---
proyecto: arnaldo
tipo: caso-estudio (pro-bono / referidos)
estado: discovery pendiente
reunion: sábado 10 AM en la iglesia
contacto: Pablo Ezequiel Tomé Pose Weninger (Pastor)
relacion_personal: Arnaldo es amigo de Gastón (hermano de Pablo)
tracks_paralelos:
  - A: Iglesia (Nuestra Iglesia / Café Nueva Vida) — pro-bono, caso de estudio
  - B: Pablo persona (redes sociales personales del Pastor) — cliente potencial pago, conversación posterior
---

# Brief Discovery — Nuestra Iglesia

## Objetivo del documento

Recopilar TODA la información técnica + operativa el sábado para diseñar la automatización
sin volver a molestar al equipo. Imprimible o abrir en celu durante la reunión.

## Cómo usar este formulario

1. Llegá 15 min antes y observá un ensayo o servicio si están preparándose.
2. Recorré las 7 secciones con el equipo presente (medios + TV).
3. Pedí ver físicamente la PC, los cables, la consola de audio, la pantalla.
4. Si te dejan, **grabá audio de la reunión** (con permiso explícito) — vas a captar detalles que no anotes.
5. Sacá fotos de: PC operador (pantalla y trasera con conexiones), consola de audio, pantalla gigante en uso, setup de cámaras, cualquier setlist o cuaderno físico que usen.
6. Al final, dejá 10 min para que ELLOS te muestren lo que les frustra (no preguntar — observar).

---

## SECCIÓN 1 — Equipo humano y roles

| Pregunta | Respuesta |
|----------|-----------|
| ¿Cuántas personas componen el equipo de medios? | |
| ¿Cuántas el equipo de TV/streaming? | |
| ¿Quién opera la pantalla gigante un domingo típico? (nombre) | |
| ¿Es siempre la misma persona o rotan? | |
| ¿Qué nivel técnico tienen? (autodidactas / curso formal / nada) | |
| ¿Hay alguien con conocimiento de programación o redes? | |
| ¿Quién decide qué canciones se cantan y cuándo se carga el setlist? | |
| ¿Cuándo se prepara el setlist? (sábado / domingo a la mañana / sobre la marcha) | |

---

## SECCIÓN 2 — PC del operador y software actual

| Pregunta | Respuesta |
|----------|-----------|
| Marca y modelo de la PC | |
| Sistema operativo (Windows / Mac / Linux) y versión | |
| Memoria RAM (mínimo deseado: 16GB para correr Whisper + Gemma local) | |
| Procesador (anotar generación: ej "Ryzen 5 5600", "Intel i5 12va gen") | |
| ¿Tiene GPU dedicada? Marca/modelo y VRAM | |
| Espacio libre en disco (Whisper + Gemma 3 4B ocupan ~10GB juntos) | |
| ¿Cuántas salidas de video tiene la PC? (HDMI / VGA / DisplayPort) | |
| ¿Cuántos monitores usa el operador hoy? (uno solo / monitor + pantalla gigante) | |
| ¿La PC se queda encendida 24/7 o se apaga entre cultos? | |
| Software de presentación que usan HOY (ProPresenter / EasyWorship / PowerPoint / OpenLP / Freeshow / otro) | |
| ¿Versión y si es licencia paga o gratis? | |
| ¿Hace cuánto lo usan? | |
| ¿Por qué eligieron ese software? | |
| ¿Qué cosas les gustan de él? | |
| ¿Qué cosas les frustran? | |

**Foto requerida**: pantalla del software abierto + parte trasera de la PC (conexiones)

**Nota técnica para Arnaldo (actualizada con Gemma 4):**

Gemma 4 (lanzado abril 2026) tiene multimodal nativo audio + texto + imagen + video. Reemplaza la combinación Whisper + Gemma 3 anterior con un solo modelo. Variantes:
- **Gemma 4 E2B (~2B efectivos)**: corre con 8GB RAM, sin GPU. Audio + visión + texto.
- **Gemma 4 E4B (~4B efectivos)**: corre con 8-12GB RAM, sin GPU. Calidad superior. **Default recomendado para iglesia.**
- **Gemma 4 26B MoE**: necesita 16GB RAM + GPU 12-16GB VRAM (RTX 4070 Ti+). Overkill para este caso.
- **Gemma 4 31B Dense**: 24GB+ VRAM. Innecesario.

Escenarios según hardware iglesia:
- PC con 8GB+ RAM y CPU moderno (i5/Ryzen 5 últimos 4 años) → **Gemma 4 E4B corre cómodo sin GPU**. Estamos.
- PC con 16GB RAM y GPU 8GB+ → vuela todo, podríamos usar 26B MoE para mejor calidad.
- PC con <8GB RAM o muy vieja → mini-PC dedicado IA (~USD 400-500) o usar E2B que es más liviano.

Audio en Gemma 4: ventanas de 30 segundos máximo, 25 tokens/seg de audio. Implementación: ventana móvil 5-10s con solapamiento. Ver proyecto open source `Parlor` (github.com/fikrikarim/parlor) como referencia de arquitectura.

---

## SECCIÓN 3 — Textos bíblicos: formato actual

| Pregunta | Respuesta |
|----------|-----------|
| ¿Qué versión/traducción usan habitualmente? (RV1960 / NVI / NTV / DHH / otra) | |
| ¿Tienen la Biblia completa cargada en el software? | |
| ¿Cómo la cargaron? (importada / vino con el software / la tipearon a mano) | |
| ¿En qué formato la guardan? (archivo del software / Word / PDF / base de datos / otro) | |
| ¿Tienen acceso al archivo fuente o solo está dentro del software? | |
| Cuando el Pastor cita un versículo en vivo, ¿cómo lo busca el operador? (escribe referencia / busca por palabra / lo tiene pre-cargado en setlist) | |
| ¿Cuánto tarda en aparecer en pantalla un versículo no preparado? (estimación en segundos) | |
| ¿El Pastor avisa antes qué versículos va a citar o improvisa? | |
| ¿Tienen lista de "versículos del culto" preparada antes? | |

**Foto requerida**: una búsqueda real de un versículo, midiendo tiempo con cronómetro del celu

---

## SECCIÓN 4 — Canciones y letras

| Pregunta | Respuesta |
|----------|-----------|
| ¿Cuántas canciones cantan en un culto típico? | |
| ¿Tienen las letras cargadas o las tipean cada vez? | |
| ¿Tienen licencia CCLI / SongSelect? (sí / no) | |
| Repertorio aproximado de canciones (10 / 50 / 200+) | |
| ¿En qué formato guardan las letras? (dentro del software / Word / cuaderno físico) | |
| ¿Quién las cargó? ¿Hace cuánto? | |
| Hoy las letras avanzan: (manualmente con espacio/click / automático por tiempo / no avanzan, quedan estáticas con toda la letra) | |
| Cuando avanzan, ¿hay animación o son cambios "duros"? | |
| ¿El operador conoce las canciones de memoria o sigue de oído? | |
| ¿El equipo de músicos avisa por intercom cuándo cambia de estrofa? | |

**Anotación crítica**: durante un ensayo si lo ves, anotá cuántas veces se "atrasa" la letra vs el cantante.

---

## SECCIÓN 5 — Audio (clave para Whisper)

| Pregunta | Respuesta |
|----------|-----------|
| Marca y modelo de la consola de audio | |
| ¿Es analógica o digital? | |
| ¿Cuántos canales? | |
| ¿De qué tipo de micrófonos usa el Pastor? (corbatero / vincha / mano) | |
| ¿El audio del Pastor sale por un canal independiente o mezclado con todo? | |
| ¿Hay salida AUX disponible que puedan rutear a la PC? | |
| ¿Hay tarjeta de audio USB / interfaz entre consola y PC? | |
| ¿Cómo entra el audio a la PC del streaming hoy? (cable directo / interfaz USB / no entra) | |
| Distancia de la consola a la PC del operador (metros) | |
| ¿Hay ruido de fondo significativo en el ambiente? (banda tocando / aire acondicionado / eco) | |

**Foto requerida**: consola de audio + cualquier interfaz USB que tengan

---

## SECCIÓN 6 — Pantalla gigante y proyección

| Pregunta | Respuesta |
|----------|-----------|
| ¿Es pantalla LED, proyector, TV grande? | |
| Tamaño aproximado / resolución (si saben) | |
| ¿Cómo se conecta a la PC? (HDMI directo / cable largo / extensor HDMI sobre red / wireless) | |
| Distancia entre PC operador y pantalla (metros) | |
| ¿Qué se ve en la pantalla cuando NO hay versículo o letra? (logo / cámara en vivo / fondo estático / negro) | |
| ¿Tiene buena visibilidad para todo el público? | |
| Estilo visual actual: ¿blanco sobre negro, otra paleta, cuál? | |
| Tipografía actual: ¿saben qué fuente usan? | |

**Foto requerida**: la pantalla en uso real durante un servicio (pedir si tienen)

---

## SECCIÓN 7 — Streaming a YouTube y Facebook

| Pregunta | Respuesta |
|----------|-----------|
| ¿Streamean en vivo? (sí / no) | |
| ¿A qué plataformas? (YouTube / Facebook / ambas / otra) | |
| ¿Streamean a las 2 simultáneamente o de a una? | |
| Si simultáneamente, ¿cómo lo hacen? (Restream / OBS multi-output / 2 PCs / otro) | |
| Software de streaming (OBS / vMix / StreamYard / nativo) | |
| ¿La PC del streaming es la misma del operador de pantalla? | |
| ¿Cuántas cámaras usan? | |
| ¿Quién opera el switcher? | |
| ¿Tienen overlays o lower thirds? (nombre del predicador, cita bíblica en pantalla del stream) | |
| ¿Bajan los videos para subirlos editados después o queda solo el live? | |
| ¿Hacen clips/Reels del culto para redes? | |
| Si los hacen: ¿quién, con qué herramienta, cuánto tiempo? | |
| Internet de la iglesia (fibra / cable / 4G) y velocidad de subida estimada | |

---

## SECCIÓN 8 — Redes sociales de la iglesia

| Pregunta | Respuesta |
|----------|-----------|
| Instagram (link / handle) | |
| Facebook (link de la página) | |
| YouTube (canal) | |
| TikTok (si tienen) | |
| ¿Quién maneja las redes? | |
| ¿Con qué frecuencia publican? | |
| ¿Qué publican? (versículos / clips / anuncios / fotos) | |
| ¿Usan algún programador de posts? (Meta Business Suite / Buffer / Later / nada) | |
| ¿Tienen identidad visual definida? (logo, paleta, tipografía) | |
| ¿Hay manual de marca o lo hacen "a ojo"? | |

---

## SECCIÓN 9 — Dolor real (no preguntar — escuchar)

> Esta sección la llenás VOS después de la reunión, con lo que el equipo dijo entre líneas.
> Si todos coinciden en una queja → es prioridad real. Si solo lo dice 1 persona → matiz pero no urgente.

| Dolor mencionado | Quién lo dijo | ¿Qué tan grave? |
|-------------------|--------------|------------------|
| | | |
| | | |
| | | |

---

## SECCIÓN 10 — Restricciones y límites

| Pregunta | Respuesta |
|----------|-----------|
| Presupuesto disponible para hardware nuevo (si necesitamos) | |
| ¿Hay alguien que se opondría a cambiar el software actual? | |
| ¿Quién tiene la última palabra técnica? (Pablo / líder de medios / nadie definido) | |
| ¿Hay reuniones de equipo de medios? ¿Cada cuánto? | |
| ¿Están dispuestos a aprender un software nuevo si es claramente mejor? | |
| Días/horarios disponibles para entrenamiento del equipo | |
| ¿Hay riesgo de que el operador principal renuncie o se vaya pronto? | |

---

## Después de la reunión — checklist Arnaldo

- [ ] Sumar todas las fotos a `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/nuestra-iglesia/discovery/`
- [ ] Pasar audio de reunión (si grabé) a Whisper para tener transcripción literal
- [ ] Llenar Sección 9 (dolor real) con lo escuchado entre líneas
- [ ] Marcar en cada sección con 🔴 / 🟡 / 🟢 las cosas críticas / importantes / nice-to-have
- [ ] Decidir Fase 1 con info real: si tienen GPU → Whisper local desde día 1; si no → quick wins primero, IA fase 2
- [ ] Armar propuesta formal con `/crear-plan` archivada en `02_OPERACION_COMPARTIDA/planes/`
- [ ] Dejar entidad `nuestra-iglesia.md` y `pablo-tome-pastor.md` en wiki Obsidian
- [ ] Mensaje de seguimiento a Pablo el lunes con resumen + próximos pasos

---

## Stack técnico decidido (referencia para Arnaldo)

> No leer esto al equipo el sábado. Es para vos, por si te preguntan en detalle.

| Capa | Herramienta | Por qué |
|------|-------------|---------|
| Software presentación | **Freeshow** (gratis, open source, multiplataforma) | Reemplaza ProPresenter/EasyWorship sin costo. API REST para integrar IA. |
| Captura audio | Tarjeta USB simple si no hay (Behringer UCA222 ~USD 30) | Lleva el audio de la consola a la PC del operador o PC dedicada IA |
| Comprensión audio + razonamiento | **Gemma 4 E4B** (multimodal nativo) vía LM Studio o Ollama | Procesa audio + razonamiento en una sola pieza. Reemplaza Whisper+Gemma 3 separados. Local, gratis, privado, multilingüe (140+ idiomas, español incluido). |
| Matcheo letra cantada | **`rapidfuzz`** (string matching) | Para sincronizar línea cantada con letra cargada — más rápido y confiable que LLM para esta tarea específica. |
| Worker integrador | **FastAPI Python** | Stack que ya manejamos. Reusa workers de Maicol. |
| Base de versículos | Importados de los archivos actuales de la iglesia (Sección 3) | Respetar versión bíblica que ya usan |
| Referencia de arquitectura | Proyecto Parlor (open source) | Demo funcional de Gemma 4 E2B haciendo voz+visión local en tiempo real. Mismo patrón aplica a iglesia. |

**Versiones de modelos (al 2026-04-26):**
- **Gemma 4** es la última generación oficial de Google (lanzada abril 2026). Multimodal: texto, imagen, audio, video.
- Usar **E4B** para iglesia: 4B parámetros efectivos, corre con 8-12GB RAM sin GPU obligatoria.
- Audio: ventanas de 30s máx, 25 tokens/seg. Implementar ventana móvil 5-10s con solapamiento.
- Tooling: **LM Studio** (UI) o **Ollama** (CLI/API REST) — ambos sirven. Ollama mejor para integrar con FastAPI.

**Por qué local y no cloud (OpenAI/Anthropic API):**
- Privacidad: contenido del sermón no sale de la iglesia
- Costo cero recurrente (la iglesia es pro-bono)
- Sin dependencia de internet (si se cae el wifi durante un culto, igual funciona)
- Aprendizaje para Arnaldo: este mismo stack se reusa en clientes pagos del rubro educación / eventos / podcasting

---

## Recordatorios para el sábado

- Llegá con **demo de Freeshow** corriendo en tu notebook: 2-3 versículos cargados + 1 canción con CSS bonito + búsqueda rápida funcionando. **5 minutos de demo > 1 hora de explicación**.
- No prometas la fase 2 (Whisper IA) hasta saber si tienen GPU. Si la prometés y después no se puede, perdés credibilidad.
- No mezcles los 2 tracks: hoy es **iglesia**. Lo de **redes personales de Pablo** es otra conversación, no la inicies vos.
- Sos amigo del hermano (Gastón) — es capital de confianza. **No lo usés explícitamente**. Si surge en charla, bien. Si no, tampoco.
- Tono: **par técnico que viene a aportar**, no agencia que viene a vender. La iglesia detecta el "modo venta" en 2 segundos.
- Llevá cuaderno físico para tomar notas. PC abierta solo cuando demostrás Freeshow.
