# Log de Operaciones

<!-- Formato: ## [YYYY-MM-DD] operacion | Detalle -->
<!-- Parseable: grep "^## \[" log.md | tail -10 -->
<!-- Tipos de operacion: init, ingest, query, lint, update, sesion-claude -->

## [2026-04-21] sesion-claude | Setup CRM v2 Mica + decisión Embedded Signup compartido
- Replicado el trabajo de CRM v2 de Robert para Mica (System IA), adaptando al stack Mica: Airtable `appA8QxIhBYYAHw0F` + Evolution API + Coolify Arnaldo. Respeta regla #0 de aislamiento entre stacks (nada de Postgres ni Meta Graph API propio, por ahora).
- Creado `demos/SYSTEM-IA/dev/crm-v2.html` clonado del de Robert con: paleta ámbar/rojo `#f59e0b` + `#dc2626` (vs purple/cyan Robert), branding "System IA / Inmobiliaria Demo Mica", endpoints `/clientes/system_ia/*`, sidebar con 3 subnichos.
- Base Airtable Mica ampliada de 5 tablas a **17 tablas** via Metadata API: agregadas 12 (core + agencia + config). Ver [[wiki/entidades/inmobiliaria-demo-mica-airtable]] para Table IDs completos.
- Tenant `mica-demo` en Supabase corregido: `airtable_base_id` apuntaba a base de Arnaldo, colores heredados de demo anterior. Fix via PATCH directo a REST API Supabase. PIN reseteado a `1234`.
- 5 bugs arreglados en el CRM Mica: (1) backend apuntaba a Vercel en vez de Coolify, (2) faltaba carpeta `dev/js/` con helpers externos, (3) endpoint `/crm/resumenes` bloqueaba por Postgres requerido, (4) tenant en Supabase con base Airtable cruzada, (5) colores residuales verde/beige.
- Verificación end-to-end OK: CRM local muestra los 19 leads reales de Airtable Mica, paleta ámbar aplicada, webhook bot Evolution HTTP 200, sincronización bot↔Airtable↔CRM funcionando.
- **Decisión estratégica**: Embedded Signup de Meta para Robert fue aprobado. El número que usa Mica (`+54 9 3765 00-5465`) se migrará de Evolution a Meta Graph API vía TP de Robert como tránsito técnico, hasta que Arnaldo y Mica saquen sus propios TPs. Infraestructura ya preparada en commit `ec33418` con columnas `agencia_origen` + `meta_user_id`. Migración del bot Mica queda para otra sesión.
- Pendiente no urgente: deploy Vercel Mica (cupo 100 deploys/día agotado, reabre mañana), resúmenes IA stub hasta primer cliente pago, refactor "1 base Airtable por cliente" cuando haya cliente real.
- Commits: `01c98f3` (CRM v2 adaptado), `8b32da1` (12 tablas Airtable), `31a85f9` (rewrite Vercel), `92617fe` (fixes backend+JS+resumenes).
- Páginas wiki creadas: [[wiki/sintesis/2026-04-21-crm-v2-mica]], [[wiki/entidades/inmobiliaria-demo-mica-airtable]], [[raw/mica/sesion-2026-04-21-crm-v2-mica]].

