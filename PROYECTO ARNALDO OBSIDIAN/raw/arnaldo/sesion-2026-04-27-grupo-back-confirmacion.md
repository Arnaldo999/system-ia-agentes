---
title: Sesión 2026-04-27 — Confirmación Grupo Back + expansión a 6 marcas
date: 2026-04-27
source_path: raw/arnaldo/sesion-2026-04-27-grupo-back-confirmacion.md
type: sesion-claude
proyecto: arnaldo
tags: [grupo-back, patricia-back, hernan-weninger, descubrimiento, multi-marca, confirmacion-roadmap]
---

# Sesión 2026-04-27 — Grupo Back confirma + expande a 6 marcas

## Contexto

Hace varios días Arnaldo tuvo una reunión con [[patricia-back]] (dueña de Grupo Back, Posadas) donde se discutió la idea de un ecosistema digital unificado para el grupo. Como salida de esa reunión, Arnaldo armó y entregó la **Hoja de Ruta** (publicada en `backends/system-ia-agentes/clientes-publicos/patricia-back/roadmap.html` → URL pública `agentes.arnaldoayalaestratega.cloud/propuestas/patricia-back/roadmap.html`) describiendo:

- Las 3 marcas iniciales: Patricios (eventos), Inmobiliaria Back (real estate), La Misionerita (gastro+turismo)
- Las 4 piezas del ecosistema: sitio web multi-marca, bot WhatsApp único multi-rubro, CRM con sidebar, Cal.com multi-evento
- 6 fases de construcción
- Lista de inputs necesarios del cliente

## Eventos del 2026-04-27

### 09:03 — Hernán saluda

> *"Hola Arnaldo, Buenos días. Te saluda Hernán Weninger, estaba en la reunión del otro día con Patricia"*

Primera vez que Hernán contacta a Arnaldo directamente. Antes el canal era directo Patricia ↔ Arnaldo.

### 09:31-09:32 — Arnaldo intenta cerrar con Patricia

Arnaldo iba a escribirle a Patricia justo, así que aprovecha y le pregunta a Hernán si llegaron a alguna decisión sobre la hoja de ruta enviada.

### 09:39-09:40 — Hernán confirma el OK de Patricia

> *"Si me la envió. Me comentó que sí. Que te de la confirmación y empezamos a ver los detalles."*

✅ Patricia confirma la hoja de ruta. Pasamos a Fase 1 — Descubrimiento.

### 09:46 — Arnaldo pregunta detalles

> *"ok ok dale, com te pareció la hoja de Ruta, es asi como quieren?"*

### 09:47 — Audio de Hernán (transcrito por él con IA)

> *"Hola Arnaldo, ¿cómo estás? Sí, el 90% está bien, lo que sí es que vamos a agregar no solamente tres, digamos tres empresas, sino vamos a agregar más. Creo que llegarían a ser seis."*

🚨 **Cambio de alcance importante**: pasan de **3 marcas → 6 marcas**.

### 09:52 — Arnaldo pide cerrar alcance antes de avanzar

> *"la idea es que me confirmen bien cual nicho exactos van a ser, así organizo el Proyecto bien estructurado y los nombres exactos de las Firmas que van a ir dentro del Grupo Back"*

## Decisiones tomadas en esta sesión (con Claude Code)

1. **No actualizar el roadmap.html ni armar plan técnico todavía**. Esperar a que Hernán y Patricia confirmen las 3 firmas nuevas con nombre + nicho exacto.

2. **Orden acordado** del flujo de cierre:
   - Hernán/Patricia definen las 6 firmas + nichos + nombre del Grupo
   - Arnaldo cotiza con su Cotizador (path por confirmar — no documentado todavía dónde vive)
   - Se arma Contrato con cláusula de tratamiento de datos (aislamiento físico, propiedad de datos, confidencialidad, Ley 25.326, backups)
   - Patricia firma + paga implementación
   - Recién ahí: `/crear-plan` técnico + arrancar Fase 1

3. **Ingesta a wiki anticipada** (esta sesión) — crear entidades [[grupo-back]], [[patricia-back]], [[hernan-weninger]] para que cualquier sesión futura tenga contexto cargado sin tener que reconstruirlo.

## Pendientes con el cliente

- ⏳ Hernán confirma las 3 firmas nuevas (nombre + nicho + estructura legal)
- ⏳ Hernán confirma el nombre definitivo del paraguas ("Grupo Back" es placeholder)
- ⏳ Patricia confirma estructura legal/comercial: ¿1 CUIT o varios? ¿"Grupo Back" es razón social o solo marca?
- ⏳ Confirmar si el WhatsApp es único para las 6 firmas o algunas necesitan número propio
- ⏳ Confirmar prioridad: ¿qué marca arranca primero?

## Pendientes con Arnaldo (lado nuestro)

- ⏳ Arnaldo me pasa el path/herramienta del Cotizador para que la próxima sesión la lea
- ⏳ Arnaldo me confirma exactamente qué cláusulas de tratamiento de datos entrarán en el contrato
- ⏳ Cuando llegue info de las 6 firmas: actualizar `roadmap.html` + `wiki/entidades/grupo-back.md`
- ⏳ Cuando se cierre alcance: armar plan técnico formal con `/crear-plan`

## Reflexión / aprendizaje (mañana)

- Es el **primer cliente multi-marca/multi-rubro** del ecosistema Arnaldo. Todo lo que aprendamos acá queda como template para futuros grupos empresariales.
- Patricia tiene tendencia a **expandir el alcance** — pasó de 3 a 6 sin que se le ofreciera. Atender que puede seguir creciendo y **cerrar contractualmente** el alcance.

