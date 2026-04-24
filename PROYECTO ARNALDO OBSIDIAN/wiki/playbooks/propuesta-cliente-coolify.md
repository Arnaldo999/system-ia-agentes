---
name: Playbook — Propuesta/landing pública del cliente en Coolify
description: Crear landing, propuesta comercial o formulario público para un cliente. Path `clientes-publicos/{slug}/` en el repo, deploy automático en Coolify Hostinger (Arnaldo) con URL `agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/`.
type: playbook
proyecto: compartido
tags: [landing, propuesta, coolify, arnaldo, clientes-publicos, playbook]
version: 1
ultima_actualizacion: 2026-04-24
casos_aplicados: [cesar-posada-turismo, futuros-arnaldo]
agencia_principal: arnaldo
---

# Playbook — Propuesta/landing pública en Coolify

> **Cuándo usar**: cliente en negociación o cerrado necesita una URL para ver propuesta, llenar formulario, ver sitio demo. NO es app reactiva (CRM) — es contenido que se navega.

## Stack y patrón (no se negocia)

- HTML + Tailwind CDN + JS vanilla
- Path en repo: `backends/system-ia-agentes/clientes-publicos/{slug}/`
- Deploy: git push → Coolify Hostinger autodetecta → servido por FastAPI estático
- URL final: `https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/`

**NO usar Vercel** para propuestas nuevas. Ver `feedback_REGLA_coolify_default.md`.

## Estructura de archivos por propuesta

```
clientes-publicos/
└── {slug}/                          ← ej: cesar-posada
    ├── index.html                   ← propuesta (landing)
    ├── formulario.html              ← formulario brief
    ├── assets/
    │   ├── logo.png
    │   ├── hero.jpg
    │   └── propuesta-firmada.pdf    ← si ya firmó, opcional
    └── gracias.html                 ← post-submit del formulario
```

URL final:
- `/propuestas/cesar-posada/` → index.html
- `/propuestas/cesar-posada/formulario.html`
- `/propuestas/cesar-posada/gracias.html`

---

## Pasos exactos — propuesta nueva (total ~2-3h primera vez, 1h clonando)

### Precondiciones

- [ ] Cliente identificado, slug decidido (kebab-case sin tildes: `cesar-posada`, `juan-turismo-salta`)
- [ ] Paleta y fuentes: **PREGUNTARLE al cliente** — ver skill `agencia-frontend-rules`
- [ ] Brief del cliente tenés: qué servicio, qué vertical, qué tono, precios
- [ ] Logo del cliente si ya tiene (sino, podemos usar tipografía)

### Paso 1 — Clonar propuesta anterior más cercana (3 min)

```bash
# Ejemplo: propuesta nueva para cliente Juan, basada en Cesar Posada
cd backends/system-ia-agentes/clientes-publicos/
cp -r cesar-posada/ juan-turismo-salta/
```

**NUNCA escribir propuesta desde cero.** Siempre clonar la más parecida en vertical/tono.

### Paso 2 — Consultar skill guardrails (antes de codear) (2 min)

**Antes de escribir una línea**, activar mentalmente `/agencia-frontend-rules`:

- ¿Qué cliente? → agencia correspondiente → Coolify correcto
- ¿Paleta elegida? Si NO: preguntar al cliente con 3 opciones
- ¿Fuentes elegidas? Idem
- Path correcto: `clientes-publicos/{slug}/`
- Sin `@apply` con display utilities
- Sin frameworks pesados

### Paso 3 — Adaptar contenido (30-60 min)

En `index.html`:

1. **CSS variables paleta** (del cliente):
   ```css
   :root {
     --color-primary: #<cliente-eligió>;
     --color-accent: #<cliente-eligió>;
     --font-display: '<cliente-eligió>';
     --font-body: '<cliente-eligió>';
   }
   ```

2. **Hero section**: nombre cliente + propuesta de valor específica a su negocio

3. **Servicios/plan**: qué incluye el paquete (bot, CRM, social automation, etc.) con precios reales

4. **Casos de éxito**: referenciar clientes previos (con permiso) — Maicol, etc.

5. **CTA**: botón a `formulario.html` para completar brief

