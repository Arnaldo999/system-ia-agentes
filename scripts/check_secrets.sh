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
# Nota: se usan como substrings en paths, no como regex. Deben ser suficientemente
# específicos para no excluir rutas legítimas (ej: "env" no se usa, sí "/env/").
EXCLUDES=(
    "/.git/"
    "/.venv/"
    "/venv/"
    "/env/"
    "/node_modules/"
    "/__pycache__/"
    ".env.example"
    "scripts/check_secrets.sh"   # se autoexcluye
    "docs/testing-policy.md"     # documenta patrones intencionalmente
)

# ── Patrones de secretos a detectar ──────────────────────────────────────────
# Formato: "NOMBRE_PATRON|REGEX_PERL"
#
# Principios de diseño:
#   - Preferir patrones con comillas para reducir falsos positivos
#   - No usar rangos demasiado amplios (ej: [a-f0-9]{32} matchea cualquier hash)
#   - Documentar falsos positivos conocidos con comentario
PATTERNS=(
    # ── Tokens largos genéricos ───────────────────────────────────────────────
    # Requiere comillas para evitar FP en paths, hashes, hexpairs de código.
    # No incluye '/' en charset (paths de sistema) ni '[a-f0-9]' puro (hashes SHA).
    "TOKEN_GENERICO_LARGO|['\"][A-Za-z0-9+]{40,}[=]{0,2}['\"]"

    # ── Bearer tokens en headers HTTP ────────────────────────────────────────
    "BEARER_TOKEN|Bearer\s+[A-Za-z0-9\-_.~+/]{20,}"

    # ── API keys con prefijos de proveedores conocidos ────────────────────────
    "OPENAI_KEY|sk-[A-Za-z0-9]{20,}"
    "OPENAI_KEY_V2|sk-proj-[A-Za-z0-9\-]{20,}"
    "ANTHROPIC_KEY|sk-ant-[A-Za-z0-9\-]{20,}"

    # Airtable personal access token (formato: pat + 14 chars + . + 60+ chars)
    "AIRTABLE_TOKEN|pat[A-Za-z0-9]{14,}\.[A-Za-z0-9]{60,}"

    "GEMINI_KEY|AIza[A-Za-z0-9\-_]{35}"
    "STRIPE_KEY|sk_(live|test)_[A-Za-z0-9]{24,}"

    # Twilio: SID empieza con AC + 32 hex. Token separado (34 chars alfanum, NO puro hex)
    # Se excluye el token genérico de Twilio ([a-f0-9]{32}) por excesivos FP con hashes.
    "TWILIO_SID|AC[a-f0-9]{32}"

    "GITHUB_TOKEN|gh[pousr]_[A-Za-z0-9]{36,}"
    "CLOUDINARY_KEY|[0-9]{15,}:[A-Za-z0-9_\-]{27,}"

    # Meta / Facebook: tokens EAA (Graph API) y tokens largos genéricos (System User)
    "META_ACCESS_TOKEN|EAA[A-Za-z0-9]{50,}"
    # META_TOKEN_GENERICO: requiere comillas y mínimo 80 chars para evitar FP en UUIDs/hashes
    "META_TOKEN_GENERICO|['\"][A-Za-z0-9_\-]{80,}['\"]"

    # ── WhatsApp / Evolution API ──────────────────────────────────────────────
    # Evolution API key: string alfanumérico largo en header o asignación
    "EVOLUTION_KEY|(evolution.{0,20}key|apikey|api_key)\s*[=:]\s*['\"][A-Za-z0-9\-_]{16,}['\"]"

    # ── Assignments genéricos de credenciales ─────────────────────────────────
    # Captura: password = "valor", secret = "valor", api_key = "valor", etc.
    # Case-insensitive vía (?i).
    "PASSWORD_ASSIGN|(?i)(password|passwd|secret|api_key|apikey|access_token|auth_token)\s*=\s*['\"][^'\"]{8,}['\"]"

    # ── URLs con credenciales embebidas ──────────────────────────────────────
    "URL_CON_CRED|https?://[^:\s]+:[^@\s]{6,}@"

    # ── Teléfonos argentinos hardcodeados ────────────────────────────────────
    # Formato 549 + 10 dígitos, en string con comillas.
    # Excluye placeholders terminados en 4+ ceros (ej: +5491100000000).
    "TELEFONO_ARG|['\"]549[0-9]{6}[1-9][0-9]{3}['\"]"
    "TELEFONO_ARG_INTL|['\"\+]54\s?9\s?[0-9]{4}\s?[0-9]{2}\-?[1-9][0-9]{3}['\"]"

    # ── IDs/tokens hardcodeados como defaults en os.environ.get() ────────────
    # Estos representan riesgo de exposición de estructura aunque no sean tokens de acceso.
    "AIRTABLE_BASE_DEFAULT|os\.environ\.get\(['\"]AIRTABLE_BASE_ID['\"],\s*['\"]app[A-Za-z0-9]{14,}['\"]"
    "AIRTABLE_TABLE_DEFAULT|os\.environ\.get\(['\"]AIRTABLE_TABLE_ID['\"],\s*['\"]tbl[A-Za-z0-9]{14,}['\"]"
    "WEBHOOK_TOKEN_DEFAULT|os\.environ\.get\(['\"]META_WEBHOOK_VERIFY_TOKEN['\"],\s*['\"][^'\"]{4,}['\"]"
    # Cualquier os.environ.get con default no-vacío para vars de credenciales
    "CRED_VAR_DEFAULT|os\.environ\.get\(['\"](?:TOKEN|KEY|SECRET|PASSWORD|API)[A-Z_]*['\"],\s*['\"][^'\"]{6,}['\"]"
)