## Entidades creadas/actualizadas (mañana)

- ✨ Nueva: [[grupo-back]]
- ✨ Nueva: [[patricia-back]]
- ✨ Nueva: [[hernan-weninger]]

---

# SESIÓN VESPERTINA — 2026-04-27 (14:30–18:30)

## Reunión presencial en La Misionerita

Hernán propuso reunirse presencialmente: *"para mí es más fácil hacerlo en persona y así lo vamos resolviendo y armamos todito rapidito"*. Arnaldo viajó desde San Ignacio.

En esa reunión se cerró el **alcance final** del proyecto.

## Alcance final cerrado

**7 firmas definitivas:**

1. **Rizoma Propiedades** — inmo multi-vertical: venta lotes/terrenos/casas, obras y loteos, alquileres casas/habitaciones/deptos, tasaciones judiciales, asesorías, estados contables. Toda Misiones. Bot ✅
2. **La Misionerita** — restaurant + parador turístico. Comidas, menús personalizados, contingentes colectivos, reservas, carta online. Bot ✅
3. **Patricio's** — resto-bar + eventos. Alquiler salones para fiestas, carta online, reservas, catering. Bot ✅ (alcance acotado: solo alquiler salón)
4. **La Martina Apart Hotel** — hospedaje en San Ignacio, reservas y alquiler deptos. Bot ✅
5. **Bocanada** — panadería/pastelería. Pedidos personalizados: panificados, confitería, catering, milanesas. Bot ✅
6. **Club Progreso** — blog informativo club de fútbol por categorías. Bot ❌
7. **Fundación Misión Emprender** — blog + grilla calendario cursos y talleres. Bot ❌

**5 bots WhatsApp** — 1 número dedicado por servicio. Decisión de Patricia/Hernán.

**Dominio propuesto**: `grupoback.com` (a Hernán le gusta, disponible, pendiente OK Patricia).

## Decisiones arquitectónicas tomadas en esta sesión

- **Bots separados** (no único multi-rubro): cada marca con su propio número WhatsApp, prompt y razonamiento
- **Airtable** como BD (no PostgreSQL): velocidad de desarrollo, Patricia/Hernán pueden cargar contenido sin panel propio
- **Estrategia secuencial**: 1 firma por vez, tiempos reales de **5 a 10 días total** el ecosistema completo
- **Stack entregado al cliente**: WordPress (sitio + dominio + hosting) + VPS (servidor privado) + n8n (motor de automatizaciones) + Coolify (bots/CRM/servicios) + Airtable (BD central) + capas de seguridad (HTTPS, tokens, backups diarios)

## Roadmap: de v1 → v4 en una tarde

| Versión | Qué cambió | Commit |
|---------|-----------|--------|
| v1 (original, 22/04) | 3 marcas, hoja de ruta inicial | `15abadf` |
| v2 | 7 firmas reales, herramientas, tiempos 5-10d | `f864f33` |
| v3 | Mapa visual SVG (2 vistas), n8n bloque propio | `54f8e57` |
| v4 | Footer `arnaldoayalaestratega.com`, 5 bots badges activos | `dae0ece` |

URL LIVE: `https://agentes.arnaldoayalaestratega.cloud/propuestas/patricia-back/roadmap.html`

## Mapa visual SVG (pedido de Hernán)

Hernán pidió visualización de cómo se conecta el ecosistema. Se implementó como SVG inline:

**Vista 1 — Capas** (flujo de información):
- Capa 1: 👤 Cliente final
- Capa 2: 🌐 Web + 💬 WhatsApp 1nº/bot + 📅 Cal.com
- Capa 3: 🛡️ Seguridad (VPS + 🔄 n8n + ⚙️ Coolify + 🌐 WordPress)
- Capa 4: 📊 Airtable — base central
- Capa 5: Equipo Grupo Back / CRM

**Vista 2 — Multi-marca** (7 firmas en círculo):
- Núcleo morado central: Airtable + n8n + Coolify + capas seguridad + "Ficha única cross-marca"
- 7 firmas alrededor con color/emoji propio

## Reglas nuevas grabadas en memoria del ecosistema

1. **No mencionar otros clientes en docs cliente-facing** — roadmap tenía "replicamos modelo de otro cliente inmobiliario"
2. **Eliminar archivos obsoletos al reemplazar** — `roadmap.html` local v2 + publicado v1 en paralelo durante días → Patricia veía la versión vieja
3. **Footer = `arnaldoayalaestratega.com`** — todos los docs firmaban con `.cloud` (backend técnico). Patrón: `clientes-publicos/{slug}/` = fuente única
4. **Cláusula tratamiento datos = argumento de venta** — objeción "¿qué hacés con mis datos?" ya apareció en prospectos en tono irónico

## Estado al cierre de la sesión

- ✅ Alcance cerrado: 7 firmas, 5 bots, dominio propuesto, stack definido
- ✅ Roadmap v4 LIVE con mapa visual
- ✅ Plan formal en `02_OPERACION_COMPARTIDA/planes/2026-04-27-grupo-back-ecosistema.md`
- ✅ Wiki, memoria y plan sincronizados
- ✅ Commit de docs en Mission Control
- ⏳ Patricia confirma dominio + estructura legal + 5 números WhatsApp
- ⏳ Cotizador n8n → cotización oficial
- ⏳ Contrato → firma → arranque Rizoma (~2 días)

## Relaciones con otras sesiones / fuentes

- Continuidad directa de la sesión matutina (arriba)
- [[sesion-2026-04-22-brief-cesar-posada]] — patrón de onboarding cliente nuevo Arnaldo
