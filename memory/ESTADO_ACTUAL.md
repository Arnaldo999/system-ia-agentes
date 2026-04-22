# ESTADO ACTUAL

Fecha: 2026-04-22 (tarde) ART
Responsable última actualización: Claude Opus 4.7 / Arnaldo

## 🎯 Regla operativa NUEVA — Coolify default (2026-04-22)

Desde ahora, **cualquier HTML/sitio/propuesta/formulario nuevo se deploya en Coolify Hostinger**, no en Vercel. Motivo: cupo Hobby Vercel 100 deploys/día se agotó en 2 sesiones seguidas.

Patrón: archivos en `backends/system-ia-agentes/clientes-publicos/{slug}/` → `git push` → auto-deploy en ~30s → URL `agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/archivo.html`.

**Vercel solo se mantiene para**:
- Apps existentes ya productivas (`crm.lovbot.ai` hasta migrarse, `system-ia-agencia.vercel.app` hasta que Mica compre dominio)

**Migraciones agendadas**:
- **Robert** → Coolify Hetzner Robert (2026-04-23, tras reset cupo Vercel de hoy)
- **Mica** → diferida (sin dominio propio aún)

Ver doc completa: `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/coolify-default-deploy.md`

---

## 🎯 Abierto — Cliente nuevo Cesar Posada (agencia turismo)

**Estado**: propuesta enviada, esperando brief.

**Contacto**: Cesar Posada (persona, la marca de su agencia se confirma en el brief)
**Vertical**: agencia de turismo / viajes
**Cliente de**: Arnaldo (directo, NO Mica ni Robert)

**Entregables LIVE**:
- Formulario: https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/brief.html
- Propuesta: https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/propuesta.html

**Precios enviados**:
- Implementación única: USD 300
- Mantenimiento: USD 80/mes

**Mensaje WhatsApp enviado**: Arnaldo ya le mandó los 2 links con el resumen.

**Próximos pasos** (cuando Cesar envíe el brief .md):
1. Copiar el brief recibido a `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/cesar-posada/brief-recibido-YYYY-MM-DD.md`
2. Crear base Airtable nueva para turismo (tablas: Leads, Clientes_Activos, Paquetes, Asesores, Conversaciones, Destinos)
3. Scaffold worker en `workers/clientes/arnaldo/cesar-posada/worker.py` basado en patrón Maicol
4. Scaffold CRM web en `demos/turismo/dev/crm-v2.html` como template del nicho
5. Onboarding WhatsApp YCloud
6. Deploy Coolify Hostinger + smoke tests
7. Capacitación

**Docs de referencia**:
- Entidad Obsidian: `PROYECTO ARNALDO OBSIDIAN/wiki/entidades/cesar-posada.md`
- Síntesis: `PROYECTO ARNALDO OBSIDIAN/raw/arnaldo/sesion-2026-04-22-brief-cesar-posada.md`
- Patrón reutilizable: `PROYECTO ARNALDO OBSIDIAN/wiki/conceptos/onboarding-cliente-nuevo-arnaldo.md`

---

## 🎯 Hito cerrado — CRM v3 Mica COMPLETO (misma jornada que Robert)

Replicado el modelo v3 en el stack Airtable de Mica con paridad funcional completa. Sesión 3 de 3 fases:

- **Fase 1** — Schema Airtable `appA8QxIhBYYAHw0F`: 39 campos nuevos agregados (roles, linkedRecords polimórficos, campos cuotas, etc.). Tenant mica-demo con subniche=mixto.
- **Fase 2** — Backend adapter `db_airtable.py` +978 líneas: helpers `_at_*`, serializer polimórfico, 12 endpoints nuevos espejo de Robert. Smoke tests 11/11 OK.
- **Fase 3** — Frontend `demos/SYSTEM-IA/dev/`: 5 JS nuevos, `crm-v2.html` +657 líneas, paleta ámbar respetada (64× `#f59e0b`, 0× purple). Deploy Vercel inmediato.

**Commits Mica**: `5ef5303` → `a9dc86a` → `a616f70` → `e3817bb`.
**Producción Vercel Mica**: `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo` (deployado).
**Backend Mica**: `https://agentes.arnaldoayalaestratega.cloud/clientes/system_ia/demos/inmobiliaria`.

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

## 🎯 Próximo paso — validación visual Mica + pendientes menores

1. **Hard reload** en `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo` y probar:
   - PIN demo `1234`
   - Modal unificado "Nuevo contrato" desde panel Clientes Activos
   - Tab "Relaciones" en ficha de cliente
   - Paneles GESTIÓN (Inmuebles, Inquilinos, Pagos, Liquidaciones, Propietarios) — crear 1 de cada para validar
   - Sidebar acordeón 3 grupos (Desarrolladora / Agencia / Mixto)

2. **Panel loteos granular Mica** — pendiente portar CRUD por manzana/lote (botones +Manzana, +lote, renombrar, borrar individual). Backend ya tiene `/crm/lotes-mapa/seguro` y `/crm/loteos/{id}/lotes`.

3. **Tipos granulares** Airtable Contratos.Tipo — autorizar PATCH si se quiere `venta_lote` vs `venta_casa` a nivel DB (hoy se guarda como `venta` + subtipo en `Item_Descripcion`).

4. **Sync dev → prod HTML** (`sync-crm-prod`) cuando el usuario valide todo.

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
