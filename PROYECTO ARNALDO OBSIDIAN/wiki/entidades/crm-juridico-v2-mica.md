---
title: CRM Jurídico v2 — Mica (Estudio de Marcas INPI)
type: producto
proyecto: mica
tags: [proyecto-mica, system-ia, crm-juridico, airtable, inpi, marcas, estudio-juridico]
---

# CRM Jurídico v2 — Estudio de Marcas INPI (Mica)

CRM vertical para estudios que tramitan marcas ante el INPI (Instituto Nacional de la Propiedad Industrial, Argentina). Demo de System IA para vender a estudios jurídicos y contadores. Diseñado entre Arnaldo y Mica en tiempo real.

## Estado (al 2026-04-27)

🟠 **Demo funcional** — Airtable conectado, backend operativo, UX co-diseñada con Mica. Pendiente: SMTP real, Excel boletín, bot captación, n8n recordatorios.

## Stack

| Capa | Tecnología | Detalle |
|------|------------|---------|
| Base de datos | Airtable `appSjeRUoBGZo5DtO` | Base dedicada (no compartida con CRM inmobiliaria) |
| Backend | FastAPI | `workers/clientes/system_ia/demos/juridico/router.py` |
| Frontend | HTML + Tailwind CDN + JS vanilla | `demos-system-ia/dev/crm-juridico-v2.html` |
| Archivos | Static `/uploads/` | Montado en `main.py` como `StaticFiles` |
| Hosting backend | Coolify Arnaldo Hostinger | `agentes.arnaldoayalaestratega.cloud` |
| Hosting frontend | (mismo servidor vía static files) | — |

## Tablas Airtable

| Tabla | ID | Propósito |
|-------|----|-----------|
| Leads | — | Prospectos (activos / nutrición) |
| Propuestas | — | Para hacer / Ya enviadas |
| Clientes_Estudio | — | Titular de marca + datos personales completos |
| Marcas | — | Cada solicitud INPI |
| Socios_Marca | `tblX4NQCEzFZRwEar` | Co-titulares con % participación |
| Comunicaciones_Oposicion | — | Notificaciones recibidas del INPI |
| Trámites | — | Seguimiento estado marca |
| Plantillas | — | Templates de email editables |

## Features implementadas

- [x] Login modal con validación de usuario (localStorage)
- [x] Dashboard 2 columnas (alertas con plazo verde / sin plazo azul + 8 cards de sección)
- [x] Leads con 2 listas (activos / nutrición) + botón "Pasar a Propuesta"
- [x] Propuestas con 2 listas (para hacer / enviadas) + botones aceptada/rechazada
- [x] Modal Aceptar Propuesta: titular + N socios dinámicos + datos marca + Nota Poder
- [x] Marcas: 2 listas (para presentar / ya presentadas) + "Ver Datos para Cargar" + "Listo ✅"
- [x] Ficha de marca editable (titular + socios inline)
- [x] Upload real de archivos (DNI, Nota Poder) → Airtable `multipleAttachments`
- [x] Comunicaciones y Oposiciones con tipos de notificación
- [x] Trámites con fechas y estados
- [x] Plantillas con render (interpolación de variables cliente/marca)
- [x] Modo oscuro/claro con toggle + persistencia localStorage + auto-detect SO

## Features pendientes

- [ ] SMTP real (emails simulados como preview HTML)
- [ ] Upload Excel Boletín de Marcas → análisis automático de oposiciones
- [ ] Bot WhatsApp para captación de leads entrantes
- [ ] n8n workflow para recordatorios de vencimiento por email
- [ ] CRUD completo desde UI (editar/eliminar con botones conectados)

## Patrones técnicos clave

- **Socios reverse-link**: `filterByFormula` falla en linked records → leer array `Socios_Marca` del record Marca → GET individual de cada ID. Ver `[[wiki/conceptos/airtable-reverse-link-pattern]]`.
- **Upload pipeline**: browser FormData → `/crm/upload` → `/uploads/` static → URL pública → Airtable `multipleAttachments`. Ver `[[wiki/conceptos/fastapi-upload-attachment-pipeline]]`.
- **Dark mode**: CSS vars `:root` + `[data-theme="dark"]` + override `background: white` inline.
- **Airtable typecast**: usar `typecast: True` en creación para singleSelect con valores nuevos.

## Fuentes

- [[wiki/fuentes/sesion-2026-04-27-crm-juridico-v2]] (raw: `raw/mica/sesion-2026-04-27-crm-juridico-v2.md`)
- Sesión previa (base): [[wiki/fuentes/sesion-2026-04-26]] (raw: `raw/mica/...`)

## Relaciones

- Dueña: [[wiki/entidades/micaela-colmenares]]
- Agencia: [[wiki/entidades/system-ia]]
- Infraestructura: [[wiki/entidades/vps-hostinger-mica]] (backend en Arnaldo Hostinger)
