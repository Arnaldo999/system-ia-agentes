---
name: Playbook — Airtable base + schema setup para cliente
description: Crear base Airtable con schema estándar (Leads, Propiedades, Branding, Contratos) para un cliente nuevo de Arnaldo o Mica. Incluye campos canónicos, views, y conexión al backend.
type: playbook
proyecto: compartido
tags: [airtable, schema, multi-tenant, arnaldo, mica, playbook]
version: 1
ultima_actualizacion: 2026-04-24
casos_aplicados: [maicol-back-urbanizaciones, lau, mica-demo-inmo]
stack_aplicable: [arnaldo, mica]
---

# Playbook — Airtable base + schema para cliente

> **Cuándo usar**: cliente nuevo de Arnaldo o Mica necesita una base Airtable. Bot + CRM + brandbook social automation todo usa la misma base.
>
> **NO aplica a Robert** (usa PostgreSQL). Ver playbook #4.

## 2 patrones posibles

### Patrón A — Base dedicada por cliente (Arnaldo)

Cada cliente su base:
- **Maicol** → base `appaDT7uwHnimVZLM` ("Back Urbanizaciones")
- **Lau** → base propia
- **Cliente nuevo** → base nueva

Ventajas: aislamiento total, el cliente puede dar acceso a su equipo sin ver otros clientes.

### Patrón B — Base compartida con filtros (Mica)

Una sola base `appA8QxIhBYYAHw0F` ("System IA") con múltiples tablas o un campo `tenant`:
- Todos los clientes Mica comparten base
- Tabla `Branding` filtrable por `ID Cliente`
- Tabla `Leads` filtrable por cliente

Ventajas: Mica gestiona todo desde una sola UI.

**Decisión**: cada agencia usa su patrón. Arnaldo = A, Mica = B.

---

## Schema canónico (tablas estándar)

Las 4 tablas que toda base de cliente tiene:

### 1. Tabla `Branding` (brandbook del cliente)

Usada por el worker social para generar posts + el bot WhatsApp para responder con tono del cliente.

| Campo | Tipo | Notas |
|-------|------|-------|
| `ID Cliente` | Single line text | slug único (ej: `Back_Urbanizaciones`) |
| `Nombre Comercial` | Single line text | |
| `Industria` | Single select | Inmobiliaria / Gastronomía / Turismo / Otro |
| `Servicio Principal` | Long text | |
| `Público Objetivo` | Long text | |
| `Tono de Voz` | Long text | |
| `Reglas Estrictas` | Long text | NO decir X, SÍ decir Y |
| `Estilo Visual` | Long text | minimalista / bold / retro |
| `Colores de Marca` | Single line text | hex codes, ej `#f59e0b, #0f172a` |
| `Logo` | Attachment | PNG/SVG |
| `CTA` | Single line text | "Reservar ahora", "Ver propiedades" |
| `Facebook Page ID` | Single line text | 15-16 dígitos |
| `IG Business Account ID` | Single line text | 17-18 dígitos, empieza con `17841` |
| `WhatsApp Número Bot` | Phone | formato E.164 |

### 2. Tabla `Leads` (conversaciones WhatsApp)

Cada conversación del bot WhatsApp genera un lead.

| Campo | Tipo | Notas |
|-------|------|-------|
| `ID Lead` | Autonumber | PK |
| `Teléfono` | Phone | E.164 |
| `Nombre` | Single line text | extraído por LLM |
| `Estado` | Single select | Nuevo / Contactando / Calificado / Agendado / Perdido |
| `BANT — Presupuesto` | Single line text | |
| `BANT — Timing` | Single line text | |
| `BANT — Autoridad` | Single line text | |
| `BANT — Necesidad` | Long text | |
| `Producto de interés` | Link to another record | FK a `Propiedades` / `Platos` / etc. |
| `Última interacción` | Date/time | auto-update por bot |
| `Resumen conversación` | Long text | generado por LLM al final |
| `Notas humanas` | Long text | equipo agrega comentarios |

### 3. Tabla `Propiedades` / `Productos` / `Servicios` (catálogo)

Lo que el cliente ofrece. Nombre de la tabla según vertical:

**Inmobiliaria**: `Propiedades`

| Campo | Tipo |
|-------|------|
| `Nombre` | Single line text |
| `Tipo` | Single select (Casa / Departamento / Terreno / Local) |
| `Ubicación` | Single line text |
| `Precio` | Currency |
| `Moneda` | Single select (USD / ARS / PYG) |
| `Superficie m²` | Number |
| `Dormitorios` | Number |
| `Disponible` | Checkbox |
| `Descripción` | Long text |
| `Fotos` | Multiple attachments |
| `Link listado` | URL |

