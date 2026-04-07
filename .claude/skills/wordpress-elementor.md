---
name: wordpress-elementor
description: Experto en WordPress con Elementor y tema Astra para System IA. Activar SIEMPRE que el pedido involucre WordPress, Elementor, Astra, WPCode, cargar HTML en WordPress, conflictos de CSS, header fijo, espacio en blanco, estilos que no aplican, secciones de ancho completo, menú móvil, CSS que Elementor bloquea, o cualquier problema de sitio web en WordPress. También activar ante "el CSS no aplica", "hay un espacio arriba", "el header se mueve", "Elementor no me deja", "cómo meto este HTML en WordPress", "el tema rompe mi diseño".
---

# SKILL: WordPress + Elementor + Astra

## El problema central (leer primero)

Cuando cargamos HTML/CSS propio en WordPress con Elementor + Astra, hay **3 capas de CSS que se pisan**:

```
Astra (tema)          →  genera #masthead, padding en body, márgenes
Elementor             →  agrega sus propias clases, contenedores, z-index
Tu HTML propio        →  tus estilos llegan últimos y a veces pierden
```

La solución no es luchar contra Astra y Elementor — es **rodearlos**.

---

## Regla de oro — estructura de archivos

| Archivo | Dónde va en WP | Qué contiene |
|---------|---------------|--------------|
| CSS global | **WPCode → HTML Snippet** (en `<head>`) | `<link>` Google Fonts + `<style>` con TODO el CSS |
| Header | **Elementor → Plantilla Header** (Header Footer & Blocks) | Solo HTML puro + `<style>` inline mínimo |
| Footer | **Elementor → Plantilla Footer** | Solo HTML puro |
| Contenido de página | **Elementor → Bloque HTML** dentro de la página | Solo HTML puro — SIN `<!DOCTYPE>`, SIN `<head>`, SIN `<style>` |

**Nunca pegar HTML completo (con DOCTYPE) dentro de un bloque Elementor** — lo rompe.

---

## Problema 1: Espacio en blanco debajo del header / entre header y hero

### Causa
Astra genera `#masthead` que ocupa espacio aunque esté oculto o vacío.

### Lo que NO funciona
```css
#masthead { display: none !important }   /* oculta también el header de Elementor */
header { margin: 0 }                     /* Astra lo sobreescribe */
/* Personalizar → Cabecera transparente → no elimina el espacio */
```

### Solución correcta — header fixed + padding-top en body
```css
/* En WPCode — aplicar SIEMPRE */
body:not(.elementor-editor-active) {
  padding-top: [ALTURA_HEADER]px;  /* ej: 80px, 100px, 110px */
}

/* El #masthead de Astra queda debajo del header fixed — invisible */
#masthead {
  display: none !important;
}
```

```html
<!-- En el HTML del header -->
<style>
.mi-header {
  position: fixed;
  top: 0; left: 0;
  width: 100%;
  z-index: 9999;
  background: #1a4a2e;  /* color del cliente */
}
/* En el editor de Elementor, volver a posición normal */
body.elementor-editor-active .mi-header {
  position: static !important;
}
</style>

<header class="mi-header">
  <!-- logo + nav + CTA -->
</header>
```

### Compensar el hero para que arranque justo debajo del header
```css
#inicio {
  margin-top: -[ALTURA_HEADER]px;
  padding-top: [ALTURA_HEADER]px;
}
```

---

## Problema 2: CSS que escribís no aplica — Elementor lo bloquea

### Causa
Elementor tiene alta especificidad en sus selectores y bloquea HTML con `<style>` interno en bloques de contenido.

### Solución
**Separar CSS del HTML** — nunca juntos en el mismo bloque Elementor:

1. **CSS → WPCode** (plugin): Apariencia → WPCode → + Add Snippet → HTML Snippet
   ```html
   <link href="https://fonts.googleapis.com/css2?family=TuFuente&display=swap" rel="stylesheet">
   <style>
     /* Todo tu CSS aquí */
     .mi-seccion { ... }
   </style>
   ```
   - Ubicación: "Head" para que cargue antes
   - Los círculos rojos/amarillos del linter de WPCode son decorativos — no afectan funcionamiento

2. **HTML → Bloque Elementor**: solo el markup, sin ningún `<style>`

---

## Problema 3: Sección/hero que no ocupa ancho completo

### Solución — 3 pasos obligatorios

**Paso 1**: En la página → "Ajustes de entrada" (ícono tuerca) → Estructura de página: **Elementor Full Width**

**Paso 2**: En Elementor → click derecho en la sección → Editar sección → Layout → Ancho del contenido: **Ancho completo**

**Paso 3**: En WPCode agregar:
```css
.elementor-page .site-content,
.elementor-page #primary,
.elementor-page #content,
.ast-container {
  padding: 0 !important;
  max-width: 100% !important;
}
```

---

## Problema 4: Menú móvil no funciona / se muestra siempre

### Estructura correcta de menú responsive
```html
<style>
/* Desktop: mostrar nav horizontal */
#nav-links { display: flex; }
#hamburger { display: none; }
#nav-mobile { display: none; }

/* Móvil */
@media (max-width: 768px) {
  #nav-links { display: none !important; }
  #hamburger { display: flex !important; }
  #nav-mobile.active { display: flex !important; flex-direction: column; }
}
</style>

<!-- Menú desktop -->
<nav id="nav-links">...</nav>

<!-- Botón hamburguesa -->
<button id="hamburger" onclick="toggleMenu()">☰</button>

<!-- Menú móvil desplegable -->
<nav id="nav-mobile" style="
  display: none;
  position: fixed;
  top: [ALTURA_HEADER]px;
  left: 0; width: 100%;
  z-index: 9998;
  background: [COLOR];
">
  <!-- links -->
</nav>

<script>
function toggleMenu() {
  const m = document.getElementById('nav-mobile');
  m.classList.toggle('active');
}
</script>
```

