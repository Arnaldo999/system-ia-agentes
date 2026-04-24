# Setup Airtable — Demo Estudio Jurídico Mica

**Base destino**: `appSjeRUoBGZo5DtO` (Estudio Jurídico Demo — base DEDICADA, propiedad Mica/System IA)
**Tenant slug**: `mica-demo-juridico`
**Subnicho**: `juridico` (nuevo, paralelo a `inmobiliaria`)
**Creado**: 2026-04-24
**Pedido**: cliente de Mica que necesita CRM con alertas de vencimientos de trámites legales + bot WhatsApp para abogados.

---

## Tablas a crear en Airtable

> **Pre-paso**: la base ya viene con una "Table 1" vacía por default (3 registros sin nada). **Eliminala** o renombrala como `Estudios_Juridicos` para no dejar basura.
>
> Crear estas 5 tablas en la base **dedicada** `appSjeRUoBGZo5DtO` ("Estudio Jurídico Demo").
>
> Como la base es dedicada al demo jurídico, **NO hace falta el campo `Tenant`** (cada base = 1 demo aislado). Esto es distinto al CRM inmobiliario Mica que comparte base `appA8QxIhBYYAHw0F` con campo Tenant.
>
> Cuando Arnaldo quiera replicar para sus propios clientes: duplicar esta base entera en su workspace → setear nuevo `MICA_DEMO_JURIDICO_BASE_ID` env var → listo.

### 1. Tabla `Estudios_Juridicos`

Cabecera del estudio cliente.

| Campo | Tipo | Notas |
|-------|------|-------|
| `Nombre Estudio` | Single line text | ej "Estudio Demo Jurídico" |
| `Razón Social` | Single line text | |
| `CUIT` | Single line text | |
| `Email Contacto` | Email | |
| `Teléfono` | Phone | |
| `Dirección` | Single line text | |
| `Ciudad` | Single line text | |
| `Provincia` | Single line text | |
| `Logo` | Attachment | opcional |
| `Activo` | Checkbox | default true |
| `Fecha Alta` | Date | auto |

### 2. Tabla `Abogados`

Equipo del estudio que recibe alertas y agenda con clientes.

| Campo | Tipo | Notas |
|-------|------|-------|
| `Estudio` | Link to `Estudios_Juridicos` | FK |
| `Nombre Completo` | Single line text | |
| `Especialidad` | Single select | Civil / Laboral / Penal / Comercial / Familia / Tributario / Otros |
| `Teléfono WhatsApp` | Phone | E.164 (`+5493764999999`) — usado por bot |
| `Email` | Email | |
| `Matrícula` | Single line text | T° XXX F° YYY |
| `Activo` | Checkbox | default true |
| `Recibe Alertas WhatsApp` | Checkbox | default true |
| `Notas` | Long text | |

### 3. Tabla `Clientes_Estudio`

Personas físicas/jurídicas que son clientes del estudio (NO confundir con Mica = cliente nuestro).

| Campo | Tipo | Notas |
|-------|------|-------|
| `Estudio` | Link to `Estudios_Juridicos` | FK |
| `Tipo` | Single select | Persona Física / Persona Jurídica |
| `Nombre Completo / Razón Social` | Single line text | |
| `DNI / CUIT` | Single line text | |
| `Teléfono WhatsApp` | Phone | E.164 — alertas van por acá |
| `Email` | Email | |
| `Dirección` | Single line text | |
| `Abogado Asignado` | Link to `Abogados` | quién lleva el caso principal |
| `Notas Iniciales` | Long text | |
| `Recibe Alertas WhatsApp` | Checkbox | default true (cliente puede optar no recibir) |
| `Fecha Alta` | Date | auto |
| `Estado` | Single select | Activo / Inactivo / Cerrado |

### 4. Tabla `Tramites` (la más importante)

Cada trámite tiene su vencimiento independiente.

