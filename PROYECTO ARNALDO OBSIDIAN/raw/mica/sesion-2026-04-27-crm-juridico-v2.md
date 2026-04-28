---
title: Sesión Claude 2026-04-27 — CRM Jurídico v2 Mica (INPI marcas, iteración intensiva)
date: 2026-04-27
type: sesion-claude
proyecto: mica
tags: [proyecto-mica, system-ia, crm-juridico, airtable, dark-mode, upload, socios, dashboard]
---

# Sesión 2026-04-27 — CRM Jurídico v2 Mica

Sesión de iteración intensiva sobre el CRM de Estudio de Marcas (INPI) de Mica. 11 commits en el día, todo co-diseñado con Mica vía WhatsApp en tiempo real. Base de datos dedicada `appSjeRUoBGZo5DtO`.

## Contexto

La sesión previa (2026-04-26) había iniciado el CRM con base Airtable dedicada, Plantillas Email, flujo Propuestas→Marcas, y primeras secciones funcionales. Esta sesión arrancó con el CRM operativo y Mica probando en vivo, dando feedback detallado de flujo y UX.

## Commits en orden cronológico

### 1. `73802e7` — fix: aceptarPropuesta usa campos válidos
- Campo `Descripción Productos/Servicios` no existe en tabla Marcas.
- Fix: usar `Notas` en su lugar.

### 2. `4913ee3` — fix: pasarLeadAPropuesta usa campos válidos
- Campo `Notas Internas` no existe en tabla Propuestas.
- Fix: usar `Notas` + `Lead Origen` (linkedRecord correcto).

### 3. `62080a3` — feat: filtración Leads (activos/nutrición) + Propuestas (para hacer/enviadas)
- Leads separados en 2 listas: Activos (calientes, en seguimiento) vs. Nutrición (fríos, no urgentes).
- Propuestas separadas en: Para Hacer vs. Ya Enviadas.
- Botón "Pasar a Propuesta" en cada lead activo.

### 4. `c80d5a9` — feat: modal Aceptar Propuesta con datos titular + socios + marca
- Al marcar Propuesta como Aceptada, abre un PopUp para completar:
  - Datos del Titular: nombre, DNI, CUIT, estado civil, dirección completa.
  - Socios de la Marca (dinámico, N socios): nombre, DNI/CUIT, porcentaje de participación.
  - Datos de la Marca: nombre, clase, rubro.
  - Nota Poder (campo de texto).
- Endpoint `POST /crm/propuestas/{id}/aceptar-con-datos`.
- Crea en Airtable: registro Cliente, registro Marca (linkedRecord), N registros Socios (tabla `Socios_Marca`).

### 5. `80ac060` — feat: modo oscuro/claro con toggle + persistencia + auto-detect SO
- Toggle en navbar (ícono luna/sol).
- Persistencia en `localStorage.crm_theme`.
- Auto-detect con `prefers-color-scheme` al primer ingreso.
- Implementado con CSS variables en `:root` + selector `[data-theme="dark"]`.
- Override de `background: white` inline: `[data-theme="dark"] [style*="background: white"] { background: var(--surface) !important; }`.

### 6. `20f8bd2` — feat: Dashboard prioriza Alertas operativas (vencimientos próximos)
- Dashboard reestructurado para mostrar primero las marcas con plazo urgente (≤30 días).
- Función `renderDashboardAlertas()` agrupa por urgencia.

### 7. `863a613` — feat: rediseño Dashboard 2 columnas (notifs verde+azul + secciones)
- Layout 2 columnas:
  - Izquierda: notificaciones CON plazo (verde, urgentes).
  - Derecha: notificaciones SIN plazo (azul, informativas).
- 8 cards de sección (Leads, Propuestas, Marcas, Comunicaciones, Oposiciones, Trámites, Análisis, Plantillas).
- Arnaldo propuso layout, Mica aprobó.

