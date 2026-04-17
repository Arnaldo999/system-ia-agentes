# WordPress + Elementor — Lecciones Aprendidas

## Problema: Header fijo sin espacio entre header y hero

### Solución probada (funciona)
El header debe ser `position: fixed` y el body debe tener `padding-top` igual a la altura del header.

**En el HTML del header (Elementor):**
```html
<style>
body:not(.elementor-editor-active) { padding-top: 110px; }
.back-header {
  position: fixed; top: 0; left: 0; width: 100%; z-index: 9999;
}
body.elementor-editor-active .back-header { position: static !important; }
</style>
```

**En el CSS del hero:**
```css
#inicio {
  margin-top: -110px;
  padding-top: 110px;
}
```

> Esto compensa el header fixed para que el hero arranque justo debajo sin espacio.

---

## Problema: Espacio en blanco debajo del header de Elementor

### Causa
Astra genera su propio `#masthead` que ocupa espacio aunque esté vacío.

### Lo que NO funcionó
- `#masthead { display: none !important }` → oculta también el header de Elementor
- Márgenes en 0 desde Personalizar → no afecta
- Cabecera transparente de Astra → no elimina el espacio

### Solución correcta
Usar `position: fixed` en el header + `padding-top` en el body. El `#masthead` de Astra queda debajo y no se ve.

---

## Problema: CSS no aplica en Elementor

### Causa
Elementor bloquea HTML completo (con DOCTYPE/head/style).

### Solución
- Separar CSS en **WPCode** como **HTML Snippet** con `<link>` + `<style>...</style>`
- Pegar solo HTML puro (sin DOCTYPE/head) en el bloque HTML de Elementor
- Los círculos rojos/amarillos en WPCode son del linter, no afectan el funcionamiento

---

## Problema: Ancho completo del hero

### Solución
1. En Elementor → sección → Layout → **Ancho completo**
2. En Ajustes de entrada de la página → **Estructura de página: Elementor Full Width**
3. Agregar en WPCode:
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

## Estructura de archivos para un sitio WordPress + Elementor

| Archivo | Dónde va | Contenido |
|---------|----------|-----------|
| `back-header.html` | Elementor → Header Principal | HTML del nav con `position:fixed` + `<style>` inline |
| `back-footer.html` | Elementor → Footer Principal | HTML del footer con inline styles |
| CSS global | WPCode → HTML Snippet | `<link>` Google Fonts + `<style>` con todo el CSS |
| Contenido | Elementor → Página Inicio | HTML puro sin DOCTYPE/head |

---

## Plugins recomendados para sitios de clientes

- **Really Simple Security** — SSL
- **Yoast SEO** — SEO
- **UpdraftPlus** — Backups → Google Drive
- **WPCode** — Inyectar CSS/HTML en el head (gratis, reemplaza "Personalizar CSS" de pago)
- **Header Footer & Blocks for Elementor** — Header/Footer globales con Elementor gratis

---

## Patrón de header probado (Back Urbanizaciones / Arnaldo Ayala)

```html
<style>
body:not(.elementor-editor-active) { padding-top: [ALTURA]px; }
.mi-header {
  position: fixed; top: 0; left: 0; width: 100%; z-index: 9999;
  background: [COLOR];
}
body.elementor-editor-active .mi-header { position: static !important; }
@media (max-width: 768px) {
  #nav-links { display: none !important; }
  #hamburger { display: flex !important; }
  #nav-mobile.active { display: flex !important; }
}
</style>

<header class="mi-header">
  <!-- logo + nav + botón CTA -->
</header>

<nav id="nav-mobile" style="display:none;position:fixed;top:[ALTURA]px;left:0;width:100%;z-index:9998;">
  <!-- links móviles -->
</nav>
```

---

## Notas Astra (tema)

- Astra Free tiene opciones de header limitadas — para deshabilitar el header de Astra sin CSS se necesita Pro
- La "Cabecera transparente" de Astra es independiente del header principal
- El `#masthead` es el contenedor del header de Astra — manipularlo con CSS puede ocultar el header de Elementor también
- Solución: ignorar el header de Astra y usar header fixed de Elementor con padding-top en body
