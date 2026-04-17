# Wiki Schema — Ecosistema Arnaldo Ayala

## Dominio

Base de conocimiento permanente del ecosistema **System IA Mission Control**, que orquesta 3 proyectos físicamente separados:

- **Arnaldo Ayala** — agencia propia (bots con Airtable + YCloud, Coolify Hostinger)
- **Robert Bazán (Lovbot.ai)** — desarrolladora inmobiliaria (PostgreSQL `robert_crm` + Meta Graph API, Coolify Hetzner)
- **Micaela Colmenares (System IA, marca de Mica)** — (Airtable `appA8QxIhBYYAHw0F` + Evolution API, Easypanel)

Esta wiki acumula: stacks técnicos, decisiones arquitectónicas, incidentes y sus fixes, skills del equipo, integraciones con terceros (Meta, YCloud, Evolution, Cal.com, Supabase, Airtable, PostgreSQL, OpenAI, Gemini, Chatwoot, n8n), y resúmenes de sesiones importantes con Claude Code.

**Principio irrompible**: cada página debe etiquetarse claramente con el/los proyecto/s al que pertenece. Jamás mezclar stacks (ej: no escribir "Robert usa Airtable" — usa PostgreSQL).

## Estructura de carpetas

```
PROYECTO ARNALDO OBSIDIAN/
├── CLAUDE.md              ← esquema (este archivo)
├── index.md               ← catálogo de todas las páginas
├── log.md                 ← registro cronológico append-only
├── raw/                   ← fuentes originales INMUTABLES
│   ├── arnaldo/           ← docs, transcripciones, PDFs del proyecto Arnaldo
│   ├── robert/            ← idem Robert/Lovbot
│   ├── mica/              ← idem Mica/System IA
│   ├── compartido/        ← fuentes que aplican a 2+ proyectos
│   └── assets/            ← imágenes descargadas localmente
└── wiki/                  ← territorio del LLM — páginas sintetizadas
    ├── entidades/         ← personas, empresas, productos, proyectos
    ├── conceptos/         ← stacks, patrones, metodologías, técnicas
    ├── fuentes/           ← resumen de cada fuente ingestada
    └── sintesis/          ← exploraciones guardadas, comparaciones, análisis cruzados
```

## Formatos de página

### Página de fuente (`wiki/fuentes/`)
Frontmatter: `title`, `date`, `source_path`, `source_url` (opcional), `type` (pdf/video/transcripcion/articulo/sesion-claude), `proyecto` (arnaldo/robert/mica/compartido), `tags`.
Secciones: Resumen, Ideas clave, Entidades mencionadas, Conceptos relacionados, Citas destacadas, Notas de síntesis.

### Página de entidad (`wiki/entidades/`)
Frontmatter: `title`, `type` (persona/empresa/producto/proyecto/cliente/stack), `proyecto`, `tags`.
Secciones: Descripción, Stack asociado (si aplica), Aparece en [fuentes], Relaciones con otras entidades, Notas.

### Página de concepto (`wiki/conceptos/`)
Frontmatter: `title`, `tags`, `source_count`, `proyectos_aplicables` (lista).
Secciones: Definición, Fuentes que lo mencionan, Perspectivas distintas, Contradicciones detectadas, Ejemplos de uso.

### Página de síntesis (`wiki/sintesis/`)
Frontmatter: `title`, `date`, `query_origin`, `tags`, `fuentes_citadas`, `proyecto` (o `compartido`).
Secciones: Pregunta de origen, Síntesis, Fuentes citadas.

## Convenciones de naming

- **Filenames**: `kebab-case`, español sin tildes, minúsculas.
  - ✅ `robert-bazan.md`, `postgresql-robert-crm.md`, `meta-graph-api.md`
  - ❌ `Robert Bazán.md`, `PostgreSQL.md`
- **Títulos (H1)**: español normal con tildes y mayúsculas apropiadas.
- **Tags**: sin tildes, con guiones. Prefijo de proyecto recomendado.
  - `proyecto-arnaldo`, `proyecto-robert`, `proyecto-mica`, `compartido`
  - `whatsapp-provider`, `base-de-datos`, `llm-provider`, `orquestador`, `stack-tecnico`
- **Wikilinks**: `[[wiki/entidades/robert-bazan]]` o relativos `[[robert-bazan]]` si Obsidian lo resuelve.

## Etiquetado obligatorio de proyecto

**TODA página de entidad, concepto, fuente o síntesis debe indicar a qué proyecto pertenece** vía frontmatter `proyecto:` y vía tag. Valores válidos:

- `arnaldo` — ecosistema agencia Arnaldo (Maicol, Back Urbanizaciones, bots propios)
- `robert` — Lovbot / Robert Bazán / lovbot.ai
- `mica` — System IA / Micaela / Lau
- `compartido` — aplica a 2+ proyectos (ej: Cal.com de Arnaldo que usan los 3)
- `global` — infraestructura del Mission Control (skills, hooks, agentes)

## Formato del log

```
## [YYYY-MM-DD] operacion | Detalle
```

Tipos de operación: `init`, `ingest`, `query`, `lint`, `update`, `sesion-claude` (ingesta de resumen de sesión).

## Workflow de ingesta preferido

- Ingesta **supervisada** (Claude muestra qué va a escribir antes de commitear).
- Fuentes en `raw/[proyecto]/` — nunca mezclar. Si una fuente aplica a varios, va a `raw/compartido/`.
- Preferir chunks chicos: 1 fuente por ingestión (en vez de procesar 20 PDFs de golpe).
- Al ingerir, Claude debe etiquetar con `proyecto:` el frontmatter — sin esta etiqueta la página es inválida.

## Integración con Mission Control

- El Mission Control raíz (`~/PROYECTOS SYSTEM IA/SYSTEM_IA_MISSION_CONTROL/CLAUDE.md`) tiene una REGLA #0 de router de proyectos que delega a subagentes `proyecto-arnaldo`, `proyecto-robert`, `proyecto-mica`.
- **Esta wiki es la memoria persistente compartida entre sesiones de Claude Code**. No reemplaza a `memory/` del Mission Control (memoria operativa cotidiana), la complementa como base de conocimiento navegable + visualizable en Obsidian.
- Al final de sesiones importantes, Claude debería proponer ingerir el resumen como fuente tipo `sesion-claude` en `raw/[proyecto]/sesion-YYYY-MM-DD.md`.

## Reglas especiales para este ecosistema

1. **Jamás documentar un stack en un proyecto que no lo usa**. Robert NO tiene Airtable. Mica NO tiene PostgreSQL. Si hay duda, consultar la entidad `[[wiki/conceptos/matriz-infraestructura]]`.
2. **Bugs recurrentes** (ej: mezcla de stacks, env vars con prefijo incorrecto) van a `wiki/sintesis/bugs-recurrentes.md` agrupados por tipo.
3. **Entidades que aparecen en todos los proyectos** (Cal.com, Supabase, Coolify) deben tener su página con sección "Quién la usa" y "Cómo la usa cada uno".
4. **Fuentes de APIs externas** (docs de Meta Graph, Evolution, YCloud, etc.) van a `wiki/fuentes/` con tag `documentacion-oficial`.