## [2026-04-21] sesion-claude | Refactor Postgres Lovbot a arquitectura workspaces
- Detectada violación de regla #0 (aislamiento físico por cliente): `robert_crm` tenía 38 leads mezclados entre `tenant_slug='demo'` (19) y `tenant_slug='robert'` (19).
- Descubierta vulnerabilidad en validator SQL n8n (workflow `CRM IA - Ejecutar SQL` id `0t32XZ9AuQXB9fOn`): saltaba inyección de tenant si el query mencionaba `tenant_slug` como SELECT-field → cross-tenant leak posible. Fix aplicado vía MCP n8n.
- Detectado código legacy en worker demo `workers/demos/inmobiliaria/worker.py`: los 3 GET endpoints (`/crm/clientes`, `/crm/propiedades`, `/crm/activos`) leían de Airtable en lugar de Postgres. Refactorizado con patrón `if USE_POSTGRES: return db.get_all_X()` como ya hacía Robert.
- Creada **`lovbot_crm_modelo`** como BD modelo única (10 leads + 10 props + 3 activos demo + 15 tablas cubriendo 3 subnichos). Schema ampliado con 6 tablas nuevas para agencia inmobiliaria (inmuebles_renta, inquilinos, contratos_alquiler, pagos_alquiler, liquidaciones, config_cliente).
- Arnaldo actualizó Coolify (`LOVBOT_PG_DB=lovbot_crm_modelo`, `LOVBOT_TENANT_SLUG=demo`) + redeploy + credencial n8n "Postgres account 2" → `lovbot_crm_modelo`.
- Verificación end-to-end: CRM frontend muestra 10/10/3, IA dice 10/10/3, Postgres tiene 10/10/3. Sincronización total.
- Limpieza: 29 DBs → 1. Borradas 26 DBs de test + `robert_crm` + `lovbot_crm` + `demo_crm`.
- Endpoints admin creados: `/admin/listar-dbs`, `/crear-db-cliente` (con param `from_db`), `/ampliar-schema-agencia`, `/reducir-modelo`, `/debug-db`, `/debug-worker-demo`, `/borrar-db`.
- Commits relevantes en repo `Arnaldo999/system-ia-agentes`: 722617d, 859fc14, 34b16cd, e8f6bee, 35e91a7, b4abac0, b393eba, 14481f5, b245635.
- Páginas wiki actualizadas: [[wiki/conceptos/postgresql]], [[wiki/entidades/lovbot-crm-modelo]] (nueva), [[wiki/sintesis/2026-04-21-refactor-postgres-workspaces]] (nueva).
- Fuente ingestada: `raw/robert/sesion-2026-04-21-postgres-refactor.md`.

## [2026-04-20] ingest | Kevin curso "Tech Provider SaaS" — Intro
- Nuevo curso de Kevin sobre convertir el TP en un SaaS multi-tenant (distinto al curso general de TP que ya completamos).
- Distinción clave SaaS vs Agencia: SaaS = tú eres responsable de datos, multi-tenant en 1 infra, MÁS restricciones Meta. Agencia = cliente maneja sus datos, no escala.
- Robert está operando modelo SaaS aunque lo venda como "agencia": multi-tenant backend + almacena datos clientes + compliance responsable. Confirmación de que todo lo que implementamos hoy (agencia_origen, compliance webhooks, meta_user_id) es exactamente el patrón SaaS que Kevin enseña.
- Estructura del curso: 9 lecciones (1-4 setup + 5-7 App Review + 8 skills bonus + 9 Data Handling).
- Primeras 7 lecciones ya están cubiertas en Robert por el curso anterior. Lecciones 8 (skills bonus) y 9 (Data Handling) pueden aportar info nueva.

## [2026-04-20] feat | Multi-agencia en infra Tech Provider Robert
- Decisión Arnaldo: usar app TP de Robert como tránsito técnico para onboardear clientes propios hasta verificar portfolio Arnaldo y sacar TP propio.
- Implementado commit `ec33418`:
  - PG `waba_clients`: columnas `agencia_origen` + `meta_user_id` (ALTER idempotente).
  - Helpers DB: `listar_waba_clients_por_agencia`, `actualizar_agencia_origen`.
  - Endpoints admin FastAPI: `GET /tenants-por-agencia` + `POST /reclasificar-agencia`.
  - `access_token` siempre REDACTED en responses admin.
- Documentado SOP de migración futura en `meta-tech-provider-onboarding.md` (cuando Arnaldo saque su propio TP, cliente hace 1 click y migra sin pérdida de datos).
- Arnaldo comunicará a Robert via WhatsApp — mensaje simple: "voy a onboardear clientes míos via tu app TP, es tránsito técnico, cuando tenga TP propio los migro". Sin mencionar a Mica (decisión de Mica será propia cuando llegue el momento).

