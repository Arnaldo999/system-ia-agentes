---
name: Cliente Maicol — Back Urbanizaciones
description: Primer cliente real en produccion — bot inmobiliario WhatsApp + sitio web + formulario leads
type: project
---

Bot WhatsApp para inmobiliaria Maicol (Back Urbanizaciones) — **en producción desde 2026-03-29**.

**Cliente propio de Arnaldo** — no es proyecto de Mica ni de Robert.

## Stack técnico
- Worker: `workers/clientes/arnaldo/maicol/worker.py` (repo central, deploy **Coolify Hostinger** — Render ya no se usa)
- Solo vende **Lotes y Terrenos** (sin alquiler)
- Zonas: San Ignacio, Gdor Roca, Apóstoles, Leandro N. Alem
- Numero bot: `5493764815689`
- Numero asesor: `+5493765384843` (env `NUMERO_ASESOR_MAICOL`)
- Notificación asesor: texto + link wa.me directo (no CTA — YCloud no soporta sin WABA oficial)
- n8n workflow Coolify: `o4CrjByltFurUWox`
- Keep-alive: `kjmQdyTGFzMSfzov` (ping /health cada 14min)

## CRM — crm.backurbanizaciones.com
Carpeta fuente: `PROYECTO PROPIO ARNALDO AUTOMATIZACION/INMOBILIARIA MAICOL/PRESENTACION/dashboard-crm.html`
Copia deploy: `DEMOS/back-urbanizaciones/crm.html` — **SIEMPRE sincronizar ambas con cp antes de push**
- Deploy: Vercel auto desde push `master:main`, dominio `crm.backurbanizaciones.com`

### Paneles del CRM (sidebar — 7 tabs):
1. **📋 Inicio** — KPIs propiedades + leads + accesos rápidos
2. **🏠 Propiedades** — tabla con filtros, modal nueva/editar propiedad, upload Cloudinary
3. **📊 Pipeline** — Kanban 5 columnas (no_contactado → contactado → en_negociacion → cerrado → descartado)
4. **👥 Leads** — grid con filtros, stats compactos estilo kanban-header, modal editar lead
5. **💼 Clientes Activos** — CRUD completo, Estado_Pago automático, alertas vencimiento, fetch fresco al entrar al tab
6. **🖼️ Galería** — grid de cards con imagen, filtros, modal detalle
7. **🗺️ Loteos** — cards loteo con stats (vendidos/reservados/disponibles), mapas interactivos SVG — **6 loteos** en LOTEOS_CONFIG

### Mapa Interactivo San Ignacio Golf & Resort (tab Loteos):
- **163 lotes** con pins SVG coloreados: verde=disponible, amarillo=reservado, rojo=vendido
- Coordenadas `LOTES_COORDS` absolutas [x,y] px sobre PNG 1241×1754 — **calibradas por usuario drag&drop 2026-04-07**
- ViewBox: `VX=30, VY=25, VW=1185, VH=1350` — crop del PNG sin footer
- Modo calibración: drag & drop pins + export coordenadas en 2 partes (1-82 y 83-163) al clipboard
- **Fetch fresco**: `abrirMapaLoteo()` hace GET `/activos` antes de renderizar — pins reflejan estado real

### Clientes Activos — fixes aplicados 2026-04-07:
- **Select Loteo dinámico**: dropdown generado desde `LOTEOS_CONFIG` — nuevo loteo = aparece automáticamente
- **Guardar**: usa `patchProxy()`/`postProxy()` con timeout 20s + `resetBtn()` siempre ejecuta (try+catch)
- **Datos frescos**: `recargarActivos()` hace GET antes de renderizar — tab siempre muestra data actual
- **Loteos disponibles (6)**: San Ignacio Golf & Resort / Loteo Altos de Apóstoles / Loteo Altos de Alem / Loteo La Paulina segunda Etapa / Loteo Altos de San Ignacio / Loteo Altos de Roca (últimos 3 agregados 2026-04-08)

### Features implementados (2026-04-04):
- Migración completa a **Tailwind CSS CDN** (eliminado CSS custom ~235 líneas)
- API endpoints corregidos: `${API}/clientes/arnaldo/maicol/crm/{propiedades|clientes}`
- **Perfil editable**: chip topbar → dropdown → modal con nombre, empresa, teléfono, email, dirección, foto (Cloudinary). Persiste en localStorage key `crm_perfil_maicol`
- **Tipos propiedad** actualizados a: `Lote residencial`, `Lote comercial`, `Lote en esquina`, `Terreno rural` (coincide exacto con Airtable — sin lowercase)
- **Buscador global** activo: filtra en el panel visible (título/zona/tipo props, nombre/teléfono leads)
- **fix modal-overlay**: `display:none/flex` CSS puro — NO usar `@apply hidden` + `@apply flex` (el `!important` de Tailwind rompe el toggle)

**CRM endpoints activos en worker:**
- `GET  /crm/clientes` — lista leads desde Airtable
- `POST /crm/clientes` — crea lead manual desde CRM
- `PATCH /crm/clientes/{id}` — edita lead (estado, teléfono, email, notas)
- `GET  /crm/propiedades` — lista propiedades
- `POST /crm/propiedades` — agrega propiedad
- `PATCH /crm/propiedades/{id}` — edita propiedad
- `POST /crm/upload-imagen` — sube imagen a Cloudinary, retorna URL
- `GET  /crm/activos` — lista clientes activos
- `POST /crm/activos` — crea cliente activo
- `PATCH /crm/activos/{id}` — edita cliente activo (Estado_Pago recalculado automáticamente)
- `DELETE /crm/activos/{id}` — elimina cliente activo

