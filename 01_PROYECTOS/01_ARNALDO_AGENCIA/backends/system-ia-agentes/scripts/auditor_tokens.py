"""
Auditor de Tokens — Fase 2.3
==============================
Verifica vencimiento de tokens críticos del ecosistema.
Chequea: LinkedIn Arnaldo, LinkedIn Mica, Gemini API, Airtable.

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas:
    LINKEDIN_EXPIRY_ARNALDO  → fecha vencimiento token LinkedIn Arnaldo (ISO: YYYY-MM-DD)
    LINKEDIN_EXPIRY_MICA     → fecha vencimiento token LinkedIn Mica (ISO: YYYY-MM-DD)
    GEMINI_API_KEY           → API key Gemini (test de accesibilidad)
    AIRTABLE_API_KEY         → API key Airtable (test de accesibilidad)

Severidades LinkedIn:
    ≤3d  → crítico 🔴
    ≤7d  → urgente 🟠
    ≤14d → importante 🟡
    ≤30d → aviso 🔵
"""

import os
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()  # en container las vars vienen del entorno Coolify

LINKEDIN_EXPIRY_ARNALDO = os.getenv("LINKEDIN_EXPIRY_ARNALDO", "")
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


def _check_linkedin(nombre: str, fecha_str: str) -> dict:
    if not fecha_str:
        return {"token": f"LinkedIn {nombre}", "ok": True,
                "detalle": "fecha no configurada — skip"}
    try:
        vence = datetime.date.fromisoformat(fecha_str)
    except ValueError:
        return {"token": f"LinkedIn {nombre}", "ok": False,
                "tipo": "config_invalida",
                "detalle": f"LINKEDIN_EXPIRY_{nombre.upper()} tiene formato inválido: {fecha_str}"}

    hoy  = datetime.date.today()
    dias = (vence - hoy).days

    if dias < 0:
        return {"token": f"LinkedIn {nombre}", "ok": False,
                "tipo": "token_vencido",
                "detalle": f"venció hace {abs(dias)} días ({fecha_str})"}

    for umbral, severidad, icono in UMBRALES:
        if dias <= umbral:
            return {"token": f"LinkedIn {nombre}", "ok": False,
                    "tipo": "token_por_vencer",
                    "detalle": f"{icono} {severidad} — {dias} días restantes (vence {fecha_str})"}

    return {"token": f"LinkedIn {nombre}", "ok": True,
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
        _check_linkedin("Arnaldo", LINKEDIN_EXPIRY_ARNALDO),
        _check_linkedin("Mica",    LINKEDIN_EXPIRY_MICA),
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
