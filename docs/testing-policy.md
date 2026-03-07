# Testing Policy — system-ia-agentes

## Principio fundamental

**Nunca hacer llamadas reales a APIs en tests de entorno.**
Los tests de entorno solo validan que las variables de configuración estén presentes y con formato correcto, sin consumir créditos ni modificar datos de producción.

---

## Estructura de tests

```
scripts/
├── load_env.sh                         # Cargador de .env para scripts bash
├── check_secrets.sh                    # Escáner de secretos pre-commit
└── manual_tests/
    ├── test_gastro_env.py              # Valida entorno del worker gastronómico
    └── test_social_env.py              # Valida entorno del worker social (Meta)
```

---

## Configuración del entorno local

### 1. Copiar y completar `.env`

```bash
cp .env.example .env
# Editar .env con los valores reales de credenciales
```

El `.env` real **nunca se commitea** (está en `.gitignore`).
El `.env.example` sí se commitea y **no contiene valores reales**.

### 2. Verificar entorno (sin credenciales reales)

Para probar que el entorno está bien configurado sin hacer llamadas a APIs:

```bash
# Worker gastronómico
python scripts/manual_tests/test_gastro_env.py

# Worker social (Meta / Instagram)
python scripts/manual_tests/test_social_env.py
```

**Salida esperada cuando el entorno está OK:**
```
══════════════════════════════════════════════════════
  Test de entorno: worker gastronomico
══════════════════════════════════════════════════════

  Variables presentes:
    ✓ GEMINI_API_KEY                    = AIzaSy...
    ✓ AIRTABLE_API_KEY                  = patXXX...
    ...

  ✅ Entorno OK — todas las variables requeridas están definidas.
     (No se hicieron llamadas reales a ninguna API)
══════════════════════════════════════════════════════
```

**Salida cuando faltan variables:**
```
  Variables FALTANTES (requeridas):
    ✗ GEMINI_API_KEY
    ✗ EVOLUTION_API_KEY

  ❌ Entorno incompleto. Copiá .env.example → .env y completá.
```

---

## Escáner de secretos

### Uso manual

```bash
# Escanear todo el repo
./scripts/check_secrets.sh

# Escanear solo archivos en staging (pre-commit)
./scripts/check_secrets.sh --staged
```

### Instalación como pre-commit hook

```bash
# Una sola vez por clon del repo
ln -sf ../../scripts/check_secrets.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

A partir de ese momento, el escáner corre automáticamente en cada `git commit --staged`.

### Si hay falsos positivos

Si el escáner detecta algo que NO es un secreto real (ej: un hash en un comentario de ejemplo):

1. Identificar el patrón que dispara la alerta
2. Agregar una excepción en la sección `EXCLUDES` de `check_secrets.sh`
3. Documentar el motivo con un comentario en el mismo archivo

**Nunca ignorar un hallazgo sin revisarlo.**

---

## Reglas para tests de integración (con APIs reales)

Si en algún momento se necesita un test que SÍ llame a una API real:

1. **Crear en una carpeta separada**: `scripts/integration_tests/`
2. **Nombrar con prefijo `integration_`**: `integration_test_airtable.py`
3. **Agregar un aviso claro** al inicio del script:
   ```python
   print("⚠️  Este script hace llamadas REALES a la API. Solo correr en entorno de prueba.")
   ```
4. **Nunca correr en CI** (el CI solo corre tests de entorno)
5. **Documentar en este archivo** qué llamadas hace y a qué entorno

---

## Checklist antes de cada deploy

- [ ] `./scripts/check_secrets.sh` → sin hallazgos
- [ ] `python scripts/manual_tests/test_gastro_env.py` → exit 0
- [ ] `python scripts/manual_tests/test_social_env.py` → exit 0
- [ ] Variables en Easypanel actualizadas si hubo rotación de tokens
- [ ] `.env.example` actualizado si se agregaron nuevas variables

---

## Variables de entorno — referencia rápida

| Variable | Worker | Descripción |
|----------|--------|-------------|
| `GEMINI_API_KEY` | gastro + social | Google Gemini API |
| `OPENAI_API_KEY` | gastro (opcional) | Whisper para audio |
| `AIRTABLE_API_KEY` | gastro | Token de Airtable |
| `AIRTABLE_TOKEN` | social | Token de Airtable |
| `AIRTABLE_BASE_ID` | gastro + social | ID de base Airtable |
| `AIRTABLE_TABLE_ID` | social | ID de tabla Airtable |
| `NUMERO_DUENO` | gastro | Teléfono del dueño |
| `EVOLUTION_API_URL` | gastro + social | URL de Evolution API |
| `EVOLUTION_INSTANCE` | gastro + social | Instancia de Evolution |
| `EVOLUTION_API_KEY` | gastro + social | Key de Evolution API |
| `META_ACCESS_TOKEN` | social | Token permanente Meta |
| `FACEBOOK_PAGE_ID` | social | ID página de Facebook |
| `IG_BUSINESS_ACCOUNT_ID` | social | ID cuenta IG Business |
| `META_WEBHOOK_VERIFY_TOKEN` | social | Token verificación webhook |
| `CLIENT_2_META_TOKEN` | social | Token Meta cliente 2 |
| `CLIENT_2_PAGE_ID` | social | Page ID cliente 2 |
| `CLIENT_2_IG_ID` | social | IG ID cliente 2 |

---

## Rotación de tokens

Si se compromete un secreto:

1. **Revocar inmediatamente** en el proveedor (Meta Business Manager, Airtable, etc.)
2. **Generar nuevo token**
3. **Actualizar en Easypanel** (Variables de entorno del servicio `agente`)
4. **No modificar** el código del worker (los tokens van en env vars, nunca hardcodeados)
5. **Verificar** con los scripts de test que el nuevo token está disponible

---

## Riesgos conocidos (pendientes de resolver)

Los siguientes hallazgos fueron detectados por `check_secrets.sh` y corresponden a valores
hardcodeados como defaults en los workers de producción. **No son secretos expuestos en git**
(los valores reales vienen de Easypanel), pero representan un riesgo si el código se corre
en un entorno sin las env vars correctamente configuradas.

| Archivo | Línea | Hallazgo | Riesgo |
|---------|-------|----------|--------|
| `workers/social/worker.py` | 1397 | `META_WEBHOOK_VERIFY_TOKEN` default `"SystemIA2026"` | Bajo — predecible si se expone el repo |
| `workers/social/worker.py` | 1398 | `AIRTABLE_BASE_ID` default `appejn9ep8JMLJmPG` | Medio — expone estructura de la base |
| `workers/social/worker.py` | 1399 | `AIRTABLE_TABLE_ID` default `tblgFvYebZcJaYM07` | Medio — expone estructura de la tabla |
| `workers/gastronomico/worker.py` | 21 | `AIRTABLE_BASE_ID` default `appdA5rJOmtVvpDrx` | Medio — expone estructura de la base |

**Acción recomendada**: Eliminar los valores default de `os.environ.get()` en los workers
y hacer que fallen con error claro si la variable no está definida. Pendiente para sprint de
hardening de producción.
