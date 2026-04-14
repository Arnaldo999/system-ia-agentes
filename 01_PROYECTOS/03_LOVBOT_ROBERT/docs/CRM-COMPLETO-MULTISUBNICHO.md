# CRM Completo Multi-Subnicho — Roadmap de Implementación

**Inicio**: 2026-04-14
**Objetivo**: Un solo CRM universal que sirve para desarrolladora, agencia y agente
**Estrategia**: Todos los paneles disponibles para todos los clientes. Si no usan un
campo/panel, queda vacío sin afectar nada. Producto robusto, percepción de valor alto.

---

## Filosofía

- **Un solo CRM, un solo código, un solo deploy** — mantenible y escalable
- **Campos/paneles opcionales** — cliente usa lo que le sirve
- **Percepción comercial de panel completo** — evita objeciones "¿y si más adelante...?"
- **Upsell natural** — cliente descubre paneles y empieza a usarlos solo
- **La realidad LATAM**: pocos inmobiliarios son "puros" — casi todos mezclan roles

---

## Sprints

### ✅ Sprint 1 — Campos universales (PostgreSQL + endpoint)
**Completado**: 2026-04-14

**Cambios en PostgreSQL** (idempotentes):
- `leads` + `asesor_asignado`, `tipo_cliente`, `propiedad_interes_id`
- `propiedades` + `propietario_*`, `comision_pct`, `tipo_cartera`, `asesor_asignado`, `loteo`, `numero_lote`, `propietario_id` (FK)

**Tablas nuevas**:
- `asesores` (Sprint 3)
- `propietarios` (Sprint 4)
- `loteos` + `lotes_mapa` (Sprint 5)
- `contratos` (Sprint 6)
- `visitas` (Sprint 8)

**Endpoint**: `GET /admin/setup-crm-completo`

**Pendiente**:
- [ ] Ejecutar endpoint en Coolify Robert para aplicar migración
- [ ] Actualizar `db_postgres.py` con funciones para nuevos campos
- [ ] Actualizar modal edición lead/propiedad en CRM HTML

---

### 🟡 Sprint 2 — Panel Clientes Activos (cuotas)
**Objetivo**: Portar el panel de Maicol al CRM Lovbot

**Tabla**: `clientes_activos` ya existe en PostgreSQL ✅

**Pendiente**:
- [ ] Funciones `get_all_activos`, `create_activo`, `update_activo`, `delete_activo` en `db_postgres.py` (verificar si existen)
- [ ] Endpoints `/crm/activos` CRUD en worker
- [ ] Panel HTML con tabla + modal edición
- [ ] Estado_Pago automático (al_dia / atrasado / vencido) según fecha

**Valor para cada subnicho**:
- Desarrolladora: cuotas de lotes/proyectos
- Agencia: cobranza de alquileres
- Agente: financiamientos privados

---

### 🟡 Sprint 3 — Panel Equipo / Asesores
**Tabla**: `asesores` (Sprint 1) ✅

**Pendiente**:
- [ ] CRUD endpoints en worker (`/crm/asesores`)
- [ ] Panel HTML con listado + modal edición
- [ ] Upload foto via Cloudinary
- [ ] Asignación de leads: dropdown "Asesor asignado" en modal lead
- [ ] Filtro "mis leads" vs "todos"

**Valor para cada subnicho**:
- Agencia: gestión de múltiples asesores (principal)
- Desarrolladora mediana: equipo de ventas
- Agente independiente: lo deja vacío y listo

---

### 🟡 Sprint 4 — Panel Propietarios
**Tabla**: `propietarios` (Sprint 1) ✅

**Pendiente**:
- [ ] CRUD endpoints en worker (`/crm/propietarios`)
- [ ] Panel HTML con listado + modal edición
- [ ] Vincular propiedades a propietario (FK `propietario_id` ya existe)
- [ ] Trigger: actualizar `cantidad_propiedades` cuando se asigna/desasigna

**Valor para cada subnicho**:
- Agencia: cartera de propietarios terceros (principal)
- Desarrolladora: propietarios de lotes/unidades vendidas (histórico)

---

### 🟡 Sprint 5 — Panel Loteos + Mapa SVG
**Tablas**: `loteos` + `lotes_mapa` (Sprint 1) ✅
**Referencia**: Sistema completo ya funciona en Maicol CRM (6 loteos, 500+ pins)

**Pendiente**:
- [ ] Portar HTML/JS de Maicol (mapa SVG, pins interactivos)
- [ ] CRUD endpoints en worker (`/crm/loteos`, `/crm/lotes-mapa`)
- [ ] Upload SVG base a Cloudinary
- [ ] Workflow calibración pins (coordenadas x/y sobre SVG)
- [ ] Sincronización con propiedades (pin se pone rojo si lote vendido)

**Valor para cada subnicho**:
- Desarrolladora: mapa visual interactivo (principal, "wow factor")
- Agencia con emprendimientos propios: idem

---

### 🟡 Sprint 6 — Panel Contratos / Documentos
**Tabla**: `contratos` (Sprint 1) ✅

**Pendiente**:
- [ ] CRUD endpoints en worker (`/crm/contratos`)
- [ ] Upload PDFs a Cloudinary
- [ ] Panel HTML con listado + modal edición
- [ ] Tipos: reserva, venta, alquiler, boleto
- [ ] Vincular con lead + propiedad + asesor

**Valor para todos los subnichos**:
- Reservas firmadas, contratos de venta, alquileres, boletos

---

### 🟡 Sprint 7 — Panel Reportes
**Pendiente**:
- [ ] Endpoint `/crm/reportes` con queries agregadas
- [ ] Métricas: ventas/mes, cierres por asesor, propiedades más visitadas, conversión por fuente
- [ ] Charts con Chart.js en HTML
- [ ] Filtro por rango de fechas

**Valor para todos los subnichos**.

---

### 🟡 Sprint 8 — Panel Agenda (Visitas)
**Tabla**: `visitas` (Sprint 1) ✅

**Pendiente**:
- [ ] CRUD endpoints en worker
- [ ] Vista calendario (FullCalendar o similar)
- [ ] Sync bi-direccional con Cal.com (webhook on_booking)
- [ ] Vista por asesor (filtro)

**Valor para todos los subnichos**.

---

## Changelog

| Fecha | Sprint | Cambio |
|-------|--------|--------|
| 2026-04-14 | 1 | Migración PostgreSQL: columnas universales + 5 tablas nuevas |
| 2026-04-14 | 1 | Endpoint GET /admin/setup-crm-completo |
