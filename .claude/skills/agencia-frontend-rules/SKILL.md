---
name: agencia-frontend-rules
description: Guardrails técnicos OBLIGATORIOS para todo HTML, CRM, landing, dashboard o propuesta que se construya dentro del Mission Control de la Agencia Arnaldo Ayala / System IA / Lovbot. Se activa ANTES que frontend-design o cualquier generador visual. NO dicta paleta ni tipografía (eso es libre por cliente) — solo restringe el stack técnico, los paths de deploy, y las convenciones que ya rompieron cosas en producción.
---

# Reglas técnicas obligatorias del ecosistema de agencias

Este skill se activa cuando la tarea involucra construir o modificar: HTML, CRM, landing page, dashboard, formulario, propuesta, demo visual, panel admin, o cualquier output visual en navegador.

**Orden de activación**: este skill corre ANTES de `frontend-design`. Las reglas acá son innegociables. `frontend-design` aporta la parte creativa (paleta, tipografía, composición, motion) DENTRO del marco técnico que define este skill.

---

## Regla 0 — Identificá el cliente antes de codear

Antes de generar una sola línea de código, identificá a qué agencia/cliente pertenece el trabajo. Esto determina el stack físico de deploy. Si no está claro, **preguntá**: "¿Esto es para Arnaldo, Robert o Mica? ¿Y qué cliente?"

Los 3 proyectos NO comparten stack, DB, ni deploy. Ver `CLAUDE.md` raíz, REGLA #0.

---

## Regla 1 — Stack técnico permitido

### Para CRMs, paneles admin, dashboards internos (dev o prod de clientes)

- **HTML + Tailwind via CDN** (`<script src="https://cdn.tailwindcss.com"></script>`)
- JavaScript vanilla (sin framework) o Alpine.js si hace falta reactividad local
- Sin build step. Un archivo `.html` que se sirve directo.

### Para landings, propuestas, formularios públicos

- Mismo stack: HTML + Tailwind CDN + JS vanilla
- Se deployan en Coolify Hostinger (Arnaldo) bajo `clientes-publicos/{slug}/` → URL auto `agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/`
- **NO usar Vercel para sitios nuevos** (ver `feedback_REGLA_coolify_default.md`). Vercel queda solo para Mica (`system-ia-agencia.vercel.app`) y Maicol (`crm.backurbanizaciones.com`) por legacy.

### Para features que requieren reactividad compleja (admin multi-tenant, CRM v3)

- Seguir lo que ya existe en el repo. Robert CRM v3 usa HTML + Tailwind + JS vanilla con fetch. NO introducir React/Next/Vue a menos que el usuario lo pida explícitamente.

### Frameworks PROHIBIDOS por default

- ❌ Next.js, React, Vue, Svelte en proyectos nuevos
- ❌ Tailwind compilado con PostCSS/Vite (solo CDN)
- ❌ shadcn/ui, Material UI, Chakra (son para Next.js)
- ❌ Motion library de React (no hay React)
- ❌ CSS-in-JS

Si `frontend-design` sugiere React + Motion + shadcn, **reescribí a HTML + Tailwind CDN + CSS animations/vanilla JS**.

---

## Regla 2 — Tailwind CDN tiene 1 limitación crítica

**NUNCA uses `@apply` con utilidades `hidden`, `block`, `flex`, `grid` en Tailwind CDN.** Causa pantalla negra. Bug ya documentado en `memory/` como `feedback_tailwind_cdn_css.md`.

Solución: aplicá las clases directamente en el HTML (`class="hidden"`) o usá CSS puro (`display: none`) dentro de `<style>`.

Ejemplo MAL:
```css
.oculto { @apply hidden; }  /* rompe en CDN */
```

Ejemplo BIEN:
```html
<div class="hidden">...</div>
<!-- o -->
<style>.oculto { display: none; }</style>
```

---

## Regla 3 — Paleta y tipografía son libres por cliente

**NO imponer paleta ni fuentes predefinidas.** Cada cliente elige las suyas. Si el usuario no especifica:

1. Preguntar: "¿Qué paleta y fuentes querés para este cliente? Si no tenés preferencia, te propongo 3 opciones."
2. Proponer 3 opciones coherentes con el vertical del cliente (turismo, inmobiliaria, gastronomía, etc.)
3. Esperar decisión antes de codear.

Una vez elegida la paleta:
- Definirla como CSS variables en `:root` (`--color-primary`, `--color-accent`, etc.) para que sea fácil cambiarla después.
- Aplicarla consistentemente en toda la interfaz.

