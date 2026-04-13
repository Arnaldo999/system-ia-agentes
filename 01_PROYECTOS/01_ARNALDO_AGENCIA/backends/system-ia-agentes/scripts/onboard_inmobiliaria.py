"""
Onboarding Automático — Cliente Inmobiliaria (Lovbot)
=====================================================
Crea toda la infraestructura para un cliente nuevo:
  1. Tenant en Supabase (CRM SaaS)
  2. Labels en Chatwoot + cuenta asesor
  3. Registro en Airtable
  4. Configuración env vars

Uso:
  Desde FastAPI: POST /admin/onboard con JSON
  Desde CLI: python onboard_inmobiliaria.py --nombre "..." --asesor-email "..."

Requiere:
  SUPABASE_URL, SUPABASE_KEY
  LOVBOT_CHATWOOT_API_TOKEN, LOVBOT_CHATWOOT_URL
  AIRTABLE_TOKEN
"""

import os
import re
import json
import hashlib
import datetime
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Config ───────────────────────────────────────────────────────────────────
SUPABASE_URL  = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "")
CHATWOOT_URL  = os.environ.get("LOVBOT_CHATWOOT_URL", "https://chatwoot.lovbot.ai")
CHATWOOT_TOKEN = os.environ.get("LOVBOT_CHATWOOT_API_TOKEN", "")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "") or os.environ.get("AIRTABLE_API_KEY", "")
REQUEST_TIMEOUT = 10

# Labels estándar para cada cliente
LABELS_ESTANDAR = [
    {"title": "caliente", "color": "#FF0000"},
    {"title": "tibio", "color": "#F7FC04"},
    {"title": "frio", "color": "#00E9FF"},
    {"title": "atiende-humano", "color": "#FFFFFF"},
    {"title": "atiende-agenteai", "color": "#FF00DB"},
    {"title": "automatizacion", "color": "#2FFF00"},
]


def generar_slug(nombre: str) -> str:
    """Convierte nombre a slug URL-safe."""
    slug = nombre.lower().strip()
    slug = re.sub(r'[áàä]', 'a', slug)
    slug = re.sub(r'[éèë]', 'e', slug)
    slug = re.sub(r'[íìï]', 'i', slug)
    slug = re.sub(r'[óòö]', 'o', slug)
    slug = re.sub(r'[úùü]', 'u', slug)
    slug = re.sub(r'[ñ]', 'n', slug)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    return slug[:50]


def generar_pin() -> str:
    """Genera PIN de 4 dígitos."""
    import random
    return str(random.randint(1000, 9999))


# ── 1. Supabase — Crear tenant ───────────────────────────────────────────────

