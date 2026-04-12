"""
Auditor Social — Verifica que las publicaciones diarias se ejecutaron bien
==========================================================================
Para cada cliente en Supabase (tabla clientes), verifica que tenga
credenciales válidas de cada plataforma configurada (IG, FB, LinkedIn).

Si un token es inválido o falta, genera alerta antes de que la publicación falle.

Variables de entorno:
    SUPABASE_URL, SUPABASE_KEY
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TIMEOUT = 10


def _supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def _check_linkedin_token(token: str, cliente: str) -> dict:
    """Verifica si un token de LinkedIn es válido."""
    if not token:
        return {"ok": False, "nombre": f"LinkedIn {cliente}",
                "tipo": "credencial_faltante", "detalle": "sin token configurado"}
    try:
        r = requests.get("https://api.linkedin.com/v2/userinfo",
                         headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
        if r.status_code == 200:
            return {"ok": True}
        return {"ok": False, "nombre": f"LinkedIn {cliente}",
                "tipo": "token_invalido", "detalle": f"HTTP {r.status_code} — renovar token"}
    except Exception as e:
        return {"ok": False, "nombre": f"LinkedIn {cliente}",
                "tipo": "api_error", "detalle": str(e)[:100]}


def _check_facebook_token(token: str, page_id: str, cliente: str) -> dict:
    """Verifica si un token de Facebook es válido."""
    if not token or not page_id:
        return {"ok": False, "nombre": f"Facebook {cliente}",
                "tipo": "credencial_faltante", "detalle": "sin token o page_id"}
    try:
        r = requests.get(f"https://graph.facebook.com/v21.0/{page_id}",
                         params={"access_token": token, "fields": "name"},
                         timeout=TIMEOUT)
        if r.status_code == 200:
            return {"ok": True}
        return {"ok": False, "nombre": f"Facebook {cliente}",
                "tipo": "token_invalido", "detalle": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "nombre": f"Facebook {cliente}",
                "tipo": "api_error", "detalle": str(e)[:100]}


def _check_instagram_token(token: str, ig_id: str, cliente: str) -> dict:
    """Verifica si un token de Instagram es válido."""
    if not token or not ig_id:
        return {"ok": False, "nombre": f"Instagram {cliente}",
                "tipo": "credencial_faltante", "detalle": "sin token o ig_user_id"}
    try:
        r = requests.get(f"https://graph.facebook.com/v21.0/{ig_id}",
                         params={"access_token": token, "fields": "username"},
                         timeout=TIMEOUT)
        if r.status_code == 200:
            return {"ok": True}
        return {"ok": False, "nombre": f"Instagram {cliente}",
                "tipo": "token_invalido", "detalle": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "nombre": f"Instagram {cliente}",
                "tipo": "api_error", "detalle": str(e)[:100]}


def run() -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"auditor": "social", "ok": False,
                "alertas": [{"nombre": "Supabase", "tipo": "config",
                             "detalle": "SUPABASE_URL o SUPABASE_KEY no configuradas"}]}

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/clientes?select=cliente_id,linkedin_access_token,linkedin_person_id,"
            "facebook_page_token,facebook_page_id,instagram_token,instagram_user_id",
            headers=_supa_headers(), timeout=TIMEOUT)
        if r.status_code != 200:
            return {"auditor": "social", "ok": False,
                    "alertas": [{"nombre": "Supabase", "tipo": "api_error",
                                 "detalle": f"HTTP {r.status_code}"}]}
        clientes = r.json()
    except Exception as e:
        return {"auditor": "social", "ok": False,
                "alertas": [{"nombre": "Supabase", "tipo": "api_error",
                             "detalle": str(e)[:100]}]}

    alertas = []
    for c in clientes:
        cid = c.get("cliente_id", "?")

        # LinkedIn
        li_token = c.get("linkedin_access_token", "")
        if li_token:
            check = _check_linkedin_token(li_token, cid)
            if not check["ok"]:
                alertas.append(check)

        # Facebook
        fb_token = c.get("facebook_page_token", "")
        fb_page = c.get("facebook_page_id", "")
        if fb_token:
            check = _check_facebook_token(fb_token, fb_page, cid)
            if not check["ok"]:
                alertas.append(check)

        # Instagram
        ig_token = c.get("instagram_token", "") or fb_token
        ig_id = c.get("instagram_user_id", "")
        if ig_token and ig_id:
            check = _check_instagram_token(ig_token, ig_id, cid)
            if not check["ok"]:
                alertas.append(check)

    return {
        "auditor": "social",
        "ok": len(alertas) == 0,
        "alertas": alertas,
        "detalle": {"clientes_verificados": len(clientes)},
    }
