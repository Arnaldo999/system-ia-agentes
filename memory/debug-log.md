# Debug y errores frecuentes

## 2026-04-22 — Bug histórico de tokens: por qué pedíamos credenciales una y otra vez

**Síntoma**: Arnaldo mostró captura de Coolify con 4 tokens emitidos (`worker-arnaldo`, dos `agentes`, `flujos agenticos`). Cada subagente le pedía un token Coolify "porque no funcionaba", aunque ya había 1 guardado en `.env`.

**Causa raíz (3 capas)**:
1. **Quoting**: `COOLIFY_TOKEN='3|9jSOO...'` con comillas SIMPLES en `.env` raíz. `bash source .env` rompe en el `|` (lo lee como pipe) → "orden no encontrada" → token nunca se cargaba en variables de entorno → API auth devolvía 401.
2. **Lookup incompleto**: subagentes buscaban `COOLIFY_TOKEN` solo en `.env` del backend monorepo (donde NO estaba — solo `COOLIFY_ROBERT_TOKEN`). El de Arnaldo vivía solo en `.env` raíz Mission Control.
3. **Síntoma engaño**: 401 lo interpretaban como "token inválido/expirado" y pedían uno nuevo. La verdad era "token correcto, mal cargado".

**Fix definitivo**:
- Cambiar TODOS los tokens con `|` a comillas DOBLES: `COOLIFY_TOKEN="3|9jSOO..."`. Aplicado a `.env` raíz y `.env` backend (también el `COOLIFY_ROBERT_TOKEN`).
- Agregado `COOLIFY_TOKEN` (Arnaldo) al `.env` del backend monorepo, no solo al raíz, para que `guardia_critica.py` lo encuentre directo.
- Memoria persistente nueva: `feedback_REGLA_env_quoting_y_lookup.md` — antes de pedir token Coolify, agotar lookup en ambos `.env` y validar con curl.

**Validación**: `curl Bearer $COOLIFY_TOKEN /api/v1/applications` → HTTP 200 con app `system-ia-agentes` running:healthy.

**Acción pendiente para Arnaldo**: revocar manualmente desde panel Coolify los 3 tokens viejos no usados (dejar solo el `agentes` que figura como "Last used: 4 hours ago").

## 2026-04-22 — Hallazgo: la Guardia Crítica YA estaba programada hace 11 días, solo le faltaban env vars

**Descubierto al integrar guardia_critica.py**: la Scheduled Task "Guardia Crítica" (`*/5 * * * *  cd /app/scripts && python guardia_critica.py`) ya existía en Coolify desde 2026-04-11 (UUID `fo5l5or8bbz3bl8d0n47dj9a`). Llevaba 11 días corriendo sin alertar — no porque todo estuviera bien, sino porque le faltaban las env vars `COOLIFY_API_URL`, `COOLIFY_APP_UUID`, `FASTAPI_URL`, `N8N_URL` y el script crasheaba antes de poder mandar Telegram.

**Fix**: Agregadas las 4 env vars vía API Coolify (`POST /api/v1/applications/<uuid>/envs`). Disparado deploy `ph3xsqna8ag7vowvmsgzwjht` para que el container las recoja. Eliminada la Scheduled Task duplicada que mi subagente había creado.

**Lección**: antes de "crear" un cron en Coolify, listar `GET /scheduled-tasks` y verificar si ya existe.

## 2026-04-22 — CRM Maicol caído por CORS + monitor Capa 1 instalado

**Síntoma**: `crm.backurbanizaciones.com` mostraba "Failed to fetch" y "Cargando leads…" infinito. Maicol avisó.

**Causa**: El `CORSMiddleware` del backend FastAPI Arnaldo (`agentes.arnaldoayalaestratega.cloud`) no tenía `https://crm.backurbanizaciones.com` en `allow_origins`. Preflight OPTIONS rechazado sin header `Access-Control-Allow-Origin`.