### 8. `a095867` — fix: ficha-completa lee socios por reverse-link
- `filterByFormula` sobre campos linkedRecord retorna 0 resultados en ciertos contextos de Airtable.
- Fix: leer el array `Socios_Marca` (reverse-link) en el record de la Marca → GET individual de cada socio.
- Endpoint `GET /crm/marcas/{id}/ficha-completa` actualizado.

### 9. `e6b0730` — feat: ficha modificable de marca + marcar presentada directo
- Modal `modalFichaMarca` con todos los campos del titular + socios editables.
- Botón "Datos Listos para INPI" (toggle en Airtable).
- Columna extra en lista Marcas: muestra estado visual (pendiente / listo).

### 10. `a4a741f` — feat: Nota Poder + Datos para Cargar + Listo + contexto en alertas
- Campo "Nota Poder" en modal Datos para Cargar.
- Botón "Ver Datos para Cargar" al lado de cada marca (abre ficha con datos precargados).
- Botón "Listo ✅" al lado opuesto (toggle `Datos Listos para INPI`).
- Alertas en Dashboard incluyen nombre del trámite notificado al lado del nombre de marca.

### 11. `3c185d8` (esta sesión continuó más tarde) — feat(voz): agente voz inmobiliaria Robert
- Sesión paralela para Robert — no forma parte del CRM Jurídico.

## Patrones técnicos descubiertos

### 1. Airtable reverse-link sobre filterByFormula
`filterByFormula` sobre campos linkedRecord puede retornar 0 resultados aunque el link exista.
**Solución**: leer el campo reverse-link del record padre (array de IDs) → iterar GET individual de cada ID hijo.

### 2. Upload pipeline real (no placeholder)
`browser → FormData POST /crm/upload → FastAPI UploadFile → /uploads/ estático → URL pública → Airtable multipleAttachments URL`
Airtable descarga el archivo desde la URL pública. El frontend NO debe enviar base64.

### 3. Dark mode con CSS variables + data-theme
```css
:root { --bg: #f8fafc; --surface: #fff; ... }
[data-theme="dark"] { --bg: #0f172a; --surface: #1e293b; ... }
[data-theme="dark"] [style*="background: white"] { background: var(--surface) !important; }
```
Toggle: `document.documentElement.setAttribute('data-theme', theme)` + `localStorage`.

### 4. Airtable PATCH vs typecast en singleSelect
PATCH directo de un singleSelect con valor nuevo da 422 si la opción no existe aún.
**Solución**: usar `typecast: True` en la creación (Airtable crea el choice automáticamente). Para updates posteriores, el choice ya existe.

## Pendientes del CRM Jurídico v2

- [ ] SMTP real (emails actualmente simulados con preview HTML).
- [ ] Subir Excel del Boletín de Marcas para análisis automático.
- [ ] Bot WhatsApp para captación de leads entrantes.
- [ ] n8n workflow para recordatorios de vencimientos por email.
- [ ] CRUD completo desde UI (editar/eliminar con botones conectados a API).

## Tabla Airtable nueva creada en esta sesión

**Socios_Marca** (`tblX4NQCEzFZRwEar`) — 15 campos:
- Nombre Socio, DNI, CUIT, Porcentaje Participación, Marca (linkedRecord → Marcas), Titular (linkedRecord → Clientes_Estudio), Nota, Estado, Tipo Socio, País, Provincia, Ciudad, CP, Email, Teléfono.

## Campos nuevos en tablas existentes

- **Clientes_Estudio**: DNI, CUIT, País, Estado Civil, Ciudad, Provincia, Código Postal, Adjunto DNI.
- **Marcas**: Rubro, Porcentaje Participación Titular, Nota Poder, Datos Listos para INPI (checkbox), Fecha Datos Listos.
- **Comunicaciones_Oposicion**: Tipo Notificación (Recomendación de Oposición / Vista Administrativa 30 días / Vista Administrativa 10 días / Notificación Simple).

## Archivos de código

- Frontend: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/demos-system-ia/dev/crm-juridico-v2.html`
- Router backend: `workers/clientes/system_ia/demos/juridico/router.py`
- Static uploads: `/uploads/` montado en `main.py` como `StaticFiles`.
