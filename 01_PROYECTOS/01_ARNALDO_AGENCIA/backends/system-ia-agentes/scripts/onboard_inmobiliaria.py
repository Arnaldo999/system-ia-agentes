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
    """Crea tenant en Supabase para el CRM SaaS.
    Mapea los datos del config a las columnas reales de la tabla tenants.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"ok": False, "error": "Supabase no configurado"}

    pin_hash = hashlib.sha256(pin.encode()).hexdigest()

    # Mapeo al schema real de Supabase (ver tenant "demo" como referencia)
    payload = {
        "slug": slug,
        "nombre": nombre,
        "pin_hash": pin_hash,
        "activo": True,
        "subniche": config.get("vertical", "inmobiliaria"),
        "api_prefix": f"/clientes/lovbot/{slug}",
        "ciudad": config.get("ciudad", ""),
        "moneda": config.get("moneda", "USD"),
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


# ── Multi-inbox Mode ─────────────────────────────────────────────────────────
# En vez de crear una cuenta Chatwoot por cliente (Multi-account, requiere
# Platform Token), creamos UN inbox WhatsApp por cliente DENTRO de la unica
# cuenta "Lovbot AI" (account_id = LOVBOT_CHATWOOT_ACCOUNT_ID).
#
# Cada cliente recibe un agent con role="agent" y solo el inbox que le
# corresponde. Asi no ve chats de otros clientes pero la agencia (admins)
# ve todo desde una sola vista.

CHATWOOT_PLATFORM_TOKEN = os.environ.get("LOVBOT_CHATWOOT_PLATFORM_TOKEN", "")
CHATWOOT_ACCOUNT_ID = int(os.environ.get("LOVBOT_CHATWOOT_ACCOUNT_ID", "2"))


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


# ── 6. Chatwoot — Crear agent y asignar inbox (Multi-inbox mode) ─────────────

def crear_agent_chatwoot(
    account_id: int,
    email: str,
    name: str,
    password: str = "",
    role: str = "agent",
    inbox_ids: list = None,
) -> dict:
    """Crea un agent en una cuenta Chatwoot usando la API de cuenta normal
    (no requiere Platform Token).

    role:
      - "agent" (default): solo ve inboxes asignados — IDEAL PARA CLIENTES
      - "administrator": ve toda la cuenta — para vos/Robert internamente

    inbox_ids: lista de IDs de inboxes a los que el agent tendra acceso.
    Si se omite, el agent no tiene acceso a ningun inbox (hay que asignar
    despues con asignar_inbox_a_agent).
    """
    if not CHATWOOT_TOKEN:
        return {"ok": False, "error": "CHATWOOT_TOKEN no configurado"}

    headers = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}
    user_id = None
    reused = False

    # 0. Verificar si el agent con ese email ya existe (evita HTTP 422 duplicado)
    try:
        r_list = requests.get(
            f"{CHATWOOT_URL}/api/v1/accounts/{account_id}/agents",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if r_list.status_code == 200:
            agents = r_list.json()
            if isinstance(agents, dict):
                agents = agents.get("payload", [])
            for a in agents:
                if (a.get("email") or "").lower() == email.lower():
                    user_id = a.get("id")
                    reused = True
                    break
    except Exception:
        pass  # si falla la verificacion, seguimos y dejamos que el POST falle explicitamente

    # 1. Si NO existe, crear el agent (POST /api/v1/accounts/{id}/agents)
    if not user_id:
        payload = {"name": name, "email": email, "role": role}
        if password:
            payload["password"] = password
        try:
            r1 = requests.post(
                f"{CHATWOOT_URL}/api/v1/accounts/{account_id}/agents",
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            if r1.status_code not in (200, 201):
                return {"ok": False, "error": f"Agent create HTTP {r1.status_code}: {r1.text[:200]}"}
            agent_data = r1.json()
            user_id = agent_data.get("id")
        except Exception as e:
            return {"ok": False, "error": f"Excepcion creando agent: {e}"}

    # 2. Asignar inboxes si se especificaron
    inbox_assigns = []
    if inbox_ids:
        for inbox_id in inbox_ids:
            r_assign = asignar_inbox_a_agent(account_id, inbox_id, user_id)
            inbox_assigns.append({"inbox_id": inbox_id, "ok": r_assign.get("ok")})

    return {
        "ok": True,
        "user_id": user_id,
        "email": email,
        "role": role,
        "reused_existing_agent": reused,
        "inboxes_assigned": inbox_assigns,
    }


def asignar_inbox_a_agent(account_id: int, inbox_id: int, user_id: int) -> dict:
    """Asigna un agent a un inbox especifico (le da permiso de verlo)."""
    if not CHATWOOT_TOKEN:
        return {"ok": False, "error": "CHATWOOT_TOKEN no configurado"}

    headers = {"api_access_token": CHATWOOT_TOKEN, "Content-Type": "application/json"}
    try:
        r = requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{account_id}/inbox_members",
            headers=headers,
            json={"inbox_id": inbox_id, "user_ids": [user_id]},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            return {"ok": True}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


# ── 9. Email de bienvenida via Resend ────────────────────────────────────────

RESEND_API_KEY = os.environ.get("LOVBOT_RESEND_API_KEY", "") or os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("LOVBOT_RESEND_FROM", "Lovbot <onboarding@lovbot.mx>")


def enviar_bienvenida_email(
    to_email: str,
    nombre_empresa: str,
    nombre_asesor: str,
    accesos: dict,
) -> dict:
    """Envia email de bienvenida al cliente con todos los accesos.
    Backup permanente de las credenciales en caso de que se pierda el WhatsApp.

    Requiere LOVBOT_RESEND_API_KEY (Resend.com — 3000 emails/mes free).
    El dominio FROM debe estar verificado en Resend (ej: lovbot.mx).
    """
    if not RESEND_API_KEY:
        return {"ok": False, "error": "LOVBOT_RESEND_API_KEY no configurado"}

    chatwoot_url = accesos.get("chatwoot_url", "")
    chatwoot_email = accesos.get("chatwoot_email", "")
    chatwoot_password = accesos.get("chatwoot_password", "")
    crm_url = accesos.get("crm_url", "")
    crm_pin = accesos.get("crm_pin", "")

    subject = f"🎉 Tu bot Lovbot está activo — {nombre_empresa}"

    # HTML email con branding Lovbot
    html_body = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:14px;border:1px solid #e2e8f0;overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="background:#0f172a;padding:32px;text-align:center;">
              <h1 style="color:#fff;font-size:24px;margin:0;">🎉 ¡Bienvenido a Lovbot!</h1>
              <p style="color:#94a3b8;font-size:14px;margin:8px 0 0;">{nombre_empresa}</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <p style="font-size:16px;color:#0f172a;margin:0 0 16px;">Hola <strong>{nombre_asesor}</strong>,</p>
              <p style="font-size:15px;color:#475569;line-height:1.6;margin:0 0 24px;">
                Tu bot de WhatsApp ya está conectado y respondiendo automáticamente.
                Acá te dejamos todos los accesos a tus paneles de gestión.
                Guardá este email en lugar seguro — son tus credenciales permanentes.
              </p>

              <!-- Chatwoot card -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;border-radius:10px;padding:20px;margin-bottom:16px;">
                <tr><td>
                  <p style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;font-weight:600;">📊 Panel Chatwoot — Chats en vivo</p>
                  <p style="margin:4px 0;font-size:14px;color:#0f172a;"><strong>URL:</strong> <a href="{chatwoot_url}" style="color:#1a56db;">{chatwoot_url}</a></p>
                  <p style="margin:4px 0;font-size:14px;color:#0f172a;"><strong>Email:</strong> {chatwoot_email}</p>
                  <p style="margin:4px 0;font-size:14px;color:#0f172a;"><strong>Clave:</strong> <code style="background:#fff;padding:2px 8px;border-radius:4px;border:1px solid #e2e8f0;">{chatwoot_password}</code></p>
                </td></tr>
              </table>

              <!-- CRM card -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;border-radius:10px;padding:20px;margin-bottom:24px;">
                <tr><td>
                  <p style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 8px;font-weight:600;">📈 Tu CRM</p>
                  <p style="margin:4px 0;font-size:14px;color:#0f172a;"><strong>URL:</strong> <a href="{crm_url}" style="color:#1a56db;">{crm_url}</a></p>
                  <p style="margin:4px 0;font-size:14px;color:#0f172a;"><strong>PIN:</strong> <code style="background:#fff;padding:2px 8px;border-radius:4px;border:1px solid #e2e8f0;font-size:16px;">{crm_pin}</code></p>
                </td></tr>
              </table>

              <p style="font-size:14px;color:#475569;line-height:1.6;margin:0 0 16px;">
                <strong>Tutorial 5 minutos:</strong>
                <a href="https://lovbot.mx/tutorial-onboarding" style="color:#1a56db;">lovbot.mx/tutorial-onboarding</a>
              </p>

              <p style="font-size:14px;color:#475569;line-height:1.6;margin:0;">
                Cualquier duda escribinos a
                <a href="mailto:hola@lovbot.mx" style="color:#1a56db;">hola@lovbot.mx</a>.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;padding:24px;text-align:center;border-top:1px solid #e2e8f0;">
              <p style="font-size:12px;color:#94a3b8;margin:0;">© 2026 LOVBOT · Robert Bazán · Cancún, México</p>
              <p style="font-size:12px;color:#94a3b8;margin:6px 0 0;">
                <a href="https://lovbot-legal.vercel.app/terminos-de-servicio" style="color:#94a3b8;">Términos</a> ·
                <a href="https://lovbot.mx/politica-de-privacidad" style="color:#94a3b8;">Privacidad</a> ·
                <a href="https://lovbot-legal.vercel.app/eliminacion-datos" style="color:#94a3b8;">Eliminación de datos</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # Versión texto plano (fallback)
    text_body = f"""Hola {nombre_asesor},