## [2026-04-20] ingest | Kevin Ber video "Cómo Verificar Negocio en Meta" — SOP portfolio
- Video de Kevin Ber (otro mentor, canal AISH Automation) sobre paso 0 absoluto: verificar Business Portfolio en business.facebook.com.
- Creada `wiki/conceptos/meta-business-portfolio-verificacion.md` con SOP 12 pasos + 8 errores comunes ordenados por frecuencia + casos de uso por agencia del ecosistema.
- Aplicabilidad: Robert ya verificado (es TP). Arnaldo y Mica: por confirmar si tienen portfolio propio o dependen de BSP (YCloud/Evolution).
- Oportunidad estratégica documentada: Robert puede ofrecer "WhatsApp oficial llave en mano" a clientes sin TP propio, cobrar premium (Kevin menciona que agencias cobran miles de USD por asesoría TP).
- Diferenciado de ruta BSP: Kevin desaconseja Evolution API explícitamente por inestabilidad + riesgo de baneo.

## [2026-04-20] wrap-up | Curso Kevin "Tech Provider + Embedded Signup" COMPLETADO
- 12 clases Kevin validadas contra Robert (2 submódulos al 100%).
- Arquitectura Robert SUPERA lo que Kevin enseña (FastAPI multi-tenant auto vs workflows n8n manuales clickeados).
- Todo el trabajo práctico del día consolidado en `wiki/conceptos/meta-tech-provider-onboarding.md` + `meta-webhooks-compliance.md`.
- Estado Robert: Tech Provider 100% funcional a nivel infra. Solo espera aprobación Meta (8 días restantes).

## [2026-04-20] ingest + feat | Clase Kevin #8 — Override callback URI por cliente
- Validación: Robert YA tenía `POST /webhook/meta/override` por WABA en `webhook_meta.py:414`.
- Gap detectado: Kevin también cubre override por `phone_number_id` (para separar varios números de la misma WABA, caso ventas vs soporte).
- Implementado `POST /webhook/meta/override-phone` (commit `b940288`) con mismo patrón admin auth.
- Nota arquitectural: Robert NO necesita override_callback para multi-tenant normal — ya tiene router FastAPI que forwardea por `phone_number_id` a `worker_url` del tenant en `waba_clients`. El override solo sirve para casos enterprise donde cliente exige SU propia infra separada.
- Endpoints disponibles ahora:
  - `POST /webhook/meta/override` (por WABA entera) — ya existía
  - `POST /webhook/meta/override-phone` (por número específico) — agregado hoy

## [2026-04-20] ingest | Clase Kevin #7 — Envío de mensajes via Graph API
- Validación cross-check: YA IMPLEMENTADO LIVE en `robert_inmobiliaria/worker.py` hace meses.
- Tipos cubiertos: texto (`_enviar_texto` línea 510), imagen (`_enviar_imagen` línea 540), templates (`_enviar_template` línea ~4070).
- Ventana de 24h: enforced por diseño — el bot solo envía libres en respuesta a mensajes entrantes. Templates pre-aprobados (`nurturing_3_dias/15/30`) para fuera de ventana, ya justificados ante Meta en App Review.
- Robert tiene ventajas vs Kevin: (a) 3 tipos de mensaje vs solo texto, (b) automatico vs manual Set Datos, (c) mirror a Chatwoot para que dueño vea el chat, (d) templates para nurturing fuera de 24h.
- Sin cambios requeridos — stack 100% alineado + superado. Versiones Graph API: webhook_meta.py=v24.0, worker.py=v21.0/v22.0 (no tocar sin testing, hay conversaciones reales).

## [2026-04-20] ingest | Clase Kevin #6 — Configuración webhook eventos mensaje
- Validación cross-check: YA IMPLEMENTADO en `webhook_meta.py` LIVE desde antes de esta sesión.
- Tests corridos: GET /verify + /events con token incorrecto → 403 ✅, POST con `object: page` → 400 ✅, POST con WABA válido → 200 ✅.
- Robert tiene 5 features BONUS que Kevin no cubre: (1) multi-tenant routing por phone_number_id, (2) dedup de reintentos Meta, (3) background processing <5s, (4) descarte mensajes viejos (>30s), (5) separación statuses vs messages.
- Arquitectura ventajosa: 1 endpoint FastAPI multi-tenant vs 1 workflow n8n por cliente que propone Kevin.
- Sin cambios de código requeridos — solo confirmación que el stack actual está alineado 100% + supera en varios aspectos.