6. **Footer**: datos de Arnaldo (San Ignacio, Misiones — NO Posadas. Ver `user_arnaldo_ubicacion.md`)

### Paso 4 — Formulario brief (20 min)

En `formulario.html`:

Campos típicos del brief:
- Nombre comercial del cliente
- Vertical (inmobiliaria / gastronomía / turismo / otro)
- Número WhatsApp del bot deseado
- Tono de voz (formal / cercano / técnico)
- Público objetivo (2-3 líneas)
- Reglas estrictas ("NO decir precios en público", etc.)
- Colores de marca (hex)
- Logo (file upload a Cloudinary o Airtable attachment)
- Catálogo inicial (texto libre o adjunto)

Submit handler:
```javascript
formulario.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  await fetch('https://agentes.arnaldoayalaestratega.cloud/propuestas/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug: '{slug}', ...data }),
  });
  window.location.href = 'gracias.html';
});
```

Backend recibe → guarda en Airtable de Arnaldo (tabla `Briefs de clientes`) → notifica WhatsApp.

### Paso 5 — Gracias page (10 min)

Pantalla post-submit. Corta y clara:
- "¡Gracias [Nombre]!"
- Próximos pasos: "Te contacto en 24h con el setup inicial"
- Link a WhatsApp de Arnaldo
- Opcional: agendar llamada con link Cal.com

### Paso 6 — Verificar linkeo correcto al backend (5 min)

El FastAPI de Arnaldo ya sirve la carpeta `clientes-publicos/` automáticamente. Verificar:

```python
# En main.py, debería estar:
from fastapi.staticfiles import StaticFiles
app.mount("/propuestas", StaticFiles(directory="clientes-publicos", html=True), name="propuestas")
```

Si no está, agregarlo. Una sola vez — todos los clientes nuevos heredan.

### Paso 7 — Deploy (5 min)

```bash
git add clientes-publicos/{slug}/
git commit -m "feat(propuestas): landing + formulario cliente {nombre}"
git push origin master:main
```

Coolify Hostinger detecta cambio y rebuildea. **Si no rebuildea**: force rebuild manual (`force=true`). Ver `feedback_REGLA_coolify_cache_force.md`.

Esperar 2-3 min y verificar:

```bash
curl -I https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/
# Debe devolver 200 OK
```

### Paso 8 — Test en navegador + mobile (10 min)

1. Abrir en desktop Chrome → verificar paleta, fuentes, CTAs
2. Abrir en mobile (o DevTools mobile emulation) → responsive OK
3. Click en CTA → formulario carga
4. Submit formulario con datos test → gracias.html carga
5. Verificar que el submit llegó al backend (log Coolify o Airtable)
6. Borrar el record test de Airtable

### Paso 9 — Mandar URL al cliente (2 min)

Mensaje plantilla:

```
Hola [Nombre],

Te mandé la propuesta + formulario para el setup:

👉 https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/

Tomate 10 min para leerla y completar el formulario cuando puedas.

Cualquier duda me avisás.
```

---

## Gotchas conocidos

### Gotcha #1 — Coolify NO rebuildea aunque hay commit

**Síntoma**: pusheaste a main, pasaron 5 min, la URL sigue mostrando versión vieja.

**Causa**: bug Coolify v4 beta.

**Solución**: force rebuild manual:
- UI Coolify → Service → Redeploy → marcar "Force rebuild"
- O API: `curl -X POST ".../deploy?force=true" -H "Authorization: Bearer $COOLIFY_TOKEN"`

Verificar `last_online_at` vs timestamp del commit.

Ver `feedback_REGLA_coolify_cache_force.md`.

### Gotcha #2 — Mobile viewport mal

**Síntoma**: se ve bien en desktop, en celular el contenido se sale de pantalla.

**Solución**: viewport meta tag al inicio del `<head>`:

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

Y usar clases responsive de Tailwind: `text-base md:text-lg`, `grid-cols-1 md:grid-cols-3`, etc.

### Gotcha #3 — Formulario sin CORS

**Síntoma**: submit falla con `CORS error`.

**Causa**: el backend no acepta origen del formulario.

**Solución**: el backend FastAPI Arnaldo ya tiene `allow_origins=["*"]` en prod (está bien para propuestas públicas). Si no funciona, revisar `main.py` CORS middleware.