**Fix**: Agregado el origen al `CORSMiddleware` en `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/main.py`. Commit `a681a5c`. Validado con preflight OPTIONS → `200` + header correcto.

**Lección y acción permanente — Monitor Capa 1 (guardia_critica.py)**:
- Script definitivo: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/scripts/guardia_critica.py`
- 9 checks: FastAPI Arnaldo, n8n Arnaldo, n8n Mica, n8n Lovbot, Coolify app, Maicol CRM CORS preflight, Maicol CRM frontend, Chatwoot Arnaldo, Backend Robert (ping externo)
- Envío CONSOLIDADO: 1 solo Telegram con todos los fallos juntos (no un mensaje por servicio)
- Cooldown 30 min por servicio (no spamea)
- Kill switch: env var `GUARDIA_DISABLED=1`
- Deploy: Coolify Hostinger → Scheduled Tasks `*/5 * * * *  python scripts/guardia_critica.py`
- Vars de entorno a configurar en Coolify (ver sección abajo)
- Commit: `[ver commit guardia_critica refactor]`

### Env vars a configurar en Coolify (app FastAPI Arnaldo — Hostinger)

Ir a `coolify.arnaldoayalaestratega.cloud` → app `system-ia-agentes` → Environment Variables → agregar:

```
TELEGRAM_BOT_TOKEN=<token del bot>
TELEGRAM_CHAT_ID=863363759
COOLIFY_API_URL=https://coolify.arnaldoayalaestratega.cloud
COOLIFY_TOKEN=<token API Coolify Arnaldo>
COOLIFY_APP_UUID=ygjvl9byac1x99laqj4ky1b5
FASTAPI_URL=https://agentes.arnaldoayalaestratega.cloud
N8N_URL=https://n8n.arnaldoayalaestratega.cloud
```

Luego en Coolify → Scheduled Tasks → agregar:
- Schedule: `*/5 * * * *`
- Command: `python scripts/guardia_critica.py`

Para deshabilitar temporalmente sin tocar el cron: agregar env var `GUARDIA_DISABLED=1`.

### Resultado del run local (2026-04-22)

Con COOLIFY_TOKEN correcto, los 9 checks pasan. Con token bogus y N8N_URL bogus, se mandó correctamente 1 Telegram consolidado con 2 alertas juntas — formato correcto.

## 2026-04-22 — Refinamiento checks Robert en guardia_critica.py (chat con Robert)

**Motivo**: Arnaldo habló con Robert y confirmó el esquema real del CRM Lovbot. La URL que se monitoreaba (`crm.lovbot.ai/` raíz) no era la que importaba — el modelo real del CRM vive en `/dev/crm-v2`.

**Esquema confirmado por Robert**:
- `https://crm.lovbot.ai/?tenant=robert` → YA NO EXISTE (URL legacy, descartada).
- `https://crm.lovbot.ai/dev/crm-v2` → CRM modelo real (template del que se replica para cada cliente futuro).
- `https://lovbot-demos.vercel.app/dev/admin` → Panel de Gestión (admin para crear/configurar tenants). Crítico.
- `https://crm.lovbot.ai/` (raíz) → sigue siendo 200 (sirve HTML), vale como check de disponibilidad de dominio.
- `https://admin.lovbot.ai/` → sin cambios.
- `https://agentes.lovbot.ai/health` → sin cambios.

**Cambios aplicados en `scripts/guardia_critica.py`**:
- `check_robert_crm_frontend` → renombrado a `check_robert_crm_modelo`, apunta a `/dev/crm-v2`.
- Nuevo `check_robert_crm_dominio` → GET `crm.lovbot.ai/` (raíz, 200 = dominio responde).
- Nuevo `check_robert_panel_gestion` → GET `lovbot-demos.vercel.app/dev/admin` (200).
- `check_robert_crm_cors` → sin cambios (preflight con Origin `crm.lovbot.ai` sigue siendo correcto).
- `check_robert_admin` → sin cambios.
- Vars env: `ROBERT_CRM_URL` → `ROBERT_CRM_MODELO_URL` + nuevas `ROBERT_CRM_DOMINIO_URL` y `ROBERT_PANEL_GESTION_URL`.

