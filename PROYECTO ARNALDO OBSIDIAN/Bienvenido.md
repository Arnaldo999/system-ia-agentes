# Bienvenido a la Wiki del Ecosistema Arnaldo Ayala

Esta bóveda Obsidian es la **memoria persistente compartida** entre sesiones de Claude Code y el trabajo diario en los 3 proyectos: [[wiki/entidades/arnaldo-ayala|Arnaldo]] · [[wiki/entidades/robert-bazan|Robert/Lovbot]] · [[wiki/entidades/micaela-colmenares|Mica/System IA]].

## Puntos de entrada

- 📚 **[[index]]** — catálogo de todas las páginas (fuentes, entidades, conceptos, síntesis)
- 📋 **[[log]]** — registro cronológico de operaciones
- 🔒 **[[wiki/conceptos/matriz-infraestructura]]** — regla irrompible de qué stack usa cada proyecto
- 📖 **[[CLAUDE]]** — esquema de la wiki (convenciones, reglas, workflow)

## Cómo agregar conocimiento (trabajo con Claude Code)

1. Tirá el documento original (PDF, transcripción, nota, URL, .md) en la carpeta correspondiente:
   - `raw/arnaldo/` — si es del proyecto Arnaldo
   - `raw/robert/` — si es del proyecto Robert/Lovbot
   - `raw/mica/` — si es del proyecto Mica/System IA
   - `raw/compartido/` — si aplica a 2+ proyectos
2. En Claude Code decí: **"ingerí la fuente en raw/[proyecto]/[archivo]"** o simplemente **"procesá esta fuente"**.
3. Claude lee el archivo, extrae ideas/entidades/conceptos, crea las páginas en `wiki/` con wikilinks y actualiza el `index.md` + `log.md`.

## Cómo consultar la wiki

En Claude Code: **"qué dice mi wiki sobre X"** o **"buscá en la wiki qué stack usa Robert"**. Claude lee el `index.md`, navega las páginas relevantes y responde con citas `[[page]]`.

Si la respuesta es valiosa, Claude puede guardarla como síntesis en `wiki/sintesis/`.

## Mantenimiento

Pedile a Claude un **lint** periódico (una vez por semana o después de una ingesta grande):
> "hacé un lint de la wiki"

Esto revisa huérfanos, wikilinks rotos, conceptos sin página propia, etc.

---

_Esta wiki usa la skill **`llm-wiki`** (Método Karpathy) instalada en `.claude/skills/llm-wiki/`._
