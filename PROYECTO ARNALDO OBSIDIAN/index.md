# Índice de la Wiki — Ecosistema Arnaldo Ayala

Última actualización: 2026-04-24 | Total páginas: 64 (1 fuente + 20 entidades + 27 conceptos + 8 síntesis + 1 mapa de prod + **7 playbooks** incluyendo README)

## Fuentes (1)
| Página | Resumen | Fecha | Proyecto | Tags |
|--------|---------|-------|----------|------|
| [[wiki/fuentes/sesion-2026-04-22]] | Sesión densa: CORS Maicol + Monitor Capa 1 + CRM v2 unificado Robert+Mica + audit Postgres + bug tokens .env | 2026-04-22 | compartido | cors, monitoreo, crm-v2, postgres, env-vars, telegram, coolify |

## Entidades (20)

### Las 3 agencias del ecosistema
| Página | Dueño | Estado |
|--------|-------|--------|
| [[wiki/entidades/agencia-arnaldo-ayala]] | [[arnaldo-ayala]] | 🟢 producción (Maicol + Lau) |
| [[wiki/entidades/lovbot-ai]] | [[robert-bazan]] | 🟠 en construcción |
| [[wiki/entidades/system-ia]] | [[micaela-colmenares]] | 🟡 sin producción propia aún |

### Personas
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/arnaldo-ayala]] | persona / dueño agencia Arnaldo Ayala | arnaldo |
| [[wiki/entidades/robert-bazan]] | persona / dueño Lovbot.ai | robert |
| [[wiki/entidades/micaela-colmenares]] | persona / dueña System IA | mica |
| [[wiki/entidades/lau]] | persona / cliente-propio (familia) | arnaldo |
| [[wiki/entidades/maicol]] | cliente externo de Arnaldo | arnaldo |
| [[wiki/entidades/cesar-posada]] | cliente nuevo de Arnaldo — agencia turismo (propuesta enviada 2026-04-22) | arnaldo |

### Marcas de clientes
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/back-urbanizaciones]] | marca comercial (cliente Maicol) | arnaldo |

### Productos / BDs modelo
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/lovbot-crm-modelo]] | BD Postgres modelo (plantilla para clientes Lovbot) | robert |
| [[wiki/entidades/inmobiliaria-demo-mica-airtable]] | Base Airtable modelo (plantilla para clientes System IA) | mica |

### Productos / Frontends CRM modelo (HTML)
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/crm-v2-modelo-robert]] | Frontend HTML CRM modelo Lovbot (`crm.lovbot.ai/dev/crm-v2`) | robert |
| [[wiki/entidades/crm-v2-modelo-mica]] | Frontend HTML CRM modelo System IA (`/system-ia/dev/crm-v2`) | mica |

### Productos / Paneles Gestión (admin de tenants/clientes)
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/panel-gestion-robert]] | Admin Lovbot (`admin.lovbot.ai/clientes` — Coolify Hetzner desde 2026-04-23 con DNS propagado) — gestiona clientes Lovbot | robert |
| [[wiki/entidades/panel-gestion-mica]] | Admin System IA (`system-ia-agencia.vercel.app/system-ia/admin`) — gestiona clientes Mica | mica |

### Productos / Marketing y captura
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/landing-lovbot-ai]] | Landing pública Lovbot (`https://lovbot.ai/`) — captura leads agencia | robert |

### Infraestructura — VPS
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/vps-hostinger-arnaldo]] | vps | arnaldo |
| [[wiki/entidades/vps-hetzner-robert]] | vps | robert |
| [[wiki/entidades/vps-hostinger-mica]] | vps | mica |

### Infraestructura — Orquestadores
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/coolify-arnaldo]] | orquestador | arnaldo |
| [[wiki/entidades/coolify-robert]] | orquestador | robert |
| [[wiki/entidades/easypanel-mica]] | orquestador | mica |

## Conceptos (27)

### Reglas transversales (leer PRIMERO)
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/regla-de-atribucion]] | ⚠️ SIEMPRE preguntar "¿Arnaldo / Robert / Mica?" antes de operar | arnaldo, robert, mica |
| [[wiki/conceptos/aislamiento-entre-agencias]] | ⚠️ Las 3 agencias NUNCA se cruzan entre sí (ni clientes, ni datos, ni stacks) | arnaldo, robert, mica |
| [[wiki/conceptos/matriz-infraestructura]] | Tabla definitiva stack por agencia (VPS, DB, provider, LLM) | arnaldo, robert, mica |

### Bases de datos
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/airtable]] | SaaS low-code — Arnaldo + Mica | arnaldo, mica |
| [[wiki/conceptos/postgresql]] | `robert_crm` en container Coolify — solo Robert | robert |

