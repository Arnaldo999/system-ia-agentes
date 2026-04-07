---
name: tailwind-builder
description: Especialista en construcción de interfaces con Tailwind CSS para System IA. Usar SIEMPRE que el pedido involucre crear o modificar HTML con Tailwind, paneles CRM, dashboards, landing pages, formularios, demos para clientes, componentes UI, páginas HTML estáticas o apps visuales. También activar cuando el usuario diga "haceme una pantalla", "armá un panel", "quiero un formulario", "necesito una página", "crea el frontend", "armá el CRM", "quiero ver los datos en una tabla", "hacé una landing" o cualquier pedido de interfaz visual.
---

# SKILL: Tailwind Builder — UI Expert

## Stack obligatorio por tipo de archivo

| Tipo | Stack |
|------|-------|
| CRM, dashboards, paneles admin | HTML + Tailwind CDN + JS vanilla |
| Landing pages de captación (clientes) | HTML + CSS propio (sin Tailwind) |
| Demos para clientes | HTML + Tailwind CDN |
| Formularios de onboarding | HTML + Tailwind CDN |
| Apps React/Vite | Tailwind instalado como dependencia |

**Regla**: Tailwind CDN (`<script src="https://cdn.tailwindcss.com"></script>`) para todo HTML estático. NUNCA instalar Tailwind como build step en archivos standalone.

## Paleta de colores — Sistema IA

```
Primario:   #1a1a2e (azul muy oscuro)
Secundario: #16213e
Acento:     #0f3460
Highlight:  #533483 (violeta)
Texto:      #e0e0e0
Success:    #10b981 (green-500)
Warning:    #f59e0b (amber-500)
Danger:     #ef4444 (red-500)
```

### Por cliente — usar brandbook en Airtable
- **Maicol / Back Urbanizaciones**: verde oscuro `#1a4a2e`, dorado `#c9a84c`
- **Robert / Lovbot**: consultar brandbook en base Airtable de Robert
- **Demos gastronómicos**: neutro oscuro, acentos según nicho

## Patrones de componentes — usar siempre estos

### Estructura base HTML estático
```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nombre del Panel</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            primary: '#1a4a2e',   // ajustar por cliente
            accent: '#c9a84c',
          }
        }
      }
    }
  </script>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
  <!-- contenido -->
</body>
</html>
```

### Sidebar de navegación (CRM / dashboards)
```html
<div class="flex h-screen">
  <!-- Sidebar -->
  <aside class="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
    <div class="p-4 border-b border-gray-700">
      <h1 class="text-lg font-bold text-white">Nombre App</h1>
    </div>
    <nav class="flex-1 p-4 space-y-1">
      <a href="#" class="flex items-center gap-3 px-3 py-2 rounded-lg bg-primary text-white text-sm font-medium">
        <!-- item activo -->
      </a>
      <a href="#" class="flex items-center gap-3 px-3 py-2 rounded-lg text-gray-400 hover:bg-gray-700 hover:text-white text-sm transition-colors">
        <!-- item inactivo -->
      </a>
    </nav>
  </aside>
  <!-- Main content -->
  <main class="flex-1 overflow-auto p-6">
    <!-- contenido principal -->
  </main>
</div>
```

### Tabla de datos con filtros
```html
<div class="bg-gray-800 rounded-xl border border-gray-700">
  <!-- Header con filtros -->
  <div class="p-4 border-b border-gray-700 flex items-center justify-between gap-4">
    <input type="text" placeholder="Buscar..." 
           class="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 w-64">
    <select class="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none">
      <option value="">Todos</option>
    </select>
  </div>
  <!-- Tabla -->
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-700">
          <th class="text-left px-4 py-3 text-gray-400 font-medium">Columna</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-700">
        <tr class="hover:bg-gray-750 transition-colors">
          <td class="px-4 py-3 text-white">Dato</td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
```

