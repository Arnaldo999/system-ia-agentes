# Refactor Postgres — arquitectura "workspaces" estilo Airtable

Fecha: 2026-04-21
Autor: Arnaldo + Claude

---

## 🚨 REGLA #0 IRROMPIBLE

**Ningún cliente puede ver o escribir datos de otro cliente. Sería catastrófico.**

- Aislamiento FÍSICO por database Postgres (no por columna `tenant_slug`)
- Cada cliente = su propia DB aislada a nivel engine
- Un bug de código, un env mal seteado, un LLM confundido NUNCA pueden cruzar datos porque las DBs son físicamente separadas
- NO onboardear ningún cliente real hasta que esto esté implementado

---

## Decisión arquitectónica

**Una sola instancia Postgres en Coolify Hetzner.**
**Múltiples databases dentro (workspaces).**
**Cada cliente = una database aislada con sus tablas propias.**

Ejemplo:
```
postgres://5.161.235.99:5432/
├── robert_crm       ← DEMO maestro (modelo que se duplica)
├── cliente_a_crm    ← cliente real #1
├── cliente_b_crm    ← cliente real #2
└── ...
```

Sin columna `tenant_slug`. Aislamiento por database.

---

## Estado actual (auditado 2026-04-21)

1 única DB (probablemente `lovbot_crm` o `robert_crm`) con:
- tabla `leads` (28 filas: 19 tenant='demo' + 9 tenant='robert')
- tabla `propiedades` (116 filas, sin desglose aún)
- tabla `clientes_activos` (12 filas)
- probablemente también: `loteos`, `contratos`, `visitas`, `asesores`, `propietarios`
- columna `tenant_slug` en todas

---

## Plan de migración (ejecutar cuando Vercel abra)

### Paso 1 — Snapshot completo antes de tocar

```bash
# En el servidor Hetzner, como postgres user
pg_dump robert_crm > /backups/robert_crm_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Paso 2 — Renombrar DB actual como DB maestra "demo"

Si la DB actual se llama `lovbot_crm`:
```sql
ALTER DATABASE lovbot_crm RENAME TO robert_crm;  -- si no se llama así ya
```

Si la DB actual ya se llama `robert_crm` y Robert-persona tiene datos reales ahí mezclados con demo:
```bash
# Crear DB nueva robert_prod_crm para datos reales de Robert
createdb robert_prod_crm
pg_dump -d robert_crm --data-only --where="tenant_slug='robert'" | psql robert_prod_crm
```

### Paso 3 — Limpiar robert_crm (DB demo)

```sql
-- Dentro de robert_crm
DELETE FROM leads WHERE tenant_slug != 'demo';
DELETE FROM propiedades WHERE tenant_slug != 'demo';
DELETE FROM clientes_activos WHERE tenant_slug != 'demo';
DELETE FROM loteos WHERE tenant_slug != 'demo';
-- etc para todas las tablas

-- Después, eliminar columna tenant_slug (ya no hace falta)
ALTER TABLE leads DROP COLUMN tenant_slug;
ALTER TABLE propiedades DROP COLUMN tenant_slug;
ALTER TABLE clientes_activos DROP COLUMN tenant_slug;
ALTER TABLE loteos DROP COLUMN tenant_slug;
-- etc
```

### Paso 4 — Limpiar datos sucios en robert_crm

Revisar y decidir:
- Lead "Bobo" (Waterloo/Cancún) → eliminar, es residuo de test
- Lead "Invertir" (tu número) → eliminar o renombrar a "Arnaldo"

### Paso 5 — Refactor código worker demo

En `workers/demos/inmobiliaria/db_postgres.py`:
```python
# Eliminar
TENANT = os.environ.get("LOVBOT_TENANT_SLUG", "demo")