**Airtable — Tipo_Propiedad (Clientes) y Tipo (Propiedades):**
Opciones actuales (Maicol solo vende lotes/terrenos): `Lote residencial`, `Lote comercial`, `Lote en esquina`, `Terreno rural`

**Cloudinary:** `CLOUDINARY_CLOUD_NAME=dmqkqcreo`, `CLOUDINARY_UPLOAD_PRESET=social_media_posts`

**Cal.com:** pendiente — Maicol debe crear cuenta y pasar API Key + Event Type ID

## Airtable
- Base: `appaDT7uwHnimVZLM` (env `AIRTABLE_BASE_ID_MAICOL`)
- Tabla Propiedades: `tbly67z1oY8EFQoFj`
- Tabla Clientes: `tblonoyIMAM5kl2ue`
- Tabla CLIENTES_ACTIVOS: endpoint `/crm/activos`
- Estado Clientes (singleSelect): `no_contactado`, `contactado`, `en_negociacion`, `cerrado`, `descartado`
- **CRITICO**: Airtable API no permite modificar schema (singleSelect choices) con este token — hacerlo manualmente en UI

## Pendiente — Conexión número producción Maicol

Cuando Maicol active su número definitivo, seguir este orden:

### 1. YCloud
- Comprar/activar número en YCloud (misma cuenta de Arnaldo)
- Configurar webhook del número nuevo: `https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/whatsapp` (Coolify — primario)
- Obtener la API Key del número nuevo (o confirmar si es la misma key de cuenta)

### 2. Coolify — env vars
Actualizar/agregar via Coolify panel o `coolify_manager.set_env_vars()`:
- `YCLOUD_API_KEY_MAICOL` → key del número nuevo (si cambió)
- `NUMERO_BOT_MAICOL` → número nuevo (ej: `5493764XXXXXX`)
- `CHATWOOT_API_TOKEN_MAICOL` → mismo token del agente Chatwoot
- `CHATWOOT_INBOX_ID_MAICOL` → ID del inbox nuevo de Maicol en Chatwoot

### 3. Chatwoot
- Crear inbox nuevo: Ajustes → Bandejas → Agregar → tipo API → nombre "Bot Maicol - Back Urbanizaciones"
- Anotar el Inbox ID
- Configurar webhook: Ajustes → Integraciones → Webhook → URL `/clientes/arnaldo/maicol/chatwoot-webhook` → evento `message_created`

### 4. Código (yo agrego al worker de Maicol)
- Config vars Chatwoot (CHATWOOT_URL, API_TOKEN, ACCOUNT_ID, INBOX_ID)
- Funciones: `_cw_get_or_create_contact`, `_cw_get_or_create_conversation`, `_cw_send_message`, `_sincronizar_chatwoot`
- Llamada a `_sincronizar_chatwoot()` en endpoints `/whatsapp` y `/lead`
- Endpoint `POST /chatwoot-webhook` para respuestas manuales del agente

### 5. n8n
- Desactivar workflow `o4CrjByltFurUWox` (ya no hace falta — YCloud va directo a FastAPI)
- Mantener activo solo el keep-alive `kjmQdyTGFzMSfzov`

## Lecciones aprendidas
- Botones CTA YCloud no funcionan sin WABA oficial — texto + link wa.me
- Airtable singleSelect: valores deben coincidir EXACTO (case sensitive) o da 422
- Imagen_URL en Airtable es campo attachment (array), no string — enviar como `[{url: "..."}]`
- API meta de Airtable no permite editar schema con token PAT sin scope `schema.bases:write`
- rootDir Render debe apuntar al subdirectorio del monorepo
- **Tailwind modal bug**: `@apply hidden` genera `display:none !important` — `.open { @apply flex }` no lo sobreescribe. Solución: usar `display:none` / `display:flex` CSS puro en `.modal-overlay` y `.modal-overlay.open`
- **Sync CRM**: siempre editar fuente en `PROYECTO PROPIO.../dashboard-crm.html` y copiar a `DEMOS/back-urbanizaciones/crm.html` antes de hacer git add
- **Mapa SVG**: coordenadas son px absolutos sobre PNG; ViewBox crop = [VX,VY,VW,VH]; pin.cx = coord.x - VX
- **Botón guardar**: SIEMPRE resetBtn() en try Y catch — si no, queda en "Guardando..." ante cualquier error
- **Datos frescos**: todo panel que muestra data de Airtable debe hacer fetch al entrar al tab, no usar array cacheado

## ⚠️ PRODUCCIÓN ACTIVA — 2026-04-06
**Maicol ya está cargando datos reales en el CRM** (`crm.backurbanizaciones.com`).
- Cualquier cambio al CRM o al worker debe ser cuidadoso: no romper endpoints existentes, no cambiar nombres de campos Airtable, no alterar lógica de modales/tablas sin probar primero.
- Antes de modificar: leer el panel afectado, verificar que el endpoint siga funcionando.
- Zonas activas en Airtable: San Ignacio, Gdor Roca, Apóstoles, Leandro N. Alem, Posadas, Jardín América, Otra, **Lote Urbano**

**Ownership:** Cliente 100% de Arnaldo.
**How to apply:** Cambios al worker → push `master:main` → Coolify redeploy automático. Render ya NO se usa — toda la infraestructura migrada a Coolify Hostinger.