### Modal
```html
<!-- Overlay -->
<div id="modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 hidden">
  <div class="bg-gray-800 rounded-xl border border-gray-700 w-full max-w-lg mx-4 shadow-2xl">
    <div class="flex items-center justify-between p-4 border-b border-gray-700">
      <h3 class="text-white font-semibold">Título</h3>
      <button onclick="closeModal()" class="text-gray-400 hover:text-white">✕</button>
    </div>
    <div class="p-4 space-y-4"><!-- contenido --></div>
    <div class="flex gap-3 p-4 border-t border-gray-700">
      <button class="flex-1 bg-primary hover:bg-primary/80 text-white py-2 rounded-lg text-sm font-medium transition-colors">Guardar</button>
      <button onclick="closeModal()" class="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-lg text-sm transition-colors">Cancelar</button>
    </div>
  </div>
</div>
```

### Card de estadística (KPI)
```html
<div class="bg-gray-800 rounded-xl border border-gray-700 p-4">
  <div class="flex items-center justify-between mb-2">
    <span class="text-gray-400 text-sm">Métrica</span>
    <span class="text-2xl">📊</span>
  </div>
  <div class="text-2xl font-bold text-white">123</div>
  <div class="text-xs text-green-400 mt-1">↑ +12% vs mes anterior</div>
</div>
```

### Badge de estado
```html
<!-- Estados comunes -->
<span class="px-2 py-1 rounded-full text-xs font-medium bg-green-900/30 text-green-400">Activo</span>
<span class="px-2 py-1 rounded-full text-xs font-medium bg-yellow-900/30 text-yellow-400">Pendiente</span>
<span class="px-2 py-1 rounded-full text-xs font-medium bg-red-900/30 text-red-400">Vencido</span>
<span class="px-2 py-1 rounded-full text-xs font-medium bg-blue-900/30 text-blue-400">En proceso</span>
```

## Integración con Airtable (fetch desde JS)

```javascript
const AIRTABLE_TOKEN = 'patXXXX'; // desde env o hardcoded en dev
const BASE_ID = 'appXXXX';
const TABLE = 'Clientes';

async function fetchAirtable(filterFormula = '') {
  const params = new URLSearchParams({ maxRecords: 100 });
  if (filterFormula) params.set('filterByFormula', filterFormula);
  
  const res = await fetch(`https://api.airtable.com/v0/${BASE_ID}/${TABLE}?${params}`, {
    headers: { Authorization: `Bearer ${AIRTABLE_TOKEN}` }
  });
  const data = await res.json();
  return data.records.map(r => ({ id: r.id, ...r.fields }));
}
```

## Reglas de diseño

1. **Dark mode siempre** para CRM/dashboards (fondo `gray-900`, cards `gray-800`)
2. **Hover states** en todos los elementos interactivos (`hover:bg-gray-700`, `transition-colors`)
3. **Responsive**: sidebar colapsable en móvil, tablas con `overflow-x-auto`
4. **Loading states**: spinner o skeleton mientras carga Airtable
5. **Empty states**: mensaje cuando no hay datos (no dejar tabla vacía sin feedback)
6. **Consistencia**: mismo padding (`p-4`/`p-6`), mismos bordes (`border-gray-700`), mismos radios (`rounded-xl` para cards, `rounded-lg` para inputs)

## Ubicaciones de archivos por proyecto

| Proyecto | Archivo |
|----------|---------|
| CRM Maicol | `DEMOS/back-urbanizaciones/crm.html` |
| Demo inmobiliaria | `DEMOS/INMOBILIARIA/` |
| Demo gastronomía | `DEMOS/GASTRONOMIA/gastronomia.html` |
| Nuevo demo | `DEMOS/[NOMBRE]/index.html` |

## Checklist antes de entregar

- [ ] Tailwind CDN incluido en `<head>`
- [ ] `tailwind.config` con colores del cliente
- [ ] Todos los botones tienen `hover:` y `transition-colors`
- [ ] Tablas tienen `overflow-x-auto`
- [ ] Modales funcionan con JS vanilla (open/close)
- [ ] Loading state mientras carga Airtable
- [ ] Filtros de búsqueda funcionan en tiempo real (`input` event)
- [ ] Colores y branding del cliente aplicados