# Quitar de TODAS las queries
"WHERE tenant_slug=%s AND telefono=%s"
# Pasar a
"WHERE telefono=%s"
```

En `workers/demos/inmobiliaria/worker.py`:
- Quitar `tenant_slug` de todos los INSERTs
- Quitar filtros `WHERE tenant_slug=` de todos los SELECTs
- Aceptar que la DB conecta solo a robert_crm y toda data pertenece al demo

### Paso 6 — Refactor workflow n8n IA

Workflow `CRM IA - Ejecutar SQL` (0t32XZ9AuQXB9fOn):
- Eliminar función `inyectarTenant()` completa del Validator
- La credencial PG ya apunta a una sola DB (robert_crm), no necesita inyección

Workflow `CRM IA - Asistente Inmobiliario` (fKeUXQXxpI0xUKGs):
- Eliminar referencia a `tenant_slug` del systemMessage
- El agente ya no necesita filtrar por tenant — la DB es única

### Paso 7 — Script de onboarding cliente nuevo

Crear `02_OPERACION_COMPARTIDA/scripts/onboarding_cliente_lovbot.sh`:
```bash
#!/bin/bash
# Uso: ./onboarding_cliente_lovbot.sh <slug_cliente>
# Crea una DB nueva copiando la estructura (schema) de robert_crm

SLUG=$1
DB_SOURCE="robert_crm"
DB_TARGET="${SLUG}_crm"

# 1. Crear DB nueva
psql -c "CREATE DATABASE ${DB_TARGET};"

# 2. Copiar solo estructura (schema-only, sin datos)
pg_dump --schema-only ${DB_SOURCE} | psql ${DB_TARGET}

# O si querés copiar con datos ejemplo:
# pg_dump ${DB_SOURCE} | psql ${DB_TARGET}

# 3. Crear usuario dedicado (opcional pero recomendado)
psql -c "CREATE USER ${SLUG}_user WITH PASSWORD 'xxx';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_TARGET} TO ${SLUG}_user;"

echo "DB ${DB_TARGET} creada. Configurar worker con:"
echo "  LOVBOT_PG_DB=${DB_TARGET}"
echo "  LOVBOT_PG_USER=${SLUG}_user"
```

### Paso 8 — Deploy de cada cliente en Coolify

Cada cliente real tiene SU PROPIO worker Coolify con env vars apuntando a SU DB:
- cliente_a: `LOVBOT_PG_DB=cliente_a_crm`
- cliente_b: `LOVBOT_PG_DB=cliente_b_crm`

Sin posibilidad técnica de leer datos cruzados: el worker conecta a una DB concreta y punto.

### Paso 9 — Workflow n8n IA por cliente

2 opciones:

**A. Un workflow por cliente** (más aislado pero más mantenimiento)
- `CRM IA - Ejecutar SQL - Robert` → conecta a `robert_crm`
- `CRM IA - Ejecutar SQL - Cliente A` → conecta a `cliente_a_crm`

**B. Un solo workflow que recibe el nombre de DB en el webhook**
- El frontend manda `{"db_name": "cliente_a_crm"}` junto con el mensaje
- El workflow switchea la credencial dinámicamente
- Requiere auth token fuerte para no permitir bypass

**Recomendación**: Opción A (simplicidad + aislamiento físico).

---

## Checklist pre-ejecución

- [ ] Vercel disponible (cuota deploy reset)
- [ ] Snapshot completo Postgres confirmado
- [ ] Confirmar con Arnaldo que `robert_crm` es la DB del demo (no de Robert-persona real)
- [ ] Si Robert-persona tiene datos reales, crear `robert_prod_crm` aparte primero
- [ ] Bajar tráfico del bot demo durante la migración (10-15 min)
- [ ] Tests post-migración:
  - [ ] `SELECT COUNT(*) FROM leads` devuelve 19 (solo demo)
  - [ ] CRM muestra 19 en el sidebar
  - [ ] IA n8n dice 19 al preguntar cuántos hay
  - [ ] Bot sigue creando leads nuevos correctamente
