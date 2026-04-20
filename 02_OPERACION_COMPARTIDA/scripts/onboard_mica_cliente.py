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

AIRTABLE_API_KEY   = os.getenv("AIRTABLE_API_KEY", "") or os.getenv("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_MICA = os.getenv("MICA_AIRTABLE_BASE_ID", "") or os.getenv("MICA_DEMO_AIRTABLE_BASE", "") or "appA8QxIhBYYAHw0F"
TABLE_CLIENTES_AGENCIA = os.getenv("MICA_AIRTABLE_TABLE_CLIENTES_AGENCIA", "Clientes_Agencia")

MICA_WHATSAPP = os.getenv("MICA_WHATSAPP_CONTACTO", "5493XXXXXXXXX")
ONBOARDING_URL = os.getenv("MICA_ONBOARDING_URL", "https://systemia-onboarding.vercel.app")
CRM_BASE_URL = os.getenv("MICA_CRM_BASE_URL", "https://lovbot-demos.vercel.app")
CHATWOOT_BASE_URL = os.getenv("MICA_CHATWOOT_URL", "")

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


def _registrar_airtable(brief: dict) -> dict:
    """Upsert del cliente en tabla Clientes_Agencia de base Mica.
    Retorna dict con ok, detalle, chatwoot_url, crm_url, onboarding_url.
    """
    if not AIRTABLE_API_KEY:
        return {"ok": False, "detalle": "AIRTABLE_API_KEY no configurada — skip"}

    slug = brief["slug"]
    asesor = brief.get("asesor", {})
    integraciones = brief.get("integraciones", {})

    crm_url = f"{CRM_BASE_URL}/?tenant={slug}" if CRM_BASE_URL else ""
    chatwoot_url = f"{CHATWOOT_BASE_URL}?cliente={slug}" if CHATWOOT_BASE_URL else ""
    onboarding_url = f"{ONBOARDING_URL}/?slug={slug}"

    fields = {
        "Slug": slug,
        "Nombre_Empresa": brief.get("nombre_empresa", ""),
        "Vertical": brief.get("vertical", "inmobiliaria"),
        "Numero_WhatsApp": str(asesor.get("telefono", "")),
        "Evolution_Instance": integraciones.get("evolution_instance", "") or slug,
        "Provider": "evolution",
        "Chatwoot_Url": chatwoot_url,
        "CRM_Url": crm_url,
        "Asesor_Nombre": asesor.get("nombre", ""),
        "Asesor_Telefono": str(asesor.get("telefono", "")),
        "Asesor_Email": asesor.get("email", ""),
        "Ciudad": brief.get("ciudad", ""),
        "Estado": "pendiente",
        "Fecha_Alta": datetime.now().strftime("%Y-%m-%d"),
    }
    # Eliminar vacíos
    fields = {k: v for k, v in fields.items() if v not in (None, "", "0")}

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_MICA}/{TABLE_CLIENTES_AGENCIA}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.patch(url, headers=headers, json={
            "performUpsert": {"fieldsToMergeOn": ["Slug"]},
            "records": [{"fields": fields}],
        }, timeout=15)
        if r.status_code >= 400:
            return {"ok": False, "detalle": f"Airtable HTTP {r.status_code}: {r.text[:200]}"}
        rec = (r.json().get("records") or [{}])[0]
        return {
            "ok": True,
            "detalle": f"Cliente '{slug}' registrado en {TABLE_CLIENTES_AGENCIA} (id={rec.get('id','?')})",
            "chatwoot_url": chatwoot_url,
            "crm_url": crm_url,
            "onboarding_url": onboarding_url,
        }
    except Exception as e:
        return {"ok": False, "detalle": f"Error Airtable: {e}"}


def _generar_mensaje_cliente(brief: dict, registro: dict) -> str:
    """Genera el mensaje de WhatsApp listo para copiar y enviar al cliente."""
    nombre_empresa = brief.get("nombre_empresa", "")
    asesor = brief.get("asesor", {}).get("nombre", "").split()[0] or ""
    onboarding_url = registro.get("onboarding_url", "")

    return f"""¡Hola {asesor}! 👋

Ya tenemos lista tu integración de *{nombre_empresa}* con System IA.

Para activar tu bot de WhatsApp solo tenés que:

1️⃣ Entrar a este link desde la PC o celular:
{onboarding_url}

2️⃣ Escanear el código QR con el WhatsApp Business que vas a usar para el bot (desde tu celular: menú → Dispositivos vinculados → Vincular nuevo)

3️⃣ Listo. La página te muestra automáticamente:
 • Link a tu CRM (donde vas a ver todos tus leads y propiedades)
 • Link a Chatwoot (para atender manualmente cuando haga falta)

Si tenés cualquier duda, escribime por acá. 🙌

— Micaela | System IA"""


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

    # Easypanel / Coolify
    if env_vars:
        print(f"\n  [ ] Coolify/Easypanel — agregar env vars al servicio 'system-ia-agentes'")
        print(f"       (ver bloque ENV VARS arriba)")
    else:
        print(f"\n  [✓] ENV vars — no hay vars especiales (cliente usa config por defecto)")

    # Airtable
    print(f"\n  [✓] Airtable — registro automatico en {TABLE_CLIENTES_AGENCIA}")

    # Cal.com
    agenda = brief.get("agenda", {})
    if agenda.get("cal_com_activo"):
        cal_user = agenda.get("cal_com_username", "?")
        cal_event = agenda.get("cal_com_event_slug", "?")
        print(f"\n  [ ] Cal.com — verificar cuenta '{cal_user}' con event '{cal_event}'")
        print(f"       Asegurar que el usuario tenga slots disponibles")

    # Chatwoot
    print(f"\n  [ ] Chatwoot — crear inbox para '{slug}'")
    print(f"       Opcion recomendada: inbox tipo 'API' con webhook a un endpoint del backend")

    # WhatsApp connection — ahora automatico
    print(f"\n  [→] Enviar mensaje al cliente (ver abajo)")

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

    # 5. Guardar brief + registrar en Airtable Clientes_Agencia (si no es dry-run)
    registro = {}
    if not args.dry_run:
        dest = _guardar_brief(brief, slug)
        print(f"\n[onboard_mica] Brief guardado en: {dest}")

        print(f"[onboard_mica] Registrando cliente en Airtable {TABLE_CLIENTES_AGENCIA}...")
        registro = _registrar_airtable(brief)
        print(f"[onboard_mica] Airtable: {registro['detalle']}")
    else:
        print(f"\n[onboard_mica] Dry-run: no se guardan archivos ni se registra en Airtable")

    # 6. Checklist
    _imprimir_checklist(brief, env_vars, instance_check)

    # 7. Mensaje WhatsApp listo para copiar y enviar al cliente
    if registro.get("ok"):
        mensaje = _generar_mensaje_cliente(brief, registro)
        print("\n" + "="*60)
        print("  MENSAJE LISTO PARA ENVIAR AL CLIENTE POR WHATSAPP")
        print("="*60)
        print(mensaje)
        print("="*60)
        print(f"\n  Link onboarding: {registro['onboarding_url']}")
        if registro.get('crm_url'):
            print(f"  Link CRM:        {registro['crm_url']}")
        if registro.get('chatwoot_url'):
            print(f"  Link Chatwoot:   {registro['chatwoot_url']}")
        print()


if __name__ == "__main__":
    main()
