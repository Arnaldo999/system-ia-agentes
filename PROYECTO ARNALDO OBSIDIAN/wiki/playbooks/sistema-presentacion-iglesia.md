---
name: sistema-presentacion-iglesia
description: Patrón reutilizable para construir sistemas de presentación inteligente para cultos/iglesias. FastAPI + Gemini cloud + Whisper local + WebSocket sync. 4 modos de avance de letras.
type: playbook
proyecto: arnaldo
tags: [playbook, iglesia, sistema-presentacion, fastapi, gemini, whisper, karaoke, websocket]
version: v1
ultima_actualizacion: 2026-04-27
caso_base: nuestra-iglesia (Iglesia Nueva Vida, 2026-04-26)
---

# Playbook — Sistema de Presentación Inteligente para Iglesias

> **Qué construye**: software completo para reemplazar PowerPoint/ProPresenter en cultos. Pantalla operador + pantalla proyector sincronizadas en tiempo real, con detección automática por IA de qué se está predicando o cantando.

## Cuándo usar este playbook

- Cliente es iglesia o ministerio
- Necesitan proyectar versículos bíblicos y letras de canciones en pantalla gigante
- Quieren que el sistema avance las letras solo (sin operador tecleando)
- El técnico de medios tiene nivel básico — el sistema debe ser simple

## Stack estándar

```
Backend:   FastAPI + Python 3.11+ + WebSocket (broadcast sync)
IA cloud:  Gemini 2.5 Flash (detección texto + audio multimodal)
           → modelo: gemini-2.5-flash | free tier: 500 req/día (suficiente para culto semanal)
IA local:  faster-whisper (model: small, offline, transcripción en tiempo real)
           → instalar con: pip install faster-whisper
Frontend:  HTML puro + CSS vars + JS vanilla (sin frameworks)
           → operador: 3 columnas, controles táctiles
           → público: full-screen, Spectral font, Spotify-style lyrics
Datos:     JSON files (versiculos.json, canciones.json, data/timings/*.json)
```

### Por qué Gemini cloud y NO modelo local

| Factor | Gemini cloud | Ollama/Gemma local |
|--------|-------------|-------------------|
| Instalación en PC operador | Ninguna | Runtime + modelo (3-8GB) |
| Soporte técnico futuro | Cero | Actualizaciones manuales |
| Free tier | 500 req/día | Ilimitado local |
| Privacidad datos | Sube audio a Google | 100% local |
| Veredicto | ✅ Default | Solo si la iglesia exige privacidad absoluta |

## Arquitectura de pantallas

```
[PC Operador] ←→ FastAPI WS ←→ [Proyector pantalla gigante]
      │                              │
  operador.html               publico.html
  (controles)                 (fullscreen display)
```

WebSocket paths:
- `/ws/operador` — operador envía comandos → broadcast
- `/ws/publico` — pantalla recibe y renderiza

Estado de reconexión disponible en `GET /estado`.

## 4 modos de avance de letras

| Modo | Cómo funciona | Cuándo usar |
|------|--------------|------------|
| **Manual** | Operador presiona botón/flecha | Control total, congregaciones variables |
| **Auto-timer** | Avanza cada N segundos configurables | Canciones lentas, operador ausente |
| **MP3 LRC Karaoke** | MP3 mudo como metrónomo + timestamps JSON | La iglesia grabó su versión propia |
| **IA Whisper** | Micrófono en vivo → transcribe → Gemini decide avance | Experimental, latencia 2-4s |

**Recomendación**: demo con Manual, luego enseñar Auto-timer, ofrecer Karaoke como "upgrade".

## Datos de muestra para demos

Cargar al arrancar para no llegar con sistema vacío:
- **12 versículos RV1960**: Juan 3:16, Salmo 23:1, 23:4, Romanos 8:28, Filipenses 4:13, Proverbios 3:5, Jeremías 29:11, Mateo 6:33, 1 Corintios 13:4, Efesios 2:8, Salmo 91:1, Isaías 41:10
- **8 canciones adoración latina**: Cuán Grande es Él, Mi Amor es Jesús, Renuévame Señor Jesús, Te Doy Gloria, Al Que Está Sentado en el Trono, Tu Fidelidad es Grande, El Poderoso de Israel, Santo Santo Santo

## Diseño pantalla pública (Spotify-style)

```css
/* Contenedor con fade top/bottom */
.lines-stack {
  mask-image: linear-gradient(transparent 0%, black 15%, black 85%, transparent 100%);
}

/* Línea actual: grande, bold, glow */
.line.current { font-size: 4.5cqw; font-weight: 700; color: #f5e6c8; text-shadow: glow-dorado; }

/* Líneas vecinas: fade de opacidad */
.line.near    { opacity: 0.40; }
.line.far     { opacity: 0.18; }
```

**Font**: Spectral (peso 500, no italic). NO usar Cormorant Garamond italic — ilegible a 10m.

**Container queries** (`cqw`) para que el texto escale con el iframe de preview del operador.

## Gotchas conocidos

### 1. Timer global en pantalla pública
Si el HTML de `publico.html` tiene un `setInterval` para demo, envuelve en `if (urlParams.get('demo'))`. De lo contrario el timer pisa los comandos del operador.

```js
const forceDemo = new URLSearchParams(window.location.search).has('demo');
if (forceDemo) { setInterval(ciclaDemoVersiculos, 3500); }
```

### 2. Upload de videos grandes: NO usar `await archivo.read()`
Para videos > 500MB crashea con OOM. Usar streaming:

```python
async with aiofiles.open(ruta, 'wb') as f:
    async for chunk in archivo.chunks(1024 * 1024):  # 1MB chunks
        await f.write(chunk)
```

