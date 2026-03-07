#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/check_secrets.sh
# Scanner de secretos para el repo system-ia-agentes.
# Ejecutar ANTES de cada commit o integrado como pre-commit hook.
#
# Uso:
#   ./scripts/check_secrets.sh           # escanea todo el repo
#   ./scripts/check_secrets.sh --staged  # solo archivos en staging area (git add)
#
# Retorna:
#   0  → sin hallazgos
#   1  → se encontraron posibles secretos (bloquea el commit)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || realpath "$(dirname "$0")/..")"
STAGED_ONLY=false

if [[ "${1:-}" == "--staged" ]]; then
    STAGED_ONLY=true
fi

# ── Directorios y archivos a excluir ─────────────────────────────────────────
EXCLUDES=(
    ".git"
    ".venv"
    "venv"
    "env"
    "node_modules"
    "__pycache__"
    "*.pyc"
    ".env.example"          # el ejemplo no tiene secretos reales
    "scripts/check_secrets.sh"  # excluimos este mismo archivo
)

# Construir args --exclude-dir para grep
GREP_EXCLUDES=()
for ex in "${EXCLUDES[@]}"; do
    GREP_EXCLUDES+=("--exclude-dir=$ex" "--exclude=$ex")
done

# ── Patrones de secretos a detectar ──────────────────────────────────────────
# Formato: "NOMBRE_PATRON|REGEX"
PATTERNS=(
    # Tokens genéricos largos (Base64/hex > 40 chars).
    # Excluye '/' del charset para no disparar en paths de sistema (fuentes, libs).
    "TOKEN_GENERICO_LARGO|['\"]?[A-Za-z0-9+]{40,}[=]{0,2}['\"]?"

    # Bearer tokens en código o configs
    "BEARER_TOKEN|Bearer\s+[A-Za-z0-9\-_.~+/]{20,}"

    # API keys con prefijos conocidos de proveedores
    "OPENAI_KEY|sk-[A-Za-z0-9]{20,}"
    "ANTHROPIC_KEY|sk-ant-[A-Za-z0-9\-]{20,}"
    "AIRTABLE_TOKEN|pat[A-Za-z0-9]{14,}\.[A-Za-z0-9]{60,}"
    "GEMINI_KEY|AIza[A-Za-z0-9\-_]{35}"
    "STRIPE_KEY|sk_(live|test)_[A-Za-z0-9]{24,}"
    "TWILIO_SID|AC[a-f0-9]{32}"
    "TWILIO_TOKEN|[a-f0-9]{32}"
    "GITHUB_TOKEN|gh[pousr]_[A-Za-z0-9]{36,}"
    "CLOUDINARY_KEY|[0-9]{15,}:[A-Za-z0-9_\-]{27,}"

    # Meta / Facebook tokens
    "META_ACCESS_TOKEN|EAA[A-Za-z0-9]{50,}"
    "META_TOKEN_GENERICO|['\"]?[A-Za-z0-9_\-]{100,}['\"]?"

    # Teléfonos argentinos hardcodeados en código.
    # Falso positivo conocido: "+5491100000000" en bloques TEST_DEBUG → ignorar.
    # Solo se detectan números que NO terminen en 4+ ceros consecutivos (evita placeholders).
    "TELEFONO_REAL|['\"]549[0-9]{6}[1-9][0-9]{3}['\"]"
    "TELEFONO_REAL_2|['\"\+]54\s?9\s?[0-9]{4}\s?[0-9]{2}\-?[1-9][0-9]{3}['\"]"

    # URLs con credenciales embebidas
    "URL_CON_CRED|https?://[^:]+:[^@]{6,}@"

    # Secrets / passwords en assignments
    "PASSWORD_ASSIGN|(password|passwd|secret|api_key|apikey|access_token)\s*=\s*['\"][^'\"]{8,}['\"]"

    # IDs de Airtable hardcodeados como default (riesgo de exposición de estructura)
    "AIRTABLE_BASE_HARDCODE|os\.environ\.get\(['\"]AIRTABLE_BASE_ID['\"],\s*['\"]app[A-Za-z0-9]{14,}['\"]"
    "AIRTABLE_TABLE_HARDCODE|os\.environ\.get\(['\"]AIRTABLE_TABLE_ID['\"],\s*['\"]tbl[A-Za-z0-9]{14,}['\"]"
    "WEBHOOK_TOKEN_HARDCODE|os\.environ\.get\(['\"]META_WEBHOOK_VERIFY_TOKEN['\"],\s*['\"][^'\"]{4,}['\"]"
)

