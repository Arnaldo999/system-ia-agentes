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


# ── 4. Chatwoot — Crear CUENTA nueva (multi-account) ─────────────────────────

CHATWOOT_PLATFORM_TOKEN = os.environ.get("LOVBOT_CHATWOOT_PLATFORM_TOKEN", "")


def crear_cuenta_chatwoot(nombre: str) -> dict:
    """Crea una NUEVA cuenta (account) en Chatwoot.
    Requiere CHATWOOT_PLATFORM_TOKEN (super admin token, distinto al api_access_token).
    Devuelve {ok, account_id, account_name}.
    """
    if not CHATWOOT_PLATFORM_TOKEN:
        return {"ok": False, "error": "LOVBOT_CHATWOOT_PLATFORM_TOKEN no configurado"}

    try:
        r = requests.post(
            f"{CHATWOOT_URL}/platform/api/v1/accounts",
            headers={
                "api_access_token": CHATWOOT_PLATFORM_TOKEN,
                "Content-Type": "application/json",
            },
            json={"name": nombre},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {
                "ok": True,
                "account_id": data.get("id"),
                "account_name": data.get("name"),
            }
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 5. Chatwoot — Crear inbox WhatsApp Cloud API ─────────────────────────────

def crear_inbox_whatsapp(
    account_id: int,
    nombre_inbox: str,
    phone_number: str,
    phone_number_id: str,
    waba_id: str,
    access_token: str,
) -> dict:
    """Crea inbox WhatsApp Cloud API en una cuenta de Chatwoot.
    Apunta directamente al WABA del cliente conectado vía Embedded Signup.
    """
    if not CHATWOOT_TOKEN:
        return {"ok": False, "error": "CHATWOOT_TOKEN no configurado"}

    headers = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}
    payload = {
        "name": nombre_inbox,
        "channel": {
            "type": "whatsapp",
            "provider": "whatsapp_cloud",
            "phone_number": phone_number,  # ej: "+5219987434234"
            "provider_config": {
                "api_key": access_token,
                "phone_number_id": phone_number_id,
                "business_account_id": waba_id,
            },
        },
    }

    try:
        r = requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{account_id}/inboxes",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {
                "ok": True,
                "inbox_id": data.get("id"),
                "inbox_identifier": data.get("inbox_identifier"),
            }
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── 6. Chatwoot — Crear agent admin para el cliente ──────────────────────────

