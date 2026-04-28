---
title: Sesión 2026-04-27 — Grupo Back alcance cerrado (7 firmas, 5 bots, roadmap v4 LIVE)
date: 2026-04-27
source_path: raw/arnaldo/sesion-2026-04-27-grupo-back-confirmacion.md
type: sesion-claude
proyecto: arnaldo
tags: [grupo-back, alcance-cerrado, multi-marca, roadmap, mapa-visual, 5-bots, wordpress, n8n]
---

# Sesión 2026-04-27 — Grupo Back alcance cerrado

## Resumen

Sesión extensa (mañana + tarde) que comenzó con la confirmación de Patricia Back (vía Hernán) sobre la hoja de ruta inicial, y terminó con el **alcance final cerrado en 7 firmas** y el roadmap v4 publicado y LIVE con mapa visual SVG embebido. Se tomaron decisiones arquitectónicas clave y se grabaron 4 reglas nuevas irrompibles en la memoria del ecosistema.

## Sesión matutina (09:03–12:00)

### Eventos
- Hernán Weninger contacta por primera vez directamente a Arnaldo (09:03)
- Patricia confirma la hoja de ruta vía Hernán: *"Me comentó que sí. Que te de la confirmación y empezamos a ver los detalles"* (09:39)
- Audio de Hernán (09:47): *"Sí, el 90% está bien, lo que sí es que vamos a agregar... creo que llegarían a ser seis."*
- Arnaldo pide cerrar alcance antes de codear (09:52): *"la idea es que me confirmen bien cual nicho exactos van a ser"*

### Acciones tomadas (mañana)
- Ingesta inicial a wiki: entidades [[grupo-back]], [[patricia-back]], [[hernan-weninger]]
- Hoja de ruta v1 existente en `clientes-publicos/patricia-back/roadmap.html` identificada como publicada desde 2022-04-22
- Checklist rellenable HTML para la reunión presencial: `clientes/patricia-back/checklist-reunion-2026-04-27.html`
- Feedback grabado: cláusula tratamiento de datos = argumento de venta

## Sesión vespertina (14:30–18:30)

### Reunión presencial en La Misionerita (14:30)

Hernán propuso reunirse en La Misionerita ("para mí es más fácil hacerlo en persona"). Arnaldo fue desde San Ignacio. En esa reunión se cerró el alcance final:

**Las 7 firmas definitivas:**

| # | Marca | Rubro | Bot |
|---|-------|-------|-----|
| 1 | Rizoma Propiedades | Inmo multi-vertical (ventas, alquileres, obras, tasaciones judiciales, asesorías) | ✅ |
| 2 | La Misionerita | Restaurant + parador turístico (contingentes colectivos, reservas, carta online) | ✅ |
| 3 | Patricio's | Resto-bar + eventos (alquiler salón, catering) | ✅ |
| 4 | La Martina Apart Hotel | Hospedaje San Ignacio | ✅ |
| 5 | Bocanada | Panadería / Pastelería (pedidos personalizados) | ✅ |
| 6 | Club Progreso | Blog informativo fútbol | ❌ |
| 7 | Fundación Misión Emprender | Blog + calendario cursos/talleres | ❌ |

**Decisiones arquitectónicas confirmadas:**
- **5 bots WhatsApp separados** — 1 número por servicio (no un único bot multi-rubro)
- **Dominio**: `grupoback.com` (disponible, a Hernán le gusta, pendiente OK Patricia)
- **Estrategia secuencial**: una firma por vez, ~5-10 días total el ecosistema completo
- **Stack entregado al cliente**: WordPress (web) + VPS (servidor) + n8n (automatizaciones) + Coolify (bots/CRM) + Airtable (BD central) + capas de seguridad

### Roadmap v2 → v3 → v4 publicado

Commits al repo `system-ia-agentes`:

| Commit | Cambio |
|--------|--------|
| `f864f33` | Roadmap v2: 7 firmas reales, herramientas, tiempos 5-10 días |
| `54f8e57` | Mapa visual SVG (2 vistas) + n8n como bloque propio en herramientas |
| `dae0ece` | Footer firma `arnaldoayalaestratega.com`, 5 bots confirmados en badges y SVG |

URL LIVE: `https://agentes.arnaldoayalaestratega.cloud/propuestas/patricia-back/roadmap.html`

Cada versión verificada con `curl` + grep de marcadores clave antes de reportar LIVE.

### Mapa visual SVG — pedido de Hernán

Hernán pidió "un mapa visual de cómo se va a conectar todo el ecosistema". Se implementó como SVG inline en el roadmap (sin dependencias externas):

- **Vista 1 — Capas**: cliente final → 3 canales → infra+seguridad (VPS+n8n+Coolify+WordPress) → Airtable → CRM equipo
- **Vista 2 — Multi-marca**: 7 firmas en círculo alrededor de núcleo central (Airtable + n8n + Coolify + seguridad + "Ficha única cross-marca")

### 4 reglas nuevas irrompibles grabadas en memoria

1. **No mencionar otros clientes en docs cliente-facing** (`feedback_REGLA_doc_cliente_facing_no_mencionar_otros.md`) — Caso: roadmap tenía "replicamos modelo de otro cliente inmobiliario"
2. **Eliminar archivos obsoletos al reemplazar** (`feedback_REGLA_eliminar_archivos_obsoletos.md`) — Caso: `roadmap.html` local v2 + publicado v1 en paralelo durante días
3. **Footer cliente-facing firma con `arnaldoayalaestratega.com`** (`feedback_REGLA_dominio_firma_cliente_facing.md`) — Caso: todos los docs firmaban con `.cloud` (backend técnico, no marca pública)
4. **Cláusula tratamiento datos = argumento de venta** (`feedback_clausula_tratamiento_datos_es_argumento_venta.md`) — Caso: objeción "¿qué hacés con mis datos?" ya apareció en prospectos en tono irónico

## Ideas clave

1. **Primer cliente multi-marca del ecosistema Arnaldo** — si sale bien, queda como template para grupos empresariales futuros.
2. **Ficha única cross-marca** es el diferenciador técnico central: si un cliente de Rizoma también reserva en Misionerita, el sistema lo reconoce como la misma persona.
3. **5 bots separados** > 1 bot multi-rubro: cada marca mantiene identidad propia, mejor UX para el cliente final.
4. **Tiempos reales 5-10 días** con infraestructura pre-construida — no semanas como en clientes sin base.
5. **Patricia tiende a expandir alcance** — de 3 a 7 sin que se le ofreciera. Cerrar contractualmente.
6. **n8n es el motor de conexión** de todo el ecosistema — aunque el cliente no lo vea, conecta WhatsApp → Airtable → Cal.com → CRM.

## Entidades mencionadas

- [[grupo-back]] (actualizada: alcance cerrado)
- [[patricia-back]] (actualizada: estado alcance-cerrado)
- [[hernan-weninger]] (actualizada: reunión presencial, rol expandido)
- [[arnaldo-ayala]]
- [[agencia-arnaldo-ayala]]
- [[maicol]] — referencia técnica interna (NO mencionada en docs cliente-facing)

## Conceptos relacionados

- Bot WhatsApp dedicado por marca (nuevo patrón en ecosistema Arnaldo)
- Mapa visual SVG inline en roadmap (nuevo patrón de presentación)
- Footer con firma de marca en docs cliente-facing

## Fuentes citadas

- `raw/arnaldo/sesion-2026-04-27-grupo-back-confirmacion.md`
- Repo `system-ia-agentes` commits f864f33, 54f8e57, dae0ece
