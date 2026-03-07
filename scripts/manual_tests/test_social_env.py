#!/usr/bin/env python3
"""
scripts/manual_tests/test_social_env.py
─────────────────────────────────────────
Verifica que el entorno esté correctamente configurado para el worker
de redes sociales (Meta / Instagram / Facebook) SIN hacer llamadas
reales a APIs ni consumir créditos.

Estrategia de carga (en orden de prioridad):
  1. Variables ya exportadas en el sistema (Easypanel, CI, shell)
  2. Archivo .env en la raíz del repo (desarrollo local)

Uso:
    python scripts/manual_tests/test_social_env.py

Variables requeridas:
    META_ACCESS_TOKEN
    IG_BUSINESS_ACCOUNT_ID
    FACEBOOK_PAGE_ID
    AIRTABLE_TOKEN
    AIRTABLE_BASE_ID
    AIRTABLE_TABLE_ID
    EVOLUTION_API_URL
    EVOLUTION_INSTANCE
    EVOLUTION_API_KEY
    META_WEBHOOK_VERIFY_TOKEN
    GEMINI_API_KEY

Variables opcionales (clientes adicionales):
    CLIENT_2_META_TOKEN / CLIENT_2_PAGE_ID / CLIENT_2_IG_ID
    CLIENT_3_META_TOKEN / CLIENT_3_PAGE_ID / CLIENT_3_IG_ID

Salida:
    EXIT 0 → entorno OK (todas las vars presentes y sin valores placeholder)
    EXIT 1 → una o más variables faltan o tienen valores de ejemplo sin reemplazar
"""

import os
import sys
from pathlib import Path

# Patrones que indican que la variable NO fue completada con un valor real.
PLACEHOLDER_MARKERS = [
    "REEMPLAZAR",
    "COMPLETAR",
    "YOUR_",
    "TU_",
    "TU-",
    "<",
    "TEST_VALUE",
    "PLACEHOLDER",
    "EXAMPLE",
    "CHANGE_ME",
]


def load_dotenv_safe() -> None:
    """
    Carga .env desde la raíz del repo SOLO si las vars no están ya en el sistema.
    No falla si no existe .env (puede correr en Easypanel/CI directamente).

    La raíz del repo se resuelve como dos niveles arriba de este archivo:
        scripts/manual_tests/test_social_env.py  →  parents[2] = repo root
    """
    repo_root = Path(__file__).resolve().parents[2]
    env_file = repo_root / ".env"

    if env_file.exists():
        print(f"[env] Cargando {env_file}")
        with env_file.open() as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                # Sistema tiene prioridad: no sobreescribir vars ya exportadas.
                if key not in os.environ:
                    os.environ[key] = value
    else:
        print("[env] No se encontró .env — usando variables del sistema.")


def is_placeholder(value: str) -> bool:
    """Devuelve True si el valor parece un placeholder sin reemplazar."""
    v = value.upper()
    return any(marker.upper() in v for marker in PLACEHOLDER_MARKERS)


REQUIRED_VARS = [
    # Meta / Facebook / Instagram
    "META_ACCESS_TOKEN",
    "IG_BUSINESS_ACCOUNT_ID",
    "FACEBOOK_PAGE_ID",
    # Airtable
    "AIRTABLE_TOKEN",
    "AIRTABLE_BASE_ID",
    "AIRTABLE_TABLE_ID",
    # Evolution API (WhatsApp)
    "EVOLUTION_API_URL",
    "EVOLUTION_INSTANCE",
    "EVOLUTION_API_KEY",
    # Webhook de Meta
    "META_WEBHOOK_VERIFY_TOKEN",
    # IA
    "GEMINI_API_KEY",
]

OPTIONAL_VARS = [
    "CLIENT_2_META_TOKEN",
    "CLIENT_2_PAGE_ID",
    "CLIENT_2_IG_ID",
    "CLIENT_3_META_TOKEN",
    "CLIENT_3_PAGE_ID",
    "CLIENT_3_IG_ID",
]


def check_env() -> bool:
    ok = True
    missing: list[str] = []
    placeholder: list[str] = []
    present: list[tuple[str, str]] = []

    for var in REQUIRED_VARS:
        val = os.environ.get(var, "")
        if not val:
            missing.append(var)
            ok = False
        elif is_placeholder(val):
            placeholder.append(var)
            ok = False
        else:
            # Solo primeros 6 chars para no loguear el secreto completo
            safe = val[:6] + "..." if len(val) > 6 else "****"
            present.append((var, safe))

    print()
    print("══════════════════════════════════════════════════════")
    print("  Test de entorno: worker social (Meta / IG / FB)")
    print("══════════════════════════════════════════════════════")

    if present:
        print("\n  Variables presentes:")
        for var, safe in present:
            print(f"    ✓ {var:<40} = {safe}")

    opt_present = []
    opt_missing = []
    for var in OPTIONAL_VARS:
        val = os.environ.get(var, "")
        if val and not is_placeholder(val):
            safe = val[:6] + "..."
            opt_present.append((var, safe))
        else:
            opt_missing.append(var)

    if opt_present or opt_missing:
        print("\n  Variables opcionales (clientes adicionales):")
        for var, safe in opt_present:
            print(f"    ○ {var:<40} = {safe}  (presente)")
        for var in opt_missing:
            print(f"    ○ {var:<40} = (no definida)")

    if missing:
        print("\n  Variables FALTANTES (requeridas):")
        for var in missing:
            print(f"    ✗ {var}")

    if placeholder:
        print("\n  Variables con VALOR PLACEHOLDER (completá con valor real):")
        for var in placeholder:
            print(f"    ⚠ {var}")

    if not ok:
        print()
        print("  ❌ Entorno incompleto.")
        print("     Copiá .env.example → .env, completá los valores reales.")
        print("     Ver docs/testing-policy.md para instrucciones detalladas.")
    else:
        print()
        print("  ✅ Entorno OK — todas las variables requeridas están definidas.")
        print("     (No se hicieron llamadas reales a ninguna API)")

    print("══════════════════════════════════════════════════════")
    print()
    return ok


if __name__ == "__main__":
    load_dotenv_safe()
    success = check_env()
    sys.exit(0 if success else 1)