def crear_agent_chatwoot(
    account_id: int,
    email: str,
    name: str,
    password: str,
    role: str = "administrator",
) -> dict:
    """Crea un user (agent o administrator) en una cuenta Chatwoot.
    El cliente usa estas credenciales para entrar a su panel y atender chats.
    """
    if not CHATWOOT_PLATFORM_TOKEN:
        return {"ok": False, "error": "LOVBOT_CHATWOOT_PLATFORM_TOKEN no configurado"}

    # 1. Crear el user a nivel platform
    try:
        r1 = requests.post(
            f"{CHATWOOT_URL}/platform/api/v1/users",
            headers={
                "api_access_token": CHATWOOT_PLATFORM_TOKEN,
                "Content-Type": "application/json",
            },
            json={"name": name, "email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        if r1.status_code not in (200, 201):
            # Si ya existe, intentamos buscarlo
            return {"ok": False, "error": f"User create HTTP {r1.status_code}: {r1.text[:200]}"}
        user_id = r1.json().get("id")
    except Exception as e:
        return {"ok": False, "error": f"Excepcion creando user: {e}"}

    # 2. Asignar el user a la cuenta como administrator/agent
    try:
        r2 = requests.post(
            f"{CHATWOOT_URL}/platform/api/v1/accounts/{account_id}/account_users",
            headers={
                "api_access_token": CHATWOOT_PLATFORM_TOKEN,
                "Content-Type": "application/json",
            },
            json={"user_id": user_id, "role": role},
            timeout=REQUEST_TIMEOUT,
        )
        if r2.status_code in (200, 201):
            return {"ok": True, "user_id": user_id, "email": email, "role": role}
        return {"ok": False, "error": f"Account assign HTTP {r2.status_code}: {r2.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"Excepcion asignando user: {e}"}


# ── 7. Generar password seguro ────────────────────────────────────────────────

def generar_password() -> str:
    """Genera password de 12 chars (alfanumerico + simbolos)."""
    import secrets
    import string
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(chars) for _ in range(12))


# ── 8. Enviar mensaje de bienvenida al cliente via Meta API ──────────────────

def enviar_bienvenida_whatsapp(
    phone_number_id: str,
    access_token: str,
    to: str,
    nombre_empresa: str,
    accesos: dict,
) -> dict:
    """Envia mensaje de bienvenida con accesos al cliente recien onboardeado.
    Usa el access_token del MISMO cliente para enviar desde su numero a si mismo,
    o desde el numero del Tech Provider al cliente.
    """
    chatwoot_url = accesos.get("chatwoot_url", "")
    chatwoot_email = accesos.get("chatwoot_email", "")
    chatwoot_password = accesos.get("chatwoot_password", "")
    crm_url = accesos.get("crm_url", "")
    crm_pin = accesos.get("crm_pin", "")

    body = (
        f"🎉 Bienvenido a Lovbot, {nombre_empresa}!\n\n"
        f"Tu bot WhatsApp ya esta activo y respondiendo.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 PANEL CHATWOOT (chats en vivo)\n"
        f"🔗 {chatwoot_url}\n"
        f"📧 Usuario: {chatwoot_email}\n"
        f"🔑 Clave: {chatwoot_password}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 TU CRM\n"
        f"🔗 {crm_url}\n"
        f"🔢 PIN: {crm_pin}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📚 Tutorial 5 min: https://lovbot.mx/tutorial-onboarding\n\n"
        f"Cualquier duda escribinos.\n"
        f"— Equipo Lovbot"
    )

    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body},
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            return {"ok": True, "message_id": r.json().get("messages", [{}])[0].get("id")}
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
    # Datos opcionales del Embedded Signup (si viene desde la landing)
    waba_id: str = "",
    phone_number_id: str = "",
    access_token: str = "",
    enviar_bienvenida: bool = False,
) -> dict:
    """Ejecuta el onboarding completo de un cliente inmobiliario.

    Si chatwoot_account_id es None, crea una CUENTA NUEVA en Chatwoot
    (modo full auto, requiere LOVBOT_CHATWOOT_PLATFORM_TOKEN).

    Si vienen waba_id + phone_number_id + access_token (datos del Embedded
    Signup), también:
      - Crea inbox WhatsApp Cloud API en la cuenta nueva
      - Crea agent admin para el cliente
      - Envía mensaje WhatsApp con accesos (si enviar_bienvenida=True)
    """

    slug = generar_slug(nombre_empresa)
    pin = generar_pin()
    password_chatwoot = generar_password()
    resultados = {"slug": slug, "pin": pin, "pasos": {}}

    # 1. Supabase tenant
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

    # 2. Chatwoot — crear cuenta si no se provee account_id
    if not chatwoot_account_id:
        r_cuenta = crear_cuenta_chatwoot(f"{nombre_empresa} (Lovbot)")
        resultados["pasos"]["chatwoot_cuenta"] = r_cuenta
        if r_cuenta.get("ok"):
            chatwoot_account_id = r_cuenta["account_id"]

    # 3. Si tenemos account_id (provisto o recién creado), seguimos
    if chatwoot_account_id:
        # 3a. Labels estándar
        r2 = crear_labels_chatwoot(chatwoot_account_id)
        resultados["pasos"]["chatwoot_labels"] = r2

        # 3b. Webhook bot pausa/retoma
        webhook_url = f"https://agentes.lovbot.ai/clientes/lovbot/{slug}/chatwoot/webhook"
        r3 = crear_webhook_chatwoot(chatwoot_account_id, webhook_url)
        resultados["pasos"]["chatwoot_webhook"] = r3

        # 3c. Inbox WhatsApp Cloud API (solo si tenemos credenciales WABA del cliente)
        if waba_id and phone_number_id and access_token:
            r_inbox = crear_inbox_whatsapp(
                account_id=chatwoot_account_id,
                nombre_inbox=f"WhatsApp {nombre_empresa}",
                phone_number=telefono_whatsapp,
                phone_number_id=phone_number_id,
                waba_id=waba_id,
                access_token=access_token,
            )
            resultados["pasos"]["chatwoot_inbox"] = r_inbox

        # 3d. Crear agent admin para que el cliente entre a Chatwoot
        if email_asesor:
            r_agent = crear_agent_chatwoot(
                account_id=chatwoot_account_id,
                email=email_asesor,
                name=nombre_asesor,
                password=password_chatwoot,
                role="administrator",
            )
            resultados["pasos"]["chatwoot_agent"] = r_agent

    # 4. Enviar mensaje de bienvenida via WhatsApp (opcional)
    if enviar_bienvenida and access_token and phone_number_id and telefono_whatsapp:
        accesos = {
            "chatwoot_url": CHATWOOT_URL,
            "chatwoot_email": email_asesor,
            "chatwoot_password": password_chatwoot,
            "crm_url": f"https://crm.lovbot.ai?tenant={slug}",
            "crm_pin": pin,
        }
        r_welcome = enviar_bienvenida_whatsapp(
            phone_number_id=phone_number_id,
            access_token=access_token,
            to=telefono_whatsapp,
            nombre_empresa=nombre_empresa,
            accesos=accesos,
        )
        resultados["pasos"]["whatsapp_welcome"] = r_welcome

    # Resumen
    ok_count = sum(1 for p in resultados["pasos"].values() if p.get("ok"))
    total = len(resultados["pasos"])
    resultados["resumen"] = {
        "ok": ok_count == total,
        "completados": f"{ok_count}/{total}",
        "accesos": {
            "crm_url": f"https://crm.lovbot.ai?tenant={slug}",
            "crm_pin": pin,
            "chatwoot_url": CHATWOOT_URL,
            "chatwoot_account_id": chatwoot_account_id,
            "chatwoot_email": email_asesor,
            "chatwoot_password": password_chatwoot,
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
