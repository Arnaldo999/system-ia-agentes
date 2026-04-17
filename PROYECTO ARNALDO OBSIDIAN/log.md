# Log de Operaciones

<!-- Formato: ## [YYYY-MM-DD] operacion | Detalle -->
<!-- Parseable: grep "^## \[" log.md | tail -10 -->
<!-- Tipos de operacion: init, ingest, query, lint, update, sesion-claude -->

## [2026-04-17] init | Wiki inicializada
- Estructura de carpetas creada: `raw/{arnaldo,robert,mica,compartido,assets}` + `wiki/{entidades,conceptos,fuentes,sintesis}`
- Esquema `CLAUDE.md` configurado para 3 proyectos físicamente separados (Arnaldo, Robert, Mica) + stacks compartidos (Cal.com, Supabase, OpenAI Arnaldo)
- Reglas críticas establecidas: etiquetado obligatorio de proyecto en frontmatter, prohibido mezclar stacks entre proyectos
- Skill `llm-wiki` instalada en `.claude/skills/llm-wiki/`
- Bóveda Obsidian configurada en `.obsidian/`

## [2026-04-17] init | Seed de entidades base
- `wiki/entidades/arnaldo-ayala.md` creada (persona, dueño del ecosistema)
- `wiki/entidades/robert-bazan.md` creada (persona/cliente Lovbot)
- `wiki/entidades/micaela-colmenares.md` creada (persona/socia System IA)
- `wiki/conceptos/matriz-infraestructura.md` creada (concepto fundamental — tabla stack por proyecto)

## [2026-04-17] update | Corrección error de clasificación de Lau
- Error detectado: `micaela-colmenares.md` decía "(ej: [[lau]])" como cliente de Mica. Lau es proyecto propio de Arnaldo (esposa).
- Causa raíz: confusión por el path legacy `workers/clientes/system_ia/lau/` que NO implica ownership de Mica.
- Fix: creada `wiki/entidades/lau.md` con `proyecto: arnaldo` y advertencia de trampa del path. Corregidas referencias cruzadas en `arnaldo-ayala.md`, `micaela-colmenares.md` y `matriz-infraestructura.md`.
- Documentado en la matriz como "Trampa del path — Lau" para prevenir repetición.

## [2026-04-17] update | Clarificación: 2 proyectos en producción propios (Maicol + Lau)
- Confirmado por Arnaldo: solo **2 proyectos** están 100% en producción como propios (Maicol + Lau). Robert es alianza técnica (no cliente); Mica es sociedad comercial (sin clientes productivos documentados aún).
- Creada `wiki/entidades/maicol.md` (Back Urbanizaciones, LIVE desde 2026-04-06, cliente externo de Arnaldo).
- Reescrita sección "Estructura de sus proyectos" en `arnaldo-ayala.md` con 3 categorías: Producción propia · Alianza técnica · Sociedad comercial.
- Actualizado mapa mental en `index.md` para reflejar la jerarquía real.

## [2026-04-17] ingest | Pasada 1a — 12 fuentes desde memory/ Mission Control
Arquitectura de silos aplicada (CLAUDE.md REGLA #0bis). Se copiaron archivos de `memory/` (silo 3) a `raw/[agencia]/` (silo 2) para que se puedan ingerir con llm-wiki.

Fuentes copiadas:
- `raw/arnaldo/` (1): crm-apostoles-mapa
- `raw/robert/` (1): robert-bazan-alianza-brief
- `raw/mica/` (1): guia-ventas-micaela
- `raw/compartido/` (9): gastronomia-subnichos, restaurante-gastronomico, onboarding-redes-sociales, nuevo-cliente-redes-sociales, social-publicaciones, wordpress-elementor-sitios-web, membresia-app, rag-sistema-google-embeddings, historial-crewai-saas-agencias

Pendiente: ingerir con skill llm-wiki + eliminar originales de memory/ una vez validado.

## [2026-04-17] update | Regla: aislamiento total entre las 3 agencias
Refinamiento conceptual confirmado por Arnaldo: las 3 agencias son **paralelas y nunca se cruzan entre sí**. Arnaldo es el centro, asociado individualmente con Robert y con Mica (2 sociedades separadas), pero Robert y Mica no tienen relación comercial entre sí.

Página nueva:
- `wiki/conceptos/aislamiento-entre-agencias.md` — define qué NO se cruza (clientes, datos, bases, providers, env vars, credenciales, dominios), qué SÍ puede compartirse (Cal.com, Supabase, OpenAI en algunos casos) y lista trampas detectadas en sesiones anteriores.

Index actualizado con la nueva página como tercera referencia maestra junto con `regla-de-atribucion` y `matriz-infraestructura`.

## [2026-04-17] update | Modelo de 3 agencias + regla de atribución
Confirmado por Arnaldo: el ecosistema tiene **3 agencias** distintas (no era un solo workspace con clientes):
- **Agencia Arnaldo Ayala — Estratega en IA y Marketing** (mía propia, dueño Arnaldo, 🟢 LIVE con Maicol + Lau)
- **System IA** (dueña Mica, Arnaldo socio técnico)
- **Lovbot.ai** (dueño Robert, Arnaldo socio técnico)

Páginas nuevas:
- `wiki/entidades/agencia-arnaldo-ayala.md` (agencia de Arnaldo)
- `wiki/entidades/lovbot-ai.md` (agencia de Robert)
- `wiki/conceptos/regla-de-atribucion.md` — **regla irrompible**: siempre preguntar a cuál de las 3 agencias corresponde antes de operar.

Actualizadas:
- `system-ia.md` → tipo cambiado de "marca-comercial" a "agencia" + sección desambiguación actualizada.
- `arnaldo-ayala.md` → descripción menciona las 3 agencias y su rol en cada una (dueño / socio / socio).
- `matriz-infraestructura.md` → fila nueva "Dueño de la agencia" + "Rol de Arnaldo" en cada columna, y sección nueva "Paso 0 obligatorio — atribución" arriba del todo.
- `index.md` → sección nueva "Las 3 agencias del ecosistema" destacada, reorganizado mapa mental.

## [2026-04-17] ingest | Infraestructura base (14 páginas nuevas)
Fuente: panorama de infraestructura dictado directamente por Arnaldo (conocimiento propio).

Entidades creadas (8):
- VPS: `vps-hostinger-arnaldo`, `vps-hetzner-robert`, `vps-hostinger-mica`
- Orquestadores: `coolify-arnaldo`, `coolify-robert`, `easypanel-mica`
- Marcas: `back-urbanizaciones`, `system-ia`

Conceptos creados (6):
- Bases: `airtable`, `postgresql`
- WhatsApp providers: `meta-graph-api`, `evolution-api`, `ycloud`
- Automatización: `n8n`

Actualizado `matriz-infraestructura.md` con wikilinks transversales a todas las entidades y conceptos nuevos + 2 secciones especiales (Lau con trampa del path + Back Urbanizaciones).

Estado wiki: 12 entidades + 7 conceptos = 19 páginas. Falta ingestar fuentes oficiales (briefs, memory/*.md del Mission Control).