Ver `wiki/conceptos/cors-preflight-monitoreo.md`.

### Gotcha #4 — Footer con ubicación incorrecta

**Síntoma**: footer dice "Posadas, Misiones" — pero Arnaldo es de San Ignacio.

**Causa**: LLM asumió Posadas (capital provincia).

**Solución**: siempre usar "San Ignacio, Misiones, Argentina".

Ver `user_arnaldo_ubicacion.md` en auto-memory.

### Gotcha #5 — Slug con tildes o espacios

**Síntoma**: URL `/propuestas/josé-pérez/` no funciona.

**Solución**: slug siempre kebab-case sin tildes: `jose-perez`. Mover carpeta si ya la creaste mal.

### Gotcha #6 — Assets cargan desde `/` root en vez de relativo

**Síntoma**: logo no aparece en la propuesta live, funciona en local.

**Causa**: `<img src="/logo.png">` busca desde root del dominio, no desde `/propuestas/{slug}/`.

**Solución**: rutas relativas: `<img src="assets/logo.png">` o absolutas desde base: `<img src="/propuestas/{slug}/assets/logo.png">`.

### Gotcha #7 — Secrets en HTML

NUNCA meter API keys, tokens, URLs de Supabase con `service_role` en el HTML. Es público, se puede ver con View Source.

**Regla**: todo endpoint que requiere auth va por backend. Formulario submit → endpoint del backend → backend valida + escribe.

---

## Checklist antes de mandar URL al cliente

- [ ] Slug kebab-case sin tildes
- [ ] Paleta y fuentes del cliente aplicadas (preguntadas, no inventadas)
- [ ] Contenido adaptado al cliente (no texto del cliente anterior)
- [ ] Logo del cliente adjuntado
- [ ] Footer con "San Ignacio, Misiones" (NO Posadas)
- [ ] Formulario conecta correctamente al backend
- [ ] Submit test llega a Airtable
- [ ] Viewport meta tag presente (responsive OK)
- [ ] Sin `@apply hidden/block/flex`
- [ ] Sin secrets en HTML
- [ ] Coolify rebuildeó (verificar con curl)
- [ ] URL carga en desktop + mobile
- [ ] Gracias page funciona
- [ ] Record test de Airtable limpiado

---

## Archivos que tocás

```
backends/system-ia-agentes/clientes-publicos/{slug}/
  ├─ index.html                 ← nuevo
  ├─ formulario.html            ← nuevo
  ├─ gracias.html               ← nuevo
  └─ assets/                    ← nuevo
backends/system-ia-agentes/main.py   ← solo si falta el mount de StaticFiles
```

---

## Variantes del patrón

### Landing comercial pública (no propuesta de brief)

Si el cliente quiere que le hagamos un sitio público real (no solo landing de propuesta), usar path `clientes-publicos/{slug}/sitio/` o subdominio dedicado (ej: `cesar-posada.com` apuntando al mismo backend Coolify).

### Formulario sin propuesta

A veces solo es un formulario público para captar leads (sin landing extensa). Usar misma estructura, `index.html` redirige a `formulario.html` o es directamente el formulario.

### Multi-idioma

Si el cliente tiene público en 2 idiomas: `index.html` (español), `en/index.html` (inglés). Navbar con flag toggle.

---

## Histórico de descubrimientos

- **2026-04-22** — Patrón `clientes-publicos/{slug}/` establecido con Cesar Posada (turismo). Propuesta live en `/propuestas/cesar-posada/`.
- **2026-04-22** — Regla Coolify por default (no Vercel). Ver `feedback_REGLA_coolify_default.md`.

---

## Referencias cruzadas

- `.claude/skills/agencia-frontend-rules/SKILL.md` — guardrails técnicos
- `feedback_REGLA_coolify_default.md` — regla Coolify vs Vercel
- `feedback_REGLA_coolify_cache_force.md` — force rebuild
- `project_cesar_posada_turismo.md` — caso ejemplo en auto-memory
- `user_arnaldo_ubicacion.md` — San Ignacio vs Posadas
- `wiki/conceptos/coolify-default-deploy.md` — referencia Coolify
