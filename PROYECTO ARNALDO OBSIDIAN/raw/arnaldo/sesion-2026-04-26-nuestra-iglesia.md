---
title: "Sesión 2026-04-26 — Construcción Sistema Presentación Iglesia Nueva Vida"
date: 2026-04-26
source_path: raw/arnaldo/sesion-2026-04-26-nuestra-iglesia.md
type: sesion-claude
proyecto: arnaldo
tags: [iglesia, sistema-presentacion, fastapi, gemini, whisper, karaoke, pro-bono]
---

# Sesión 2026-04-26 — Sistema Presentación Iglesia Nueva Vida

## Contexto

Arnaldo conversó con Pastor Pablo (amigo de Gastón, hermano de Arnaldo) sobre una reunión el sábado 2026-05-03 a las 10 AM con el equipo de medios de Iglesia Nueva Vida. En esa reunión hay que llevar una demo del sistema.

El sistema surge de la idea de reemplazar PowerPoint/ProPresenter con algo inteligente: IA que detecta qué se está predicando/cantando y sincroniza la pantalla gigante automáticamente.

## Decisiones arquitectónicas tomadas

### Gemma 4 local vs Gemini cloud

Arnaldo consideró usar Gemma 4 (modelo local, recién lanzado). Evaluación:
- Gemma 4 = modelo de pesos, necesita runtime (Ollama/LM Studio) — instalación en PC del operador
- Gemini cloud = sin instalación, free tier 500 req/día sobra para culto semanal, cero soporte futuro
- **Decisión**: Gemini cloud gana porque la iglesia no tiene capacidad técnica de mantener Ollama

### Whisper: acotado a transcripción, NO a lógica

- faster-whisper local (model: small, offline) = transcribe con buena precisión
- La "intención" (¿está cantando estrofa 1 o coro?) la decide Gemini con la transcripción
- **Decisión**: Whisper solo transcribe → texto → Gemini decide → avance de línea
- Stack más limpio, latencia manejable (~2-4s)

### Karaoke con MP3 propio de la iglesia

- Problema: Whisper en vivo tiene latencia 2-4s, voces simultáneas confunden, música tapa voz
- Solución: la iglesia graba su propia versión de cada canción → sistema genera timestamps LRC → letras avanzan sincronizadas con MP3 mudo como metrónomo
- **Ventaja**: timing exacto, sin latencia, sin falsos positivos
- Modo LRC aprendizaje: operador toca SPACE al inicio de cada línea → sistema guarda timestamps

### 4 modos de avance seleccionables

Se decidió no imponer un modo único — cada iglesia tiene preferencias distintas:
1. **Manual** (flechas / click) — máximo control
2. **Auto-timer** (avanza cada N segundos) — simple para congregaciones lentas
3. **MP3 LRC Karaoke** — MP3 propio de la iglesia + timestamps LRC pregunados
4. **IA Whisper** — detección en vivo con micrófono (experimental)

## Bugs encontrados y solucionados

### Timer global en pantalla pública pisaba operador
- `setInterval` en `publico.html` ciclaba versículos cada 3.5s automáticamente
- Fix: envuelto en `if (forceDemo)` — solo activa con `?demo` en URL
- Lección: siempre revisar timers globales en HTMLs antes de integrar

### Upload de archivos grandes crasheaba con RAM
- `await archivo.read()` cargaba todo el MP4 en memoria → crash para videos >500MB
- Fix: streaming chunks de 1MB escritos directamente a disco
- Pattern: `async for chunk in archivo.chunks(1024*1024): f.write(chunk)`

### Font Cormorant Garamond cursiva ilegible a distancia
- Cormorant Garamond italic = elegante pero ilegible a 10m en pantalla gigante
- Reemplazada por Spectral peso 500 (serif legible, sin italic, excelente a distancia)

### Logo invisible en dark mode
- Logo transparente de la iglesia se perdía en fondo oscuro
- Fix: `.brand-logo-wrap` con caja blanca + sombra magenta (patrón reutilizable para clientes con logo rosa/magenta)
- Luego el usuario envió foto del logo con fondo blanco — se usó directamente

### em-dash en comentarios bloqueaba Edit tool
- Líneas con `—` (em-dash) en comentarios del código impedían que `old_string` del Edit tool hiciera match
- Workaround: usar Python regex via Bash para editar esas líneas

### Múltiples instancias uvicorn en mismo puerto
- Patrón correcto: `pkill -9 -f "uvicorn"` → verificar `ss -tlnp` → reiniciar

## Modelo Gemini

- Arnaldo aclaró que Gemini 2.0 Flash está siendo deprecado en junio 2026
- **Usar: `gemini-2.5-flash`** para todos los proyectos que usen Gemini cloud
- API key dedicada para Iglesia Nueva Vida: creada y cargada en `.env` local
- PENDIENTE: rotar la key después de la demo del sábado (fue compartida por chat)

## Datos de muestra cargados

- 12 versículos RV1960: Juan 3:16, Salmo 23:1, Salmo 23:4, Romanos 8:28, Filipenses 4:13, Proverbios 3:5, Jeremías 29:11, Mateo 6:33, 1 Corintios 13:4, Efesios 2:8, Salmo 91:1, Isaías 41:10
- 8 canciones adoración latina: Cuán Grande es Él, Mi Amor es Jesús, Renuévame Señor Jesús, Te Doy Gloria, Al Que Está Sentado en el Trono, Tu Fidelidad es Grande, El Poderoso de Israel, Santo Santo Santo

## Pantalla pública — diseño Spotify

- `lines-stack`: contenedor con `mask-image` fade top/bottom para sensación de profundidad
- `.current`: línea grande, peso 700, glow dorado pulsante
- `.near` (offset 1-2): 40% opacidad, ligeramente desplazada
- `.far` (offset 3+): 18% opacidad

## Sincronización WebSocket

- `/ws/operador`: operador envía comandos → broadcast a todos los clientes
- `/ws/publico`: pantalla proyector recibe y renderiza
- Estado del sistema en `/estado` (REST) para reconexión

## Próximos pasos post-sesión

1. Demo presencial sábado 2026-05-03 10 AM con Pastor Pablo + equipo medios
2. Validar Whisper end-to-end con audio real antes del sábado
3. Recopilar checklist de la iglesia (versión bíblica, canciones, MP3, logo HD)
4. Rotar API key Gemini post-demo
5. Post-demo: evaluar Track B (redes sociales personales de Pablo)