**Resultado run local post-cambio**: 14 checks activos OK, 2 Mica deshabilitados (skip). Todo verde.

**TODOs futuros**:
- Cuando se replique el modelo para clientes reales de Lovbot (ej: subdominios o tenant-paths), agregar checks por cliente.
- Cuando Arnaldo y Robert armen el "CRM agencia" (hablado el 22/04), sumar check a la guardia.
- Nuevas env vars a agregar en Coolify Hostinger si se quieren cambiar las URLs por defecto:
  - `ROBERT_CRM_MODELO_URL` (default: `https://crm.lovbot.ai/dev/crm-v2`)
  - `ROBERT_CRM_DOMINIO_URL` (default: `https://crm.lovbot.ai`)
  - `ROBERT_PANEL_GESTION_URL` (default: `https://lovbot-demos.vercel.app/dev/admin`)

## 2026-04-22 — Guardia Crítica ampliada: checks Robert CRM/admin + Mica preparado

**Cambio**: se sumaron 5 checks nuevos a `guardia_critica.py` (total 14 en el dict, 12 activos + 2 deshabilitados).

**3 checks Robert (LIVE, habilitados)**:
- `robert_crm` → GET `https://crm.lovbot.ai/` → espera 200. Agnóstico a v1/v2 (el dominio no cambia con sync-crm-prod).
- `robert_crm_cors` → OPTIONS `https://agentes.lovbot.ai/health` con `Origin: https://crm.lovbot.ai`. Valida 200/204 + ACAO correcto.
- `robert_admin` → GET `https://admin.lovbot.ai/` → 200.

**2 checks Mica (deshabilitados — `enabled=False` via env var)**:
- `mica_crm` → GET `$MICA_CRM_URL` (default: `https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2`).
- `mica_crm_cors` → preflight al backend Arnaldo con `Origin: $MICA_CRM_URL`.

**Patrón de deshabilitar**: las funciones retornan `None` si `MICA_CRM_ENABLED != "1"`. El loop de `main()` hace `continue` en `None` y loggea `deshabilitado (skip)`.

**Cómo activar Mica cuando entre a prod**:
1. Definir dominio prod con Arnaldo (ej: `crm.systemia.com`).
2. En Coolify → app `system-ia-agentes` → env vars: `MICA_CRM_URL=https://crm.systemia.com` y `MICA_CRM_ENABLED=1`.
3. Redeploy automático. Próximo ciclo cron ya los corre.

**Run local confirmado (2026-04-22)**:
```
[guardia] OK  FastAPI Arnaldo: healthy, workers=6
[guardia] OK  n8n Arnaldo: ok
[guardia] OK  n8n Mica: ok
[guardia] OK  n8n Lovbot: ok
[guardia] OK  Coolify app: status=running:healthy
[guardia] OK  Maicol CRM — preflight CORS: CORS ok (ACAO=https://crm.backurbanizaciones.com)
[guardia] OK  Maicol CRM — frontend: HTTP 200
[guardia] OK  Chatwoot Arnaldo: HTTP 200
[guardia] OK  Backend Robert (ping externo): HTTP 200
[guardia] OK  Robert CRM frontend: HTTP 200
[guardia] OK  Robert CRM CORS: CORS ok (ACAO=https://crm.lovbot.ai)
[guardia] OK  Robert admin: HTTP 200
[guardia] --- Mica CRM frontend: deshabilitado (skip)
[guardia] --- Mica CRM CORS: deshabilitado (skip)
[guardia] Todo OK — sin alertas a enviar
```


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

## 2026-04-22 — CORS bloqueaba CRM Maicol (Back Urbanizaciones)

