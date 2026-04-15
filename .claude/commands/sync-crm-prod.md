---
description: Sync CRM demo → producción con paridad + smoke tests (Mica o Robert)
---

# /sync-crm-prod

Copia el CRM de **desarrollo** al archivo de **producción**, bumpea `CRM_VERSION`, commitea, pushea **y valida que prod quede funcional**. El banner de "nueva versión disponible" aparece automáticamente en los CRMs abiertos.

**Principio**: "demo 100% funcional = prod 100% funcional". El comando **aborta el sync** si detecta que prod va a fallar, y **valida post-deploy** que todo responda correcto.

## Argumento

Usuario debe indicar: **mica** o **robert** (o preguntar si no lo dice).

## Mapeo de archivos + endpoints

| Proyecto | Archivo DEMO (editable) | Archivo PROD (read-only) | Backend URL prod | api_prefix |
|----------|-------------------------|---------------------------|------------------|------------|
| **mica**   | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/crm.html` | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/crm.html` | `https://agentes.arnaldoayalaestratega.cloud` | `/mica/demos/inmobiliaria` |
| **robert** | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/crm.html` | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/demo-crm-mvp.html` | `https://agentes.lovbot.ai` | `/clientes/lovbot/inmobiliaria` |

Los archivos PROD están en la lista `deny` de `.claude/settings.json`. Este comando usa `cat > PROD` desde Bash (permitido) para evitar la restricción.

---

## Flujo obligatorio (7 pasos)

### PASO 1 — Confirmar proyecto
Si no se pasa argumento, preguntar "¿Mica o Robert?". NUNCA asumir.

### PASO 2 — Diff preview
```bash
diff <DEMO> <PROD> | wc -l
```
- Si son idénticos → avisar y abortar (nada que sincronizar).
- Si hay diff → mostrar resumen (líneas agregadas/quitadas). Si detectás cambios sospechosos (credenciales hardcodeadas, URLs invertidas, `console.log` debug), pausar y pedir revisión manual.

### PASO 3 — PARIDAD PRE-SYNC (la capa A)
**Objetivo**: antes de tocar prod, verificar que el backend de prod tiene todo lo que el HTML de dev va a necesitar.

Extraer del HTML dev todas las rutas que invoca:
```bash
grep -oE '\$\{API_BASE\}/[a-zA-Z0-9/_-]+|\$\{SAAS_API\}/[a-zA-Z0-9/_-]+' <DEMO> | sort -u
```

Para cada ruta encontrada, hacer un `curl -o /dev/null -w "%{http_code}"` al backend de prod (timeout 8s). Rutas críticas que **deben** existir:

- `{SAAS_API}/crm/version`
- `{SAAS_API}/tenant/<slug-ejemplo>` (usar `robert` para Robert, `mica-demo` para Mica)
- `{SAAS_API}{api_prefix}/crm/leads` o `/crm/clientes` (una de las 2)
- `{SAAS_API}{api_prefix}/crm/propiedades`
- `{SAAS_API}{api_prefix}/crm/metricas` (opcional pero recomendado)

Clasificar respuestas:
- `200` → OK
- `404` → endpoint NO EXISTE en backend prod
- `500` → endpoint existe pero explota (puede ser config faltante)
- timeout → backend caído o mal configurado

**Si alguna ruta crítica NO responde 200**:
- **ABORTAR el sync**.
- Reportar: "❌ Prod no está listo. Endpoint `X` responde `Y`. Ejecutá [acción sugerida] antes de sincronizar."
- Acciones sugeridas comunes:
  - `404` → "agregar endpoint en worker → `/crm/<ruta>` en `workers/clientes/<proyecto>/worker.py`"
  - `500` → "revisar env vars Coolify (probable falta SUPABASE_URL / SUPABASE_KEY / otras)"
  - timeout → "verificar que el servicio en Coolify esté UP + redeploy"

### PASO 4 — Copiar DEMO → PROD
Solo si el paso 3 pasó todo en verde.

```bash
cat <DEMO> > <PROD>
diff -q <DEMO> <PROD>  # debe decir "son idénticos" o sin output
```

### PASO 5 — Bumpear versiones
Leer versión actual de DEMO con `grep "const CRM_VERSION" <DEMO>`.

- Si es `X.Y.Z-dev` → prod queda en `X.Y.Z` y dev pasa a `X.Y.(Z+1)-dev`
- Si no tiene `-dev` → prod queda igual a dev, dev pasa a `X.Y.(Z+1)-dev`

Preguntar al usuario si confirma la versión propuesta o quiere otra.

Aplicar con `sed -i "s/const CRM_VERSION = '.*';/const CRM_VERSION = 'NUEVA';/"` en ambos archivos.

### PASO 6 — Commit + push
- Staged: los 2 archivos (demo + prod).
- Mensaje: `sync(crm-<proyecto>): prod → vX.Y.Z desde dev`
- Push: `git push origin master:main`

### PASO 7 — SMOKE TEST POST-DEPLOY (la capa B)
**Objetivo**: verificar que la versión que acaba de deployar Vercel funciona de verdad.

1. **Esperar deploy Vercel**: pollear `https://<dominio-prod>` cada 15s hasta 120s o hasta que la nueva versión del HTML esté servida. Detectar buscando el nuevo `CRM_VERSION` en el HTML descargado:
   ```bash
   curl -s "<URL_PROD>" | grep -oE "CRM_VERSION = '[^']+'" | head -1
   ```

2. **Pegar a endpoints críticos (prod, no dev)** — mismas rutas del paso 3 pero volviendo a verificar después del deploy:
   - `GET /crm/version` → debe devolver JSON con `version`
   - `GET /tenant/<slug>` → debe devolver JSON con `slug` y `nombre`
   - `GET {api_prefix}/crm/leads` → debe devolver `{records: [...]}` y `total >= 0`
   - `GET {api_prefix}/crm/propiedades` → idem

3. **Reporte final**:
   - ✅ Verde si todo OK → `"✅ Sync completo. Prod v{X.Y.Z} funcional. URL: <url>"`
   - ⚠️ Amarillo si deploy OK pero algún endpoint lento/raro → `"⚠️ Sync OK pero: <lista warnings>"`
   - ❌ Rojo si algún endpoint crítico rompe → `"❌ Prod ROTO en <endpoint>. Recomendación: /rollback-crm-prod <proyecto>"`

---

## URLs de verificación

- **Mica prod**: https://system-ia-agencia.vercel.app/system-ia/crm?tenant=mica-demo
- **Mica dev**:  https://system-ia-agencia.vercel.app/system-ia/dev/crm?tenant=mica-demo
- **Robert prod**: https://crm.lovbot.ai/?tenant=robert
- **Robert dev**:  https://lovbot-demos.vercel.app/dev/crm?tenant=robert

---

## Reglas irrompibles

- **NUNCA editar prod a mano.** Siempre pasa por este comando.
- **NUNCA tocar el CRM del otro proyecto.** Si el usuario dice "mica", no tocar Robert y viceversa.
- **NUNCA saltear el paso 3** (paridad pre-sync). Ese paso es el que impide "romper prod".
- **NUNCA saltear el paso 7** (smoke post-deploy). Sin validación post-deploy, no hay forma de saber si el sync funcionó.
- **Commit atómico**: demo + prod en el mismo commit para que la versión quede alineada.
- **Si el smoke test falla**: recomendar `/rollback-crm-prod` — NO intentar fixes ad-hoc sobre prod.
