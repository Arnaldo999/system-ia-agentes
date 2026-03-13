#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/load_env.sh
# Cargador robusto de variables de entorno para scripts manuales.
#
# USO:  source scripts/load_env.sh
#       load_env_require VAR1 VAR2 ...   # falla si alguna falta
#
# Estrategia:
#   1. Si las vars ya están exportadas en el sistema → las usa tal cual.
#   2. Si existe .env en la raíz del repo → las carga desde ahí.
#   3. Si faltan vars críticas → mensaje claro + exit 1.
#
# NO usar paths hardcodeados a subdirectorios ni rutas absolutas.
# ─────────────────────────────────────────────────────────────────────────────

# Resuelve la raíz del repo desde cualquier directorio de trabajo
_repo_root() {
    git -C "${BASH_SOURCE[0]%/*}" rev-parse --show-toplevel 2>/dev/null \
        || realpath "$(dirname "${BASH_SOURCE[0]}")/.."
}

load_env() {
    local repo
    repo="$(_repo_root)"
    local env_file="$repo/.env"

    if [[ -f "$env_file" ]]; then
        echo "[load_env] Cargando variables desde $env_file"
        # Solo exporta líneas VAR=valor; ignora comentarios y líneas vacías.
        set -o allexport
        # shellcheck source=/dev/null
        source "$env_file"
        set +o allexport
    else
        echo "[load_env] No se encontró .env en $repo — usando variables del sistema."
    fi
}

# Verifica que todas las variables requeridas estén definidas y no vacías.
# Uso: load_env_require GEMINI_API_KEY AIRTABLE_TOKEN ...
load_env_require() {
    local missing=()
    for var in "$@"; do
        if [[ -z "${!var:-}" ]]; then
            missing+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo ""
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║  ERROR: Variables de entorno requeridas no definidas         ║"
        echo "╠══════════════════════════════════════════════════════════════╣"
        for v in "${missing[@]}"; do
            printf "║  ✗ %-58s ║\n" "$v"
        done
        echo "╠══════════════════════════════════════════════════════════════╣"
        echo "║  Copiá .env.example → .env y completá los valores.          ║"
        echo "║  Ver docs/testing-policy.md para instrucciones.              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo ""
        exit 1
    fi

    echo "[load_env] ✓ Variables verificadas: $*"
}