| Campo | Tipo | Notas |
|-------|------|-------|
| `Estudio` | Link to `Estudios_Juridicos` | FK |
| `Cliente` | Link to `Clientes_Estudio` | a quién pertenece |
| `Abogado Responsable` | Link to `Abogados` | quién lo lleva |
| `Tipo Trámite` | Single line text | TEXTO LIBRE (jurídico es muy heterogéneo: "Audiencia preliminar", "Vencimiento contestación demanda", "Apelación ART", "Renovación poder", etc.) |
| `Categoría` | Single select | Civil / Laboral / Penal / Comercial / Familia / Tributario / Administrativo / Otros |
| `Descripción` | Long text | detalle libre |
| `Fecha Inicio` | Date | cuándo arrancó |
| **`Fecha Vencimiento`** | **Date** | **CRÍTICO — driver del sistema de alertas** |
| `Estado` | Single select | Activo / Vencido / Cumplido / Cerrado / Pausado |
| `Días Para Vencer` | Formula | `DATETIME_DIFF({Fecha Vencimiento}, TODAY(), 'days')` |
| `Urgencia` | Formula | `IF({Días Para Vencer} < 0, "🔴 VENCIDO", IF({Días Para Vencer} <= 1, "🔴 HOY/MAÑANA", IF({Días Para Vencer} <= 7, "🟠 ESTA SEMANA", IF({Días Para Vencer} <= 30, "🟡 ESTE MES", "🟢 OK"))))` |
| `Documentos` | Multiple attachments | PDFs, escritos |
| `Fuero / Juzgado` | Single line text | |
| `N° Expediente` | Single line text | |
| `Notas Internas` | Long text | solo equipo del estudio |
| `Notas Cliente` | Long text | lo que sí ve el cliente en alertas |
| `Fecha Última Alerta` | Date | última vez que se le avisó al cliente |
| `Fecha Creación` | Date | auto |
| `Fecha Última Modificación` | Last modified time | auto |

### 5. Tabla `Alertas_Enviadas`

Bitácora de cada alerta WhatsApp disparada (al cliente del estudio, NO al abogado).

| Campo | Tipo | Notas |
|-------|------|-------|
| `Trámite` | Link to `Tramites` | FK |
| `Cliente Destinatario` | Link to `Clientes_Estudio` | redundante pero útil para queries |
| `Fecha Envío` | Date/time | |
| `Días Anticipación` | Number | 30 / 15 / 7 / 3 / 1 / 0 (vencido hoy) / -N (post-vencimiento) |
| `Mensaje Enviado` | Long text | texto exacto que recibió el cliente |
| `Canal` | Single select | WhatsApp / Email / SMS |
| `Estado Envío` | Single select | Enviado / Entregado / Leído / Falló |
| `Respuesta Cliente` | Long text | si respondió algo |
| `Fecha Respuesta` | Date/time | |
| `Confirmación Cliente` | Single select | Confirmó / Rechazó / Sin respuesta |
| `Notas` | Long text | |

---

## Datos seed para la demo

Una vez creadas las 5 tablas, populá con esto para que el demo no esté vacío:

### 1 estudio

```
Nombre Estudio: Estudio Demo Jurídico
Razón Social: Estudio Demo Jurídico SAS
Email Contacto: contacto@estudiodemo.com.ar
Teléfono: +54 11 4000-0000
Ciudad: Buenos Aires
Provincia: CABA
Activo: true
```

### 3 abogados

```
1. Dra. María González — Civil — +54 9 11 5555-1111
2. Dr. Pablo Ramírez — Laboral — +54 9 11 5555-2222
3. Dr. Carlos Méndez — Penal — +54 9 11 5555-3333
```

### 5 clientes del estudio

```
1. Juan Pérez (Persona Física) — DNI 25.000.000 — abogado: María González
2. Distribuidora SRL (Persona Jurídica) — CUIT 30-XXXXXX — abogado: Pablo Ramírez
3. Laura Martínez (Persona Física) — DNI 30.000.000 — abogada: María González
4. Logística SA (Persona Jurídica) — CUIT 30-YYYYY — abogado: Carlos Méndez
5. Roberto Silva (Persona Física) — DNI 28.000.000 — abogado: Pablo Ramírez
```

### 8 trámites con vencimientos diversos (realistas para mostrar las urgencias)

