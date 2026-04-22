# ESTADO ACTUAL

Fecha: 2026-04-22 06:00 ART
Responsable última actualización: Claude Opus 4.7 / Arnaldo

## 🎯 Hito cerrado — CRM v3 Robert completo

Ayer y hoy terminamos el refactor arquitectónico del CRM v2 de Robert. 18h de trabajo, 16+ commits, todo en producción con smoke tests verdes.

### Qué cambió (backend — Postgres `lovbot_crm_modelo`)
- **Tabla `clientes_activos`** ahora es la persona única del ecosistema. Campo `roles TEXT[]` permite acumular [comprador, inquilino, propietario] sin duplicar registros.
- **Tabla `contratos`** polimórfica con `tipo` + `item_tipo` + `item_id`. Un endpoint unificado `POST /crm/contratos` con 3 ramas (cliente_activo_id / convertir_lead_id / cliente_nuevo).
- **Tabla `alquileres`** nueva para datos específicos del tipo='alquiler' (fechas, garante).
- **Tablas GESTIÓN-Agencia** con CRUD real: `inmuebles_renta`, `inquilinos`, `pagos_alquiler`, `liquidaciones`, `propietarios`. Antes eran placeholders.
- **Lotes granulares**: `lotes_mapa` con UNIQUE `(tenant, loteo_id, manzana, numero_lote)`. La inmobiliaria puede agregar/borrar/renombrar manzanas y lotes individualmente.
- **20+ endpoints nuevos** en el worker Robert cubriendo todo esto.

### Qué cambió (frontend — `crm.lovbot.ai/dev/crm-v2`)
- Modal unificado "Nuevo contrato" con **3 pasos** (Cliente → Activo → Contrato).
- **3 puertas de entrada** al modal: panel Clientes, click lote en mapa, botón Convertir en lead.
- **Sidebar GESTIÓN** con 3 grupos acordeón colapsables (Desarrolladora / Agencia / Mixto) — siempre todos visibles.
- Modales "Nuevo inquilino / propietario" con **autocomplete** que busca si la persona ya existe (evita duplicados).
- **Tab "Relaciones"** en ficha de cliente — ficha 360 con contratos + alquileres + inmuebles propios.
- **Panel Loteos reescrito** — lee `lotes_mapa` real, permite CRUD granular con feedback visual.
- **CORS corregido** en backend (whitelist explícita para crm.lovbot.ai + vercel.app + localhost).

### Estado producción
- ✅ Backend Coolify Hetzner `agentes.lovbot.ai` — todos los endpoints respondiendo 200
- ✅ DB Postgres `lovbot_crm_modelo` — schema v3 aplicado, datos limpios (smoke tests borrados)
- ✅ Frontend Vercel `crm.lovbot.ai/dev/crm-v2` — cupo se resetea cada 24h (Plan Hobby), a veces 5 commits se acumulan y deployan juntos

### Bugs destacados fixeados
1. `tenant_slug` duplicado en `_crud_generico` (commit `d26d634`) — rompía POST a propietarios/inmuebles/inquilinos/pagos/liquidaciones.
2. UNIQUE constraint `lotes_mapa` tenía 2 simultáneos (auto-generado sin manzana + el nuevo con manzana) — bloqueaba A-1 + B-1 coexistir (commit `0fa97c6` + `ba5c42d`).
3. Lote vendido no mostraba cliente — triple bug: endpoint equivocado `/crm/clientes` vs `/crm/activos` + ID con prefijo `pg_16` vs `16` + mayúsculas inconsistentes `Nombre` vs `nombre` (commit `d5002d6`).
4. HTTP 410 masivo en consola — 10 URLs `airtableusercontent.com` expiradas en `propiedades.imagen_url` (commit `9b7eb4f` + `8fb0d73`).
5. CORS no configurado + modal legacy llamando `/crm/activos/pq_15` (commit `b39264c`).

### Pendientes inmediatos
1. **Validación visual del usuario** en `crm.lovbot.ai/dev/crm-v2` — probar en navegador las 3 puertas del modal + tab Relaciones + lotes granulares + paneles GESTIÓN.
2. **Vercel deploy** del último commit `d7b05d0` (tab Relaciones) — puede estar esperando cupo.
3. **Sync dev → prod HTML** (`sync-crm-prod`) cuando el usuario valide todo.

## 🎯 Próximo paso — Sesión 3 Mica

Replicar todo el modelo v3 en Airtable base `appA8QxIhBYYAHw0F`:
- Adapter `db_airtable.py` debe espejar funciones de `db_postgres.py` Robert
- Crear tablas pendientes: Contratos, Alquileres, InmueblesRenta, Inquilinos, PagosAlquiler, Liquidaciones
- Campos `Multiple select` para roles en vez de array Postgres
- Campos `linkedRecord` para FKs entre tablas (Propietarios → InmueblesRenta, etc.)
- Modal unificado + 3 puertas replicado en `demos/SYSTEM-IA/dev/crm-v2.html`
- Fix subnicho Mica: hoy `mica-demo` está como desarrolladora, ocultaba GESTIÓN-Agencia

## 🎯 Pendientes viejos del embedded signup (sigue abierto)

Hoy no se tocó. Sigue como estaba el 21 al final del día:

**Objetivo**: migrar el número demo inmobiliaria de Mica (`+54 9 3765 00-5465`, hoy en Evolution) a Meta Cloud API vía el Tech Provider de Robert.

**Bloqueante**: desconectar el número de Evolution + esperar 24-72h + desinstalar WhatsApp del celular antes del test end-to-end del signup.

Ver commits recientes: `e71028e`, `17b899d`, `d26d634`, `ba5c42d`, `b39264c`, `231eebf`, `d5002d6`, `b0d9a5c`, `9b7eb4f`, `8fb0d73`, `81df11d`, `ca73425`, `9cff805`, `d7b05d0`.

Ver docs detallados:
- `PROYECTO ARNALDO OBSIDIAN/raw/robert/sesion-2026-04-22-crm-v3-robert.md`
- `PROYECTO ARNALDO OBSIDIAN/wiki/sintesis/2026-04-22-crm-v3-robert.md`
- `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/persona-unica-crm.md`
- `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/contratos-polimorficos.md`
