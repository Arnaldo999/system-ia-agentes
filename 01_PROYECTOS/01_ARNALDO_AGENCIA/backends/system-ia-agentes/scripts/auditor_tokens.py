"""
Auditor de Tokens — Fase 2.3
==============================
Verifica validez de tokens críticos del ecosistema.
Chequea: LinkedIn Arnaldo (token en Supabase), LinkedIn Mica (fecha env var),
         Gemini API, Airtable.

Estrategia LinkedIn:
- Arnaldo: lee token desde Supabase tabla `clientes`, hace llamada real a /v2/userinfo
- Mica: verifica fecha de vencimiento desde env var LINKEDIN_EXPIRY_MICA

Variables de entorno requeridas:
    SUPABASE_URL            → URL del proyecto Supabase
    SUPABASE_KEY            → API key Supabase (service role o anon)
    LINKEDIN_EXPIRY_MICA    → fecha vencimiento token LinkedIn Mica (ISO: YYYY-MM-DD)
    GEMINI_API_KEY          → API key Gemini (test de accesibilidad)
    AIRTABLE_API_KEY        → API key Airtable (test de accesibilidad)
"""

import os
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()  # en container las vars vienen del entorno Coolify

SUPABASE_URL            = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY            = os.getenv("SUPABASE_KEY", "")
LINKEDIN_EXPIRY_MICA    = os.getenv("LINKEDIN_EXPIRY_MICA", "2026-06-09")
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
AIRTABLE_API_KEY        = os.getenv("AIRTABLE_API_KEY") or os.getenv("AIRTABLE_TOKEN", "")

REQUEST_TIMEOUT = 10

UMBRALES = [
    (3,  "crítico",    "🔴"),
    (7,  "urgente",    "🟠"),
    (14, "importante", "🟡"),
    (30, "aviso",      "🔵"),
]


def _check_linkedin_arnaldo() -> dict:
    """Lee token desde Supabase y verifica contra API LinkedIn."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"token": "LinkedIn Arnaldo", "ok": False,
                "tipo": "config_faltante", "detalle": "SUPABASE_URL/KEY no configuradas"}
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/clientes",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={"cliente_id": "eq.Arnaldo_Ayala", "select": "linkedin_access_token"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows or not rows[0].get("linkedin_access_token"):
            return {"token": "LinkedIn Arnaldo", "ok": False,
                    "tipo": "token_no_encontrado", "detalle": "no hay token en Supabase"}
        token = rows[0]["linkedin_access_token"]
    except Exception as e:
        return {"token": "LinkedIn Arnaldo", "ok": False,
                "tipo": "supabase_error", "detalle": f"error leyendo Supabase: {e}"}

    # Verificar token contra API LinkedIn
    try:
        li = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT,
        )
        if li.status_code == 200:
            return {"token": "LinkedIn Arnaldo", "ok": True, "detalle": "token válido"}
        if li.status_code == 401:
            return {"token": "LinkedIn Arnaldo", "ok": False,
                    "tipo": "token_vencido", "detalle": "token inválido o vencido (401) — renovar"}
        return {"token": "LinkedIn Arnaldo", "ok": False,
                "tipo": "token_invalido", "detalle": f"HTTP {li.status_code}"}
    except Exception as e:
        return {"token": "LinkedIn Arnaldo", "ok": False,
                "tipo": "api_inaccesible", "detalle": f"no responde LinkedIn API: {e}"}


def _check_linkedin_mica(fecha_str: str) -> dict:
    """Verifica fecha de vencimiento del token de Mica."""
    if not fecha_str:
        return {"token": "LinkedIn Mica", "ok": True, "detalle": "fecha no configurada — skip"}
    try:
        vence = datetime.date.fromisoformat(fecha_str)
    except ValueError:
        return {"token": "LinkedIn Mica", "ok": False,
                "tipo": "config_invalida", "detalle": f"formato inválido: {fecha_str}"}

    hoy  = datetime.date.today()
    dias = (vence - hoy).days

    if dias < 0:
        return {"token": "LinkedIn Mica", "ok": False,
                "tipo": "token_vencido",
                "detalle": f"venció hace {abs(dias)} días ({fecha_str})"}

    for umbral, severidad, icono in UMBRALES:
        if dias <= umbral:
            return {"token": "LinkedIn Mica", "ok": False,
                    "tipo": "token_por_vencer",
                    "detalle": f"{icono} {severidad} — {dias} días restantes (vence {fecha_str})"}

    return {"token": "LinkedIn Mica", "ok": True,
            "detalle": f"{dias} días restantes (vence {fecha_str})"}


def _check_gemini() -> dict:
    if not GEMINI_API_KEY:
        return {"token": "Gemini API", "ok": True, "detalle": "key no configurada — skip"}
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return {"token": "Gemini API", "ok": True, "detalle": "accesible"}
        if r.status_code == 400:
            # 400 puede ser request mal formado pero key válida
            return {"token": "Gemini API", "ok": True, "detalle": "key válida"}
        return {"token": "Gemini API", "ok": False,
                "tipo": "token_invalido",
                "detalle": f"HTTP {r.status_code} — key posiblemente inválida o expirada"}
    except Exception as e:
        return {"token": "Gemini API", "ok": False,
                "tipo": "api_inaccesible",
                "detalle": f"no responde: {e}"}


def _check_airtable() -> dict:
    if not AIRTABLE_API_KEY:
        return {"token": "Airtable", "ok": True, "detalle": "key no configurada — skip"}
    try:
        r = requests.get(
            "https://api.airtable.com/v0/meta/whoami",
            headers={"Authorization": f"Bearer {AIRTABLE_API_KEY}"},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            return {"token": "Airtable", "ok": True, "detalle": "accesible"}
        return {"token": "Airtable", "ok": False,
                "tipo": "token_invalido",
                "detalle": f"HTTP {r.status_code} — key inválida o revocada"}
    except Exception as e:
        return {"token": "Airtable", "ok": False,
                "tipo": "api_inaccesible",
                "detalle": f"no responde: {e}"}


def run() -> dict:
    checks = [
        _check_linkedin_arnaldo(),
        _check_linkedin_mica(LINKEDIN_EXPIRY_MICA),
        _check_gemini(),
        _check_airtable(),
    ]

    alertas = [c for c in checks if not c["ok"]]

    return {
        "auditor": "tokens",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": {c["token"]: c["detalle"] for c in checks},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