### Bug: CRM crm.backurbanizaciones.com no podía hacer fetch al backend
**Síntoma**: Todos los endpoints `/clientes/arnaldo/maicol/crm/*` devolvían error CORS en consola Chrome. UI mostraba "Failed to fetch" / "Cargando leads..." infinito / funnels en 0.
**Causa raíz**: `main.py` CORSMiddleware tenía en `allow_origins` solo orígenes Lovbot (`crm.lovbot.ai`, `lovbot-demos.vercel.app`, `admin.lovbot.ai`) + localhost. El origen `https://crm.backurbanizaciones.com` NUNCA fue agregado — omisión histórica desde que se configuró CORS (commit `b39264c`).
**Fix**: agregar `"https://crm.backurbanizaciones.com"` como primer elemento de `allow_origins` en `main.py`, con comentario de sección para Arnaldo/Maicol.
**Commit**: `a681a5c` — push `master:main` — Coolify Hostinger autodeploy.
**Validación post-deploy**: esperar redeploy y confirmar preflight OPTIONS con `Access-Control-Allow-Origin: https://crm.backurbanizaciones.com`.
**Nota**: el backend estaba VIVO (respondía 405 al GET — correcto para rutas POST). El problema era 100% CORS, no caída del servidor.

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

## 2026-04-22 — Sesión CRM v3 Mica — bugs/decisiones notables

### Decisión: polimorfismo Airtable con 3 linkedRecord
Airtable NO tiene FK polimórfica como Postgres. En vez de `item_tipo + item_id`, tabla Contratos Mica tiene 3 campos `linkedRecord` separados (Lote_Asignado, Propiedad_Asignada, Inmueble_Asignado). Solo UNO se setea por contrato. Adapter serializa a misma forma JSON que Robert para que el frontend sea portable.

### Bug: record_id int vs string en endpoints CRUD
**Síntoma**: crear/borrar propietarios/inmuebles/inquilinos devolvía 422 en Mica.
**Causa raíz**: los handlers del worker Mica estaban declarados con `record_id: int` (copiados de Robert) pero Airtable usa IDs tipo `rec12345abc...` (strings).
**Fix**: reemplazar `record_id: int` → `record_id: str` en todos los endpoints CRM del worker Mica.
**Commit**: `a616f70`.

### Decisión: Contratos.Tipo limitado a venta/reserva/alquiler/boleto en Airtable
**Síntoma**: el backend Robert usa `venta_lote/venta_casa/venta_terreno/venta_unidad` como valores válidos del campo Tipo. Mica no.
**Causa raíz**: el campo singleSelect en Airtable fue creado con opciones `venta/reserva/alquiler/boleto` de antes del refactor. Modificar las opciones vía Metadata API requiere PATCH del campo completo (destructivo si no se cuida).
**Decisión**: backend Mica mapea los subtipos granulares a `venta` en Airtable + guarda el subtipo en `Item_Descripcion` (texto libre). Si se quieren granulares explícitos en Airtable a futuro, requiere autorización del usuario.

### Decisión: sin transacciones — log warnings
**Síntoma**: operaciones multi-paso (crear cliente + contrato + update item) no son atómicas en Airtable.
**Fix**: el handler hace los pasos secuencialmente. Si uno falla, loguea WARNING y devuelve el estado parcial. El frontend puede reintentar. NO deshacer pasos exitosos anteriores (no hay ROLLBACK).

### Decisión: campo Origen_Creacion removido de Contratos
**Síntoma**: error 422 al crear contrato porque Airtable no tenía el campo `Origen_Creacion` en la tabla Contratos (sí lo tiene CLIENTES_ACTIVOS pero no Contratos).
**Fix**: el backend Mica quita ese campo del payload antes de enviar a Airtable. El origen se guarda solo en CLIENTES_ACTIVOS al crear el cliente.
**Commit**: `a9dc86a`.