# ── Función de escaneo ────────────────────────────────────────────────────────
FINDINGS=0

scan_file() {
    local file="$1"
    # Saltar binarios
    if ! file "$file" | grep -qE "text|script|empty"; then
        return
    fi

    local file_findings=0
    local file_header_printed=false

    for pattern_entry in "${PATTERNS[@]}"; do
        local name="${pattern_entry%%|*}"
        local regex="${pattern_entry##*|}"

        local matches
        if matches=$(grep -nP "$regex" "$file" 2>/dev/null); then
            if [[ "$file_header_printed" == false ]]; then
                echo ""
                echo "⚠️  $file"
                file_header_printed=true
            fi
            echo "   [$name]"
            while IFS= read -r match; do
                # Truncar a 120 chars para no loguear el secreto completo
                echo "   └─ ${match:0:120}"
            done <<< "$matches"
            file_findings=$((file_findings + 1))
        fi
    done

    FINDINGS=$((FINDINGS + file_findings))
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
    # Extensiones relevantes — repo completo excluyendo dirs de dependencias/build
    while IFS= read -r f; do
        skip=false
        for ex in "${EXCLUDES[@]}"; do
            if [[ "$f" == *"$ex"* ]]; then
                skip=true
                break
            fi
        done
        [[ "$skip" == false ]] && FILES_TO_SCAN+=("$f")
    done < <(find "$REPO_ROOT" -type f \( \
        -name "*.py"   -o -name "*.sh"  -o -name "*.env" \
        -o -name ".env" \
        -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" \
        -o -name "*.toml" -o -name "*.ini" -o -name "*.cfg" \
        -o -name "*.md"  -o -name "Dockerfile" -o -name "*.txt" \
    \) 2>/dev/null \
      | grep -v "/\.git/\|/venv/\|/\.venv/\|/node_modules/\|/__pycache__/\|/env/")
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
    echo "  2. Si es un falso positivo → agregá el patrón a EXCLUDES o documentalo."
    echo "  3. Si es real → rotá el secreto en Easypanel ANTES de continuar."
    echo "  4. Nunca commitees secretos reales. Ver: docs/testing-policy.md"
    echo "═══════════════════════════════════════════════════════════════"
    exit 1
fi
