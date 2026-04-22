---
fecha: 2026-04-21
sesion: FASE-1-CRM-v3-Mica
estado: COMPLETO
---

# Schema Airtable v3 — Base appA8QxIhBYYAHw0F (Mica)

## Resumen de cambios aplicados (Fase 1)

### Modelo persona única implementado

**CLIENTES_ACTIVOS** (tblpfSE6qkGCV6e99) — 25 campos
Campos agregados en esta sesion:
- `Roles` (multipleSelects): `comprador | inquilino | propietario`
- `Apellido` (singleLineText)
- `Documento` (singleLineText) — DNI/CUIT
- `Origen_Creacion` (singleSelect): `manual_directo | lead_convertido | activo_mapa | migracion_inquilino | migracion_propietario`
- `Ciudad` (singleLineText)
- `Lead_Origen` (link → Clientes/leads) fld5Yi3iF9CDIN2Jd
- `Asesor_Asignado` (link → Asesores) fld22ywV32xHX9008
- Links inversos creados automaticamente por Airtable al linkear otras tablas: `Contratos`, `ContratosAlquiler`, `PagosAlquiler`, `Liquidaciones`, `InmueblesRenta`, `Visitas`

### Contratos polimorficos implementados

**Contratos** (tblQvGFwL5sZdf1jU) — 23 campos
Campos agregados:
- `Cliente` (link → CLIENTES_ACTIVOS) fldSHjhliYzPvhqeP
- `Asesor` (link → Asesores) fldsduXDNJOlDPpNv
- `Lote_Asignado` (link → LotesMapa) fld4Pn871cwaAQ73i
- `Propiedad_Asignada` (link → Propiedades) fldYoz8kItbrs29i9
- `Inmueble_Asignado` (link → InmueblesRenta) fldnq1oyiZktf3yNE
- `Cuotas_Total` (number) fldIuhoOPGO2h7U10
- `Cuotas_Pagadas` (number) fldPVSI5tBalPJLS0
- `Monto_Cuota` (currency) fldo9lp8DNAVlHLzx
- `Proximo_Vencimiento` (date) fldnmCjNjoOKRKhbD
- `Estado_Pago` (singleSelect): `al_dia | atrasado | en_mora | cancelado | saldado` — fldId9KzqC6G3SRlq
- `Item_Descripcion` (singleLineText) fldd3Um3q9ZGhuswo

Nota: campo `Tipo` YA EXISTIA con opciones `venta | reserva | alquiler | boleto` (fldpG4cXlYOe9OTkk).
El modelo v3 mapea en la capa de aplicacion: `venta_lote/venta_casa/venta_terreno/venta_unidad` → `venta` en Airtable + `Item_Descripcion` para detalle.

### Integracion tablas de gestion de alquileres

**ContratosAlquiler** (tbluxdLR0bnpfLay9) — 22 campos
Agregados: `Contrato → Contratos` (fldnK6YnQiS4kDYoW), `Inquilino → CLIENTES_ACTIVOS` (fldixUZGTAipIYjN5), `Inmueble → InmueblesRenta` (fld5Sg6u8byGcv2Ll), `Propietario → CLIENTES_ACTIVOS` (fldPi5UtFnlE9q2hL), `Asesor → Asesores` (fldVnxtAMnGc4hIOx)

**PagosAlquiler** (tblUKoTFkJzk31N2m) — 17 campos
Agregados: `Contrato → ContratosAlquiler` (fldtcVIwdfgMYqV8R), `Inquilino → CLIENTES_ACTIVOS` (fldD9crTulQlvvOWA), `Inmueble → InmueblesRenta` (fldO5tyTYptz5ON8w)

**Liquidaciones** (tbl3ELdKQOTlKj4Wz) — 17 campos
Agregados: `Propietario → CLIENTES_ACTIVOS` (fld2PPmg1K99NRosU), `Contrato → ContratosAlquiler` (fldWWtNigggVnDLrS), `Inmueble → InmueblesRenta` (fldwne3bYlCQEEHkx)

### Activos inmobiliarios

**InmueblesRenta** (tblRlLK8doYDCZIiK) — 31 campos
Agregados: `Propietario → CLIENTES_ACTIVOS` (fldvS1la4lPsuKUY5), `Asesor_Link → Asesores` (fldpKE8g3IuxwSEQk)

