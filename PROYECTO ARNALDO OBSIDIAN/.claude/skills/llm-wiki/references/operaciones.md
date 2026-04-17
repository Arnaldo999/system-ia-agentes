# Flujos de Operación — LLM Wiki

Referencia detallada de cómo ejecutar cada operación de la wiki.

---

## 1. INGERIR una fuente

**Cuándo**: el usuario añade un archivo a `raw/` y pide procesarlo, o pega el contenido directamente.

### Flujo

```
1. Lee la fuente completa (o el contenido proporcionado)
2. Lee index.md para conocer el estado actual de la wiki
3. Identifica:
   - Ideas clave (3-7 puntos principales)
   - Entidades mencionadas (personas, orgs, productos, proyectos)
   - Conceptos centrales (términos, teorías, metodologías)
   - Contradicciones potenciales con lo ya conocido
4. Discute brevemente con el usuario los takeaways principales
   (omitir si el usuario pidió ingesta no-supervisada)
5. Escribe wiki/fuentes/<nombre-kebab>.md
6. Para cada entidad identificada:
   - Si existe la página → léela y añade la nueva información
   - Si no existe → crea wiki/entidades/<nombre>.md
7. Para cada concepto identificado:
   - Si existe la página → léela, actualiza, marca contradicciones si las hay
   - Si no existe → crea wiki/conceptos/<nombre>.md
8. Actualiza index.md (añade fila en la sección correspondiente)
9. Append a log.md: ## [YYYY-MM-DD] ingest | Título de la fuente
10. Resume al usuario: N páginas tocadas, entidades/conceptos nuevos, contradicciones detectadas
```

### Ejemplo de página de fuente

```markdown
---
title: "El Arte de la Guerra — Sun Tzu"
date: 2026-04-15
source_url: ""
source_path: "raw/el-arte-de-la-guerra.md"
type: libro
tags: [estrategia, clásicos, filosofía-militar]
---

# El Arte de la Guerra — Sun Tzu

## Resumen
Tratado militar chino del siglo V a.C. que expone principios de estrategia aplicables más allá de lo militar.

## Ideas clave
- Conoce al enemigo y conócete a ti mismo: en cien batallas nunca estarás en peligro
- El supremo arte de la guerra es someter al enemigo sin luchar
- La velocidad es la esencia de la guerra

## Entidades mencionadas
- [[entidades/sun-tzu]] — autor
- [[entidades/reino-wu]] — reino al que sirvió

## Conceptos relacionados
- [[conceptos/estrategia]] — libro fundacional del concepto
- [[conceptos/engano-estrategico]] — tema central

## Citas destacadas
> "Suprema excelencia consiste en romper la resistencia del enemigo sin luchar."

## Notas de síntesis
Comparar con [[fuentes/sobre-la-guerra-clausewitz]] — perspectivas opuestas sobre el rol del combate directo.
```

---

## 2. CONSULTAR la wiki

**Cuándo**: el usuario hace una pregunta sobre el conocimiento acumulado.

### Flujo

```
1. Lee index.md completo
2. Identifica qué páginas son relevantes para la pregunta
3. Lee esas páginas (empieza por las más directamente relevantes)
4. Si hay páginas de síntesis relacionadas, léelas también
5. Construye la respuesta con citas explícitas: [[fuentes/X]], [[conceptos/Y]]
6. Presenta la respuesta al usuario
7. Pregunta: "¿Quieres que guarde esta respuesta como página de síntesis?"
8. Si sí → escribe wiki/sintesis/<nombre>.md y actualiza index.md y log.md
```

### Formatos de respuesta posibles
- **Texto con citas** — para preguntas analíticas
- **Tabla comparativa** — para comparar entidades/conceptos entre sí
- **Lista priorizada** — para "¿qué dice el wiki sobre cómo hacer X?"
- **Mapa de relaciones** (texto) — para preguntas sobre conexiones entre conceptos

---

## 3. LINT — Auditoría de salud

**Cuándo**: el usuario pide una revisión de salud del wiki, o periódicamente.

