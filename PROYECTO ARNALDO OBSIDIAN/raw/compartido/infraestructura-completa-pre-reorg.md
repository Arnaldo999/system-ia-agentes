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
- **Service ID**: `srv-d6g8qg5m5p6s73a00llg`
- **rootDir en Render**: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes` ← CRÍTICO (monorepo)
- **Tier**: Free (duerme tras 15min inactivo — keep-alive en n8n lo evita)
- **Convención workers**:
  - Un worker `_demo` por vertical (punto de partida, nunca se edita)
  - Para nuevo cliente: copiar demo → renombrar → configurar env vars propias
- **Workers activos**:
  - `workers/inmobiliaria/` → `POST /inmobiliaria/whatsapp` (Maicol — producción)
  - `workers/inmobiliaria_demo/` → `POST /inmobiliaria-demo/whatsapp` (EN CONSTRUCCIÓN)
- **Variables de entorno en Render**:
  - `GEMINI_API_KEY` — general
  - `AIRTABLE_TOKEN` — token general (un token sirve para todas las bases)
  - `YCLOUD_API_KEY_MAICOL` — YCloud de Maicol
  - `AIRTABLE_BASE_ID_MAICOL` — base Airtable de Maicol
  - Identificación por cliente: solo cambia `AIRTABLE_BASE_ID_<CLIENTE>`
- **Keep-alive**: workflow n8n `kjmQdyTGFzMSfzov` pinga `/health` cada 14min (activo)

## n8n Producción — Coolify (Hostinger VPS Arnaldo)

- **URL**: https://n8n.arnaldoayalaestratega.cloud
- **API Key**: en variable de entorno `N8N_API_KEY` (no exponer en archivos)
- **Plataforma**: Coolify sobre Hostinger VPS
- **Propósito**: Producción clientes Arnaldo. Centraliza todos los flujos.
- **Clientes activos**: Inmobiliaria Maicol (bot WhatsApp YCloud + formulario leads)

## n8n Staging — Easypanel (VPS Mica)

- **URL**: https://sytem-ia-pruebas-n8n.6g0gdj.easypanel.host
- **Propósito**: Proyectos System IA (Mica + Arnaldo). Producción pendiente VPS propio.

## Infraestructura Robert — Lovbot (Hetzner VPS, acceso otorgado 2026-03-30)

| Servicio | URL | Estado |
|---------|-----|--------|
| n8n | https://n8n.lovbot.ai/ | Activo ✅ |
| Chatwoot | https://chatwoot.lovbot.ai/ | Activo ✅ (cuenta Arnaldo: arnaldoayala157@gmail.com) |
| Coolify Lovbot | http://5.161.235.99:8000/ | Proyecto "Lovbot Projects" — CPX21 |
| Coolify Arnaldo en VPS Robert | http://5.161.208.152:8000/ | CPX11 — sin proyectos aún |
| Google Drive | Compartido | Solo si necesario |

- **Servidores Hetzner**: `Lovbot-Projects` (5.161.235.99, CPX21) + `lovbot-postgres` (5.161.208.152, CPX11)
- **WhatsApp Robert**: Meta Tech Provider directo (WABA propia)
- **Plan VPS**: VPS actual = staging/agencia. Clientes nuevos → VPS dedicado por cliente (compra Robert)
- **Nicho foco**: Desarrolladores inmobiliarios México (tipo agentesinteligentes.mx)

## Airtable

- Un solo token general compartido
- Cada cliente se identifica por su `AIRTABLE_BASE_ID` propio
- Tablas Maicol: propiedades `tbly67z1oY8EFQoFj`, clientes `tblonoyIMAM5kl2ue`, base `appaDT7uwHnimVZLM`
- **CRITICO**: API meta Airtable no permite editar singleSelect choices con PAT sin scope `schema.bases:write` → hacerlo manualmente en UI
- Estado Clientes Maicol: `no_contactado`, `contactado`, `en_negociacion`, `cerrado`, `descartado`
- Imagen_URL es campo attachment (array de objetos) → leer: `imgField[0].url`, escribir: `[{url:"..."}]`

## Cloudinary

- Cloud Name: `dmqkqcreo` (env `CLOUDINARY_CLOUD_NAME`)
- Upload Preset: `social_media_posts` (env `CLOUDINARY_UPLOAD_PRESET`) — unsigned, usado por worker social + CRM Maicol
- Endpoint CRM: `POST /clientes/arnaldo/maicol/crm/upload-imagen` — recibe multipart, retorna `{url}`

## Componentes FastAPI activos — Arquitectura v3

```
workers/
├── clientes/arnaldo/maicol/   → /clientes/arnaldo/maicol/whatsapp  (Producción ✅)
├── demos/inmobiliaria/        → /demos/inmobiliaria/whatsapp        (Demo multi-subniche)
├── social/                    → /social/meta-webhook                 (System IA)
└── _legacy/                   → workers anteriores archivados (no se usan)
```

**Regla de escalado:**
- Nuevo cliente Arnaldo → `workers/clientes/arnaldo/[nombre]/`
- Nuevo cliente Mica → `workers/clientes/mica/[nombre]/`
- Cliente Robert → deploya en Coolify de su VPS (mismo código, distinto servidor)
- Demos → siempre en `workers/demos/[vertical]/`, una por vertical

**n8n Maicol workflow:** URL actualizada a `/clientes/arnaldo/maicol/whatsapp` ✅
