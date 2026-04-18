"""
Auditor Lovbot Ecosystem — Fase 2.5
=====================================
Verifica el estado de la infraestructura Tech Provider de Lovbot (Robert).

Checks:
    1. agentes.lovbot.ai health  — FastAPI backend Hetzner responde
    2. Resend API + dominio      — API key activa, lovbot.ai verificado
    3. Chatwoot Lovbot           — instancia responde, al menos 1 agente
    4. Vercel projects           — 5 URLs críticas responden 200

Nota: Supabase tenants y Meta Graph API token ya se cubren en
      auditor_crm.py y auditor_meta_provider.py respectivamente.

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas (opcionales — skip si ausentes):
    LOVBOT_RESEND_API_KEY          → API key de Resend (Robert)
    LOVBOT_CHATWOOT_API_TOKEN      → token Chatwoot instancia Lovbot
    LOVBOT_CHATWOOT_URL            → URL base Chatwoot (ej: https://chatwoot.lovbot.ai)
    LOVBOT_CHATWOOT_ACCOUNT_ID     → ID de cuenta Chatwoot (ej: 2)
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

LOVBOT_BACKEND_URL        = os.getenv("LOVBOT_BACKEND_URL", "https://agentes.lovbot.ai")
LOVBOT_RESEND_API_KEY     = os.getenv("LOVBOT_RESEND_API_KEY", "")
LOVBOT_CHATWOOT_URL       = os.getenv("LOVBOT_CHATWOOT_URL", "https://chatwoot.lovbot.ai")
LOVBOT_CHATWOOT_TOKEN     = os.getenv("LOVBOT_CHATWOOT_API_TOKEN", "")
LOVBOT_CHATWOOT_ACCOUNT   = os.getenv("LOVBOT_CHATWOOT_ACCOUNT_ID", "2")

REQUEST_TIMEOUT = 8
RETRY_WAIT      = 4

VERCEL_URLS = [
    ("Lovbot Onboarding",  "https://lovbot-onboarding.vercel.app/"),
    ("Lovbot Brief Form",  "https://lovbot-brief-form.vercel.app/"),
    ("Lovbot Legal",       "https://lovbot-legal.vercel.app/"),
    ("Lovbot Meta Review", "https://lovbot-meta-review.vercel.app/"),
    ("CRM Lovbot",         "https://crm.lovbot.ai/"),
]

RESEND_DOMAIN_ESPERADO = "lovbot.ai"


# ── helpers ───────────────────────────────────────────────────────────────────

def _get(url: str, headers: dict = None, params: dict = None,
         timeout: int = REQUEST_TIMEOUT) -> tuple[int, dict | list | None]:
    """GET con 1 retry. Devuelve (status_code, body_json_o_none)."""
    for intento in range(2):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, None
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                return -1, None
    return -1, None


def _head_or_get(url: str, timeout: int = REQUEST_TIMEOUT) -> tuple[int, float]:
    """HEAD con fallback a GET. Devuelve (status_code, latency_ms)."""
    import time as _time
    for method in (requests.head, requests.get):
        try:
            t0 = _time.monotonic()
            r = method(url, timeout=timeout, allow_redirects=True)
            latency = (_time.monotonic() - t0) * 1000
            return r.status_code, latency
        except Exception:
            continue
    return -1, 0.0


# ═══ LOVBOT ECOSYSTEM ════════════════════════════════════════════════════════


# ── Check 2: agentes.lovbot.ai health ─────────────────────────────────────────

def _check_backend_lovbot() -> dict:
    """
    Verifica que el backend FastAPI de Robert (Hetzner) responda.
    Intenta /health primero; si 404, acepta cualquier respuesta del servidor
    (200 o 404 en / indica que el proceso está vivo).
    """
    # Intentar /health
    status_health, _ = _get(f"{LOVBOT_BACKEND_URL}/health")
    if status_health == 200:
        return {"ok": True, "detalle": f"agentes.lovbot.ai /health OK (200)"}
    if status_health == 404:
        # /health no existe pero el servidor responde — verificar raiz
        status_root, _ = _get(f"{LOVBOT_BACKEND_URL}/")
        if status_root in (200, 404, 422):
            return {"ok": True,
                    "detalle": f"agentes.lovbot.ai responde (/ HTTP {status_root}, /health 404 — ruta no definida)"}
        return {"ok": False, "tipo": "backend_caido",
                "detalle": f"agentes.lovbot.ai / devolvio HTTP {status_root}"}
    if status_health == -1:
        return {"ok": False, "tipo": "backend_inaccesible",
                "detalle": "agentes.lovbot.ai no responde (timeout/conexion rechazada)"}
    # Otros status inesperados
    return {"ok": False, "tipo": "backend_error",
            "detalle": f"agentes.lovbot.ai HTTP {status_health}"}


# ── Check 3: Resend API + domain verification ──────────────────────────────────

def _check_resend() -> dict:
    """
    Verifica que la API key de Resend sea valida y que lovbot.ai
    aparezca con status verified.
    """
    if not LOVBOT_RESEND_API_KEY:
        return {"ok": None, "detalle": "LOVBOT_RESEND_API_KEY no configurada — skip"}

    status, data = _get(
        "https://api.resend.com/domains",
        headers={"Authorization": f"Bearer {LOVBOT_RESEND_API_KEY}"},
    )

    if status == 401:
        return {"ok": False, "tipo": "resend_token_invalido",
                "detalle": "Resend API key invalida o revocada (401)"}
    if status != 200:
        return {"ok": False, "tipo": "resend_error",
                "detalle": f"Resend API HTTP {status}"}

    # data puede ser lista o dict con key "data"
    dominios = data if isinstance(data, list) else (data or {}).get("data", [])

    if not dominios:
        return {"ok": False, "tipo": "resend_sin_dominios",
                "detalle": "Resend: 0 dominios configurados"}

    # Buscar lovbot.ai
    dominio_encontrado = None
    for d in dominios:
        name = (d.get("name") or "").lower()
        if RESEND_DOMAIN_ESPERADO in name:
            dominio_encontrado = d
            break

    if dominio_encontrado is None:
        nombres = [d.get("name", "?") for d in dominios]
        return {"ok": False, "tipo": "resend_dominio_faltante",
                "detalle": f"{RESEND_DOMAIN_ESPERADO} no encontrado — dominios: {', '.join(nombres)}"}

    resend_status = dominio_encontrado.get("status", "unknown")
    if resend_status != "verified":
        return {"ok": False, "tipo": "resend_dominio_no_verificado",
                "detalle": f"{RESEND_DOMAIN_ESPERADO} status={resend_status} (esperado: verified)"}

    return {"ok": True,
            "detalle": f"Resend OK — {RESEND_DOMAIN_ESPERADO} verified, {len(dominios)} dominio(s) total"}


# ── Check 4: Chatwoot Lovbot ───────────────────────────────────────────────────

def _check_chatwoot_lovbot() -> dict:
    """
    Verifica que la instancia Chatwoot de Lovbot responda y tenga al menos
    1 agente configurado en la cuenta indicada.
    """
    if not LOVBOT_CHATWOOT_TOKEN:
        return {"ok": None, "detalle": "LOVBOT_CHATWOOT_API_TOKEN no configurado — skip"}

    url = f"{LOVBOT_CHATWOOT_URL}/api/v1/accounts/{LOVBOT_CHATWOOT_ACCOUNT}/agents"
    status, data = _get(url, headers={"api_access_token": LOVBOT_CHATWOOT_TOKEN})

    if status == 401:
        return {"ok": False, "tipo": "chatwoot_token_invalido",
                "detalle": f"Chatwoot Lovbot token invalido (401)"}
    if status == 404:
        return {"ok": False, "tipo": "chatwoot_cuenta_no_encontrada",
                "detalle": f"Chatwoot Lovbot cuenta {LOVBOT_CHATWOOT_ACCOUNT} no encontrada (404)"}
    if status != 200:
        return {"ok": False, "tipo": "chatwoot_error",
                "detalle": f"Chatwoot Lovbot HTTP {status}"}
    if status == -1:
        return {"ok": False, "tipo": "chatwoot_inaccesible",
                "detalle": f"Chatwoot Lovbot no responde ({LOVBOT_CHATWOOT_URL})"}

    agentes = data if isinstance(data, list) else []
    if len(agentes) == 0:
        return {"ok": False, "tipo": "chatwoot_sin_agentes",
                "detalle": "Chatwoot Lovbot: 0 agentes en la cuenta"}

    nombres = [a.get("name", "?") for a in agentes[:3]]
    return {"ok": True,
            "detalle": f"Chatwoot Lovbot OK — {len(agentes)} agente(s): {', '.join(nombres)}"}


# ── Check 6: Vercel projects ───────────────────────────────────────────────────

def _check_vercel_projects() -> dict:
    """
    Verifica que las 5 URLs criticas de Lovbot en Vercel respondan HTTP 200.
    Reporta cuales fallan con su latencia.
    """
    fallos = []
    ok_list = []

    for nombre, url in VERCEL_URLS:
        status, latency_ms = _head_or_get(url, timeout=8)
        if status == 200:
            ok_list.append(f"{nombre} ({latency_ms:.0f}ms)")
        else:
            fallos.append(f"{nombre}: HTTP {status if status != -1 else 'timeout'}")

    if fallos:
        return {"ok": False, "tipo": "vercel_caido",
                "detalle": "Vercel fallos: " + " | ".join(fallos)}

    return {"ok": True,
            "detalle": f"Vercel OK — {len(ok_list)}/{len(VERCEL_URLS)} URLs: {', '.join(ok_list)}"}


# ── Runner ────────────────────────────────────────────────────────────────────

def run() -> dict:
    checks_raw = {
        "Backend agentes.lovbot.ai": _check_backend_lovbot(),
        "Resend API + dominio":      _check_resend(),
        "Chatwoot Lovbot":           _check_chatwoot_lovbot(),
        "Vercel projects":           _check_vercel_projects(),
    }

    alertas = []
    detalle = {}

    for nombre, c in checks_raw.items():
        detalle[nombre] = c["detalle"]
        ok_val = c["ok"]
        if ok_val is False:  # None = skip, no se alerta
            alertas.append({
                "nombre":  nombre,
                "tipo":    c.get("tipo", "desconocido"),
                "detalle": c["detalle"],
            })

    return {
        "auditor": "lovbot_ecosystem",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": detalle,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
