---
title: "Quoting de tokens en .env (regla bash source)"
tags: [env-vars, tokens, regla-irrompible, seguridad-operativa, coolify]
source_count: 1
proyectos_aplicables: [global]
---

# Quoting de tokens en `.env`

## Definición

Regla operativa irrompible: **todo token que contiene caracteres especiales de shell (`|`, `&`, `;`, `(`, `)`, `<`, `>`, `$`, espacios) DEBE estar entre comillas DOBLES en cualquier `.env` del repo**.

```bash
# ✅ CORRECTO — comillas dobles, el bash respeta el valor literal
COOLIFY_TOKEN="3|9jSOO9gENMQIafTfIMVUg8dcFvXL9UbKQGqsl64fe74c5615"

# ❌ INCORRECTO — comillas simples, algunos parsers las preservan como parte del valor
COOLIFY_TOKEN='3|9jSOO9gENMQIafTfIMVUg8dcFvXL9UbKQGqsl64fe74c5615'

# ❌ INCORRECTO — sin comillas, bash source rompe en el `|` (lo lee como pipe)
COOLIFY_TOKEN=3|9jSOO9gENMQIafTfIMVUg8dcFvXL9UbKQGqsl64fe74c5615
```

## Por qué importa

`bash source .env` ejecuta cada línea como código bash. Cuando una variable contiene `|`, bash lo interpreta como pipe shell entre comandos. El resultado:

```
.env: línea 29: 9jSOO9gENMQIafTfIMVUg8dcFvXL9UbKQGqsl64fe74c5615: orden no encontrada
```

La variable **NO se carga**. Cualquier script que después haga `os.environ["COOLIFY_TOKEN"]` recibe `KeyError` o un valor truncado. La API responde 401. El operador asume "token vencido" y pide uno nuevo. Loop infinito.

## Caso real que originó la regla (2026-04-22)

[[arnaldo-ayala|Arnaldo]] mostró captura de [[coolify-arnaldo|Coolify]] con **4 tokens emitidos** (`worker-arnaldo`, dos `agentes`, `flujos agenticos`). Cada subagente Claude Code que necesitaba operar la API Coolify pidió un token nuevo en lugar de leer el ya guardado en `.env`. Causa raíz:

1. **Quoting**: el token tenía comillas SIMPLES.
2. **Lookup incompleto**: los subagentes buscaban en `.env` del backend monorepo, donde no estaba — solo en `.env` raíz del Mission Control.
3. **Síntoma engaña**: 401 → "token inválido" → "necesito uno nuevo" → 4 tokens emitidos en lugar de 1.

Tiempo perdido en 4 sesiones distintas hasta que se identificó el patrón.

## Procedimiento operativo obligatorio

**Antes de pedirle al usuario un token, ejecutar EN ESTE ORDEN**:

### 1. Buscar en ambos `.env`

```bash
grep -E "^COOLIFY_TOKEN=" \
  "$REPO/.env" \
  "$REPO/01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/.env" \
  2>/dev/null
```

### 2. Validar que funciona

```bash
cd "$REPO"
set -a && source .env && set +a
echo "${COOLIFY_TOKEN:0:5}"   # debe ser: 3|9jS (no '3|9j ni vacío)
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $COOLIFY_TOKEN" \
  "$COOLIFY_URL/api/v1/applications"
# Esperado: HTTP 200
```

### 3. Si `source .env` falla con "orden no encontrada"

Es un value con caracteres shell sin comillas dobles. Buscarlo y arreglarlo:

```bash
# Localizar la línea problemática
grep -n "|" .env | grep -v "^#"
# Editar y poner comillas dobles
```

### 4. Solo si TODO falla, pedirle al usuario un token nuevo

Y antes de hacerlo, **revocar tokens viejos** desde el panel Coolify para no acumular basura.

## Tokens conocidos en el ecosistema

| Token | Caracteres especiales | Quoting requerido |
|-------|----------------------|-------------------|
| `COOLIFY_TOKEN` (Arnaldo Hostinger) | `|` (formato Sanctum) | ✅ comillas dobles |
| `COOLIFY_ROBERT_TOKEN` (Robert Hetzner) | `|` (formato Sanctum) | ✅ comillas dobles |
| `TELEGRAM_BOT_TOKEN` | `:` (formato Telegram) | ⚠️ funciona sin comillas pero recomendado |
| `OPENAI_API_KEY` / `LOVBOT_OPENAI_API_KEY` | `-` `_` (sk-proj-...) | sin comillas OK |
| `AIRTABLE_TOKEN` / `AIRTABLE_TOKEN_MAICOL` | `.` `_` | sin comillas OK |

## Reglas adicionales

- **Múltiples ubicaciones del mismo token**: si `COOLIFY_TOKEN` se usa en backend monorepo, debe existir TANTO en `.env` raíz como en `.env` backend (o el backend `.env` debe importar el raíz). NO asumir que un solo `.env` lo cubre todo.
- **`python-dotenv` es más tolerante que `bash source`**: si tu script usa `from dotenv import load_dotenv` puede leer comillas simples sin romperse, pero si después algún hook/script wrapper hace `source .env`, vuelve a fallar. Siempre comillas dobles.
- **NUNCA exponer un token en logs, commits, o mensajes** — usar `${TOKEN:0:8}...${TOKEN: -4}` para mostrar parcialmente.

## Memoria persistente relacionada

`feedback_REGLA_env_quoting_y_lookup.md` (Silo 1 auto-memory) duplica esta regla en formato corto para que esté siempre cargada en contexto.

## Fuentes que lo mencionan

- [[wiki/fuentes/sesion-2026-04-22]] — sesión donde se identificó el patrón
