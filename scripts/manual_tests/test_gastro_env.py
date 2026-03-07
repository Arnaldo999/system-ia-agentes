#!/usr/bin/env python3
"""
scripts/manual_tests/test_gastro_env.py
─────────────────────────────────────────
Verifica que el entorno esté correctamente configurado para el worker
gastronomico SIN hacer llamadas reales a APIs ni consumir créditos.

Uso:
    python scripts/manual_tests/test_gastro_env.py

Requiere (en .env o exportadas en el sistema):
    GEMINI_API_KEY
    AIRTABLE_API_KEY
    AIRTABLE_BASE_ID
    NUMERO_DUENO
    EVOLUTION_API_URL
    EVOLUTION_INSTANCE
    EVOLUTION_API_KEY

Salida:
    EXIT 0 → entorno OK
    EXIT 1 → una o más variables faltan o están vacías
"""

import os
import sys
from pathlib import Path


def load_dotenv_safe() -> None:
    """
    Carga .env desde la raíz del repo SOLO si las vars no están ya en el sistema.
    No falla si no existe .env (puede correr en Easypanel/CI directamente).
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
                # Solo setear si NO está ya en el entorno (sistema tiene prioridad)
                if key not in os.environ:
                    os.environ[key] = value
    else:
        print("[env] No se encontró .env — usando variables del sistema.")


REQUIRED_VARS = [
    "GEMINI_API_KEY",
    "AIRTABLE_API_KEY",
    "AIRTABLE_BASE_ID",
    "NUMERO_DUENO",
    "EVOLUTION_API_URL",
    "EVOLUTION_INSTANCE",
    "EVOLUTION_API_KEY",
]

OPTIONAL_VARS = [
    "OPENAI_API_KEY",       # solo para transcripción de audio (Whisper)
]


def check_env() -> bool:
    ok = True
    missing = []
    present = []

    for var in REQUIRED_VARS:
        val = os.environ.get(var, "")
        if not val:
            missing.append(var)
            ok = False
        else:
            # Mostrar solo primeros 6 chars para no loguear el secreto completo
            safe = val[:6] + "..." if len(val) > 6 else "****"
            present.append((var, safe))

    print()
    print("══════════════════════════════════════════════════════")
    print("  Test de entorno: worker gastronomico")
    print("══════════════════════════════════════════════════════")

    if present:
        print("\n  Variables presentes:")
        for var, safe in present:
            print(f"    ✓ {var:<35} = {safe}")

    for var in OPTIONAL_VARS:
        val = os.environ.get(var, "")
        if val:
            safe = val[:6] + "..."
            print(f"    ○ {var:<35} = {safe}  (opcional, presente)")
        else:
            print(f"    ○ {var:<35} = (no definida, opcional)")

    if missing:
        print("\n  Variables FALTANTES (requeridas):")
        for var in missing:
            print(f"    ✗ {var}")
        print()
        print("  ❌ Entorno incompleto. Copiá .env.example → .env y completá.")
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
