# Testing Policy — system-ia-agentes

## Principio fundamental

**Nunca hacer llamadas reales a APIs en tests de entorno.**

Los scripts en `scripts/manual_tests/` solo validan que las variables estén presentes,
no sean placeholders y tengan formato mínimamente plausible. No consumen créditos
ni modifican datos de producción.

---

## Orden obligatorio de ejecución (pre-deploy)

```
1. ./scripts/check_secrets.sh              # scanner anti-secretos (todo el repo)
2. python scripts/manual_tests/test_gastro_env.py
3. python scripts/manual_tests/test_social_env.py
```

Los tres deben devolver **exit 0** antes de hacer push o deploy.

---

## Scripts manuales — Variables requeridas

### `test_gastro_env.py` — Worker gastronómico

| Variable | Descripción | Obligatoria |
|----------|-------------|:-----------:|
| `GEMINI_API_KEY` | Google Gemini (modelo de conversación) | ✅ |
| `AIRTABLE_API_KEY` | Personal Access Token de Airtable | ✅ |
| `AIRTABLE_BASE_ID` | ID de la base Airtable del restaurante | ✅ |
| `NUMERO_DUENO` | Teléfono del dueño (formato 549...) | ✅ |
| `EVOLUTION_API_URL` | URL base de Evolution API | ✅ |
| `EVOLUTION_INSTANCE` | Nombre de la instancia de Evolution | ✅ |
| `EVOLUTION_API_KEY` | API Key de Evolution API | ✅ |
| `OPENAI_API_KEY` | Whisper para transcripción de audio | ○ opcional |

### `test_social_env.py` — Worker social (Meta / Instagram)

| Variable | Descripción | Obligatoria |
|----------|-------------|:-----------:|
| `META_ACCESS_TOKEN` | System User token permanente (Meta) | ✅ |
| `IG_BUSINESS_ACCOUNT_ID` | ID cuenta Instagram Business | ✅ |
| `FACEBOOK_PAGE_ID` | ID página de Facebook | ✅ |
| `AIRTABLE_TOKEN` | Personal Access Token de Airtable | ✅ |
| `AIRTABLE_BASE_ID` | ID de la base Airtable | ✅ |
| `AIRTABLE_TABLE_ID` | ID de la tabla de comentarios | ✅ |
| `EVOLUTION_API_URL` | URL base de Evolution API | ✅ |
| `EVOLUTION_INSTANCE` | Nombre de la instancia de Evolution | ✅ |
| `EVOLUTION_API_KEY` | API Key de Evolution API | ✅ |
| `META_WEBHOOK_VERIFY_TOKEN` | Token de verificación webhook Meta | ✅ |
| `GEMINI_API_KEY` | Google Gemini (modelo de respuesta) | ✅ |
| `CLIENT_2_META_TOKEN` + `_PAGE_ID` + `_IG_ID` | Cliente 2 | ○ opcional |
| `CLIENT_3_META_TOKEN` + `_PAGE_ID` + `_IG_ID` | Cliente 3 | ○ opcional |

---

## Política fail-fast

Los scripts de entorno implementan las siguientes reglas:

1. **Prioridad del sistema**: si la variable ya está exportada en el entorno del sistema
   (Easypanel, CI, shell), se usa ese valor. El `.env` del disco NO sobreescribe vars del sistema.

2. **Detección de placeholders**: si una variable está definida pero contiene strings como
   `REEMPLAZAR`, `COMPLETAR`, `YOUR_`, `TU_`, `<`, `EXAMPLE`, `CHANGE_ME`, se trata igual
   que una variable ausente y se reporta como `⚠ variable con valor placeholder`.

3. **Exit code determinístico**:
   - `0` → todas las vars presentes, sin placeholders
   - `1` → falta al menos una variable o alguna tiene valor placeholder

4. **Ninguna variable crítica tiene default silencioso** en estos scripts. Si falta, el
   proceso termina inmediatamente con mensaje claro — no continúa con valores inventados.

---

## Configuración del entorno local

```bash
# 1. Copiar la plantilla
cp .env.example .env

# 2. Completar con valores reales (editar .env)
# ⚠️ Reemplazar TODOS los "COMPLETAR" con valores reales

# 3. Verificar
python scripts/manual_tests/test_gastro_env.py
python scripts/manual_tests/test_social_env.py
```

### Salida esperada cuando el entorno está bien configurado

```
[env] Cargando /ruta/al/repo/.env

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

### Salida con variables faltantes

```
  Variables FALTANTES (requeridas):
    ✗ GEMINI_API_KEY
    ✗ EVOLUTION_API_KEY

  ❌ Entorno incompleto.
     Copiá .env.example → .env, completá los valores reales.
```

### Salida con placeholders sin reemplazar

```
  Variables con VALOR PLACEHOLDER (completá con valor real):
    ⚠ AIRTABLE_API_KEY

  ❌ Entorno incompleto.
