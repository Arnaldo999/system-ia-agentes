"""
Onboarding de cliente System IA (Mica)
=======================================
Toma el YAML generado por el brief form y provisiona el cliente:

1. Valida campos requeridos
2. Verifica/crea instancia Evolution API
3. Genera env vars para el worker Mica
4. Crea carpeta del cliente en 02_SYSTEM_IA_MICAELA/clientes/{slug}/
5. Imprime checklist de pasos manuales restantes (Easypanel, Airtable)

Uso:
    python onboard_mica_cliente.py brief.yaml
    python onboard_mica_cliente.py brief.yaml --dry-run

Variables de entorno requeridas:
    EVOLUTION_API_URL    → URL base de Evolution API (ej: https://evo.arnaldoayalaestratega.cloud)
    EVOLUTION_API_KEY    → API key de Evolution API
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    print("[ERROR] Instalá PyYAML: pip install pyyaml")
    sys.exit(1)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
REPO_ROOT = Path(__file__).resolve().parents[2]
MICA_CLIENTES_DIR = REPO_ROOT / "01_PROYECTOS" / "02_SYSTEM_IA_MICAELA" / "clientes"

CAMPOS_REQUERIDOS = ["slug", "nombre_empresa", "ciudad", "asesor"]

# ── helpers ───────────────────────────────────────────────────────────────────


def _cargar_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _validar(brief: dict) -> list[str]:
    errores = []
    for campo in CAMPOS_REQUERIDOS:
        if not brief.get(campo):
            errores.append(f"Campo requerido faltante: '{campo}'")
    if "asesor" in brief:
        asesor = brief["asesor"]
        if not asesor.get("nombre"):
            errores.append("Campo requerido faltante: 'asesor.nombre'")
        if not asesor.get("telefono"):
            errores.append("Campo requerido faltante: 'asesor.telefono'")
    slug = brief.get("slug", "")
    if slug and not all(c.isalnum() or c == "-" for c in slug):
        errores.append(f"Slug inválido: '{slug}' (solo letras, números y guiones)")
    return errores


def _check_evolution_instance(instance_name: str) -> dict:
    """
    Consulta estado de instancia Evolution API.
    Retorna dict con ok, estado, existe.
    """
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        return {"ok": None, "detalle": "EVOLUTION_API_URL/EVOLUTION_API_KEY no configuradas — skip"}

    url = f"{EVOLUTION_API_URL}/instance/connectionState/{instance_name}"
    try:
        r = requests.get(url, headers={"apikey": EVOLUTION_API_KEY}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            state = data.get("instance", {}).get("state", "unknown")
            return {"ok": state == "open", "existe": True, "estado": state,
                    "detalle": f"Instancia '{instance_name}' existe — estado: {state}"}
        if r.status_code == 404:
            return {"ok": False, "existe": False, "estado": "no_existe",
                    "detalle": f"Instancia '{instance_name}' NO existe en Evolution API"}
        return {"ok": False, "existe": None, "estado": "error",
                "detalle": f"Evolution API HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "existe": None, "estado": "timeout",
                "detalle": f"Evolution API no responde: {e}"}


def _generar_env_vars(brief: dict) -> dict:
    """
    Genera el set de env vars para Coolify/Easypanel del worker Mica.
    Prefijo: MICA_{SLUG_UPPER}_*
    """
    slug = brief["slug"]
    prefix = f"MICA_{slug.upper().replace('-', '_')}"
    asesor = brief.get("asesor", {})
    integraciones = brief.get("integraciones", {})
    agenda = brief.get("agenda", {})
    comunicacion = brief.get("comunicacion", {})

    env = {
        f"{prefix}_NOMBRE":              brief.get("nombre_empresa", ""),
        f"{prefix}_CIUDAD":              brief.get("ciudad", ""),
        f"{prefix}_ASESOR":              asesor.get("nombre", ""),
        f"{prefix}_ASESOR_TELEFONO":     str(asesor.get("telefono", "")),
        f"{prefix}_ASESOR_EMAIL":        asesor.get("email", ""),
        f"{prefix}_VERTICAL":            brief.get("vertical", "inmobiliaria"),
        f"{prefix}_TONO":                comunicacion.get("tono", "calido_rioplatense"),
        f"{prefix}_EMOJIS":              comunicacion.get("emojis", "moderados"),
        f"{prefix}_IDIOMA":              comunicacion.get("idioma", "es"),
        f"{prefix}_EVOLUTION_INSTANCE":  integraciones.get("evolution_instance", slug),
        f"{prefix}_CAL_ACTIVO":          str(agenda.get("cal_com_activo", False)).lower(),
        f"{prefix}_CAL_USERNAME":        agenda.get("cal_com_username", ""),
        f"{prefix}_CAL_EVENT_SLUG":      agenda.get("cal_com_event_slug", ""),
        f"{prefix}_TELEGRAM_CHAT_ID":    str(integraciones.get("telegram_chat_id", "")),
    }
    # Eliminar vacíos opcionales
    return {k: v for k, v in env.items() if v and v not in ("False", "false", '""')}


def _guardar_brief(brief: dict, slug: str) -> Path:
    """Guarda el brief en la carpeta del cliente."""
    carpeta = MICA_CLIENTES_DIR / slug
    carpeta.mkdir(parents=True, exist_ok=True)
    dest = carpeta / "brief.yaml"
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump(brief, f, allow_unicode=True, sort_keys=False)
    return dest


def _imprimir_env_vars(env_vars: dict):
    print("\n" + "="*60)
    print("  ENV VARS para Easypanel / Coolify")
    print("="*60)
    for k, v in sorted(env_vars.items()):
        print(f"  {k}={v}")
    print("="*60)


def _imprimir_checklist(brief: dict, env_vars: dict, instance_check: dict):
    slug = brief["slug"]
    nombre = brief.get("nombre_empresa", slug)
    instance_name = brief.get("integraciones", {}).get("evolution_instance", slug)

    print("\n" + "="*60)
    print(f"  CHECKLIST DE ONBOARDING — {nombre}")
    print("="*60)

    # Evolution API
    if instance_check.get("ok") is None:
        print("\n  [?] Evolution API — vars no configuradas, verificar manualmente")
    elif instance_check.get("ok") and instance_check.get("estado") == "open":
        print(f"\n  [✓] Evolution API — instancia '{instance_name}' conectada")
    elif instance_check.get("existe") is False:
        print(f"\n  [ ] Evolution API — CREAR instancia '{instance_name}':")
        print(f"       POST {EVOLUTION_API_URL or '<EVOLUTION_API_URL>'}/instance/create")
        print(f"       Body: {{\"instanceName\": \"{instance_name}\", \"qrcode\": true}}")
        print(f"       Luego escanear QR con el número WhatsApp del cliente")
    else:
        print(f"\n  [!] Evolution API — instancia '{instance_name}': {instance_check.get('detalle')}")

    # Easypanel
    print(f"\n  [ ] Easypanel — agregar env vars al servicio 'system-ia-agentes'")
    print(f"       (ver bloque ENV VARS arriba)")

    # Airtable
    print(f"\n  [ ] Airtable — verificar acceso a base appA8QxIhBYYAHw0F")
    print(f"       El cliente usará la base compartida de Mica")

    # Cal.com
    agenda = brief.get("agenda", {})
    if agenda.get("cal_com_activo"):
        cal_user = agenda.get("cal_com_username", "?")
        cal_event = agenda.get("cal_com_event_slug", "?")
        print(f"\n  [ ] Cal.com — verificar cuenta '{cal_user}' con event '{cal_event}'")
        print(f"       Asegurar que el usuario tenga slots disponibles")

    # WhatsApp connection
    print(f"\n  [ ] WhatsApp — enviar link de conexión al cliente")
    print(f"       (requiere instancia Evolution conectada con QR)")

    # Test
    print(f"\n  [ ] Test final — enviar mensaje de prueba al número del asesor:")
    asesor_tel = brief.get("asesor", {}).get("telefono", "?")
    print(f"       python probar_worker.sh <phone_id> mica-demo")

    print("\n" + "="*60 + "\n")


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Onboarding cliente System IA (Mica)")
    parser.add_argument("brief_yaml", help="Path al archivo YAML del brief")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo validar y mostrar output, sin guardar archivos")
    args = parser.parse_args()

    print(f"\n[onboard_mica] Procesando brief: {args.brief_yaml}")

    # 1. Cargar
    try:
        brief = _cargar_yaml(args.brief_yaml)
    except FileNotFoundError:
        print(f"[ERROR] Archivo no encontrado: {args.brief_yaml}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"[ERROR] YAML inválido: {e}")
        sys.exit(1)

    # 2. Validar
    errores = _validar(brief)
    if errores:
        print("\n[ERROR] Brief inválido:")
        for e in errores:
            print(f"  - {e}")
        sys.exit(1)

    slug = brief["slug"]
    print(f"[onboard_mica] Slug: {slug} | Empresa: {brief.get('nombre_empresa')}")

    # 3. Verificar Evolution API
    instance_name = brief.get("integraciones", {}).get("evolution_instance", "") or slug
    print(f"[onboard_mica] Verificando instancia Evolution: '{instance_name}'...")
    instance_check = _check_evolution_instance(instance_name)
    print(f"[onboard_mica] Evolution: {instance_check['detalle']}")

    # 4. Generar env vars
    env_vars = _generar_env_vars(brief)
    _imprimir_env_vars(env_vars)

    # 5. Guardar brief (si no es dry-run)
    if not args.dry_run:
        dest = _guardar_brief(brief, slug)
        print(f"\n[onboard_mica] Brief guardado en: {dest}")
    else:
        print(f"\n[onboard_mica] Dry-run: no se guardan archivos")

    # 6. Checklist
    _imprimir_checklist(brief, env_vars, instance_check)


if __name__ == "__main__":
    main()