### WhatsApp providers
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/ycloud]] | BSP — solo Arnaldo/Maicol | arnaldo |
| [[wiki/conceptos/meta-graph-api]] | Tech Provider directo — solo Robert | robert |
| [[wiki/conceptos/evolution-api]] | Self-hosted — Mica + Lau (instancias separadas) | mica, arnaldo |

### Automatización
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/n8n]] | 3 instancias independientes (una por proyecto) | arnaldo, robert, mica |
| [[wiki/conceptos/sistema-auditoria]] | Auditoría diaria 8am ARG — 7 auditores + auto-reparación + Telegram | arnaldo, robert, mica |

### Testing cross-agencia
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/numero-test-tech-provider]] | 1 nro conectado a WABA Robert → routeable a cualquier worker (demo Arnaldo/Mica/Robert) vía `probar_worker.sh` | compartido |

### Meta / WhatsApp (Tech Provider)
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/meta-business-portfolio-verificacion]] | SOP verificación Business Portfolio (paso 0 antes de Tech Provider) | robert, arnaldo, mica |
| [[wiki/conceptos/meta-tech-provider-onboarding]] | Embedded Signup + Coexistence + App Review — URLs oficiales Meta verificadas + checklist completo | robert |
| [[wiki/conceptos/meta-webhooks-compliance]] | Deauthorize + Data Deletion webhooks (n8n + Cloudflare Worker verify HMAC) | robert |

### CRM arquitectura (data model)
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/persona-unica-crm]] | Persona única con roles múltiples (comprador/inquilino/propietario) — evita duplicación cross-tabla | robert, mica |
| [[wiki/conceptos/contratos-polimorficos]] | Tabla contratos con tipo + item_tipo + item_id — 3 puertas 1 modal 1 endpoint | robert, mica |

### Ventas y onboarding
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/onboarding-cliente-nuevo-arnaldo]] | Patrón brief HTML + propuesta HTML + deploy Coolify — USD 300 impl + USD 80/mes. Primer uso: Cesar Posada | arnaldo |
| [[wiki/conceptos/runbook-meta-social-automation]] | 🔒 RUNBOOK — Onboarding publicación automática FB+IG + bot comentarios. 3 gotchas documentados (User vs Page Token, regla 7 días System User, IG-Page link). 30 min siguiendo pasos vs 6h improvisando. Probado con Maicol 2026-04-23 | compartido |

### Infraestructura y deploys
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/coolify-default-deploy]] | ⚡ Coolify como default para HTMLs/sitios nuevos (no Vercel). Sin cupo 100/día. 2026-04-22 | compartido |

### Tenants / catálogo de clientes
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/supabase-tenants]] | 🔗 Supabase compartido (cuenta Arnaldo) guarda catálogo de clientes que adquirieron CRM. Lo leen ambos paneles admin | robert, mica |

### Proyectos pendientes (propuestos, NO implementados aún)
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/crm-agencia-lovbot]] | 📋 CRM propio Robert+Arnaldo para gestionar leads agencia (landing + bot WhatsApp). Storage: Postgres Hetzner (NO Supabase). Status: pendiente | robert |

### Operación / Reglas del repo
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/cors-preflight-monitoreo]] | Patrón de check con OPTIONS + Origin header — detecta CORS roto antes que el cliente | arnaldo, robert, mica |
| [[wiki/conceptos/env-quoting-tokens]] | 🔒 REGLA — tokens con `|` requieren comillas dobles en `.env`. Bash source rompe sin ellas | global |

### Humanización de workers WhatsApp (patrón compartido)
| Página | Resumen breve | Proyectos |
|--------|--------------|-----------|
| [[wiki/conceptos/message-buffer-debounce]] | 🧠 Buffer Redis debounce 8s — consolida mensajes fragmentados antes del LLM. Patrón Kevin Bellier en Python. Tenant slugs `mica-demo`/`robert-demo`. Redis `redis-workers` en ambos Coolify | compartido |
| [[wiki/conceptos/image-describer]] | 🖼️ Normalizador imágenes → texto con GPT-4o-mini Vision. Helpers download_media_meta + download_media_evolution. Guard magic numbers + sanitización mime. Costo $0.00015/img | compartido |
| [[wiki/conceptos/typing-indicator-pattern]] | 💭 "Escribiendo..." en todas las respuestas del bot. Wrapper de `_enviar_texto()` que bloquea 2s. Soporta Meta + Evolution + YCloud (fallback). Guardar `ultimo_msg_id` para typing visual Meta | compartido |
| [[wiki/conceptos/message-splitter-pattern]] | ✂️ Partición de saludos en 2-3 chunks con GPT-4o-mini. SOLO en primer turno (detección: `"Bot:" not in HISTORIAL`). Costo $0.0001 por split. Fallback `[texto]` si falla | compartido |