```

---

## Scanner anti-secretos (`check_secrets.sh`)

### Uso

```bash
# Escanear todo el repo (usar antes de hacer push)
./scripts/check_secrets.sh

# Escanear solo archivos en staging (modo pre-commit, más rápido)
./scripts/check_secrets.sh --staged
```

### Pre-commit hook

El hook está instalado en `.git/hooks/pre-commit` y corre `--staged` automáticamente
en cada `git commit`. Si hay hallazgos, el commit es bloqueado.

Para reinstalar el hook (después de re-clonar el repo):

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/usr/bin/env bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
exec "$REPO_ROOT/scripts/check_secrets.sh" --staged
EOF
chmod +x .git/hooks/pre-commit
```

### Patrones detectados

| Patrón | Ejemplos detectados |
|--------|---------------------|
| `TOKEN_GENERICO_LARGO` | Strings de 40+ chars alfanuméricos entre comillas |
| `BEARER_TOKEN` | `Bearer <token>` en código o configs |
| `OPENAI_KEY` | `sk-...` y `sk-proj-...` |
| `ANTHROPIC_KEY` | `sk-ant-...` |
| `AIRTABLE_TOKEN` | `pat<14chars>.<60+chars>` |
| `GEMINI_KEY` | `AIza...` (35 chars) |
| `STRIPE_KEY` | `sk_live_...` / `sk_test_...` |
| `TWILIO_SID` | `AC` + 32 hex chars |
| `GITHUB_TOKEN` | `gh[pousr]_...` |
| `META_ACCESS_TOKEN` | `EAA...` (50+ chars) |
| `META_TOKEN_GENERICO` | Strings 80+ chars alfanuméricos entre comillas |
| `EVOLUTION_KEY` | API key en asignación de Evolution |
| `PASSWORD_ASSIGN` | `password=`, `secret=`, `api_key=`, etc. |
| `URL_CON_CRED` | `https://user:pass@host` |
| `TELEFONO_ARG` | Número argentino `549...` en string |
| `AIRTABLE_BASE_DEFAULT` | `os.environ.get("AIRTABLE_BASE_ID", "app...")` |
| `CRED_VAR_DEFAULT` | Cualquier var de credencial con default hardcodeado |

### Si hay falsos positivos

1. Identificar el patrón que disparó la alerta.
2. Agregar una excepción en el array `EXCLUDES` de `check_secrets.sh` (path o string).
3. Documentar el motivo con un comentario en el archivo.

**Nunca ignorar un hallazgo sin revisarlo.**

---

## Checklist pre-deploy

- [ ] `./scripts/check_secrets.sh` → exit 0, sin hallazgos
- [ ] `python scripts/manual_tests/test_gastro_env.py` → exit 0
- [ ] `python scripts/manual_tests/test_social_env.py` → exit 0
- [ ] Variables en Easypanel actualizadas si hubo rotación de tokens
- [ ] `.env.example` actualizado si se agregaron nuevas variables requeridas

---

## Rotación de tokens

Si se compromete un secreto:

1. **Revocar inmediatamente** en el proveedor (Meta Business Manager, Airtable, etc.)
2. **Generar nuevo token**
3. **Actualizar en Easypanel** (Variables de entorno del servicio `agente`)
4. **No modificar** el código del worker — los tokens van en env vars, nunca hardcodeados
5. **Verificar** con los scripts de test que el nuevo token está cargado: `test_*.py`

---

## Riesgos conocidos (pendientes de resolver)

Los siguientes hallazgos son detectados por `check_secrets.sh` al escanear el repo completo.
Corresponden a valores hardcodeados como defaults en workers de producción. **No son secretos
expuestos en git** (los valores reales vienen de Easypanel), pero si el código corre sin las
env vars, usaría estos IDs como fallback.

| Archivo | Línea | Hallazgo | Riesgo |
|---------|-------|----------|--------|
| `workers/social/worker.py` | 1397 | `META_WEBHOOK_VERIFY_TOKEN` default `"SystemIA2026"` | Bajo — predecible |
| `workers/social/worker.py` | 1398 | `AIRTABLE_BASE_ID` default `appejn9ep8JMLJmPG` | Medio — expone estructura |
| `workers/social/worker.py` | 1399 | `AIRTABLE_TABLE_ID` default `tblgFvYebZcJaYM07` | Medio — expone estructura |
| `workers/gastronomico/worker.py` | 21 | `AIRTABLE_BASE_ID` default `appdA5rJOmtVvpDrx` | Medio — expone estructura |

**Acción recomendada**: Reemplazar `os.environ.get("VAR", "valor")` por una función que
falle con error claro si la variable no está definida. Pendiente para sprint de hardening
de producción (no incluido en el alcance actual para no romper workers en producción).
