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
| **mica**   | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/SYSTEM-IA/dev/crm-v2.html` | ⚠️ **Modelo único — no hay archivo prod separado** (2026-04-22). El mismo `crm-v2.html` es producción. Las rutas `/system-ia/crm` y `/system-ia/dev/crm` son alias en vercel.json al mismo archivo. | `https://agentes.arnaldoayalaestratega.cloud` | `/mica/demos/inmobiliaria` |
| **robert** | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/dev/crm.html` | `01_PROYECTOS/01_ARNALDO_AGENCIA/demos/INMOBILIARIA/demo-crm-mvp.html` | `https://agentes.lovbot.ai` | `/clientes/lovbot/inmobiliaria` |

Los archivos PROD están en la lista `deny` de `.claude/settings.json`. Este comando usa `cat > PROD` desde Bash (permitido) para evitar la restricción.

---

## Flujo obligatorio (8 pasos)

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

### PASO 3.5 — DETECTOR DE DATOS FAKE HARDCODEADOS (guardia anti-mocks)
**Objetivo**: el HTML dev puede tener datos de prueba/mocks que no deben llegar a prod (nombres inventados, KPIs con valores fijos, teléfonos ficticios, arrays con datos demo). Este paso los detecta antes del sync.

Correr este script sobre el archivo dev y analizar salida:

```bash
DEV_FILE="<ruta al archivo dev>"
python3 <<'EOF'
import re, sys

path = "DEV_FILE"  # reemplazar
with open(path) as f:
    html = f.read()

findings = []

# 1. Nombres comunes de personas en listas obvias (ficticios típicos)
fake_names = [
    "Carlos Mendoza", "Carla Reyes", "Marcos Vega", "María González",
    "Jorge Ramírez", "Ana Torres", "Luis Hernández", "Héctor Castillo",
    "Patricia López", "Roberto Alvarado", "Sandra Ruiz", "Diana Flores",
    "Felipe Morales", "Valentina Cruz", "Andrés Ramos", "Sofía Jiménez",
    "Miguel Díaz", "Luciana Pérez", "Lucía M", "Andrea G", "Carlos M.",
    "Carla R.", "Marcos V.", "Juan Pérez", "María Pérez", "Lucas Romero",
    "Sofía Fernández", "Martín López", "Ana Pereyra", "Roberto Acosta",
    "Valeria Ríos", "Fernanda Aguirre", "Nicolás Herrera", "Patricia Molina",
    "Héctor Vargas"
]
for name in fake_names:
    for i, line in enumerate(html.splitlines(), 1):
        if name in line and "//" not in line[:line.find(name)]:
            findings.append(("NOMBRE_FAKE", i, name, line.strip()[:120]))

# 2. Teléfonos con patrones sospechosos
phone_patterns = [
    r"\+549376[0-9]{7}",         # teléfonos Misiones con patrón repetido
    r"\+52 55 1234-5678",         # secuencial obvio
    r"\+?[0-9]{2,3}[- ]?1234[- ]?5678",
]
for pat in phone_patterns:
    for m in re.finditer(pat, html):
        line_n = html[:m.start()].count("\n") + 1
        findings.append(("TEL_SOSPECHOSO", line_n, m.group(), ""))

# 3. KPIs hardcodeados (números fijos donde debería ir placeholder)
for m in re.finditer(r'<div class="kpi-val"[^>]*>(\d+s?)</div>', html):
    line_n = html[:m.start()].count("\n") + 1
    findings.append(("KPI_HARDCODE", line_n, m.group(1), m.group()))

# 4. Deltas con texto fijo
for m in re.finditer(r'<div class="kpi-delta"[^>]*>([^<]+)</div>', html):
    text = m.group(1).strip()
    if text and text != "&nbsp;" and re.search(r'(\d+|hoy|semana|mes|\$)', text):
        line_n = html[:m.start()].count("\n") + 1
        findings.append(("DELTA_HARDCODE", line_n, text[:60], ""))

# 5. Arrays con datos de demo (buscar consts con >2 objetos y nombres)
array_pattern = re.compile(r'const\s+(\w+)\s*=\s*\[[\s\S]*?\];')
for m in array_pattern.finditer(html):
    body = m.group(0)
    name_count = sum(1 for fn in fake_names if fn in body)
    if name_count >= 2:
        line_n = html[:m.start()].count("\n") + 1
        findings.append(("ARRAY_MOCK", line_n, m.group(1), f"{name_count} nombres fake"))

# 6. Fechas hardcodeadas viejas
date_patterns = [r'"2026-0[1-9]-\d{2}"', r"'2026-0[1-9]-\d{2}'"]
for pat in date_patterns:
    for m in re.finditer(pat, html):
        line_n = html[:m.start()].count("\n") + 1
        findings.append(("FECHA_FIJA", line_n, m.group(), ""))

# 7. Strings de dinero hardcodeado
for m in re.finditer(r'"\$\d{1,3}[,.]?\d{0,3}K?[^"]{0,20}(USD|mes|año)?"', html):
    line_n = html[:m.start()].count("\n") + 1
    findings.append(("DINERO_FIJO", line_n, m.group()[:50], ""))

if not findings:
    print("✅ No se detectaron datos fake hardcodeados")
    sys.exit(0)

print(f"⚠️ {len(findings)} posibles datos fake detectados:")
for tipo, linea, valor, contexto in sorted(set(findings))[:30]:
    print(f"  [{tipo}] línea {linea}: {valor}")
    if contexto:
        print(f"     → {contexto}")

if len(findings) > 30:
    print(f"  ... y {len(findings) - 30} más")
sys.exit(1)
EOF
```

**Interpretación**:
- Exit 0 → no hay datos fake → continuar al paso 4.
- Exit 1 → hay hallazgos → **ABORTAR el sync** y mostrar la lista.

**Qué hacer si hay hallazgos**:
1. Revisar cada línea reportada.
2. Si son datos reales del tenant (ej. nombre real del cliente que coincide con la lista negra) → volver a correr con flag `--force-fake-data` (el usuario asume responsabilidad).
3. Si son mocks de verdad → editar el archivo dev, eliminar los datos fake, volver a correr `/sync-crm-prod`.

**Importante**: este paso existe para que los experimentos, debug, tests y placeholders que vivan en dev NUNCA lleguen a prod sin revisión explícita. Es especialmente útil porque dev está pensado como sandbox — se van a meter cosas de prueba constantemente.

### PASO 4 — Copiar DEMO → PROD
Solo si los pasos 3 y 3.5 pasaron en verde (o el usuario aprobó `--force-fake-data` en 3.5).

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

- **Mica (modelo único)**: https://system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo
- **Mica (alias legacy)**: https://system-ia-agencia.vercel.app/system-ia/crm?tenant=mica-demo (redirige al v2)
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