**Fuentes**: seguir el criterio de `frontend-design` (evitar Inter/Roboto/Arial genéricos) pero siempre cargadas vía Google Fonts CDN o similar, nunca locales.

---

## Regla 4 — Flujo Demo → Producción (IRROMPIBLE)

**NUNCA modificar directamente archivos en producción.** Siempre primero en demo.

| Producción (NO tocar directo) | Demo (acá se trabaja) |
|-------------------------------|----------------------|
| `workers/clientes/*/worker.py` | `workers/demos/inmobiliaria/worker.py` o `gastronomia/worker.py` |
| `demos/INMOBILIARIA/demo-crm-mvp.html` (Robert) | `demos/INMOBILIARIA/dev/crm.html` |
| `demos/SYSTEM-IA/*` en `main` | Rama feature, probar, luego merge |
| URLs live del cliente | URLs de preview / staging |

Ver `feedback_REGLA_demo_primero.md` en auto-memory.

---

## Regla 5 — Rutas de archivos por proyecto

| Tipo de archivo | Ruta |
|-----------------|------|
| CRM dev de cliente Robert | `01_PROYECTOS/03_LOVBOT_ROBERT/demos/INMOBILIARIA/dev/` |
| CRM prod cliente Robert | `01_PROYECTOS/03_LOVBOT_ROBERT/demos/INMOBILIARIA/` |
| Demo Mica | `01_PROYECTOS/02_SYSTEM_IA_MICAELA/demos/SYSTEM-IA/` |
| Propuesta pública Arnaldo | `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/clientes-publicos/{slug}/` |
| Landing cliente Arnaldo | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/{vertical}/` |
| CRM agencia Lovbot | `admin.lovbot.ai/agencia/` (servido por FastAPI) |

Si no sabés qué ruta corresponde, preguntá antes de crear archivos.

---

## Regla 6 — Backend que consume el frontend

Cada proyecto tiene su backend FastAPI:

| Agencia | Backend URL | Prefijo rutas |
|---------|-------------|---------------|
| Arnaldo | `https://agentes.arnaldoayalaestratega.cloud` | `/` directo (ej `/propuestas/`, `/clientes/`) |
| Robert (Lovbot) | `https://agentes.lovbot.ai` | `/crm/`, `/agencia/`, `/admin/` |
| Mica (System IA) | `https://agentes.arnaldoayalaestratega.cloud` | `/mica/*` (mismo backend, prefijo Mica) |

Cuando un HTML hace `fetch()`, usar la URL absoluta del backend del proyecto correcto. NO asumir `localhost` ni URLs relativas si el HTML vive en otro dominio.

---

## Regla 7 — Seguridad en HTMLs cliente-facing

- **NUNCA** meter tokens, API keys, secrets en HTML (ni en `<script>` ni en vars globales).
- Auth con `localStorage` solo para UX no crítica. Validación real siempre en backend.
- CORS: los backends Coolify ya tienen headers configurados. Si falla CORS en dev, revisar `main.py` del backend, NO parchear con proxy en el HTML.

---

## Regla 8 — Cuando delegar a `frontend-design`

Después de aplicar las reglas 1-7, `frontend-design` aporta:
- Dirección estética (bold / minimal / editorial / etc.)
- Composición espacial (grid, asimetría, jerarquía)
- Motion (CSS animations, transiciones)
- Typography pairing (display + body)
- Detalles de atmósfera (gradientes, texturas, sombras)

**No delegues a `frontend-design` sin antes haber definido**:
1. Cliente / agencia ✓
2. Stack (CDN + vanilla en 99% de casos) ✓
3. Paleta elegida por el cliente ✓
4. Ruta de output ✓

---

## Checklist antes de entregar cualquier HTML

- [ ] ¿Identifiqué el cliente y agencia correcta?
- [ ] ¿Usé Tailwind CDN (no compilado) con vanilla JS?
- [ ] ¿Evité `@apply` con utilidades display?
- [ ] ¿Paleta y fuentes fueron elegidas por el cliente (no inventadas)?
- [ ] ¿Trabajé en demo/dev, no directo en prod?
- [ ] ¿La ruta del archivo sigue la convención del proyecto?
- [ ] ¿Los `fetch()` apuntan al backend correcto del proyecto?
- [ ] ¿No hay secrets en el HTML?

Si alguno falla, corregir ANTES de entregar.