Tu bot de WhatsApp ya está activo. Estos son tus accesos:

PANEL CHATWOOT (chats en vivo)
URL: {chatwoot_url}
Email: {chatwoot_email}
Clave: {chatwoot_password}

TU CRM
URL: {crm_url}
PIN: {crm_pin}

Tutorial 5 min: https://lovbot.mx/tutorial-onboarding

Cualquier duda: hola@lovbot.mx

— Equipo Lovbot
"""

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": text_body,
                "tags": [
                    {"name": "category", "value": "onboarding"},
                    {"name": "client", "value": nombre_empresa[:50]},
                ],
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code in (200, 201):
            return {"ok": True, "email_id": r.json().get("id"), "sent_to": to_email}
        return {"ok": False, "error": f"Resend HTTP {r.status_code}: {r.text[:200]}"}
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

    # Multi-inbox mode: usamos siempre la cuenta global "Lovbot AI"
    # (a menos que se pase explicitamente otra)
    if not chatwoot_account_id:
        chatwoot_account_id = CHATWOOT_ACCOUNT_ID

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

    # 2. Crear inbox WhatsApp Cloud API en la cuenta Lovbot (necesita datos WABA)
    inbox_id = None
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
        if r_inbox.get("ok"):
            inbox_id = r_inbox.get("inbox_id")

    # 3. Crear agent del cliente (role=agent) y asignarle SOLO su inbox.
    # Asi solo ve sus chats (no los de otros clientes de Lovbot).
    if email_asesor:
        inbox_ids = [inbox_id] if inbox_id else None
        r_agent = crear_agent_chatwoot(
            account_id=chatwoot_account_id,
            email=email_asesor,
            name=nombre_asesor,
            password=password_chatwoot,
            role="agent",  # NO administrator — para aislar al cliente
            inbox_ids=inbox_ids,
        )
        resultados["pasos"]["chatwoot_agent"] = r_agent

    # 4. Webhook bot pausa/retoma (compartido a nivel cuenta, ya configurado
    # para el bot Robert. No re-creamos por cliente para evitar duplicados.)
    # Si necesitas un webhook por cliente, descomentar:
    # webhook_url = f"https://agentes.lovbot.ai/clientes/lovbot/{slug}/chatwoot/webhook"
    # r_webhook = crear_webhook_chatwoot(chatwoot_account_id, webhook_url)
    # resultados["pasos"]["chatwoot_webhook"] = r_webhook

    # 5. Notificar al cliente con sus accesos por DOS canales (WhatsApp + Email)
    accesos = {
        "chatwoot_url": CHATWOOT_URL,
        "chatwoot_email": email_asesor,
        "chatwoot_password": password_chatwoot,
        "crm_url": f"https://crm.lovbot.ai?tenant={slug}",
        "crm_pin": pin,
    }

    # 5a. WhatsApp (canal inmediato)
    if enviar_bienvenida and access_token and phone_number_id and telefono_whatsapp:
        r_welcome = enviar_bienvenida_whatsapp(
            phone_number_id=phone_number_id,
            access_token=access_token,
            to=telefono_whatsapp,
            nombre_empresa=nombre_empresa,
            accesos=accesos,
        )
        resultados["pasos"]["whatsapp_welcome"] = r_welcome

    # 5b. Email (backup permanente — funciona aunque no haya WhatsApp)
    if email_asesor:
        r_email = enviar_bienvenida_email(
            to_email=email_asesor,
            nombre_empresa=nombre_empresa,
            nombre_asesor=nombre_asesor,
            accesos=accesos,
        )
        resultados["pasos"]["email_welcome"] = r_email

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
            "chatwoot_inbox_id": inbox_id,
            "chatwoot_email": email_asesor,
            "chatwoot_password": password_chatwoot,
            "chatwoot_role": "agent (solo ve su inbox)",
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
