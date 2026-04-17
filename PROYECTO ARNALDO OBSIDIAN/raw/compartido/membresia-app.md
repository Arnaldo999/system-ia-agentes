# MembresIA — App de Gestión de Membresías

**Estado**: App frontend lista. n8n pendiente (VPS vencido, retomar cuando se renueve).

---

## Descripción del Producto

PWA (Progressive Web App) white-label para negocios con suscripciones/membresías (gimnasios, academias de baile, coworkings, etc.). El cliente la instala en su celular como una app nativa.

**Propuesta de valor**: Alertas automáticas, semáforo de morosidad, cumpleaños, historial de pagos, acceso móvil — en vez de papel o planilla.

---

## Arquitectura

```
Frontend (HTML PWA) → n8n webhooks → Airtable (datos del negocio)
                   → Supabase (login/auth de System IA)
```

| Capa | Tech | Responsabilidad |
|------|------|-----------------|
| Frontend | HTML + Tailwind (PWA) | UI, session, llamadas a webhooks |
| Auth | Supabase (`comercios` table) | Login de clientes de System IA |
| Datos miembros | Airtable (1 base por cliente) | Clientes + Pagos del negocio |
| Automatización | n8n | Webhooks CRUD + lógica de negocio |
| Hosting | Vercel | Servir los HTML estáticos |

### Multi-tenant
- Cada cliente de System IA tiene su propia **base de Airtable**
- El `airtable_base_id` se guarda en Supabase columna `comercios.airtable_base_id`
- Un solo workflow n8n para todos los clientes — recibe `base_id` dinámico desde el frontend

---

## Archivos del Proyecto

```
/PROPUESTAS/PROPUESTAS LOCALES/App Suscripciones-Membresias/
├── login.html      ← Pantalla de login
├── app.html        ← Dashboard principal (PWA)
├── manifest.json   ← Config PWA (nombre, icono, standalone)
└── sw.js           ← Service Worker (cache offline)
```

---

## Login

**Credenciales demo**: `usuario: demo` / `password: demo123`
- Entra directo sin tocar la red
- Carga datos de `DEMO_CLIENTES` hardcodeados en app.html
- Base ID: `'DEMO'`

**Login real**: POST a `https://n8n.arnaldoayalaestratega.com/webhook/membresia-login`
- Body: `{ usuario, password }`
- Response esperada: `{ ok: true, activo: true, id, nombre_negocio, airtable_base_id, plan }`
- Sesión guardada en localStorage con 24h de expiración

**Mapeo Supabase → Login**:
- `slug` del comercio = campo usuario
- `pin` del comercio = campo password

---

## Supabase — Tabla `comercios`

Columnas relevantes:
- `slug` → usado como username
- `pin` → usado como password
- `nombre_local` → nombre del negocio (mostrado en app)
- `tipo_cuenta` → plan del cliente
- `activo` → si está bloqueado o no
- `airtable_base_id` → ID de la base Airtable del cliente (TEXT, nullable) ← AGREGADA

---

## Airtable — Estructura por cliente

### Base de ejemplo: "Gimnasio Prueba"
- Base ID: `appKi7rSkhf7wKwkR`

### Tabla: `Clientes`
| Campo | Tipo |
|-------|------|
| nombre | Text (primary) |
| telefono | Phone |
| email | Email |
| fecha_nacimiento | Date |
| plan | Single select |
| monto | Currency |
| estado | Single select: Activo / Inactivo / Vencido |
| fecha_inicio | Date |
| fecha_vencimiento | Date |
| metodo_pago | Single select |
| notas | Long text |

### Tabla: `Pagos`
| Campo | Tipo |
|-------|------|
| descripcion | Text (primary — no puede ser linked record) |
| cliente | Linked record → Clientes |
| fecha_pago | Date |
| monto | Currency |
| metodo | Single select |
| periodo | Text (ej: "Marzo 2026") |
| notas | Long text |

**Nota**: La columna `descripcion` de Pagos la popula n8n automáticamente con algo como `"Pago - Juan Pérez - Marzo 2026"`. Es una limitación de Airtable: el primer campo siempre es texto y no puede ser linked record.

---

## App — Pantallas y Funciones