### Checklist de lint

```
Lee index.md y luego recorre las páginas wiki/ buscando:

□ Páginas huérfanas — no tienen ningún wikilink que las apunte
□ Conceptos sin página propia — mencionados en varias fuentes pero sin [[conceptos/X]]
□ Entidades sin página propia — igual que conceptos
□ Contradicciones no resueltas — dos fuentes afirman cosas incompatibles sin nota
□ Páginas sin frontmatter YAML — rompen Dataview queries
□ Index desactualizado — páginas en wiki/ que no están en index.md
□ Log incompleto — ingestas sin entrada en log.md
□ Preguntas abiertas — gaps de conocimiento que podrían llenarse con nuevas fuentes
□ Wikilinks rotos — referencias a páginas que no existen
```

### Output del lint

Presenta un reporte con:
1. **Hallazgos críticos** — cosas a corregir ya
2. **Mejoras sugeridas** — páginas a crear, conexiones a añadir
3. **Fuentes sugeridas** — qué buscar para llenar los gaps detectados
4. **Preguntas abiertas** — investigaciones que el usuario podría explorar

Tras el reporte, pregunta cuáles problemas quiere resolver ahora.

---

## 4. GUARDAR EXPLORACIÓN como página wiki

**Cuándo**: una respuesta a una consulta es lo suficientemente valiosa para no perderse en el historial.

```markdown
---
title: "Comparación: Estrategia Occidental vs Oriental"
date: 2026-04-15
query_origin: "¿Qué diferencias hay entre Clausewitz y Sun Tzu sobre el combate directo?"
tags: [estrategia, comparacion, sintesis]
fuentes_citadas: [el-arte-de-la-guerra, sobre-la-guerra-clausewitz]
---

# Comparación: Estrategia Occidental vs Oriental

## Pregunta de origen
¿Qué diferencias hay entre Clausewitz y Sun Tzu sobre el combate directo?

## Síntesis
[respuesta elaborada con citas]

## Fuentes citadas
- [[fuentes/el-arte-de-la-guerra]]
- [[fuentes/sobre-la-guerra-clausewitz]]
```

---

## 5. INICIALIZAR la wiki

**Cuándo**: primera vez que se usa la wiki, o en un nuevo directorio/dominio.

```
1. Pregunta el dominio/tema si no está claro
2. Crea la estructura de directorios:
   mkdir -p wiki/{entidades,conceptos,fuentes,sintesis}
   mkdir -p raw/assets
3. Escribe CLAUDE.md con el esquema adaptado al dominio
4. Crea index.md con la estructura vacía y las secciones correctas
5. Crea log.md con la entrada de inicialización
6. Informa al usuario qué creaste
```

### Preguntas a hacer durante inicialización (si no son obvias)

- ¿Cuál es el dominio o tema principal de esta wiki?
- ¿Tienes fuentes ya en `raw/` que quieras ingerir de inmediato?
- ¿Quieres usar frontmatter YAML compatible con Dataview?
- ¿Prefieres ingestas supervisadas (tú revisas antes de que yo guarde) o autónomas?

---

## Convenciones de naming — referencia rápida

| Tipo | Carpeta | Ejemplo filename | Ejemplo título |
|------|---------|-----------------|----------------|
| Fuente | `wiki/fuentes/` | `el-arte-de-la-guerra.md` | El Arte de la Guerra |
| Entidad (persona) | `wiki/entidades/` | `sun-tzu.md` | Sun Tzu |
| Entidad (org) | `wiki/entidades/` | `openai.md` | OpenAI |
| Concepto | `wiki/conceptos/` | `aprendizaje-por-refuerzo.md` | Aprendizaje por Refuerzo |
| Síntesis | `wiki/sintesis/` | `comparacion-llms-2026.md` | Comparación de LLMs 2026 |

**Reglas**:
- Filenames: kebab-case, sin tildes, sin espacios, en minúsculas
- Títulos en H1: español normal con tildes y mayúsculas apropiadas
- Tags: en español, sin tildes, con guiones (`aprendizaje-automatico`)