## [2026-04-20] update | Vercel auto-deploy activado para lovbot-onboarding
- Detectado que proyecto Vercel `lovbot-onboarding` NO estaba conectado a Git (creado via `vercel deploy` CLI hace 3 días).
- Conectado repo `Arnaldo999/system-ia-agentes` + Root Directory `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/onboarding-vercel`.
- Commit `b21305e` trigger primer auto-deploy → confirmado: HTML productivo ahora sirve `featureType` correcto (Coexistence ACTIVO).
- Documentada trampa en `meta-tech-provider-onboarding.md` sección "Trampa Vercel".
- Beneficio durable: cero deploys manuales desde ahora.

## [2026-04-20] ingest | Clase Kevin #5 — Webhook recepción onboarding + Coexistence
- Validación: `lovbot-onboarding.vercel.app/?client=slug` ya tenía implementado el flow Embedded Signup pero con bug en `extras` que NO activaba Coexistence.
- Fix aplicado en `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/onboarding-vercel/index.html`:
  - `extras.feature` → `extras.featureType` (clave correcta)
  - `'whatsapp_embedded_signup'` → `'whatsapp_business_app_onboarding'` (valor correcto)
  - `sessionInfoVersion: 3` → `'3'` (string, no número)
  - SDK FB version `v21.0` → `v24.0`
- Commit `52a7fad` push → Vercel auto-deploy.
- Memorizado en `meta-tech-provider-onboarding.md` sección "Frontend Embedded Signup" con código completo y 3 trampas comunes (`featureType` vs `feature`, string vs número, requisito CONFIG_ID).
- Clarificado por qué Robert NO usa el patrón Kevin de n8n + 2 webhooks + Header Auth: tiene backend FastAPI propio con APP_SECRET server-side, más seguro y simple.
- Riesgo cero para App Review en curso: el cambio mejora el flow para clientes finales, Meta usa cuentas test que aceptan ambos formatos.

## [2026-04-20] ingest | Clase Kevin #4 — Webhooks de compliance (deauthorize + data_deletion)
- Creada: `wiki/conceptos/meta-webhooks-compliance.md` con arquitectura completa Meta → n8n → Cloudflare Worker → data table.
- Incluye código completo del Cloudflare Worker `/verify` (HMAC SHA-256 sobre encodedPayload, timingSafeEqual, base64url decoder).
- Documentado: Meta exige 2 campos opcionales en panel Facebook Login → sección "Cancelar autorización" (deauthorize + data_deletion URL).
- 3 links Drive con plantillas n8n de Kevin (son privados, hay que pedírselos).
- **Gap detectado en Robert**: ninguno de los 2 webhooks está configurado, no existe Cloudflare Worker, no hay workflows n8n. Webhook de mensajes SÍ existe (FastAPI `webhook_meta.py`, no n8n).
- Riesgo medio-alto: Meta puede pedir completarlo como condición post-review para advanced access.
- Decisión pragmática: si Robert no opera con datos UE/Brasil, se puede completar después del review. Pero conviene hacerlo antes para reducir observaciones.

## [2026-04-20] ingest | Clase Kevin #3 — Configuración Facebook Login para Embedded Signup
- Agregada sección "Configuración de Facebook Login para Embedded Signup" en `meta-tech-provider-onboarding.md`.
- Tabla con los 7 toggles correctos del panel `/fb-login/settings/` + los 2 campos de texto críticos (redirect URIs + domains SDK).
- URL `/docs/facebook-login/business/` que Kevin recomienda devuelve 404 — la canónica vigente es `/docs/facebook-login/facebook-login-for-business` (actualizada 25 mar 2026).
- URL `/docs/facebook-login/security/` vigente pero sin updates desde oct 2024.
- Pendiente de verificación: los 7 toggles en el panel real de Robert (screenshot no solicitado aún).