---

## Problema 5: z-index — elementos tapados o que tapan todo

### Jerarquía z-index para System IA
```css
#masthead (Astra)        z-index: 100   /* dejarlo donde está */
.mi-header               z-index: 9999  /* header fijo */
#nav-mobile              z-index: 9998  /* menú móvil */
.modal-overlay           z-index: 10000 /* por encima de todo */
.elementor-popup         z-index: 9997  /* popups Elementor */
```

---

## Problema 6: Fuentes de Google no cargan

### Solución en WPCode (no en Elementor)
```html
<!-- WPCode → HTML Snippet → Head -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Open+Sans:wght@400;600&display=swap" rel="stylesheet">
```

---

## Plugins obligatorios para sitios de clientes

| Plugin | Para qué | Alternativa |
|--------|----------|------------|
| **WPCode** | Inyectar CSS/JS/HTML en head — GRATIS | Personalizar CSS (requiere Astra Pro) |
| **Header Footer & Blocks for Elementor** | Header y footer globales con Elementor — GRATIS | Elementor Pro (de pago) |
| **Really Simple Security** | SSL + seguridad básica | Wordfence |
| **Yoast SEO** | SEO básico — GRATIS | Rank Math |
| **UpdraftPlus** | Backups → Google Drive — GRATIS | — |

---

## Plantilla de header completa — probada y funcional

```html
<style>
/* ── Reset Astra ── */
body:not(.elementor-editor-active) { padding-top: 80px; }
#masthead { display: none !important; }

/* ── Header ── */
.site-header {
  position: fixed; top: 0; left: 0; width: 100%;
  height: 80px;
  background: #1a1a2e;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 2rem;
  z-index: 9999;
  box-shadow: 0 2px 20px rgba(0,0,0,0.3);
}
body.elementor-editor-active .site-header { position: static !important; }

.site-logo img { height: 50px; width: auto; }

.site-nav { display: flex; gap: 2rem; list-style: none; margin: 0; padding: 0; }
.site-nav a { color: #e0e0e0; text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: color 0.2s; }
.site-nav a:hover { color: #c9a84c; }

.header-cta {
  background: #c9a84c; color: #1a1a2e;
  padding: 0.5rem 1.25rem; border-radius: 6px;
  text-decoration: none; font-weight: 600; font-size: 0.9rem;
  transition: opacity 0.2s;
}
.header-cta:hover { opacity: 0.85; }

/* ── Hamburguesa ── */
.hamburger { display: none; background: none; border: none; color: white; font-size: 1.5rem; cursor: pointer; }

/* ── Menú móvil ── */
.mobile-nav {
  display: none;
  position: fixed; top: 80px; left: 0; width: 100%;
  background: #1a1a2e; flex-direction: column;
  padding: 1rem 2rem; gap: 1rem;
  z-index: 9998; border-top: 1px solid rgba(255,255,255,0.1);
}
.mobile-nav.open { display: flex; }
.mobile-nav a { color: #e0e0e0; text-decoration: none; font-size: 1rem; padding: 0.5rem 0; }

@media (max-width: 768px) {
  .site-nav, .header-cta { display: none; }
  .hamburger { display: block; }
}
</style>

<header class="site-header">
  <a href="#inicio" class="site-logo">
    <img src="[URL_LOGO]" alt="[NOMBRE_CLIENTE]">
  </a>
  <ul class="site-nav">
    <li><a href="#inicio">Inicio</a></li>
    <li><a href="#propiedades">Propiedades</a></li>
    <li><a href="#nosotros">Nosotros</a></li>
    <li><a href="#contacto">Contacto</a></li>
  </ul>
  <a href="https://wa.me/[NUMERO]" class="header-cta" target="_blank">Consultar</a>
  <button class="hamburger" onclick="document.querySelector('.mobile-nav').classList.toggle('open')">☰</button>
</header>

<nav class="mobile-nav">
  <a href="#inicio">Inicio</a>
  <a href="#propiedades">Propiedades</a>
  <a href="#nosotros">Nosotros</a>
  <a href="#contacto">Contacto</a>
  <a href="https://wa.me/[NUMERO]" style="color:#c9a84c;font-weight:600;">Consultar →</a>
</nav>
```

---

## Checklist antes de publicar en WordPress

- [ ] CSS en WPCode (no en el bloque Elementor de contenido)
- [ ] HTML sin `<!DOCTYPE>`, sin `<head>`, sin `<style>` en bloques de contenido
- [ ] `padding-top` en body igual a la altura del header
- [ ] `#masthead { display: none }` en WPCode
- [ ] Página configurada como "Elementor Full Width"
- [ ] Sección hero con "Ancho completo" en Elementor
- [ ] Menú móvil probado en iPhone/Android
- [ ] Fuentes cargadas desde WPCode (no desde Elementor)
- [ ] z-index del header > cualquier otro elemento

---

## Notas Astra específicas

- **Astra Free**: header nativo muy limitado — usar siempre Header Footer & Blocks + header propio
- **"Cabecera transparente"** de Astra: no elimina el espacio que ocupa `#masthead`
- **`#masthead`**: es el header de Astra — si se oculta con `display:none`, NO afecta el header de Elementor si este está en una plantilla de Header Footer & Blocks
- **Personalizar → CSS adicional**: funciona pero tiene menor prioridad que WPCode en `<head>`
- **Astra Pro**: permite deshabilitar el header de Astra desde la UI — si el cliente lo tiene, usar esa opción primero
