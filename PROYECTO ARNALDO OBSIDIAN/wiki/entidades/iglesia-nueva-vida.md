---
title: "Iglesia Nueva Vida"
type: cliente-pro-bono
proyecto: arnaldo
tags: [iglesia, pro-bono, caso-de-estudio, sistema-presentacion, arnaldo, live]
---

# Iglesia Nueva Vida

## Descripción

Iglesia cristiana ubicada en la zona de **San Ignacio / Misiones, Argentina**. Cliente **pro-bono** de [[agencia-arnaldo-ayala]] — el trabajo se hace sin cobro a cambio de un caso de estudio + vínculo con el pastor para un posible servicio pago en redes sociales.

Canal de entrada: [[pablo-tome-pastor]] (pastor), amigo de Gastón Ayala (hermano de Arnaldo).

## Estado

| Item | Detalle |
|------|---------|
| **Contrato** | Pro-bono (sin pago) |
| **Demo presencial** | Sábado 2026-05-03 a las 10 AM |
| **Participantes demo** | Pastor Pablo + equipo de medios + TV |
| **Software** | v0.2 — LIVE en local, commiteado |
| **Datos cargados** | 12 versículos RV1960 + 8 canciones adoración latina (muestra) |
| **Datos reales** | Pendientes de aportar por el equipo (ver checklist) |

## Qué se construyó

**Sistema de presentación inteligente para cultos** — software completo que reemplaza el uso de PowerPoint/ProPresenter con capacidades de IA:

- Pantalla operador (laptop del técnico) sincronizada en tiempo real con pantalla pública (proyector)
- Versículos bíblicos: búsqueda por referencia o texto, detección automática cuando el pastor habla
- Letras de canciones: 4 modos de avance (Manual / Auto-timer / MP3 Karaoke / IA Whisper)
- Karaoke IA: la letra avanza sola siguiendo la voz en tiempo real (faster-whisper local)
- MP3 Karaoke: la iglesia graba su propia versión, el sistema sincroniza timestamps (formato LRC)
- Medios anexos: imágenes/videos hasta 2GB (upload streaming), se muestran entre canciones/cultos
- Pantalla pública Spotify-style: línea actual grande + degradado de líneas vecinas, Spectral font legible a 10m

## Stack técnico

```
Backend:   FastAPI + WebSocket
IA cloud:  Gemini 2.5 Flash (detección texto + audio, free tier 500 req/día)
IA local:  faster-whisper (model: small, transcripción offline)
Frontend:  HTML puro, JS vanilla, Plus Jakarta Sans / Spectral
Deploy:    localhost (demo local, sin hosting externo aún)
```

**Archivos del proyecto:**
- Software: `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/nuestra-iglesia/software/`
- Checklist cliente: `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/nuestra-iglesia/checklist-pendientes-iglesia.html`
- Brief discovery: `02_OPERACION_COMPARTIDA/handoff/brief-nuestra-iglesia.md`

**Playbook:** [[wiki/playbooks/sistema-presentacion-iglesia]]

## Lo que aporta la iglesia (post-demo)

1. **Versión bíblica** que usan (RV1960 / NVI / NTV / otra)
2. **Repertorio canciones** con letras completas (Word / PDF / app)
3. **Grabaciones MP3 propias** de cada canción (para karaoke LRC)
4. **Logo HD** (SVG/AI/EPS o PNG 1080x1080+ fondo transparente)
5. **Identidad visual** (colores oficiales, tipografía, lema/versículo distintivo)
6. **Material gráfico** (flyers, fotos, videos cortos para pantalla)
7. **Setup técnico** (PC operador, salidas HDMI, consola audio)
8. **Equipo de medios** (nombres, contactos, disponibilidad capacitación)

## Valor de negocio para Arnaldo

| Track | Descripción | Estado |
|-------|-------------|--------|
| A | Iglesia (pro-bono) — caso de estudio, aprendizaje técnico | En progreso |
| B | Redes sociales personales del Pastor Pablo — posible cliente pago | Lead caliente, post-demo |

## Equipo de medios (por descubrir)

A confirmarse en la reunión del sábado.

## Notas técnicas

- API key Gemini dedicada en `.env` local — **rotar después de la demo del sábado**
- Logo actual de muestra: `Iglesia Nueva Vida` con fondo blanco y destellos magenta
- La pantalla pública corre en `?demo` para ciclar automáticamente; sin el param, solo responde al operador
- Whisper local: latencia ~2-4s; validar en vivo con audio real antes del sábado
- Uploads: streaming 1MB chunks para soportar videos >500MB sin crashear
