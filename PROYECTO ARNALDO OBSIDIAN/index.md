# Índice de la Wiki — Ecosistema Arnaldo Ayala

Última actualización: 2026-04-17 | Total páginas: 24 (15 entidades + 9 conceptos)

## Fuentes (0)
| Página | Resumen | Fecha | Proyecto | Tags |
|--------|---------|-------|----------|------|

_Aún no hay fuentes ingestadas. Agregá archivos en `raw/[proyecto]/` y pedí "ingerir fuente"._

## Entidades (15)

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

### Marcas de clientes
| Página | Tipo | Proyecto |
|--------|------|----------|
| [[wiki/entidades/back-urbanizaciones]] | marca comercial (cliente Maicol) | arnaldo |

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

## Conceptos (9)

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

## Síntesis (0)
| Página | Origen | Fecha | Proyecto |
|--------|--------|-------|----------|

_Aún no hay síntesis guardadas._

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
