---
name: Playbook — CRM / Panel HTML+Tailwind CDN+JS vanilla
description: Patrón estándar para construir CRM, panel admin o dashboard para un cliente. HTML+Tailwind CDN+JS vanilla, sin build step. Aplica al CRM v3 (persona única + contratos polimórficos) para los 3 proyectos.
type: playbook
proyecto: compartido
tags: [crm, html, tailwind, frontend, panel, playbook]
version: 1
ultima_actualizacion: 2026-04-24
casos_aplicados: [crm-v3-robert, crm-v3-mica, crm-agencia-lovbot, admin-lovbot, back-urbanizaciones]
---

# Playbook — CRM / Panel HTML+Tailwind CDN+JS vanilla

> **Cuándo usar**: cliente pide CRM, panel admin, dashboard, formulario, landing interactiva — cualquier UI que consume datos del backend. **NO usar** para propuestas estáticas públicas (ver playbook #6).

## Stack obligatorio (no se negocia)

```
HTML + Tailwind via CDN (<script src="https://cdn.tailwindcss.com">)
  + JS vanilla (sin framework)
  + fetch() al backend FastAPI correcto del proyecto
  + CSS variables en :root para paleta del cliente
```

**Prohibido**: React, Next, Vue, Svelte, shadcn/ui, Tailwind compilado. Todo va en 1 archivo `.html`.

**Excepción**: si el cliente ya tiene un CRM Next.js corriendo (ninguno todavía), respetar stack existente — no migrar gratis.

## Modelo de datos estándar — CRM v3 persona única

Todos los CRMs siguen este modelo (implementado 2026-04-22 Robert + Mica):

```
clientes_activos (persona única con roles TEXT[])
  ├─ roles: [comprador, inquilino, propietario]
  └─ 1:N con contratos

contratos (polimórficos)
  ├─ tipo: venta/alquiler/compra
  ├─ item_tipo: lote/propiedad/inmueble
  └─ item_id: FK al item específico

alquileres (subset de contratos)
  └─ FK 1:1 con contrato

lotes / propiedades / inmuebles (los ítems)
```

**Regla operativa irrompible**: antes de crear persona, SIEMPRE autocomplete por nombre/teléfono. Evita duplicados. Ver `wiki/conceptos/persona-unica-crm.md`.

## Stack BD por agencia

| Agencia | BD | Nomenclatura IDs | Paleta referencia |
|---------|----|--------------------|-------------------|
| **Robert** | PostgreSQL `lovbot_crm_{cliente}` | INT autoincrement | azul/slate (elección libre) |
| **Mica** | Airtable `appA8QxIhBYYAHw0F` | String `rec...` (NO parseInt!) | ámbar `#f59e0b` (elección libre) |
| **Arnaldo** | Airtable cliente | String `rec...` | paleta por cliente |

---

## Pasos exactos — CRM nuevo (total ~3h si clonás v3)

### Precondiciones

- [ ] BD del cliente creada (ver playbook #4 postgres, #5 airtable)
- [ ] Schema v3 (persona única + contratos polimórficos) aplicado
- [ ] Backend FastAPI del proyecto correcto expone endpoints `/crm/*`
- [ ] Paleta y fuentes elegidas **POR EL CLIENTE** (no inventar)
- [ ] Cliente/agencia confirmada (router de proyectos)

### Paso 1 — Clonar CRM modelo (2 min)

**NUNCA escribir CRM desde cero.** Clonar el más cercano:

| Caso | Clonar |
|------|--------|
| Cliente Robert (Postgres) | `demos/INMOBILIARIA/dev/crm-v3.html` (o el que esté en producción) |
| Cliente Mica (Airtable) | `demos/SYSTEM-IA/dev/crm-v3.html` |
| Cliente Arnaldo | Clonar el de la agencia matching (si el cliente es turismo clonar el de mayor madurez) |

Colocarlo en el path correcto del proyecto. **NUNCA editar directo en prod** — siempre primero `dev/` o rama feature.

### Paso 2 — CSS variables de paleta en :root (5 min)

```css
:root {
  --color-primary: #0f172a;      /* cliente elige */
  --color-accent: #f59e0b;       /* cliente elige */
  --color-bg: #ffffff;
  --color-surface: #f8fafc;
  --color-text: #0f172a;
  --color-text-muted: #64748b;
  --color-border: #e2e8f0;
  --color-success: #10b981;
  --color-danger: #ef4444;
  --color-warning: #f59e0b;

  --font-display: 'Satoshi', 'Inter', sans-serif;   /* cliente elige */
  --font-body: 'Inter', system-ui, sans-serif;
}
```

Después usás `style="background: var(--color-primary)"` o clases Tailwind arbitrarias `bg-[var(--color-primary)]`.

### Paso 3 — Configurar fetch base al backend correcto (2 min)

```javascript
const API_BASE = (() => {
  const host = window.location.hostname;
  if (host.includes('lovbot')) return 'https://agentes.lovbot.ai';
  if (host.includes('arnaldoayalaestratega')) return 'https://agentes.arnaldoayalaestratega.cloud';
  if (host.includes('system-ia-agencia')) return 'https://agentes.arnaldoayalaestratega.cloud/mica';
  return 'http://localhost:8000';  // dev local
})();

async function api(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}
```

### Paso 4 — Implementar modal de contratos (patrón v3, 30 min)

El patrón v3: **3 puertas → 1 modal → 1 endpoint `POST /crm/contratos`**.

3 puertas de entrada:
- Click "Nuevo contrato" desde perfil de persona
- Click "Vender/alquilar" desde detalle de lote/propiedad
- Acción "Crear contrato" desde vista lista de leads

Las 3 abren el mismo modal. El modal:
1. Autocomplete persona (por nombre/teléfono) — si no existe, botón "Crear nueva"
2. Selector tipo: venta / alquiler / compra
3. Selector item_tipo: lote / propiedad / inmueble
4. Autocomplete item_id (según item_tipo elegido)
5. Campos del contrato (monto, moneda, fecha, condiciones)
6. Si tipo = alquiler: sub-formulario con datos de `alquileres` (duración, garantía, expensas)
7. Submit → POST `/crm/contratos` → cierra modal + refresca vista

Ver `wiki/conceptos/contratos-polimorficos.md` para detalles del modelo.

### Paso 5 — Autocomplete tolerante a errores (20 min)

Crítico para evitar duplicados de personas/items:

```javascript
// Debounce 300ms + búsqueda parcial case-insensitive
let searchTimeout;
input.addEventListener('input', (e) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(async () => {
    const q = e.target.value.trim();
    if (q.length < 2) return;
    const results = await api(`/crm/personas/search?q=${encodeURIComponent(q)}`);
    renderResults(results);
  }, 300);
});
```

Si Mica (Airtable): IDs son strings `rec...` — **NUNCA hacer `parseInt(id)`**, romperías los IDs. Ver `feedback_crm_v3_mica_persona_unica.md`.

### Paso 6 — Auth (si aplica) (15 min)

Patrón actual: token en `localStorage`, enviado como header `Authorization: Bearer <token>`.

Panel admin Lovbot usa `LOVBOT_ADMIN_TOKEN` (env var de Coolify, NO hardcodear `lovbot-admin-2026`).

### Paso 7 — Deploy (10 min)

| Proyecto | Path producción | URL final |
|----------|------------------|-----------|
| Robert CRM modelo | `demos/INMOBILIARIA/` servido por FastAPI | `crm.lovbot.ai/dev/crm-v2` |
| Robert admin tenants | `admin.lovbot.ai/clientes` | — |
| Robert CRM agencia | `admin.lovbot.ai/agencia` | — |
| Mica CRM | `system-ia-agencia.vercel.app/system-ia/dev/crm-v2` | — |
| Arnaldo CRM cliente | `clientes-publicos/{slug}/` o dominio propio | varía |

Deploy: git push → Coolify autodetecta. **`force=true` si no rebuildea**.

### Paso 8 — Smoke test post-deploy (10 min)

1. Abrir URL nueva, F12 → Network tab
2. Verificar:
   - Carga datos iniciales sin errores (200 en fetch a `/crm/...`)
   - Crear persona nueva
   - Crear contrato desde las 3 puertas (cada puerta debe terminar en el mismo modal)
   - Editar persona existente
   - Eliminar contrato (si permitido)
3. Revisar logs backend Coolify: no debe haber errores 500

---

## Gotchas conocidos

### Gotcha #1 — Tailwind CDN + `@apply` con display

**Síntoma**: pantalla negra al cargar.

**Causa**: `.oculto { @apply hidden; }` en CSS no funciona con Tailwind CDN (solo con Tailwind compilado via PostCSS).

**Solución**: aplicar la clase directo en el HTML (`class="hidden"`) o usar CSS puro:
```css
.oculto { display: none; }
```

Ver `feedback_tailwind_cdn_css.md`.

### Gotcha #2 — Mica IDs strings, NO parseInt

**Síntoma**: los registros Airtable se actualizan pero no se leen correctamente.

**Causa**: Airtable IDs son strings (`recABC123...`). Si el front hace `parseInt(id)` pensando que son enteros, se rompe.

**Solución**: tratar IDs como strings siempre. Sin parseInt, sin toNumber.

Ver `feedback_crm_v3_mica_persona_unica.md`.

### Gotcha #3 — Roles como multipleSelects (Airtable)

**Síntoma**: al crear persona con rol "comprador", en Airtable aparece vacío.

**Causa**: el campo `roles` en Airtable es tipo `multipleSelects`, espera array `["Comprador"]` con capitalización exacta (no `["comprador"]`).

**Solución**: en el payload, siempre capitalizar primera letra. Validar mayúsculas match con opciones del field.

### Gotcha #4 — Subnicho tenant='mixto' (Mica)

El tenant de Mica usa `subnicho='mixto'` (no uno de los 3 subnichos clásicos inmobiliaria/gastro/turismo). El backend debe respetarlo.

### Gotcha #5 — Paleta ámbar Mica vs purple

**NUNCA generar paleta purple para Mica.** Mica usa ámbar `#f59e0b` como accent (brand decidido). Si el diseñador (frontend-design) quiere purple, sobrescribir.

### Gotcha #6 — Backend URL según dominio

En dev: `localhost:8000`. En prod: depende del proyecto. **NO hardcodear `localhost`** — usar detección por `window.location.hostname`.

### Gotcha #7 — CRM modelo Lovbot vs admin vs agencia

Robert tiene 3 CRMs distintos, no confundir:

| CRM | Path | Para qué |
|-----|------|----------|
| CRM modelo | `crm.lovbot.ai/dev/crm-v2` | Cliente final (inmobiliarias) usa este |
| Admin tenants | `admin.lovbot.ai/clientes` | Robert/Arnaldo crean clientes nuevos |
| CRM agencia | `admin.lovbot.ai/agencia` | Robert gestiona leads de su agencia |

Cada uno tiene backend propio en `agentes.lovbot.ai/{crm,admin,agencia}/*`.

### Gotcha #8 — No recrear archivos legacy

Archivos legacy que NO deben recrearse (ya migrados):
- `demo-crm-mvp.html` (Lovbot)
- `dev/crm.html` raíz
- `dev/admin.html` raíz

Ver `feedback_lovbot_100_coolify_2026_04_23.md`.

---

## Checklist antes de entregar CRM

- [ ] Clonado de CRM v3 modelo, no escrito desde cero
- [ ] CSS variables para paleta del cliente (la que ELIGIÓ, no inventada)
- [ ] `API_BASE` detecta backend correcto por hostname
- [ ] Sin uso de `@apply` con `hidden/block/flex`
- [ ] Sin `parseInt` en IDs si es Airtable
- [ ] Autocomplete antes de crear persona (no duplicados)
- [ ] Modal contratos único + 3 puertas funcionando
- [ ] Auth con env var (no hardcoded)
- [ ] Deploy a ruta correcta del proyecto
- [ ] Smoke test: crear / editar / eliminar OK
- [ ] Logs backend sin errores 500
- [ ] Sin hardcodear `localhost`

---

## Archivos que tocás

```
Path específico del proyecto (ver tabla Paso 7)
  archivo .html único                 ← CRM completo
Opcionalmente:
  backends/.../main.py                ← si falta endpoint, agregarlo
  backends/.../crm_{cliente}.py       ← módulo CRM del cliente si nuevo
```

---

## Cuándo esto cambia

- Cliente exige Next.js → revisar si vale la pena (tiempo extra = plata extra)
- CRM necesita tiempo real (chat en vivo) → agregar WebSocket, no migrar todo
- 20+ vistas distintas → considerar Alpine.js para reactividad local

---

## Histórico de descubrimientos

- **2026-04-22** — CRM v3 persona única + contratos polimórficos implementado Robert + Mica.
- **2026-04-23** — CRM agencia Lovbot LIVE. BD `lovbot_agencia`. Auth con `LOVBOT_ADMIN_TOKEN`.
- **2026-04-23** — Migración 100% Coolify Hetzner (Lovbot salió de Vercel).

---

## Referencias cruzadas

- `wiki/conceptos/persona-unica-crm.md` — modelo v3 detallado
- `wiki/conceptos/contratos-polimorficos.md` — diseño de contratos
- `feedback_crm_v3_robert_persona_unica.md` — lecciones Robert
- `feedback_crm_v3_mica_persona_unica.md` — lecciones Mica (ámbar, IDs strings)
- `feedback_tailwind_cdn_css.md` — bug `@apply` display
- `feedback_crm_agencia_lovbot_live_2026_04_23.md` — CRM agencia Lovbot
- `.claude/skills/agencia-frontend-rules/SKILL.md` — guardrails técnicos
