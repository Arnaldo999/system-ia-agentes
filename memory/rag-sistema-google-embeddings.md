# RAG con Google Embeddings 2.0 + Pinecone — Skill de Referencia

**Fecha de captura**: 2026-03-18
**Fuente**: Video YouTube "Google y Claude Code cambian el RAG para siempre con esta herramienta"
**Contexto**: Prompt exacto para generar dashboard RAG interactivo con Claude Code

---

## Herramientas usadas en el video

| Herramienta | Detalle |
|-------------|---------|
| IDE | **Antigravity** (el IDE que usamos nosotros en System IA) |
| Extensión | **Claude Code** (integrada en Antigravity) |
| Dashboard generado | **Streamlit** (interfaz chat con panel de fuentes) |
| Embeddings | Google Gemini Embeddings 2.0 |
| Vector DB | Pinecone (free tier) |
| API Keys | Google AI Studio + Pinecone dashboard |

**Flujo de uso exacto**:
1. Abrir Antigravity → pegar el prompt a Claude Code
2. Claude Code genera todo el código + crea el `.env`
3. El usuario pega sus API keys en el `.env`
4. Le dice a Claude Code "inicializa el sistema"
5. Claude Code levanta Streamlit → da URL **localhost**
6. Desde esa interfaz web: cargar PDFs en la carpeta `docs/` → botón "Ingestar" → chatear

**Zero código del lado del usuario. Solo prompt + API keys + cargar documentos.**

---

## Prompt Master para construir el sistema RAG

```
Hola, necesito montar un sistema RAG y quiero ir directo al grano: usa el nuevo modelo de Google
Embeddings 2.0 (referencia: https://ai.google.dev/gemini-api/docs/embeddings) y dime exactamente
qué poner en el .env para las credenciales de Google y Pinecone, pero sin explicarme todo el
código paso a paso; dame directamente el script de un dashboard interactivo funcional configurado
para leer mis documentos (el corpus de conocimiento) desde una carpeta específica donde yo pueda
soltarlos y ponerme a chatear con ellos al instante, con el requisito clave de que el sistema me
devuelva siempre la media asociada a la fuente original, de modo que si la respuesta sale de un
PDF o una imagen (como un manual de usuario), el chat me muestre el texto de la respuesta junto
con la página de referencia y la captura o imagen de ese documento.
```

---

## Stack del sistema

| Componente | Tecnología |
|------------|-----------|
| Embeddings | Google Embeddings 2.0 (`text-embedding-004` o `gemini-embedding-exp-03-07`) |
| Vector DB | Pinecone |
| Backend | Python (FastAPI o script directo) |
| Frontend | Dashboard interactivo (Streamlit o similar) |
| LLM respuesta | Gemini o Claude |

---

## Variables .env requeridas

```env
# Google AI / Gemini API
GOOGLE_API_KEY=tu_clave_aqui

# Pinecone
PINECONE_API_KEY=tu_clave_aqui
PINECONE_ENV=us-east-1  # o tu región
PINECONE_INDEX_NAME=nombre-tu-indice

# Opcional: modelo a usar
EMBEDDING_MODEL=text-embedding-004
```

---

## Requisitos clave del sistema (no negociables)

1. **Drop folder**: carpeta `./docs/` donde se sueltan PDFs, imágenes, Word, etc.
2. **Indexación automática**: al detectar archivo nuevo → chunk → embed → upsert Pinecone
3. **Respuesta con fuente**: cada respuesta incluye:
   - Texto de la respuesta
   - Nombre del documento fuente
   - Número de página (si es PDF)
   - Captura/imagen de esa página (para PDFs/imágenes)
4. **Chat interactivo**: interfaz tipo chat, no solo Q&A estático
5. **Google Embeddings 2.0**: no usar OpenAI embeddings, usar la API de Google

---

## Flujo de arquitectura

```
[Drop folder ./docs/]
        ↓
[Loader: PDF/IMG/DOCX parser]
        ↓
[Chunker con metadata: {source, page, image_path}]
        ↓
[Google Embeddings 2.0 → vector]
        ↓
[Pinecone upsert con metadata]
        ↓
[Dashboard chat]
        ↓
[Query → embed → Pinecone search → retrieve chunks + metadata]
        ↓
[LLM genera respuesta con contexto]
        ↓
[Mostrar: respuesta + fuente + página + imagen]
```

---

## Notas para el Agente Dev (n8n / implementación)

- Este sistema es **ideal para clientes que tienen manuales, catálogos o documentación interna**
- El requisito de "media con la fuente" lo diferencia de RAG básico — es un selling point fuerte
- Para implementación en cliente: el drop folder puede ser Google Drive synced o S3
- Pinecone free tier soporta hasta 100K vectores (suficiente para demos de clientes)
- Google Embeddings 2.0 es gratuito hasta cierto límite con API key de Google AI Studio

---

## Cuándo usar esta skill

- Cliente pregunta por "chat con mis documentos"
- Cliente quiere buscar en manuales, catálogos, PDFs internos
- Proyecto de base de conocimiento con IA
- Demo técnica para cerrar venta de automatización avanzada
