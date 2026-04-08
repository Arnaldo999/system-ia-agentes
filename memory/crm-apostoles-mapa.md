---
name: CRM Apóstoles — Mapa SVG calibrado
description: Estado completo del mapa interactivo del Loteo Altos de Apóstoles — 332 pins, estructura de coordenadas, mzRanges y sincronización con Airtable
type: project
---

# CRM Apóstoles — Mapa SVG calibrado (2026-04-08)

## Estado final
- **Total pins**: 332 (331 lotes vendibles + 1 EV Mz17)
- **Archivo**: `PROYECTO PROPIO ARNALDO AUTOMATIZACION/INMOBILIARIA MAICOL/PRESENTACION/dashboard-crm.html`
- **Sincronizado a**: `DEMOS/back-urbanizaciones/crm.html`
- **Live en**: `crm.backurbanizaciones.com` → Panel Loteos → Apóstoles

## Estructura de pins

| Rango | Manzana | Lotes | Estado |
|-------|---------|-------|--------|
| 1-4 | EV Mz1-4 | 4 EV | Calibrado |
| 5-26 | Mz8 | 22 | Calibrado |
| 27-47 | Mz7 | 21 | Calibrado |
| 48-75 | Mz6 | 28 | Calibrado |
| 76-103 | Mz5 | 28 | Calibrado |
| 104-131 | Mz9 | 28 | Calibrado |
| 132-159 | Mz10 | 28 | Calibrado |
| 160-187 | Mz11 | 28 | Calibrado |
| 188-215 | Mz12 | 28 | Calibrado |
| 216-243 | Mz13 | 28 | Calibrado |
| 244-271 | Mz14 | 28 | Calibrado |
| 272-299 | Mz15 | 28 | Calibrado |
| 300-327 | Mz16 | 28 | Calibrado |
| 328-329 | Mz12 L29-30 | 2 | Calibrado |
| 330-331 | Mz13 L29-30 | 2 | Calibrado |
| 332 | EV Mz17 | 1 EV | Calibrado |

## Constante global
```javascript
const APOSTOLES_COORDS = { /* 332 entries */ }
```
- Imagen PNG background: `apostoles-plano-v3.png` (Cloudinary)
- ViewBox: `VX=30, VY=10, VW=1900, VH=1900`

## mzRanges — offsets para labels locales (1-28/30)
```javascript
const mzRanges = [
  {s:5,e:26,off:4}, {s:27,e:47,off:26}, {s:48,e:75,off:47}, {s:76,e:103,off:75},
  {s:104,e:131,off:103}, {s:132,e:159,off:131}, {s:160,e:187,off:159}, {s:188,e:215,off:187},
  {s:216,e:243,off:215}, {s:244,e:271,off:243}, {s:272,e:299,off:271}, {s:300,e:327,off:299},
  {s:328,e:329,off:299}, {s:330,e:331,off:301}
];
```

## EV pins (azul)
```javascript
const evPins = {1:'Mz1', 2:'Mz2', 3:'Mz3', 4:'Mz4', 332:'Mz17'};
const isEV = n <= 4 || n === 332;
```

## Sincronización con Airtable
- Filtra `allActivos` donde `a.Loteo === 'Loteo Altos de Apóstoles'`
- Colorea pin por `Numero_Lote` (número global 1-332)
- Verde = disponible | Amarillo = Pendiente | Rojo = Firmado/Escriturado

## Calibración — workflow
1. Abrir mapa → "Calibrar pins" → arrastrar pin a posición
2. En consola F12 ejecutar script de descarga para el rango específico
3. Pegar coordenadas → Claude actualiza `APOSTOLES_COORDS` → push

## Notas
- Mz12 y Mz13 tienen 30 lotes (no 28) — lotes 29-30 en pins 328-331
- Mz17 solo tiene 1 lote EV (pin 332) — no es vendible
- Export por clipboard se trunca con 332 pins — siempre usar script de descarga .txt