def crear_tenant_supabase(nombre: str, slug: str, pin: str, config: dict) -> dict:
    """Crea tenant en Supabase para el CRM SaaS."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"ok": False, "error": "Supabase no configurado"}

    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    hoy = datetime.date.today()
    vence = hoy + datetime.timedelta(days=365)

    payload = {
        "slug": slug,
        "nombre": nombre,
        "pin_hash": pin_hash,
        "estado_pago": "activo",
        "fecha_inicio": hoy.isoformat(),
        "fecha_vence": vence.isoformat(),
        "config": json.dumps(config),
    }

    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/tenants",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {"ok": True, "tenant": data[0] if isinstance(data, list) else data}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 2. Chatwoot — Crear labels ───────────────────────────────────────────────

def crear_labels_chatwoot(account_id: int) -> dict:
    """Crea labels estándar en una cuenta de Chatwoot."""
    if not CHATWOOT_TOKEN:
        return {"ok": False, "error": "Chatwoot no configurado"}

    headers = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}
    creados = []
    errores = []

    for label in LABELS_ESTANDAR:
        try:
            r = requests.post(
                f"{CHATWOOT_URL}/api/v1/accounts/{account_id}/labels",
                headers=headers,
                json={"title": label["title"], "color": label["color"], "show_on_sidebar": True},
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code in (200, 201):
                creados.append(label["title"])
            else:
                errores.append(f"{label['title']}: {r.status_code}")
        except Exception as e:
            errores.append(f"{label['title']}: {e}")

    return {"ok": len(errores) == 0, "creados": creados, "errores": errores}


# ── 3. Chatwoot — Crear webhook ──────────────────────────────────────────────

def crear_webhook_chatwoot(account_id: int, webhook_url: str) -> dict:
    """Configura webhook en Chatwoot para pausa/retoma del bot."""
    if not CHATWOOT_TOKEN:
        return {"ok": False, "error": "Chatwoot no configurado"}

    headers = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}
    try:
        r = requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{account_id}/webhooks",
            headers=headers,
            json={
                "webhook": {
                    "url": webhook_url,
                    "subscriptions": ["conversation_status_changed", "conversation_updated"],
                }
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            return {"ok": True, "webhook": r.json()}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Orquestador principal ────────────────────────────────────────────────────

def onboard(
    nombre_empresa: str,
    nombre_asesor: str,
    email_asesor: str,
    telefono_whatsapp: str,
    ciudad: str = "",
    zonas: str = "",
    moneda: str = "USD",
    chatwoot_account_id: int = None,
) -> dict:
    """Ejecuta el onboarding completo de un cliente inmobiliario."""

    slug = generar_slug(nombre_empresa)
    pin = generar_pin()
    resultados = {"slug": slug, "pin": pin, "pasos": {}}

    # 1. Supabase
    config = {
        "nombre_empresa": nombre_empresa,
        "nombre_asesor": nombre_asesor,
        "email_asesor": email_asesor,
        "telefono": telefono_whatsapp,
        "ciudad": ciudad,
        "zonas": zonas,
        "moneda": moneda,
    }
    r1 = crear_tenant_supabase(nombre_empresa, slug, pin, config)
    resultados["pasos"]["supabase"] = r1

    # 2. Chatwoot labels (si tiene account_id)
    if chatwoot_account_id:
        r2 = crear_labels_chatwoot(chatwoot_account_id)
        resultados["pasos"]["chatwoot_labels"] = r2

        # 3. Chatwoot webhook
        webhook_url = f"https://agentes.arnaldoayalaestratega.cloud/clientes/lovbot/inmobiliaria/chatwoot/webhook"
        r3 = crear_webhook_chatwoot(chatwoot_account_id, webhook_url)
        resultados["pasos"]["chatwoot_webhook"] = r3

    # Resumen
    ok_count = sum(1 for p in resultados["pasos"].values() if p.get("ok"))
    total = len(resultados["pasos"])
    resultados["resumen"] = {
        "ok": ok_count == total,
        "completados": f"{ok_count}/{total}",
        "accesos": {
            "crm_url": f"https://crm.lovbot.ai?tenant={slug}",
            "pin": pin,
            "email_asesor": email_asesor,
            "chatwoot_url": CHATWOOT_URL,
        },
    }

    return resultados


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Onboarding cliente inmobiliario")
    parser.add_argument("--nombre", required=True, help="Nombre empresa")
    parser.add_argument("--asesor", required=True, help="Nombre asesor")
    parser.add_argument("--email", required=True, help="Email asesor")
    parser.add_argument("--telefono", required=True, help="WhatsApp del negocio")
    parser.add_argument("--ciudad", default="", help="Ciudad")
    parser.add_argument("--zonas", default="", help="Zonas separadas por coma")
    parser.add_argument("--moneda", default="USD", help="Moneda (USD/ARS/MXN)")
    parser.add_argument("--chatwoot-account", type=int, help="Chatwoot account ID")
    args = parser.parse_args()

    resultado = onboard(
        nombre_empresa=args.nombre,
        nombre_asesor=args.asesor,
        email_asesor=args.email,
        telefono_whatsapp=args.telefono,
        ciudad=args.ciudad,
        zonas=args.zonas,
        moneda=args.moneda,
        chatwoot_account_id=args.chatwoot_account,
    )
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
