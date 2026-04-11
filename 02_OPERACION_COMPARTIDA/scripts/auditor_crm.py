"""
Auditor CRM — Fase 2.5
=======================
Verifica el estado de las bases de datos CRM de todos los proyectos.

Checks:
    1. Supabase tenants — alerta si vence en ≤1 día o ya vencido/suspendido
    2. Airtable Maicol  — base accesible (AIRTABLE_TOKEN_MAICOL + AIRTABLE_BASE_ID_MAICOL)
    3. Airtable Lau     — base accesible (AIRTABLE_API_KEY + LAU_AIRTABLE_BASE_ID)
    4. Airtable Robert  — base accesible (AIRTABLE_API_KEY + ROBERT_AIRTABLE_BASE)
    5. Airtable Mica    — base accesible (AIRTABLE_API_KEY + MICA_AIRTABLE_BASE_ID)

Interfaz estándar:
    run() -> dict con keys: auditor, ok, alertas[], detalle{}

Variables de entorno requeridas:
    SUPABASE_URL, SUPABASE_KEY
    AIRTABLE_TOKEN_MAICOL, AIRTABLE_BASE_ID_MAICOL
    AIRTABLE_API_KEY
    LAU_AIRTABLE_BASE_ID
    ROBERT_AIRTABLE_BASE
    MICA_AIRTABLE_BASE_ID
"""

import os
import time
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL  = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY  = os.getenv("SUPABASE_KEY", "")

AIRTABLE_TOKEN_MAICOL   = os.getenv("AIRTABLE_TOKEN_MAICOL", "")
AIRTABLE_BASE_MAICOL    = os.getenv("AIRTABLE_BASE_ID_MAICOL", "")

AIRTABLE_API_KEY        = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_LAU       = os.getenv("LAU_AIRTABLE_BASE_ID", "")
AIRTABLE_BASE_ROBERT    = os.getenv("ROBERT_AIRTABLE_BASE", "")
AIRTABLE_BASE_MICA      = os.getenv("MICA_AIRTABLE_BASE_ID", "")

REQUEST_TIMEOUT = 10
RETRY_WAIT      = 5
# Días de anticipación para alertar vencimiento
ALERT_DAYS_BEFORE = 1


def _get(url: str, headers: dict, params: dict = None) -> tuple[int, dict]:
    """GET con 1 retry."""
    for intento in range(2):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            return r.status_code, r.json()
        except Exception as e:
            if intento == 0:
                time.sleep(RETRY_WAIT)
            else:
                raise


# ── Supabase tenants ──────────────────────────────────────────────────────────

def _check_supabase_tenants() -> dict:
    """Verifica estado y vencimiento de todos los tenants en Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"ok": True, "detalle": "SUPABASE_URL/KEY no configurados — skip"}

    try:
        status, data = _get(
            f"{SUPABASE_URL}/rest/v1/tenants",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            params={"select": "slug,nombre,estado_pago,fecha_vence"},
        )

        if status != 200:
            return {"ok": False, "tipo": "supabase_error",
                    "detalle": f"HTTP {status} al consultar tenants"}

        if not isinstance(data, list):
            return {"ok": False, "tipo": "supabase_error",
                    "detalle": f"respuesta inesperada: {str(data)[:100]}"}

        hoy = datetime.date.today()
        alertas_internas = []
        resumen = []

        for tenant in data:
            slug        = tenant.get("slug", "?")
            nombre      = tenant.get("nombre", slug)
            estado_pago = tenant.get("estado_pago", "?")
            fecha_str   = tenant.get("fecha_vence")

            # Alerta si ya suspendido/vencido por estado
            if estado_pago in ("suspendido", "vencido"):
                alertas_internas.append(
                    f"tenant '{nombre}' ({slug}) — estado_pago={estado_pago}"
                )

            # Alerta por fecha de vencimiento
            if fecha_str:
                try:
                    fecha_vence = datetime.date.fromisoformat(fecha_str[:10])
                    dias_restantes = (fecha_vence - hoy).days
                    if dias_restantes < 0:
                        alertas_internas.append(
                            f"tenant '{nombre}' ({slug}) — vencido hace {abs(dias_restantes)} día(s)"
                        )
                    elif dias_restantes <= ALERT_DAYS_BEFORE:
                        alertas_internas.append(
                            f"tenant '{nombre}' ({slug}) — vence en {dias_restantes} día(s) ({fecha_str[:10]})"
                        )
                    resumen.append(f"{nombre}: vence {fecha_str[:10]} ({dias_restantes}d)")
                except ValueError:
                    resumen.append(f"{nombre}: fecha inválida ({fecha_str})")
            else:
                resumen.append(f"{nombre}: sin fecha_vence")

        if alertas_internas:
            return {"ok": False, "tipo": "tenant_vencimiento",
                    "detalle": " | ".join(alertas_internas)}

        return {"ok": True, "detalle": f"{len(data)} tenants OK — " + ", ".join(resumen)}

    except Exception as e:
        return {"ok": False, "tipo": "supabase_inaccesible",
                "detalle": f"error consultando Supabase: {e}"}


# ── Airtable bases ────────────────────────────────────────────────────────────

def _check_airtable_base(nombre: str, token: str, base_id: str) -> dict:
    """Verifica que una base de Airtable sea accesible via /meta/bases/{id}/tables."""
    if not token or not base_id:
        return {"ok": True, "detalle": f"{nombre}: vars no configuradas — skip"}

    try:
        status, data = _get(
            f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
            headers={"Authorization": f"Bearer {token}"},
        )
        if status == 200:
            tablas = len(data.get("tables", []))
            return {"ok": True, "detalle": f"{nombre}: {tablas} tabla(s) accesibles"}
        elif status == 401:
            return {"ok": False, "tipo": "airtable_token_invalido",
                    "detalle": f"{nombre}: token inválido o vencido (401)"}
        elif status == 403:
            return {"ok": False, "tipo": "airtable_sin_acceso",
                    "detalle": f"{nombre}: sin acceso a base {base_id} (403)"}
        elif status == 404:
            return {"ok": False, "tipo": "airtable_base_no_existe",
                    "detalle": f"{nombre}: base {base_id} no encontrada (404)"}
        else:
            return {"ok": False, "tipo": "airtable_error",
                    "detalle": f"{nombre}: HTTP {status}"}
    except Exception as e:
        return {"ok": False, "tipo": "airtable_inaccesible",
                "detalle": f"{nombre}: error de conexión — {e}"}


# ── Runner ────────────────────────────────────────────────────────────────────

def run() -> dict:
    checks = {
        "Supabase tenants": _check_supabase_tenants(),
        "Airtable Maicol":  _check_airtable_base("Maicol", AIRTABLE_TOKEN_MAICOL, AIRTABLE_BASE_MAICOL),
        "Airtable Lau":     _check_airtable_base("Lau", AIRTABLE_API_KEY, AIRTABLE_BASE_LAU),
        "Airtable Robert":  _check_airtable_base("Robert", AIRTABLE_API_KEY, AIRTABLE_BASE_ROBERT),
        "Airtable Mica":    _check_airtable_base("Mica", AIRTABLE_API_KEY, AIRTABLE_BASE_MICA),
    }

    alertas = [
        {"nombre": nombre, "tipo": c.get("tipo", "desconocido"), "detalle": c["detalle"]}
        for nombre, c in checks.items()
        if not c["ok"]
    ]

    return {
        "auditor": "crm",
        "ok":      len(alertas) == 0,
        "alertas": alertas,
        "detalle": {nombre: c["detalle"] for nombre, c in checks.items()},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, ensure_ascii=False))