## [2026-04-20] ingest | Clases de Kevin sobre Embedded Signup + Coexistence + public_profile advanced access
- Fuente: 2 clases de texto del mentor Kevin enviadas por Arnaldo durante sesión Claude.
- Creada: `wiki/conceptos/meta-tech-provider-onboarding.md` consolidando:
  - Los 4 pilares técnicos (App Meta, permisos, Embedded Signup, Coexistence).
  - URLs oficiales Meta verificadas contra developers.facebook.com (status 200 + fechas de última actualización capturadas).
  - Checklist de 9 ítems para App Review obligatoria.
  - Secuencia correcta para onboarding de un nuevo Tech Provider (10 pasos).
  - Trampas comunes (modo Desarrollo bloquea flow externo, `lovbot.mx` devuelve 403 a curl pero 200 a navegadores y Meta-ExternalAgent).
- URLs clave documentadas: Overview, Implementation v4, Coexistence, Postman collection oficial, Tech Providers, Access Verification, Permissions Reference, Migrate existing number.
- Estado App Review Robert (2026-04-20 08:58): `whatsapp_business_management` + `whatsapp_business_messaging` en revisión con 2 videos enviados. `public_profile` en Advanced access (Meta lo otorga automático).
- Validación cross-checklist paquete: todos los ítems del `PAQUETE-COMPLETO.md` están cubiertos y enviados a Meta.

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

## [2026-04-22] sesion-claude | CRM v3 Robert refactor completo — contratos polimórficos + persona única
- Ingesta: `raw/robert/sesion-2026-04-22-crm-v3-robert.md`
- Síntesis: `wiki/sintesis/2026-04-22-crm-v3-robert.md`
- Conceptos nuevos: `wiki/conceptos/persona-unica-crm.md`, `wiki/conceptos/contratos-polimorficos.md`
- 16+ commits backend+frontend, 14 smoke tests verdes en producción, UI visualmente idéntica

## [2026-04-22] sesion-claude | CRM v3 Mica — replicación del modelo persona única en Airtable
- Ingesta: `raw/mica/sesion-2026-04-22-crm-v3-mica.md`
- Síntesis: `wiki/sintesis/2026-04-22-crm-v3-mica.md`
- 4 commits backend+frontend (5ef5303 → a9dc86a → a616f70 → e3817bb), 11/11 endpoints Mica producción OK, frontend Vercel deployado inmediatamente. UI ámbar respetada (0 purple Robert). IDs Airtable strings rec... sin parseInt. Polimorfismo con 3 linkedRecord + serializer.

## [2026-04-22] sesion-claude | Onboarding Cesar Posada (cliente nuevo Arnaldo — turismo)
- Entidad nueva: `wiki/entidades/cesar-posada.md` (estado: propuesta-enviada)
- Raw: `raw/arnaldo/sesion-2026-04-22-brief-cesar-posada.md`
- Concepto nuevo: `wiki/conceptos/onboarding-cliente-nuevo-arnaldo.md` (patrón reutilizable)
- Entregables LIVE: brief.html + propuesta.html en agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/
- Stack asignado: Airtable + YCloud + Coolify Hostinger (matriz estándar clientes Arnaldo)
- Precios: USD 300 implementación + USD 80/mes mantenimiento
- Próximo paso: esperar que Cesar complete y envíe el brief .md por WhatsApp

## [2026-04-22] update | Regla: Coolify default para deploys nuevos (reemplaza Vercel)
- Concepto nuevo: `wiki/conceptos/coolify-default-deploy.md`
- Actualizado: `wiki/conceptos/onboarding-cliente-nuevo-arnaldo.md` con referencia a la regla
- Motivo: cupo Vercel Hobby 100/día se agotó 2 veces en sesiones de refactor intenso. Coolify Hostinger no tiene límite, mismo VPS ya pagado.
- Pendiente: migrar CRM v2 Robert de Vercel a Coolify Hetzner Robert (agendado 2026-04-23 tras reset cupo Vercel)
- Mica queda en Vercel hasta que compre dominio propio