```
1. Juan Pérez — Audiencia preliminar — Civil — vence 2026-04-26 (HOY/MAÑANA 🔴)
2. Distribuidora SRL — Contestación demanda — Comercial — vence 2026-04-29 (ESTA SEMANA 🟠)
3. Laura Martínez — Renovación poder — Civil — vence 2026-04-23 (VENCIDO 🔴)
4. Logística SA — Apelación ART — Laboral — vence 2026-05-15 (ESTE MES 🟡)
5. Roberto Silva — Audiencia testimonial — Penal — vence 2026-05-08 (ESTE MES 🟡)
6. Juan Pérez — Vencimiento prescripción — Civil — vence 2026-06-30 (OK 🟢)
7. Distribuidora SRL — Presentación balance — Comercial — vence 2026-05-01 (ESTA SEMANA 🟠)
8. Laura Martínez — Inscripción registro — Civil — vence 2026-04-25 (HOY/MAÑANA 🔴)
```

---

## Tenant en Supabase (control de licencia/pago)

Después de crear las tablas, agregar el tenant en Supabase `tenants` para que aparezca en tu admin Mica (`admin/clientes.html`):

```sql
INSERT INTO tenants (slug, nombre, subnicho, estado_pago, fecha_vence, api_prefix, activo)
VALUES (
  'mica-demo-juridico',
  'Demo Estudio Jurídico (Mica)',
  'juridico',
  'demo',
  NULL,
  '/clientes/system_ia/demos/juridico',
  true
);
```

---

## Env vars en Coolify (Easypanel Mica)

```bash
# Ya existentes (reusar):
AIRTABLE_API_KEY=patXXXXX  # MICA_AIRTABLE_TOKEN

# NUEVAS para el demo jurídico (base dedicada):
MICA_DEMO_JURIDICO_BASE_ID=appSjeRUoBGZo5DtO   # base "Estudio Jurídico Demo"
MICA_DEMO_JURIDICO_TABLE_ESTUDIOS=tblXXX...     # ID de tabla Estudios_Juridicos
MICA_DEMO_JURIDICO_TABLE_ABOGADOS=tblXXX...
MICA_DEMO_JURIDICO_TABLE_CLIENTES=tblXXX...
MICA_DEMO_JURIDICO_TABLE_TRAMITES=tblXXX...
MICA_DEMO_JURIDICO_TABLE_ALERTAS=tblXXX...
```

Para obtener los `tblXXX...` IDs: abrir cada tabla en Airtable → la URL contiene el ID después de `/tbl`.

⚠️ **Recordatorio Coolify** (gotcha conocido): al crear env vars NO marcar "Is Preview". Después del save, force rebuild del backend (`force=true`). Ver `feedback_REGLA_coolify_cache_force.md`.

---

## URL final del CRM jurídico (Coolify, NO Vercel)

**Producción** (Coolify Hostinger Arnaldo):
```
https://agentes.arnaldoayalaestratega.cloud/system-ia/dev/crm-juridico-v1.html
```

**Backend API** (mismo Coolify):
```
https://agentes.arnaldoayalaestratega.cloud/clientes/system_ia/demos/juridico/crm/health
```

> Decisión arquitectónica: este demo se sirve desde **Coolify**, no Vercel — siguiendo regla `feedback_REGLA_coolify_default.md` (2026-04-22). El HTML vive en `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/` y se sirve via `app.mount("/system-ia", StaticFiles(...))` en `main.py`. Cuando hagas `git push`, Coolify rebuildea y la URL queda LIVE.

**Local (testing)**:
```
http://localhost:8000/system-ia/dev/crm-juridico-v1.html
```

---

## Próximos pasos (cuando termines este setup)

1. ✅ Crear las 5 tablas en Airtable
2. ✅ Popular con datos seed (1 estudio + 3 abogados + 5 clientes + 8 trámites)
3. ✅ Insertar tenant en Supabase
4. ✅ Cargar 5 env vars en Coolify Easypanel
5. ✅ Restart del backend (`force=true` por bug Coolify cache)
6. → Smoke test: abrir URL del CRM, verificar que carga los datos
7. → **Mañana**: hacer el bot WhatsApp para abogados (agendar reuniones + consultar vencimientos)
