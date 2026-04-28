# Prompts para Claude Design — Nuestra Iglesia

Dos pantallas separadas. Pasale UN prompt a la vez para que Claude Design pueda iterar.

---

## PROMPT 1 — Pantalla Pública (la que va al proyector / TV gigante)

```
Diseñá un único archivo HTML autocontenido (HTML + CSS + JS inline, sin frameworks externos, sin CDNs salvo Google Fonts) para la PANTALLA PÚBLICA de una iglesia evangélica. Esta pantalla la ve el público durante el culto, proyectada en una TV grande o pantalla LED. Debe ser visualmente impactante, espiritualmente cálida pero moderna, y completamente legible desde 20 metros.

CONTEXTO:
- Iglesia evangélica de comunidad pequeña-mediana en Argentina (LATAM)
- Hoy proyectan en blanco sobre negro, plano, sin estilo. Quieren un salto visual fuerte
- Debe servir para mostrar versículos bíblicos Y letras de canciones de adoración
- Pantalla a 1920x1080 mínimo, 16:9, fullscreen permanente

REQUISITOS DE DISEÑO:
- Dark mode obligatorio (el ambiente del culto está con luz baja)
- Tipografía: usar Google Fonts. Sugerencia: "Cormorant Garamond" para versículos (elegante, serif espiritual) + "Inter" o "Plus Jakarta Sans" para letras de canciones (clean, moderno). Podés elegir otras si justificás
- Paleta sugerida (modificar si tenés mejor idea):
  * Fondo: gradient dinámico oscuro tipo púrpura profundo / azul noche / negro
  * Acentos: dorado suave (#f59e0b o #fbbf24) o gradient cálido para "presencia"
  * Texto: blanco puro con leve glow
- 3 escenas distintas: idle, versículo, canción/letra. Transiciones suaves entre escenas (fade ~800ms)
- En modo CANCIÓN: mostrar 3 líneas verticales centradas — anterior (chica, 25% opacidad arriba), actual (gigante, 100% blanco, animación de entrada), siguiente (chica, 25% opacidad abajo). Barra de progreso fina al pie
- En modo VERSÍCULO: referencia chica arriba en color acento (ej "JUAN 3:16"), versículo gigante centrado en serif elegante, versión de la biblia chiquita abajo (ej "RV1960")
- En modo IDLE: nombre de la iglesia "Nuestra Iglesia" minimalista + "Bienvenidos" o algo cálido. Animación sutil de fondo (partículas, gradient breathing, lo que se vea espiritual sin ser kitsch)
- NO usar emojis, NO usar imágenes raster, NO usar logos genéricos. Todo CSS puro
- Cursor: oculto siempre (cursor: none)
- Click en cualquier parte → fullscreen automático

INTEGRACIÓN TÉCNICA OBLIGATORIA (no la cambies, el backend ya está hecho):
La pantalla recibe estado vía WebSocket en `ws://${location.host}/ws/publico`. Cada mensaje JSON tiene esta estructura:

Estado IDLE:
{ "tipo": "idle", "contenido": null }

Estado VERSÍCULO:
{ "tipo": "versiculo", "referencia": "Juan 3:16", "texto": "Porque de tal manera amó Dios al mundo...", "version": "RV1960" }

Estado LETRA DE CANCIÓN:
{ "tipo": "letra", "cancion_titulo": "Cuán grande es Él", "linea_actual": "Mi corazón entona la canción", "linea_anterior": "Y ver brillar al sol en su cenit", "linea_siguiente": "Cuán grande es Él, cuán grande es Él", "linea_index": 4, "total_lineas": 14 }

El JS debe:
1. Conectar al WebSocket al cargar
2. Reconectar automáticamente si se cae (cada 2s)
3. Cambiar la escena visible según `tipo`
4. Animar la entrada de cada cambio
5. Si `linea_anterior` o `linea_siguiente` son null, ocultar el slot correspondiente sin reflowear el resto

ENTREGÁ: un solo bloque de código HTML completo, autocontenido, listo para guardar como `publico.html` y abrir directo en navegador. Sin dependencias externas más allá de Google Fonts (CDN permitido solo para fonts).
```

---

## PROMPT 2 — Panel Operador (la que ve la persona que opera la presentación)

```
Diseñá un único archivo HTML autocontenido (HTML + CSS + JS inline, sin frameworks ni build tools, podés usar CDN para Google Fonts) para el PANEL DE CONTROL de un operador de presentación de iglesia evangélica. Esta pantalla la ve UNA persona en su notebook mientras controla qué se muestra en la pantalla gigante del culto.

CONTEXTO:
- Operador típico: voluntario autodidacta, no técnico avanzado, presión de tiempo durante el culto
- Tiene que poder buscar versículos rápido, lanzar letras de canciones línea por línea, ver estado del sistema
- Debe verse profesional para impresionar al equipo de medios el primer día
- Se usa principalmente en notebook 13"-15", también responsive a tablet