### Dashboard (Inicio)
**Row 1 — KPIs de estado** (4 cards):
- Activos (% del total)
- Vencidos ($ sin cobrar)
- Vencen pronto (próximos 7 días)
- Total miembros (# inactivos)

**Row 2 — KPIs financieros** (3 cards):
- Ingreso mensual (solo activos)
- Ingreso potencial (todos)
- Ticket promedio

**Row 3** (3 columnas):
- Tipos de plan (gráfico doughnut — Chart.js)
- Vencen esta semana
- Estado general (semáforo) + Cumpleaños hoy

### Clientes
- Filtros: Todos / Activos / Vencen pronto / Vencidos / Inactivos
- PC: tabla con botón de editar por fila
- Mobile: tarjetas
- **Sin botón de eliminar** (datos históricos)
- Modal para crear/editar cliente

### Alertas
- Cumpleaños hoy
- Cumpleaños esta semana
- Vencen hoy
- Vencen en 7 días
- Vencidos sin renovar
- Botón de WhatsApp por alerta (mensaje pre-armado)

---

## Lógica de Estado (`getEstado`)

```javascript
// Calcula estado real desde fecha_vencimiento (overrides el valor guardado)
// Excepción: si estado guardado es "Inactivo", lo respeta
function getEstado(c) {
    if (c.estado === 'Inactivo') return 'Inactivo';
    const hoy = new Date();
    const vence = new Date(c.fecha_vencimiento);
    const diff = Math.ceil((vence - hoy) / (1000 * 60 * 60 * 24));
    if (diff < 0) return 'Vencido';
    if (diff === 0) return 'Vence hoy';
    if (diff <= 7) return 'Vence pronto';
    return 'Activo';
}
```

---

## n8n — Webhooks Pendientes

**Base URL**: `https://n8n.arnaldoayalaestratega.com/webhook/`

| Webhook | Método | Descripción |
|---------|--------|-------------|
| `membresia-login` | POST | Busca en Supabase por usuario/password, devuelve `airtable_base_id` |
| `membresia-listar` | POST | Lista clientes de Airtable con `base_id` dinámico |
| `membresia-crear` | POST | Crea cliente nuevo en Airtable |
| `membresia-editar` | POST | Actualiza cliente existente |

### Payload estándar desde frontend:
```json
{
  "base_id": "appKi7rSkhf7wKwkR",
  "accion": "listar",
  ...datos específicos
}
```

### Workflow de login (lógica):
1. Recibe `{ usuario, password }`
2. Busca en Supabase `comercios` WHERE `slug = usuario` AND `pin = password`
3. Si no existe → `{ ok: false, mensaje: "Usuario o contraseña incorrectos" }`
4. Si `activo = false` → `{ ok: true, activo: false }`
5. Si todo ok → `{ ok: true, activo: true, id, nombre_negocio: nombre_local, airtable_base_id, plan: tipo_cuenta }`

---

## Layout

- **PC**: Sidebar 220px + main area con header
- **Mobile**: Bottom navigation + FAB button (oculto en PC con CSS media query)
- **Tema**: Dark (#0a0f1e), glassmorphism, gradiente indigo/purple
- **Fonts**: Inter (body) + Orbitron (logo)
- **Libs**: Tailwind CDN, Font Awesome, Chart.js

---

## Próximos Pasos (cuando se renueve el VPS)

1. Crear workflow `membresia-login` en n8n (Supabase lookup)
2. Crear workflow `membresia-listar` (Airtable GET dinámico)
3. Crear workflow `membresia-crear` (Airtable POST)
4. Crear workflow `membresia-editar` (Airtable PATCH)
5. Guardar `airtable_base_id = 'appKi7rSkhf7wKwkR'` en Supabase para el comercio de prueba
6. Probar con usuario real (no demo)
7. Deploy en Vercel
8. Nombrar la base de Airtable con el nombre del cliente real

---

## Notas de Diseño

- No hay botón eliminar — los datos se conservan como historial
- "Pausado" fue renombrado a "Inactivo" en toda la app
- El FAB (botón flotante de nuevo cliente) solo aparece en mobile
- Demo mode carga datos locales hardcodeados, no toca la red
