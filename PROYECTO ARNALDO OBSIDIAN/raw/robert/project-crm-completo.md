---
name: CRM Completo Multi-Subnicho
description: Roadmap del CRM universal de Lovbot — un solo CRM para desarrolladora/agencia/agente. 8 sprints. Iniciado 2026-04-14.
type: project
originSessionId: 7accf720-af36-49d0-bc07-ba7e60eb27c2
---
# CRM Completo Multi-Subnicho — Lovbot

**Inicio**: 2026-04-14
**Doc detallada**: `01_PROYECTOS/03_LOVBOT_ROBERT/docs/CRM-COMPLETO-MULTISUBNICHO.md`

## Decisión estratégica

Arnaldo definió: **un solo CRM con TODOS los paneles disponibles** para los 3 subnichos
(desarrolladora, agencia, agente). Los campos/paneles que el cliente no use, quedan vacíos
sin afectar nada. Razones:

1. Percepción comercial de producto robusto (evita objeciones "¿y si más adelante...?")
2. Trabajo de una sola vez (no mantener 3 CRMs separados)
3. Realidad LATAM: pocos inmobiliarios son "puros" — casi todos mezclan roles
4. Upsell natural: cliente descubre paneles y empieza a usarlos solo

## Estado de los 8 sprints

| Sprint | Descripción | Estado |
|--------|-------------|--------|
| 1 | Campos universales (PG + worker + HTML) | ✅ PG + worker completos. HTML modales leads/props pendientes |
| 2 | Panel Clientes Activos (cuotas) — portar de Maicol | ⏳ Pendiente (tabla ya existía) |
| 3 | Panel Equipo / Asesores | ✅ Backend + JS + HTML + modal |
| 4 | Panel Propietarios | ✅ Backend + JS + HTML + modal |
| 5 | Panel Loteos + Mapa SVG | ✅ Backend + JS + HTML. Mapa con pins básico (mejorable) |
| 6 | Panel Contratos / Documentos | ✅ Backend + JS + HTML + upload PDF Cloudinary |
| 7 | Panel Reportes (charts) | ✅ Backend + JS + HTML con Chart.js |
| 8 | Panel Agenda / Visitas | ✅ Backend + JS + HTML (lista sin calendario visual aún) |

## Tablas PostgreSQL creadas (Sprint 1)

- `leads` + columnas: `asesor_asignado`, `tipo_cliente`, `propiedad_interes_id`
- `propiedades` + columnas: `propietario_*`, `comision_pct`, `tipo_cartera`,
  `asesor_asignado`, `loteo`, `numero_lote`, `propietario_id` (FK)
- `asesores` (nueva)
- `propietarios` (nueva)
- `loteos` + `lotes_mapa` (nuevas)
- `contratos` (nueva)
- `visitas` (nueva)

## Pendientes inmediatos

- [ ] Ejecutar `GET agentes.lovbot.ai/admin/setup-crm-completo` para aplicar migración
- [ ] Probar UI en `lovbot-demos.vercel.app/dev/crm?tenant=robert` (6 paneles nuevos)
- [ ] Sprint 1 — completar modales de lead/propiedad con campos universales (asesor_asignado, tipo_cliente, propietario_*, comision_pct, loteo, numero_lote)
- [ ] Sprint 2 — portar panel Clientes Activos completo desde Maicol CRM al Lovbot

## Arquitectura frontend

Frontend modular con JS separado por panel:
- `dev/crm.html` — core + paneles existentes (~3700 líneas)
- `dev/js/_crm-helpers.js` — helpers compartidos (crmFetch, crmCreate, etc.)
- `dev/js/panel-asesores.js`, `panel-propietarios.js`, `panel-loteos.js`,
  `panel-contratos.js`, `panel-visitas.js`, `panel-reportes.js`
- Chart.js CDN para reportes
- Cada panel ~150-200 líneas, autocontenido con IIFE

Ventaja: bug en un panel no contamina otros, fácil de mantener/extender.

## Convenciones

- Todos los campos nuevos son **opcionales** — el cliente que no los use no se ve afectado
- `tenant_slug` siempre presente para multi-tenancy
- Triggers `updated_at` automáticos en todas las tablas
- Endpoints CRM siguen patrón existente: `GET/POST/PATCH/DELETE /crm/[recurso]`
- Frontend usa `fetch(API_BASE + '/crm/...')` con `tenant.api_url` dinámico