REQUISITOS DE DISEÑO:
- Dark mode (el operador trabaja en penumbra durante el culto)
- Layout 2 columnas en desktop: izquierda controles + estado (320px), derecha listas de contenido (flexible). En mobile/tablet, 1 columna apilada
- Densidad visual ALTA — el operador necesita ver mucho a la vez sin scrollear
- Tipografía: clean sans-serif (Inter / Plus Jakarta Sans / Geist). Tamaños chicos pero legibles
- Paleta: oscura profesional. Sugerencia: fondo #0f172a, cards #1e293b, bordes #334155, acento principal #06b6d4 (cyan), acento warning #f59e0b (amber), peligro #ef4444
- Cards con bordes finos, hover sutil, no glassmorphism exagerado
- Buena jerarquía visual: estado del sistema arriba, vista previa a la derecha, demo de "simular Pastor" abajo
- Botones grandes y táctiles (mínimo 40px alto), feedback visual en click

SECCIONES NECESARIAS (NO modificar la lógica, solo visualizar mejor):

1. **CARD ESTADO DEL SISTEMA** (top izquierda): 4 indicadores con dots verde/rojo:
   - Gemma 4 (Ollama) conectado
   - Freeshow conectado
   - Pantalla pública conectada
   - Badge "DEMO" (amarillo) o "LIVE" (verde) según estado completo
   - Línea con modelo activo (ej "gemma4:4b") + link a la pantalla pública

2. **CARD VISTA PREVIA** (debajo del estado): mini-versión 16:9 de lo que se está mostrando ahora en la pantalla pública. Debe sincronizarse con el WebSocket. Botón "Limpiar pantalla" debajo.

3. **CARD DEMO SIMULAR PASTOR** (abajo izquierda, destacada con borde amber): input de texto + botón "Detectar y mostrar" + 4 botones rápidos de ejemplo ("Juan 3:16", "Salmo 23:1", "Romanos 8:28", "Filipenses 4:13"). Debajo, área que muestra resultado de detección.

4. **CARD LISTA VERSÍCULOS** (columna derecha, arriba): scroll vertical con 12 items. Cada item: referencia en color acento + primeros 80 chars del texto. Click → ejecuta endpoint `/presentar/versiculo`. Hover suave.

5. **CARD LISTA CANCIONES** (columna derecha, abajo): cada canción es un acordeón colapsable. Click en título → expande/colapsa lista de líneas. Click en línea → muestra esa línea (resaltar la línea activa con color cyan). Líneas vacías ("") se muestran como "— pausa —" en cursiva grisada y NO son clickeables.

INTEGRACIÓN TÉCNICA OBLIGATORIA (NO modificar):

El panel se conecta a un backend FastAPI corriendo en el mismo origen.

Endpoints a usar:
- `GET /estado` → estado del sistema (cada 5s polling)
  Respuesta: { ollama_disponible: bool, freeshow_disponible: bool, publicos_conectados: int, modelo: string }

- `GET /datos/versiculos` → diccionario { "JN 3:16": { referencia: "Juan 3:16", texto: "...", version: "RV1960" }, ... }

- `GET /datos/canciones` → diccionario { "cuan-grande-es-el": { titulo: "Cuán grande es Él", autor: "...", letras: ["línea 1", "línea 2", "", "línea 4"] }, ... }

- `POST /presentar/versiculo` body { referencia: "JN 3:16" }

- `POST /presentar/letra` body { cancion_id: "cuan-grande-es-el", linea_index: 4 }

- `POST /presentar/limpiar` (sin body)

- `POST /demo/simular-pastor` body { texto: "Abramos en Juan 3:16" } → respuesta { deteccion: { referencia, versiculo_existe, metodo }, accion_tomada }

- WebSocket `ws://${location.host}/ws/operador` → recibe el estado actual de la pantalla en JSON. Mismo formato que la pantalla pública. Usar para actualizar la vista previa en vivo.

UX CRÍTICA:
- Atajos de teclado: barra espaciadora avanza la línea de canción actual; flecha derecha también; flecha izquierda retrocede; ESC limpia pantalla
- Si pierde conexión WebSocket, mostrar dot rojo en estado y reconectar automáticamente cada 2s
- Loading states sutiles cuando se hace fetch (no spinners gigantes)

ENTREGÁ: un solo bloque HTML autocontenido completo, listo para `operador.html`.
```

---

## Cómo usarlos

1. Abrí Claude.ai en el navegador → modo Artifact / Diseño
2. Pasá el **PROMPT 1** primero, esperá el HTML de la pantalla pública
3. Guardalo como `software/frontend/publico.html` (sobreescribiendo el actual)
4. Pasá el **PROMPT 2**, esperá el HTML del operador
5. Guardalo como `software/frontend/operador.html`
6. Probalo: `cd software && ./run.sh` → abrir `http://localhost:8000/` y `http://localhost:8000/publico` en otro tab/pantalla

## Si Claude Design rompe el contrato

Si el HTML que devuelve no usa exactamente los endpoints o el formato de WebSocket especificado, copiar el JS de los archivos actuales `publico.html` y `operador.html` (que ya conectan bien con el backend) y pegarlo dentro del HTML nuevo de Claude Design — solo se reemplaza la parte visual, no la lógica.