**Gastronomía**: `Platos` (nombre, categoría, precio, descripción, alérgenos, foto, disponible)

**Turismo**: `Paquetes` (destino, duración, precio por persona, incluye, no incluye, fotos, disponible)

### 4. Tabla `Contratos` (solo si cliente vende/alquila formal)

Para inmobiliarias Mica/Arnaldo que gestionan contratos:

| Campo | Tipo |
|-------|------|
| `ID Contrato` | Autonumber |
| `Lead` | Link to Leads |
| `Propiedad` | Link to Propiedades |
| `Tipo` | Single select (Venta / Alquiler) |
| `Monto` | Currency |
| `Fecha firma` | Date |
| `Estado` | Single select (Pendiente / Firmado / Escriturado) |
| `Notas` | Long text |

(Modelo v3 persona única con roles solo aplica si CRM v3 en Airtable — ver playbook #3).

---

## Pasos exactos — base nueva cliente Arnaldo (total ~30 min)

### Precondiciones

- [ ] Cliente firmó, vertical identificado (inmobiliaria/gastro/turismo)
- [ ] Cuenta Airtable del cliente creada (él paga su plan si supera free tier)
- [ ] Decidido slug `ID Cliente` (ej: `Back_Urbanizaciones`, `Cesar_Posada_Turismo`)

### Paso 1 — Clonar base template (3 min)

En Airtable:
1. Abrir base template que corresponda (Maicol para inmobiliaria Arnaldo, etc.)
2. Workspace → **"Duplicate base"** → elegir workspace del cliente
3. Renombrar: `<Cliente> — CRM y Brandbook`

**Alternativa**: copiar schema desde base modelo via API (script pendiente).

### Paso 2 — Vaciar tablas clonadas (2 min)

Las tablas traen datos del cliente anterior. Eliminar:
- Todos los registros de `Leads` (eran conversaciones ajenas)
- Todos los registros de `Propiedades` / `Platos` (catálogo anterior)
- **Mantener schema**: campos, views, automatizaciones

En Airtable: seleccionar todo → `Ctrl+A` → Delete.

### Paso 3 — Popular tabla `Branding` (10 min)

Crear 1 registro con datos del cliente:
- ID Cliente, Nombre Comercial, Industria, Servicio
- Público Objetivo (2-3 líneas)
- Tono de Voz (formal/cercano/técnico)
- Reglas Estrictas ("Nunca dar precios en público", "Siempre ofrecer visita")
- Estilo Visual (palabras clave del feed IG del cliente)
- Colores de Marca (copiar del logo o paleta del cliente)
- Adjuntar Logo
- CTA

**Pro tip**: pedir al cliente que complete un formulario Airtable (public form) con estos campos en vez de preguntar uno por uno por WhatsApp.

### Paso 4 — Obtener tokens Airtable (3 min)

En `airtable.com/create/tokens`:
1. Create personal access token
2. Nombre: `Cliente — <Nombre>`
3. Scopes:
   - `data.records:read`
   - `data.records:write`
   - `schema.bases:read`
4. Access: SOLO la base del cliente (no dar acceso a otras)
5. Create → copiar token (empieza con `pat...`)

**Guardar en `.env` del backend** con prefijo correcto:
```
ARNALDO_AIRTABLE_TOKEN_CLIENTE_<SLUG>=pat...
# o Mica:
MICA_AIRTABLE_TOKEN=pat...  # ya existe, no regenerar
```

Ver `feedback_REGLA_env_quoting_y_lookup.md` — buscar token existente ANTES de regenerar.

### Paso 5 — Conectar worker al Airtable (5 min)

En el worker del cliente (playbook #1), configurar:

```python
AIRTABLE_BASE = "app..."  # base_id del cliente
AIRTABLE_TABLE_LEADS = "tbl..."
AIRTABLE_TABLE_BRANDING = "tbl..."
AIRTABLE_TABLE_CATALOG = "tbl..."
AIRTABLE_TOKEN = os.getenv("ARNALDO_AIRTABLE_TOKEN_CLIENTE_SLUG")
```

Para obtener `tbl...` IDs:
- Abrir la tabla en Airtable → URL contiene `tblXXXXXXXX`
- O usar API: `GET https://api.airtable.com/v0/meta/bases/{base_id}/tables`

### Paso 6 — Popular catálogo inicial (10-30 min)

Cliente carga sus primeros 10-20 productos/propiedades.
- **Pro tip**: si el cliente tiene un Excel, usar **CSV import de Airtable** (drag & drop).
- Validar que todos los registros tienen los campos `Nombre`, `Precio`, `Disponible`, `Fotos`.

### Paso 7 — Smoke test con bot (5 min)

1. Disparar webhook del bot con mensaje simulado
2. Verificar que el bot lee `Branding` (tono correcto) + `Catalog` (muestra productos reales)
3. Crear lead de prueba, chequear que aparece en tabla `Leads`
4. Verificar campos BANT se populan

---

## Gotchas conocidos

### Gotcha #1 — Airtable API limits

Free tier: 5 req/seg. Con bots activos podés pegarte.

**Solución**: batch writes cuando sea posible (`POST /v0/.../records` acepta array de hasta 10 registros).

Pro plan: 5 req/seg también, pero más records totales.

### Gotcha #2 — Single select con valor no existente

**Síntoma**: al escribir estado "Nuevo" en Leads, Airtable rechaza con 422 si ese valor no está pre-definido en el select.

**Solución**: definir TODAS las opciones del select al crear el campo. O usar `Single line text` si valores son variables.

### Gotcha #3 — Linked records esperan array de record IDs

Si querés vincular Lead a Propiedad:

MAL: `"Producto de interés": "Casa 123"` (texto)
BIEN: `"Producto de interés": ["recABC123"]` (array con record ID)

### Gotcha #4 — Filter formula URL-encoded

Para filtrar por campo con espacio en nombre: `{ID Cliente}='SLUG'` →

```
filterByFormula=%7BID%20Cliente%7D%3D%27SLUG%27
```

Usar `encodeURIComponent()` siempre.

### Gotcha #5 — Mica base compartida — tenant field

En la base Mica `appA8QxIhBYYAHw0F`, múltiples clientes comparten tablas. Siempre filtrar por campo `tenant` o `ID Cliente`.

**Valor `subnicho='mixto'`** es el tenant standard de Mica para demo multi-vertical (ver `feedback_crm_v3_mica_persona_unica.md`).

### Gotcha #6 — Attachments limit

Campo attachment acepta URLs públicas (sube el archivo automáticamente) pero:
- URL debe ser HTTPS accesible sin auth
- Cloudinary OK, Google Drive con share link SÍ funciona pero a veces Airtable no descarga
- Tamaño max: 5MB por archivo (free), 20MB (Pro)

### Gotcha #7 — Formulas con campos renombrados

Si renombrás un campo, Airtable actualiza referencias en formulas automáticamente. PERO las API calls con `filterByFormula={ID Cliente}` rompen (hardcoded).

**Solución**: actualizar el worker con el nuevo nombre de campo. O usar IDs en vez de nombres (cuando la API lo soporte).

---

## Checklist antes de dar por lista la base

- [ ] Schema clonado de template (no escrito desde cero)
- [ ] Tablas vacías de datos del cliente anterior
- [ ] `Branding` populada con 1 registro completo del nuevo cliente
- [ ] Logo adjuntado, colores definidos
- [ ] Token Airtable generado, scoped a esta base
- [ ] Token en `.env` / Coolify del backend correcto (con prefijo)
- [ ] Worker del cliente lee base correctamente
- [ ] Catálogo mínimo populado (10+ registros)
- [ ] Smoke test bot: tono + catalog OK
- [ ] Cliente tiene acceso edit a su base (si es su patrón A)

---

## Archivos que tocás

```
Airtable (externo)                           ← base + tablas
.env del backend o Coolify env vars          ← token cliente
workers/clientes/{agencia}/{cliente}/worker.py ← config base_id/table_id
```

---

## Cuándo este playbook se actualiza

- Cliente pide campos custom que no estaban → evaluamos si agregar al schema estándar
- Descubrimos nueva integración (ej: Airtable Automations para Slack) → agregar sección
- Cambio en API Airtable (deprecation) → actualizar

---

## Histórico de descubrimientos

- **Anterior a 2026-04** — Maicol (`appaDT7uwHnimVZLM`) y Lau (base propia) como patrones Arnaldo.
- **2026-04-22** — CRM v3 Mica en base `appA8QxIhBYYAHw0F` — replicación persona única (Airtable edition).
- **2026-04-24** — Mica IDs strings `rec...`, NO parseInt (ver `feedback_crm_v3_mica_persona_unica.md`).

---

## Referencias cruzadas

- `wiki/conceptos/airtable.md` — referencia general
- `.claude/skills/airtable-expert/` — skill de operaciones Airtable
- `feedback_crm_v3_mica_persona_unica.md` — lecciones CRM Mica
- `feedback_REGLA_env_quoting_y_lookup.md` — gestión tokens
- Bugs: `bugs_integraciones.md` (singleSelect, date)
