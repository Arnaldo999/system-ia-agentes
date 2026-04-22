# Debug y errores frecuentes

## n8n HTTP Request — JSON inválido
- Causa: JSON body pegado como literal o con prefijo incorrecto (por ejemplo "=={{").
- Solucion: usar modo Expression y un prefijo unico "={{...}}".

## Render — "failed to read dockerfile: open Dockerfile: no such file or directory"
- Causa: Render busca el Dockerfile en la raíz del repo, pero el proyecto es un monorepo y el Dockerfile está en un subdirectorio.
- Solución: Configurar `rootDir` en Render vía API o Dashboard → Settings → Build.
  ```bash
  curl -X PATCH "https://api.render.com/v1/services/<SERVICE_ID>" \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"rootDir": "ruta/al/subdirectorio"}'
  ```
- Service ID Maicol: `srv-d6g8qg5m5p6s73a00llg`
- rootDir correcto: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`

## Render — Bot muestra versión vieja del código
- Causa: Render despliega branch `main` pero los commits iban a `master`.
- Solución: `git push origin master:main --force` para sincronizar branches.

## Dockerfile — wget falla en Render free tier
- Causa: `wget` de archivos de fuentes desde GitHub agota timeout en Render free.
- Solución: Eliminar descarga de fuentes Inter; usar solo `fonts-dejavu-core` desde apt (ya incluido en `python:3.11-slim`).

## import time mal ubicado en Python
- Causa: `import time` puesto dentro de un bloque de código (dentro de una función o sección) en lugar del top-level.
- Solución: Todos los imports al inicio del archivo, antes de cualquier código.

## 2026-04-22 — Sesión CRM v3 Robert — bugs notables fixeados

### Bug: `tenant_slug specified more than once` al POST de GESTIÓN
**Síntoma**: HTTP 422 al crear propietario/inmueble/inquilino/pago/liquidación.
**Causa raíz**: `db_postgres.py _crud_generico()` hacía `cols = ["tenant_slug"] + list(campos.keys())` donde `campos` venía del body request y YA traía `tenant_slug` → tabla dobla la columna.
**Fix**: filtrar del dict antes: `campos_clean = {k:v for k,v in campos.items() if k != "tenant_slug"}`.
**Commit**: `d26d634` — aplicado a todos los endpoints que usan _crud_generico.

### Bug: UNIQUE constraint lotes_mapa bloqueaba A-1 + B-1 coexistir
**Síntoma**: crear B-777 devolvía 409 "Ya existe un lote con ese numero en esa manzana" aunque la constraint debería permitirlo (distinta manzana).
**Causa raíz**: había DOS constraints UNIQUE simultáneos:
- `lotes_mapa_tenant_slug_loteo_id_numero_lote_key` (auto-generado Postgres, sin manzana) — el culpable
- `uq_lotes_mapa_tenant_loteo_manzana_nro` (correcto, con manzana)
**Fix**: `fix-lotes-constraint-v2` — dropea TODOS los UNIQUE sin manzana **por definición** (no por nombre). El primer intento fallaba porque buscaba por nombre específico.
**Commits**: `0fa97c6` (endpoint) + `ba5c42d` (excluir PK del check).

### Bug: lote vendido no mostraba cliente asignado
**Síntoma**: click en A-01 (vendido) mostraba "LOTEO Palo Alto" pero no los datos del cliente que lo compró.
**Causa raíz**: triple bug concatenado.
1. `panel-loteos.js` cargaba `/crm/clientes` (leads) en vez de `/crm/activos` (clientes firmados). `cliente_id` del lote apunta a `clientes_activos`.
2. Backend devuelve IDs con prefijo `"pg_16"`, lote guarda `cliente_id=16` (int). `find(c => c.id === cliente_id)` siempre falso.
3. Backend devuelve campos capitalizados (`Nombre`, `Telefono`, `Propiedad`) pero código leía `c.nombre`, `c.telefono`.
**Fix**: 
- Cambiar endpoint en 3 puntos de `panel-loteos.js` a `/crm/activos`.
- Agregar helper `clienteMatches(c, id)` que normaliza quitando prefijo `pg_`.
- Fallback `c.Nombre || c.nombre` en todos los accesos.
**Commit**: `d5002d6`.

### Bug: CORS bloqueando fetch de frontend
**Síntoma**: consola con "has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header".
**Causa raíz**: `main.py` tenía `allow_origin_regex=r"https?://.*"` con `allow_credentials=True`. Spec CORS prohíbe esa combinación — browsers rechazan.
**Fix**: whitelist explícita de orígenes (`crm.lovbot.ai`, `lovbot-demos.vercel.app`, `*.vercel.app` regex, localhost puertos 8765/8766). Credentials=true compatible con orígenes concretos.
**Commit**: `b39264c`.

### Bug: HTTP 410 masivo en consola
**Síntoma**: 10+ errores `Failed to load resource: 410` al cargar CRM.
**Causa raíz**: columna `propiedades.imagen_url` tenía URLs firmadas `airtableusercontent.com` expiradas hace 10 días. Eran data de seed migrada desde Airtable al Postgres (Robert NO usa Airtable — eran strings legacy en DB).
**Fix**: 
- Backend: `UPDATE propiedades SET imagen_url = NULL WHERE imagen_url LIKE '%airtableusercontent%'`.
- Frontend: helper `getPropertyImage(p)` que ignora URLs de Airtable y devuelve placeholder 🏠.
**Commits**: `9b7eb4f` (backend) + `8fb0d73` (frontend).

### Bug: sidebar GESTIÓN ocultaba grupos por subnicho
**Síntoma**: tenant demo (desarrolladora) NO veía el grupo "AGENCIA" del sidebar.
**Causa raíz**: `groupConfig.desarrolladora.show = ['desarrolladora', 'mixto']` — el grupo agencia no figuraba en la lista, se seteaba `data-hidden="true"`.
**Fix**: todos los subnichos muestran TODOS los grupos. `show: ALL_GROUPS`. El subnicho solo decide cuál abre por default. UI más flexible para el usuario.
**Commit**: `b0d9a5c`.

### Bug: Vercel deploy cupo 100/día agotado
**Síntoma**: git push a main no se reflejaba en `crm.lovbot.ai`. Dashboard Vercel mostraba "Resource is limited - try again in 24 hours".
**Causa raíz**: Plan Hobby tiene límite 100 deploys/día. Hicimos 20+ commits y el límite se activó.
**Mitigación**: esperar reset (medianoche UTC). Redeploy del último commit (gratis, no cuenta). O upgrade a Pro ($20/mes, 6000/día).
**No requiere fix en código** — limitación de plan.
