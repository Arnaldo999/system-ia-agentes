# Log de Operaciones

<!-- Formato: ## [YYYY-MM-DD] operacion | Detalle -->
<!-- Parseable: grep "^## \[" log.md | tail -10 -->
<!-- Tipos de operacion: init, ingest, query, lint, update, sesion-claude -->

## [2026-04-20] update | Patrón "numero test via Tech Provider Robert" implementado
- Creado: `workers/shared/wa_provider.py` — capa abstracción Meta/Evolution/YCloud (send + parse unificados).
- Adaptados: 2 workers demo inmobiliaria (Arnaldo `workers/demos/inmobiliaria/` + Mica `workers/clientes/system_ia/demos/inmobiliaria/`) para switch via env var `WHATSAPP_PROVIDER=meta`.
- Intactos (producción): `arnaldo/maicol/`, `system_ia/lau/`, `lovbot/robert_inmobiliaria/`.
- Creado: `02_OPERACION_COMPARTIDA/scripts/probar_worker.sh` — CLI switch rápido con aliases (arnaldo-demo, mica-demo, robert-demo, gastronomia) que llama `/admin/waba/client/{phone_id}/update-worker-url`.
- Creada: `wiki/conceptos/numero-test-tech-provider.md` — doc completa del patrón.
- Uso: 1 nro conectado via Embedded Signup a app Meta Robert → routeable a cualquier worker solo cambiando el worker_url en PG `waba_clients` (sin desconectar nro de Meta).
- Motivación: aprovechar que Robert es el único Tech Provider del ecosistema para darle a Arnaldo (socio técnico de las 3 agencias) nro WhatsApp oficial testeable cross-agencia sin depender de Evolution/YCloud.

## [2026-04-18] update | Eliminado tenant Supabase 'robert' (duplicado funcional con 'demo')
- Decisión: dejar UN solo tenant demo por agencia en Supabase (antes había `demo` + `robert` ambos agencia=lovbot mostrando datos demo idénticos).
- Eliminado: `DELETE FROM tenants WHERE slug='robert'` en Supabase compartido.
- Estado final Supabase: 2 tenants (`demo` lovbot + `mica-demo` system-ia).
- NO afectado: tabla `waba_clients` en PG `robert_crm` (bot productivo +52 998 743 4234 sigue vivo con db_id=1). Worker `robert_inmobiliaria/` activo.
- Razón: `robert` en Supabase era una "producción simulada" con mismos datos demo que `demo`, no aportaba valor real. Se prestaba a confusión ("¿es cliente real pagando? no, es demo igual que los otros").
- Sincronización: silo 3 (`memory/ESTADO_ACTUAL.md`) actualizado con nueva sesión 2026-04-18 que documenta esta decisión.

## [2026-04-18] update | Sincronización Lau — es Arnaldo, NO Mica
- Detectado: silo 1 (auto-memory `feedback_REGLA_infraestructura_clientes.md:58`) y silo 3 (`memory/ESTADO_ACTUAL.md`) decían incorrectamente que Lau era cliente de Mica.
- Wiki (silo 2) ya lo tenía correcto: Lau = proyecto propio de Arnaldo (negocio "Creaciones Lau" de su esposa).
- Corregidos ambos silos. Path legacy `workers/clientes/system_ia/lau/` es engañoso pero dueño real = Arnaldo.
- Regla aplicada: wiki es fuente de verdad — silos 1 y 3 se sincronizan con ella.

## [2026-04-17] update | Sistema de auditoría diaria documentado y limpiado
- Verificado: n8n Arnaldo `IuHJLy2hQhOIDlYK` activo con Schedule 8am ARG → `/auditor/fase2` ✅
- Verificado: n8n Mica `jUBWVBMR6t3iPF7l` Monitor LinkedIn activo ✅
- Eliminado: `heartbeat.log` (1 línea vieja de 2026-03-13, obsoleto)
- Consolidado: `auditor_runner.py` — fuente de verdad = `02_OPERACION_COMPARTIDA/scripts/`. Copia en `backends/` sincronizada (tenía versión sin auto_reparador ni auditor_social).
- Creada: `wiki/conceptos/sistema-auditoria.md` con arquitectura completa, 7 auditores, Remote Triggers, tabla "qué pasa si falla".

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

## [2026-04-17] ingest | Pasada 2 — 18 fuentes desde auto-memory global
Copiados `project_*` y `reference_*` de `~/.claude/projects/*/memory/` a `raw/[agencia]/` clasificados por ownership.

Por agencia:
- `raw/arnaldo/` (7): project-maicol, project-lau, project-demo-pack, project-social-publishing, project-verticales, project-auditoria-agencia, project-auto-reparador
- `raw/robert/` (5): project-robert-alianza, project-robert-bot-sprint1, project-lovbot-crm, project-postgres-migration, project-crm-completo
- `raw/mica/` (1): project-mica-demo-inmo
- `raw/compartido/` (5): project-claude-code-infra, project-crm-ia-chat, project-sesion-2026-04-13, reference-infra, reference-skill-whatsapp-bot

Originales del auto-memory siguen intactos — se eliminarán en pasada 3 tras validación.

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