# ── Función de escaneo ────────────────────────────────────────────────────────
FINDINGS=0
TOTAL_CHECKS=0

scan_file() {
    local file="$1"
    # Saltar binarios
    if ! file "$file" | grep -qE "text|script|empty"; then
        return
    fi

    for pattern_entry in "${PATTERNS[@]}"; do
        local name="${pattern_entry%%|*}"
        local regex="${pattern_entry##*|}"
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        local matches
        if matches=$(grep -nP "$regex" "$file" 2>/dev/null); then
            echo ""
            echo "⚠️  [$name] en $file:"
            while IFS= read -r match; do
                # Truncar líneas muy largas para no exponer el secreto completo en logs
                local truncated="${match:0:120}"
                echo "   └─ $truncated"
            done <<< "$matches"
            FINDINGS=$((FINDINGS + 1))
        fi
    done
}

# ── Selección de archivos a escanear ─────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════════"
echo "  🔍 check_secrets.sh — System IA Agentes"
echo "  Modo: $([ "$STAGED_ONLY" = true ] && echo 'solo staged' || echo 'repo completo')"
echo "═══════════════════════════════════════════════════════════════"

declare -a FILES_TO_SCAN

if [[ "$STAGED_ONLY" == true ]]; then
    while IFS= read -r f; do
        [[ -f "$REPO_ROOT/$f" ]] && FILES_TO_SCAN+=("$REPO_ROOT/$f")
    done < <(git diff --cached --name-only --diff-filter=ACM)
else
    # Extensiones relevantes
    while IFS= read -r f; do
        # Excluir paths de la lista
        skip=false
        for ex in "${EXCLUDES[@]}"; do
            if [[ "$f" == *"$ex"* ]]; then
                skip=true
                break
            fi
        done
        [[ "$skip" == false ]] && FILES_TO_SCAN+=("$f")
    done < <(find "$REPO_ROOT" -type f \( \
        -name "*.py" -o -name "*.sh" -o -name "*.env" \
        -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" \
        -o -name "*.toml" -o -name "*.ini" -o -name "*.cfg" \
        -o -name "*.md" -o -name "Dockerfile" -o -name "*.txt" \
    \) 2>/dev/null | grep -v "\.git/\|venv/\|\.venv/\|node_modules/\|__pycache__/")
fi

echo "  Archivos a escanear: ${#FILES_TO_SCAN[@]}"
echo ""

for f in "${FILES_TO_SCAN[@]}"; do
    scan_file "$f"
done

# ── Resultado final ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
if [[ $FINDINGS -eq 0 ]]; then
    echo "  ✅ Sin hallazgos — ${#FILES_TO_SCAN[@]} archivos escaneados"
    echo "═══════════════════════════════════════════════════════════════"
    exit 0
else
    echo "  ❌ $FINDINGS hallazgo(s) en ${#FILES_TO_SCAN[@]} archivos"
    echo ""
    echo "  ACCIÓN REQUERIDA:"
    echo "  1. Revisá cada hallazgo arriba."
    echo "  2. Si es un falso positivo, agregá el patrón a EXCLUDES."
    echo "  3. Si es real, rotá el secreto en Easypanel ANTES de continuar."
    echo "  4. Nunca commitees secretos reales — ver docs/testing-policy.md"
    echo "═══════════════════════════════════════════════════════════════"
    exit 1
fi