## Síntesis (8)
| Página | Origen | Fecha | Proyecto |
|--------|--------|-------|----------|
| [[wiki/sintesis/2026-04-18-limpieza-tenants-supabase]] | Decisión arquitectural: 1 tenant demo por agencia | 2026-04-18 | compartido |
| [[wiki/sintesis/2026-04-21-refactor-postgres-workspaces]] | Refactor Postgres Lovbot a arquitectura workspaces (1 DB x cliente) — cerrada fuga cross-tenant, creada BD modelo `lovbot_crm_modelo` | 2026-04-21 | robert |
| [[wiki/sintesis/2026-04-21-crm-v2-mica]] | Setup CRM v2 Mica con stack Airtable + Evolution + decisión Embedded Signup compartido via TP Robert | 2026-04-21 | mica |
| [[wiki/sintesis/2026-04-22-crm-v3-robert]] | Refactor CRM v3 Robert — persona única + contratos polimórficos + lotes granulares + GESTIÓN editable | 2026-04-22 | robert |
| [[wiki/sintesis/2026-04-22-crm-v3-mica]] | Replicación CRM v3 Mica (Airtable) — mismo modelo persona única + contratos + UI ámbar — backend 11/11 OK, frontend Vercel deployado | 2026-04-22 | mica |
| [[wiki/sintesis/2026-04-23-migracion-lovbot-coolify]] | 🏆 Migración completa Lovbot Vercel → Coolify Hetzner. `crm.lovbot.ai` y `admin.lovbot.ai` ahora 100% en Hetzner. Cero downtime. CRM Agencia LIVE como mockup | 2026-04-23 | robert |
| [[wiki/sintesis/2026-04-23-humanizacion-workers-redis]] | 🧠 Humanización bots demo — Redis buffer debounce 8s + Image describer Vision GPT en Mica + Robert. 10 commits. Fix colateral bug `waba_clients` faltante post-migración. Patrón Kevin Bellier aplicado en Python | 2026-04-23 | compartido |
| [[wiki/sintesis/2026-04-24-humanizacion-v2-horarios-sanitizacion]] | 🎯 Humanización v2 — typing indicator + splitter saludo + horarios atención + sanitizar nombre (`@rn@ldo`→`Arnaldo`). 10 commits. 3 bugs descubiertos: Python 3.11 f-strings triples, Coolify cache no rebuild, reglas prompt chocan entre sí | 2026-04-24 | compartido |

---

## Playbooks (6) — patrones repetibles para construcción

> **LEER ANTES de arrancar un trabajo nuevo del tipo correspondiente.** Evita repetir errores ya resueltos.

| Playbook | Qué construye | Versión | Proyectos |
|----------|---------------|---------|-----------|
| [[wiki/playbooks/worker-whatsapp-bot]] | Bot WhatsApp conversacional (BANT, 1-a-1, LLM) | v1 | arnaldo, robert, mica |
| [[wiki/playbooks/worker-social-automation]] | Publicación auto FB+IG + bot comentarios + DMs | v1 | arnaldo (extensible) |
| [[wiki/playbooks/crm-html-tailwind]] | CRM/panel con HTML+Tailwind CDN+JS vanilla | v1 | robert, mica, arnaldo |
| [[wiki/playbooks/postgres-multi-tenant]] | BD Postgres aislada por cliente (workspaces) | v1 | robert |
| [[wiki/playbooks/airtable-schema-setup]] | Base Airtable con schema estándar | v1 | arnaldo, mica |
| [[wiki/playbooks/propuesta-cliente-coolify]] | Landing/propuesta pública en `clientes-publicos/{slug}/` | v1 | arnaldo |

Ver [[wiki/playbooks/README]] para reglas de uso y cómo evolucionan.

---

## Mapa mental rápido

### Las 3 agencias del ecosistema

- 🟢 **[[wiki/entidades/agencia-arnaldo-ayala]]** (dueño Arnaldo) — única con clientes LIVE: [[wiki/entidades/maicol]] + [[wiki/entidades/lau]]
- 🟠 **[[wiki/entidades/lovbot-ai]]** (dueño Robert, Arnaldo socio técnico) — en construcción, bot demo LIVE
- 🟡 **[[wiki/entidades/system-ia]]** (dueña Mica, Arnaldo socio técnico) — sin clientes productivos propios aún

### Referencia maestra (leer PRIMERO)

- [[wiki/conceptos/regla-de-atribucion]] — ⚠️ preguntar "¿cuál agencia?" antes de actuar
- [[wiki/conceptos/aislamiento-entre-agencias]] — ⚠️ las 3 agencias jamás se cruzan
- [[wiki/conceptos/matriz-infraestructura]] — stack por agencia
