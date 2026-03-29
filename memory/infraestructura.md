# Infraestructura y despliegues

## WhatsApp por actor

| Actor | Proveedor actual | Estado |
|-------|-----------------|--------|
| Arnaldo | YCloud | Cliente YCloud, no Tech Provider directo |
| Robert | Meta directo | Ya es Tech Provider — usa WABA propia |
| Mica | Evolution API | En camino a Tech Provider Meta propio |

## FastAPI — Render

- **URL**: https://system-ia-agentes.onrender.com
- **Repo**: github.com/Arnaldo999/system-ia-agentes
- **Convención workers**:
  - Un worker `_demo` por vertical (punto de partida, nunca se edita)
  - Para nuevo cliente: copiar demo → renombrar → configurar env vars propias
- **Workers activos**:
  - `workers/inmobiliaria_maicol/` → `POST /inmobiliaria/whatsapp` (Maicol — producción)
  - `workers/inmobiliaria_demo/` → `POST /inmobiliaria-demo/whatsapp` (EN CONSTRUCCIÓN)
- **Variables de entorno en Render**:
  - `GEMINI_API_KEY` — general
  - `AIRTABLE_TOKEN` — token general (un token sirve para todas las bases)
  - `YCLOUD_API_KEY_MAICOL` — YCloud de Maicol
  - `AIRTABLE_BASE_ID_MAICOL` — base Airtable de Maicol
  - Identificación por cliente: solo cambia `AIRTABLE_BASE_ID_<CLIENTE>`

## n8n Producción — Coolify (Hostinger VPS Arnaldo)

- **URL**: https://n8n.arnaldoayalaestratega.cloud
- **API Key**: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmM2VjOTRiYi1kNjlmLTQ1NjYtYWZkMi1hNDI1OWM0ZTllMDAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiN2ZiODE5NDQtMmU3Mi00ZjM3LTg3ODgtNTQ3MTA0NjVkYjQzIiwiaWF0IjoxNzc0NjEzNDgxfQ.0Sil51HrgVx6C-TmaHZl1bOQnrYwiqA5cas5C_jPexs
- **Plataforma**: Coolify sobre Hostinger VPS
- **Propósito**: Producción clientes Arnaldo. Centraliza todos los flujos.
- **Clientes activos**: Inmobiliaria Maicol (bot WhatsApp YCloud + formulario leads)

## n8n Staging — Easypanel (VPS Mica)

- **URL**: https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host
- **Propósito**: Proyectos System IA (Mica + Arnaldo). Producción pendiente VPS propio.

## n8n Robert

- **Estado**: Sin acceso aún. Robert no otorgó credenciales.
- **Pending**: Esperar acceso. Preparar workflows exportables.
- **WhatsApp**: Meta directo (Tech Provider). Cuando haya acceso, configurar WABA propia.

## Airtable

- Un solo token general compartido
- Cada cliente se identifica por su `AIRTABLE_BASE_ID` propio
- Tablas Maicol: propiedades `tbly67z1oY8EFQoFj`, clientes `tblonoyIMAM5kl2ue`, base `appaDT7uwHnimVZLM`

## Componentes FastAPI activos

| Worker | Ruta | Cliente | Estado |
|--------|------|---------|--------|
| inmobiliaria_maicol | /inmobiliaria/whatsapp | Maicol | Producción ✅ |
| social | /social/meta-webhook | Sistema IA | Activo |
| inmobiliaria_demo | /inmobiliaria-demo/whatsapp | Demo | En construcción |