### 3. Font cursiva ilegible a distancia
- ❌ Cormorant Garamond italic — elegante pero ilegible a 10m en pantalla gigante
- ✅ Spectral peso 500, sin italic — excelente legibilidad, tono litúrgico

### 4. Logo magenta/transparente en fondo oscuro
Si el logo tiene fondo transparente y la iglesia tiene identidad rosa/magenta, se pierde en el dark background del proyector. Solución: caja blanca con glow:

```css
.brand-logo-wrap {
  background: white;
  border-radius: 12px;
  box-shadow: 0 0 24px rgba(194, 24, 91, 0.4);
  padding: 8px;
}
```

### 5. em-dash en strings bloquea Edit tool de Claude
Si el código tiene `—` (em-dash) en comentarios, el Edit tool no puede hacer match de `old_string`. Workaround: editar via `python3 -c "..."` con regex por Bash.

### 6. Puerto uvicorn ocupado por instancia anterior
```bash
pkill -9 -f "uvicorn"       # matar todas las instancias
ss -tlnp | grep 8000        # verificar que el puerto esté libre
uvicorn main:app --reload   # reiniciar
```

### 7. Karaoke Whisper: filtros estrictos para evitar falsos avances
```python
MIN_PALABRAS = 3
SCORE_MIN    = 0.5
DIFF_MIN     = 0.2   # diferencia vs línea actual para auto-avanzar
RETROCESO_SCORE = 0.7  # threshold para permitir retroceder
```

Sin estos filtros el sistema salta líneas al azar cuando el audio es ambiguo.

### 8. Gemini 2.0 Flash deprecado
- Modelo correcto: `gemini-2.5-flash` (a partir de 2026)
- Gemini 2.0 Flash se depreca en junio 2026
- Verificar `GEMINI_MODEL` en `.env` antes de cada deploy nuevo

## Checklist de activos que la iglesia debe proveer

1. Versión bíblica (RV1960 / NVI / NTV / otra) + archivo digital si tienen
2. Repertorio canciones con letras completas (Word / PDF / app)
3. Grabaciones MP3 propias de cada canción (consola USB o celular cerca del altavoz)
4. Logo en alta resolución (SVG/AI/EPS o PNG 1080x1080+ fondo transparente)
5. Identidad visual (colores, tipografía, lema/versículo)
6. Material gráfico (flyers, fotos, videos cortos para entre cantos)
7. Setup técnico (PC operador modelo + OS, salidas HDMI, consola audio)
8. Equipo de medios (nombres, contactos, disponibilidad capacitación)

## Estructura de archivos del proyecto

```
clientes/[nombre-iglesia]/
├── checklist-pendientes-iglesia.html   ← imprimible para entregar al equipo
└── software/
    ├── backend/
    │   └── main.py                     ← FastAPI + todos los endpoints
    ├── frontend/
    │   ├── operador.html               ← panel del técnico de medios
    │   └── publico.html                ← pantalla proyector full-screen
    ├── data/
    │   ├── versiculos.json             ← versículos en formato {id, referencia, texto, libro}
    │   ├── canciones.json              ← canciones en formato {id, titulo, autor, estrofas:[]}
    │   └── timings/
    │       └── {cancion_id}.json       ← timestamps LRC por canción
    ├── uploads/                        ← imágenes/videos (gitignored)
    ├── .env                            ← GEMINI_API_KEY (gitignored)
    ├── .env.example                    ← template commiteado
    ├── requirements.txt
    └── run.sh
```

## Endpoints clave del backend

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/estado` | GET | Estado actual del sistema (para reconexión WS) |
| `/datos/versiculos` | GET | Lista todos los versículos |
| `/datos/canciones` | GET | Lista todas las canciones |
| `/presentar/versiculo` | POST | Muestra versículo en pantalla |
| `/presentar/letra` | POST | Muestra línea de canción `{cancion_id, linea_idx}` |
| `/presentar/limpiar` | POST | Pantalla en blanco (idle logo) |
| `/presentar/media` | POST | Muestra imagen/video en pantalla |
| `/detectar/texto` | POST | Detecta referencia bíblica en texto libre (heurística + Gemini) |
| `/detectar/audio` | POST | Detección multimodal en audio (Gemini) |
| `/media/subir` | POST | Upload streaming de imagen/video |
| `/cancion/{id}/timing` | GET/POST/DELETE | Gestión de timestamps LRC |
| `/transcribir/whisper` | POST | Transcripción local offline |
| `/ws/operador` | WS | WebSocket del operador (comandos broadcast) |
| `/ws/publico` | WS | WebSocket de la pantalla pública (recibe comandos) |

## Capacitación al equipo de medios

Duración estimada: 1 hora.

1. Abrir el sistema (run.sh) y las dos URLs
2. Modo Manual: presentar versículo + avanzar letras
3. Modo Auto-timer: configurar segundos, activar
4. Modo MP3 Karaoke: subir MP3, grabar timestamps con SPACE, reproducir
5. Medios anexos: subir imagen/video, mostrar en pantalla
6. Emergencias: si se congela, F5 en publico.html; si el servidor cae, correr run.sh

## Histórico de descubrimientos

### 2026-04-26 (Caso base: Iglesia Nueva Vida)
- Gemini cloud > Ollama local para iglesias (sin soporte técnico propio)
- Whisper solo transcribe; Gemini cloud decide la intención — stack más limpio
- Modo Karaoke MP3 es el de mejor UX para uso regular (la iglesia graba su versión propia)
- Lección: el operador NECESITA 3 modos disponibles — las congregaciones varían mucho en ritmo
- Bug clásico: timer global en HTML de demo → siempre envolver en `?demo` param
- Font: Spectral >> Cormorant Garamond para legibilidad a distancia