**LotesMapa** (tblglWTmEsQ7n8ANf) — 11 campos
Agregado: `Proyecto → Loteos` (fldEpAwJYiO9fBixB)

**Visitas** (tblu3EHwh8eJkOPjI) — 14 campos
Agregados: `Cliente → CLIENTES_ACTIVOS` (fldKxGa0ZqmUkvlaO), `Lead → Clientes` (fldxIk9qt03bhr3Fc), `Propiedad → Propiedades` (fldp0qlDO6jRut5Yu), `Inmueble → InmueblesRenta` (fld95J6bPikJ74rtZ), `Lote → LotesMapa` (fldI3pedmxWgcnVXB), `Asesor → Asesores` (fldGPTKIeA7NSdUZ3)

## Tenant Supabase

**mica-demo** actualizado:
- `subniche`: `inmobiliaria` → `mixto`
- Razon: sidebar acordeon debe mostrar grupos Desarrolladora + Agencia
- `color_primario`: #f59e0b, `color_acento`: #dc2626 (sin cambios)
- ID tenant Supabase: 79d30848-8bbb-48e5-a250-40f0b27d4a57

## Tablas NO modificadas (sin necesidad de cambios o fuera de scope)

- `Clientes` (tblonoyIMAM5kl2ue) — tabla leads del bot, intacta
- `Propiedades` (tbly67z1oY8EFQoFj) — propiedades en venta, intacta
- `BotSessions` (tblfV9IJKv1jTCRQt) — sesiones bot, intacta
- `Clientes_Agencia` (tblclTG5G9SiNyIXj) — multi-tenant CRM SaaS, intacta
- `Asesores` (tblfso1JAoJaDUTLf) — tabla referencial, intacta
- `Propietarios` (tbl7XoZ9NOfkfqQAG) — tabla legacy, se mantiene
- `Loteos` (tbluM3b8vHShORORO) — proyectos padre, intacta
- `Inquilinos` (tblCs0nMKxExE6lp5) — tabla legacy, se mantiene para compat
- `ConfigCliente` (tblFQIoH3t7PAPNyL) — configuracion, intacta

## IDs de campo clave para el backend (Fase 2)

| Tabla | Campo | Field ID |
|-------|-------|----------|
| CLIENTES_ACTIVOS | Roles | fldsRtKBtiVHu7SMk |
| CLIENTES_ACTIVOS | Origen_Creacion | fld4BE5nf0HWBgekY |
| CLIENTES_ACTIVOS | Lead_Origen | fld5Yi3iF9CDIN2Jd |
| CLIENTES_ACTIVOS | Asesor_Asignado | fld22ywV32xHX9008 |
| Contratos | Cliente | fldSHjhliYzPvhqeP |
| Contratos | Tipo | fldpG4cXlYOe9OTkk |
| Contratos | Estado_Pago | fldId9KzqC6G3SRlq |
| Contratos | Lote_Asignado | fld4Pn871cwaAQ73i |
| Contratos | Propiedad_Asignada | fldYoz8kItbrs29i9 |
| Contratos | Inmueble_Asignado | fldnq1oyiZktf3yNE |
| ContratosAlquiler | Contrato | fldnK6YnQiS4kDYoW |
| ContratosAlquiler | Inquilino | fldixUZGTAipIYjN5 |

## Pendiente para Fase 2 — Backend adapter

1. Endpoint `GET /mica/crm/personas/buscar?q=` — search en CLIENTES_ACTIVOS
2. Endpoint `GET /mica/crm/personas/{id}` — ficha 360 persona con contratos + alquileres + inmuebles
3. Endpoint `POST /mica/crm/personas/agregar-rol` — agregar rol a persona existente
4. Endpoint `POST /mica/crm/contratos` — crear contrato atomico (cliente + contrato + update activo)
5. Endpoint `POST /mica/crm/contratos/alquiler` — contrato alquiler + ContratosAlquiler record
6. Endpoint `GET /mica/crm/contratos` — listar contratos con links resueltos
7. Actualizar `db_airtable.py` con las nuevas tablas y field IDs

## Pendiente para Fase 3 — Frontend CRM

- Replicar sidebar acordeon del CRM Robert v3 con paleta ambar/rojo
- Panel CLIENTES_ACTIVOS con badges de roles
- Modal "Nuevo contrato" wizard (3 puertas = 3 contextos)
- Panel Alquileres + Liquidaciones
- Panel Desarrolladora (Loteos + Mapa SVG)
